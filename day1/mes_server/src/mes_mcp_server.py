#!/usr/bin/env python3
"""
MES MCP Server - Press 103

A domain-specific MCP server for AI agents to execute MES (Manufacturing Execution
System) objectives on Press 103. Unlike generic data access servers, this server
exposes MES-domain tools that map directly to manufacturing operations.

Architecture:
    - MQTT: Subscribe to Press 103 topics, cache to mes_cache.json
    - MySQL: Connection pool to mes_lite database for historical data
    - Tools combine real-time UNS data with historical MySQL data

Tools:
    - get_equipment_status: Is Press 103 running? Current state and speed?
    - get_active_work_order: What are we making? Progress toward target?
    - get_oee_summary: A/P/Q breakdown, current performance metrics
    - get_downtime_summary: Why down? Top reasons? Pareto analysis
    - log_observation: Record agent observation (write to UNS)
"""

import asyncio
import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any
import threading

import paho.mqtt.client as mqtt
from paho.mqtt.reasoncodes import ReasonCode
import mysql.connector
from mysql.connector import pooling, Error as MySQLError
from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================
# All logs go to stderr (stdout reserved for MCP protocol)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("mes-mcp-server")

# =============================================================================
# ENVIRONMENT LOADING
# =============================================================================
# Load from root .env file (three directories up from src/)
env_path = Path(__file__).parent.parent.parent.parent / ".env"
load_dotenv(env_path)
logger.info(f"Loading environment from: {env_path}")

# =============================================================================
# MQTT CONFIGURATION
# =============================================================================
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")

# Unique client ID to prevent collisions
MQTT_CLIENT_ID = f"mes-press103-{uuid.uuid4().hex[:8]}"

# =============================================================================
# MYSQL CONFIGURATION
# =============================================================================
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USERNAME = os.getenv("MYSQL_USERNAME", "")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = "mes_lite"

# =============================================================================
# PRESS 103 CONSTANTS
# =============================================================================
PRESS_103_LINE_ID = 1
PRESS_103_UNS_BASE = "Enterprise/Dallas/Press/Press 103"
MQTT_SUBSCRIBE_TOPIC = f"{PRESS_103_UNS_BASE}/#"

# Cache file for MQTT messages
CACHE_FILE = Path(__file__).parent / "mes_cache.json"

# =============================================================================
# KEY UNS TOPIC PATHS (relative to PRESS_103_UNS_BASE)
# =============================================================================
TOPIC_RUNNING = f"{PRESS_103_UNS_BASE}/Dashboard/Running"
TOPIC_STATE = f"{PRESS_103_UNS_BASE}/Line/State"
TOPIC_MACHINE_SPEED = f"{PRESS_103_UNS_BASE}/MQTT/Dashboard Machine Speed"
TOPIC_RATE_SETPOINT = f"{PRESS_103_UNS_BASE}/Line/Rate Setpoint"
TOPIC_SHIFT_NAME = f"{PRESS_103_UNS_BASE}/Dashboard/Shift Name"
TOPIC_OEE = f"{PRESS_103_UNS_BASE}/Line/OEE/OEE"
TOPIC_OEE_AVAILABILITY = f"{PRESS_103_UNS_BASE}/Line/OEE/OEE Availability"
TOPIC_OEE_PERFORMANCE = f"{PRESS_103_UNS_BASE}/Line/OEE/OEE Performance"
TOPIC_OEE_QUALITY = f"{PRESS_103_UNS_BASE}/Line/OEE/OEE Quality"
TOPIC_GOOD_COUNT = f"{PRESS_103_UNS_BASE}/Line/OEE/Good Count"
TOPIC_BAD_COUNT = f"{PRESS_103_UNS_BASE}/Line/OEE/Bad Count"
TOPIC_TARGET_COUNT = f"{PRESS_103_UNS_BASE}/Line/OEE/Target Count"
TOPIC_WORK_ORDER = f"{PRESS_103_UNS_BASE}/Line/OEE/WorkOrder"
TOPIC_RUN_ID = f"{PRESS_103_UNS_BASE}/Line/OEE/RunID"
TOPIC_RUNTIME = f"{PRESS_103_UNS_BASE}/Line/OEE/Runtime"
TOPIC_UNPLANNED_DOWNTIME = f"{PRESS_103_UNS_BASE}/Line/OEE/Unplanned Downtime"
TOPIC_AGENT_OBSERVATIONS = f"{PRESS_103_UNS_BASE}/Agent/Observations"


# =============================================================================
# MYSQL CONNECTION POOL
# =============================================================================
db_pool = None

def init_db_pool():
    """Initialize the MySQL connection pool."""
    global db_pool
    try:
        db_pool = pooling.MySQLConnectionPool(
            pool_name="mes_pool",
            pool_size=3,
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USERNAME,
            password=MYSQL_PASSWORD,
            database=MYSQL_DATABASE,
            autocommit=True,
        )
        logger.info(f"MySQL connection pool created for {MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}")
        return True
    except MySQLError as e:
        logger.error(f"Failed to create MySQL connection pool: {e}")
        return False


def execute_query(query: str, params: tuple = None) -> list[dict]:
    """Execute a read-only query and return results as list of dicts."""
    if db_pool is None:
        raise ConnectionError("MySQL connection pool not initialized")
    
    conn = None
    cursor = None
    try:
        conn = db_pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query, params)
        results = cursor.fetchall()
        logger.debug(f"Query returned {len(results)} rows")
        return results
    except MySQLError as e:
        logger.error(f"MySQL query error: {e}")
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# =============================================================================
# MQTT CLIENT WRAPPER (adapted from mqtt_mcp_server.py)
# =============================================================================
class MQTTClientWrapper:
    """MQTT client with file-based caching, scoped to Press 103."""

    def __init__(self):
        """Initialize MQTT client with v2.0+ API."""
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=MQTT_CLIENT_ID,
            protocol=mqtt.MQTTv311,
            clean_session=True,
        )
        self.connected = False
        self._reconnect_count = 0
        self._cache_lock = threading.Lock()
        self._message_count = 0

        # Set up callbacks
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

        # Set credentials
        if MQTT_USERNAME and MQTT_PASSWORD:
            self.client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

        # Configure reconnection backoff
        self.client.reconnect_delay_set(min_delay=1, max_delay=120)

        # Initialize cache file
        self._init_cache()

    def _init_cache(self):
        """Initialize cache file if it doesn't exist."""
        with self._cache_lock:
            try:
                if not CACHE_FILE.exists():
                    with open(CACHE_FILE, 'w') as f:
                        json.dump({}, f)
                    logger.info(f"Created new cache file: {CACHE_FILE}")
                else:
                    try:
                        with open(CACHE_FILE, 'r') as f:
                            cache = json.load(f)
                        logger.info(f"Loaded existing cache with {len(cache)} topics")
                    except (json.JSONDecodeError, Exception):
                        with open(CACHE_FILE, 'w') as f:
                            json.dump({}, f)
                        logger.warning("Cache file was corrupted, starting fresh")
            except Exception as e:
                logger.error(f"Failed to initialize cache file: {e}")

    def _read_cache(self) -> dict[str, Any]:
        """Read the current cache from file."""
        with self._cache_lock:
            try:
                if CACHE_FILE.exists():
                    with open(CACHE_FILE, 'r') as f:
                        return json.load(f)
            except json.JSONDecodeError:
                logger.warning("Cache file corrupted, returning empty cache")
            except Exception as e:
                logger.error(f"Failed to read cache file: {e}")
            return {}

    def _write_to_cache(self, topic: str, value: str):
        """Write/update a single topic value in the cache file."""
        with self._cache_lock:
            try:
                cache = {}
                if CACHE_FILE.exists():
                    try:
                        with open(CACHE_FILE, 'r') as f:
                            cache = json.load(f)
                    except (json.JSONDecodeError, Exception):
                        cache = {}

                cache[topic] = {
                    "value": value,
                    "timestamp": time.time(),
                }

                # Atomic write
                temp_file = CACHE_FILE.with_suffix('.tmp')
                with open(temp_file, 'w') as f:
                    json.dump(cache, f)
                temp_file.replace(CACHE_FILE)

            except Exception as e:
                logger.error(f"Failed to write to cache file: {e}")

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        """Callback for when the client connects to the broker."""
        if reason_code == 0 or (isinstance(reason_code, ReasonCode) and reason_code.is_failure is False):
            self.connected = True
            if self._reconnect_count > 0:
                logger.info(f"Reconnected to MQTT broker (attempt {self._reconnect_count})")
            else:
                logger.info(f"Connected to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
            self._reconnect_count = 0

            # Subscribe ONLY to Press 103 topics
            result, mid = self.client.subscribe(MQTT_SUBSCRIBE_TOPIC, qos=1)
            if result == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"Subscribed to {MQTT_SUBSCRIBE_TOPIC}")
            else:
                logger.error(f"Failed to subscribe: {result}")
        else:
            logger.error(f"Connection failed: {reason_code}")

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        """Callback for when the client disconnects from the broker."""
        self.connected = False
        self._reconnect_count += 1
        # Cache persists across disconnections
        if reason_code == 0:
            logger.info("Disconnected from MQTT broker")
        else:
            logger.warning(f"Disconnected from MQTT broker: {reason_code} (will auto-reconnect)")

    def _on_message(self, client, userdata, message):
        """Callback for when a message is received - updates cache file."""
        try:
            payload = message.payload.decode("utf-8")
        except UnicodeDecodeError:
            payload = str(message.payload)

        self._write_to_cache(message.topic, payload)
        self._message_count += 1
        logger.debug(f"Cached: {message.topic}")

    def connect(self):
        """Connect to the MQTT broker."""
        try:
            logger.info(f"Connecting to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}...")
            logger.info(f"Client ID: {MQTT_CLIENT_ID}")
            logger.info(f"Subscription: {MQTT_SUBSCRIBE_TOPIC}")

            self.client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
            self.client.loop_start()

            # Wait for connection
            timeout = 10
            start = time.time()
            while not self.connected and (time.time() - start) < timeout:
                time.sleep(0.1)

            if not self.connected:
                logger.error("Failed to connect to MQTT broker within timeout")
                return False
            return True
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            return False

    def disconnect(self):
        """Disconnect from the MQTT broker."""
        self.client.loop_stop()
        self.client.disconnect()
        logger.info("Disconnected from MQTT broker (cache preserved)")

    def get_topic_value(self, topic: str) -> str | None:
        """Get a specific topic's cached value (just the value string)."""
        cache = self._read_cache()
        data = cache.get(topic)
        return data.get("value") if data else None

    def get_topic_data(self, topic: str) -> dict[str, Any] | None:
        """Get a specific topic's cached data (value + timestamp)."""
        cache = self._read_cache()
        return cache.get(topic)

    def get_all_topics(self) -> dict[str, Any]:
        """Get all cached topics."""
        return self._read_cache()

    async def publish_message(self, topic: str, payload: str, retain: bool = False, qos: int = 1) -> dict[str, Any]:
        """Publish a message to a topic."""
        if not self.connected:
            raise ConnectionError("Not connected to MQTT broker")

        if not topic or "#" in topic or "+" in topic:
            raise ValueError("Invalid topic")

        logger.info(f"Publishing to '{topic}': {payload[:100]}")
        result = self.client.publish(topic, payload, qos=qos, retain=retain)

        if qos > 0:
            result.wait_for_publish(timeout=10)

        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            return {"success": True, "topic": topic, "timestamp": time.time()}
        else:
            return {"success": False, "error": f"Publish failed: {result.rc}"}


# =============================================================================
# GLOBAL INSTANCES
# =============================================================================
mqtt_client = MQTTClientWrapper()
server = Server("mes-press103")


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================
def safe_float(value: str | None, default: float = 0.0) -> float:
    """Safely convert a value to float."""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int(value: str | None, default: int = 0) -> int:
    """Safely convert a value to int."""
    if value is None:
        return default
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default


def format_duration(minutes: float) -> str:
    """Format minutes into human-readable duration."""
    if minutes < 60:
        return f"{minutes:.1f} min"
    hours = minutes / 60
    if hours < 24:
        return f"{hours:.1f} hr"
    days = hours / 24
    return f"{days:.1f} days"


# =============================================================================
# MCP TOOL DEFINITIONS
# =============================================================================
@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available MES tools for Press 103."""
    return [
        Tool(
            name="get_equipment_status",
            description=(
                "Get the current operational status of Press 103. "
                "Returns: running state, current state code, speed vs setpoint, "
                "current shift, and connection status. "
                "Use this to answer 'What is Press 103 doing right now?'"
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="get_active_work_order",
            description=(
                "Get the currently active work order on Press 103. "
                "Returns: work order number, product code, target quantity, "
                "current good count, percent complete. "
                "Use this to answer 'What are we making?' or 'How close to target?'"
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="get_oee_summary",
            description=(
                "Get OEE (Overall Equipment Effectiveness) metrics for Press 103. "
                "Returns: current OEE percentage, Availability/Performance/Quality breakdown, "
                "good/bad counts, runtime, and downtime. "
                "Use this to answer 'How is Press 103 performing?'"
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="get_downtime_summary",
            description=(
                "Get downtime analysis for Press 103. "
                "Returns: current downtime state (if any), top downtime reasons (Pareto), "
                "total downtime minutes, planned vs unplanned breakdown. "
                "Use this to answer 'Why has Press 103 been down?' or 'What's causing losses?'"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "hours_back": {
                        "type": "integer",
                        "description": "How many hours back to analyze (default: 24)",
                        "default": 24,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="log_observation",
            description=(
                "Log an observation or note about Press 103 to the UNS. "
                "Use this to record insights, issues, or recommendations. "
                "The observation is published to the Agent/Observations topic."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "The observation message to log",
                    },
                    "category": {
                        "type": "string",
                        "description": "Optional category (e.g., 'quality', 'maintenance', 'safety')",
                        "default": "general",
                    },
                },
                "required": ["message"],
            },
        ),
    ]


# =============================================================================
# TOOL HANDLERS
# =============================================================================
@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Route tool calls to handlers."""
    if name == "get_equipment_status":
        return await handle_get_equipment_status(arguments)
    elif name == "get_active_work_order":
        return await handle_get_active_work_order(arguments)
    elif name == "get_oee_summary":
        return await handle_get_oee_summary(arguments)
    elif name == "get_downtime_summary":
        return await handle_get_downtime_summary(arguments)
    elif name == "log_observation":
        return await handle_log_observation(arguments)
    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def handle_get_equipment_status(arguments: dict[str, Any]) -> list[TextContent]:
    """
    Get current operational status of Press 103.
    
    Data sources: UNS cache (real-time)
    """
    try:
        # Read from UNS cache
        running = mqtt_client.get_topic_value(TOPIC_RUNNING)
        state = mqtt_client.get_topic_value(TOPIC_STATE)
        speed = mqtt_client.get_topic_value(TOPIC_MACHINE_SPEED)
        setpoint = mqtt_client.get_topic_value(TOPIC_RATE_SETPOINT)
        shift = mqtt_client.get_topic_value(TOPIC_SHIFT_NAME)

        # Determine running status
        is_running = str(running).lower() in ('true', '1', 'yes', 'running') if running else False
        running_text = "🟢 RUNNING" if is_running else "🔴 STOPPED"

        # Format speed comparison
        speed_val = safe_float(speed)
        setpoint_val = safe_float(setpoint)
        if setpoint_val > 0:
            speed_pct = (speed_val / setpoint_val) * 100
            speed_text = f"{speed_val:.1f} / {setpoint_val:.1f} ({speed_pct:.0f}% of setpoint)"
        else:
            speed_text = f"{speed_val:.1f} (no setpoint)"

        # Build output
        lines = [
            "═══ PRESS 103 STATUS ═══",
            "",
            f"Status: {running_text}",
            f"State Code: {state or 'Unknown'}",
            f"Speed: {speed_text}",
            f"Current Shift: {shift or 'Unknown'}",
            "",
            f"MQTT Connected: {'Yes' if mqtt_client.connected else 'No'}",
        ]

        return [TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        logger.exception("Error in get_equipment_status")
        return [TextContent(type="text", text=f"Error getting equipment status: {e}")]


async def handle_get_active_work_order(arguments: dict[str, Any]) -> list[TextContent]:
    """
    Get active work order information.
    
    Data sources: UNS cache (current WO number, counts) + MySQL (WO details)
    """
    try:
        # Get current work order from UNS
        wo_number = mqtt_client.get_topic_value(TOPIC_WORK_ORDER)
        good_count = safe_int(mqtt_client.get_topic_value(TOPIC_GOOD_COUNT))
        target_count = safe_int(mqtt_client.get_topic_value(TOPIC_TARGET_COUNT))
        run_id = mqtt_client.get_topic_value(TOPIC_RUN_ID)

        if not wo_number:
            return [TextContent(type="text", text="No active work order detected on Press 103.")]

        # Query MySQL for work order details
        wo_details = None
        try:
            query = """
                SELECT w.WorkOrder, w.ProductCode, w.Quantity, 
                       s.Quantity as ScheduledQty, s.ScheduleStartDateTime
                FROM mes_lite.workorder w
                JOIN mes_lite.schedule s ON s.WorkOrderID = w.ID
                WHERE w.WorkOrder = %s AND s.LineID = %s
                ORDER BY s.ScheduleStartDateTime DESC 
                LIMIT 1
            """
            results = execute_query(query, (wo_number, PRESS_103_LINE_ID))
            if results:
                wo_details = results[0]
        except Exception as e:
            logger.warning(f"Could not fetch work order details from MySQL: {e}")

        # Calculate progress
        if target_count > 0:
            pct_complete = (good_count / target_count) * 100
            remaining = target_count - good_count
        else:
            pct_complete = 0
            remaining = 0

        # Build output
        lines = [
            "═══ ACTIVE WORK ORDER ═══",
            "",
            f"Work Order: {wo_number}",
        ]

        if wo_details:
            lines.append(f"Product Code: {wo_details.get('ProductCode', 'N/A')}")
            lines.append(f"Order Quantity: {wo_details.get('Quantity', 'N/A')}")

        lines.extend([
            "",
            "─── Progress ───",
            f"Good Count: {good_count:,}",
            f"Target Count: {target_count:,}",
            f"Remaining: {remaining:,}",
            f"Complete: {pct_complete:.1f}%",
        ])

        if run_id:
            lines.append(f"Run ID: {run_id}")

        return [TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        logger.exception("Error in get_active_work_order")
        return [TextContent(type="text", text=f"Error getting work order: {e}")]


async def handle_get_oee_summary(arguments: dict[str, Any]) -> list[TextContent]:
    """
    Get OEE metrics for Press 103.
    
    Data sources: UNS cache (real-time OEE)
    """
    try:
        # Read OEE metrics from UNS
        oee = safe_float(mqtt_client.get_topic_value(TOPIC_OEE))
        availability = safe_float(mqtt_client.get_topic_value(TOPIC_OEE_AVAILABILITY))
        performance = safe_float(mqtt_client.get_topic_value(TOPIC_OEE_PERFORMANCE))
        quality = safe_float(mqtt_client.get_topic_value(TOPIC_OEE_QUALITY))
        good_count = safe_int(mqtt_client.get_topic_value(TOPIC_GOOD_COUNT))
        bad_count = safe_int(mqtt_client.get_topic_value(TOPIC_BAD_COUNT))
        runtime = safe_float(mqtt_client.get_topic_value(TOPIC_RUNTIME))
        downtime = safe_float(mqtt_client.get_topic_value(TOPIC_UNPLANNED_DOWNTIME))

        # Calculate totals
        total_count = good_count + bad_count
        quality_rate = (good_count / total_count * 100) if total_count > 0 else 0

        # OEE rating
        if oee >= 85:
            oee_rating = "🟢 World Class"
        elif oee >= 65:
            oee_rating = "🟡 Typical"
        elif oee >= 40:
            oee_rating = "🟠 Below Average"
        else:
            oee_rating = "🔴 Needs Improvement"

        # Build output
        lines = [
            "═══ OEE SUMMARY - PRESS 103 ═══",
            "",
            f"Overall OEE: {oee:.1f}%  {oee_rating}",
            "",
            "─── Components ───",
            f"  Availability: {availability:.1f}%",
            f"  Performance:  {performance:.1f}%",
            f"  Quality:      {quality:.1f}%",
            "",
            "─── Counts ───",
            f"  Good:  {good_count:,}",
            f"  Bad:   {bad_count:,}",
            f"  Total: {total_count:,}",
            "",
            "─── Time ───",
            f"  Runtime:  {format_duration(runtime)}",
            f"  Downtime: {format_duration(downtime)}",
        ]

        return [TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        logger.exception("Error in get_oee_summary")
        return [TextContent(type="text", text=f"Error getting OEE summary: {e}")]


async def handle_get_downtime_summary(arguments: dict[str, Any]) -> list[TextContent]:
    """
    Get downtime analysis for Press 103.
    
    Data sources: MySQL (historical downtime), UNS (current state)
    """
    try:
        hours_back = arguments.get("hours_back", 24)

        # Get current state from UNS
        current_state = mqtt_client.get_topic_value(TOPIC_STATE)
        is_running = str(mqtt_client.get_topic_value(TOPIC_RUNNING)).lower() in ('true', '1', 'yes', 'running')

        # Query MySQL for downtime Pareto
        pareto_data = []
        total_downtime = 0
        planned_downtime = 0
        unplanned_downtime = 0

        try:
            query = """
                SELECT 
                    COALESCE(sh.ReasonName, 'Unknown') as ReasonName,
                    sr.PlannedDowntime,
                    COUNT(*) as Events,
                    SUM(TIMESTAMPDIFF(MINUTE, sh.StartDateTime, 
                        COALESCE(sh.EndDateTime, NOW()))) as Minutes
                FROM mes_lite.statehistory sh
                LEFT JOIN mes_lite.statereason sr ON sh.StateReasonID = sr.ID
                WHERE sh.LineID = %s 
                  AND sh.StartDateTime >= DATE_SUB(NOW(), INTERVAL %s HOUR)
                GROUP BY sh.ReasonName, sr.PlannedDowntime
                ORDER BY Minutes DESC
                LIMIT 10
            """
            pareto_data = execute_query(query, (PRESS_103_LINE_ID, hours_back))

            # Calculate totals
            for row in pareto_data:
                minutes = row.get('Minutes') or 0
                total_downtime += minutes
                if row.get('PlannedDowntime'):
                    planned_downtime += minutes
                else:
                    unplanned_downtime += minutes

        except Exception as e:
            logger.warning(f"Could not fetch downtime data from MySQL: {e}")

        # Build output
        lines = [
            f"═══ DOWNTIME SUMMARY - PRESS 103 ═══",
            f"(Last {hours_back} hours)",
            "",
        ]

        # Current state
        if is_running:
            lines.append("Current State: 🟢 Running")
        else:
            lines.append(f"Current State: 🔴 Down ({current_state or 'Unknown reason'})")

        lines.extend([
            "",
            "─── Totals ───",
            f"  Total Downtime: {format_duration(total_downtime)}",
            f"  Planned:   {format_duration(planned_downtime)}",
            f"  Unplanned: {format_duration(unplanned_downtime)}",
        ])

        if pareto_data:
            lines.extend([
                "",
                "─── Top Reasons (Pareto) ───",
            ])
            for i, row in enumerate(pareto_data[:5], 1):
                reason = row.get('ReasonName', 'Unknown')
                minutes = row.get('Minutes') or 0
                events = row.get('Events') or 0
                pct = (minutes / total_downtime * 100) if total_downtime > 0 else 0
                planned = "P" if row.get('PlannedDowntime') else "U"
                lines.append(f"  {i}. {reason} [{planned}]: {format_duration(minutes)} ({events} events, {pct:.0f}%)")
        else:
            lines.append("\nNo downtime events recorded in this period.")

        return [TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        logger.exception("Error in get_downtime_summary")
        return [TextContent(type="text", text=f"Error getting downtime summary: {e}")]


async def handle_log_observation(arguments: dict[str, Any]) -> list[TextContent]:
    """
    Log an agent observation to the UNS.
    
    Data sources: UNS (write)
    """
    try:
        message = arguments.get("message")
        category = arguments.get("category", "general")

        if not message:
            return [TextContent(type="text", text="Error: 'message' parameter is required")]

        # Build payload
        payload = json.dumps({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "source": "mes-agent",
            "category": category,
            "message": message,
        })

        # Publish to observations topic
        result = await mqtt_client.publish_message(
            topic=TOPIC_AGENT_OBSERVATIONS,
            payload=payload,
            retain=False,
            qos=1,
        )

        if result.get("success"):
            lines = [
                "✓ Observation logged successfully!",
                "",
                f"Topic: {TOPIC_AGENT_OBSERVATIONS}",
                f"Category: {category}",
                f"Message: {message}",
                f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            ]
            return [TextContent(type="text", text="\n".join(lines))]
        else:
            return [TextContent(type="text", text=f"Failed to log observation: {result.get('error')}")]

    except Exception as e:
        logger.exception("Error in log_observation")
        return [TextContent(type="text", text=f"Error logging observation: {e}")]


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================
async def main():
    """Main entry point for the MES MCP Server."""
    logger.info("=" * 50)
    logger.info("Starting MES MCP Server - Press 103")
    logger.info("=" * 50)
    logger.info(f"MQTT Broker: {MQTT_BROKER}:{MQTT_PORT}")
    logger.info(f"MySQL Host: {MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}")
    logger.info(f"Press 103 Line ID: {PRESS_103_LINE_ID}")
    logger.info(f"UNS Base: {PRESS_103_UNS_BASE}")

    # Initialize MySQL connection pool
    if not init_db_pool():
        logger.warning("MySQL connection pool failed. Database tools may not work.")

    # Connect to MQTT broker
    if not mqtt_client.connect():
        logger.warning("MQTT connection failed. UNS tools may not work.")

    try:
        # Run the MCP server with stdio transport
        async with stdio_server() as (read_stream, write_stream):
            logger.info("MCP server running with stdio transport")
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )
    finally:
        # Clean up
        mqtt_client.disconnect()
        logger.info("MES MCP Server shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())

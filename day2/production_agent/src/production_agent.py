#!/usr/bin/env python3
"""
Production Agent - A2A Server for Press 103

FastAPI server implementing the A2A protocol for manufacturing data access.
Exposes Press 103 MES data through standardized A2A endpoints.

Endpoints:
    - GET  /.well-known/agent.json  → Agent Card (discovery)
    - POST /a2a/message/send         → Send message, route to skill
    - GET  /a2a/tasks/{task_id}      → Retrieve task results
    - GET  /a2a/skills/*             → Direct skill access
    - GET  /health                   → Health check

Skills:
    - get_equipment_status: Running state, speed, setpoint, shift
    - get_oee_summary: OEE breakdown (A/P/Q), counts
    - get_downtime_summary: Top downtime reasons
"""

import json
import logging
import os
import sys
import time
import uuid
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

import paho.mqtt.client as mqtt
from paho.mqtt.reasoncodes import ReasonCode
import mysql.connector
from mysql.connector import pooling, Error as MySQLError
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("production-agent")

# =============================================================================
# ENVIRONMENT LOADING
# =============================================================================
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
MQTT_CLIENT_ID = f"production-agent-{uuid.uuid4().hex[:8]}"

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
CACHE_FILE = Path(__file__).parent / "production_cache.json"

# =============================================================================
# UNS TOPICS
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
TOPIC_RUNTIME = f"{PRESS_103_UNS_BASE}/Line/OEE/Runtime"
TOPIC_UNPLANNED_DOWNTIME = f"{PRESS_103_UNS_BASE}/Line/OEE/Unplanned Downtime"

# =============================================================================
# PYDANTIC MODELS FOR A2A PROTOCOL
# =============================================================================
class MessagePart(BaseModel):
    type: str
    text: str

class Message(BaseModel):
    role: str
    parts: list[MessagePart]

class MessageRequest(BaseModel):
    message: Message

class Artifact(BaseModel):
    type: str = "application/json"
    data: dict

class Task(BaseModel):
    task_id: str
    state: str  # "completed", "failed"
    artifacts: list[Artifact] = []

# =============================================================================
# MYSQL CONNECTION POOL
# =============================================================================
db_pool = None

def init_db_pool():
    """Initialize the MySQL connection pool."""
    global db_pool
    try:
        db_pool = pooling.MySQLConnectionPool(
            pool_name="production_agent_pool",
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
# MQTT CLIENT WRAPPER
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

            # Subscribe to Press 103 topics
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
# SKILL FUNCTIONS
# =============================================================================
def get_equipment_status() -> dict:
    """
    Get current operational status of Press 103.
    Returns dict with running state, speed, setpoint, shift.
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

        # Calculate speed percentage
        speed_val = safe_float(speed)
        setpoint_val = safe_float(setpoint)
        speed_pct = (speed_val / setpoint_val * 100) if setpoint_val > 0 else 0.0

        return {
            "running": is_running,
            "state": state or "Unknown",
            "speed": speed_val,
            "setpoint": setpoint_val,
            "speed_percent": round(speed_pct, 1),
            "shift": shift or "Unknown",
            "mqtt_connected": mqtt_client.connected,
        }
    except Exception as e:
        logger.exception("Error in get_equipment_status")
        raise

def get_oee_summary() -> dict:
    """
    Get OEE metrics for Press 103.
    Returns dict with OEE breakdown, counts, runtime/downtime.
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

        total_count = good_count + bad_count

        # OEE rating
        if oee >= 85:
            rating = "World Class"
        elif oee >= 65:
            rating = "Typical"
        elif oee >= 40:
            rating = "Below Average"
        else:
            rating = "Needs Improvement"

        return {
            "oee": round(oee, 1),
            "availability": round(availability, 1),
            "performance": round(performance, 1),
            "quality": round(quality, 1),
            "good_count": good_count,
            "bad_count": bad_count,
            "total_count": total_count,
            "runtime_minutes": round(runtime, 1),
            "downtime_minutes": round(downtime, 1),
            "rating": rating,
        }
    except Exception as e:
        logger.exception("Error in get_oee_summary")
        raise

def get_downtime_summary(hours_back: int = 24) -> dict:
    """
    Get downtime analysis for Press 103.
    Returns dict with current state, downtime totals, top reasons.
    """
    try:
        # Get current state from UNS
        current_state = mqtt_client.get_topic_value(TOPIC_STATE)
        is_running = str(mqtt_client.get_topic_value(TOPIC_RUNNING)).lower() in ('true', '1', 'yes', 'running')

        # Query MySQL for downtime Pareto
        top_reasons = []
        total_downtime = 0.0
        planned_downtime = 0.0
        unplanned_downtime = 0.0

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

            # Calculate totals and build top reasons
            for row in pareto_data:
                minutes = row.get('Minutes') or 0
                total_downtime += minutes
                if row.get('PlannedDowntime'):
                    planned_downtime += minutes
                else:
                    unplanned_downtime += minutes
                
                top_reasons.append({
                    "reason": row.get('ReasonName', 'Unknown'),
                    "minutes": round(minutes, 1),
                    "events": row.get('Events', 0),
                    "planned": bool(row.get('PlannedDowntime')),
                })

        except Exception as e:
            logger.warning(f"Could not fetch downtime data from MySQL: {e}")

        return {
            "current_state": current_state or "Unknown",
            "is_running": is_running,
            "hours_analyzed": hours_back,
            "total_downtime_minutes": round(total_downtime, 1),
            "planned_minutes": round(planned_downtime, 1),
            "unplanned_minutes": round(unplanned_downtime, 1),
            "top_reasons": top_reasons[:5],  # Top 5
        }
    except Exception as e:
        logger.exception("Error in get_downtime_summary")
        raise

# =============================================================================
# SKILL ROUTING
# =============================================================================
def route_message_to_skill(message_text: str) -> tuple[str, dict]:
    """
    Route a message to the appropriate skill based on keywords.
    Returns (skill_name, skill_result).
    """
    text_lower = message_text.lower()
    
    # Check for OEE keywords
    if any(keyword in text_lower for keyword in ['oee', 'performance', 'availability', 'quality', 'count']):
        return "get_oee_summary", get_oee_summary()
    
    # Check for downtime keywords
    elif any(keyword in text_lower for keyword in ['downtime', 'down', 'stopped', 'reason', 'why']):
        return "get_downtime_summary", get_downtime_summary()
    
    # Default to equipment status
    else:
        return "get_equipment_status", get_equipment_status()

# =============================================================================
# FASTAPI APP
# =============================================================================
app = FastAPI(
    title="Production Agent",
    description="A2A server for Press 103 manufacturing data",
    version="1.0.0",
)

# Enable CORS for browser/Claude access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Task storage (in-memory for workshop demo)
task_storage: dict[str, Task] = {}

# Global MQTT client instance
mqtt_client = None

# =============================================================================
# STARTUP/SHUTDOWN EVENTS
# =============================================================================
@app.on_event("startup")
async def startup_event():
    """Initialize connections on startup."""
    global mqtt_client
    
    logger.info("=" * 50)
    logger.info("Starting Production Agent A2A Server")
    logger.info("=" * 50)
    logger.info(f"MQTT Broker: {MQTT_BROKER}:{MQTT_PORT}")
    logger.info(f"MySQL Host: {MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}")
    logger.info(f"Press 103 Line ID: {PRESS_103_LINE_ID}")
    logger.info(f"UNS Base: {PRESS_103_UNS_BASE}")
    
    # Initialize MySQL connection pool
    if not init_db_pool():
        logger.warning("MySQL connection pool failed. Database queries may not work.")
    
    # Connect to MQTT broker
    mqtt_client = MQTTClientWrapper()
    if not mqtt_client.connect():
        logger.warning("MQTT connection failed. Real-time data may not be available.")
    
    logger.info("Production Agent startup complete")

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up connections on shutdown."""
    if mqtt_client:
        mqtt_client.disconnect()
    logger.info("Production Agent shutdown complete")

# =============================================================================
# A2A ENDPOINTS
# =============================================================================
@app.get("/.well-known/agent.json")
async def get_agent_card():
    """Return the Agent Card describing this agent's identity and capabilities."""
    return {
        "name": "Production Agent",
        "description": "Monitors Press 103 equipment status, OEE, and production metrics for the Flexible Packaging line",
        "url": "http://localhost:8001",
        "version": "1.0.0",
        "provider": {
            "organization": "IIoT University"
        },
        "capabilities": {
            "streaming": False,
            "pushNotifications": False
        },
        "skills": [
            {
                "id": "get_equipment_status",
                "name": "Get Equipment Status",
                "description": "Returns current running state, speed, setpoint, and shift for Press 103",
                "inputModes": ["text/plain"],
                "outputModes": ["application/json"]
            },
            {
                "id": "get_oee_summary",
                "name": "Get OEE Summary",
                "description": "Returns OEE breakdown (Availability, Performance, Quality) and production counts",
                "inputModes": ["text/plain"],
                "outputModes": ["application/json"]
            },
            {
                "id": "get_downtime_summary",
                "name": "Get Downtime Summary",
                "description": "Returns downtime analysis with top reasons from the last 24 hours",
                "inputModes": ["text/plain"],
                "outputModes": ["application/json"]
            }
        ]
    }

@app.post("/a2a/message/send")
async def send_message(request: MessageRequest):
    """
    Receive a message, route to appropriate skill, return task with artifacts.
    """
    try:
        # Extract message text
        message_text = request.message.parts[0].text if request.message.parts else ""
        
        # Route to skill
        skill_name, skill_result = route_message_to_skill(message_text)
        
        # Create task
        task_id = str(uuid.uuid4())
        task = Task(
            task_id=task_id,
            state="completed",
            artifacts=[
                Artifact(
                    type="application/json",
                    data=skill_result
                )
            ]
        )
        
        # Store task
        task_storage[task_id] = task
        
        logger.info(f"Message routed to {skill_name}, task {task_id} created")
        
        return task.model_dump()
    
    except Exception as e:
        logger.exception("Error in send_message")
        task_id = str(uuid.uuid4())
        task = Task(
            task_id=task_id,
            state="failed",
            artifacts=[
                Artifact(
                    type="application/json",
                    data={"error": str(e)}
                )
            ]
        )
        task_storage[task_id] = task
        return task.model_dump()

@app.get("/a2a/tasks/{task_id}")
async def get_task(task_id: str):
    """Retrieve a previously created task by ID."""
    if task_id not in task_storage:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return task_storage[task_id].model_dump()

# =============================================================================
# DIRECT SKILL ENDPOINTS (Browser-Friendly)
# =============================================================================
@app.get("/a2a/skills/get_equipment_status")
async def skill_get_equipment_status():
    """Direct access to get_equipment_status skill."""
    try:
        data = get_equipment_status()
        return {
            "skill": "get_equipment_status",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "data": data
        }
    except Exception as e:
        logger.exception("Error in skill_get_equipment_status")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/a2a/skills/get_oee_summary")
async def skill_get_oee_summary():
    """Direct access to get_oee_summary skill."""
    try:
        data = get_oee_summary()
        return {
            "skill": "get_oee_summary",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "data": data
        }
    except Exception as e:
        logger.exception("Error in skill_get_oee_summary")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/a2a/skills/get_downtime_summary")
async def skill_get_downtime_summary(hours_back: int = 24):
    """Direct access to get_downtime_summary skill."""
    try:
        data = get_downtime_summary(hours_back=hours_back)
        return {
            "skill": "get_downtime_summary",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "data": data
        }
    except Exception as e:
        logger.exception("Error in skill_get_downtime_summary")
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# HEALTH CHECK
# =============================================================================
@app.get("/health")
async def health_check():
    """Return connection status and health information."""
    mysql_connected = False
    try:
        if db_pool:
            conn = db_pool.get_connection()
            mysql_connected = conn.is_connected()
            conn.close()
    except Exception:
        pass
    
    return {
        "status": "ok",
        "agent": "Production Agent",
        "mqtt_connected": mqtt_client.connected if mqtt_client else False,
        "mysql_connected": mysql_connected,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

# =============================================================================
# MAIN ENTRY POINT
# =============================================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

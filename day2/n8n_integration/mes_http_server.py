#!/usr/bin/env python3
"""
MES HTTP Server - Press 103

HTTP wrapper around MES functionality for N8N integration (Day 2, Session 3).
This exposes the same Press 103 data as the MCP server, but via REST endpoints.

Endpoints:
    GET  /health              - Health check
    GET  /equipment/status    - Current equipment status
    GET  /workorder/active    - Active work order
    GET  /oee/summary         - OEE metrics
    GET  /downtime/summary    - Downtime analysis
    POST /observation         - Log an observation

Usage:
    python mes_http_server.py
    
    Server runs on http://localhost:8001
"""

import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
import threading

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

import paho.mqtt.client as mqtt
from paho.mqtt.reasoncodes import ReasonCode
import mysql.connector
from mysql.connector import pooling, Error as MySQLError
from dotenv import load_dotenv

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("mes-http-server")

# =============================================================================
# ENVIRONMENT LOADING
# =============================================================================
# Load from root .env file (three directories up: n8n_integration -> day2 -> MCP_A2A_Workshop)
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)
logger.info(f"Loading environment from: {env_path}")

# =============================================================================
# MQTT CONFIGURATION
# =============================================================================
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
MQTT_CLIENT_ID = f"mes-http-test-{uuid.uuid4().hex[:8]}"

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
# KEY UNS TOPIC PATHS
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
# PYDANTIC MODELS
# =============================================================================
class ObservationRequest(BaseModel):
    message: str
    category: str = "general"

class HealthResponse(BaseModel):
    status: str
    mqtt_connected: bool
    mysql_connected: bool
    timestamp: str

class EquipmentStatusResponse(BaseModel):
    running: bool
    state: Optional[str]
    speed: float
    setpoint: float
    speed_percent: float
    shift: Optional[str]
    mqtt_connected: bool

class WorkOrderResponse(BaseModel):
    work_order: Optional[str]
    product_code: Optional[str]
    good_count: int
    target_count: int
    remaining: int
    percent_complete: float
    run_id: Optional[str]

class OEEResponse(BaseModel):
    oee: float
    availability: float
    performance: float
    quality: float
    good_count: int
    bad_count: int
    total_count: int
    runtime_minutes: float
    downtime_minutes: float
    rating: str

class DowntimeReason(BaseModel):
    reason: str
    minutes: float
    events: int
    percent: float
    planned: bool

class DowntimeResponse(BaseModel):
    current_state: str
    is_running: bool
    hours_analyzed: int
    total_downtime_minutes: float
    planned_minutes: float
    unplanned_minutes: float
    top_reasons: list[DowntimeReason]

class ObservationResponse(BaseModel):
    success: bool
    topic: str
    message: str
    category: str
    timestamp: str

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
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=MQTT_CLIENT_ID,
            protocol=mqtt.MQTTv311,
            clean_session=True,
        )
        self.connected = False
        self._cache_lock = threading.Lock()

        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

        if MQTT_USERNAME and MQTT_PASSWORD:
            self.client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

        self.client.reconnect_delay_set(min_delay=1, max_delay=120)
        self._init_cache()

    def _init_cache(self):
        with self._cache_lock:
            try:
                if not CACHE_FILE.exists():
                    with open(CACHE_FILE, 'w') as f:
                        json.dump({}, f)
                    logger.info(f"Created new cache file: {CACHE_FILE}")
            except Exception as e:
                logger.error(f"Failed to initialize cache file: {e}")

    def _read_cache(self) -> dict[str, Any]:
        with self._cache_lock:
            try:
                if CACHE_FILE.exists():
                    with open(CACHE_FILE, 'r') as f:
                        return json.load(f)
            except Exception as e:
                logger.error(f"Failed to read cache file: {e}")
            return {}

    def _write_to_cache(self, topic: str, value: str):
        with self._cache_lock:
            try:
                cache = {}
                if CACHE_FILE.exists():
                    try:
                        with open(CACHE_FILE, 'r') as f:
                            cache = json.load(f)
                    except Exception:
                        cache = {}

                cache[topic] = {"value": value, "timestamp": time.time()}

                temp_file = CACHE_FILE.with_suffix('.tmp')
                with open(temp_file, 'w') as f:
                    json.dump(cache, f)
                temp_file.replace(CACHE_FILE)

            except Exception as e:
                logger.error(f"Failed to write to cache file: {e}")

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0 or (isinstance(reason_code, ReasonCode) and reason_code.is_failure is False):
            self.connected = True
            logger.info(f"Connected to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
            self.client.subscribe(MQTT_SUBSCRIBE_TOPIC, qos=1)
            logger.info(f"Subscribed to {MQTT_SUBSCRIBE_TOPIC}")
        else:
            logger.error(f"Connection failed: {reason_code}")

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        self.connected = False
        logger.warning(f"Disconnected from MQTT broker: {reason_code}")

    def _on_message(self, client, userdata, message):
        try:
            payload = message.payload.decode("utf-8")
        except UnicodeDecodeError:
            payload = str(message.payload)
        self._write_to_cache(message.topic, payload)

    def connect(self):
        try:
            logger.info(f"Connecting to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}...")
            self.client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
            self.client.loop_start()

            timeout = 10
            start = time.time()
            while not self.connected and (time.time() - start) < timeout:
                time.sleep(0.1)

            return self.connected
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            return False

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()

    def get_topic_value(self, topic: str) -> str | None:
        cache = self._read_cache()
        data = cache.get(topic)
        return data.get("value") if data else None

    def publish_message(self, topic: str, payload: str, retain: bool = False, qos: int = 1) -> dict[str, Any]:
        if not self.connected:
            raise ConnectionError("Not connected to MQTT broker")

        result = self.client.publish(topic, payload, qos=qos, retain=retain)
        if qos > 0:
            result.wait_for_publish(timeout=10)

        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            return {"success": True, "topic": topic, "timestamp": time.time()}
        else:
            return {"success": False, "error": f"Publish failed: {result.rc}"}

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================
def safe_float(value: str | None, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

def safe_int(value: str | None, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default

def format_duration(minutes: float) -> str:
    if minutes < 60:
        return f"{minutes:.1f} min"
    hours = minutes / 60
    if hours < 24:
        return f"{hours:.1f} hr"
    days = hours / 24
    return f"{days:.1f} days"

# =============================================================================
# FASTAPI APPLICATION
# =============================================================================
app = FastAPI(
    title="MES HTTP Server - Press 103",
    description="HTTP API for Press 103 MES data (test server for N8N integration)",
    version="1.0.0",
)

# Add CORS middleware for N8N
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global MQTT client
mqtt_client: MQTTClientWrapper = None

@app.on_event("startup")
async def startup_event():
    """Initialize connections on startup."""
    global mqtt_client
    
    logger.info("=" * 50)
    logger.info("Starting MES HTTP Server - Press 103")
    logger.info("=" * 50)
    
    # Initialize MySQL
    if not init_db_pool():
        logger.warning("MySQL connection pool failed")
    
    # Initialize MQTT
    mqtt_client = MQTTClientWrapper()
    if not mqtt_client.connect():
        logger.warning("MQTT connection failed")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    global mqtt_client
    if mqtt_client:
        mqtt_client.disconnect()
    logger.info("MES HTTP Server shutdown complete")

# =============================================================================
# API ENDPOINTS
# =============================================================================
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="ok",
        mqtt_connected=mqtt_client.connected if mqtt_client else False,
        mysql_connected=db_pool is not None,
        timestamp=datetime.utcnow().isoformat() + "Z",
    )

@app.get("/equipment/status", response_model=EquipmentStatusResponse)
async def get_equipment_status():
    """Get current operational status of Press 103."""
    running = mqtt_client.get_topic_value(TOPIC_RUNNING)
    state = mqtt_client.get_topic_value(TOPIC_STATE)
    speed = safe_float(mqtt_client.get_topic_value(TOPIC_MACHINE_SPEED))
    setpoint = safe_float(mqtt_client.get_topic_value(TOPIC_RATE_SETPOINT))
    shift = mqtt_client.get_topic_value(TOPIC_SHIFT_NAME)

    is_running = str(running).lower() in ('true', '1', 'yes', 'running') if running else False
    speed_pct = (speed / setpoint * 100) if setpoint > 0 else 0

    return EquipmentStatusResponse(
        running=is_running,
        state=state,
        speed=speed,
        setpoint=setpoint,
        speed_percent=speed_pct,
        shift=shift,
        mqtt_connected=mqtt_client.connected,
    )

@app.get("/workorder/active", response_model=WorkOrderResponse)
async def get_active_work_order():
    """Get the currently active work order on Press 103."""
    wo_number = mqtt_client.get_topic_value(TOPIC_WORK_ORDER)
    good_count = safe_int(mqtt_client.get_topic_value(TOPIC_GOOD_COUNT))
    target_count = safe_int(mqtt_client.get_topic_value(TOPIC_TARGET_COUNT))
    run_id = mqtt_client.get_topic_value(TOPIC_RUN_ID)

    # Try to get product code from MySQL
    product_code = None
    if wo_number:
        try:
            query = """
                SELECT w.ProductCode
                FROM mes_lite.workorder w
                WHERE w.WorkOrder = %s
                LIMIT 1
            """
            results = execute_query(query, (wo_number,))
            if results:
                product_code = results[0].get('ProductCode')
        except Exception as e:
            logger.warning(f"Could not fetch work order details: {e}")

    remaining = max(0, target_count - good_count)
    pct_complete = (good_count / target_count * 100) if target_count > 0 else 0

    return WorkOrderResponse(
        work_order=wo_number,
        product_code=product_code,
        good_count=good_count,
        target_count=target_count,
        remaining=remaining,
        percent_complete=round(pct_complete, 1),
        run_id=run_id,
    )

@app.get("/oee/summary", response_model=OEEResponse)
async def get_oee_summary():
    """Get OEE metrics for Press 103."""
    oee = safe_float(mqtt_client.get_topic_value(TOPIC_OEE))
    availability = safe_float(mqtt_client.get_topic_value(TOPIC_OEE_AVAILABILITY))
    performance = safe_float(mqtt_client.get_topic_value(TOPIC_OEE_PERFORMANCE))
    quality = safe_float(mqtt_client.get_topic_value(TOPIC_OEE_QUALITY))
    good_count = safe_int(mqtt_client.get_topic_value(TOPIC_GOOD_COUNT))
    bad_count = safe_int(mqtt_client.get_topic_value(TOPIC_BAD_COUNT))
    runtime = safe_float(mqtt_client.get_topic_value(TOPIC_RUNTIME))
    downtime = safe_float(mqtt_client.get_topic_value(TOPIC_UNPLANNED_DOWNTIME))

    total_count = good_count + bad_count

    if oee >= 85:
        rating = "World Class"
    elif oee >= 65:
        rating = "Typical"
    elif oee >= 40:
        rating = "Below Average"
    else:
        rating = "Needs Improvement"

    return OEEResponse(
        oee=round(oee, 1),
        availability=round(availability, 1),
        performance=round(performance, 1),
        quality=round(quality, 1),
        good_count=good_count,
        bad_count=bad_count,
        total_count=total_count,
        runtime_minutes=round(runtime, 1),
        downtime_minutes=round(downtime, 1),
        rating=rating,
    )

@app.get("/downtime/summary", response_model=DowntimeResponse)
async def get_downtime_summary(hours_back: int = Query(default=24, ge=1, le=168)):
    """Get downtime analysis for Press 103."""
    current_state = mqtt_client.get_topic_value(TOPIC_STATE)
    running = mqtt_client.get_topic_value(TOPIC_RUNNING)
    is_running = str(running).lower() in ('true', '1', 'yes', 'running') if running else False

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

        for row in pareto_data:
            minutes = row.get('Minutes') or 0
            total_downtime += minutes
            if row.get('PlannedDowntime'):
                planned_downtime += minutes
            else:
                unplanned_downtime += minutes

    except Exception as e:
        logger.warning(f"Could not fetch downtime data: {e}")

    # Build top reasons
    top_reasons = []
    for row in pareto_data[:5]:
        minutes = row.get('Minutes') or 0
        pct = (minutes / total_downtime * 100) if total_downtime > 0 else 0
        top_reasons.append(DowntimeReason(
            reason=row.get('ReasonName', 'Unknown'),
            minutes=round(minutes, 1),
            events=row.get('Events') or 0,
            percent=round(pct, 1),
            planned=bool(row.get('PlannedDowntime')),
        ))

    return DowntimeResponse(
        current_state=current_state or "Unknown",
        is_running=is_running,
        hours_analyzed=hours_back,
        total_downtime_minutes=round(total_downtime, 1),
        planned_minutes=round(planned_downtime, 1),
        unplanned_minutes=round(unplanned_downtime, 1),
        top_reasons=top_reasons,
    )

@app.post("/observation", response_model=ObservationResponse)
async def log_observation(request: ObservationRequest):
    """Log an observation about Press 103 to the UNS."""
    payload = json.dumps({
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "source": "n8n-agent",
        "category": request.category,
        "message": request.message,
    })

    result = mqtt_client.publish_message(
        topic=TOPIC_AGENT_OBSERVATIONS,
        payload=payload,
        retain=False,
        qos=1,
    )

    if result.get("success"):
        return ObservationResponse(
            success=True,
            topic=TOPIC_AGENT_OBSERVATIONS,
            message=request.message,
            category=request.category,
            timestamp=datetime.utcnow().isoformat() + "Z",
        )
    else:
        raise HTTPException(status_code=500, detail=f"Failed to publish: {result.get('error')}")

# =============================================================================
# MAIN ENTRY POINT
# =============================================================================
if __name__ == "__main__":
    uvicorn.run(
        "mes_http_server:app",
        host="0.0.0.0",
        port=8002,
        reload=False,
        log_level="info",
    )

#!/usr/bin/env python3
"""
Agent Telemetry — UNS Publishing Module

Publishes agent state, health, and activity to the Unified Namespace via MQTT.
Designed to be imported by MCP servers and HTTP agents.

Usage:
    from shared.agent_telemetry import AgentTelemetry

    telemetry = AgentTelemetry(
        agent_id="mes-press103",
        agent_type="mcp",
        name="MES MCP Server - Press 103",
        version="1.0.0",
        tools=["get_equipment_status", "get_oee_summary"],
    )
    telemetry.start()

    # Track tool invocations
    with telemetry.track_tool("get_oee_summary"):
        result = do_something()

    telemetry.stop()
"""

import json
import logging
import os
import socket
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import paho.mqtt.client as mqtt
from paho.mqtt.reasoncodes import ReasonCode
from dotenv import load_dotenv

# =============================================================================
# LOGGING
# =============================================================================
logger = logging.getLogger("agent-telemetry")

# =============================================================================
# ENVIRONMENT LOADING
# =============================================================================
# Try multiple paths to find .env file
_possible_env_paths = [
    Path(__file__).parent.parent.parent / ".env",  # shared/agent_telemetry -> root
    Path(__file__).parent.parent.parent.parent / ".env",  # deeper nesting
    Path.cwd() / ".env",  # current working directory
]

for _env_path in _possible_env_paths:
    if _env_path.exists():
        load_dotenv(_env_path)
        logger.debug(f"Loaded environment from: {_env_path}")
        break

# =============================================================================
# MQTT CONFIGURATION
# =============================================================================
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")

# =============================================================================
# DEFAULT CONFIGURATION
# =============================================================================
DEFAULT_BASE_TOPIC = "Enterprise/Dallas/Agents"
DEFAULT_HEARTBEAT_INTERVAL = 30  # seconds


class AgentTelemetry:
    """
    Publishes agent telemetry to the UNS via MQTT.
    
    Manages its own MQTT connection separate from the agent's data connection.
    Publishes:
        - Identity: Agent metadata (on startup + with heartbeat)
        - Status: Connection health (on change + with heartbeat)
        - Heartbeat: Alive signal (periodic)
        - Tools/{name}: Invocation details (on each call)
        - Activity: Event stream (on significant events)
    """

    def __init__(
        self,
        agent_id: str,
        agent_type: str,
        name: str,
        version: str = "1.0.0",
        description: str = "",
        tools: Optional[list[str]] = None,
        capabilities: Optional[list[str]] = None,
        base_topic: str = DEFAULT_BASE_TOPIC,
        heartbeat_interval: int = DEFAULT_HEARTBEAT_INTERVAL,
        publish_activity: bool = True,
    ):
        """
        Initialize the telemetry publisher.

        Args:
            agent_id: Unique identifier for this agent (e.g., "mes-press103")
            agent_type: Type of agent ("mcp" or "http")
            name: Human-readable name
            version: Agent version string
            description: Brief description of what the agent does
            tools: List of tool/skill names this agent provides
            capabilities: List of capabilities (e.g., ["mqtt", "mysql"])
            base_topic: UNS base path for telemetry topics
            heartbeat_interval: Seconds between heartbeat publishes
            publish_activity: Whether to publish activity stream events
        """
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.name = name
        self.version = version
        self.description = description
        self.tools = tools or []
        self.capabilities = capabilities or []
        self.base_topic = base_topic
        self.heartbeat_interval = heartbeat_interval
        self.publish_activity = publish_activity

        # State tracking
        self._started_at: Optional[datetime] = None
        self._tool_stats: dict[str, dict[str, Any]] = {}
        self._total_tool_calls = 0
        self._failed_tool_calls = 0
        self._last_error: Optional[str] = None
        self._external_status: dict[str, bool] = {}  # e.g., {"mqtt": True, "mysql": False}

        # MQTT client (separate connection for telemetry)
        self._client_id = f"telemetry-{agent_id}-{uuid.uuid4().hex[:8]}"
        self._client: Optional[mqtt.Client] = None
        self._connected = False
        self._lock = threading.Lock()

        # Heartbeat thread
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._stop_heartbeat = threading.Event()

    # =========================================================================
    # TOPIC HELPERS
    # =========================================================================
    def _topic(self, suffix: str) -> str:
        """Build full topic path."""
        return f"{self.base_topic}/{self.agent_id}/{suffix}"

    # =========================================================================
    # MQTT CONNECTION
    # =========================================================================
    def _on_connect(self, client, userdata, flags, reason_code, properties):
        """Callback when MQTT connects."""
        if reason_code == 0 or (isinstance(reason_code, ReasonCode) and not reason_code.is_failure):
            self._connected = True
            logger.info(f"[Telemetry] Connected to MQTT broker for {self.agent_id}")
        else:
            logger.error(f"[Telemetry] Connection failed: {reason_code}")

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        """Callback when MQTT disconnects."""
        self._connected = False
        if reason_code == 0:
            logger.info(f"[Telemetry] Disconnected from MQTT broker")
        else:
            logger.warning(f"[Telemetry] Disconnected: {reason_code} (will auto-reconnect)")

    def _connect_mqtt(self) -> bool:
        """Establish MQTT connection for telemetry."""
        try:
            self._client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id=self._client_id,
                protocol=mqtt.MQTTv311,
                clean_session=True,
            )

            self._client.on_connect = self._on_connect
            self._client.on_disconnect = self._on_disconnect

            if MQTT_USERNAME and MQTT_PASSWORD:
                self._client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

            self._client.reconnect_delay_set(min_delay=1, max_delay=120)

            logger.info(f"[Telemetry] Connecting to {MQTT_BROKER}:{MQTT_PORT}...")
            self._client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
            self._client.loop_start()

            # Wait for connection
            timeout = 10
            start = time.time()
            while not self._connected and (time.time() - start) < timeout:
                time.sleep(0.1)

            if not self._connected:
                logger.error("[Telemetry] Failed to connect within timeout")
                return False

            return True

        except Exception as e:
            logger.error(f"[Telemetry] Failed to connect: {e}")
            return False

    def _disconnect_mqtt(self):
        """Disconnect MQTT client."""
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
            self._client = None
            self._connected = False
            logger.info("[Telemetry] MQTT disconnected")

    # =========================================================================
    # PUBLISHING
    # =========================================================================
    def _publish(self, topic_suffix: str, payload: dict, qos: int = 1):
        """Publish a message to the UNS (non-blocking, no retain)."""
        if not self._connected or not self._client:
            logger.debug(f"[Telemetry] Not connected, skipping publish to {topic_suffix}")
            return

        try:
            topic = self._topic(topic_suffix)
            message = json.dumps(payload)
            self._client.publish(topic, message, qos=qos, retain=False)
            logger.debug(f"[Telemetry] Published to {topic}")
        except Exception as e:
            logger.error(f"[Telemetry] Publish failed: {e}")

    def _get_timestamp(self) -> str:
        """Get current UTC timestamp in ISO format."""
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _get_uptime_seconds(self) -> int:
        """Get seconds since agent started."""
        if self._started_at:
            delta = datetime.now(timezone.utc) - self._started_at
            return int(delta.total_seconds())
        return 0

    def _get_hostname(self) -> str:
        """Get local hostname."""
        try:
            return socket.gethostname()
        except Exception:
            return "unknown"

    # =========================================================================
    # PAYLOAD BUILDERS
    # =========================================================================
    def _build_identity_payload(self) -> dict:
        """Build Identity payload."""
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "capabilities": self.capabilities,
            "tools": self.tools,
            "started_at": self._started_at.isoformat().replace("+00:00", "Z") if self._started_at else None,
            "host": self._get_hostname(),
        }

    def _build_status_payload(self) -> dict:
        """Build Status payload."""
        payload = {
            "agent_id": self.agent_id,
            "timestamp": self._get_timestamp(),
            "state": "running" if self._connected else "disconnected",
            "uptime_seconds": self._get_uptime_seconds(),
            "telemetry_connected": self._connected,
            "tool_calls_total": self._total_tool_calls,
            "tool_calls_failed": self._failed_tool_calls,
            "last_error": self._last_error,
        }
        # Add external connection statuses
        for key, value in self._external_status.items():
            payload[f"{key}_connected"] = value
        return payload

    def _build_heartbeat_payload(self) -> dict:
        """Build Heartbeat payload."""
        return {
            "agent_id": self.agent_id,
            "timestamp": self._get_timestamp(),
            "uptime_seconds": self._get_uptime_seconds(),
        }

    def _build_tool_payload(self, tool_name: str, duration_ms: float, success: bool, error: Optional[str]) -> dict:
        """Build Tool invocation payload."""
        stats = self._tool_stats.get(tool_name, {})
        return {
            "agent_id": self.agent_id,
            "tool": tool_name,
            "timestamp": self._get_timestamp(),
            "duration_ms": round(duration_ms, 2),
            "success": success,
            "error": error,
            "invocation_count": stats.get("count", 0),
        }

    def _build_activity_payload(self, event: str, details: Optional[dict] = None) -> dict:
        """Build Activity payload."""
        return {
            "agent_id": self.agent_id,
            "timestamp": self._get_timestamp(),
            "event": event,
            "details": details or {},
        }

    # =========================================================================
    # HEARTBEAT THREAD
    # =========================================================================
    def _heartbeat_loop(self):
        """Background thread that publishes heartbeat + identity + status periodically."""
        logger.info(f"[Telemetry] Heartbeat thread started (interval: {self.heartbeat_interval}s)")

        while not self._stop_heartbeat.wait(timeout=self.heartbeat_interval):
            if self._connected:
                # Publish heartbeat
                self._publish("Heartbeat", self._build_heartbeat_payload(), qos=0)
                # Republish identity and status for discovery (no retain)
                self._publish("Identity", self._build_identity_payload(), qos=1)
                self._publish("Status", self._build_status_payload(), qos=1)

        logger.info("[Telemetry] Heartbeat thread stopped")

    # =========================================================================
    # PUBLIC API
    # =========================================================================
    def start(self):
        """
        Start telemetry publishing.
        
        Connects to MQTT, publishes initial Identity/Status, starts heartbeat thread.
        """
        logger.info(f"[Telemetry] Starting telemetry for {self.agent_id}")

        self._started_at = datetime.now(timezone.utc)

        # Connect to MQTT
        if not self._connect_mqtt():
            logger.warning("[Telemetry] Running without telemetry (MQTT connection failed)")
            return

        # Publish initial identity and status
        self._publish("Identity", self._build_identity_payload(), qos=1)
        self._publish("Status", self._build_status_payload(), qos=1)

        # Publish startup activity
        if self.publish_activity:
            self._publish("Activity", self._build_activity_payload("startup", {
                "name": self.name,
                "version": self.version,
            }), qos=0)

        # Start heartbeat thread
        self._stop_heartbeat.clear()
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()

        logger.info(f"[Telemetry] Telemetry started for {self.agent_id}")

    def stop(self):
        """
        Stop telemetry publishing.
        
        Publishes shutdown activity, stops heartbeat thread, disconnects MQTT.
        """
        logger.info(f"[Telemetry] Stopping telemetry for {self.agent_id}")

        # Publish shutdown activity
        if self.publish_activity and self._connected:
            self._publish("Activity", self._build_activity_payload("shutdown", {
                "uptime_seconds": self._get_uptime_seconds(),
                "total_tool_calls": self._total_tool_calls,
            }), qos=0)

        # Stop heartbeat thread
        self._stop_heartbeat.set()
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            self._heartbeat_thread.join(timeout=5)

        # Disconnect MQTT
        self._disconnect_mqtt()

        logger.info(f"[Telemetry] Telemetry stopped for {self.agent_id}")

    def update_status(self, **kwargs):
        """
        Update external connection statuses and publish Status.
        
        Example:
            telemetry.update_status(mqtt=True, mysql=False)
        """
        with self._lock:
            self._external_status.update(kwargs)

        if self._connected:
            self._publish("Status", self._build_status_payload(), qos=1)

    def record_error(self, error: str):
        """Record an error (updates last_error and publishes Status)."""
        with self._lock:
            self._last_error = error

        if self._connected:
            self._publish("Status", self._build_status_payload(), qos=1)

        if self.publish_activity:
            self._publish("Activity", self._build_activity_payload("error", {
                "error": error,
            }), qos=0)

    @contextmanager
    def track_tool(self, tool_name: str):
        """
        Context manager to track tool invocations.
        
        Usage:
            with telemetry.track_tool("get_oee_summary"):
                result = do_something()
        
        Automatically tracks duration, success/failure, and publishes to UNS.
        """
        start_time = time.perf_counter()
        success = True
        error = None

        try:
            yield
        except Exception as e:
            success = False
            error = str(e)
            raise
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Update stats
            with self._lock:
                self._total_tool_calls += 1
                if not success:
                    self._failed_tool_calls += 1
                    self._last_error = error

                if tool_name not in self._tool_stats:
                    self._tool_stats[tool_name] = {"count": 0, "total_ms": 0, "failures": 0}

                self._tool_stats[tool_name]["count"] += 1
                self._tool_stats[tool_name]["total_ms"] += duration_ms
                if not success:
                    self._tool_stats[tool_name]["failures"] += 1

            # Publish tool invocation
            if self._connected:
                self._publish(
                    f"Tools/{tool_name}",
                    self._build_tool_payload(tool_name, duration_ms, success, error),
                    qos=1,
                )

            # Publish activity
            if self.publish_activity and self._connected:
                self._publish("Activity", self._build_activity_payload("tool_call", {
                    "tool": tool_name,
                    "success": success,
                    "duration_ms": round(duration_ms, 2),
                }), qos=0)

    def publish_custom_activity(self, event: str, details: Optional[dict] = None):
        """
        Publish a custom activity event.
        
        Example:
            telemetry.publish_custom_activity("work_order_changed", {"old": "123", "new": "456"})
        """
        if self.publish_activity and self._connected:
            self._publish("Activity", self._build_activity_payload(event, details), qos=0)

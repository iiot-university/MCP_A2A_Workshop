#!/usr/bin/env python3
"""
MQTT MCP Server - UNS (Unified Namespace) Interface

This MCP server connects to an MQTT broker and exposes UNS data to Claude Desktop
through tools for reading and writing MQTT topics.

Architecture:
    - On connect: Subscribe to all topics (#) and cache values in a JSON file
    - On message: Update the cache file with the latest value for each topic
    - Cache persists across reconnections for stability
    - Tools read from the cache file for instant responses

Tools:
    - list_uns_topics: List all cached topics and their values
    - get_topic_value: Get the cached value for a specific topic
    - search_topics: Find topics matching a pattern or keyword
    - publish_message: Publish a message to a specific topic
"""

import asyncio
import json
import logging
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any
import fnmatch
import re
import threading

import paho.mqtt.client as mqtt
from paho.mqtt.reasoncodes import ReasonCode
from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Add project root to path for shared module imports
_project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(_project_root))

try:
    from shared.agent_telemetry import AgentTelemetry
    TELEMETRY_AVAILABLE = True
except ImportError as e:
    TELEMETRY_AVAILABLE = False
    AgentTelemetry = None
    # Will log warning after logger is configured

# Configure logging to stderr (stdout reserved for MCP protocol)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("mqtt-mcp-server")

# Log telemetry availability
if TELEMETRY_AVAILABLE:
    logger.info("AgentTelemetry module loaded successfully")
else:
    logger.warning("AgentTelemetry module not available - agent state will not be published to UNS")

# Load environment variables from .env file (two directories up from src/)
env_path = Path(__file__).parent.parent.parent.parent / ".env"
load_dotenv(env_path)
logger.info(f"Loading environment from: {env_path}")

# MQTT Configuration
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")

# Generate unique client ID to prevent collisions
# Use base from env + unique suffix to allow multiple instances
_base_client_id = os.getenv("MQTT_CLIENT_ID", "mcp-mqtt")
MQTT_CLIENT_ID = f"{_base_client_id}-{uuid.uuid4().hex[:8]}"

# Cache file configuration
CACHE_FILE = Path(__file__).parent / "mqtt_cache.json"


class MQTTClientWrapper:
    """Wrapper class for MQTT client with file-based caching."""

    def __init__(self):
        """Initialize MQTT client with v2.0+ API."""
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=MQTT_CLIENT_ID,
            protocol=mqtt.MQTTv311,
            clean_session=True,  # Don't persist session state
        )
        self.connected = False
        self._reconnect_count = 0
        self._cache_lock = threading.Lock()  # Thread-safe file access
        self._message_count = 0

        # Set up callbacks
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

        # Set credentials if provided
        if MQTT_USERNAME and MQTT_PASSWORD:
            self.client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

        # Configure reconnection with exponential backoff
        # min_delay=1s, max_delay=120s - prevents rapid reconnection cycling
        self.client.reconnect_delay_set(min_delay=1, max_delay=120)

        # Initialize cache file (create if doesn't exist, preserve if exists)
        self._init_cache()

    def _init_cache(self):
        """Initialize cache file if it doesn't exist (preserves existing cache)."""
        with self._cache_lock:
            try:
                if not CACHE_FILE.exists():
                    with open(CACHE_FILE, 'w') as f:
                        json.dump({}, f)
                    logger.info(f"Created new cache file: {CACHE_FILE}")
                else:
                    # Load existing cache to get topic count
                    try:
                        with open(CACHE_FILE, 'r') as f:
                            cache = json.load(f)
                        logger.info(f"Loaded existing cache with {len(cache)} topics")
                    except (json.JSONDecodeError, Exception):
                        # If corrupted, start fresh
                        with open(CACHE_FILE, 'w') as f:
                            json.dump({}, f)
                        logger.warning("Cache file was corrupted, starting fresh")
            except Exception as e:
                logger.error(f"Failed to initialize cache file: {e}")

    def _clear_cache(self):
        """Clear the cache file (write empty JSON object)."""
        with self._cache_lock:
            try:
                with open(CACHE_FILE, 'w') as f:
                    json.dump({}, f)
                logger.debug(f"Cache file cleared: {CACHE_FILE}")
            except Exception as e:
                logger.error(f"Failed to clear cache file: {e}")

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
                # Read existing cache
                cache = {}
                if CACHE_FILE.exists():
                    try:
                        with open(CACHE_FILE, 'r') as f:
                            cache = json.load(f)
                    except (json.JSONDecodeError, Exception):
                        cache = {}

                # Update the topic value
                cache[topic] = {
                    "value": value,
                    "timestamp": time.time(),
                }

                # Write back atomically (write to temp, then rename)
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
                logger.info(f"Reconnected to MQTT broker at {MQTT_BROKER}:{MQTT_PORT} (attempt {self._reconnect_count})")
            else:
                logger.info(f"Connected to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
            self._reconnect_count = 0

            # Subscribe to all topics to populate cache
            result, mid = self.client.subscribe("#", qos=1)
            if result == mqtt.MQTT_ERR_SUCCESS:
                logger.info("Subscribed to all topics (#) for caching")
            else:
                logger.error(f"Failed to subscribe to all topics: {result}")
        else:
            reason_str = self._get_reason_string(reason_code)
            logger.error(f"Connection failed: {reason_str}")

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        """Callback for when the client disconnects from the broker."""
        self.connected = False
        self._reconnect_count += 1

        # Cache persists across disconnections for stability
        # (will be updated when connection is restored)

        reason_str = self._get_reason_string(reason_code)

        # Only log as warning for unexpected disconnects
        # Normal disconnection (rc=0) or client-initiated are expected
        if reason_code == 0 or reason_str == "Normal disconnection":
            logger.info(f"Disconnected from MQTT broker: {reason_str}")
        else:
            logger.warning(f"Disconnected from MQTT broker: {reason_str} (will auto-reconnect, cache preserved)")

    def _get_reason_string(self, reason_code) -> str:
        """Convert reason code to human-readable string."""
        # Handle paho-mqtt ReasonCode objects
        if isinstance(reason_code, ReasonCode):
            return str(reason_code)

        # Handle integer reason codes (MQTT 3.1.1 style)
        reason_map = {
            0: "Normal disconnection",
            1: "Incorrect protocol version",
            2: "Invalid client identifier",
            3: "Server unavailable",
            4: "Bad username or password",
            5: "Not authorized",
            7: "Unexpected disconnect (no DISCONNECT packet)",
            16: "Normal disconnection",
            128: "Unspecified error",
            129: "Malformed packet",
            130: "Protocol error",
            131: "Implementation specific error",
            132: "Unsupported protocol version",
            133: "Client identifier not valid",
            134: "Bad username or password",
            135: "Not authorized",
            136: "Server unavailable",
            137: "Server busy",
            138: "Banned",
            139: "Server shutting down",
            140: "Bad authentication method",
            141: "Keep alive timeout",
            142: "Session taken over",  # Another client with same ID connected
            143: "Topic filter invalid",
            144: "Topic name invalid",
            147: "Receive maximum exceeded",
            148: "Topic alias invalid",
            149: "Packet too large",
            150: "Message rate too high",
            151: "Quota exceeded",
            152: "Administrative action",
            153: "Payload format invalid",
            154: "Retain not supported",
            155: "QoS not supported",
            156: "Use another server",
            157: "Server moved",
            158: "Shared subscriptions not supported",
            159: "Connection rate exceeded",
            160: "Maximum connect time",
            161: "Subscription identifiers not supported",
            162: "Wildcard subscriptions not supported",
        }
        return reason_map.get(int(reason_code) if reason_code else 0, f"Unknown ({reason_code})")

    def _on_message(self, client, userdata, message):
        """Callback for when a message is received - updates cache file."""
        try:
            payload = message.payload.decode("utf-8")
        except UnicodeDecodeError:
            payload = str(message.payload)

        # Update the cache file with this topic's value
        self._write_to_cache(message.topic, payload)
        self._message_count += 1

        logger.debug(f"Cached message on {message.topic}: {payload[:100]}")

    def connect(self):
        """Connect to the MQTT broker."""
        try:
            logger.info(f"Connecting to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}...")
            logger.info(f"Using client ID: {MQTT_CLIENT_ID}")
            logger.info(f"Cache file: {CACHE_FILE}")

            # Connect with keepalive of 60 seconds
            self.client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)

            # Start the network loop in a background thread
            # This handles reconnection automatically with the configured backoff
            self.client.loop_start()

            # Wait for initial connection
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
        """Disconnect from the MQTT broker (cache is preserved)."""
        self.client.loop_stop()
        self.client.disconnect()
        # Cache is preserved for stability across restarts
        logger.info("Disconnected from MQTT broker (cache preserved)")

    def ensure_connected(self) -> bool:
        """Ensure the client is connected, reconnecting if necessary."""
        if not self.connected:
            return self.connect()
        return True

    def get_all_topics(self) -> dict[str, Any]:
        """Get all cached topics and their values."""
        return self._read_cache()

    def get_topic_value(self, topic: str) -> dict[str, Any] | None:
        """Get a specific topic's cached value."""
        cache = self._read_cache()
        return cache.get(topic)

    def get_topic_count(self) -> int:
        """Get the number of cached topics."""
        cache = self._read_cache()
        return len(cache)

    async def publish_message(
        self,
        topic: str,
        payload: str,
        retain: bool = False,
        qos: int = 1,
    ) -> dict[str, Any]:
        """
        Publish a message to a specific topic.

        Args:
            topic: Full topic path to publish to
            payload: Message payload (string)
            retain: Whether to retain the message on the broker (default: False)
            qos: Quality of Service level 0, 1, or 2 (default: 1)

        Returns:
            Dictionary with publish result details
        """
        if not self.ensure_connected():
            raise ConnectionError("Not connected to MQTT broker")

        # Validate QoS
        if qos not in (0, 1, 2):
            raise ValueError(f"Invalid QoS level: {qos}. Must be 0, 1, or 2.")

        # Validate topic (basic validation)
        if not topic or not topic.strip():
            raise ValueError("Topic cannot be empty")
        if "#" in topic or "+" in topic:
            raise ValueError("Cannot publish to wildcard topics (# or +)")

        # Log the publish operation for safety/auditing
        logger.info(f"Publishing to '{topic}': payload='{payload[:100]}{'...' if len(payload) > 100 else ''}', retain={retain}, qos={qos}")

        # Publish the message
        result = self.client.publish(topic, payload, qos=qos, retain=retain)

        # Wait for publish to complete (for QoS > 0)
        if qos > 0:
            result.wait_for_publish(timeout=10)

        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            logger.info(f"Successfully published to '{topic}'")
            return {
                "success": True,
                "topic": topic,
                "payload": payload,
                "retain": retain,
                "qos": qos,
                "message_id": result.mid,
                "timestamp": time.time(),
            }
        else:
            error_msg = f"Publish failed with error code: {result.rc}"
            logger.error(error_msg)
            return {
                "success": False,
                "topic": topic,
                "error": error_msg,
                "error_code": result.rc,
            }


# Create global MQTT client instance
mqtt_client = MQTTClientWrapper()

# Create MCP server instance
server = Server("mqtt-uns")

# Telemetry for UNS visibility
if TELEMETRY_AVAILABLE:
    telemetry = AgentTelemetry(
        agent_id="mqtt-uns",
        agent_type="mcp",
        name="MQTT MCP Server - UNS Interface",
        version="1.0.0",
        description="Generic MQTT/UNS access server for reading and writing topics",
        tools=["list_uns_topics", "get_topic_value", "search_topics", "publish_message"],
        capabilities=["mqtt"],
    )
else:
    telemetry = None


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools."""
    return [
        Tool(
            name="list_uns_topics",
            description=(
                "List all topics currently available in the UNS (Unified Namespace) cache. "
                "The cache is continuously updated with live data from the MQTT broker. "
                "Use this to explore what data is available. "
                "Returns topic paths with their current values."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "base_path": {
                        "type": "string",
                        "description": (
                            "Optional filter: only return topics starting with this path prefix. "
                            "Example: 'flexpack/packaging' to see only packaging topics. "
                            "Leave empty or use '#' for all topics."
                        ),
                        "default": "#",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="get_topic_value",
            description=(
                "Get the current cached value for a specific MQTT topic. "
                "Returns the latest value received from the broker. "
                "Example topic: 'flexpack/packaging/line1/filler/speed'"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": (
                            "Full topic path to read, e.g., 'flexpack/packaging/line1/filler/speed'"
                        ),
                    },
                },
                "required": ["topic"],
            },
        ),
        Tool(
            name="search_topics",
            description=(
                "Search cached topics matching a pattern or keyword. "
                "Use this to find topics by name without knowing the exact path. "
                "Supports glob patterns (*, ?) and simple keyword search."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": (
                            "Search pattern or keyword. Can be: "
                            "1) A simple keyword to search in topic names (e.g., 'temperature'), "
                            "2) A glob pattern with wildcards (e.g., '*speed*', 'line1/*'), "
                            "3) An MQTT wildcard pattern (e.g., 'flexpack/+/line1/#')"
                        ),
                    },
                },
                "required": ["pattern"],
            },
        ),
        Tool(
            name="publish_message",
            description=(
                "Publish a message to a specific MQTT topic in the UNS. "
                "Use this to write data back to the Unified Namespace. "
                "Example: publish 'hello from claude' to 'flexpack/test/claude'. "
                "WARNING: This writes to the live MQTT broker - use with caution."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": (
                            "Full topic path to publish to, e.g., 'flexpack/test/claude'. "
                            "Cannot contain wildcards (# or +)."
                        ),
                    },
                    "payload": {
                        "type": "string",
                        "description": (
                            "The message payload to publish. Can be any string value, "
                            "including JSON-formatted data."
                        ),
                    },
                    "retain": {
                        "type": "boolean",
                        "description": (
                            "Whether to retain the message on the broker. Retained messages "
                            "are stored and sent to new subscribers. Default is false."
                        ),
                        "default": False,
                    },
                    "qos": {
                        "type": "integer",
                        "description": (
                            "Quality of Service level: 0 (at most once), 1 (at least once), "
                            "or 2 (exactly once). Default is 1."
                        ),
                        "default": 1,
                        "enum": [0, 1, 2],
                    },
                },
                "required": ["topic", "payload"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls with telemetry tracking."""
    if telemetry:
        with telemetry.track_tool(name, arguments):
            return await _route_tool(name, arguments)
    else:
        return await _route_tool(name, arguments)


async def _route_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Route tool calls to handlers."""
    if name == "list_uns_topics":
        return await handle_list_uns_topics(arguments)
    elif name == "get_topic_value":
        return await handle_get_topic_value(arguments)
    elif name == "search_topics":
        return await handle_search_topics(arguments)
    elif name == "publish_message":
        return await handle_publish_message(arguments)
    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def handle_list_uns_topics(arguments: dict[str, Any]) -> list[TextContent]:
    """
    List all cached topics from the UNS.

    Reads from the cache file which is continuously updated
    with live data from the MQTT broker.
    """
    base_path = arguments.get("base_path", "#")

    try:
        if not mqtt_client.connected:
            return [
                TextContent(
                    type="text",
                    text="Not connected to MQTT broker. Cache may be empty.",
                )
            ]

        all_topics = mqtt_client.get_all_topics()

        if not all_topics:
            return [
                TextContent(
                    type="text",
                    text="No topics in cache. The broker may have no retained messages, "
                    "or the connection was just established (wait a moment for messages to arrive).",
                )
            ]

        # Filter by base_path if specified
        if base_path and base_path != "#":
            filtered_topics = {
                k: v for k, v in all_topics.items()
                if k.startswith(base_path.rstrip('/'))
            }
        else:
            filtered_topics = all_topics

        if not filtered_topics:
            return [
                TextContent(
                    type="text",
                    text=f"No topics found matching prefix '{base_path}'. "
                    f"Total topics in cache: {len(all_topics)}",
                )
            ]

        # Format the results
        result_lines = [f"Found {len(filtered_topics)} topics:\n"]
        for topic_path in sorted(filtered_topics.keys()):
            data = filtered_topics[topic_path]
            value = data.get("value", "")
            # Truncate long values for readability
            if len(value) > 100:
                value = value[:100] + "..."
            result_lines.append(f"  • {topic_path}: {value}")

        return [TextContent(type="text", text="\n".join(result_lines))]

    except Exception as e:
        logger.exception("Error in list_uns_topics")
        return [TextContent(type="text", text=f"Error listing topics: {e}")]


async def handle_get_topic_value(arguments: dict[str, Any]) -> list[TextContent]:
    """
    Get the cached value for a specific topic.

    Reads from the cache file for instant response.
    """
    topic = arguments.get("topic")
    if not topic:
        return [TextContent(type="text", text="Error: 'topic' parameter is required")]

    try:
        if not mqtt_client.connected:
            return [
                TextContent(
                    type="text",
                    text="Not connected to MQTT broker. Cache may be stale.",
                )
            ]

        result = mqtt_client.get_topic_value(topic)

        if result is None:
            # Check if we have any topics to give context
            topic_count = mqtt_client.get_topic_count()
            return [
                TextContent(
                    type="text",
                    text=f"Topic '{topic}' not found in cache. "
                    f"Total topics in cache: {topic_count}. "
                    "The topic may not exist or hasn't published a message yet.",
                )
            ]

        # Format the result
        timestamp = result.get("timestamp", 0)
        age_seconds = time.time() - timestamp if timestamp else 0

        output = [
            f"Topic: {topic}",
            f"Value: {result['value']}",
            f"Last updated: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))}",
            f"Age: {age_seconds:.1f} seconds ago",
        ]

        return [TextContent(type="text", text="\n".join(output))]

    except Exception as e:
        logger.exception("Error in get_topic_value")
        return [TextContent(type="text", text=f"Error reading topic: {e}")]


async def handle_search_topics(arguments: dict[str, Any]) -> list[TextContent]:
    """
    Search cached topics matching a pattern or keyword.

    Reads from the cache file and filters by pattern.
    """
    pattern = arguments.get("pattern")
    if not pattern:
        return [TextContent(type="text", text="Error: 'pattern' parameter is required")]

    try:
        if not mqtt_client.connected:
            return [
                TextContent(
                    type="text",
                    text="Not connected to MQTT broker. Cache may be empty.",
                )
            ]

        all_topics = mqtt_client.get_all_topics()

        if not all_topics:
            return [
                TextContent(
                    type="text",
                    text="No topics in cache to search through. "
                    "The broker may have no retained messages.",
                )
            ]

        # Filter topics by pattern
        matching_topics = {}

        # Determine if pattern contains wildcards
        has_wildcards = any(c in pattern for c in ["*", "?", "+", "#"])

        for topic_path, data in all_topics.items():
            matched = False

            if has_wildcards:
                # Handle MQTT wildcards (+ and #)
                if "+" in pattern or "#" in pattern:
                    mqtt_pattern = pattern.replace("+", "[^/]+").replace("#", ".*")
                    if re.match(f"^{mqtt_pattern}$", topic_path):
                        matched = True
                # Handle glob wildcards (* and ?)
                else:
                    if fnmatch.fnmatch(topic_path, f"*{pattern}*"):
                        matched = True
            else:
                # Simple case-insensitive keyword search
                if pattern.lower() in topic_path.lower():
                    matched = True

            if matched:
                matching_topics[topic_path] = data

        if not matching_topics:
            return [
                TextContent(
                    type="text",
                    text=f"No topics found matching pattern '{pattern}'. "
                    f"Searched through {len(all_topics)} cached topics.",
                )
            ]

        # Format the results
        result_lines = [
            f"Found {len(matching_topics)} topics matching '{pattern}':\n"
        ]
        for topic_path in sorted(matching_topics.keys()):
            data = matching_topics[topic_path]
            value = data.get("value", "")
            # Truncate long values for readability
            if len(value) > 100:
                value = value[:100] + "..."
            result_lines.append(f"  • {topic_path}: {value}")

        return [TextContent(type="text", text="\n".join(result_lines))]

    except Exception as e:
        logger.exception("Error in search_topics")
        return [TextContent(type="text", text=f"Error searching topics: {e}")]


async def handle_publish_message(arguments: dict[str, Any]) -> list[TextContent]:
    """
    Publish a message to a specific MQTT topic.

    Validates inputs and publishes the message to the broker.
    All publish operations are logged for safety/auditing.
    """
    topic = arguments.get("topic")
    payload = arguments.get("payload")
    retain = arguments.get("retain", False)
    qos = arguments.get("qos", 1)

    # Validate required parameters
    if not topic:
        return [TextContent(type="text", text="Error: 'topic' parameter is required")]
    if payload is None:
        return [TextContent(type="text", text="Error: 'payload' parameter is required")]

    # Convert payload to string if needed
    if not isinstance(payload, str):
        payload = str(payload)

    try:
        result = await mqtt_client.publish_message(
            topic=topic,
            payload=payload,
            retain=retain,
            qos=qos,
        )

        if result.get("success"):
            # Format success message
            output = [
                "✓ Message published successfully!",
                "",
                f"Topic: {result['topic']}",
                f"Payload: {result['payload']}",
                f"Retain: {result['retain']}",
                f"QoS: {result['qos']}",
                f"Message ID: {result['message_id']}",
                f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(result['timestamp']))}",
            ]
            return [TextContent(type="text", text="\n".join(output))]
        else:
            # Format error message
            return [
                TextContent(
                    type="text",
                    text=f"✗ Publish failed: {result.get('error', 'Unknown error')}",
                )
            ]

    except ValueError as e:
        return [TextContent(type="text", text=f"Validation error: {e}")]
    except ConnectionError as e:
        return [TextContent(type="text", text=f"Connection error: {e}")]
    except Exception as e:
        logger.exception("Error in publish_message")
        return [TextContent(type="text", text=f"Error publishing message: {e}")]


async def main():
    """Main entry point for the MCP server."""
    logger.info("Starting MQTT MCP Server...")
    logger.info(f"MQTT Broker: {MQTT_BROKER}:{MQTT_PORT}")
    logger.info(f"Client ID: {MQTT_CLIENT_ID}")
    logger.info(f"Cache file: {CACHE_FILE}")

    # Connect to MQTT broker
    mqtt_connected = mqtt_client.connect()
    if not mqtt_connected:
        logger.error("Failed to connect to MQTT broker. Server will start but tools may fail.")

    # Start telemetry (publishes to UNS)
    if telemetry:
        telemetry.start()
        telemetry.update_status(mqtt=mqtt_connected)
        logger.info("Telemetry started and publishing to UNS")
    else:
        logger.warning("Telemetry not available - agent state will not be published to UNS")

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
        if telemetry:
            telemetry.stop()
        mqtt_client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())

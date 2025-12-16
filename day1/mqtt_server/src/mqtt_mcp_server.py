#!/usr/bin/env python3
"""
MQTT MCP Server - Read-Only Phase 1

This MCP server connects to an MQTT broker and exposes UNS (Unified Namespace) 
data to Claude Desktop through read-only tools.

Tools:
    - list_uns_topics: Discover available topics via wildcard subscription
    - get_topic_value: Read current retained value from a specific topic
    - search_topics: Find topics matching a pattern or keyword
"""

import asyncio
import logging
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any
import fnmatch
import re

import paho.mqtt.client as mqtt
from paho.mqtt.reasoncodes import ReasonCode
from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Configure logging to stderr (stdout reserved for MCP protocol)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("mqtt-mcp-server")

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


class MQTTClientWrapper:
    """Wrapper class for MQTT client with connection management."""

    def __init__(self):
        """Initialize MQTT client with v2.0+ API."""
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=MQTT_CLIENT_ID,
            protocol=mqtt.MQTTv311,
            clean_session=True,  # Don't persist session state
        )
        self.connected = False
        self.messages: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        self._message_event = asyncio.Event()
        self._reconnect_count = 0

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

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        """Callback for when the client connects to the broker."""
        if reason_code == 0 or (isinstance(reason_code, ReasonCode) and reason_code.is_failure is False):
            self.connected = True
            if self._reconnect_count > 0:
                logger.info(f"Reconnected to MQTT broker at {MQTT_BROKER}:{MQTT_PORT} (attempt {self._reconnect_count})")
            else:
                logger.info(f"Connected to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
            self._reconnect_count = 0
        else:
            reason_str = self._get_reason_string(reason_code)
            logger.error(f"Connection failed: {reason_str}")

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        """Callback for when the client disconnects from the broker."""
        self.connected = False
        self._reconnect_count += 1
        
        reason_str = self._get_reason_string(reason_code)
        
        # Only log as warning for unexpected disconnects
        # Normal disconnection (rc=0) or client-initiated are expected
        if reason_code == 0 or reason_str == "Normal disconnection":
            logger.info(f"Disconnected from MQTT broker: {reason_str}")
        else:
            logger.warning(f"Disconnected from MQTT broker: {reason_str} (will auto-reconnect)")

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
        """Callback for when a message is received."""
        try:
            payload = message.payload.decode("utf-8")
        except UnicodeDecodeError:
            payload = str(message.payload)

        self.messages[message.topic] = {
            "topic": message.topic,
            "payload": payload,
            "qos": message.qos,
            "retain": message.retain,
            "timestamp": time.time(),
        }
        # Signal that a message was received
        self._message_event.set()
        logger.debug(f"Received message on {message.topic}: {payload[:100]}")

    def connect(self):
        """Connect to the MQTT broker."""
        try:
            logger.info(f"Connecting to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}...")
            logger.info(f"Using client ID: {MQTT_CLIENT_ID}")
            
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
        """Disconnect from the MQTT broker."""
        self.client.loop_stop()
        self.client.disconnect()
        logger.info("Disconnected from MQTT broker")

    def ensure_connected(self) -> bool:
        """Ensure the client is connected, reconnecting if necessary."""
        if not self.connected:
            return self.connect()
        return True

    async def discover_topics(
        self, base_path: str = "#", timeout: float = 3.0
    ) -> dict[str, dict[str, Any]]:
        """
        Discover available topics by subscribing to a wildcard pattern.

        Args:
            base_path: MQTT wildcard pattern (default: # for all topics)
            timeout: How long to collect messages in seconds

        Returns:
            Dictionary of discovered topics with their values
        """
        if not self.ensure_connected():
            raise ConnectionError("Not connected to MQTT broker")

        async with self._lock:
            # Clear previous messages for fresh discovery
            self.messages.clear()
            self._message_event.clear()

            # Subscribe to the wildcard pattern
            result, mid = self.client.subscribe(base_path, qos=1)
            if result != mqtt.MQTT_ERR_SUCCESS:
                raise Exception(f"Failed to subscribe to {base_path}")

            logger.info(f"Subscribed to {base_path}, collecting messages for {timeout}s...")

            # Wait for messages to arrive
            await asyncio.sleep(timeout)

            # Unsubscribe
            self.client.unsubscribe(base_path)

            # Return a copy of collected messages
            return dict(self.messages)

    async def get_topic_value(
        self, topic: str, timeout: float = 5.0
    ) -> dict[str, Any] | None:
        """
        Get the current value of a specific topic.

        Args:
            topic: Full topic path
            timeout: How long to wait for a message

        Returns:
            Message data if received, None if timeout
        """
        if not self.ensure_connected():
            raise ConnectionError("Not connected to MQTT broker")

        async with self._lock:
            # Clear the specific topic from cache
            if topic in self.messages:
                del self.messages[topic]
            self._message_event.clear()

            # Subscribe to the specific topic
            result, mid = self.client.subscribe(topic, qos=1)
            if result != mqtt.MQTT_ERR_SUCCESS:
                raise Exception(f"Failed to subscribe to {topic}")

            logger.info(f"Subscribed to {topic}, waiting for message...")

            # Wait for a message with timeout
            start = time.time()
            while (time.time() - start) < timeout:
                if topic in self.messages:
                    break
                await asyncio.sleep(0.1)

            # Unsubscribe
            self.client.unsubscribe(topic)

            # Return the message if received
            return self.messages.get(topic)


# Create global MQTT client instance
mqtt_client = MQTTClientWrapper()

# Create MCP server instance
server = Server("mqtt-uns")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools."""
    return [
        Tool(
            name="list_uns_topics",
            description=(
                "Discover available topics in the UNS (Unified Namespace) by subscribing "
                "to a wildcard pattern and collecting messages for a brief period. "
                "Use this to explore what data is available in the MQTT broker. "
                "Returns a list of topic paths with their current values."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "base_path": {
                        "type": "string",
                        "description": (
                            "MQTT wildcard pattern to subscribe to. Use '#' for all topics, "
                            "or a specific path like 'flexpack/#' for a subtree. "
                            "Default is '#' (all topics)."
                        ),
                        "default": "#",
                    },
                    "timeout": {
                        "type": "number",
                        "description": (
                            "How long to collect messages in seconds. Longer timeout = more topics discovered. "
                            "Default is 3 seconds."
                        ),
                        "default": 3,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="get_topic_value",
            description=(
                "Read the current retained value from a specific MQTT topic. "
                "Use this when you know the exact topic path and want to read its current value. "
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
                    "timeout": {
                        "type": "number",
                        "description": (
                            "How long to wait for a message in seconds. Default is 5 seconds."
                        ),
                        "default": 5,
                    },
                },
                "required": ["topic"],
            },
        ),
        Tool(
            name="search_topics",
            description=(
                "Find topics matching a pattern or keyword. "
                "Use this when you want to find topics by name without knowing the exact path. "
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
                    "timeout": {
                        "type": "number",
                        "description": (
                            "How long to collect topics before searching in seconds. Default is 3 seconds."
                        ),
                        "default": 3,
                    },
                },
                "required": ["pattern"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""

    if name == "list_uns_topics":
        return await handle_list_uns_topics(arguments)
    elif name == "get_topic_value":
        return await handle_get_topic_value(arguments)
    elif name == "search_topics":
        return await handle_search_topics(arguments)
    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def handle_list_uns_topics(arguments: dict[str, Any]) -> list[TextContent]:
    """
    Discover available topics in the UNS.

    Subscribes to a wildcard pattern and collects messages for a brief period
    to discover what topics are available.
    """
    base_path = arguments.get("base_path", "#")
    timeout = arguments.get("timeout", 3.0)

    try:
        topics = await mqtt_client.discover_topics(base_path, timeout)

        if not topics:
            return [
                TextContent(
                    type="text",
                    text=f"No topics discovered with pattern '{base_path}' within {timeout} seconds. "
                    "The broker may have no retained messages, or the pattern may not match any topics.",
                )
            ]

        # Format the results
        result_lines = [f"Discovered {len(topics)} topics:\n"]
        for topic_path, data in sorted(topics.items()):
            payload = data.get("payload", "")
            # Truncate long payloads for readability
            if len(payload) > 100:
                payload = payload[:100] + "..."
            result_lines.append(f"  • {topic_path}: {payload}")

        return [TextContent(type="text", text="\n".join(result_lines))]

    except ConnectionError as e:
        return [TextContent(type="text", text=f"Connection error: {e}")]
    except Exception as e:
        logger.exception("Error in list_uns_topics")
        return [TextContent(type="text", text=f"Error discovering topics: {e}")]


async def handle_get_topic_value(arguments: dict[str, Any]) -> list[TextContent]:
    """
    Read the current value from a specific topic.

    Subscribes to the exact topic path and waits for a retained message
    or a new publish.
    """
    topic = arguments.get("topic")
    if not topic:
        return [TextContent(type="text", text="Error: 'topic' parameter is required")]

    timeout = arguments.get("timeout", 5.0)

    try:
        result = await mqtt_client.get_topic_value(topic, timeout)

        if result is None:
            return [
                TextContent(
                    type="text",
                    text=f"No message received on topic '{topic}' within {timeout} seconds. "
                    "The topic may not exist or have no retained message.",
                )
            ]

        # Format the result
        output = [
            f"Topic: {result['topic']}",
            f"Value: {result['payload']}",
            f"QoS: {result['qos']}",
            f"Retained: {result['retain']}",
            f"Received at: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(result['timestamp']))}",
        ]

        return [TextContent(type="text", text="\n".join(output))]

    except ConnectionError as e:
        return [TextContent(type="text", text=f"Connection error: {e}")]
    except Exception as e:
        logger.exception("Error in get_topic_value")
        return [TextContent(type="text", text=f"Error reading topic: {e}")]


async def handle_search_topics(arguments: dict[str, Any]) -> list[TextContent]:
    """
    Find topics matching a pattern or keyword.

    Uses list_uns_topics internally, then filters results by the pattern.
    Supports glob patterns and simple keyword matching.
    """
    pattern = arguments.get("pattern")
    if not pattern:
        return [TextContent(type="text", text="Error: 'pattern' parameter is required")]

    timeout = arguments.get("timeout", 3.0)

    try:
        # First, discover all topics
        all_topics = await mqtt_client.discover_topics("#", timeout)

        if not all_topics:
            return [
                TextContent(
                    type="text",
                    text=f"No topics discovered to search through. "
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
                    f"Searched through {len(all_topics)} available topics.",
                )
            ]

        # Format the results
        result_lines = [
            f"Found {len(matching_topics)} topics matching '{pattern}':\n"
        ]
        for topic_path, data in sorted(matching_topics.items()):
            payload = data.get("payload", "")
            # Truncate long payloads for readability
            if len(payload) > 100:
                payload = payload[:100] + "..."
            result_lines.append(f"  • {topic_path}: {payload}")

        return [TextContent(type="text", text="\n".join(result_lines))]

    except ConnectionError as e:
        return [TextContent(type="text", text=f"Connection error: {e}")]
    except Exception as e:
        logger.exception("Error in search_topics")
        return [TextContent(type="text", text=f"Error searching topics: {e}")]


async def main():
    """Main entry point for the MCP server."""
    logger.info("Starting MQTT MCP Server (Read-Only Phase 1)...")
    logger.info(f"MQTT Broker: {MQTT_BROKER}:{MQTT_PORT}")
    logger.info(f"Client ID: {MQTT_CLIENT_ID}")

    # Connect to MQTT broker
    if not mqtt_client.connect():
        logger.error("Failed to connect to MQTT broker. Server will start but tools may fail.")

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
        # Clean up MQTT connection
        mqtt_client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())

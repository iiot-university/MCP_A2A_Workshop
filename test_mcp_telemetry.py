#!/usr/bin/env python3
"""
MCP Server Telemetry Test Script

This script tests the telemetry integration by running each MCP server
directly (not via Claude Desktop) and verifying telemetry publishes to the UNS.

USAGE:
======
1. Open a terminal and run this script to monitor telemetry:
   
   cd /Users/walkerreynolds/PycharmProjects/mcp_a2a/MCP_A2A_Workshop
   python test_mcp_telemetry.py

2. Open Claude Desktop with the MCP servers configured

3. Ask Claude to use the tools (see prompts below)

4. Watch this terminal for telemetry messages appearing in the UNS


CLAUDE DESKTOP PROMPTS TO TEST:
===============================

--- Test 1: MES Server (mes-press103) ---
Prompt: "What is the current status of Press 103? Also show me the OEE summary."

Expected telemetry topics:
  - Enterprise/Dallas/Agents/mes-press103/Identity
  - Enterprise/Dallas/Agents/mes-press103/Status  
  - Enterprise/Dallas/Agents/mes-press103/Heartbeat
  - Enterprise/Dallas/Agents/mes-press103/Tools/get_equipment_status
  - Enterprise/Dallas/Agents/mes-press103/Tools/get_oee_summary


--- Test 2: MQTT Server (mqtt-uns) ---
Prompt: "List all topics in the UNS that contain 'OEE' in the name."

Expected telemetry topics:
  - Enterprise/Dallas/Agents/mqtt-uns/Identity
  - Enterprise/Dallas/Agents/mqtt-uns/Status
  - Enterprise/Dallas/Agents/mqtt-uns/Heartbeat
  - Enterprise/Dallas/Agents/mqtt-uns/Tools/search_topics


--- Test 3: MySQL Server (mysql-mes) ---
Prompt: "Show me the available database schemas, then list the tables in mes_lite."

Expected telemetry topics:
  - Enterprise/Dallas/Agents/mysql-mes/Identity
  - Enterprise/Dallas/Agents/mysql-mes/Status
  - Enterprise/Dallas/Agents/mysql-mes/Heartbeat
  - Enterprise/Dallas/Agents/mysql-mes/Tools/list_schemas
  - Enterprise/Dallas/Agents/mysql-mes/Tools/list_tables


--- Test 4: All Servers Together ---
Prompt: "I need a complete picture of Press 103. Get the equipment status from 
the MES server, search for any 'downtime' topics in the UNS, and query the 
mes_lite.statehistory table for the last 5 state changes on LineID 1."

This should trigger tools on all three servers and you'll see telemetry
from mes-press103, mqtt-uns, and mysql-mes simultaneously.


WHAT TO LOOK FOR:
=================
- Identity messages on startup (agent name, version, tools list)
- Status messages showing connection state (mqtt_connected, mysql_connected)
- Heartbeat messages every 30 seconds
- Tool invocation messages with duration_ms and success status
- Activity messages for each tool call

"""

import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
import paho.mqtt.client as mqtt

# Load environment
load_dotenv(Path(__file__).parent / ".env")

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")

# Subscribe to all agent telemetry
TELEMETRY_TOPIC = "Enterprise/Dallas/Agents/#"

# Track message counts per agent
agent_stats = {}


def on_connect(client, userdata, flags, reason_code, properties):
    """Handle connection."""
    if reason_code == 0:
        print(f"\n{'='*60}")
        print(f"Connected to MQTT broker: {MQTT_BROKER}:{MQTT_PORT}")
        print(f"Subscribing to: {TELEMETRY_TOPIC}")
        print(f"{'='*60}\n")
        client.subscribe(TELEMETRY_TOPIC, qos=1)
    else:
        print(f"Connection failed: {reason_code}")


def on_message(client, userdata, message):
    """Handle incoming telemetry messages."""
    topic = message.topic
    
    try:
        payload = json.loads(message.payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        payload = message.payload.decode("utf-8", errors="replace")
    
    # Parse topic to extract agent and message type
    # Format: Enterprise/Dallas/Agents/{agent_id}/{type}
    parts = topic.split("/")
    if len(parts) >= 5:
        agent_id = parts[3]
        msg_type = "/".join(parts[4:])  # e.g., "Tools/get_oee_summary"
    else:
        agent_id = "unknown"
        msg_type = topic
    
    # Update stats
    if agent_id not in agent_stats:
        agent_stats[agent_id] = {"messages": 0, "first_seen": datetime.now()}
    agent_stats[agent_id]["messages"] += 1
    agent_stats[agent_id]["last_seen"] = datetime.now()
    
    # Format output based on message type
    timestamp = datetime.now().strftime("%H:%M:%S")
    
    if msg_type == "Identity":
        print(f"\n[{timestamp}] 🟢 AGENT STARTED: {agent_id}")
        print(f"    Name: {payload.get('name', 'N/A')}")
        print(f"    Type: {payload.get('agent_type', 'N/A')}")
        print(f"    Version: {payload.get('version', 'N/A')}")
        print(f"    Tools: {', '.join(payload.get('tools', []))}")
        print(f"    Capabilities: {', '.join(payload.get('capabilities', []))}")
        
    elif msg_type == "Status":
        mqtt_status = "✓" if payload.get("mqtt_connected") or payload.get("telemetry_connected") else "✗"
        mysql_status = "✓" if payload.get("mysql_connected") else "✗"
        print(f"[{timestamp}] 📊 STATUS [{agent_id}]: state={payload.get('state')} | mqtt={mqtt_status} mysql={mysql_status} | tools_total={payload.get('tool_calls_total', 0)} failed={payload.get('tool_calls_failed', 0)}")
        
    elif msg_type == "Heartbeat":
        uptime = payload.get("uptime_seconds", 0)
        uptime_str = f"{uptime//60}m {uptime%60}s" if uptime >= 60 else f"{uptime}s"
        print(f"[{timestamp}] 💓 HEARTBEAT [{agent_id}]: uptime={uptime_str}")
        
    elif msg_type.startswith("Tools/"):
        tool_name = msg_type.replace("Tools/", "")
        duration = payload.get("duration_ms", 0)
        success = "✓" if payload.get("success") else "✗"
        count = payload.get("invocation_count", 0)
        print(f"[{timestamp}] 🔧 TOOL CALL [{agent_id}]: {tool_name} | {success} | {duration:.1f}ms | call #{count}")
        if payload.get("error"):
            print(f"    ERROR: {payload.get('error')}")
            
    elif msg_type == "Activity":
        event = payload.get("event", "unknown")
        details = payload.get("details", {})
        if event == "startup":
            print(f"[{timestamp}] 🚀 ACTIVITY [{agent_id}]: {event}")
        elif event == "shutdown":
            print(f"[{timestamp}] 🛑 ACTIVITY [{agent_id}]: {event} | uptime={details.get('uptime_seconds', 0)}s | total_calls={details.get('total_tool_calls', 0)}")
        elif event == "tool_call":
            pass  # Already logged above
        else:
            print(f"[{timestamp}] 📝 ACTIVITY [{agent_id}]: {event} | {details}")
    else:
        print(f"[{timestamp}] 📨 MESSAGE [{agent_id}]: {msg_type}")
        print(f"    {json.dumps(payload, indent=2)[:200]}")


def print_stats():
    """Print summary statistics."""
    print(f"\n{'='*60}")
    print("AGENT STATISTICS")
    print(f"{'='*60}")
    for agent_id, stats in agent_stats.items():
        duration = (stats["last_seen"] - stats["first_seen"]).total_seconds()
        print(f"  {agent_id}:")
        print(f"    Messages: {stats['messages']}")
        print(f"    First seen: {stats['first_seen'].strftime('%H:%M:%S')}")
        print(f"    Last seen: {stats['last_seen'].strftime('%H:%M:%S')}")
        print(f"    Duration: {duration:.0f}s")
    print(f"{'='*60}\n")


def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║           MCP SERVER TELEMETRY MONITOR                       ║
╠══════════════════════════════════════════════════════════════╣
║  This script monitors agent telemetry from the UNS.          ║
║                                                              ║
║  1. Keep this terminal open                                  ║
║  2. Open Claude Desktop with MCP servers configured          ║
║  3. Ask Claude to use the tools (see prompts in script)      ║
║  4. Watch telemetry appear here                              ║
║                                                              ║
║  Press Ctrl+C to stop and see statistics                     ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    # Create MQTT client
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"telemetry-monitor-{os.getpid()}",
        protocol=mqtt.MQTTv311,
    )
    
    client.on_connect = on_connect
    client.on_message = on_message
    
    if MQTT_USERNAME and MQTT_PASSWORD:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    
    print(f"Connecting to {MQTT_BROKER}:{MQTT_PORT}...")
    
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        client.loop_forever()
    except KeyboardInterrupt:
        print("\n\nStopping monitor...")
        print_stats()
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.disconnect()


if __name__ == "__main__":
    main()

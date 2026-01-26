# Agent Telemetry — UNS Publishing Module

**Shared module for publishing agent/server state to the Unified Namespace**

---

## Overview

This module provides a shared telemetry system that enables all MCP servers and HTTP agents to publish their state, activity, and health information to the UNS (Unified Namespace) via MQTT. Anyone viewing the UNS can see what agents are doing in real time.

### Why?

- **Visibility** — See all active agents and their current state in one place
- **Debugging** — Track tool invocations, errors, and performance
- **Monitoring** — Heartbeats show which agents are alive and connected
- **Audit Trail** — Log of what agents are doing and when

---

## UNS Topic Structure

All telemetry publishes to a dedicated namespace under the enterprise hierarchy:

```
Enterprise/Dallas/Agents/{agent_id}/
├── Identity          # Agent metadata (on startup + with heartbeat)
├── Status            # Connection health (on change + with heartbeat)
├── Heartbeat         # Alive signal (every 30 seconds)
├── Tools/{tool_name} # Invocation details (on each call)
└── Activity          # Event stream (startup, shutdown, tool calls)
```

### Topic Details

| Topic | QoS | Frequency | Description |
|-------|-----|-----------|-------------|
| `.../Identity` | 1 | On startup + with heartbeat | Agent name, version, type, capabilities |
| `.../Status` | 1 | On change + with heartbeat | Connection status, uptime, error count |
| `.../Heartbeat` | 0 | Every 30s | Timestamp proving agent is alive |
| `.../Tools/{name}` | 1 | On invocation | Last call time, duration, success/fail |
| `.../Activity` | 0 | On event | Rolling log of recent actions |

**Note:** No retained messages are used. Identity and Status are republished with each heartbeat so subscribers can discover active agents by listening for ~30 seconds.

---

## Integrated Servers

The following servers have telemetry enabled:

| Server | Agent ID | Type | Status |
|--------|----------|------|--------|
| MQTT MCP Server | `mqtt-uns` | mcp | ✅ Integrated |
| MySQL MCP Server | `mysql-mes` | mcp | ✅ Integrated |
| MES MCP Server | `mes-press103` | mcp | ✅ Integrated |
| Production Agent | `production-agent` | http | ✅ Integrated |
| MES HTTP Server | `mes-http` | http | ✅ Integrated |

---

## Payload Schemas

### Identity (published on startup + with heartbeat)

```json
{
  "agent_id": "mes-press103",
  "agent_type": "mcp",
  "name": "MES MCP Server - Press 103",
  "version": "1.0.0",
  "description": "Domain-specific MES server for Press 103",
  "capabilities": ["mqtt", "mysql"],
  "tools": ["get_equipment_status", "get_oee_summary", "get_downtime_summary"],
  "started_at": "2026-01-26T10:30:00Z",
  "host": "walkers-macbook.local"
}
```

### Status (published on connection changes + with heartbeat)

```json
{
  "agent_id": "mes-press103",
  "timestamp": "2026-01-26T10:35:00Z",
  "state": "running",
  "uptime_seconds": 300,
  "telemetry_connected": true,
  "mqtt_connected": true,
  "mysql_connected": true,
  "tool_calls_total": 42,
  "tool_calls_failed": 1,
  "last_error": null
}
```

### Heartbeat (published every 30 seconds)

```json
{
  "agent_id": "mes-press103",
  "timestamp": "2026-01-26T10:35:30Z",
  "uptime_seconds": 330
}
```

### Tool Invocation (published after each tool call)

```json
{
  "agent_id": "mes-press103",
  "tool": "get_oee_summary",
  "timestamp": "2026-01-26T10:34:15Z",
  "duration_ms": 45.2,
  "success": true,
  "error": null,
  "invocation_count": 12
}
```

### Activity (published on significant events)

```json
{
  "agent_id": "mes-press103",
  "timestamp": "2026-01-26T10:34:15Z",
  "event": "tool_call",
  "details": {
    "tool": "get_oee_summary",
    "success": true,
    "duration_ms": 45.2
  }
}
```

---

## Integration Guide

### For MCP Servers (stdio transport)

```python
# 1. Add to imports (after logging is configured)
import sys
from pathlib import Path

_project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(_project_root))

try:
    from shared.agent_telemetry import AgentTelemetry
    TELEMETRY_AVAILABLE = True
except ImportError:
    TELEMETRY_AVAILABLE = False
    AgentTelemetry = None

# 2. Create telemetry instance (after logger is defined)
if TELEMETRY_AVAILABLE:
    telemetry = AgentTelemetry(
        agent_id="my-server",
        agent_type="mcp",
        name="My MCP Server",
        version="1.0.0",
        tools=["tool1", "tool2"],
        capabilities=["mqtt"],
    )
else:
    telemetry = None

# 3. Wrap tool calls
@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if telemetry:
        with telemetry.track_tool(name):
            return await _route_tool(name, arguments)
    else:
        return await _route_tool(name, arguments)

# 4. Start/stop in main()
async def main():
    # ... connection setup ...
    
    if telemetry:
        telemetry.start()
        telemetry.update_status(mqtt=mqtt_connected)
    
    try:
        # ... run server ...
    finally:
        if telemetry:
            telemetry.stop()
```

### For HTTP Servers (FastAPI)

```python
from shared.agent_telemetry import AgentTelemetry

telemetry = AgentTelemetry(
    agent_id="my-http-server",
    agent_type="http",
    name="My HTTP Server",
    version="1.0.0",
    tools=["endpoint1", "endpoint2"],
)

@app.on_event("startup")
async def startup():
    telemetry.start()
    telemetry.update_status(mqtt=True, mysql=True)

@app.on_event("shutdown")
async def shutdown():
    telemetry.stop()

@app.get("/api/endpoint1")
async def endpoint1():
    with telemetry.track_tool("endpoint1"):
        # ... endpoint logic ...
        return result
```

---

## Configuration

The module reads MQTT credentials from environment variables (same `.env` file):

| Variable | Description |
|----------|-------------|
| `MQTT_BROKER` | Broker hostname |
| `MQTT_PORT` | Broker port (default: 1883) |
| `MQTT_USERNAME` | Authentication username |
| `MQTT_PASSWORD` | Authentication password |

Optional constructor parameters:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `heartbeat_interval` | 30 | Seconds between heartbeat publishes |
| `base_topic` | `Enterprise/Dallas/Agents` | UNS base path for telemetry |
| `publish_activity` | True | Whether to publish activity stream |

---

## Files

```
shared/
├── __init__.py             # Makes shared a package
└── agent_telemetry/
    ├── __init__.py         # Package exports (AgentTelemetry)
    ├── telemetry.py        # AgentTelemetry class implementation
    ├── requirements.txt    # Dependencies (paho-mqtt, python-dotenv)
    └── README.md           # This file
```

---

## Viewing Telemetry

Once agents are running with telemetry enabled, view their state using:

1. **MQTT Explorer** — Subscribe to `Enterprise/Dallas/Agents/#`
2. **Claude Desktop** — Ask: "What agents are currently active in the UNS?"
3. **Custom Dashboard** — Subscribe and visualize agent health

### Example Queries (via MQTT MCP Server)

- "List all topics under Enterprise/Dallas/Agents"
- "What is the status of the mes-press103 agent?"
- "Show me the last tool invocation for the mysql-mes agent"
- "Which agents have heartbeats in the last minute?"

---

## Dependencies

```
paho-mqtt>=2.0.0
python-dotenv>=1.0.0
```

**Note:** Servers using this module must have `paho-mqtt` installed in their virtual environment.

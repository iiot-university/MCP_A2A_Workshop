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
├── Identity          # Static: Agent metadata (published on startup)
├── Status            # Dynamic: Current connection/health status
├── Heartbeat         # Periodic: Alive signal with timestamp
├── Tools/
│   └── {tool_name}   # Dynamic: Last invocation details per tool
└── Activity          # Stream: Recent activity log (last N events)
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

## Payload Schemas

### Identity (published once on startup)

```json
{
  "agent_id": "mes-press103",
  "agent_type": "mcp",
  "name": "MES MCP Server - Press 103",
  "version": "1.0.0",
  "description": "Domain-specific MES server for Press 103",
  "capabilities": ["mqtt", "mysql"],
  "tools": ["get_equipment_status", "get_oee_summary", "get_downtime_summary", "get_active_work_order", "log_observation"],
  "started_at": "2026-01-26T10:30:00Z",
  "host": "walkers-macbook.local"
}
```

### Status (published on connection changes)

```json
{
  "agent_id": "mes-press103",
  "timestamp": "2026-01-26T10:35:00Z",
  "state": "running",
  "uptime_seconds": 300,
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
  "duration_ms": 45,
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
    "success": true
  }
}
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Servers (import shared module)                                             │
│                                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │ MQTT MCP Server │  │ MySQL MCP Server│  │ MES MCP Server  │              │
│  │ (mqtt-uns)      │  │ (mysql-mes)     │  │ (mes-press103)  │              │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘              │
│           │                    │                    │                       │
│  ┌────────┴────────┐  ┌────────┴────────┐  ┌────────┴────────┐              │
│  │ Production Agent│  │ MES HTTP Server │  │  (Future...)    │              │
│  │ (A2A :8001)     │  │ (REST :8002)    │  │                 │              │
│  └────────┬────────┘  └────────┬────────┘  └─────────────────┘              │
│           │                    │                                            │
└───────────┼────────────────────┼────────────────────────────────────────────┘
            │                    │
            ▼                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        AgentTelemetry (shared module)                       │
│                                                                             │
│   - Manages dedicated MQTT connection for telemetry                         │
│   - Publishes Identity on startup                                           │
│   - Publishes Status on connection changes                                  │
│   - Publishes Heartbeat every 30 seconds (background thread)                │
│   - Provides decorators/wrappers for tool invocation tracking               │
│   - Thread-safe, non-blocking                                               │
│                                                                             │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │
                                   ▼ MQTT Publish
┌─────────────────────────────────────────────────────────────────────────────┐
│                              MQTT Broker (UNS)                              │
│                        balancer.virtualfactory.online                       │
│                                                                             │
│   Enterprise/Dallas/Agents/                                                 │
│   ├── mqtt-uns/                                                             │
│   │   ├── Identity                                                          │
│   │   ├── Status                                                            │
│   │   ├── Heartbeat                                                         │
│   │   └── Tools/list_uns_topics                                             │
│   ├── mysql-mes/                                                            │
│   │   ├── Identity                                                          │
│   │   ├── Status                                                            │
│   │   └── Tools/execute_query                                               │
│   ├── mes-press103/                                                         │
│   │   ├── Identity                                                          │
│   │   ├── Status                                                            │
│   │   └── Tools/get_oee_summary                                             │
│   └── production-agent/                                                     │
│       ├── Identity                                                          │
│       ├── Status                                                            │
│       └── Tools/get_equipment_status                                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Integration

### For MCP Servers (stdio transport)

```python
from shared.agent_telemetry import AgentTelemetry

# Initialize telemetry
telemetry = AgentTelemetry(
    agent_id="mes-press103",
    agent_type="mcp",
    name="MES MCP Server - Press 103",
    version="1.0.0",
    tools=["get_equipment_status", "get_oee_summary", ...],
)

# Start telemetry (connects to MQTT, publishes Identity, starts heartbeat)
telemetry.start()

# Wrap tool calls to track invocations
@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    with telemetry.track_tool(name):
        # ... existing tool logic ...
        return result

# On shutdown
telemetry.stop()
```

### For HTTP Servers (FastAPI)

```python
from shared.agent_telemetry import AgentTelemetry

telemetry = AgentTelemetry(
    agent_id="production-agent",
    agent_type="http",
    name="Production Agent",
    version="1.0.0",
    tools=["get_equipment_status", "get_oee_summary", "get_downtime_summary"],
)

@app.on_event("startup")
async def startup():
    telemetry.start()

@app.on_event("shutdown")
async def shutdown():
    telemetry.stop()

# Wrap skill calls
@app.get("/a2a/skills/get_equipment_status")
async def skill_get_equipment_status():
    with telemetry.track_tool("get_equipment_status"):
        data = get_equipment_status()
        return {"skill": "get_equipment_status", "data": data}
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

Optional configuration via constructor:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `heartbeat_interval` | 30 | Seconds between heartbeat publishes |
| `base_topic` | `Enterprise/Dallas/Agents` | UNS base path for telemetry |
| `publish_activity` | True | Whether to publish activity stream |

---

## Files

```
shared/
└── agent_telemetry/
    ├── README.md           # This file
    ├── __init__.py         # Package exports
    ├── telemetry.py        # AgentTelemetry class
    └── requirements.txt    # Dependencies (paho-mqtt, python-dotenv)
```

---

## Viewing Telemetry in the UNS

Once agents are running with telemetry enabled, you can view their state using:

1. **MQTT Explorer** — Subscribe to `Enterprise/Dallas/Agents/#`
2. **Claude Desktop** — Ask the MQTT MCP Server: "What agents are currently active?"
3. **Custom Dashboard** — Subscribe and visualize agent health

### Example Queries (via MQTT MCP Server)

- "List all topics under Enterprise/Dallas/Agents"
- "What is the status of the mes-press103 agent?"
- "Show me the last tool invocation for the production agent"
- "Which agents have heartbeats in the last minute?"

---

## Implementation Plan

1. **Create shared module** — `shared/agent_telemetry/telemetry.py`
2. **Integrate into MES MCP Server** — Test with one server first
3. **Integrate into remaining MCP servers** — MQTT and MySQL servers
4. **Integrate into HTTP servers** — Production Agent and MES HTTP Server
5. **Test end-to-end** — Verify all agents visible in UNS
6. **Document** — Update main README with telemetry info

---

## Dependencies

```
paho-mqtt>=2.0.0
python-dotenv>=1.0.0
```

No additional dependencies beyond what the servers already use.

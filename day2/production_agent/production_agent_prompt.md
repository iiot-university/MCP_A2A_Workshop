# Cursor Prompt: Build Production Agent A2A Server

**Objective:** Create `src/production_agent.py` — a FastAPI server implementing the A2A protocol for Press 103 MES data.

**Location:** `/Users/walkerreynolds/PycharmProjects/mcp_a2a/MCP_A2A_Workshop/day2/production_agent/src/production_agent.py`

---

## Reference Implementation

Copy the MQTT client wrapper and MySQL connection pool patterns from:
`/Users/walkerreynolds/PycharmProjects/mcp_a2a/MCP_A2A_Workshop/day1/mes_server/src/mes_mcp_server.py`

Use the same:
- Environment loading pattern (`.env` from root: `Path(__file__).parent.parent.parent.parent / ".env"`)
- MQTT client class with paho-mqtt 2.0+ API (`CallbackAPIVersion.VERSION2`)
- MySQL connection pool with `mysql-connector-python`
- Press 103 constants and UNS topic definitions
- Helper functions (`safe_float`, `safe_int`, `format_duration`)

---

## Build Specification

Read the full spec from:
`/Users/walkerreynolds/PycharmProjects/mcp_a2a/MCP_A2A_Workshop/day2/production_agent/README.md`

---

## Required Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/.well-known/agent.json` | Return Agent Card JSON |
| POST | `/a2a/message/send` | Receive message, route to skill, return task with artifacts |
| GET | `/a2a/tasks/{task_id}` | Retrieve task by ID |
| GET | `/a2a/skills/get_equipment_status` | Direct skill access |
| GET | `/a2a/skills/get_oee_summary` | Direct skill access |
| GET | `/a2a/skills/get_downtime_summary` | Direct skill access (accepts `hours_back` query param) |
| GET | `/health` | Return connection status |

---

## Pydantic Models Needed

```python
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
```

---

## Skill Routing Logic (for `/a2a/message/send`)

Parse the text from `message.parts[0].text` and route based on keywords:

| Keywords | Skill |
|----------|-------|
| status, running, state, speed, shift | `get_equipment_status` |
| oee, performance, availability, quality, count | `get_oee_summary` |
| downtime, down, stopped, reason, why | `get_downtime_summary` |
| (default) | `get_equipment_status` |

---

## Skill Functions

Adapt from Day 1 `mes_mcp_server.py` handlers, but return `dict` instead of `TextContent`:

1. **`get_equipment_status()`** — Returns dict with: `running`, `state`, `speed`, `setpoint`, `speed_percent`, `shift`, `mqtt_connected`

2. **`get_oee_summary()`** — Returns dict with: `oee`, `availability`, `performance`, `quality`, `good_count`, `bad_count`, `total_count`, `runtime_minutes`, `downtime_minutes`, `rating`

3. **`get_downtime_summary(hours_back: int = 24)`** — Returns dict with: `current_state`, `is_running`, `hours_analyzed`, `total_downtime_minutes`, `planned_minutes`, `unplanned_minutes`, `top_reasons` (list of dicts)

---

## FastAPI Configuration

- Enable CORS for all origins (browser/Claude access)
- Run on port 8001
- Add `@app.on_event("startup")` to init MQTT and MySQL
- Add `@app.on_event("shutdown")` to cleanup connections
- Log to stderr

---

## Task Storage

Use in-memory dict:
```python
task_storage: dict[str, Task] = {}
```

Generate task IDs with `uuid.uuid4()`.

---

## Main Entry Point

```python
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
```

---

## Success Criteria

- Server starts without errors
- MQTT connects to `balancer.virtualfactory.online`
- MySQL connects to `proveit.virtualfactory.online`
- All endpoints return valid JSON
- Browser can access `/.well-known/agent.json` and `/a2a/skills/*` endpoints

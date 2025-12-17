# Production Agent — A2A Server for Press 103

**Workshop:** Day 2, Session 2 — Building Your First A2A Agent  
**Purpose:** Build an A2A-compliant agent that exposes Press 103 MES data  
**Status:** ✅ COMPLETE - Tested and working

---

## Overview

The Production Agent is a FastAPI server implementing the A2A (Agent-to-Agent) protocol. It wraps the same MES functionality from Day 1 but exposes it through standardized A2A endpoints. This agent demonstrates how to transform MCP tools into A2A-compliant skills accessible via HTTP.

### What We're Building

```
┌─────────────────────────────────────────────────────────────────┐
│  Production Agent (FastAPI on :8001)                            │
│                                                                 │
│  A2A Endpoints:                                                 │
│  ├── GET  /.well-known/agent.json    → Agent Card (discovery)   │
│  ├── POST /a2a/message/send          → Send message, get task   │
│  └── GET  /a2a/tasks/{task_id}       → Retrieve task results    │
│                                                                 │
│  Skills:                                                        │
│  ├── get_equipment_status  → Running state, speed, shift        │
│  ├── get_oee_summary       → OEE breakdown (A/P/Q)              │
│  └── get_downtime_summary  → Top downtime reasons               │
│                                                                 │
│  Data Sources:                                                  │
│  ├── MQTT → UNS real-time data (balancer.virtualfactory.online) │
│  └── MySQL → Historical MES data (proveit.virtualfactory.online)│
└─────────────────────────────────────────────────────────────────┘
```

---

## Session Payoffs

### Payoff 1: Browser JSON Response

After building, open in browser:
```
http://localhost:8001/.well-known/agent.json
http://localhost:8001/a2a/skills/get_equipment_status
http://localhost:8001/a2a/skills/get_oee_summary
http://localhost:8001/a2a/skills/get_downtime_summary
```

Students see formatted JSON responses directly in the browser.

### Payoff 2: Claude Desktop React Visualization

Give Claude Desktop this prompt to build a real-time dashboard from the A2A data:

```
I have a Production Agent running at http://localhost:8001 that returns Press 103 manufacturing data.

Fetch data from these endpoints and create a React dashboard:
- http://localhost:8001/a2a/skills/get_equipment_status
- http://localhost:8001/a2a/skills/get_oee_summary  
- http://localhost:8001/a2a/skills/get_downtime_summary

Build a single-page dashboard artifact showing:
1. Equipment status card (running/stopped, current state, speed vs setpoint)
2. OEE gauge or progress bars for Availability, Performance, Quality
3. Good/Bad count display
4. Top downtime reasons if available

Use a dark industrial theme. Add a refresh button that re-fetches all data.
```

---

## Project Structure

```
day2/production_agent/
├── README.md              # This file
├── requirements.txt       # Python dependencies
└── src/
    └── production_agent.py    # Main FastAPI application
```

---

## Cursor Build Instructions

### Step 1: Create requirements.txt

Create `requirements.txt` with these dependencies:

```
fastapi>=0.104.0
uvicorn>=0.24.0
paho-mqtt>=2.0.0
mysql-connector-python>=8.0.0
python-dotenv>=1.0.0
```

### Step 2: Create production_agent.py

Create `src/production_agent.py` following the specification below.

---

## Production Agent Specification

### Environment Configuration

- Load `.env` from project root: `Path(__file__).parent.parent.parent.parent / ".env"`
- This provides MQTT and MySQL credentials

### MQTT Configuration

```python
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
```

### MySQL Configuration

```python
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USERNAME = os.getenv("MYSQL_USERNAME", "")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = "mes_lite"
```

### Press 103 Constants

```python
PRESS_103_LINE_ID = 1
PRESS_103_UNS_BASE = "Enterprise/Dallas/Press/Press 103"
```

### UNS Topics to Subscribe

```python
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
```

---

## Required Endpoints

### 1. Agent Card Discovery

```
GET /.well-known/agent.json
```

Returns the Agent Card describing this agent's identity and capabilities.

**Response:**
```json
{
  "name": "Production Agent",
  "description": "Monitors Press 103 equipment status, OEE, and production metrics for the Flexible Packaging line",
  "url": "http://localhost:8001",
  "version": "1.0.0",
  "provider": {
    "organization": "IIoT University"
  },
  "capabilities": {
    "streaming": false,
    "pushNotifications": false
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
```

### 2. A2A Message Send

```
POST /a2a/message/send
Content-Type: application/json
```

Receives a message, routes to appropriate skill, returns task with artifacts.

**Request Body:**
```json
{
  "message": {
    "role": "user",
    "parts": [
      {
        "type": "text",
        "text": "What is the OEE for Press 103?"
      }
    ]
  }
}
```

**Response:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "state": "completed",
  "artifacts": [
    {
      "type": "application/json",
      "data": {
        "oee": 0.0,
        "availability": 0.1,
        "performance": 0.0,
        "quality": 1.0,
        "good_count": 8576,
        "bad_count": 0,
        "total_count": 8576,
        "runtime_minutes": 1024.0,
        "downtime_minutes": 6450.0,
        "rating": "Needs Improvement"
      }
    }
  ]
}
```

**Skill Routing Logic:**

| Keywords in Message | Skill |
|---------------------|-------|
| status, running, state, speed, shift | get_equipment_status |
| oee, performance, availability, quality, count | get_oee_summary |
| downtime, down, stopped, reason, why | get_downtime_summary |
| (default) | get_equipment_status |

### 3. A2A Task Retrieval

```
GET /a2a/tasks/{task_id}
```

Retrieves a previously created task by ID.

**Response:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "state": "completed",
  "artifacts": [...]
}
```

**Error Response (404):**
```json
{
  "detail": "Task not found"
}
```

### 4. Direct Skill Endpoints (Browser-Friendly)

For easy browser testing and Claude Desktop access, also expose skills directly:

```
GET /a2a/skills/get_equipment_status
GET /a2a/skills/get_oee_summary
GET /a2a/skills/get_downtime_summary?hours_back=24
```

These return the skill result directly as JSON (not wrapped in task/artifacts).

**GET /a2a/skills/get_equipment_status Response:**
```json
{
  "skill": "get_equipment_status",
  "timestamp": "2025-12-17T13:45:00Z",
  "data": {
    "running": false,
    "state": "0",
    "speed": 0.0,
    "setpoint": 25500.0,
    "speed_percent": 0.0,
    "shift": "Day",
    "mqtt_connected": true
  }
}
```

**GET /a2a/skills/get_oee_summary Response:**
```json
{
  "skill": "get_oee_summary",
  "timestamp": "2025-12-17T13:45:00Z",
  "data": {
    "oee": 0.0,
    "availability": 0.1,
    "performance": 0.0,
    "quality": 1.0,
    "good_count": 8576,
    "bad_count": 0,
    "total_count": 8576,
    "runtime_minutes": 1024.0,
    "downtime_minutes": 6450.0,
    "rating": "Needs Improvement"
  }
}
```

**GET /a2a/skills/get_downtime_summary Response:**
```json
{
  "skill": "get_downtime_summary",
  "timestamp": "2025-12-17T13:45:00Z",
  "data": {
    "current_state": "0",
    "is_running": false,
    "hours_analyzed": 24,
    "total_downtime_minutes": 0.0,
    "planned_minutes": 0.0,
    "unplanned_minutes": 0.0,
    "top_reasons": []
  }
}
```

### 5. Health Check

```
GET /health
```

**Response:**
```json
{
  "status": "ok",
  "agent": "Production Agent",
  "mqtt_connected": true,
  "mysql_connected": true,
  "timestamp": "2025-12-17T13:45:00Z"
}
```

---

## Implementation Requirements

### MQTT Client

- Use paho-mqtt 2.0+ API with `CallbackAPIVersion.VERSION2`
- Subscribe to `{PRESS_103_UNS_BASE}/#` on connect
- Cache messages to file-based JSON (`production_cache.json`)
- Use thread-safe atomic writes
- Unique client ID with UUID suffix

Reference: Copy pattern from `day1/mes_server/src/mes_mcp_server.py`

### MySQL Connection Pool

- Use mysql-connector-python with connection pooling
- Pool size: 3 connections
- Read-only queries (SELECT only)
- Query for downtime uses `statehistory` table

Reference: Copy pattern from `day1/mes_server/src/mes_mcp_server.py`

### Task Storage

- In-memory dict is fine for workshop demo
- Key: task_id (UUID string)
- Value: Task object with state and artifacts

### FastAPI Configuration

- Enable CORS for all origins (required for browser/Claude access)
- Add startup event to initialize MQTT and MySQL
- Add shutdown event to clean up connections
- Run on port 8001

### Logging

- Log to stderr (not stdout)
- Log level: INFO
- Include connection status on startup

---

## Testing Commands

### Start the Server

```bash
cd /Users/walkerreynolds/PycharmProjects/mcp_a2a/MCP_A2A_Workshop/day2/production_agent
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python src/production_agent.py
```

### Test in Browser

Open these URLs directly:
- http://localhost:8001/.well-known/agent.json
- http://localhost:8001/health
- http://localhost:8001/a2a/skills/get_equipment_status
- http://localhost:8001/a2a/skills/get_oee_summary
- http://localhost:8001/a2a/skills/get_downtime_summary

### Test with curl

```bash
# Agent Card
curl http://localhost:8001/.well-known/agent.json | jq

# Health check
curl http://localhost:8001/health | jq

# Direct skill access
curl http://localhost:8001/a2a/skills/get_equipment_status | jq
curl http://localhost:8001/a2a/skills/get_oee_summary | jq
curl http://localhost:8001/a2a/skills/get_downtime_summary | jq

# A2A message send
curl -X POST http://localhost:8001/a2a/message/send \
  -H "Content-Type: application/json" \
  -d '{
    "message": {
      "role": "user",
      "parts": [{"type": "text", "text": "What is the current OEE?"}]
    }
  }' | jq

# Get task by ID (use task_id from previous response)
curl http://localhost:8001/a2a/tasks/{task_id} | jq
```

---

## Claude Desktop Visualization Prompt

Once the Production Agent is running, give Claude Desktop this prompt:

```
I have an A2A Production Agent running locally that provides manufacturing data for Press 103.

The agent exposes these endpoints:
- http://localhost:8001/a2a/skills/get_equipment_status
- http://localhost:8001/a2a/skills/get_oee_summary
- http://localhost:8001/a2a/skills/get_downtime_summary

Create a React artifact that:

1. Fetches data from all three endpoints on load and when a "Refresh" button is clicked

2. Displays an Equipment Status card showing:
   - Running/Stopped indicator (green/red)
   - Current state code
   - Speed vs Setpoint with percentage
   - Current shift

3. Displays OEE metrics:
   - Overall OEE as a large number with rating
   - Three progress bars for Availability, Performance, Quality
   - Good count and bad count

4. Displays Downtime Summary:
   - Current state
   - Total downtime in hours
   - Planned vs Unplanned breakdown
   - Top 3 downtime reasons if available

Use a dark industrial theme with:
- Dark gray background (#1a1a2e)
- Card backgrounds (#16213e)
- Accent colors: green for good, red for bad, blue for info
- Clean, readable typography

Add error handling for failed fetches and show a loading state.
```

---

## Files to Create

### requirements.txt

```
fastapi>=0.104.0
uvicorn>=0.24.0
paho-mqtt>=2.0.0
mysql-connector-python>=8.0.0
python-dotenv>=1.0.0
```

### src/production_agent.py

Follow the specification above. Key sections:
1. Imports and configuration
2. Pydantic models for A2A structures
3. MQTT client wrapper (copy from Day 1)
4. MySQL connection pool (copy from Day 1)
5. Skill execution functions
6. Agent Card endpoint
7. A2A message/task endpoints
8. Direct skill endpoints
9. Health check endpoint
10. Startup/shutdown events
11. Main entry point

---

## Success Criteria

- [x] Server starts without errors
- [x] MQTT connects to balancer.virtualfactory.online
- [x] MySQL connects to proveit.virtualfactory.online
- [x] Agent Card accessible at `/.well-known/agent.json`
- [x] All three skills return data in browser
- [x] A2A message/send routes to correct skill
- [x] Claude Desktop can build visualization from endpoints

---

## Implementation Notes

### Key Features Implemented

1. **A2A Protocol Compliance**
   - Agent Card discovery endpoint (`/.well-known/agent.json`)
   - Message-based interaction (`/a2a/message/send`)
   - Task-based response pattern (`/a2a/tasks/{task_id}`)

2. **Intelligent Skill Routing**
   - Keyword-based message routing to appropriate skills
   - Natural language query processing
   - Default fallback to equipment status

3. **Browser-Friendly Direct Access**
   - Direct skill endpoints for easy testing
   - Query parameters for customization (e.g., `hours_back`)
   - Formatted JSON responses with timestamps

4. **Production-Ready Architecture**
   - Thread-safe MQTT caching with atomic writes
   - MySQL connection pooling for efficiency
   - CORS enabled for cross-origin access
   - Comprehensive error handling and logging
   - Graceful startup/shutdown with resource cleanup

5. **Pydantic v2 Support**
   - Uses `.model_dump()` for JSON serialization
   - Type-safe request/response models
   - Automatic validation of A2A protocol messages

### Data Flow

```
User Message → A2A Endpoint → Route by Keywords → Execute Skill → Return Task with Artifacts
                    ↓
            Direct Skill Access → Execute Skill → Return Wrapped JSON
```

### Skill Mapping

| Input Keywords | Routed Skill | Data Sources |
|----------------|--------------|--------------|
| oee, performance, availability, quality, count | get_oee_summary | MQTT (UNS) |
| downtime, down, stopped, reason, why | get_downtime_summary | MySQL + MQTT |
| status, running, state, speed, shift (or default) | get_equipment_status | MQTT (UNS) |

---

## Testing Results

All endpoints tested and verified:

✅ Agent Card returns proper JSON structure  
✅ Health check shows MQTT and MySQL connected  
✅ Equipment status shows real-time Press 103 data  
✅ OEE summary calculates correctly with ratings  
✅ Downtime summary queries historical data successfully  
✅ Message routing works for all keyword patterns  
✅ Task storage and retrieval functions properly  
✅ Browser access works without CORS issues

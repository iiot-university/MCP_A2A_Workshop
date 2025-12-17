# Production Agent — A2A Protocol Server

**Day 2, Session 2** — Building Your First A2A Agent

**Status:** ✅ Complete

---

## Overview

This is a **Production Agent** implementing the Agent2Agent (A2A) protocol. It exposes Press 103 MES data via HTTP endpoints, enabling other agents and systems (like N8N) to discover and interact with it programmatically.

---

## Architecture

```
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│   Other Agents      │────▶│   Production Agent  │────▶│   MQTT Broker       │
│   N8N Workflows     │HTTP │   (A2A Server)      │MQTT │   (Real-time)       │
│   Web Dashboards    │     │   Port 8001         │     └─────────────────────┘
│                     │     │                     │
│   /.well-known/     │     │   Skills:           │     ┌─────────────────────┐
│     agent.json      │     │   - equipment_status│────▶│   MySQL Database    │
│                     │     │   - oee_summary     │ SQL │   (Historical)      │
│   /a2a/message/send │     │   - downtime_summary│     └─────────────────────┘
└─────────────────────┘     └─────────────────────┘
```

---

## A2A Protocol Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/.well-known/agent.json` | GET | Agent Card — discovery metadata |
| `/a2a/message/send` | POST | Send message, routes to skill |
| `/a2a/tasks/{task_id}` | GET | Retrieve task result by ID |
| `/health` | GET | Connection status |

---

## Direct Skill Endpoints

For convenience (and browser testing), skills are also exposed directly:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/a2a/skills/get_equipment_status` | GET | Current equipment state |
| `/a2a/skills/get_oee_summary` | GET | OEE metrics breakdown |
| `/a2a/skills/get_downtime_summary` | GET | Downtime Pareto analysis |

---

## Agent Card

The Agent Card at `/.well-known/agent.json` provides:

```json
{
  "name": "Production Agent - Press 103",
  "description": "Monitors Press 103 production metrics",
  "url": "http://localhost:8001",
  "version": "1.0.0",
  "capabilities": {
    "streaming": false,
    "pushNotifications": false
  },
  "skills": [
    {"id": "get_equipment_status", "name": "Get Equipment Status"},
    {"id": "get_oee_summary", "name": "Get OEE Summary"},
    {"id": "get_downtime_summary", "name": "Get Downtime Summary"}
  ]
}
```

---

## Message Routing

When you POST to `/a2a/message/send`, the agent routes based on keywords:

| Keywords | Skill Invoked |
|----------|---------------|
| oee, performance, availability, quality, count | `get_oee_summary` |
| downtime, down, stopped, reason, why | `get_downtime_summary` |
| (default) | `get_equipment_status` |

---

## Files

| File | Description |
|------|-------------|
| `src/production_agent.py` | FastAPI A2A server implementation |
| `production_agent_prompt.md` | Cursor prompt used to build this |
| `requirements.txt` | Python dependencies |
| `README.md` | This file |

---

## Setup

```bash
cd day2/production_agent
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python src/production_agent.py
```

Server starts on **http://localhost:8001**

---

## Testing

```bash
# Agent Card (discovery)
curl http://localhost:8001/.well-known/agent.json

# Direct skill access
curl http://localhost:8001/a2a/skills/get_equipment_status
curl http://localhost:8001/a2a/skills/get_oee_summary
curl http://localhost:8001/a2a/skills/get_downtime_summary?hours_back=24

# A2A message
curl -X POST http://localhost:8001/a2a/message/send \
  -H "Content-Type: application/json" \
  -d '{"message": {"role": "user", "parts": [{"text": "What is the current OEE?"}]}}'

# Health check
curl http://localhost:8001/health
```

---

## Dependencies

```
fastapi>=0.104.0
uvicorn>=0.24.0
paho-mqtt>=2.0.0
mysql-connector-python>=8.0.0
python-dotenv>=1.0.0
```

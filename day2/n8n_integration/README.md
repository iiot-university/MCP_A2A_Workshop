# N8N Integration — MES HTTP Server & Workflows

**Day 2, Session 3** — Multi-Agent Workflows with N8N

**Status:** ✅ Complete

---

## Overview

This module demonstrates integration between N8N workflow orchestration and MES data from the Virtual Factory. It includes an HTTP server exposing Press 103 data and pre-built N8N workflows for import.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Docker                                                         │
│  ┌─────────────┐                                                │
│  │    N8N      │                                                │
│  │  :5678      │                                                │
│  └──────┬──────┘                                                │
│         │ HTTP Request                                          │
│         │ http://host.docker.internal:8002                      │
└─────────┼───────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────┐
│  Mac (localhost)                                                │
│  ┌─────────────────────────────┐                                │
│  │   MES HTTP Server           │                                │
│  │   FastAPI on :8002          │                                │
│  │                             │                                │
│  │   /health                   │                                │
│  │   /equipment/status         │                                │
│  │   /workorder/active         │                                │
│  │   /oee/summary              │                                │
│  │   /downtime/summary         │                                │
│  │   /observation (POST)       │                                │
│  └──────────┬──────────────────┘                                │
└─────────────┼───────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Virtual Factory (Cloud)                                        │
│  ┌─────────────────────┐    ┌─────────────────────┐             │
│  │ MQTT Broker         │    │ MySQL Database      │             │
│  │ balancer.virtual    │    │ proveit.virtual     │             │
│  │ factory.online:1883 │    │ factory.online:3306 │             │
│  └─────────────────────┘    └─────────────────────┘             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Port Assignments

| Server | Port | Purpose |
|--------|------|---------|
| Production Agent | 8001 | A2A protocol (Session 2) |
| **MES HTTP Server** | **8002** | N8N integration (Session 3) |
| N8N | 5678 | Workflow engine (Docker) |

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Connection status |
| `/equipment/status` | GET | Running state, speed, shift |
| `/workorder/active` | GET | Current WO, progress |
| `/oee/summary` | GET | A/P/Q breakdown |
| `/downtime/summary` | GET | Pareto analysis |
| `/observation` | POST | Write to UNS |

---

## N8N Workflows Included

### 1. Shift Status Check (Exercise 1)
**File:** `n8n_shift_status_workflow.json`

Simple linear workflow:
```
Trigger → Get Status → Get OEE → Get Work Order → Build Message → Post Observation
```

### 2. AI Analysis (Bonus)
**File:** `n8n_ai_analysis_workflow.json`

Sends data to Claude API for analysis:
```
Trigger → Get All Data → Prepare Prompt → Claude API → Format Response → Post Observation
```

Requires `ANTHROPIC_API_KEY` in N8N environment variables.

### 3. Decision Logic (Exercise 2)
**File:** `n8n_decision_logic_workflow.json`

Branching based on availability threshold:
```
                              ┌──────────────┐
                         ┌───▶│ Low Avail.   │───┐
Trigger → Get Data → Switch ──┤              │   ├──▶ Post Observation
                         └───▶│ Normal       │───┘
                              └──────────────┘
```

Condition: `availability < 0.5` triggers alert path.

---

## Files

| File | Description |
|------|-------------|
| `mes_http_server.py` | FastAPI server exposing MES endpoints |
| `n8n_shift_status_workflow.json` | Exercise 1: Basic workflow |
| `n8n_ai_analysis_workflow.json` | Bonus: AI-powered analysis |
| `n8n_decision_logic_workflow.json` | Exercise 2: Branching logic |
| `requirements.txt` | Python dependencies |
| `mes_cache.json` | MQTT message cache (auto-generated) |
| `README.md` | This file |

---

## Setup

### 1. Start MES HTTP Server

```bash
cd day2/n8n_integration
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python mes_http_server.py
```

Server starts on **http://localhost:8002**

### 2. Verify Endpoints

```bash
curl http://localhost:8002/health
curl http://localhost:8002/equipment/status
curl http://localhost:8002/oee/summary
```

### 3. Import Workflows into N8N

1. Open http://localhost:5678
2. Click ⋮ menu → Import from File
3. Select workflow JSON file
4. Click "Test Workflow"

---

## N8N Docker Networking

Since N8N runs in Docker, use `host.docker.internal` to reach localhost:

| From N8N | URL |
|----------|-----|
| Health | `http://host.docker.internal:8002/health` |
| Equipment | `http://host.docker.internal:8002/equipment/status` |
| OEE | `http://host.docker.internal:8002/oee/summary` |
| Observation | `http://host.docker.internal:8002/observation` |

---

## Dependencies

```
fastapi>=0.104.0
uvicorn>=0.24.0
paho-mqtt>=2.0.0
mysql-connector-python>=8.0.0
python-dotenv>=1.0.0
```

# MES MCP Server — Press 103 Domain Server

**Day 1, Session 4** — Practical Industrial Use Cases

**Status:** ✅ Complete

---

## Overview

This is a **domain-specific MCP server** that combines MQTT and MySQL to provide manufacturing-focused tools for Press 103. Unlike the generic MQTT and MySQL servers, this server exposes tools that map directly to MES objectives — the questions operators and supervisors actually ask.

---

## Architecture

```
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│   Claude Desktop    │────▶│   MES MCP Server    │────▶│   MQTT Broker       │
│                     │ MCP │   (Press 103)       │MQTT │   (Real-time)       │
│   "Is Press 103     │     │                     │     └─────────────────────┘
│    running?"        │     │   Domain Tools:     │
│                     │     │   - equipment_status│     ┌─────────────────────┐
│   "What's our OEE?" │     │   - active_work_ord │────▶│   MySQL Database    │
│                     │     │   - oee_summary     │ SQL │   (Historical)      │
│   "Why are we down?"│     │   - downtime_summary│     └─────────────────────┘
│                     │     │   - log_observation │
└─────────────────────┘     └─────────────────────┘
```

---

## Design Philosophy: Domain Servers

**Generic servers** expose data access (topics, tables, queries).

**Domain servers** expose business objectives:
- "Is the equipment running?" not "SELECT * FROM statehistory"
- "What's our OEE?" not "Calculate from multiple UNS topics"
- "Why are we down?" not "JOIN statehistory with statereason"

This pattern reduces cognitive load on operators and ensures consistent, correct answers.

---

## Tools Implemented

| Tool | Question It Answers |
|------|---------------------|
| `get_equipment_status` | Is Press 103 running? Current state? Speed? |
| `get_active_work_order` | What are we making? Progress toward target? |
| `get_oee_summary` | A/P/Q breakdown, current performance rating |
| `get_downtime_summary` | Why down? Top reasons (Pareto analysis) |
| `log_observation` | Record agent note to UNS (write operation) |

---

## Scope: Single-Asset Pattern

This server is intentionally scoped to **Press 103 only**:
- LineID: 1
- UNS Base: `Enterprise/Dallas/Press/Press 103/#`

This "single-asset agent" pattern is scalable — deploy one agent per asset, each with focused context and responsibility.

---

## Files

| File | Description |
|------|-------------|
| `src/mes_mcp_server.py` | Main MCP server implementation |
| `CURSOR_PROMPT.md` | Build instructions used to generate the server |
| `requirements.txt` | Python dependencies |
| `README.md` | This file |

---

## Setup

```bash
cd day1/mes_server
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## Claude Desktop Configuration

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mes-press103": {
      "command": "/path/to/day1/mes_server/venv/bin/python",
      "args": ["/path/to/day1/mes_server/src/mes_mcp_server.py"]
    }
  }
}
```

---

## Example Queries

- "What is Press 103 doing right now?"
- "How is Press 103 performing?"
- "Why has Press 103 been down?"
- "What's causing our biggest losses?"
- "Log an observation that we're investigating the speed issue"

---

## Press 103 Data Context

| Metric | Current Value |
|--------|---------------|
| Work Order | 12237611 |
| OEE | ~0% (line stopped) |
| Availability | ~10-13% |
| Quality | 100% |
| Top Downtime | Washdown/Parts Change, Color Match, Running Setup |

---

## Dependencies

```
mcp>=1.0.0
paho-mqtt>=2.0.0
mysql-connector-python>=8.0.0
python-dotenv>=1.0.0
```

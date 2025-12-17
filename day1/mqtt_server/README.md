# MQTT MCP Server — Unified Namespace Access

**Day 1, Session 2** — Building Your First MCP Server

**Status:** ✅ Complete

---

## Overview

This MCP server provides Claude Desktop with read/write access to the Unified Namespace (UNS) via MQTT. It connects to the Flexible Packager virtual factory and exposes tools for discovering topics, reading values, and publishing messages.

---

## Architecture

```
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│   Claude Desktop    │────▶│   MQTT MCP Server   │────▶│   MQTT Broker       │
│                     │ MCP │                     │MQTT │   (UNS)             │
│   Natural Language  │     │   - list_uns_topics │     │   balancer.virtual  │
│   Queries           │     │   - get_topic_value │     │   factory.online    │
│                     │     │   - search_topics   │     │                     │
│                     │     │   - publish_message │     │   Press 103 Data    │
└─────────────────────┘     └─────────────────────┘     └─────────────────────┘
```

---

## Tools Implemented

| Tool | Description |
|------|-------------|
| `list_uns_topics` | Discover topics via wildcard subscription |
| `get_topic_value` | Read retained value from specific topic |
| `search_topics` | Find topics by pattern or keyword |
| `publish_message` | Write messages to UNS topics |

---

## Key Concepts Taught

1. **MCP Server Structure** — `@server.list_tools()` and `@server.call_tool()` decorators
2. **MQTT 2.0 API** — Using `paho-mqtt` with `CallbackAPIVersion.VERSION2`
3. **File-based Caching** — Thread-safe JSON cache for instant responses
4. **Environment Loading** — Credentials from root `.env` file
5. **Unique Client IDs** — UUID suffix prevents broker collisions

---

## Files

| File | Description |
|------|-------------|
| `src/mqtt_mcp_server.py` | Main MCP server implementation |
| `requirements.txt` | Python dependencies |
| `README.md` | This file |

---

## Setup

```bash
cd day1/mqtt_server
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
    "mqtt-uns": {
      "command": "/path/to/day1/mqtt_server/venv/bin/python",
      "args": ["/path/to/day1/mqtt_server/src/mqtt_mcp_server.py"]
    }
  }
}
```

---

## Example Queries

- "What topics are available in the UNS?"
- "What is the current OEE for Press 103?"
- "Search for topics containing 'speed'"
- "Publish a test message to the agent observations topic"

---

## Dependencies

```
mcp>=1.0.0
paho-mqtt>=2.0.0
python-dotenv>=1.0.0
```

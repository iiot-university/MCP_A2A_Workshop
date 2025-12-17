# MySQL MCP Server — Relational Data Access

**Day 1, Session 3** — Multi-Server Architecture

**Status:** ✅ Complete

---

## Overview

This MCP server provides Claude Desktop with read-only access to MySQL databases. It connects to the ProveIt! virtual factory database and exposes tools for schema discovery, table inspection, and SQL queries.

---

## Architecture

```
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│   Claude Desktop    │────▶│   MySQL MCP Server  │────▶│   MySQL Database    │
│                     │ MCP │                     │ SQL │                     │
│   Natural Language  │     │   - list_schemas    │     │   proveit.virtual   │
│   Queries           │     │   - list_tables     │     │   factory.online    │
│                     │     │   - describe_table  │     │                     │
│                     │     │   - execute_query   │     │   mes_lite schema   │
└─────────────────────┘     └─────────────────────┘     └─────────────────────┘
```

---

## Tools Implemented

| Tool | Description |
|------|-------------|
| `list_schemas` | Discover available databases |
| `list_tables` | List tables with approximate row counts |
| `describe_table` | Get column definitions and types |
| `execute_query` | Run read-only SELECT queries |

---

## Key Concepts Taught

1. **Multi-Server MCP** — Running multiple MCP servers in Claude Desktop
2. **Connection Pooling** — Efficient database connection management
3. **Read-Only Enforcement** — Only SELECT queries allowed
4. **Schema Introspection** — Dynamic discovery of database structure
5. **Cross-Server Queries** — Combining MQTT and MySQL data via natural language

---

## Files

| File | Description |
|------|-------------|
| `src/mysql_mcp_server.py` | Main MCP server implementation |
| `requirements.txt` | Python dependencies |
| `schemas/README.md` | Database schema documentation |
| `README.md` | This file |

---

## Database Schemas

| Schema | Description |
|--------|-------------|
| `mes_lite` | Core MES tables (work_orders, production_runs, equipment, statehistory) |
| `mes_custom` | Custom extensions and user-defined fields |
| `proveitdb` | ProveIt! demo data (batches, quality_checks, recipes) |

---

## Setup

```bash
cd day1/mysql_server
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
    "mysql-mes": {
      "command": "/path/to/day1/mysql_server/venv/bin/python",
      "args": ["/path/to/day1/mysql_server/src/mysql_mcp_server.py"]
    }
  }
}
```

---

## Example Queries

- "What database schemas are available?"
- "Show me the tables in mes_lite"
- "Describe the work_orders table"
- "Get the last 10 work orders for Press 103"
- "What are the top downtime reasons in the last 24 hours?"

---

## Dependencies

```
mcp>=1.0.0
mysql-connector-python>=8.0.0
python-dotenv>=1.0.0
```

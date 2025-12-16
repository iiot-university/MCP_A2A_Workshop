# Multi-Server Architecture — Adding MySQL

## Overview

This section adds a second MCP server that connects to MySQL databases from the Virtual Factory. Combined with the MQTT server from Session 2, Claude can now query both real-time UNS data and relational database records.

## Goals

- Build a second MCP server for relational data access
- Configure Claude Desktop to use multiple MCP servers simultaneously
- Demonstrate cross-server queries using natural language

## Prerequisites

- Completed Session 2 (MQTT MCP Server)
- Access to MySQL at proveit.virtualfactory.online:3306
- MySQL client libraries installed

---

## Why Multiple Servers?

Separation of concerns in industrial systems:

| Server | Data Type | Use Case |
|--------|-----------|----------|
| MQTT Server | Real-time process data | Current values, live status, alarms |
| MySQL Server | Historical/transactional data | Batch records, production logs, recipes |

Benefits:
- Each server focused on one data domain
- Independent scaling and maintenance
- Clear security boundaries
- Easier troubleshooting

---

## Project Setup

### 1. Project Structure

```
MCP_A2A_Workshop/
├── .env                    # All credentials (root level, gitignored)
├── .env.example            # Template for students
└── day1/
    ├── mqtt_server/        # From Session 2
    └── mysql_server/
        ├── README.md
        ├── requirements.txt
        └── src/
            └── mysql_mcp_server.py
```

### 2. Environment Configuration

Credentials are stored in the root `.env` file. The MySQL settings are:

```
MYSQL_HOST=proveit.virtualfactory.online
MYSQL_PORT=3306
MYSQL_USERNAME=your_username
MYSQL_PASSWORD=your_password
MYSQL_SCHEMAS=hivemq_ese_db,mes_custom,mes_lite,proveitdb
```

**Note:** The `MYSQL_SCHEMAS` variable defines which schemas the MCP server can access. All four schemas from the Virtual Factory database are included.

### 3. Initialize Virtual Environment

```bash
cd MCP_A2A_Workshop/day1/mysql_server
python -m venv venv
source venv/bin/activate
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Database Connection Details

### Server Information

| Setting | Value |
|---------|-------|
| Host | proveit.virtualfactory.online |
| Port | 3306 |

### Available Schemas

| Schema | Purpose | Description |
|--------|---------|-------------|
| hivemq_ese_db | HiveMQ Enterprise Security | User accounts and permissions for the Virtual Factory MQTT broker |
| mes_custom | Custom MES extensions | Custom attributes, user-defined fields, extended configurations |
| mes_lite | Core MES data | Work orders, production runs, equipment, operators, materials |
| proveitdb | ProveIt! demo data | Batch records, quality checks, recipes, process parameters |

All four schemas are accessible to the MCP server and can be queried using natural language through Claude.

**📚 Detailed Schema Documentation:** See the [schemas/](schemas/) directory for comprehensive table definitions, column descriptions, and example queries for each database.

---

## Building Query Tools

### Tool 1 -- list_schemas

Lists available database schemas the agent can access.

**Purpose:** Let Claude discover what databases are available

**Input:** None

**Output:** List of schema names with descriptions

### Tool 2 -- list_tables

Lists tables within a specified schema.

**Purpose:** Let Claude explore database structure

**Input:** Schema name (e.g., `mes_lite`)

**Output:** List of tables with row counts

### Tool 3 -- describe_table

Returns column definitions for a table.

**Purpose:** Let Claude understand table structure before querying

**Input:** Schema name, table name

**Output:** Column names, types, nullable, keys

### Tool 4 -- execute_query

Runs a SELECT query and returns results.

**Purpose:** Let Claude retrieve specific data

**Input:** SQL SELECT statement (read-only)

**Output:** Query results as structured data

### Safety Considerations

- Only allow SELECT statements
- Validate schema/table names against allowlist
- Limit result set size (e.g., max 1000 rows)
- Log all queries for audit

---

## Configuring Claude Desktop for Multi-Server

### Update Config File

Add the MySQL server alongside the existing MQTT server. Use the **venv Python interpreter** for each server:

```json
{
  "mcpServers": {
    "mqtt-uns": {
      "command": "/path/to/MCP_A2A_Workshop/day1/mqtt_server/venv/bin/python",
      "args": ["/path/to/MCP_A2A_Workshop/day1/mqtt_server/src/mqtt_mcp_server.py"]
    },
    "mysql-mes": {
      "command": "/path/to/MCP_A2A_Workshop/day1/mysql_server/venv/bin/python",
      "args": ["/path/to/MCP_A2A_Workshop/day1/mysql_server/src/mysql_mcp_server.py"]
    }
  }
}
```

**Note:** Both servers load credentials from the root `.env` file automatically — no need to pass environment variables in the config.

### Restart Claude Desktop

- Quit completely
- Relaunch
- Verify both servers appear in the MCP server list (hammer icon)

---

## Live Demo -- Querying Both Servers

### Single-Server Queries

1. **MQTT only:**
   > "What is the current filler speed on line 1?"

2. **MySQL only:**
   > "Show me the last 10 production runs from mes_lite"

### Cross-Server Queries

3. **Correlate real-time and historical:**
   > "Is the current line speed consistent with the target from the active work order?"

4. **Context-aware queries:**
   > "What batch is currently running and what's its quality status?"

### What to Observe

- Claude determines which server to call based on the question
- For cross-server queries, Claude calls both and synthesizes results
- Tool selection happens automatically based on context

---

## How Claude Routes Requests

Claude uses tool descriptions to decide which server to call:

| Question Type | Server Selected | Why |
|--------------|-----------------|-----|
| "current value of..." | MQTT | Real-time data |
| "show me records from..." | MySQL | Historical data |
| "compare current to target..." | Both | Needs both sources |

Key insight -- Good tool descriptions make routing automatic.

---

## Checkpoint

By the end of this section, you have:

- [ ] A second MCP server connected to MySQL
- [ ] Tools for exploring schemas and tables
- [ ] Safe, read-only query execution
- [ ] Claude Desktop configured for multiple servers
- [ ] Demonstrated cross-server natural language queries

**Next:** Build practical industrial dashboards using both servers

---

## Files in This Section

| File | Purpose |
|------|---------|
| `schemas/` | Database schema documentation for agents |
| `schemas/MES_LITE.md` | Core MES tables reference |
| `schemas/MES_CUSTOM.md` | Extended MES features reference |
| `schemas/PROVEITDB.md` | Demo data reference |
| `README.md` | This guide |
| `requirements.txt` | Python dependencies |
| `src/mysql_mcp_server.py` | Main MCP server implementation (built with Cursor) |

**Note:** Credentials are in the root `.env` file, not in this directory.

---

## Troubleshooting

### MySQL connection fails

- Verify hostname and port
- Check credentials in root .env
- Test connection with mysql client directly
- Check firewall/network access

### Queries return errors

- Verify schema name is correct
- Check table exists in schema
- Validate SQL syntax
- Check query isn't hitting row limits

### Claude uses wrong server

- Review tool descriptions -- make them more specific
- Check that both servers loaded successfully
- Look at Claude's reasoning in the tool use panel

---

## Resources

- [MCP Documentation](https://modelcontextprotocol.io)
- [MySQL Connector Python](https://dev.mysql.com/doc/connector-python/en/)
- [ISA-95 Data Model](https://www.isa.org/isa95)

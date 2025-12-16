# Advanced MCP and Agent to Agent Workshop

**IIoT University | December 16-17, 2025**

A hands-on workshop for engineers, integrators, and digital transformation professionals in industrial automation. Learn to build multi-server MCP architectures and implement the Agent2Agent protocol for collaborative AI systems.

---

## Workshop Overview

| Day | Topic | Focus |
|-----|-------|-------|
| Day 1 | Advanced MCP | Multi-server architectures connecting AI to industrial data |
| Day 2 | Agent2Agent | Collaborative intelligence with coordinating AI agents |

---

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/iiot-university/MCP_A2A_Workshop.git
cd MCP_A2A_Workshop
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your credentials
```

### 3. Follow the Day 1 or Day 2 Guide

Each session has its own README with step-by-step instructions.

---

## Project Structure

```
MCP_A2A_Workshop/
├── .env                    # Credentials (gitignored - create from .env.example)
├── .env.example            # Template with placeholder values
├── README.md               # This file
│
├── day1/                   # Advanced MCP - Multi-Server Architectures
│   ├── mqtt_server/        # Session 2: MQTT MCP Server
│   │   ├── README.md       # Step-by-step guide
│   │   ├── requirements.txt
│   │   └── src/
│   │       └── mqtt_mcp_server.py
│   │
│   ├── mysql_server/       # Session 3: MySQL MCP Server
│   │   ├── README.md       # Step-by-step guide
│   │   ├── requirements.txt
│   │   └── src/
│   │       └── mysql_mcp_server.py
│   │
│   └── use_cases/          # Session 4: Industrial Use Cases
│       └── README.md       # Dashboard prompts and examples
│
└── day2/                   # Agent2Agent - Collaborative Intelligence
    └── (coming Day 2)
```

---

## Day 1 Sessions

### Session 1: Introduction & Workshop Overview (9:00 - 9:45)

Instructor-led introduction covering:
- Learning objectives for both days
- Infrastructure overview (cloud and local)
- Virtual Factory data sources
- What is MCP and why manufacturers should care

### Session 2: Building Your First MCP Server — MQTT & UNS (10:00 - 10:45) ✅

**Guide:** [day1/mqtt_server/README.md](day1/mqtt_server/README.md)

**Status:** Complete

Build a Python MCP server that connects to the Flexible Packager Unified Namespace via MQTT. Query and publish to the UNS using natural language through Claude Desktop.

**Tools Implemented:**
- `list_uns_topics` - Discover available topics
- `get_topic_value` - Read specific topic values  
- `search_topics` - Search topics by pattern
- `publish_message` - Publish messages to topics

### Session 3: Multi-Server Architecture — Adding MySQL (11:00 - 11:45) ✅

**Guide:** [day1/mysql_server/README.md](day1/mysql_server/README.md)

**Status:** Complete

Add a second MCP server for relational database access. Configure Claude Desktop for multiple servers and demonstrate cross-server queries.

**Tools Implemented:**
- `list_schemas` - Discover available databases
- `list_tables` - List tables with row counts
- `describe_table` - Get column definitions
- `execute_query` - Run read-only SELECT queries

### Session 4: Practical Industrial Use Cases (12:00 - 12:45)

**Guide:** [day1/use_cases/README.md](day1/use_cases/README.md)

Apply multi-server MCP to real scenarios. Build React dashboards from natural language prompts that pull data from both MQTT and MySQL sources.

---

## Infrastructure

### Cloud Resources

| Resource | Endpoint | Purpose |
|----------|----------|---------|
| HiveMQ Broker | balancer.virtualfactory.online:1883 | MQTT / Unified Namespace |
| MySQL Database | proveit.virtualfactory.online:3306 | MES and batch data |
| Ignition | ignition.virtualfactory.online:8088 | SCADA (internal use) |

### Virtual Factory Data

Data comes from the Flexible Packager virtual factory built for ProveIt! Conference 2025. The UNS follows ISA-95 hierarchy and publishes to the HiveMQ broker.

### Database Schemas

| Schema | Purpose |
|--------|---------|
| hivemq_ese_db | HiveMQ Enterprise Security -- user accounts and broker permissions |
| mes_custom | Custom extensions and user-defined fields |
| mes_lite | Core MES data -- work orders, production runs, equipment |
| proveitdb | ProveIt! demo data -- batches, quality checks, recipes |

---

## Local Development

### Prerequisites

- Python 3.10+
- Claude Desktop
- Cursor IDE (recommended)
- Git

### Tools We Use

| Tool | Purpose |
|------|---------|
| Claude Desktop | MCP client for natural language interaction |
| Cursor | IDE with AI-assisted coding |
| Python | MCP server implementation |
| paho-mqtt | MQTT client library |
| mysql-connector-python | MySQL client library |

---

## Environment Variables

All credentials are stored in the root `.env` file. This file is gitignored and never committed.

```bash
# MQTT Broker Configuration
MQTT_BROKER=balancer.virtualfactory.online
MQTT_PORT=1883
MQTT_USERNAME=your_username
MQTT_PASSWORD=your_password
# Note: MQTT_CLIENT_ID is auto-generated with a unique suffix (e.g., mcp-mqtt-a1b2c3d4)
# to allow multiple MCP server instances to run simultaneously without conflicts

# MySQL Database Configuration
MYSQL_HOST=proveit.virtualfactory.online
MYSQL_PORT=3306
MYSQL_USERNAME=your_username
MYSQL_PASSWORD=your_password
MYSQL_SCHEMAS=hivemq_ese_db,mes_custom,mes_lite,proveitdb
```

---

## For Cursor / AI Agents

When building code for this workshop:

1. **Read the session README first** -- Each session directory contains a README with specifications for what to build

2. **Use the root .env for credentials** -- Load environment variables from the project root, not from session directories

3. **Follow MCP patterns** -- Servers use stdio transport, expose tools for actions and resources for data

4. **Ground examples in the Virtual Factory** -- Use real topic paths and table names from the infrastructure described above

5. **Keep code simple and readable** -- This is teaching code, prioritize clarity over optimization

---

## GitHub Repository

**Public:** https://github.com/iiot-university/MCP_A2A_Workshop

Code is published at the end of each day for students to clone and reference.

---

## Resources

- [MCP Documentation](https://modelcontextprotocol.io)
- [Anthropic MCP GitHub](https://github.com/anthropics/anthropic-cookbook/tree/main/misc/model_context_protocol)
- [Paho MQTT Python](https://eclipse.dev/paho/files/paho.mqtt.python/html/)
- [HiveMQ MQTT Essentials](https://www.hivemq.com/mqtt-essentials/)
- [ISA-95 Standard](https://www.isa.org/isa95)

---

## License

MIT License - See LICENSE file for details.

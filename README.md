# Advanced MCP and Agent to Agent Workshop

**IIoT University | December 16-17, 2025**

A hands-on workshop for engineers, integrators, and digital transformation professionals in industrial automation. Learn to build multi-server MCP architectures and implement the Agent2Agent protocol for collaborative AI systems.

---

## 🎯 Workshop Status

**Day 1:** ✅ **COMPLETE** - All sessions finished, code tested and published  
**Day 2:** ✅ **COMPLETE** - Production Agent A2A Server implemented and tested

---

## Workshop Overview

| Day | Topic | Focus | Status |
|-----|-------|-------|--------|
| Day 1 | Advanced MCP | Multi-server architectures connecting AI to industrial data | ✅ Complete |
| Day 2 | Agent2Agent | A2A protocol implementation for Press 103 production data | ✅ Complete |

### What We Built

**Day 1 - Advanced MCP:**
- **3 MCP Servers:** MQTT (UNS), MySQL (MES Database), and domain-specific MES server
- **Multi-server architecture** enabling Claude to query both real-time and historical data
- **Domain-specific tooling** for manufacturing operations (OEE, work orders, downtime analysis)
- **React dashboard** with real-time monitoring and AI-powered recommendations
- **Write capabilities** allowing AI agents to log observations back to the UNS

**Day 2 - Agent2Agent:**
- **Production Agent** - FastAPI server implementing A2A protocol for Press 103
- **Agent Card discovery** enabling standardized agent capability advertisement
- **Message-based routing** with intelligent keyword-based skill selection
- **HTTP-accessible skills** for browser testing and web integration
- **Task storage system** with UUID-based retrieval
- **Production-ready architecture** with MQTT caching and MySQL pooling

---

## Learning Outcomes

By completing this workshop, participants will be able to:

### Day 1 Outcomes ✅
- ✅ Build MCP servers in Python from scratch
- ✅ Connect AI agents to industrial MQTT brokers (UNS)
- ✅ Integrate AI agents with relational databases (MySQL)
- ✅ Configure multi-server architectures in Claude Desktop
- ✅ Design domain-specific tooling for manufacturing operations
- ✅ Implement read and write capabilities for AI agents
- ✅ Generate industrial dashboards from natural language prompts
- ✅ Integrate Claude API into web applications

### Day 2 Outcomes ✅
- ✅ Understand the A2A (Agent-to-Agent) protocol specification
- ✅ Build FastAPI servers implementing A2A endpoints
- ✅ Transform MCP tools into A2A-compliant skills
- ✅ Implement Agent Card discovery mechanism
- ✅ Create browser-accessible manufacturing data APIs
- ✅ Design message routing and skill execution patterns
- ✅ Build production-ready agent architecture with proper error handling

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

**Day 1:** Start with [day1/mqtt_server/README.md](day1/mqtt_server/README.md)  
**Day 2:** Start with [day2/production_agent/README.md](day2/production_agent/README.md)

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
│   ├── mes_server/         # Session 4: MES Domain Server
│   │   ├── README.md       # Full specification
│   │   ├── CURSOR_PROMPT.md # Build prompt for Cursor
│   │   ├── requirements.txt
│   │   └── src/
│   │       └── mes_mcp_server.py
│   │
│   └── use_cases/          # Session 4: Documentation
│       └── README.md       # Session guide and use cases
│
└── day2/                   # Agent2Agent - A2A Protocol Implementation
    ├── production_agent/   # Session 2: Production Agent A2A Server
    │   ├── README.md       # Complete specification & testing guide
    │   ├── requirements.txt
    │   └── src/
    │       └── production_agent.py  # FastAPI A2A server
    │
    └── setup/              # Session 1: Setup guide
        └── README.md       # Environment configuration
```

---

## Day 1: Advanced MCP - Multi-Server Architectures ✅ COMPLETE

**Status:** All sessions completed and tested. Code pushed to repository.

### Session 1: Introduction & Workshop Overview (9:00 - 9:45) ✅

Instructor-led introduction covering:
- Learning objectives for both days
- Infrastructure overview (cloud and local)
- Virtual Factory data sources
- What is MCP and why manufacturers should care

### Session 2: Building Your First MCP Server — MQTT & UNS (10:00 - 10:45) ✅

**Guide:** [day1/mqtt_server/README.md](day1/mqtt_server/README.md)

**Status:** Complete and tested

Built a Python MCP server that connects to the Flexible Packager Unified Namespace via MQTT. Enables querying and publishing to the UNS using natural language through Claude Desktop.

**Tools Implemented:**
- `list_uns_topics` - Discover available topics
- `get_topic_value` - Read specific topic values  
- `search_topics` - Search topics by pattern
- `publish_message` - Publish messages to topics

**Key Features:**
- File-based MQTT caching for instant responses
- Unique client IDs to prevent collisions
- Automatic reconnection with exponential backoff
- Thread-safe cache operations

### Session 3: Multi-Server Architecture — Adding MySQL (11:00 - 11:45) ✅

**Guide:** [day1/mysql_server/README.md](day1/mysql_server/README.md)

**Status:** Complete and tested

Added a second MCP server for relational database access. Configured Claude Desktop for multiple servers and demonstrated cross-server queries combining real-time and historical data.

**Tools Implemented:**
- `list_schemas` - Discover available databases
- `list_tables` - List tables with row counts
- `describe_table` - Get column definitions
- `execute_query` - Run read-only SELECT queries

**Key Features:**
- Read-only query validation with dangerous keyword blocking
- Schema allowlist for security
- Connection pooling for efficiency
- Row limits and query auditing

### Session 4: Practical Industrial Use Cases (12:00 - 12:45) ✅

**Guide:** [day1/use_cases/README.md](day1/use_cases/README.md)

**Status:** Complete and tested

Built a domain-specific MES MCP server for Press 103 that combines MQTT and MySQL into unified MES-objective tools. Demonstrated the "single-asset agent" pattern with manufacturing-specific operations.

**What We Built:**
- MES MCP Server scoped to Press 103 (single-asset agent pattern)
- Tools: `get_equipment_status`, `get_active_work_order`, `get_oee_summary`, `get_downtime_summary`, `log_observation`
- React dashboard with real-time tab and AI recommendations tab
- Claude API integration in artifacts for analysis

**Key Insights:**
- Domain-specific servers reduce token usage and improve accuracy
- MES-objective tools map directly to manufacturing decisions
- Combining real-time (UNS) and historical (MySQL) data in single tools
- Agent observations can be written back to the UNS for tracking

### Day 1 Achievements

✅ Three fully functional MCP servers (MQTT, MySQL, MES)  
✅ Multi-server architecture with Claude Desktop  
✅ Cross-server queries combining real-time and historical data  
✅ Domain-specific tooling for manufacturing operations  
✅ React dashboard with AI-powered recommendations  
✅ Write capabilities to the UNS for agent observations

---

## Day 2: Agent2Agent - A2A Protocol Implementation ✅ COMPLETE

**Status:** Production Agent built, tested, and documented.

**Focus:** Building HTTP-accessible A2A agents that expose manufacturing data through standardized endpoints.

### Session 1: Introduction to A2A Protocol ✅

Instructor-led introduction covering:
- The Agent-to-Agent protocol specification
- Differences between MCP (stdio) and A2A (HTTP)
- Agent Card discovery mechanism
- Message routing and skill execution patterns
- When to use A2A vs MCP

### Session 2: Building the Production Agent ✅

**Guide:** [day2/production_agent/README.md](day2/production_agent/README.md)

**Status:** Complete and tested

Built a FastAPI server implementing the A2A protocol for Press 103 manufacturing data. This agent transforms the Day 1 MES MCP server into an HTTP-accessible A2A-compliant agent.

**A2A Endpoints Implemented:**
- `GET /.well-known/agent.json` - Agent Card discovery
- `POST /a2a/message/send` - Natural language message routing
- `GET /a2a/tasks/{task_id}` - Task result retrieval
- `GET /health` - Connection status

**Direct Skill Endpoints (Browser-Friendly):**
- `GET /a2a/skills/get_equipment_status` - Running state, speed, shift
- `GET /a2a/skills/get_oee_summary` - OEE breakdown with ratings
- `GET /a2a/skills/get_downtime_summary` - Historical downtime analysis

**Key Features:**
- Intelligent keyword-based message routing
- Task-based response pattern with artifacts
- MQTT caching for real-time UNS data
- MySQL connection pooling for historical queries
- CORS enabled for browser/Claude Desktop access
- Production-ready error handling and logging

**Architecture:**
```
┌─────────────────────────────────────────────────────────────┐
│  Production Agent (FastAPI on :8001)                        │
│  ┌───────────────┐  ┌───────────────┐  ┌─────────────────┐ │
│  │ Agent Card    │  │ Message Router│  │ Direct Skills   │ │
│  │ Discovery     │  │ (Keywords)    │  │ (Browser Access)│ │
│  └───────────────┘  └───────────────┘  └─────────────────┘ │
│         ↓                  ↓                    ↓           │
│  ┌──────────────────────────────────────────────────────┐  │
│  │          Skill Execution Layer                        │  │
│  │  • get_equipment_status • get_oee_summary             │  │
│  │  • get_downtime_summary                               │  │
│  └──────────────────────────────────────────────────────┘  │
│         ↓                                 ↓                 │
│  ┌─────────────┐                  ┌─────────────────┐      │
│  │ MQTT Client │                  │ MySQL Pool      │      │
│  │ (UNS Cache) │                  │ (Historical)    │      │
│  └─────────────┘                  └─────────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### Day 2 Achievements

✅ Production Agent A2A server (FastAPI on port 8001)  
✅ A2A protocol compliance with Agent Card discovery  
✅ Message-based interaction with intelligent routing  
✅ Three production-ready skills exposing Press 103 data  
✅ Browser-accessible direct skill endpoints  
✅ Task storage and retrieval system  
✅ Production architecture with proper error handling

### Comparison: MCP vs A2A

| Feature | Day 1 MES MCP Server | Day 2 Production Agent |
|---------|---------------------|------------------------|
| Protocol | MCP (stdio) | A2A (HTTP) |
| Client | Claude Desktop only | Any HTTP client (browser, curl, Claude) |
| Discovery | Tool list | Agent Card (/.well-known/agent.json) |
| Interaction | Tool calls | Message routing or direct skill access |
| Response | TextContent | Task with JSON artifacts |
| Port | N/A (stdio) | 8001 (HTTP) |
| Use Case | Desktop AI assistant | Web-accessible agent services |

**Prerequisites:** Completion of Day 1 (understanding of MES data and Press 103)

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

**Day 1 Status:** ✅ Complete - All MCP servers published and tested  
**Day 2 Status:** ✅ Complete - Production Agent A2A server published and tested

Students can clone the repository to access:
- Complete Day 1 implementation (MQTT, MySQL, MES servers)
- Step-by-step guides and documentation
- Requirements files and configuration templates
- Database schema documentation

---

## Day 1 Summary & Lessons Learned

### Technical Achievements

**Architecture:**
- Successfully implemented multi-server MCP architecture
- Demonstrated separation of concerns (MQTT, MySQL, domain-specific)
- Proved domain-specific servers reduce token usage and improve accuracy

**Implementation:**
- 3 fully functional MCP servers with 12 total tools
- File-based MQTT caching for instant responses
- Connection pooling for database efficiency
- Thread-safe operations throughout
- Comprehensive error handling and logging

**Security:**
- Read-only query validation
- Dangerous keyword blocking
- Schema allowlist enforcement
- Query auditing and logging
- Unique client IDs preventing collisions

### Key Insights

1. **Domain-Specific Beats Generic**
   - MES server with 5 tools outperforms generic MQTT + MySQL with 8 tools
   - Tools map to business objectives, not data structures
   - Reduces token usage and improves response accuracy

2. **Multi-Server Architecture Works**
   - Claude seamlessly routes requests to appropriate servers
   - Cross-server queries combine real-time and historical data
   - Independent scaling and maintenance per server

3. **Caching is Critical**
   - File-based MQTT cache enables instant topic lookups
   - Persists across reconnections for stability
   - Thread-safe operations prevent race conditions

4. **Write Capabilities Enable Feedback**
   - Agents can log observations back to the UNS
   - Creates audit trail of AI decisions
   - Enables agent-to-agent communication (Day 2 preview)

### Production Readiness Checklist

For deploying these servers in production:

- [ ] Add authentication/authorization to MCP servers
- [ ] Implement topic allowlists for MQTT writes
- [ ] Add rate limiting on database queries
- [ ] Set up monitoring and alerting
- [ ] Implement proper secrets management
- [ ] Add comprehensive error recovery
- [ ] Create deployment automation
- [ ] Document operational procedures
- [ ] Set up log aggregation
- [ ] Implement health checks

### Future Enhancements

Potential extensions beyond the workshop:
- Additional specialized agents (Quality, Maintenance, Scheduling)
- Agent-to-agent communication and coordination
- Workflow orchestration across multiple agents
- Real-time notifications and streaming updates
- Authentication and authorization for production deployment
- Integration with Claude API for autonomous operation

---

## Day 2 Summary & Lessons Learned

### Technical Achievements

**Architecture:**
- Successfully implemented A2A protocol in FastAPI
- Demonstrated MCP-to-A2A transformation pattern
- Browser-accessible manufacturing data APIs
- Dual access pattern: message-based + direct skills

**Implementation:**
- FastAPI server with 7 endpoints (3 A2A + 3 skills + 1 health)
- Intelligent keyword-based message routing
- Task storage system with UUID-based retrieval
- Reused Day 1 MQTT and MySQL patterns
- Production-ready error handling throughout

**Protocol Compliance:**
- Agent Card discovery at `/.well-known/agent.json`
- Message request/response with Pydantic models
- Task-based response pattern with artifacts
- CORS enabled for cross-origin access

### Key Insights

1. **A2A Enables Broader Access**
   - HTTP-based protocol accessible from any client
   - Browser testing without special tools
   - Suitable for web integrations and dashboards
   - Claude Desktop can still consume via HTTP

2. **Message Routing is Powerful**
   - Natural language queries route to appropriate skills
   - Keyword patterns enable intelligent dispatch
   - Reduces need for explicit tool selection
   - More user-friendly than direct tool calls

3. **Dual Access Pattern Works Well**
   - Message routing for natural language interaction
   - Direct skill endpoints for programmatic access
   - Browser-friendly JSON responses
   - Query parameters for customization

4. **MCP → A2A Transformation is Straightforward**
   - Skills map directly to MCP tools
   - Data layer (MQTT/MySQL) remains unchanged
   - Main changes: protocol wrapper and routing logic
   - Code reuse from Day 1 saves time

### Production Deployment Considerations

For deploying the Production Agent in production:

- [ ] Add API authentication (API keys, OAuth, etc.)
- [ ] Implement rate limiting per client
- [ ] Add request/response logging and auditing
- [ ] Set up monitoring and health checks
- [ ] Deploy with proper process manager (systemd, PM2)
- [ ] Configure reverse proxy (nginx) with SSL
- [ ] Implement caching strategy for frequent queries
- [ ] Add graceful shutdown handling
- [ ] Document API with OpenAPI/Swagger
- [ ] Create deployment automation (Docker, K8s)

### Comparison with Day 1

| Aspect | Day 1 (MCP) | Day 2 (A2A) |
|--------|-------------|-------------|
| **Transport** | stdio | HTTP |
| **Discovery** | Tool list | Agent Card |
| **Client** | Claude Desktop | Any HTTP client |
| **Response** | TextContent | JSON with artifacts |
| **Testing** | Claude only | Browser, curl, Postman |
| **Deployment** | Desktop only | Web servers, cloud |
| **Use Case** | AI assistant integration | Web APIs, dashboards |

---

## Resources

### MCP & AI
- [MCP Documentation](https://modelcontextprotocol.io)
- [Anthropic MCP GitHub](https://github.com/anthropics/anthropic-cookbook/tree/main/misc/model_context_protocol)
- [Claude API Documentation](https://docs.anthropic.com)

### Industrial Protocols
- [Paho MQTT Python](https://eclipse.dev/paho/files/paho.mqtt.python/html/)
- [HiveMQ MQTT Essentials](https://www.hivemq.com/mqtt-essentials/)
- [ISA-95 Standard](https://www.isa.org/isa95)

### Development Tools
- [Python MySQL Connector](https://dev.mysql.com/doc/connector-python/en/)
- [React Documentation](https://react.dev)
- [Tailwind CSS](https://tailwindcss.com)

---

## Support & Community

**Workshop Repository:** https://github.com/iiot-university/MCP_A2A_Workshop  
**IIoT University:** [Contact Information]

For questions, issues, or contributions, please open an issue on GitHub.

---

## License

MIT License - See LICENSE file for details.

---

## Acknowledgments

Built for the IIoT University Advanced MCP and Agent2Agent Workshop, December 2025.

Special thanks to:
- The Virtual Factory team for providing the industrial data infrastructure
- Anthropic for the MCP protocol and Claude API
- All workshop participants and contributors

**Workshop Complete!** ✅ Both Day 1 (MCP) and Day 2 (A2A) finished and tested.

# MCP & A2A Workshop

**Advanced MCP and Agent-to-Agent Workshop**  
IIoT University — December 16-17, 2025

---

## Workshop Overview

A hands-on 2-day workshop for engineers, integrators, and digital transformation professionals in industrial automation. Learn to build multi-server MCP architectures and implement the Agent2Agent protocol for collaborative AI systems.

| Day | Date | Topic | Status |
|-----|------|-------|--------|
| 1 | Dec 16, 2025 | Advanced MCP — Multi-Server Architectures | ✅ Complete |
| 2 | Dec 17, 2025 | Agent2Agent — Collaborative Intelligence | ✅ Complete |
| 3 | Jan 2026 | Containerization & Production Deployment | 📅 Scheduled |

---

## Quick Start

### Prerequisites

| Requirement | Version | Purpose |
|-------------|---------|---------|
| Python | 3.11+ | MCP servers and A2A agents |
| Claude Desktop | Latest | MCP client interface |
| Docker Desktop | Latest | N8N and container orchestration (Day 2) |
| Git | Any | Clone repository |

### 1. Clone & Configure

```bash
# Clone the repository
git clone https://github.com/iiot-university/MCP_A2A_Workshop.git
cd MCP_A2A_Workshop

# Copy environment template
cp .env.example .env

# Edit .env with your Virtual Factory credentials
# Required variables:
#   MQTT_BROKER, MQTT_PORT, MQTT_USERNAME, MQTT_PASSWORD
#   MYSQL_HOST, MYSQL_PORT, MYSQL_USERNAME, MYSQL_PASSWORD
```

### 2. Day 1 Setup — MCP Servers

```bash
# Setup each MCP server (creates venv, installs dependencies)
cd day1/mqtt_server && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt && deactivate && cd ../..
cd day1/mysql_server && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt && deactivate && cd ../..
cd day1/mes_server && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt && deactivate && cd ../..
```

Then configure Claude Desktop (`claude_desktop_config.json`) — see Day 1 section below.

### 3. Day 2 Setup — Docker & HTTP Servers

```bash
# Install Docker and N8N (see day2/setup/README.md for full guide)
docker run -d --name n8n --restart=always -p 5678:5678 -v n8n_data:/home/node/.n8n n8nio/n8n

# Make startup scripts executable (one time)
chmod +x start_servers.sh stop_servers.sh

# Start all Day 2 HTTP servers
./start_servers.sh
```

### 4. Verify Everything Works

```bash
# Check Day 2 HTTP servers
curl http://localhost:8001/health          # Production Agent
curl http://localhost:8002/health          # MES HTTP Server

# Check N8N
open http://localhost:5678

# Check MCP servers (in Claude Desktop)
# Ask: "What topics are available in the UNS?"
# Ask: "What is the current OEE for Press 103?"
```

### 5. Stop Everything

```bash
# Stop HTTP servers
./stop_servers.sh

# Stop N8N (optional)
docker stop n8n
```

---

## Port Assignments

| Server | Port | Protocol | Purpose |
|--------|------|----------|---------|
| Production Agent | 8001 | HTTP/A2A | A2A protocol endpoints |
| MES HTTP Server | 8002 | HTTP | N8N workflow integration |
| N8N | 5678 | HTTP | Workflow orchestration (Docker) |
| Portainer | 9443 | HTTPS | Docker management UI |

---

## Project Structure

```
MCP_A2A_Workshop/
├── .env                    # Credentials (gitignored)
├── .env.example            # Template for credentials
├── start_servers.sh        # Start all HTTP servers
├── stop_servers.sh         # Stop all servers
├── README.md               # This file
│
├── day1/                   # Day 1: Advanced MCP
│   ├── mqtt_server/        # Session 2: MQTT/UNS access
│   ├── mysql_server/       # Session 3: MySQL access
│   ├── mes_server/         # Session 4: Domain MES server
│   └── use_cases/          # Session 4: Use case documentation
│
├── day2/                   # Day 2: Agent2Agent
│   ├── setup/              # Docker/N8N setup guide
│   ├── production_agent/   # Session 2: A2A Production Agent
│   └── n8n_integration/    # Session 3: N8N workflows
│
└── logs/                   # Server logs (auto-created)
```

---

## Day 1: Advanced MCP — Multi-Server Architectures

Build Python MCP servers that give Claude Desktop access to industrial data.

### Sessions

| Session | Time | Topic |
|---------|------|-------|
| 1 | 9:00-9:45 | Introduction & Workshop Overview |
| 2 | 10:00-10:45 | Building Your First MCP Server — MQTT & UNS |
| 3 | 11:00-11:45 | Multi-Server Architecture — Adding MySQL |
| 4 | 12:00-12:45 | Practical Industrial Use Cases |

### What You'll Build

1. **MQTT MCP Server** — Read/write to Unified Namespace
2. **MySQL MCP Server** — Query relational MES data
3. **MES Domain Server** — Manufacturing-focused tools for Press 103

### Claude Desktop Configuration

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mqtt-uns": {
      "command": "/path/to/day1/mqtt_server/venv/bin/python",
      "args": ["/path/to/day1/mqtt_server/src/mqtt_mcp_server.py"]
    },
    "mysql-mes": {
      "command": "/path/to/day1/mysql_server/venv/bin/python",
      "args": ["/path/to/day1/mysql_server/src/mysql_mcp_server.py"]
    },
    "mes-press103": {
      "command": "/path/to/day1/mes_server/venv/bin/python",
      "args": ["/path/to/day1/mes_server/src/mes_mcp_server.py"]
    }
  }
}
```

---

## Day 2: Agent2Agent — Collaborative Intelligence

Expose MCP capabilities via HTTP and orchestrate with N8N workflows.

### Sessions

| Session | Time | Topic |
|---------|------|-------|
| 1 | 9:00-9:45 | Introduction to A2A Protocol |
| 2 | 10:00-10:45 | Building A2A Agents |
| 3 | 11:00-11:45 | Multi-Agent Workflows with N8N |
| 4 | 12:00-12:45 | Debugging & Future Directions |

### What You'll Build

1. **Production Agent** — A2A server exposing Press 103 data (port 8001)
2. **MES HTTP Server** — REST endpoints for N8N integration (port 8002)
3. **N8N Workflows** — Orchestrated multi-step agent workflows

### N8N Workflows Included

| Workflow | Description |
|----------|-------------|
| `n8n_shift_status_workflow.json` | Basic: Gather data → Build message → Post observation |
| `n8n_ai_analysis_workflow.json` | AI: Send to Claude API for analysis |
| `n8n_decision_logic_workflow.json` | Branching: Switch on availability threshold |

---

## Virtual Factory Data Sources

All examples use the ProveIt! Conference virtual factory environments.

### MQTT Broker (UNS)

| Setting | Value |
|---------|-------|
| Broker | balancer.virtualfactory.online |
| Port | 1883 |
| Topic Pattern | Enterprise/Dallas/Press/Press 103/# |

### MySQL Database

| Setting | Value |
|---------|-------|
| Host | proveit.virtualfactory.online |
| Port | 3306 |
| Schemas | mes_lite, mes_custom, proveitdb |

### Press 103 Context

| Metric | Value |
|--------|-------|
| LineID | 1 |
| Work Order | 12237611 |
| UNS Base | Enterprise/Dallas/Press/Press 103 |

---

## Action Items

### Video Content
- [ ] **A2A Agent Integration Video** — Document what was pulled from Day 2 Session 2-3 for standalone tutorial

### Day 3: Containerization & Production (January 2026)
- [ ] Schedule session for first week of January
- [ ] Containerize MCP servers with Docker
- [ ] Containerize A2A agents
- [ ] Deploy to production infrastructure
- [ ] CI/CD pipeline setup

---

## Resources

- **GitHub:** [github.com/iiot-university/MCP_A2A_Workshop](https://github.com/iiot-university/MCP_A2A_Workshop)
- **MCP Documentation:** [modelcontextprotocol.io](https://modelcontextprotocol.io)
- **A2A Protocol:** [google.github.io/A2A](https://google.github.io/A2A)
- **N8N Documentation:** [docs.n8n.io](https://docs.n8n.io)

---

## License

MIT License — See LICENSE file for details.

---

## Instructor

**Walker Reynolds**  
IIoT University  
[iiot.university](https://iiot.university)

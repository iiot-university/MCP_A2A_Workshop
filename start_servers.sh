#!/bin/bash
# =============================================================================
# MCP A2A Workshop - Startup Script
# =============================================================================
# Starts all HTTP servers for the workshop demonstration.
# 
# Servers started:
#   - Production Agent (A2A)     → http://localhost:8001
#   - MES HTTP Server (N8N)      → http://localhost:8002
#
# Note: MCP servers (mqtt, mysql, mes) are started automatically by Claude
#       Desktop based on claude_desktop_config.json
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo "============================================================"
echo "  MCP A2A Workshop - Server Startup"
echo "============================================================"
echo ""

# Create logs directory
mkdir -p "$LOG_DIR"

# Function to check if a port is in use
check_port() {
    local port=$1
    if lsof -i :$port > /dev/null 2>&1; then
        return 0  # Port is in use
    else
        return 1  # Port is free
    fi
}

# Function to kill process on a port
kill_port() {
    local port=$1
    local pid=$(lsof -ti :$port 2>/dev/null)
    if [ -n "$pid" ]; then
        echo -e "${YELLOW}  Killing existing process on port $port (PID: $pid)${NC}"
        kill -9 $pid 2>/dev/null || true
        sleep 1
    fi
}

# Function to setup virtual environment and install requirements
setup_venv() {
    local dir=$1
    local name=$2
    
    cd "$dir"
    
    # Check if requirements.txt exists
    if [ ! -f "requirements.txt" ]; then
        echo -e "${RED}  ✗ No requirements.txt found in $dir${NC}"
        return 1
    fi
    
    # Create venv if it doesn't exist
    if [ ! -d "venv" ]; then
        echo -e "${YELLOW}  Creating virtual environment for $name...${NC}"
        python3 -m venv venv
        if [ $? -ne 0 ]; then
            echo -e "${RED}  ✗ Failed to create virtual environment${NC}"
            return 1
        fi
    fi
    
    # Activate venv
    source venv/bin/activate
    
    # Check if requirements need to be installed/updated
    # Compare requirements.txt modification time with a marker file
    local marker_file="venv/.requirements_installed"
    local needs_install=false
    
    if [ ! -f "$marker_file" ]; then
        needs_install=true
    elif [ "requirements.txt" -nt "$marker_file" ]; then
        needs_install=true
        echo -e "${YELLOW}  Requirements.txt changed, updating dependencies...${NC}"
    fi
    
    if [ "$needs_install" = true ]; then
        echo -e "${YELLOW}  Installing dependencies for $name...${NC}"
        pip install --upgrade pip > /dev/null 2>&1
        pip install -r requirements.txt > /dev/null 2>&1
        if [ $? -eq 0 ]; then
            touch "$marker_file"
            echo -e "${GREEN}  ✓ Dependencies installed${NC}"
        else
            echo -e "${RED}  ✗ Failed to install dependencies${NC}"
            deactivate
            return 1
        fi
    else
        echo -e "${GREEN}  ✓ Dependencies already installed${NC}"
    fi
    
    return 0
}

# Function to start a server
start_server() {
    local name=$1
    local port=$2
    local dir=$3
    local script=$4
    local log_file="$LOG_DIR/${name// /_}.log"
    
    echo ""
    echo -e "${BLUE}[$name]${NC}"
    echo "------------------------------------------------------------"
    
    # Check and kill if port is in use
    if check_port $port; then
        kill_port $port
    fi
    
    # Setup venv and install requirements
    setup_venv "$dir" "$name"
    if [ $? -ne 0 ]; then
        echo -e "${RED}  ✗ Failed to setup environment for $name${NC}"
        cd "$SCRIPT_DIR"
        return 1
    fi
    
    # Start the server in background (venv should still be active from setup_venv)
    echo -e "${YELLOW}  Starting server on port $port...${NC}"
    nohup python "$script" > "$log_file" 2>&1 &
    local pid=$!
    
    # Wait a moment and check if it's running
    sleep 2
    if ps -p $pid > /dev/null 2>&1; then
        echo -e "${GREEN}  ✓ Server started (PID: $pid)${NC}"
        echo -e "${GREEN}  → URL: http://localhost:$port${NC}"
        echo -e "${GREEN}  → Log: $log_file${NC}"
    else
        echo -e "${RED}  ✗ Server failed to start${NC}"
        echo -e "${RED}  → Check log: $log_file${NC}"
        tail -5 "$log_file" 2>/dev/null
    fi
    
    deactivate 2>/dev/null || true
    cd "$SCRIPT_DIR"
}

# =============================================================================
# Check Python is available
# =============================================================================
echo -e "${BLUE}Checking prerequisites...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python 3 is not installed or not in PATH${NC}"
    exit 1
fi
PYTHON_VERSION=$(python3 --version 2>&1)
echo -e "${GREEN}✓ $PYTHON_VERSION${NC}"

# Check .env file exists
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    echo -e "${RED}✗ .env file not found in project root${NC}"
    echo -e "${YELLOW}  Copy .env.example to .env and configure credentials${NC}"
    exit 1
fi
echo -e "${GREEN}✓ .env file found${NC}"

# =============================================================================
# Start Day 2 HTTP Servers
# =============================================================================

echo ""
echo "============================================================"
echo "  Starting Day 2 HTTP Servers"
echo "============================================================"

# Production Agent (A2A Protocol) - Port 8001
start_server "Production Agent" 8001 \
    "$SCRIPT_DIR/day2/production_agent" \
    "src/production_agent.py"

# MES HTTP Server (N8N Integration) - Port 8002
start_server "MES HTTP Server" 8002 \
    "$SCRIPT_DIR/day2/n8n_integration" \
    "mes_http_server.py"

echo ""
echo "============================================================"
echo "  Server Summary"
echo "============================================================"
echo ""
echo -e "  ${GREEN}Production Agent (A2A)${NC}    → http://localhost:8001"
echo -e "    Agent Card:              http://localhost:8001/.well-known/agent.json"
echo -e "    Health:                  http://localhost:8001/health"
echo ""
echo -e "  ${GREEN}MES HTTP Server (N8N)${NC}     → http://localhost:8002"
echo -e "    Health:                  http://localhost:8002/health"
echo -e "    Equipment Status:        http://localhost:8002/equipment/status"
echo -e "    OEE Summary:             http://localhost:8002/oee/summary"
echo ""
echo -e "  ${BLUE}N8N Workflow Engine${NC}       → http://localhost:5678"
echo -e "    (Start separately with: docker start n8n)"
echo ""
echo -e "  ${YELLOW}Logs:${NC} $LOG_DIR/"
echo ""
echo "============================================================"
echo ""
echo -e "To stop all servers: ${YELLOW}./stop_servers.sh${NC}"
echo ""

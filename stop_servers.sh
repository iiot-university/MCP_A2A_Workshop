#!/bin/bash
# =============================================================================
# MCP A2A Workshop - Stop Servers Script
# =============================================================================
# Stops all HTTP servers started by start_servers.sh
# =============================================================================

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo ""
echo "============================================================"
echo "  MCP A2A Workshop - Stopping Servers"
echo "============================================================"
echo ""

# Function to stop server on a port
stop_port() {
    local port=$1
    local name=$2
    local pid=$(lsof -ti :$port 2>/dev/null)
    
    if [ -n "$pid" ]; then
        echo -e "${YELLOW}Stopping $name on port $port (PID: $pid)...${NC}"
        kill -9 $pid 2>/dev/null || true
        echo -e "${GREEN}  ✓ Stopped${NC}"
    else
        echo -e "${GREEN}  ✓ $name not running on port $port${NC}"
    fi
}

# Stop Day 2 HTTP servers
stop_port 8001 "Production Agent"
stop_port 8002 "MES HTTP Server"

echo ""
echo -e "${GREEN}All servers stopped.${NC}"
echo ""

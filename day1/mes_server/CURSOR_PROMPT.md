# Cursor Prompt: Build MES MCP Server for Press 103

## Task

Build `day1/mes_server/src/mes_mcp_server.py` — a domain-specific MCP server for AI agents to execute MES objectives on Press 103.

## Reference Files

1. **Specification:** `day1/mes_server/README.md` — contains complete tool specs, data mappings, queries, and architecture
2. **Template:** `day1/mqtt_server/src/mqtt_mcp_server.py` — use this as your code pattern for MQTT caching, MCP server structure, and logging

## What to Build

A single Python file (`mes_mcp_server.py`) that:

1. **Connects to MQTT broker** and subscribes ONLY to `Enterprise/Dallas/Press/Press 103/#`
2. **Connects to MySQL** (mes_lite database) using connection pooling
3. **Caches MQTT messages** to `mes_cache.json` using the same file-based pattern as the MQTT server
4. **Exposes 5 MCP tools** that combine UNS real-time data with MySQL historical data:

| Tool | Purpose | Primary Source |
|------|---------|----------------|
| `get_equipment_status` | Is it running? Current state? Speed? | UNS |
| `get_active_work_order` | What are we making? Progress? | UNS + MySQL |
| `get_oee_summary` | A/P/Q breakdown, performance | UNS |
| `get_downtime_summary` | Why down? Top reasons? | MySQL + UNS |
| `log_observation` | Record agent note (write pattern) | UNS write |

## Critical Implementation Details

### Environment Loading
```python
env_path = Path(__file__).parent.parent.parent.parent / ".env"
```

### Constants
```python
PRESS_103_LINE_ID = 1
PRESS_103_UNS_BASE = "Enterprise/Dallas/Press/Press 103"
MQTT_SUBSCRIBE_TOPIC = f"{PRESS_103_UNS_BASE}/#"
```

### MQTT Pattern
- Copy the `MQTTClientWrapper` class from mqtt_mcp_server.py
- Modify subscription to use `MQTT_SUBSCRIBE_TOPIC` instead of `#`
- Keep the file-based cache pattern with thread-safe atomic writes

### MySQL Pattern
```python
import mysql.connector
from mysql.connector import pooling

db_pool = pooling.MySQLConnectionPool(
    pool_name="mes_pool",
    pool_size=3,
    host=MYSQL_HOST,
    port=int(MYSQL_PORT),
    user=MYSQL_USERNAME,
    password=MYSQL_PASSWORD,
    database="mes_lite"
)
```

### MCP Server Pattern
```python
server = Server("mes-press103")

@server.list_tools()
async def list_tools() -> list[Tool]:
    # Return all 5 tools
    
@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    # Route to handlers
```

### Key UNS Topics to Read
```python
# Equipment status
f"{PRESS_103_UNS_BASE}/Dashboard/Running"
f"{PRESS_103_UNS_BASE}/Line/State"
f"{PRESS_103_UNS_BASE}/MQTT/Dashboard Machine Speed"
f"{PRESS_103_UNS_BASE}/Line/Rate Setpoint"
f"{PRESS_103_UNS_BASE}/Dashboard/Shift Name"

# OEE
f"{PRESS_103_UNS_BASE}/Line/OEE/OEE"
f"{PRESS_103_UNS_BASE}/Line/OEE/OEE Availability"
f"{PRESS_103_UNS_BASE}/Line/OEE/OEE Performance"
f"{PRESS_103_UNS_BASE}/Line/OEE/OEE Quality"
f"{PRESS_103_UNS_BASE}/Line/OEE/Good Count"
f"{PRESS_103_UNS_BASE}/Line/OEE/Bad Count"
f"{PRESS_103_UNS_BASE}/Line/OEE/Target Count"
f"{PRESS_103_UNS_BASE}/Line/OEE/WorkOrder"
f"{PRESS_103_UNS_BASE}/Line/OEE/RunID"
f"{PRESS_103_UNS_BASE}/Line/OEE/Runtime"
f"{PRESS_103_UNS_BASE}/Line/OEE/Unplanned Downtime"
```

### Key MySQL Queries

**Active work order:**
```sql
SELECT w.WorkOrder, w.ProductCode, w.Quantity, s.Quantity as ScheduledQty
FROM mes_lite.workorder w
JOIN mes_lite.schedule s ON s.WorkOrderID = w.ID
WHERE w.WorkOrder = %s AND s.LineID = 1
ORDER BY s.ScheduleStartDateTime DESC LIMIT 1
```

**Downtime pareto:**
```sql
SELECT sh.ReasonName, 
       COUNT(*) as Events,
       SUM(TIMESTAMPDIFF(MINUTE, sh.StartDateTime, COALESCE(sh.EndDateTime, NOW()))) as Minutes
FROM mes_lite.statehistory sh
WHERE sh.LineID = 1 AND sh.StartDateTime >= DATE_SUB(NOW(), INTERVAL %s HOUR)
GROUP BY sh.ReasonName
ORDER BY Minutes DESC
LIMIT 10
```

### Log Observation Write Topic
```python
f"{PRESS_103_UNS_BASE}/Agent/Observations"
```

Payload format:
```json
{
  "timestamp": "ISO8601",
  "source": "mes-agent", 
  "category": "optional category",
  "message": "the observation"
}
```

## Output Requirements

1. Single file: `day1/mes_server/src/mes_mcp_server.py`
2. Well-commented for teaching purposes
3. Robust error handling (return useful messages, don't crash)
4. All logging to stderr
5. Follow the exact patterns from mqtt_mcp_server.py for MCP structure

## Do NOT

- Create multiple files
- Add dependencies beyond requirements.txt
- Use abstract/placeholder data — use the real topics and queries
- Change the established patterns from mqtt_mcp_server.py

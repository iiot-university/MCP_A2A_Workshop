# Day 1 Use Cases — Practical Industrial Applications

**Day 1, Session 4** — Demonstrating MCP in Manufacturing Context

**Status:** ✅ Complete

---

## Overview

This section documents the practical use cases demonstrated in Day 1, Session 4. After building three MCP servers (MQTT, MySQL, MES), we show how they work together to answer real manufacturing questions.

---

## Use Case 1: Equipment Status Check

**Question:** "What is Press 103 doing right now?"

**Tools Used:** `mes-press103.get_equipment_status`

**Response includes:**
- Running state (true/false)
- State code
- Current speed vs setpoint
- Speed percentage
- Current shift

---

## Use Case 2: Production Progress

**Question:** "How close are we to finishing this work order?"

**Tools Used:** `mes-press103.get_active_work_order`

**Response includes:**
- Work order number
- Product code
- Good count vs target
- Percent complete
- Units remaining

---

## Use Case 3: Performance Analysis

**Question:** "How is Press 103 performing?"

**Tools Used:** `mes-press103.get_oee_summary`

**Response includes:**
- Overall OEE percentage
- Availability breakdown
- Performance breakdown
- Quality breakdown
- Good/bad counts
- Runtime vs downtime
- Performance rating (World Class, Typical, Below Average, Needs Improvement)

---

## Use Case 4: Downtime Investigation

**Question:** "Why has Press 103 been down?"

**Tools Used:** `mes-press103.get_downtime_summary`

**Response includes:**
- Current state
- Is running flag
- Total downtime minutes
- Planned vs unplanned breakdown
- Top 5 downtime reasons (Pareto)
- Minutes and event count per reason

---

## Use Case 5: Cross-Server Queries

**Question:** "Show me the OEE trend and the top downtime reasons"

**Tools Used:** 
- `mqtt-uns.get_topic_value` (real-time OEE)
- `mysql-mes.execute_query` (historical downtime)

This demonstrates Claude's ability to orchestrate multiple MCP servers to answer complex questions.

---

## Use Case 6: Agent Observations

**Question:** "Log that we're investigating the speed variance issue"

**Tools Used:** `mes-press103.log_observation`

**Result:** Message published to UNS topic `Enterprise/Dallas/Press/Press 103/Agent/Observations`

This demonstrates **write operations** — the agent can record its findings back to the UNS for other systems to consume.

---

## Key Takeaways

1. **Domain servers > Generic servers** — Tools that match operator questions reduce friction
2. **Single-asset pattern** — Scoped agents are easier to reason about and maintain
3. **Multi-server orchestration** — Claude automatically selects the right tool for each question
4. **Bidirectional communication** — Agents can read AND write to the UNS
5. **Natural language interface** — No SQL or MQTT knowledge required for operators

# MySQL Schema Documentation

## Overview

This directory contains schema reference documentation for the three MySQL databases available through the MES MCP Server. These documents are designed to help AI agents quickly understand the data structures and construct effective queries.

## Available Schemas

| Schema | Purpose | Size | Documentation |
|--------|---------|------|---------------|
| **mes_lite** | Core MES production data | 24 tables | [MES_LITE.md](MES_LITE.md) |
| **mes_custom** | Extended MES features | 113 tables | [MES_CUSTOM.md](MES_CUSTOM.md) |
| **proveitdb** | Demo/training data | 2 tables | [PROVEITDB.md](PROVEITDB.md) |

## Quick Reference

### mes_lite — Core Production Tracking
- **line** — Equipment definitions (LineID is the key)
- **schedule** — Production orders linked to lines
- **run** — Actual production runs with OEE metrics
- **statehistory** — Equipment state/downtime events
- **workorder** — Work order master data
- **counthistory** — High-frequency production counts

### mes_custom — Extended Features
- **approval_*** — Operator/supervisor approval workflows
- **jobjacket*** — Job jacket tracking and status
- **roll_*** — Material consumption/production tracking
- **schedule_*** — Enhanced scheduling with job details
- **shift_***, **mes_users** — Workforce management
- ***_log** — Audit and change tracking

### proveitdb — Demo Data
- **tag_history** — Historical Ignition tag snapshots
- **DashboardDemo** — Sample dashboard visualization data

## Common Join Patterns

```sql
-- Get production context from mes_lite
SELECT l.Name, w.WorkOrder, r.OEE, r.GoodCount
FROM mes_lite.run r
JOIN mes_lite.schedule s ON r.ScheduleID = s.ID
JOIN mes_lite.line l ON s.LineID = l.ID
JOIN mes_lite.workorder w ON s.WorkOrderID = w.ID;

-- Add custom data (approvals, roll tracking)
SELECT r.ID as RunID, ar.Operator, ar.ApprovalTime,
       SUM(rac.roll_footage_consumed) as TotalFootage
FROM mes_lite.run r
LEFT JOIN mes_custom.approval_runtime ar ON r.ID = ar.RunID
LEFT JOIN mes_custom.roll_auto_consume_log rac ON r.ID = rac.Run_ID
GROUP BY r.ID;

-- Query historical tag data
SELECT tag_path, value, timestamp
FROM proveitdb.tag_history
WHERE sequence_id = 1 AND tag_path LIKE '%OEE%';
```

## Key Line IDs (Press Equipment)

| LineID | Name | Status |
|--------|------|--------|
| 1 | Press 103 | Active |
| 4 | Press 104 | Active |
| 14 | Press 105 | Active |
| 2 | Press 101 | Disabled |
| 3 | Press 102 | Disabled |

## Agent Usage Tips

1. **Start with mes_lite** for core production queries
2. **Join to mes_custom** for approvals, materials, scheduling details
3. **Use proveitdb** for historical analysis and demos
4. **Always filter large tables** (counthistory, roll_message_log, tag_history)
5. **OEE values are 0-1** in mes_lite — multiply by 100 for percentages
6. **Check Active/Closed flags** to distinguish current vs. historical

# mes_lite Schema Reference

## Overview

The `mes_lite` schema is the **core MES (Manufacturing Execution System)** database for the Enterprise/Dallas virtual factory. It contains the fundamental production tracking tables: lines, schedules, runs, work orders, state history, and count data.

**Key Characteristics:**
- Production-focused transactional data
- Real-time state tracking
- OEE (Overall Equipment Effectiveness) calculations
- ISA-95 aligned hierarchy: Enterprise → Site → Area → Line

---

## Entity Relationship Summary

```
area (7 rows)
  └── line (26 rows)
        └── schedule (3,450 rows)
              └── run (26,445 rows)
                    ├── statehistory (119,590 rows)
                    └── counthistory (12.4M rows)

workorder (8,154 rows) ←→ schedule (linked via WorkOrderID)
statereason (607 rows) ←→ statehistory (linked via StateReasonID)
```

---

## Core Tables

### line
**Purpose:** Production line/equipment definitions  
**Row Count:** ~26 rows

| Column | Type | Description |
|--------|------|-------------|
| ID | int | Primary key (use this as LineID in joins) |
| Name | varchar(45) | Line name (e.g., "Press 103", "Elba 1") |
| Disable | tinyint(1) | 0=Active, 1=Disabled |
| ParentID | int | FK to area.ID |

**Common Queries:**
```sql
-- Get all active lines
SELECT ID, Name FROM mes_lite.line WHERE Disable = 0;

-- Get lines by area
SELECT l.ID, l.Name, a.Name as AreaName 
FROM mes_lite.line l
JOIN mes_lite.area a ON l.ParentID = a.ID;
```

**Key Lines:**
| LineID | Name | Status |
|--------|------|--------|
| 1 | Press 103 | Active |
| 4 | Press 104 | Active |
| 14 | Press 105 | Active |
| 2 | Press 101 | Disabled |
| 3 | Press 102 | Disabled |

---

### schedule
**Purpose:** Scheduled production orders linked to lines and work orders  
**Row Count:** ~3,450 rows

| Column | Type | Description |
|--------|------|-------------|
| ID | int | Primary key (ScheduleID) |
| LineID | int | FK to line.ID |
| WorkOrderID | int | FK to workorder.ID |
| Quantity | int | Scheduled quantity |
| ScheduleStartDateTime | datetime | Planned start |
| ScheduleFinishDateTime | datetime | Planned finish |
| RunID | int | FK to run.ID (once started) |
| Status | int | 0=Not Ready, 1=Ready, 2=Released |
| ScheduleRate | float | Target production rate |
| SetupMins | int | Planned setup time |

**Common Queries:**
```sql
-- Get current schedules for a line
SELECT s.ID, w.WorkOrder, s.Quantity, s.ScheduleStartDateTime, s.Status
FROM mes_lite.schedule s
JOIN mes_lite.workorder w ON s.WorkOrderID = w.ID
WHERE s.LineID = 1 AND s.Status IN (1, 2)
ORDER BY s.ScheduleStartDateTime;

-- Get schedules with run data
SELECT s.ID, w.WorkOrder, r.ID as RunID, r.GoodCount, r.OEE
FROM mes_lite.schedule s
JOIN mes_lite.workorder w ON s.WorkOrderID = w.ID
LEFT JOIN mes_lite.run r ON s.RunID = r.ID
WHERE s.LineID = 1;
```

---

### run
**Purpose:** Actual production run records with OEE metrics  
**Row Count:** ~26,445 rows

| Column | Type | Description |
|--------|------|-------------|
| ID | int | Primary key (RunID) |
| ScheduleID | int | FK to schedule.ID |
| RunStartDateTime | datetime | Actual start time |
| RunStopDateTime | datetime | Actual stop time |
| GoodCount | int | Good units produced |
| WasteCount | int | Waste/reject count |
| TotalCount | int | Total units produced |
| Availability | float | OEE Availability (0-1) |
| Performance | float | OEE Performance (0-1) |
| Quality | float | OEE Quality (0-1) |
| OEE | float | Overall OEE (0-1) |
| Runtime | int | Actual runtime (seconds) |
| UnplannedDowntime | int | Unplanned downtime (seconds) |
| PlannedDowntime | int | Planned downtime (seconds) |
| TotalTime | int | Total elapsed time (seconds) |
| Closed | tinyint(1) | Run complete flag |
| EndReason | int | FK to end reason code |

**Common Queries:**
```sql
-- Get recent runs for a line with OEE
SELECT r.ID, r.RunStartDateTime, r.GoodCount, 
       r.Availability * 100 as Avail_Pct,
       r.Performance * 100 as Perf_Pct,
       r.Quality * 100 as Qual_Pct,
       r.OEE * 100 as OEE_Pct
FROM mes_lite.run r
JOIN mes_lite.schedule s ON r.ScheduleID = s.ID
WHERE s.LineID = 1
ORDER BY r.RunStartDateTime DESC
LIMIT 20;

-- Get run with work order details
SELECT r.ID as RunID, w.WorkOrder, w.ProductCode,
       r.GoodCount, r.TotalTime, r.OEE
FROM mes_lite.run r
JOIN mes_lite.schedule s ON r.ScheduleID = s.ID
JOIN mes_lite.workorder w ON s.WorkOrderID = w.ID
WHERE r.ID = 59711;
```

---

### statehistory
**Purpose:** Equipment state transitions with downtime reasons  
**Row Count:** ~119,590 rows

| Column | Type | Description |
|--------|------|-------------|
| ID | int | Primary key |
| LineID | int | FK to line.ID |
| RunID | int | FK to run.ID |
| StateReasonID | int | FK to statereason.ID |
| ReasonCode | int | State code (see below) |
| ReasonName | varchar(255) | Human-readable reason |
| StartDateTime | datetime | State start time |
| EndDateTime | datetime | State end time (NULL if current) |
| Active | int | 1 if current state |
| Note | varchar(255) | Operator notes |

**State Codes (ReasonCode):**
| Code | Meaning |
|------|---------|
| 0 | Unassigned/Unknown |
| 1-10 | Running states |
| 11-20 | Downtime states |
| 21+ | Custom states |

**Common Queries:**
```sql
-- Get current state for all lines
SELECT l.Name, sh.ReasonName, sh.StartDateTime
FROM mes_lite.statehistory sh
JOIN mes_lite.line l ON sh.LineID = l.ID
WHERE sh.Active = 1;

-- Get downtime events for a run
SELECT sh.ReasonName, sh.StartDateTime, sh.EndDateTime,
       TIMESTAMPDIFF(MINUTE, sh.StartDateTime, sh.EndDateTime) as Duration_Min
FROM mes_lite.statehistory sh
WHERE sh.RunID = 59711 AND sh.ReasonCode > 10
ORDER BY sh.StartDateTime;

-- Downtime summary by reason for a line
SELECT sh.ReasonName, COUNT(*) as Occurrences,
       SUM(TIMESTAMPDIFF(MINUTE, sh.StartDateTime, IFNULL(sh.EndDateTime, NOW()))) as Total_Min
FROM mes_lite.statehistory sh
WHERE sh.LineID = 1 AND sh.ReasonCode > 10
GROUP BY sh.ReasonName
ORDER BY Total_Min DESC;
```

---

### statereason
**Purpose:** Master list of state/downtime reason codes  
**Row Count:** ~607 rows

| Column | Type | Description |
|--------|------|-------------|
| ID | int | Primary key |
| ReasonName | varchar(255) | Reason description |
| ReasonCode | int | Numeric code |
| ParentID | int | Parent reason (hierarchical) |
| RecordDowntime | tinyint(1) | Counts as downtime |
| PlannedDowntime | tinyint(1) | Planned vs unplanned |
| OperatorSelectable | tinyint(1) | Visible to operators |
| SubReasonOf | int | Parent category |

**Common Queries:**
```sql
-- Get all downtime reasons
SELECT ID, ReasonName, ReasonCode, PlannedDowntime
FROM mes_lite.statereason
WHERE RecordDowntime = 1
ORDER BY ReasonCode;

-- Get reason hierarchy
SELECT p.ReasonName as Category, c.ReasonName as SubReason
FROM mes_lite.statereason c
JOIN mes_lite.statereason p ON c.SubReasonOf = p.ID
WHERE c.OperatorSelectable = 1;
```

---

### workorder
**Purpose:** Work order master data  
**Row Count:** ~8,154 rows

| Column | Type | Description |
|--------|------|-------------|
| ID | int | Primary key |
| WorkOrder | varchar(255) | Work order number (unique) |
| Quantity | int | Ordered quantity |
| ProductCode | varchar(255) | Product/SKU identifier |
| ProductCodeID | int | FK to productcode.ID |
| Closed | tinyint(1) | Order complete |
| Hide | tinyint(1) | Hidden from UI |

**Common Queries:**
```sql
-- Get open work orders
SELECT ID, WorkOrder, ProductCode, Quantity
FROM mes_lite.workorder
WHERE Closed = 0 AND Hide = 0
ORDER BY WorkOrder;

-- Get work order with production progress
SELECT w.WorkOrder, w.Quantity as Ordered,
       SUM(r.GoodCount) as Produced,
       w.Quantity - SUM(r.GoodCount) as Remaining
FROM mes_lite.workorder w
JOIN mes_lite.schedule s ON w.ID = s.WorkOrderID
JOIN mes_lite.run r ON s.RunID = r.ID
WHERE w.WorkOrder = '12370711'
GROUP BY w.ID;
```

---

### counthistory
**Purpose:** High-frequency production count data  
**Row Count:** ~12.4 million rows

| Column | Type | Description |
|--------|------|-------------|
| ID | int | Primary key |
| RunID | int | FK to run.ID |
| TagID | int | FK to counttag.ID |
| CountTypeID | int | FK to counttype.ID |
| Count | int | Counter value |
| TimeStamp | datetime | Sample timestamp |

**Count Types (counttype table):**
| ID | Type |
|----|------|
| 1 | Infeed |
| 2 | Outfeed |
| 3 | Waste |

**Common Queries:**
```sql
-- Get count trend for a run
SELECT TimeStamp, Count, CountTypeID
FROM mes_lite.counthistory
WHERE RunID = 59711 AND CountTypeID = 2
ORDER BY TimeStamp;

-- Get production rate (counts per minute)
SELECT 
  DATE_FORMAT(TimeStamp, '%Y-%m-%d %H:%i') as Minute,
  MAX(Count) - MIN(Count) as Units_Produced
FROM mes_lite.counthistory
WHERE RunID = 59711 AND CountTypeID = 2
GROUP BY DATE_FORMAT(TimeStamp, '%Y-%m-%d %H:%i')
ORDER BY Minute;
```

---

## Common Join Patterns

### Full Production Context
```sql
-- Get complete run context
SELECT 
  l.Name as LineName,
  w.WorkOrder,
  w.ProductCode,
  r.RunStartDateTime,
  r.GoodCount,
  r.OEE * 100 as OEE_Pct
FROM mes_lite.run r
JOIN mes_lite.schedule s ON r.ScheduleID = s.ID
JOIN mes_lite.line l ON s.LineID = l.ID
JOIN mes_lite.workorder w ON s.WorkOrderID = w.ID
WHERE l.Name = 'Press 103'
ORDER BY r.RunStartDateTime DESC
LIMIT 10;
```

### OEE Dashboard Query
```sql
-- Current OEE by line
SELECT 
  l.Name,
  r.OEE * 100 as OEE,
  r.Availability * 100 as Availability,
  r.Performance * 100 as Performance,
  r.Quality * 100 as Quality,
  r.GoodCount,
  r.RunStartDateTime
FROM mes_lite.line l
JOIN mes_lite.schedule s ON l.ID = s.LineID
JOIN mes_lite.run r ON s.RunID = r.ID
WHERE l.Disable = 0 AND r.Closed = 0
ORDER BY l.Name;
```

---

## Notes for Agents

1. **Always use LineID** from `mes_lite.line` when filtering by equipment
2. **Join through schedule** to connect runs to work orders
3. **Check Closed/Active flags** to distinguish current vs historical data
4. **OEE values are 0-1**, multiply by 100 for percentages
5. **Time values in seconds** for Runtime, Downtime fields
6. **counthistory is large** (12M+ rows) — always filter by RunID

# proveitdb Schema Reference

## Overview

The `proveitdb` schema is a **demonstration database** created for the ProveIt! Conference. It contains historical snapshots of tag data from the Enterprise/Dallas virtual factory, useful for demos, training, and testing without impacting production data.

**Key Characteristics:**
- Point-in-time snapshots of Ignition tag values
- Dashboard demo data for visualization
- 1505 tags captured per sequence (snapshot)
- Data from Nov 2024 – Jan 2025

**Primary Use Cases:**
- Demonstrating historical tag queries
- Training on MES data patterns
- Building dashboards without live connections
- Comparing historical vs. real-time data

---

## Tables

### tag_history
**Purpose:** Historical snapshots of Ignition tag values  
**Row Count:** ~651,813 rows

| Column | Type | Description |
|--------|------|-------------|
| id | int | Primary key |
| tag_path | varchar(255) | Full Ignition tag path |
| value | mediumtext | Tag value (string, number, JSON, etc.) |
| timestamp | datetime | When captured |
| sequence_id | int | Snapshot sequence number |

**Data Structure:**
- Each `sequence_id` represents one point-in-time snapshot
- Each sequence contains **1505 tags**
- Sequences captured approximately every 10 seconds
- Total of ~433 sequences available

**Tag Path Format:**
```
[OVER_MES01_mes_lite]OF/Dallas/{Area}/{Asset}/Line/{TagGroup}/{TagName}
```

**Assets Captured:**
| Asset | Area | Type |
|-------|------|------|
| Elba 1 | Bag | Bag Making |
| Lam 124 | Lam | Lamination |
| Press 103 | Press | Printing |
| Press 104 | Press | Printing |
| Press 105 | Press | Printing |
| SRC 139 | Slit | Slitting |

---

## Common Tag Categories

### OEE Tags (per asset, ~47 tags)
```
.../Line/OEE/OEE
.../Line/OEE/OEE Availability
.../Line/OEE/OEE Performance
.../Line/OEE/OEE Quality
.../Line/OEE/Good Count
.../Line/OEE/Bad Count
.../Line/OEE/Total Count
.../Line/OEE/Runtime
.../Line/OEE/Unplanned Downtime
.../Line/OEE/Planned Downtime
.../Line/OEE/Total Time
.../Line/OEE/Production Rate
.../Line/OEE/Standard Rate
.../Line/OEE/WorkOrder
.../Line/OEE/RunID
.../Line/OEE/Start Time
.../Line/OEE/End Time
```

### Dispatch Tags
```
.../Line/Dispatch/OEE Infeed/Count
.../Line/Dispatch/OEE Infeed/Enable
.../Line/Dispatch/OEE Outfeed/Count
.../Line/Dispatch/OEE Outfeed/Enable
.../Line/Dispatch/OEE Waste/Count
.../Line/Dispatch/OEE Waste/Enable
.../Line/Dispatch/Line State
.../Line/Dispatch/StateReason
.../Line/Dispatch/RunID
```

### Production Tags
```
.../Line/Infeed
.../Line/Outfeed
.../Line/Waste
.../Line/State
.../Line/RunTime
```

---

## Common Queries

### Get All Tags for One Sequence
```sql
-- Get all 1505 tags from sequence 1
SELECT tag_path, value, timestamp
FROM proveitdb.tag_history
WHERE sequence_id = 1
ORDER BY tag_path;
```

### Get OEE Tags for Specific Asset
```sql
-- Get OEE data for Press 104 at sequence 1
SELECT 
  SUBSTRING_INDEX(tag_path, '/', -1) as tag_name,
  value,
  timestamp
FROM proveitdb.tag_history
WHERE sequence_id = 1 
  AND tag_path LIKE '%Press 104%'
  AND tag_path LIKE '%OEE%'
ORDER BY tag_path;
```

### Get Specific Tag Across Time
```sql
-- Get OEE Availability for Press 104 across sequences
SELECT 
  sequence_id,
  value as OEE_Availability,
  timestamp
FROM proveitdb.tag_history
WHERE tag_path LIKE '%Press 104%Line/OEE/OEE Availability'
ORDER BY sequence_id
LIMIT 50;
```

### Get All Assets
```sql
-- List distinct assets in the data
SELECT DISTINCT 
  SUBSTRING_INDEX(SUBSTRING_INDEX(tag_path, '/', 4), '/', -1) as asset
FROM proveitdb.tag_history
WHERE sequence_id = 1
ORDER BY asset;
```

### Get Tag Categories for an Asset
```sql
-- Get distinct tag groups for Press 104
SELECT DISTINCT 
  SUBSTRING_INDEX(SUBSTRING_INDEX(tag_path, 'Press 104/', -1), '/', 1) as category
FROM proveitdb.tag_history
WHERE sequence_id = 1 AND tag_path LIKE '%Press 104%'
ORDER BY category;
```

### Compare Values Across Sequences
```sql
-- Compare OEE across first 10 sequences for all assets
SELECT 
  sequence_id,
  SUBSTRING_INDEX(SUBSTRING_INDEX(tag_path, '/', 4), '/', -1) as asset,
  value as OEE,
  timestamp
FROM proveitdb.tag_history
WHERE tag_path LIKE '%Line/OEE/OEE'
  AND tag_path NOT LIKE '%OEE Availability%'
  AND tag_path NOT LIKE '%OEE Performance%'
  AND tag_path NOT LIKE '%OEE Quality%'
  AND tag_path NOT LIKE '%OEE OLD%'
  AND sequence_id <= 10
ORDER BY sequence_id, asset;
```

### Get Sequence Time Range
```sql
-- Get time range for each sequence
SELECT 
  sequence_id,
  MIN(timestamp) as earliest,
  MAX(timestamp) as latest,
  COUNT(*) as tag_count
FROM proveitdb.tag_history
GROUP BY sequence_id
ORDER BY sequence_id
LIMIT 20;
```

---

### DashboardDemo
**Purpose:** Sample data for dashboard visualizations  
**Row Count:** ~240 rows

| Column | Type | Description |
|--------|------|-------------|
| JobJacket | int | Job jacket number |
| DeckTempSP | float | Deck temperature setpoint |
| DecksTemp | float | Actual deck temperature |
| TunnelTempSP | float | Tunnel temperature setpoint |
| TunnelTemp | float | Actual tunnel temperature |
| Speed | float | Line speed |
| OutfeedTensionSP | float | Outfeed tension setpoint |
| OutfeedTension | float | Actual outfeed tension |
| InfeedTensionSP | float | Infeed tension setpoint |
| InfeedTension | float | Actual infeed tension |
| LF | int | Linear feet |
| ReelLF | int | Reel linear feet |
| ReelImpressions | int | Reel impressions |
| Timestamp | datetime | Data timestamp |

**Common Queries:**
```sql
-- Get dashboard data for a job
SELECT *
FROM proveitdb.DashboardDemo
WHERE JobJacket = 122966
ORDER BY Timestamp;

-- Get temperature trends
SELECT Timestamp, DeckTempSP, DecksTemp, TunnelTempSP, TunnelTemp
FROM proveitdb.DashboardDemo
WHERE JobJacket = 122966
ORDER BY Timestamp;

-- Get production metrics
SELECT Timestamp, Speed, LF, ReelLF, ReelImpressions
FROM proveitdb.DashboardDemo
ORDER BY Timestamp DESC
LIMIT 50;
```

---

## Linking to mes_lite

The `tag_history` data can be correlated with `mes_lite` data using common identifiers:

### By Work Order
```sql
-- Find historical tag data for a specific work order
SELECT th.tag_path, th.value, th.timestamp
FROM proveitdb.tag_history th
WHERE th.sequence_id = 1 
  AND th.tag_path LIKE '%OEE/WorkOrder'
  AND th.value = '12370711';
```

### By RunID
```sql
-- Get tag history and mes_lite run data
SELECT 
  th.tag_path,
  th.value as TagValue,
  r.GoodCount,
  r.OEE * 100 as MES_OEE
FROM proveitdb.tag_history th
JOIN mes_lite.run r ON th.value = CAST(r.ID AS CHAR)
WHERE th.tag_path LIKE '%OEE/RunID'
  AND th.sequence_id = 1;
```

### Cross-Reference Tag OEE with MES OEE
```sql
-- Compare tag history OEE with mes_lite calculated OEE
SELECT 
  'Tag History' as Source,
  th.value as OEE_Value,
  th.timestamp
FROM proveitdb.tag_history th
WHERE th.tag_path LIKE '%Press 104%Line/OEE/OEE Availability'
  AND th.sequence_id = 1

UNION ALL

SELECT 
  'MES Run' as Source,
  CAST(r.Availability * 100 AS CHAR) as OEE_Value,
  r.RunStartDateTime as timestamp
FROM mes_lite.run r
JOIN mes_lite.schedule s ON r.ScheduleID = s.ID
WHERE s.LineID = 4  -- Press 104
ORDER BY timestamp DESC
LIMIT 5;
```

---

## Notes for Agents

1. **sequence_id is your time dimension** — each sequence is a snapshot
2. **1505 tags per sequence** — always filter to specific assets or tag types
3. **Tag paths are long strings** — use LIKE with wildcards for matching
4. **Values are stored as text** — cast to numeric types when needed
5. **Use SUBSTRING_INDEX** to parse tag path components
6. **Data range:** Nov 2024 – Jan 2025
7. **Link to mes_lite** via WorkOrder or RunID values in the tags
8. **DashboardDemo** is small and simple — good for quick visualizations

---

## Tag Path Parsing Examples

```sql
-- Extract asset name from tag path
SUBSTRING_INDEX(SUBSTRING_INDEX(tag_path, '/', 4), '/', -1) as asset

-- Extract tag name (last component)
SUBSTRING_INDEX(tag_path, '/', -1) as tag_name

-- Extract category (e.g., "OEE", "Dispatch")
SUBSTRING_INDEX(SUBSTRING_INDEX(tag_path, '/', -2), '/', 1) as category

-- Remove provider prefix
REPLACE(tag_path, '[OVER_MES01_mes_lite]', '') as clean_path
```

# mes_custom Schema Reference

## Overview

The `mes_custom` schema contains **extended MES functionality** built on top of `mes_lite`. It provides advanced features including approval workflows, job jacket tracking, roll/material management, scheduling enhancements, shift management, and audit logging.

**Key Characteristics:**
- Extensions to core MES functionality
- Approval and quality control workflows
- Material/roll tracking for converting operations
- Advanced scheduling with job jacket integration
- User/shift management and audit trails

**Relationship to mes_lite:** Most tables join to `mes_lite` via `RunID`, `LineID`, or `ScheduleID`.

---

## Feature Categories

| Category | Key Tables | Purpose |
|----------|------------|---------|
| Approvals | `approval_*` | Operator/supervisor approval workflows |
| Job Jackets | `jobjacket*` | Job tracking and status management |
| Roll Management | `roll_*` | Material consumption/production tracking |
| Scheduling | `schedule_*` | Enhanced scheduling with details |
| Shift/User | `shift_*`, `mes_users` | Workforce management |
| Audit | `*_log` tables | Change tracking and history |

---

## Approval System Tables

### approval_config
**Purpose:** Configuration for approval workflows per line/operation  
**Row Count:** ~353 rows

| Column | Type | Description |
|--------|------|-------------|
| ID | int | Primary key |
| LineID | int | FK to mes_lite.line.ID |
| OperationID | int | Operation type |
| RequireApproval | tinyint | Approval required flag |
| RequireSupervisor | tinyint | Supervisor approval required |

### approval_runtime
**Purpose:** Runtime approval records for production runs  
**Row Count:** ~3,493 rows

| Column | Type | Description |
|--------|------|-------------|
| ApprovalID | int | Primary key |
| RunID | int | FK to mes_lite.run.ID |
| ProductionID | int | Production record ID |
| WorkOrder | varchar(75) | Work order reference |
| Operator | varchar(45) | Operator who approved |
| ApprovalTime | datetime | When approved |
| Supervisor | varchar(45) | Supervisor who approved |
| SupervisorApprovalTime | datetime | Supervisor approval time |
| LifetimeCounter | bigint | Counter value at approval |

**Common Queries:**
```sql
-- Get approvals for a run
SELECT ar.ApprovalTime, ar.Operator, ar.Supervisor, ar.SupervisorApprovalTime
FROM mes_custom.approval_runtime ar
WHERE ar.RunID = 59711
ORDER BY ar.ApprovalTime;

-- Get pending supervisor approvals
SELECT ar.*, w.WorkOrder
FROM mes_custom.approval_runtime ar
JOIN mes_lite.run r ON ar.RunID = r.ID
JOIN mes_lite.schedule s ON r.ScheduleID = s.ID
JOIN mes_lite.workorder w ON s.WorkOrderID = w.ID
WHERE ar.Supervisor IS NULL AND ar.ApprovalTime IS NOT NULL;
```

### approval_runtime_checklist
**Purpose:** Checklist items completed during approvals  
**Row Count:** ~70,264 rows

| Column | Type | Description |
|--------|------|-------------|
| ID | int | Primary key |
| ApprovalID | int | FK to approval_runtime |
| ChecklistItemID | int | Item definition |
| Checked | tinyint | Item completed |
| CheckedBy | varchar(45) | Who checked |
| CheckedTime | datetime | When checked |

---

## Job Jacket Tables

### jobjacketstatus
**Purpose:** Job jacket state tracking over time  
**Row Count:** ~16,410 rows

| Column | Type | Description |
|--------|------|-------------|
| ID | int | Primary key |
| JobJacket | varchar(20) | Job jacket number |
| JobStatus | int | Current status code |
| DateTime | datetime | Status timestamp |
| Sequence | int | Sequence number |

**Status Codes:**
| Code | Meaning |
|------|---------|
| 1 | Created |
| 2 | In Queue |
| 3 | In Progress |
| 4 | Complete |
| 5 | On Hold |

### jobjacketstatuscurrent
**Purpose:** Current status snapshot (denormalized for performance)  
**Row Count:** ~27,375 rows

| Column | Type | Description |
|--------|------|-------------|
| JobJacket | varchar(20) | Job jacket number |
| JobStatus | int | Current status |
| LastUpdate | datetime | Last status change |

**Common Queries:**
```sql
-- Get current status for a job jacket
SELECT JobJacket, JobStatus, LastUpdate
FROM mes_custom.jobjacketstatuscurrent
WHERE JobJacket = '122966';

-- Get job jacket history
SELECT JobJacket, JobStatus, DateTime
FROM mes_custom.jobjacketstatus
WHERE JobJacket = '122966'
ORDER BY DateTime;

-- Count jobs by status
SELECT JobStatus, COUNT(*) as Count
FROM mes_custom.jobjacketstatuscurrent
GROUP BY JobStatus;
```

### jobjacketevents
**Purpose:** Events/milestones for job jackets  
**Row Count:** ~5,814 rows

---

## Roll Management Tables

### roll_auto_consume_log
**Purpose:** Automatic roll consumption tracking (unwinders)  
**Row Count:** ~66,766 rows

| Column | Type | Description |
|--------|------|-------------|
| id | int | Primary key |
| line_id | int | FK to mes_lite.line.ID |
| Run_ID | int | FK to mes_lite.run.ID |
| roll_id | varchar(500) | Roll identifier |
| unwind_no | int | Unwinder position (1, 2) |
| roll_start_time | datetime | When roll started |
| roll_end_time | datetime | When roll finished |
| roll_start_footage | bigint | Starting footage |
| roll_end_footage | bigint | Ending footage |
| roll_footage_consumed | int | Total consumed |
| roll_active | tinyint | Currently active |
| Username | varchar(75) | Operator |
| Roll_Returned | int | Returned to inventory |
| Override_Footage | int | Manual override value |

**Common Queries:**
```sql
-- Get roll consumption for a run
SELECT roll_id, unwind_no, roll_footage_consumed, 
       roll_start_time, roll_end_time, Username
FROM mes_custom.roll_auto_consume_log
WHERE Run_ID = 59711
ORDER BY roll_start_time;

-- Get total consumption by line
SELECT l.Name, SUM(r.roll_footage_consumed) as TotalFootage
FROM mes_custom.roll_auto_consume_log r
JOIN mes_lite.line l ON r.line_id = l.ID
WHERE r.roll_start_time >= DATE_SUB(NOW(), INTERVAL 7 DAY)
GROUP BY l.Name;

-- Find active rolls
SELECT line_id, roll_id, unwind_no, roll_start_time
FROM mes_custom.roll_auto_consume_log
WHERE roll_active = 1;
```

### roll_auto_produce_log
**Purpose:** Automatic roll production tracking (rewinders)  
**Row Count:** ~57,995 rows

| Column | Type | Description |
|--------|------|-------------|
| id | int | Primary key |
| line_id | int | FK to mes_lite.line.ID |
| Run_ID | int | FK to mes_lite.run.ID |
| roll_id | varchar(500) | Produced roll identifier |
| rewind_no | int | Rewinder position |
| roll_footage_produced | int | Footage on roll |
| roll_start_time | datetime | Production start |
| roll_end_time | datetime | Production end |

### roll_message_log
**Purpose:** Roll transaction message queue/history  
**Row Count:** ~2.4 million rows

**Note:** Large table — always filter by date range or line_id.

---

## Scheduling Tables

### schedule_release
**Purpose:** Schedule version releases  
**Row Count:** ~15,334 rows

| Column | Type | Description |
|--------|------|-------------|
| ID | int | Primary key |
| Version | int | Version number |
| StartDate | datetime | Schedule period start |
| Released | tinyint | Published to floor |
| Active | tinyint | Currently active |
| CreatedBy | varchar(200) | Creator |
| CreatedAt | datetime | Creation time |
| EditedBy | varchar(200) | Last editor |
| EditedAt | datetime | Last edit time |

### schedule_release_detail
**Purpose:** Detailed schedule line items  
**Row Count:** ~818,139 rows

### schedule_detail_print
**Purpose:** Print-specific job specifications  
**Row Count:** ~2,834 rows

| Column | Type | Description |
|--------|------|-------------|
| ID | int | Primary key |
| JobNum | varchar(100) | Job number |
| ReferenceItemNo | varchar(100) | SKU reference |
| Customer | varchar(250) | Customer name |
| Colors | int | Number of colors |
| SleeveSize | varchar(100) | Sleeve size |
| FilmWidth | float | Film width |
| FilmLFAvailable | float | Available footage |
| Active | bit(1) | Currently active |

**Common Queries:**
```sql
-- Get print specs for a job
SELECT JobNum, Customer, Colors, SleeveSize, FilmWidth
FROM mes_custom.schedule_detail_print
WHERE JobNum = '122966' AND Active = 1;

-- Get jobs by customer
SELECT JobNum, ReferenceItemNo, Colors, FilmWidth
FROM mes_custom.schedule_detail_print
WHERE Customer LIKE '%Acme%' AND Active = 1;
```

### schedule_detail_lam
**Purpose:** Lamination job specifications  
**Row Count:** ~2,137 rows

### schedule_detail_slit
**Purpose:** Slitting job specifications  
**Row Count:** ~1,983 rows

### schedule_exception
**Purpose:** Schedule exceptions and overrides  
**Row Count:** ~6,127 rows

---

## Shift & User Management

### shift_info
**Purpose:** Shift definitions  
**Row Count:** ~48 rows

| Column | Type | Description |
|--------|------|-------------|
| ID | int | Primary key |
| ShiftName | varchar(45) | Shift name |
| StartTime | time | Shift start |
| EndTime | time | Shift end |
| LineID | int | Line-specific shift |

### shift_user
**Purpose:** User-to-shift assignments  
**Row Count:** ~34,515 rows

| Column | Type | Description |
|--------|------|-------------|
| ID | int | Primary key |
| RunID | int | FK to mes_lite.run.ID |
| LineID | int | FK to mes_lite.line.ID |
| Username | varchar(75) | User assigned |
| CreateDate | datetime | Assignment created |
| LogInTime | datetime | Actual login time |

**Common Queries:**
```sql
-- Get users on shift for a line
SELECT su.Username, su.LogInTime, l.Name
FROM mes_custom.shift_user su
JOIN mes_lite.line l ON su.LineID = l.ID
WHERE su.LineID = 1 AND DATE(su.CreateDate) = CURDATE();

-- Get shift history for a run
SELECT Username, LogInTime
FROM mes_custom.shift_user
WHERE RunID = 59711
ORDER BY LogInTime;
```

### mes_users
**Purpose:** MES user accounts  
**Row Count:** ~320 rows

### run_username
**Purpose:** User-run associations  
**Row Count:** ~44,074 rows

---

## Standards & Configuration

### standard_run_rate
**Purpose:** Standard production rates by line/operation  
**Row Count:** ~70 rows

| Column | Type | Description |
|--------|------|-------------|
| ID | int | Primary key |
| LineID | int | FK to mes_lite.line.ID |
| OperationID | int | Operation type |
| ColumnName | varchar(50) | Rate basis column |
| Value | varchar(50) | Column value |
| RunRate | double | Standard rate |

### standard_setup_time
**Purpose:** Standard setup times  
**Row Count:** ~161 rows

### statereason_downtimereason
**Purpose:** Maps state reasons to downtime categories  
**Row Count:** ~514 rows

| Column | Type | Description |
|--------|------|-------------|
| ID | int | Primary key |
| StateReasonID | int | FK to mes_lite.statereason.ID |
| DowntimeReasonID | int | Downtime category |

---

## Audit & Logging Tables

### production_edit_log
**Purpose:** Production data edit history  
**Row Count:** ~128,319 rows

| Column | Type | Description |
|--------|------|-------------|
| ID | int | Primary key |
| WorkOrderID | int | Affected work order |
| RunID | int | Affected run |
| ProductionID | int | Production record |
| Username | varchar(75) | Who made change |
| TableAffected | varchar(50) | Table modified |
| ColumnChanged | varchar(50) | Column modified |
| Message | varchar(255) | Change description |
| Timestamp | datetime | When changed |

**Common Queries:**
```sql
-- Get edit history for a run
SELECT Username, TableAffected, ColumnChanged, Message, Timestamp
FROM mes_custom.production_edit_log
WHERE RunID = 59711
ORDER BY Timestamp DESC;
```

### override_user_log
**Purpose:** Manual override audit trail  
**Row Count:** ~6,674 rows

### material_management_log
**Purpose:** Material movement history  
**Row Count:** ~343,046 rows

### inventory_waste_log
**Purpose:** Waste/scrap tracking  
**Row Count:** ~11,508 rows

---

## Common Join Patterns

### Get Full Run Context with Custom Data
```sql
SELECT 
  l.Name as LineName,
  w.WorkOrder,
  r.GoodCount,
  ar.Operator,
  ar.ApprovalTime,
  COUNT(DISTINCT rac.id) as RollsConsumed,
  SUM(rac.roll_footage_consumed) as TotalFootage
FROM mes_lite.run r
JOIN mes_lite.schedule s ON r.ScheduleID = s.ID
JOIN mes_lite.line l ON s.LineID = l.ID
JOIN mes_lite.workorder w ON s.WorkOrderID = w.ID
LEFT JOIN mes_custom.approval_runtime ar ON r.ID = ar.RunID
LEFT JOIN mes_custom.roll_auto_consume_log rac ON r.ID = rac.Run_ID
WHERE r.ID = 59711
GROUP BY r.ID;
```

### Shift Report Query
```sql
SELECT 
  l.Name as Line,
  su.Username,
  su.LogInTime,
  COUNT(DISTINCT r.ID) as RunsWorked,
  SUM(r.GoodCount) as TotalProduced
FROM mes_custom.shift_user su
JOIN mes_lite.line l ON su.LineID = l.ID
LEFT JOIN mes_lite.run r ON su.RunID = r.ID
WHERE DATE(su.CreateDate) = CURDATE()
GROUP BY l.Name, su.Username;
```

---

## Notes for Agents

1. **Join to mes_lite via RunID or LineID** — most custom tables reference core MES
2. **Roll tables use line_id (lowercase)** — different naming convention
3. **Check Active flags** — many tables have Active/Current variants
4. **Audit tables are large** — always filter by date or ID range
5. **Job jacket numbers are strings** — use varchar matching
6. **Schedule detail tables are operation-specific** — print, lam, slit
7. **Approval workflow is two-step** — operator then supervisor

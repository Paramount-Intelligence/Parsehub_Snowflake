# SQLite Reference Audit - ParseHub Snowflake Backend

**Audit Date:** March 25, 2026  
**Scope:** Complete backend codebase search for SQLite imports, connections, and database logic

---

## Summary

The backend codebase contains **legacy SQLite code** that is currently **obsolete or redundant** with the Snowflake migration. The system has been migrated to Snowflake, but several files still contain SQLite imports, connections, and data access code that should be either updated or removed.

**Key Findings:**
- **6 files** with direct `sqlite3` imports or usage
- **3 files** with missing `sqlite3` imports but referencing `sqlite3` classes
- **1 migration script** for SQLite to Snowflake
- **Multiple service files** using SQLite as default parameter
- **Physical SQLite database files** present in the codebase

---

## 1. Direct SQLite Imports

### 1.1 [backend/migrations/migrate_sqlite_to_snowflake.py](backend/migrations/migrate_sqlite_to_snowflake.py)

**Purpose:** Migration utility to transfer data from SQLite to Snowflake

**Import:**
- **Line 6:** `import sqlite3`

**SQLite-Specific Usage:**
- **Lines 47, 70:** SQLite connection setup
  ```python
  SQLITE_DB_PATH = Path(__file__).parent.parent / "parsehub.db"
  self.sqlite_conn = sqlite3.connect(SQLITE_DB_PATH)
  self.sqlite_conn.row_factory = sqlite3.Row
  ```

- **Lines 99-101:** SQLite schema inspection (sqlite_master)
  ```python
  cursor = self.sqlite_conn.cursor()
  cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
  return [table[0] for table in cursor.fetchall()]
  ```

- **Lines 105-107:** SQLite PRAGMA for table info
  ```python
  cursor = self.sqlite_conn.cursor()
  cursor.execute(f"PRAGMA table_info({table_name})")
  columns = cursor.fetchall()
  ```

- **Lines 190-204:** SQLite data extraction and iteration
  ```python
  sqlite_cursor = self.sqlite_conn.cursor()
  sqlite_cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
  row_count = sqlite_cursor.fetchone()[0]
  sqlite_cursor.execute(f"SELECT * FROM {table_name}")
  rows = sqlite_cursor.fetchall()
  ```

- **Lines 306-307:** SQLite connection cleanup
  ```python
  if self.sqlite_conn:
      self.sqlite_conn.close()
  ```

---

## 2. SQLite Database Files

### 2.1 [backend/src/models/parsehub.db](backend/src/models/parsehub.db)
- **Type:** SQLite database file
- **Size:** Exists (actual binary data)
- **Associated Files:**
  - `parsehub.db-shm` (SQLite write-ahead log shared memory file)
  - `parsehub.db-wal` (SQLite write-ahead log)

---

## 3. Services Using SQLite as Default Database

These services default to local SQLite files but are intended to work with Snowflake in production:

### 3.1 [backend/src/services/advanced_analytics.py](backend/src/services/advanced_analytics.py)

**Status:** ⚠️ **CRITICAL** - Missing sqlite3 import but uses `sqlite3.connect()` and `sqlite3.Row`

**Issue:** File uses sqlite3 without importing it - will cause `NameError` at runtime.

**Lines with sqlite3 usage:**
- **Line 15:** Default parameter uses local SQLite path
  ```python
  def __init__(self, db_path: str = "parsehub.db"):
      self.db_path = db_path
  ```

- **Lines 31-32:** SQLite connection without import
  ```python
  conn = sqlite3.connect(self.db_path)
  conn.row_factory = sqlite3.Row
  ```

- **Lines 36-39:** SQLite cursor operations
  ```python
  cursor.execute('''
      SELECT id, token, title FROM projects WHERE id = %s
  ''', (project_id,))
  project = cursor.fetchone()
  ```

- **Lines 46-49:** Column access using SQLite Row factory syntax
  ```python
  cursor.execute('''
      SELECT COUNT(*) as total FROM scraped_data WHERE project_id = %s
  ''', (project_id,))
  total_records = cursor.fetchone()['total'] or 0
  ```

- **Lines 52-59:** Additional cursor operations
  ```python
  cursor.execute('''
      SELECT...FROM runs WHERE project_id = %s
  ''', (project_id,))
  runs_info = cursor.fetchone()
  ```

- **Lines 65-70:** Pagination info extraction
  ```python
  cursor.execute('''
      SELECT MAX(CAST(json_extract(data, '$.page_number') AS INTEGER)) as last_page
      FROM scraped_data WHERE project_id = %s
  ''', (project_id,))
  page_result = cursor.fetchone()
  ```

- **Lines 113-114, 207-208, 232-233, 274-275:** Multiple instances of `sqlite3.connect()` and `sqlite3.Row` usage

- **Lines 211-216, 236-241, 278-283:** Additional cursor.execute() and fetchall() operations with JSON extraction

---

### 3.2 [backend/src/services/pagination_service.py](backend/src/services/pagination_service.py)

**Status:** ⚠️ **CRITICAL** - Missing sqlite3 import but uses `sqlite3.connect()` and `sqlite3.Row`

**Line 14:** Default parameter uses local SQLite path
```python
def __init__(self, db_path: str = "parsehub.db"):
    self.db_path = db_path
```

**Lines 89-90:** SQLite connection without import
```python
conn = sqlite3.connect(self.db_path)
conn.row_factory = sqlite3.Row
```

**Line 140:** Another `sqlite3.connect()` call without import

---

### 3.3 [backend/src/services/analytics_service.py](backend/src/services/analytics_service.py)

**Status:** ⚠️ **CRITICAL** - References `sqlite3.Row` without importing sqlite3

**Missing Import:** File imports `ParseHubDatabase` but NOT `sqlite3`

**Lines 65:** Conditional check for `sqlite3.Row`
```python
runs = [dict(row) if isinstance(row, sqlite3.Row) else dict(zip([d[0] for d in cursor.description], row)) for row in cursor.fetchall()]
```

**Line 79:** Another `sqlite3.Row` check
```python
recovery_ops = [dict(row) if isinstance(row, sqlite3.Row) else dict(zip([d[0] for d in cursor.description], row)) for row in cursor.fetchall()]
```

**Issue:** This code attempts to handle both SQLite rows (which are `sqlite3.Row` objects) and Snowflake rows (which are tuple-like). However, `sqlite3` is never imported, so this will raise `NameError`.

---

### 3.4 [backend/src/services/scraping_session_service.py](backend/src/services/scraping_session_service.py)

**Status:** ⚠️ **CRITICAL** - References `sqlite3.IntegrityError` without importing sqlite3

**Line 46:** Exception handling without import
```python
except sqlite3.IntegrityError:
    # Session already exists for this project_token and target
```

**Issue:** Uses `sqlite3.IntegrityError` exception class without importing sqlite3. Will cause `NameError` at runtime when a duplicate key violation occurs.

---

## 4. Database Configuration

### 4.1 [backend/src/config/.env.example](backend/src/config/.env.example)

**Line 21:** SQLite path configuration option (commented as local development)
```
# SQLite (for local development)
DATABASE_PATH=parsehub.db
```

**Line 24:** PostgreSQL URL for production
```
# PostgreSQL (for production)
DATABASE_URL=postgresql://user:password@host:5432/database
```

**Note:** Current system uses Snowflake (not PostgreSQL), so this configuration is outdated.

---

### 4.2 [backend/src/models/database.py](backend/src/models/database.py)

**Status:** ⚠️ Snowflake-only with legacy SQLite exception handling

**Lines 1-18:** No SQLite imports - Snowflake-only implementation

**Line 1554:** Legacy SQLite exception handling
```python
except sqlite3.IntegrityError:
    # Record already exists (duplicate), skip
    pass
```

**Issue:** References `sqlite3.IntegrityError` without importing sqlite3. This line will cause `NameError` if executed. However, since the primary database is now Snowflake, this code path may not actually be reached in production.

---

## 5. Migration-Related Documentation

### 5.1 [backend/migrations/MIGRATION_GUIDE.md](backend/migrations/MIGRATION_GUIDE.md)

**Purpose:** Guide for migrating from SQLite to Snowflake

**References:**
- **Line 5:** Describes migration from SQLite (`parsehub.db`) to Snowflake
- **Line 10:** Lists SQLite as source database
- **Lines 55-56:** Backup commands for `parsehub.db`
- **Line 80:** Example connection string for SQLite
- **Lines 240-241:** Commands to restore SQLite backup

---

### 5.2 [backend/migrations/MIGRATION_COMPLETE.md](backend/migrations/MIGRATION_COMPLETE.md)

**Purpose:** Documentation completed after migration

**References to SQLite:**
- **Line 31:** Backup command for `parsehub.db`
- **Lines 187-188:** Restore commands

---

## 6. API Server with Legacy Cursor Compatibility

### 6.1 [backend/src/api/api_server.py](backend/src/api/api_server.py)

**Status:** Snowflake-native but with mixed cursor handling

**Lines 221-225:** Dual-mode cursor result handling
```python
cursor.execute('SELECT COUNT(*) AS count FROM projects')
r1 = cursor.fetchone()
projects = r1['count'] if isinstance(r1, dict) else r1[0]

cursor.execute('SELECT COUNT(*) AS count FROM metadata')
r2 = cursor.fetchone()
metadata = r2['count'] if isinstance(r2, dict) else r2[0]
```

**Note:** Code is designed to work with both SQLite row objects (dict-like) and other database cursor results. However, this is now Snowflake-only.

---

## 7. Code Patterns Analysis

### SQLite-Specific Patterns Found

| Pattern | Count | Files | Status |
|---------|-------|-------|--------|
| `sqlite3.connect()` | 5 | advanced_analytics.py, pagination_service.py | ⚠️ Missing import |
| `sqlite3.Row` | 7+ | advanced_analytics.py, pagination_service.py, analytics_service.py | ⚠️ Missing import |
| `conn.row_factory = sqlite3.Row` | 5 | advanced_analytics.py, pagination_service.py | ⚠️ Missing import |
| `cursor.fetchone()` | 20+ | Multiple files | ✅ Generic pattern |
| `cursor.fetchall()` | 15+ | Multiple files | ✅ Generic pattern |
| `cursor.execute()` | 30+ | Multiple files | ✅ Generic pattern |
| `db_path = "parsehub.db"` | 3 | Default parameters | ✅ Local fallback |
| `sqlite_master` queries | 2 | migrate_sqlite_to_snowflake.py | ✅ Migration only |
| `PRAGMA table_info` | 1 | migrate_sqlite_to_snowflake.py | ✅ Migration only |
| `sqlite3.IntegrityError` | 3 | database.py, scraping_session_service.py | ⚠️ Missing import |

---

## 8. Conditional Database Logic

### Fallback/Dual-Database Patterns

**Pattern 1: Service with default SQLite but accepting db parameter**
```python
class AdvancedAnalyticsService:
    def __init__(self, db_path: str = "parsehub.db"):  # Default to SQLite
        self.db_path = db_path
```

Services with this pattern:
- [backend/src/services/advanced_analytics.py](backend/src/services/advanced_analytics.py#L15)
- [backend/src/services/pagination_service.py](backend/src/services/pagination_service.py#L14)

**Pattern 2: Snowflake-primary with exception handling**
- Services using `ParseHubDatabase()` for Snowflake
- Exception handling for legacy `sqlite3.IntegrityError`

---

## 9. Recommendations

### Priority 1: Critical Fixes (Runtime Errors)

1. **Add missing `sqlite3` import to `advanced_analytics.py`**
   - Currently uses `sqlite3.connect()` and `sqlite3.Row` without import
   - Will fail with `NameError` if instantiated

2. **Add missing `sqlite3` import to `pagination_service.py`**
   - Currently uses `sqlite3.connect()` and `sqlite3.Row` without import
   - Will fail with `NameError` if instantiated

3. **Add missing `sqlite3` import to `analytics_service.py`**
   - References `sqlite3.Row` in isinstance checks without import
   - Will fail with `NameError` when processing query results

4. **Add missing `sqlite3` import to `scraping_session_service.py`**
   - References `sqlite3.IntegrityError` exception without import
   - Will fail with `NameError` on duplicate key errors

5. **Add missing `sqlite3` import to `database.py` (line 1554)**
   - References `sqlite3.IntegrityError` without import
   - Will fail with `NameError` if reached

### Priority 2: Code Cleanup (Redundancy)

1. **Deprecate `AdvancedAnalyticsService`**
   - Uses local SQLite by default
   - Should use Snowflake via `ParseHubDatabase`
   - Remove default SQLite parameter or update to use Snowflake

2. **Deprecate `PaginationService`**
   - Uses local SQLite by default
   - Should integrate with `ParseHubDatabase`
   - Remove default SQLite parameter

3. **Update `AnalyticsService`**
   - Currently uses `ParseHubDatabase` for Snowflake
   - Remove legacy `sqlite3.Row` compatibility checks
   - Simplify result handling

4. **Update `ScrapingSessionService`**
   - Currently uses `ParseHubDatabase` for Snowflake
   - Replace `sqlite3.IntegrityError` with Snowflake error handling

### Priority 3: Infrastructure Cleanup

1. **Remove SQLite database files**
   - `backend/src/models/parsehub.db`
   - `backend/src/models/parsehub.db-shm`
   - `backend/src/models/parsehub.db-wal`

2. **Update `.env.example`**
   - Remove SQLite `DATABASE_PATH` option or mark as deprecated
   - Update PostgreSQL reference to Snowflake configuration

3. **Archive migration scripts**
   - `backend/migrations/migrate_sqlite_to_snowflake.py` is complete
   - Move to separate migration history folder
   - Update migration guides to reflect Snowflake-only status

---

## 10. Impact Analysis

### Files Using Local SQLite as Default
- **advanced_analytics.py** - If called without db_path parameter, will attempt SQLite
- **pagination_service.py** - If called without db_path parameter, will attempt SQLite

### Files with Missing Imports (Will Fail)
- **advanced_analytics.py** - ✅ Needs `import sqlite3`
- **pagination_service.py** - ✅ Needs `import sqlite3`
- **analytics_service.py** - ✅ Needs `import sqlite3`
- **scraping_session_service.py** - ✅ Needs `import sqlite3`
- **database.py** - ✅ Needs `import sqlite3` or exception handling update

### Snowflake-Native Files (No Issues)
- **api_server.py** - Uses `ParseHubDatabase` (Snowflake)
- **database.py** - Primary Snowflake implementation
- **db_pool.py** - SQLAlchemy pool for PostgreSQL/Snowflake

---

## 11. Actionable Audit Summary Table

| File | Issue | Severity | Type | Lines | Fix |
|------|-------|----------|------|-------|-----|
| advanced_analytics.py | Missing `import sqlite3` | 🔴 Critical | Import | 31,32,113,114,207,208,232,233,274,275 | Add import or refactor to Snowflake |
| pagination_service.py | Missing `import sqlite3` | 🔴 Critical | Import | 89,90,140 | Add import or refactor to Snowflake |
| analytics_service.py | Missing `import sqlite3` | 🔴 Critical | Reference | 65,79 | Add import or remove isinstance checks |
| scraping_session_service.py | Missing `import sqlite3` | 🔴 Critical | Exception | 46 | Add import or use Snowflake exceptions |
| database.py | Missing `import sqlite3` | 🔴 Critical | Exception | 1554 | Add import or remove legacy handling |
| parsehub.db | Obsolete SQLite file | 🟠 High | File | N/A | Delete after backup |
| migrate_sqlite_to_snowflake.py | Completed migration script | 🟡 Medium | Legacy Code | All | Archive/document completion |
| advanced_analytics.py | Default SQLite parameter | 🟡 Medium | Design | 15 | Update to use Snowflake |
| pagination_service.py | Default SQLite parameter | 🟡 Medium | Design | 14 | Update to use Snowflake |
| .env.example | Outdated configuration | 🟡 Medium | Config | 21,24 | Update to Snowflake only |

---

## Summary Statistics

- **Total files with SQLite references:** 11
- **Files with missing imports:** 5
- **Critical runtime issues:** 5
- **Obsolete files/artifacts:** 3
- **Database files to remove:** 3
- **SQLite-specific patterns found:** 50+
- **Migration status:** ✅ Complete (Snowflake active)


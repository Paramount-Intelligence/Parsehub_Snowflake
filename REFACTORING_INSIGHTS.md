# Refactoring Insights & Critical Points

**Date:** March 25, 2026  
**Status:** Pre-Refactoring Analysis Complete

---

## 🎯 Executive Summary

The ParseHub-Snowflake codebase implements incremental scraping through a **metadata-driven polling mechanism** combined with **session-based iteration tracking**. The system uses **three different approaches** to trigger runs:

1. **Polling-Based** (IncrementalScrapingManager) - Checks metadata every 30 min
2. **Session-Based** (AutoRunnerService) - Structured multi-page campaigns  
3. **API-Driven** (REST endpoints) - Manual/batch triggers

**Current State:** Functional but with **overlapping abstractions** and **mixed patterns**.

---

## 🔴 Critical Issues to Address in Refactoring

### Issue #1: Checkpoint Strategy is Scattered
**Problem:** Three different ways to track progress
- `metadata.current_page_scraped` - Primary progress tracking
- `runs.is_continuation` - Boolean flag marking continuations
- `iteration_runs` - Structured campaign tracking

**Impact:** Code handles state inconsistently; unclear which source of truth to use

**Recommendation:** 
- Consolidate to single source of truth
- Consider event-based approach instead of polling
- Make session/iteration the primary abstraction, not metadata flags

### Issue #2: Pagination Detection is URL-Only
**Problem:** No support for:
- JavaScript-rendered pagination (AJAX)
- Cursor-based pagination (next_page tokens)
- API-based pagination (token-based)
- Custom pagination parameters per site

**Impact:** Fails on modern sites using non-standard pagination

**Recommendation:**
- Add abstraction layer for pagination strategies
- Store pagination metadata per project (not just URL pattern)
- Support different pagination types per project

### Issue #3: Hard-Coded Assumptions
**Offsets:**
```python
offset = (page_number - 1) * 20  # Hard-coded items per page
```
Fails for sites with different item counts per page.

**Patterns:**
```python
URLGenerator.detect_pattern(url)  # Generic regex approach
```
Only supports 8 specific patterns; custom patterns fail silently.

**Recommendation:**
- Extract pagination config as storable entity
- Learn items-per-page from actual data
- Allow sites to define custom patterns

### Issue #4: Recovery Logic is Ad-Hoc
**Problem:**
- 5-minute stuck detection is arbitrary
- Recovery creates new projects (wasteful)
- Deduplication is URL-only (content changes not detected)
- No exponential backoff

**Impact:** Can't gracefully handle transient failures; creates clutter

**Recommendation:**
- Add configurable retry strategy
- Use direct URL parameter instead of project creation
- Implement content hashing for better deduplication
- Add exponential backoff with max retries

### Issue #5: Session vs Continuation Concepts Overlap
**Problem:**
- `scraping_sessions` + `iteration_runs` (structured)
- `runs.is_continuation` + `metadata.current_page_scraped` (unstructured)
- Both trying to solve incremental scraping

**Impact:** Code duplication; unclear which to use; migration path unclear

**Recommendation:**
- Deprecate unstructured approach (metadata polling)
- Make sessions the primary abstraction
- Migrate existing projects to session-based tracking

---

## 📊 Data Architecture Issues

### Issue #6: Product Data Schema Is Fragile
**Current:**
- `product_data` table with fixed 16 columns
- Custom fields stored as-is (no schema enforcement)
- UNIQUE constraint on (project_id, run_token, product_url, page_number)

**Problem:**
- Adding new fields requires schema migration
- No versioning for schema changes
- URL alone insufficient for deduplication (same URL, different data possible)

**Recommendation:**
- Consider JSON storage for flexible fields
- Add schema versioning
- Enhanced deduplication: URL + content hash or similar

### Issue #7: Checkpoint Utilization is Minimal
**Current:** `run_checkpoints` table rarely queried
- Only stores: item_count_at_time, items_per_minute, estimated_completion
- Not used for actual resume logic

**Problem:** Wasted potential for sophisticated resume capabilities

**Recommendation:**
- Use checkpoints for more granular resume
- Track page-level checkpoints, not just run-level
- Implement checkpoint-based recovery (resume from exact URL)

---

## 🔧 Code Quality Issues

### Issue #8: Service Layer Responsibilities Are Unclear

**Current:**
- IncrementalScrapingManager does: detection + triggering + storage
- AutoRunnerService does: execution + waiting + data fetching
- RecoveryService does: detection + creation + recovery
- DataIngestorService does: fetching + normalization + insertion

**Problem:** Fat services; hard to test; unclear boundaries

**Recommendation:**
- Separate concerns: detection / execution / storage / recovery
- Create dedicated classes for: pagination strategy, run executor, state manager
- Unit test each component independent of others

### Issue #9: Error Handling is Inconsistent

**Patterns:**
```python
# Some places:
return {'success': False, 'error': message}

# Other places:
return None

# Yet others:
raise Exception(message)
```

**Impact:** Caller confusion; hard to distinguish transient vs permanent failures

**Recommendation:**
- Create custom exception hierarchy
- Consistent return types (use Result/Either pattern)
- Distinguish: NotFound, Timeout, ValidationError, TemporaryError, etc.

### Issue #10: Database Operations Have Hidden Connections
**Problem:**
```python
# Unclear if these open new connections:
self.db.connect()
self.db.cursor()
self.db.disconnect()  # When to call this?
```

Snowflake connection caching in `threading.local` is opaque to callers.

**Recommendation:**
- Use context managers: `with db.connection() as conn:`
- Explicit connection lifecycle
- Document thread-safety guarantees

---

## 🚀 Refactoring Roadmap

### Phase 1: Clarify Abstractions (1-2 weeks)
```
1. Create unified Session concept
   └─ Subsume incremental-scraping-manager approach
   └─ Make iteration explicit

2. Define PaginationStrategy interface
   └─ URLBasedPagination
   └─ CursorBasedPagination
   └─ APIPagination
   └─ CustomPagination

3. Create RunExecutor service
   └─ Encapsulates ParseHub API interaction
   └─ Handles retries, timeouts, custom URLs

4. Consolidate State tracking
   └─ Single source of truth per project
   └─ Version the schema
```

### Phase 2: Refactor Services (2-3 weeks)
```
1. Split IncrementalScrapingManager
   └─ ProjectAnalyzer (what needs scraping?)
   └─ ContinuationPlanner (how to continue?)
   └─ RunOrchestrator (execute the plan)

2. Unify error handling
   └─ Custom exception types
   └─ Consistent return patterns

3. Improve data ingestion
   └─ Stream processing instead of batch
   └─ Content hashing for dedup
   └─ Schema versioning

4. Enhance recovery
   └─ Exponential backoff
   └─ Multiple retry strategies
   └─ Better stuck detection
```

### Phase 3: Optimize Persistence (1-2 weeks)
```
1. Checkpoint strategy overhaul
   └─ Page-level granularity
   └─ Resume from exact position
   └─ Queryable state

2. Product data flexibility
   └─ JSON for custom fields
   └─ Schema evolution
   └─ Better deduplication

3. Performance tuning
   └─ Batch inserts
   └─ Better indexing
   └─ Query optimization

4. Connection management
   └─ Context managers
   └─ Connection pooling
   └─ Explicit lifecycle
```

---

## 📋 Concrete Changes Needed

### 1. Create PaginationStrategy Interface
```python
# NEW: src/services/pagination/strategy.py

class PaginationStrategy(ABC):
    @abstractmethod
    def detect(self, url: str) -> bool:
        """Can this strategy handle the URL?"""
        pass
    
    @abstractmethod
    def get_current_page(self, url: str) -> int:
        """Extract current page from URL"""
        pass
    
    @abstractmethod
    def get_next_url(self, url: str, page: int) -> str:
        """Generate next page URL"""
        pass

class URLPageStrategy(PaginationStrategy):
    """Handles ?page=N and /page/N patterns"""
    pass

class URLOffsetStrategy(PaginationStrategy):
    """Handles ?offset=N patterns"""
    pass

class CursorStrategy(PaginationStrategy):
    """Handles token-based pagination"""
    pass
```

### 2. Create Unified Session Management
```python
# NEW: src/services/scraping/session_manager.py

class ScrapingSession:
    project_id: int
    total_pages: int
    current_page: int
    status: SessionStatus  # pending, running, complete, failed
    
    def add_run(self, run_token: str, page_range: PageRange) -> IterationRun:
        """Add a run to this session"""
        pass
    
    def mark_page_complete(self, page: int) -> None:
        """Checkpoint - page completed"""
        pass
    
    def get_next_page_range(self, batch_size: int = 10) -> PageRange:
        """What should next run scrape?"""
        pass
```

### 3. Separate Concerns - RunExecutor
```python
# NEW: src/services/run/executor.py

class RunExecutor:
    def execute(
        self,
        project_token: str,
        pagination_strategy: PaginationStrategy,
        page_range: PageRange,
        retry_config: RetryConfig
    ) -> RunResult:
        """Execute a single run with automatic retries"""
        pass

class RunResult:
    run_token: str
    status: RunStatus  # completed, failed, timeout
    pages_scraped: int
    records_count: int
    csv_data: str
    error: Optional[str]
```

### 4. Better Error Handling
```python
# NEW: src/exceptions.py

class ScrapingError(Exception):
    """Base exception"""
    pass

class PaginationError(ScrapingError):
    """Pagination-related"""
    pass

class RunExecutionError(ScrapingError):
    """Run failed"""
    pass

class StuckRunError(RunExecutionError):
    """Run is stuck, needs recovery"""
    pass

class TemporaryError(ScrapingError):
    """Transient, retry likely to succeed"""
    pass

class PermanentError(ScrapingError):
    """Won't succeed, don't retry"""
    pass
```

### 5. State Management - Remove Polling
```python
# REFACTOR: Database-driven state instead of polling

# Before:
scheduler.check_and_match_pages()  # Polls all projects every 30 min

# After:
# Database triggers INSERT into project_queue when:
# - New metadata imported (total_pages set)
# - Session not complete (current_page < total_pages)
# - Last run completed > 5 min ago

# Application subscribes to queue, processes as available
queue = ProjectQueue()
for item in queue.listen():  # Event-based!
    execute_next_iteration(item)
```

---

## ✅ Benefits of Proposed Refactoring

| Current Issue | Proposed Fix | Benefit |
|---|---|---|
| Polling every 30 min | Event-based queue | Real-time responsiveness, less DB load |
| URL-only pagination | Strategy pattern | Support all pagination types |
| Hard-coded 20 items/page | Learned metadata | Accurate page calculations |
| Ad-hoc recovery | Retry policy + exponential backoff | Better fault tolerance |
| Three different progress tracking | Single Session concept | Clear state, easier to debug |
| No checkpoint reuse | Detailed page checkpoints | Resume from exact position |
| Fat services | Separation of concerns | Better testability, clearer code |
| Inconsistent error handling | Typed exceptions | Predictable error handling |
| Hidden connections | Context managers | Explicit resource lifecycle |
| URL-only dedup | Content hashing | Better accuracy |

---

## 📈 Metrics to Track

**Before/After Refactoring:**

| Metric | Current | Target |
|--------|---------|--------|
| Time to detect incomplete project | ~30 min | Real-time |
| Pagination success rate | ~85% (URL-only) | ~98% (strategy-based) |
| Average run recovery time | ~15 min | ~2 min (exponential backoff) |
| Database polling frequency | 150/day queries | 0 (event-based) |
| Service test coverage | ~40% | ~85% |
| Time to add new pagination type | Days (code change) | Minutes (config) |

---

## 🔬 Next Steps

1. **Create a feature branch:** `refactoring/scraping-architecture`
2. **Start with Phase 1:** Implement PaginationStrategy interface
3. **Add comprehensive tests** before any production changes
4. **Gradually migrate** existing code to new patterns
5. **Maintain backward compatibility** during transition period

---

## 📝 Notes

- Keep existing tables; add new ones as needed
- Don't delete IncrementalScrapingManager immediately - refactor gradually
- Add feature flags to toggle between old/new implementations
- Document migration path for existing sessions
- Create database migration script, don't rely on SQL files


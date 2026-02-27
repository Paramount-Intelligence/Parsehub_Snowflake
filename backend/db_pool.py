"""
db_pool.py — Centralized PostgreSQL connection pool for Flask / Gunicorn.

Architecture
------------
* One process-level pool per Gunicorn worker (created lazily on first use).
* pg8000 is used as the driver; psycopg2 is preferred when available.
* Pool is sized to 2 connections per worker to stay well under Railway's
  default limit of 100 (e.g. 4 workers × 2 connections = 8 total).
* Each request borrows a connection, uses it, and returns it to the pool.
* If the pool is exhausted the request waits up to POOL_TIMEOUT seconds
  before raising a clear error rather than crashing the worker.

Why this fixes "sorry, too many clients already"
-------------------------------------------------
Before: each ParseHubDatabase() instantiation called connect() immediately at
        module import time. Gunicorn forks N workers; each worker imports the
        module → N × 3+ connections opened on boot, exhausting the limit.

After:  The pool is only created lazily (on the first actual HTTP request).
        No connections open at import time.  The pool has a hard cap so the
        total connections across all workers stay within Railway's limit.
"""

import os
import threading
import queue
import logging
from contextlib import contextmanager
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# ── Pool configuration (tune via environment variables) ──────────────────────
POOL_SIZE      = int(os.getenv('DB_POOL_SIZE', '2'))      # connections per worker
POOL_TIMEOUT   = float(os.getenv('DB_POOL_TIMEOUT', '10')) # seconds to wait for a conn
DB_URL         = os.getenv('DATABASE_URL', '')


def _detect_driver():
    try:
        import psycopg2  # noqa: F401
        return 'psycopg2'
    except ImportError:
        pass
    try:
        import pg8000  # noqa: F401
        return 'pg8000'
    except ImportError:
        return None


DRIVER = _detect_driver()


def _open_raw_connection():
    """Open a brand-new connection to PostgreSQL."""
    if not DB_URL:
        raise RuntimeError(
            'DATABASE_URL is not set. '
            'Add it to your Railway backend service → Variables.'
        )

    if DRIVER == 'psycopg2':
        import psycopg2
        conn = psycopg2.connect(DB_URL)
        conn.autocommit = True
        return conn

    if DRIVER == 'pg8000':
        import pg8000
        url = urlparse(DB_URL)
        conn = pg8000.connect(
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port or 5432,
            database=url.path.lstrip('/'),
        )
        conn.autocommit = True
        return conn

    raise RuntimeError(
        'No PostgreSQL driver found. '
        'Install psycopg2-binary or pg8000 (already in requirements.txt).'
    )


def _is_alive(conn) -> bool:
    """Cheap health-check for a pooled connection."""
    try:
        if DRIVER == 'psycopg2':
            conn.cursor().execute('SELECT 1')
        else:
            conn.run('SELECT 1')
        return True
    except Exception:
        return False


class ConnectionPool:
    """
    A minimal, thread-safe connection pool backed by a Queue.

    * `get()` → borrows a healthy connection (blocks up to POOL_TIMEOUT).
    * `put(conn)` → returns it; closes and replaces broken connections.
    * `close_all()` → drains the pool (call on worker shutdown).
    """

    def __init__(self, size: int = POOL_SIZE):
        self._size  = size
        self._pool: queue.Queue = queue.Queue(maxsize=size)
        self._lock  = threading.Lock()
        self._count = 0   # total connections ever created (≤ size)
        self._initialized = False

    def _ensure_initialized(self):
        """Fill the pool on first use (lazy — no connections at import time)."""
        if self._initialized:
            return
        with self._lock:
            if self._initialized:
                return
            for _ in range(self._size):
                try:
                    conn = _open_raw_connection()
                    self._pool.put_nowait(conn)
                    self._count += 1
                except Exception as exc:
                    logger.warning(f'[pool] Could not pre-fill connection: {exc}')
            self._initialized = True
            logger.info(
                f'[pool] Initialized with {self._pool.qsize()}/{self._size} connections '
                f'(driver={DRIVER})'
            )

    def get(self):
        """Borrow a connection from the pool."""
        self._ensure_initialized()
        try:
            conn = self._pool.get(timeout=POOL_TIMEOUT)
        except queue.Empty:
            raise RuntimeError(
                f'[pool] No connection available after {POOL_TIMEOUT}s. '
                'Consider increasing DB_POOL_SIZE or reducing worker count.'
            )

        # Replace dead connections silently
        if not _is_alive(conn):
            logger.warning('[pool] Stale connection detected, replacing...')
            try:
                conn.close()
            except Exception:
                pass
            conn = _open_raw_connection()

        return conn

    def put(self, conn, broken: bool = False):
        """Return a connection to the pool (or discard if broken)."""
        if broken:
            try:
                conn.close()
            except Exception:
                pass
            # Spin up a replacement so the pool stays full
            try:
                conn = _open_raw_connection()
            except Exception as exc:
                logger.error(f'[pool] Could not replace broken connection: {exc}')
                return
        try:
            self._pool.put_nowait(conn)
        except queue.Full:
            # Pool is full (shouldn't happen but be safe)
            try:
                conn.close()
            except Exception:
                pass

    def close_all(self):
        """Drain and close every connection in the pool."""
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                conn.close()
            except Exception:
                pass
        self._initialized = False
        logger.info('[pool] All connections closed.')


# ── Module-level singleton ────────────────────────────────────────────────────
# One pool per Gunicorn worker process.  Forking creates independent pools.
_pool: Optional[ConnectionPool] = None
_pool_lock = threading.Lock()


def get_pool() -> ConnectionPool:
    """Return the process-level pool, creating it on first call."""
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = ConnectionPool(size=POOL_SIZE)
    return _pool


@contextmanager
def get_db_connection():
    """
    Context manager: borrow a connection, yield it, always return it.

    Usage in a route:
        from db_pool import get_db_connection
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(...)
    """
    pool = get_pool()
    conn = pool.get()
    broken = False
    try:
        yield conn
    except Exception:
        broken = True
        raise
    finally:
        pool.put(conn, broken=broken)


def ping_db() -> bool:
    """Quick DB health check — returns True if reachable."""
    try:
        with get_db_connection() as conn:
            if DRIVER == 'psycopg2':
                conn.cursor().execute('SELECT 1')
            else:
                conn.run('SELECT 1')
        return True
    except Exception:
        return False

"""SQLite connection management and the versioned migration runner.

Design goals (Master Prompt §4, §49):
  * local-first single file, SQLite + FTS5;
  * idempotent, transactional, checksum-verified migrations;
  * safe additive column migrations;
  * no destructive migration is ever automatic;
  * concurrent startup is guarded by a file lock.
"""

from __future__ import annotations

import hashlib
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Sequence

from .errors import MigrationError
from .util import now_iso

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

try:  # pragma: no cover - platform dependent
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]


def split_sql_statements(script: str) -> list[str]:
    """Split a SQL script into statements using SQLite's own completeness test.

    This correctly handles triggers (which contain internal semicolons).
    """
    statements: list[str] = []
    buffer = ""
    for line in script.splitlines(keepends=True):
        buffer += line
        if sqlite3.complete_statement(buffer):
            stmt = buffer.strip()
            if stmt and stmt != ";":
                statements.append(stmt)
            buffer = ""
    tail = buffer.strip()
    if tail:
        statements.append(tail)
    return statements


def _checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def discover_migrations(directory: Path | None = None) -> list[tuple[int, str, Path]]:
    directory = directory or MIGRATIONS_DIR
    found: list[tuple[int, str, Path]] = []
    for path in sorted(directory.glob("*.sql")):
        stem = path.stem
        if "_" not in stem:
            continue
        prefix, _, name = stem.partition("_")
        if not prefix.isdigit():
            continue
        found.append((int(prefix), name, path))
    return sorted(found, key=lambda item: item[0])


class Database:
    """A single authoritative local SQLite store."""

    def __init__(
        self,
        path: str | Path = ":memory:",
        *,
        timeout: float = 30.0,
        auto_migrate: bool = True,
    ) -> None:
        self.path = str(path)
        self.timeout = timeout
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.RLock()
        self._tx_depth = 0
        if auto_migrate:
            self.migrate()

    # ── connection ───────────────────────────────────────────────────────────
    @property
    def connection(self) -> sqlite3.Connection:
        with self._lock:
            if self._conn is None:
                self._conn = self._connect()
            return self._conn

    def _connect(self) -> sqlite3.Connection:
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(
            self.path,
            timeout=self.timeout,
            isolation_level=None,          # autocommit; we drive transactions
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 30000")
        if self.path != ":memory:":
            try:
                conn.execute("PRAGMA journal_mode = WAL")
            except sqlite3.DatabaseError:
                pass
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.create_function("regexp", 2, _regexp)
        return conn

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ── transactions ─────────────────────────────────────────────────────────
    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Re-entrant transaction using SAVEPOINTs for nesting."""
        with self._lock:
            conn = self.connection
            depth = self._tx_depth
            savepoint = f"pp_sp_{depth}"
            try:
                if depth == 0:
                    conn.execute("BEGIN IMMEDIATE")
                else:
                    conn.execute(f"SAVEPOINT {savepoint}")
                self._tx_depth = depth + 1
                yield conn
            except BaseException:
                self._tx_depth = depth
                if depth == 0:
                    conn.execute("ROLLBACK")
                else:
                    conn.execute(f"ROLLBACK TO {savepoint}")
                    conn.execute(f"RELEASE {savepoint}")
                raise
            else:
                self._tx_depth = depth
                if depth == 0:
                    conn.execute("COMMIT")
                else:
                    conn.execute(f"RELEASE {savepoint}")

    # ── query helpers ────────────────────────────────────────────────────────
    def execute(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Cursor:
        with self._lock:
            return self.connection.execute(sql, tuple(params))

    def executemany(self, sql: str, seq: Sequence[Sequence[Any]]) -> sqlite3.Cursor:
        with self._lock:
            return self.connection.executemany(sql, seq)

    def query(self, sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self.connection.execute(sql, tuple(params)).fetchall()

    def query_one(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Row | None:
        with self._lock:
            return self.connection.execute(sql, tuple(params)).fetchone()

    def scalar(self, sql: str, params: Sequence[Any] = (), default: Any = None) -> Any:
        row = self.query_one(sql, params)
        if row is None:
            return default
        value = row[0]
        return default if value is None else value

    # ── migrations ───────────────────────────────────────────────────────────
    def migrate(self, directory: Path | None = None) -> list[int]:
        with self._lock:
            conn = self.connection
            lock_handle = self._acquire_lock()
            try:
                self._ensure_migration_table(conn)
                applied = {
                    row["version"]
                    for row in conn.execute("SELECT version FROM schema_migrations")
                }
                newly: list[int] = []
                for version, name, path in discover_migrations(directory):
                    if version in applied:
                        self._verify_checksum(conn, version, path)
                        continue
                    self._apply_migration(conn, version, name, path)
                    newly.append(version)
                return newly
            finally:
                self._release_lock(lock_handle)

    def _ensure_migration_table(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version    INTEGER PRIMARY KEY,
                name       TEXT NOT NULL,
                applied_at TEXT NOT NULL,
                checksum   TEXT NOT NULL
            )
            """
        )

    def _verify_checksum(self, conn: sqlite3.Connection, version: int, path: Path) -> None:
        expected = _checksum(path.read_bytes())
        row = conn.execute(
            "SELECT checksum FROM schema_migrations WHERE version = ?", (version,)
        ).fetchone()
        if row and row["checksum"] != expected:
            raise MigrationError(
                f"migration {version} ({path.name}) checksum changed after it was "
                f"applied; refusing to continue"
            )

    def _apply_migration(self, conn: sqlite3.Connection, version: int, name: str, path: Path) -> None:
        script = path.read_text(encoding="utf-8")
        statements = split_sql_statements(script)
        try:
            conn.execute("BEGIN IMMEDIATE")
            for stmt in statements:
                if self._skip_redundant_alter(conn, stmt):
                    continue
                conn.execute(stmt)
            conn.execute(
                "INSERT INTO schema_migrations(version, name, applied_at, checksum) "
                "VALUES (?, ?, ?, ?)",
                (version, name, now_iso(), _checksum(path.read_bytes())),
            )
            conn.execute("COMMIT")
        except Exception as exc:  # noqa: BLE001 - re-raised as MigrationError
            conn.execute("ROLLBACK")
            raise MigrationError(f"failed to apply migration {version} ({path.name}): {exc}") from exc

    @staticmethod
    def _skip_redundant_alter(conn: sqlite3.Connection, stmt: str) -> bool:
        """Skip ``ALTER TABLE t ADD COLUMN c`` if the column already exists.

        Keeps additive migrations idempotent even if a prior partial run occurred
        or a fresh schema already defines the column.
        """
        upper = stmt.upper()
        if not upper.startswith("ALTER TABLE") or " ADD COLUMN " not in upper:
            return False
        try:
            head, _, rest = stmt.partition(" ADD COLUMN ")
            table = head.replace("ALTER TABLE", "", 1).strip().strip('"`[]')
            column = rest.strip().split()[0].strip('"`[]')
        except Exception:  # noqa: BLE001
            return False
        rows = conn.execute(f"PRAGMA table_info({_quote_ident(table)})").fetchall()
        return any(r[1].lower() == column.lower() for r in rows)

    # ── locking ──────────────────────────────────────────────────────────────
    def _acquire_lock(self):  # type: ignore[no-untyped-def]
        if self.path == ":memory:" or fcntl is None:
            return None
        lock_path = Path(self.path + ".migrate.lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = lock_path.open("w")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        except OSError:  # pragma: no cover
            handle.close()
            return None
        return handle

    @staticmethod
    def _release_lock(handle) -> None:  # type: ignore[no-untyped-def]
        if handle is None:
            return
        try:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()

    # ── diagnostics ──────────────────────────────────────────────────────────
    def applied_migrations(self) -> list[sqlite3.Row]:
        return self.query("SELECT version, name, applied_at FROM schema_migrations ORDER BY version")

    def integrity_check(self) -> str:
        return str(self.scalar("PRAGMA integrity_check", default="unknown"))

    def fts_ok(self) -> bool:
        try:
            self.query_one("SELECT rowid FROM memory_fts LIMIT 1")
            return True
        except sqlite3.DatabaseError:
            return False

    def size_bytes(self) -> int:
        if self.path == ":memory:":
            return 0
        try:
            return Path(self.path).stat().st_size
        except OSError:
            return 0


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _regexp(pattern: str, value: str | None) -> bool:
    import re

    if value is None:
        return False
    try:
        return re.search(pattern, value) is not None
    except re.error:
        return False

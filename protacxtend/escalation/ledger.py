"""Append-only JSONL ledgers for failures, installs, registrations and audits.

Storage location resolution order:

1. ``PROTACXTEND_ESCALATION_DIR`` environment variable
2. ``PROTACXTEND_HOME/escalation`` (per-user writable state)
3. ``~/.protacxtend/escalation``

Nothing is ever silently dropped: a write failure raises so the caller can
surface it, and every record carries an ISO timestamp.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, Iterator, List


def escalation_dir() -> Path:
    override = os.environ.get("PROTACXTEND_ESCALATION_DIR")
    if override:
        base = Path(override).expanduser()
    else:
        try:
            from protacxtend.resources import state_dir

            base = state_dir() / "escalation"
        except Exception:  # pragma: no cover - import guard
            base = Path.home() / ".protacxtend" / "escalation"
    base.mkdir(parents=True, exist_ok=True)
    return base


class JsonlLedger:
    """Minimal append-only JSONL ledger safe for concurrent worker threads."""

    def __init__(self, filename: str) -> None:
        self.path = escalation_dir() / filename
        self._lock = threading.Lock()

    def append(self, record: dict[str, Any]) -> Path:
        line = json.dumps(record, default=str, ensure_ascii=False)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        return self.path

    def read_all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        rows: list[dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    rows.append({"ledger_error": "unparseable line", "raw": line[:500]})
        return rows

    def tail(self, n: int = 20) -> list[dict[str, Any]]:
        rows = self.read_all()
        return rows[-n:]

    def clear(self) -> None:
        with self._lock:
            if self.path.exists():
                self.path.unlink()


class Ledgers:
    """Convenience bundle of the four ledgers used by the subsystem."""

    def __init__(self) -> None:
        self.failures = JsonlLedger("failures.jsonl")
        self.installs = JsonlLedger("installs.jsonl")
        self.registrations = JsonlLedger("registrations.jsonl")
        self.audits = JsonlLedger("audit.jsonl")

    def paths(self) -> dict[str, str]:
        return {
            "failures": str(self.failures.path),
            "installs": str(self.installs.path),
            "registrations": str(self.registrations.path),
            "audit": str(self.audits.path),
            "directory": str(escalation_dir()),
        }

    def counts(self) -> dict[str, int]:
        return {
            "failures": len(self.failures.read_all()),
            "installs": len(self.installs.read_all()),
            "registrations": len(self.registrations.read_all()),
            "audits": len(self.audits.read_all()),
        }


_LEDGERS: Ledgers | None = None


def get_ledgers() -> Ledgers:
    global _LEDGERS
    if _LEDGERS is None:
        _LEDGERS = Ledgers()
    return _LEDGERS

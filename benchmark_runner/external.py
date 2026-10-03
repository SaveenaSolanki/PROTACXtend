"""External-system adapters: Biomni and a TPD comparator.

Both adapters are *real* integration points that are fail-closed:

* with ``allow_real=False`` they raise :class:`~benchmark_runner.runner.AdapterError`,
  exactly like every other benchmark system;
* with ``allow_real=True`` they invoke a configured external command over a
  JSON stdin/stdout contract and record the command, version and raw output;
* if no command/endpoint is configured they return an explicit ``unavailable``
  result — they never fabricate an answer.

Configuration (environment variables):

* ``PROTACXTEND_BIOMNI_CMD``       — command template, e.g. ``biomni run --json``
* ``PROTACXTEND_BIOMNI_VERSION``   — optional version string
* ``PROTACXTEND_TPD_COMPARATOR_CMD``      — comparator command template
* ``PROTACXTEND_TPD_COMPARATOR_VERSION``  — optional version string

The task is passed as a JSON object on stdin; the command must print a JSON
object on stdout. Any recognised ``answer`` key is used for scoring; the full
payload is preserved as the raw response.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import time
from typing import Any, Dict

from benchmark_runner.runner import AdapterError, SystemAdapter, TaskInput

#: Timeout for an external command (seconds).
EXTERNAL_TIMEOUT_S = 1800


class _ExternalCommandAdapter(SystemAdapter):
    """Subprocess adapter with a documented JSON contract."""

    env_command = ""
    env_version = ""
    system_id = "external"

    def __init__(self, system_id: str, allow_real: bool = False) -> None:
        self.system_id = system_id or self.system_id
        self.allow_real = allow_real

    # ------------------------------------------------------------------
    def _command(self) -> list[str]:
        raw = os.environ.get(self.env_command, "").strip()
        return shlex.split(raw) if raw else []

    def _declared_version(self) -> str:
        return os.environ.get(self.env_version, "").strip() or "unconfigured"

    def execute(self, task: TaskInput, ctx: dict[str, Any]) -> dict[str, Any]:
        if not self.allow_real:
            raise AdapterError(
                f"adapter {self.system_id}: real benchmark execution disabled "
                "(set allow_real=True and configure the external command)"
            )
        command = self._command()
        if not command:
            return {
                "status": "unavailable",
                "raw": "",
                "answer": None,
                "provider": self.system_id,
                "model": self.system_id,
                "version": self._declared_version(),
                "tool_calls": 0,
                "tokens_in": 0,
                "tokens_out": 0,
                "cost_usd": 0.0,
                "artifacts": [],
                "error": f"{self.env_command} is not configured; external system unavailable",
                "external": {"command": "", "returncode": None},
            }
        payload = {
            "task": task.to_run_dict(),
            "seed": ctx.get("seed", 0),
            "temperature": ctx.get("temperature", 0.0),
        }
        started = time.monotonic()
        try:
            completed = subprocess.run(  # noqa: S603 - command is operator-configured
                command,
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                timeout=EXTERNAL_TIMEOUT_S,
                check=False,
            )
        except FileNotFoundError as exc:
            return {
                "status": "unavailable", "raw": "", "answer": None,
                "provider": self.system_id, "model": self.system_id,
                "version": self._declared_version(), "tool_calls": 0,
                "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "artifacts": [],
                "error": f"command not found: {exc}",
                "external": {"command": command, "returncode": None},
            }
        latency = round(time.monotonic() - started, 3)
        stdout = completed.stdout or ""
        parsed: dict[str, Any] = {}
        try:
            parsed = json.loads(stdout) if stdout.strip() else {}
        except json.JSONDecodeError:
            parsed = {"answer": stdout.strip()}
        answer = parsed.get("answer") or parsed.get("final_answer") or parsed.get("output")
        status = "ok" if completed.returncode == 0 else "tool_failure"
        return {
            "status": status,
            "raw": stdout,
            "answer": answer,
            "provider": self.system_id,
            "model": self.system_id,
            "version": self._declared_version(),
            "tool_calls": int(parsed.get("tool_calls", 0) or 0),
            "tokens_in": int(parsed.get("tokens_in", 0) or 0),
            "tokens_out": int(parsed.get("tokens_out", 0) or 0),
            "cost_usd": float(parsed.get("cost_usd", 0.0) or 0.0),
            "artifacts": list(parsed.get("artifacts", []) or []),
            "error": (completed.stderr or "").strip()[:500] if completed.returncode else None,
            "external": {
                "command": command,
                "returncode": completed.returncode,
                "latency_s": latency,
            },
        }


class BiomniAdapter(_ExternalCommandAdapter):
    """Biomni scientific-agent workflow (external command contract)."""

    system_id = "Biomni"
    env_command = "PROTACXTEND_BIOMNI_CMD"
    env_version = "PROTACXTEND_BIOMNI_VERSION"


class TPDComparatorAdapter(_ExternalCommandAdapter):
    """TPD comparator (external command or frozen comparator table)."""

    system_id = "TPD-comparator"
    env_command = "PROTACXTEND_TPD_COMPARATOR_CMD"
    env_version = "PROTACXTEND_TPD_COMPARATOR_VERSION"


__all__ = ["BiomniAdapter", "TPDComparatorAdapter", "_ExternalCommandAdapter"]

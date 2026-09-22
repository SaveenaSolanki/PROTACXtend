"""Persistent dynamic tool registry.

When an external tool is installed and validated by the escalation pipeline it
is *registered* here so subsequent runs can reuse it without re-diagnosing.
The registry is a single JSON document and never shadows the static
``toolkit_registry`` — it layers on top with ``source="dynamic"``.
"""

from __future__ import annotations

import builtins
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from protacxtend.escalation.contracts import ExternalToolCandidate, RegistrationRecord
from protacxtend.escalation.ledger import escalation_dir, get_ledgers


class DynamicToolRegistry:
    def __init__(self, path: Path | None = None, ledgers=None) -> None:
        self.path = Path(path) if path else (escalation_dir() / "dynamic_registry.json")
        self.ledgers = ledgers
        self._cache: dict[str, Any] | None = None

    # ── io ──────────────────────────────────────────────────────────
    def _load(self) -> dict[str, Any]:
        if self._cache is not None:
            return self._cache
        if self.path.exists():
            try:
                self._cache = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                self._cache = {}
        else:
            self._cache = {}
        self._cache.setdefault("tools", {})
        return self._cache

    def _save(self) -> None:
        if self._cache is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._cache, indent=2, default=str), encoding="utf-8"
        )

    # ── api ─────────────────────────────────────────────────────────
    def register(
        self,
        tool_name: str,
        *,
        capabilities: builtins.list[str] | None = None,
        version: str = "",
        status: str = "installed",
        source: str = "escalation",
        pip_package: str = "",
        install_method: str = "",
        category: str = "",
        notes: str = "",
    ) -> RegistrationRecord:
        data = self._load()
        entry = data["tools"].get(tool_name, {})
        caps = sorted(set(entry.get("capabilities", []) or []) | set(capabilities or []))
        entry.update(
            {
                "tool_name": tool_name,
                "capabilities": caps,
                "version": version or entry.get("version", ""),
                "status": status,
                "source": source,
                "pip_package": pip_package or entry.get("pip_package", ""),
                "install_method": install_method or entry.get("install_method", ""),
                "category": category or entry.get("category", ""),
                "notes": notes or entry.get("notes", ""),
            }
        )
        data["tools"][tool_name] = entry
        self._save()

        record = RegistrationRecord(
            tool_name=tool_name,
            registered=True,
            source=source,
            version=entry["version"],
            capabilities=caps,
            status=status,
            notes=notes,
        )
        if self.ledgers is None:
            self.ledgers = get_ledgers()
        self.ledgers.registrations.append(record.to_dict())
        return record

    def is_registered(self, tool_name: str) -> bool:
        return tool_name in self._load()["tools"]

    def get(self, tool_name: str) -> dict[str, Any] | None:
        return self._load()["tools"].get(tool_name)

    def list(self) -> builtins.list[dict[str, Any]]:
        return sorted(self._load()["tools"].values(), key=lambda r: r["tool_name"])

    def find_by_capability(self, capability: str) -> builtins.list[dict[str, Any]]:
        return [r for r in self.list() if capability in r.get("capabilities", [])]

    def as_candidates(self) -> builtins.list[ExternalToolCandidate]:
        out: list[ExternalToolCandidate] = []
        for row in self.list():
            out.append(
                ExternalToolCandidate(
                    tool_name=row["tool_name"],
                    category=row.get("category", "") or "dynamic",
                    purpose=row.get("notes", "") or "dynamically registered tool",
                    reason="dynamic registry",
                    status=row.get("status", "installed"),
                    installed=True,
                    version=row.get("version", ""),
                    install_method=row.get("install_method", ""),
                    pip_package=row.get("pip_package", ""),
                )
            )
        return out

    def unregister(self, tool_name: str) -> bool:
        data = self._load()
        if tool_name in data["tools"]:
            del data["tools"][tool_name]
            self._save()
            return True
        return False

    def clear(self) -> None:
        self._cache = {"tools": {}}
        self._save()

    def merge_into_toolkit_view(self) -> builtins.list[dict[str, Any]]:
        """Return the static toolkit registry plus dynamic entries.

        Dynamic entries are tagged so callers can distinguish validated
        external installs from the shipped catalogue.
        """
        try:
            from protacxtend.tools.toolkit_registry import get_toolkit_registry

            base = [dict(r) for r in get_toolkit_registry()]
        except Exception:
            base = []
        known = {r.get("tool_name") for r in base}
        for row in self.list():
            if row["tool_name"] in known:
                continue
            base.append(
                {
                    "tool_name": row["tool_name"],
                    "category": row.get("category", "dynamic"),
                    "subcategory": "dynamically_registered",
                    "purpose": row.get("notes", ""),
                    "executable_type": row.get("install_method", ""),
                    "install_hint": "",
                    "executable_names": [],
                    "python_imports": [],
                    "api_required": False,
                    "license_type": "",
                    "commercial": False,
                    "local_executable": True,
                    "web_service": False,
                    "agent_use_case": ", ".join(row.get("capabilities", [])),
                    "expected_inputs": [],
                    "expected_outputs": [],
                    "status": row.get("status", "installed"),
                    "reliability_level": "research",
                    "notes": "dynamic escalation registration",
                    "source": "dynamic",
                }
            )
        return base

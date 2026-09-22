"""Evidence Store — one provenance ledger for the canonical stack.

Every module result, tool call and claim is recorded here with a stable
``evidence_ref``. Downstream stages (critic, decision engine, reports,
benchmarks) reference evidence by key, never by re-deriving it. This replaces
the previous situation where the deterministic state, the adaptive graph and
the legacy agent each carried their own partially-overlapping provenance.

The in-memory ledger is authoritative for a run. When ``persist=True`` (or a
store is injected) records are also appended to the shared
:class:`protacxtend.memory.stores.EvidenceStore` JSONL.
"""

from __future__ import annotations

import hashlib
from typing import Any

from protacxtend.canonical.schemas import ModuleResult


class CanonicalEvidenceStore:
    """Append-only evidence ledger with module attribution."""

    def __init__(self, run_id: str = "", persist: bool = False, store: Any = None):
        self.run_id = run_id
        self._records: list[dict[str, Any]] = []
        self._by_ref: dict[str, dict[str, Any]] = {}
        self._persist = persist
        self._store = store
        if store is None and persist:
            try:
                from protacxtend.memory.stores import (
                    EvidenceStore as SharedEvidenceStore,
                )

                self._store = SharedEvidenceStore()
            except Exception:  # pragma: no cover - persistence is best-effort
                self._store = None

    # ------------------------------------------------------------------
    def add(
        self,
        *,
        evidence_type: str,
        content: Any,
        source: str,
        tool_version: str,
        citation: str = "",
        ref_key: str = "",
        module_id: str = "",
    ) -> str:
        ref = ref_key or self._make_ref(module_id, source, content)
        record = {
            "key": ref,
            "run_id": self.run_id,
            "evidence_type": evidence_type,
            "content": content,
            "source": source,
            "tool_version": tool_version,
            "citation": citation,
            "module_id": module_id,
        }
        self._records.append(record)
        self._by_ref[ref] = record
        if self._store is not None:
            try:
                self._store.record(
                    evidence_type=evidence_type,
                    content=content,
                    source=source,
                    tool_version=tool_version,
                    run_id=self.run_id,
                    citation=citation,
                    ref_key=ref,
                )
            except Exception:  # pragma: no cover - never fail a run on persistence
                pass
        return ref

    def add_module_result(self, result: ModuleResult) -> list[str]:
        refs: list[str] = []
        for key, value in result.outputs.items():
            ref = self.add(
                evidence_type="module_output",
                content=value if isinstance(value, (str, int, float, bool, list, dict, type(None))) else str(value),
                source=f"module:{result.module_id}",
                tool_version=str(result.provenance.get("tool_version") or result.module_id),
                module_id=result.module_id,
                ref_key=f"{result.module_id}:{key}",
            )
            refs.append(ref)
        if not result.outputs:
            refs.append(
                self.add(
                    evidence_type="module_result",
                    content={"summary": result.summary, "status": result.status.value},
                    source=f"module:{result.module_id}",
                    tool_version=result.module_id,
                    module_id=result.module_id,
                )
            )
        return refs

    # ------------------------------------------------------------------
    def get(self, ref: str) -> dict[str, Any] | None:
        return self._by_ref.get(ref)

    def records(self, module_id: str = "") -> list[dict[str, Any]]:
        if not module_id:
            return list(self._records)
        return [record for record in self._records if record.get("module_id") == module_id]

    def refs_for_module(self, module_id: str) -> list[str]:
        return [record["key"] for record in self.records(module_id)]

    def summary(self) -> dict[str, Any]:
        by_module: dict[str, int] = {}
        by_type: dict[str, int] = {}
        for record in self._records:
            by_module[record.get("module_id") or "unknown"] = by_module.get(record.get("module_id") or "unknown", 0) + 1
            by_type[record["evidence_type"]] = by_type.get(record["evidence_type"], 0) + 1
        return {"n_records": len(self._records), "by_module": by_module, "by_type": by_type}

    @staticmethod
    def _make_ref(module_id: str, source: str, content: Any) -> str:
        raw = f"{module_id}|{source}|{content}".encode("utf-8", errors="replace")
        return f"ev_{hashlib.sha256(raw).hexdigest()[:12]}"

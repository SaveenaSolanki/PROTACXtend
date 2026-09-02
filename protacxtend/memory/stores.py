"""
Memory unification (Task 7) — three separate stores, one module.
================================================================

  Run State Store   — current workflow + candidate state (per run)
  Evidence Store    — database records, structures, model outputs, citations
  Learning Store    — prior failures, successful repairs, human corrections

They are deliberately SEPARATE stores (not one generic memory database).

Learning retrieval sequence (the live-graph loop):
  current failure
      ↓ convert to structured failure signature (problem_type + failure_reason)
      ↓ search prior LearningEntry records (validated, matching signature)
      ↓ retrieve only matching cases
      ↓ suggest repair
      ↓ validate repair deterministically (closed vocabulary)
      ↓ record outcome (confirm/reject → adjusts future priority)

Hard rule: memory can suggest, but can NEVER override scientific validators.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("protacpilot.memory")

ROOT = Path(__file__).resolve().parents[2]
MEMORY_DIR = ROOT / "protacxtend" / "memory"
RUN_STATE_DIR = MEMORY_DIR / "run_state"
EVIDENCE_DIR = MEMORY_DIR / "evidence"


# ═══════════════════════════════════════════════════════════════
# 1. Run State Store
# ═══════════════════════════════════════════════════════════════

class RunStateStore:
    """Per-run workflow + candidate state snapshots (JSONL, append-only)."""

    def __init__(self, base_dir: Path | str | None = None):
        self.base_dir = Path(base_dir) if base_dir else RUN_STATE_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_snapshot(self, run_id: str, state: Dict[str, Any], label: str = "final") -> Path:
        path = self.base_dir / f"{run_id}.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "run_id": run_id,
                "label": label,
                "ts": datetime.now(timezone.utc).isoformat(),
                "state": _safe_state(state),
            }, default=str) + "\n")
        return path

    def load_snapshots(self, run_id: str) -> List[Dict[str, Any]]:
        path = self.base_dir / f"{run_id}.jsonl"
        if not path.exists():
            return []
        out = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return out


def _safe_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """Drop non-serializable large objects (mol objects, tensors)."""
    out = {}
    for k, v in state.items():
        if isinstance(v, (str, int, float, bool, list, dict)) or v is None:
            out[k] = v
        else:
            out[k] = f"<{type(v).__name__}>"
    return out


# ═══════════════════════════════════════════════════════════════
# 2. Evidence Store
# ═══════════════════════════════════════════════════════════════

class EvidenceStore:
    """Append-only evidence records with provenance (citations, versions)."""

    def __init__(self, base_dir: Path | str | None = None):
        self.base_dir = Path(base_dir) if base_dir else EVIDENCE_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._path = self.base_dir / "evidence.jsonl"

    def record(self, *, evidence_type: str, content: Any, source: str,
               tool_version: str, run_id: str = "", citation: str = "",
               ref_key: str = "") -> str:
        """Append one evidence record. Returns its key."""
        key = ref_key or f"ev_{uuid.uuid4().hex[:10]}"
        rec = {
            "key": key,
            "evidence_type": evidence_type,     # database/structure/model_output/citation
            "content": content,
            "source": source,                    # e.g. "ProtacPilot:chemprop_multitarget"
            "tool_version": tool_version,
            "run_id": run_id,
            "citation": citation,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, default=str) + "\n")
        return key

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        if not self._path.exists():
            return None
        with self._path.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    if rec.get("key") == key:
                        return rec
                except json.JSONDecodeError:
                    continue
        return None

    def query(self, evidence_type: Optional[str] = None, run_id: Optional[str] = None,
              limit: int = 50) -> List[Dict[str, Any]]:
        if not self._path.exists():
            return []
        out = []
        with self._path.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if evidence_type and rec.get("evidence_type") != evidence_type:
                    continue
                if run_id and rec.get("run_id") != run_id:
                    continue
                out.append(rec)
        return out[-limit:]


# ═══════════════════════════════════════════════════════════════
# 3. Learning Store (canonical wrapper over learning_memory)
# ═══════════════════════════════════════════════════════════════

class LearningStore:
    """Prior failures, successful repairs, human corrections.

    Wraps the canonical learning_memory engine (LearningEntry schema,
    validation lifecycle, reuse counts, outliers). Human corrections are
    kept distinguishable via LearningSource.HUMAN_FEEDBACK.
    """

    def __init__(self, memory=None):
        from protacxtend.tools.learning_memory import LearningMemory
        self.memory = memory or LearningMemory()

    def record_repair_outcome(self, *, problem_type: str, approach: str,
                              outcome: str, failure_reason: str = "other",
                              source: str = "direct_synthesis", run_id: str = "",
                              human_correction: str = "") -> str:
        from protacxtend.tools.learning_memory import LearningSource, Outcome
        if source == "human_feedback":
            src = LearningSource.HUMAN_FEEDBACK.value
        else:
            src = LearningSource.DIRECT_SYNTHESIS.value
        entry = self.memory.record(
            problem_type=problem_type, approach=approach, outcome=outcome,
            human_correction=human_correction, failure_reason=failure_reason,
            source=src, auto_validate_human=(src == "human_feedback"),
            # validated entries must clear the reuse gate (conf >= 0.7)
            confidence=0.85 if src == "human_feedback" else 0.8,
            run_id=run_id,
        )
        return entry.learning_id

    def retrieve_repair_for_failure(self, *, problem_type: str, failure_reason: str,
                                    target: str = "") -> List[Dict[str, Any]]:
        """Learning retrieval sequence: failure signature → matching validated
        learnings (only those with confidence ≥ reuse gate)."""
        from protacxtend.agents.learning_integration import advise_repair
        entries = advise_repair(problem_type, failure_reason, self.memory, target)
        return [e.to_dict() for e in entries]

    def mark_repair_failed(self, learning_id: str, note: str = "") -> None:
        """A reused repair that failed reduces future priority (reject/supersede)."""
        entry = self.memory.get(learning_id)
        if entry is None:
            return
        if entry.reuse_count > 0:
            # it was reused and failed → reject so it stops being suggested
            self.memory.reject(learning_id, note=f"reused repair failed: {note}")

    def confirm_repair_success(self, learning_id: str, run_id: str) -> None:
        """A reused repair that succeeded strengthens the learning."""
        self.memory.confirm_by_reuse(learning_id, run_id=run_id)

    def search(self, problem_type: Optional[str] = None, source: Optional[str] = None,
               validated_only: bool = True, limit: int = 20) -> List[Dict[str, Any]]:
        hits = self.memory.search(problem_type=problem_type, source=source,
                                  validated_only=validated_only, limit=limit)
        return [h.to_dict() for h in hits]


# ═══════════════════════════════════════════════════════════════
# Unified accessor
# ═══════════════════════════════════════════════════════════════

class MemoryHub:
    """One access point for all three stores (Task 7 definition of done)."""

    def __init__(self):
        self.run_state = RunStateStore()
        self.evidence = EvidenceStore()
        self.learning = LearningStore()

    def record_run(self, run_id: str, state: Dict[str, Any], label: str = "final") -> Path:
        return self.run_state.save_snapshot(run_id, state, label)

    def record_evidence(self, **kwargs) -> str:
        return self.evidence.record(**kwargs)

    def suggest_repair(self, *, problem_type: str, failure_reason: str,
                       target: str = "") -> List[Dict[str, Any]]:
        return self.learning.retrieve_repair_for_failure(
            problem_type=problem_type, failure_reason=failure_reason, target=target)

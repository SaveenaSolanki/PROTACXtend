"""
Structured Learning Memory for ProtacPilot agents.
===================================================

What this is
------------
A validated, structured learning database shared across agent runs.
Every process (direct synthesis run or human-feedback synthesis run)
can contribute learnings; agents query them before tackling similar
or new tasks; pattern extraction turns validated learnings into
explanations of *why* certain strategies succeed or fail.

Why structured (not free text)
------------------------------
Free-text lessons are noisy and preserve incorrect assumptions.
Each learning carries:
  - problem_type       (controlled vocabulary)
  - approach           (what was tried)
  - outcome            (success / partial / failure)
  - human_correction   (optional fix from the human)
  - failure_reason     (FailureClass-aligned + details)
  - confidence         (0-1)
  - source             (direct_synthesis | human_feedback)
  - validation         (candidate | validated | rejected | superseded)
  - provenance         (run_id, tool_versions, decision_log refs)

Validation lifecycle
--------------------
candidate → validated (by human confirmation OR by independent reuse)
candidate → rejected  (human says the learning is wrong)

Only VALIDATED learnings with confidence >= REUSE_CONFIDENCE_THRESHOLD
are returned by `search_learnings(..., validated_only=True)`.

Outliers
--------
A learning is an outlier when its outcome contradicts the established
pattern for its (problem_type, approach) cluster, or when its confidence
is far below the cluster norm. Outliers are flagged, not silently used.
Over time, pattern extraction on validated learnings explains why
synthesis strategies succeed or fail.

Storage
-------
- Machine-readable: JSONL append-only store
  (protacxtend/memory/learnings/learning_store.jsonl)
- Human-readable: per-run learnings.md
  (protacxtend/memory/learnings/runs/<run_id>/learnings.md)
- Global patterns: patterns.md (regenerated on demand)
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("protacpilot.learning")

# ─────────────────────────────────────────────────────────────────────
# Storage layout
# ─────────────────────────────────────────────────────────────────────

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
MEMORY_DIR = PACKAGE_ROOT / "memory"
LEARNING_DIR = MEMORY_DIR / "learnings"
STORE_PATH = LEARNING_DIR / "learning_store.jsonl"
RUNS_DIR = LEARNING_DIR / "runs"
PATTERNS_PATH = LEARNING_DIR / "patterns.md"

REUSE_CONFIDENCE_THRESHOLD = 0.7
VALIDATION_BY_REUSE_COUNT = 2  # independent runs needed to auto-validate


# ─────────────────────────────────────────────────────────────────────
# Controlled vocabularies
# ─────────────────────────────────────────────────────────────────────

class ProblemType(str, Enum):
    """Controlled vocabulary of problem types a PROTAC-design stage can face."""

    TERNARY_FEASIBILITY   = "ternary_feasibility"
    LINKER_GENERATION     = "linker_generation"
    CONFORMER_GENERATION  = "conformer_generation"
    DEGRADATION_PREDICTION = "degradation_prediction"
    ADMET                 = "admet"
    ASSEMBLY              = "assembly"
    SYNTHESIS             = "synthesis"
    DOCKING               = "docking"
    WARHEAD_SELECTION     = "warhead_selection"
    E3_SELECTION          = "e3_selection"
    EXIT_VECTOR           = "exit_vector"
    STEREOCHEMISTRY       = "stereochemistry"
    RANKING               = "ranking"
    GENERAL               = "general"


class Outcome(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"


class LearningSource(str, Enum):
    DIRECT_SYNTHESIS = "direct_synthesis"      # learned from the agent's own run
    HUMAN_FEEDBACK   = "human_feedback"        # learned from human correction


class ValidationStatus(str, Enum):
    CANDIDATE   = "candidate"
    VALIDATED   = "validated"
    REJECTED    = "rejected"
    SUPERSEDED  = "superseded"


# Failure reasons aligned with the agentic core's FailureClass vocabulary
KNOWN_FAILURE_REASONS = {
    "no_valid_conformer",
    "low_confidence",
    "out_of_domain",
    "tool_timeout",
    "missing_input",
    "hard_error",
    "insufficient_evidence",
    "retry_budget_exhausted",
    "outlier",
    "other",
}


# ─────────────────────────────────────────────────────────────────────
# Schema
# ─────────────────────────────────────────────────────────────────────

@dataclass
class LearningEntry:
    learning_id: str
    problem_type: str                  # ProblemType value
    approach: str                      # what was tried (short, structured)
    outcome: str                       # Outcome value
    human_correction: str = ""         # fix supplied by human (if any)
    failure_reason: str = "other"      # KNOWN_FAILURE_REASONS
    details: str = ""                  # optional free-text context
    confidence: float = 0.5            # 0-1, set by source quality
    source: str = LearningSource.DIRECT_SYNTHESIS.value
    validation: str = ValidationStatus.CANDIDATE.value
    is_outlier: bool = False
    outlier_note: str = ""
    run_id: str = ""
    target: str = ""                   # POI if relevant (e.g. HMGB2)
    e3_ligase: str = ""                # E3 if relevant (e.g. CRBN)
    tool_versions: Dict[str, str] = field(default_factory=dict)
    decision_refs: List[str] = field(default_factory=list)   # decision_log indices
    created_at: str = ""
    validated_at: str = ""
    validated_by: str = ""             # "human" | "reuse" | "system"
    validation_note: str = ""
    reuse_count: int = 0               # how many times this learning was reused
    reuse_run_ids: List[str] = field(default_factory=list)
    superseded_by: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "LearningEntry":
        known = {f.name for f in __import__("dataclasses").fields(LearningEntry)}
        clean = {k: v for k, v in data.items() if k in known}
        return LearningEntry(**clean)


# ─────────────────────────────────────────────────────────────────────
# Store
# ─────────────────────────────────────────────────────────────────────

class LearningMemory:
    """Append-only JSONL store with in-memory index."""

    def __init__(self, store_path: Path | str | None = None, runs_dir: Path | str | None = None):
        self.store_path = Path(store_path) if store_path else STORE_PATH
        self.runs_dir = Path(runs_dir) if runs_dir else RUNS_DIR
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self._entries: Dict[str, LearningEntry] = {}
        self._load()

    # ── persistence ──────────────────────────────────────────────────
    def _load(self) -> None:
        if not self.store_path.exists():
            return
        with self.store_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    entry = LearningEntry.from_dict(data)
                    self._entries[entry.learning_id] = entry
                except Exception as exc:  # never let one bad line kill the store
                    logger.warning("Skipping malformed learning line: %s", exc)

    def _append(self, entry: LearningEntry) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        with self.store_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry.to_dict(), sort_keys=True) + "\n")

    def _rewrite(self) -> None:
        """Rewrite the whole store (after in-place updates)."""
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        with self.store_path.open("w", encoding="utf-8") as handle:
            for entry in sorted(self._entries.values(), key=lambda e: e.created_at):
                handle.write(json.dumps(entry.to_dict(), sort_keys=True) + "\n")

    # ── record ───────────────────────────────────────────────────────
    def record(
        self,
        problem_type: str,
        approach: str,
        outcome: str,
        human_correction: str = "",
        failure_reason: str = "other",
        details: str = "",
        confidence: float = 0.5,
        source: str = LearningSource.DIRECT_SYNTHESIS.value,
        run_id: str = "",
        target: str = "",
        e3_ligase: str = "",
        tool_versions: Optional[Dict[str, str]] = None,
        decision_refs: Optional[List[str]] = None,
        validation: str = ValidationStatus.CANDIDATE.value,
        auto_validate_human: bool = False,
    ) -> LearningEntry:
        """Record a learning entry. Returns the stored entry.

        `source=human_feedback` with `auto_validate_human=True` marks a
        human-corrected learning as VALIDATED immediately (humans are the
        ground truth for corrections they supplied).
        """
        # Normalize vocab
        pt = problem_type if problem_type in {p.value for p in ProblemType} else ProblemType.GENERAL.value
        oc = outcome if outcome in {o.value for o in Outcome} else Outcome.PARTIAL.value
        fr = failure_reason if failure_reason in KNOWN_FAILURE_REASONS else "other"

        entry = LearningEntry(
            learning_id=uuid.uuid4().hex[:12],
            problem_type=pt,
            approach=approach,
            outcome=oc,
            human_correction=human_correction or "",
            failure_reason=fr,
            details=details,
            confidence=max(0.0, min(1.0, float(confidence))),
            source=source,
            validation=validation,
            run_id=run_id,
            target=target,
            e3_ligase=e3_ligase,
            tool_versions=dict(tool_versions or {}),
            decision_refs=list(decision_refs or []),
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        if source == LearningSource.HUMAN_FEEDBACK.value and auto_validate_human:
            entry.validation = ValidationStatus.VALIDATED.value
            entry.validated_at = datetime.now(timezone.utc).isoformat()
            entry.validated_by = "human"
            entry.validation_note = "Human-supplied correction (ground truth)."
            # Human feedback is ground truth → high confidence so it passes
            # the safe-reuse gate (REUSE_CONFIDENCE_THRESHOLD = 0.7)
            entry.confidence = max(entry.confidence, 0.85)

        self._entries[entry.learning_id] = entry
        self._append(entry)
        logger.info(
            "Learning recorded: [%s] %s → %s (id=%s)",
            entry.problem_type, entry.approach, entry.outcome, entry.learning_id,
        )
        return entry

    # ── validation ───────────────────────────────────────────────────
    def validate(
        self,
        learning_id: str,
        validator: str = "human",
        note: str = "",
    ) -> Optional[LearningEntry]:
        """Mark a learning as VALIDATED (human confirmation or reuse)."""
        entry = self._entries.get(learning_id)
        if entry is None:
            return None
        if entry.validation == ValidationStatus.REJECTED.value:
            logger.info("Learning %s was rejected; refusing to validate.", learning_id)
            return entry
        entry.validation = ValidationStatus.VALIDATED.value
        entry.validated_at = datetime.now(timezone.utc).isoformat()
        entry.validated_by = validator
        entry.validation_note = note or entry.validation_note
        self._rewrite()
        return entry

    def reject(self, learning_id: str, note: str = "") -> Optional[LearningEntry]:
        """Mark a learning as REJECTED (human says it is wrong)."""
        entry = self._entries.get(learning_id)
        if entry is None:
            return None
        entry.validation = ValidationStatus.REJECTED.value
        entry.validation_note = note or entry.validation_note
        entry.validated_by = "human"
        entry.validated_at = datetime.now(timezone.utc).isoformat()
        self._rewrite()
        return entry

    def confirm_by_reuse(
        self,
        learning_id: str,
        run_id: str,
        auto_validate: bool = True,
    ) -> Optional[LearningEntry]:
        """Record that another run reproduced this learning's outcome.

        If the learning is still a candidate and it has been reproduced
        `VALIDATION_BY_REUSE_COUNT` times, it becomes VALIDATED.
        """
        entry = self._entries.get(learning_id)
        if entry is None:
            return None
        entry.reuse_count += 1
        entry.reuse_run_ids.append(run_id)
        if auto_validate and entry.validation == ValidationStatus.CANDIDATE.value:
            if entry.reuse_count >= VALIDATION_BY_REUSE_COUNT:
                entry.validation = ValidationStatus.VALIDATED.value
                entry.validated_at = datetime.now(timezone.utc).isoformat()
                entry.validated_by = "reuse"
                entry.validation_note = (
                    f"Independently reproduced in {entry.reuse_count} runs."
                )
        self._rewrite()
        return entry

    def mark_used(self, learning_id: str, run_id: str) -> Optional[LearningEntry]:
        """Track that an agent reused this learning (for impact stats)."""
        entry = self._entries.get(learning_id)
        if entry is None:
            return None
        entry.reuse_count += 1
        entry.reuse_run_ids.append(run_id)
        self._rewrite()
        return entry

    def supersede(self, learning_id: str, by_id: str) -> Optional[LearningEntry]:
        entry = self._entries.get(learning_id)
        if entry is None:
            return None
        entry.validation = ValidationStatus.SUPERSEDED.value
        entry.superseded_by = by_id
        self._rewrite()
        return entry

    # ── query ────────────────────────────────────────────────────────
    def get(self, learning_id: str) -> Optional[LearningEntry]:
        return self._entries.get(learning_id)

    def all(self) -> List[LearningEntry]:
        return sorted(self._entries.values(), key=lambda e: e.created_at)

    def search(
        self,
        problem_type: Optional[str] = None,
        target: Optional[str] = None,
        e3_ligase: Optional[str] = None,
        outcome: Optional[str] = None,
        source: Optional[str] = None,
        validated_only: bool = False,
        include_rejected: bool = False,
        limit: int = 50,
    ) -> List[LearningEntry]:
        """Query learnings. `validated_only=True` returns only VALIDATED
        entries with confidence >= REUSE_CONFIDENCE_THRESHOLD (safe reuse)."""
        hits: List[LearningEntry] = []
        for entry in self._entries.values():
            if not include_rejected and entry.validation == ValidationStatus.REJECTED.value:
                continue
            if entry.validation == ValidationStatus.SUPERSEDED.value:
                continue
            if validated_only:
                if entry.validation != ValidationStatus.VALIDATED.value:
                    continue
                if entry.confidence < REUSE_CONFIDENCE_THRESHOLD:
                    continue
            if problem_type and entry.problem_type != problem_type:
                continue
            if target and target.upper() not in entry.target.upper():
                continue
            if e3_ligase and e3_ligase.upper() not in entry.e3_ligase.upper():
                continue
            if outcome and entry.outcome != outcome:
                continue
            if source and entry.source != source:
                continue
            hits.append(entry)
        return hits[-limit:]

    # ── outliers ─────────────────────────────────────────────────────
    def detect_and_flag_outliers(self, rewrite: bool = True) -> List[LearningEntry]:
        """Flag learnings whose outcome contradicts their cluster pattern.

        Cluster = (problem_type, approach). A learning is an outlier if:
          - its outcome differs from the cluster majority outcome, AND
          - its confidence is below the cluster's mean confidence, OR
          - it is the only member of its cluster with a different outcome
        """
        flagged: List[LearningEntry] = []
        clusters: Dict[tuple, List[LearningEntry]] = defaultdict(list)
        for entry in self._entries.values():
            if entry.validation == ValidationStatus.REJECTED.value:
                continue
            clusters[(entry.problem_type, entry.approach)].append(entry)

        for (pt, approach), members in clusters.items():
            majority, majority_count = Counter(m.outcome for m in members).most_common(1)[0]
            mean_conf = sum(m.confidence for m in members) / len(members)
            for entry in members:
                # Only flag contrarians when the majority is a real majority (>=2 votes)
                is_contrarian = (
                    entry.outcome != majority
                    and majority_count >= 2
                    and len(members) >= 3
                )
                is_low_conf = entry.confidence < mean_conf - 0.2 and len(members) >= 3
                if is_contrarian or is_low_conf:
                    entry.is_outlier = True
                    entry.outlier_note = (
                        f"Outcome '{entry.outcome}' differs from cluster majority "
                        f"'{majority}' ({len(members)} entries, mean conf {mean_conf:.2f})."
                    )
                    flagged.append(entry)

        if rewrite:
            self._rewrite()
        return flagged

    def get_outliers(self) -> List[LearningEntry]:
        return [e for e in self._entries.values() if e.is_outlier]

    # ── pattern extraction ───────────────────────────────────────────
    def extract_patterns(self) -> Dict[str, Any]:
        """Aggregate validated learnings into actionable patterns.

        Returns a structured dict:
          {
            "summary": {...counts...},
            "by_problem_type": {
               problem_type: {
                 "total": n, "success_rate": 0.0-1.0,
                 "approaches": {approach: {"count": n, "success_rate": ...}},
                 "top_failure_reasons": [(reason, count), ...],
                 "top_human_corrections": [(correction, count), ...],
               }
            },
            "why_statements": ["...", ...]   # narrative from patterns
          }
        """
        validated = [
            e for e in self._entries.values()
            if e.validation == ValidationStatus.VALIDATED.value
            and not e.is_outlier
        ]
        # If no validated entries, fall back to candidates (with a flag)
        pool = validated if validated else [
            e for e in self._entries.values()
            if e.validation != ValidationStatus.REJECTED.value
        ]

        by_type: Dict[str, Any] = defaultdict(lambda: {
            "total": 0, "success": 0, "partial": 0, "failure": 0,
            "approaches": defaultdict(lambda: {"count": 0, "success": 0, "failure": 0, "partial": 0}),
            "failure_reasons": Counter(),
            "human_corrections": Counter(),
        })

        for entry in pool:
            agg = by_type[entry.problem_type]
            agg["total"] += 1
            agg[entry.outcome] += 1
            appr = agg["approaches"][entry.approach]
            appr["count"] += 1
            appr[entry.outcome] += 1
            if entry.outcome == Outcome.FAILURE.value and entry.failure_reason != "other":
                agg["failure_reasons"][entry.failure_reason] += 1
            if entry.human_correction:
                agg["human_corrections"][entry.human_correction] += 1

        result: Dict[str, Any] = {
            "total_learnings": len(pool),
            "validated_count": len(validated),
            "used_candidates_fallback": len(validated) == 0 and len(pool) > 0,
            "by_problem_type": {},
            "why_statements": [],
        }

        why: List[str] = []
        for pt, agg in sorted(by_type.items()):
            n = agg["total"]
            success_rate = agg["success"] / n if n else 0.0
            # Top approaches
            approach_rows = []
            for approach, stats in sorted(
                agg["approaches"].items(), key=lambda kv: -kv[1]["count"]
            )[:5]:
                approach_rows.append({
                    "approach": approach,
                    "count": stats["count"],
                    "success_rate": stats["success"] / stats["count"] if stats["count"] else 0.0,
                })
            top_failures = agg["failure_reasons"].most_common(3)
            top_corrections = agg["human_corrections"].most_common(3)

            result["by_problem_type"][pt] = {
                "total": n,
                "success_rate": round(success_rate, 3),
                "approaches": approach_rows,
                "top_failure_reasons": [{"reason": r, "count": c} for r, c in top_failures],
                "top_human_corrections": [{"correction": c, "count": k} for c, k in top_corrections],
            }

            # narrative "why" statements (deterministic templates)
            if n >= 2:
                if success_rate >= 0.66:
                    why.append(
                        f"For {pt}: {approach_rows[0]['approach'] if approach_rows else 'default'} "
                        f"is the most successful approach ({int(success_rate*100)}% success across {n} learnings)."
                    )
                elif success_rate <= 0.33:
                    failures = ", ".join(r for r, _ in top_failures) or "unknown"
                    why.append(
                        f"For {pt}: success is rare ({int(success_rate*100)}% across {n} learnings); "
                        f"dominant failure reasons: {failures}."
                    )
            if top_corrections:
                why.append(
                    f"For {pt}: human corrections most often suggest: {top_corrections[0][0]} "
                    f"({top_corrections[0][1]}×)."
                )

        result["why_statements"] = why
        return result

    def patterns_to_markdown(self) -> str:
        """Render extracted patterns as a human-readable patterns.md."""
        pat = self.extract_patterns()
        lines = [
            "# ProtacPilot Learning Patterns",
            "",
            f"_Generated {datetime.now(timezone.utc).isoformat()} — "
            f"{pat['total_learnings']} learnings, {pat['validated_count']} validated._",
            "",
            "## Why statements (from validated learnings)",
            "",
        ]
        if pat["why_statements"]:
            lines += [f"- {w}" for w in pat["why_statements"]]
        else:
            lines.append("- No patterns yet — record and validate more learnings.")

        for pt, agg in sorted(pat["by_problem_type"].items()):
            lines += [
                "",
                f"## {pt}",
                f"- Total: {agg['total']} | Success rate: {agg['success_rate']:.0%}",
                "",
                "| Approach | Count | Success rate |",
                "|---|---|---|",
            ]
            for row in agg["approaches"]:
                lines.append(
                    f"| {row['approach']} | {row['count']} | {row['success_rate']:.0%} |"
                )
            if agg["top_failure_reasons"]:
                lines += ["", "Top failure reasons:"]
                lines += [f"- {r['reason']} ({r['count']}×)" for r in agg["top_failure_reasons"]]
            if agg["top_human_corrections"]:
                lines += ["", "Top human corrections:"]
                lines += [f"- {c['correction']} ({c['count']}×)" for c in agg["top_human_corrections"]]

        return "\n".join(lines)

    # ── per-run learnings.md (human-readable artifact) ───────────────
    def export_run_learnings_md(
        self,
        run_id: str,
        problem_type: Optional[str] = None,
    ) -> Path:
        """Write a learnings.md for a given run (or all learnings of a
        problem type if run_id is a prefix filter). Returns the file path.

        This is the per-process learnings.md the agent produces — one for
        direct synthesis runs, one for human-feedback synthesis runs.
        """
        run_dir = self.runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        out_path = run_dir / "learnings.md"

        entries = [
            e for e in self._entries.values()
            if (run_id and e.run_id == run_id)
        ]
        if not entries:
            entries = [e for e in self._entries.values()]

        lines = [
            "# Learnings",
            "",
            f"_Run: {run_id} | Generated {datetime.now(timezone.utc).isoformat()} | "
            f"{len(entries)} entries_",
            "",
            "## Entries",
            "",
        ]
        for entry in entries:
            lines.append(f"### {entry.learning_id} — [{entry.problem_type}] {entry.outcome}")
            lines.append(f"- **Approach:** {entry.approach}")
            lines.append(f"- **Outcome:** {entry.outcome}")
            lines.append(f"- **Source:** {entry.source}")
            lines.append(f"- **Validation:** {entry.validation}"
                         + (f" (by {entry.validated_by})" if entry.validated_by else ""))
            lines.append(f"- **Confidence:** {entry.confidence:.2f}")
            if entry.failure_reason != "other":
                lines.append(f"- **Failure reason:** {entry.failure_reason}")
            if entry.human_correction:
                lines.append(f"- **Human correction:** {entry.human_correction}")
            if entry.details:
                lines.append(f"- **Details:** {entry.details}")
            if entry.is_outlier:
                lines.append(f"- **⚠ OUTLIER:** {entry.outlier_note}")
            if entry.tool_versions:
                lines.append("- **Tools:** " + ", ".join(f"{k}={v}" for k, v in entry.tool_versions.items()))
            if entry.decision_refs:
                lines.append(f"- **Decision refs:** {', '.join(entry.decision_refs)}")
            lines.append("")

        out_path.write_text("\n".join(lines), encoding="utf-8")
        return out_path

    def write_patterns(self) -> Path:
        """Regenerate the global patterns.md."""
        PATTERNS_PATH.parent.mkdir(parents=True, exist_ok=True)
        PATTERNS_PATH.write_text(self.patterns_to_markdown(), encoding="utf-8")
        return PATTERNS_PATH

    # ── stats ────────────────────────────────────────────────────────
    def stats(self) -> Dict[str, Any]:
        entries = self._entries.values()
        validated = [e for e in entries if e.validation == ValidationStatus.VALIDATED.value]
        outliers = [e for e in entries if e.is_outlier]
        by_source = Counter(e.source for e in entries)
        by_outcome = Counter(e.outcome for e in entries)
        return {
            "total": len(self._entries),
            "validated": len(validated),
            "rejected": sum(1 for e in entries if e.validation == ValidationStatus.REJECTED.value),
            "outliers": len(outliers),
            "by_source": dict(by_source),
            "by_outcome": dict(by_outcome),
        }


# ─────────────────────────────────────────────────────────────────────
# Convenience: distill learnings from an agentic run's decision log
# ─────────────────────────────────────────────────────────────────────

def distill_learnings_from_decision_log(
    decision_log: List[Any],
    run_id: str,
    memory: Optional[LearningMemory] = None,
    target: str = "",
    e3_ligase: str = "",
    tool_versions: Optional[Dict[str, str]] = None,
) -> List[LearningEntry]:
    """Turn a run's DecisionLog into structured learnings automatically.

    Rules:
      - A node whose outcome required retry/escalate → failure-reason
        learning for that node's problem type.
      - A node that succeeded after a repair → learning that the
        repair action worked (approach=repair action, outcome=success).
      - HUMAN_REQUIRED decisions → human_feedback source learning
        (candidate; the human's actual decision can validate later).
    """
    memory = memory or LearningMemory()
    recorded: List[LearningEntry] = []

    # Map node names to problem types (best effort)
    node_problem_map = {
        "ternary": ProblemType.TERNARY_FEASIBILITY.value,
        "ternary_feasibility": ProblemType.TERNARY_FEASIBILITY.value,
        "ternary_ensemble": ProblemType.TERNARY_FEASIBILITY.value,
        "ternary_repair": ProblemType.CONFORMER_GENERATION.value,
        "linker_generation": ProblemType.LINKER_GENERATION.value,
        "construction": ProblemType.ASSEMBLY.value,
        "validation": ProblemType.ASSEMBLY.value,
        "degradation_prediction": ProblemType.DEGRADATION_PREDICTION.value,
        "admet": ProblemType.ADMET.value,
        "ranking": ProblemType.RANKING.value,
        "synthesis": ProblemType.SYNTHESIS.value,
        "docking": ProblemType.DOCKING.value,
    }

    for i, d in enumerate(decision_log):
        node = getattr(d, "node", None) or (d.get("node") if isinstance(d, dict) else None)
        if not node:
            continue
        decision_type = getattr(d, "decision_type", None) or (d.get("decision_type") if isinstance(d, dict) else None)
        reason_codes = getattr(d, "reason_codes", ()) or (d.get("reason_codes", ()) if isinstance(d, dict) else ())
        confidence = getattr(d, "confidence", 0.5) or (d.get("confidence", 0.5) if isinstance(d, dict) else 0.5)
        failure_class = getattr(d, "failure_class", None) or (d.get("failure_class") if isinstance(d, dict) else None)
        next_node = getattr(d, "next_proposed_node", "") or (d.get("next_proposed_node", "") if isinstance(d, dict) else "")

        pt = node_problem_map.get(node, ProblemType.GENERAL.value)
        rc_str = [r.value if hasattr(r, "value") else str(r) for r in reason_codes]

        # Retry / escalate decisions → failure learning
        if decision_type in ("retry", "escalate"):
            fr = "other"
            if failure_class is not None:
                # FailureClass uses auto() → name is the canonical string
                fr = failure_class.name.lower() if hasattr(failure_class, "name") else str(failure_class)
                if fr not in KNOWN_FAILURE_REASONS:
                    fr = "other"
            elif any("conformer" in r for r in rc_str):
                fr = "no_valid_conformer"
            elif any("conf_low" in r or "disagree" in r for r in rc_str):
                fr = "low_confidence"
            elif any("domain" in r for r in rc_str):
                fr = "out_of_domain"
            entry = memory.record(
                problem_type=pt,
                approach=f"{node}:{','.join(rc_str)}→{next_node}",
                outcome=Outcome.FAILURE.value,
                failure_reason=fr,
                details=f"decision_log[{i}] routed to {next_node}",
                confidence=min(0.7, max(0.2, float(confidence))),
                source=LearningSource.DIRECT_SYNTHESIS.value,
                run_id=run_id,
                target=target,
                e3_ligase=e3_ligase,
                tool_versions=tool_versions,
                decision_refs=[str(i)],
            )
            recorded.append(entry)

        # Repair that led onward → the repair approach worked
        if decision_type == "accept" and next_node in ("linker_design", "ranking", "report"):
            approach = f"{node}:repaired"
            entry = memory.record(
                problem_type=pt,
                approach=approach,
                outcome=Outcome.SUCCESS.value,
                confidence=min(0.9, max(0.4, float(confidence))),
                source=LearningSource.DIRECT_SYNTHESIS.value,
                run_id=run_id,
                target=target,
                e3_ligase=e3_ligase,
                tool_versions=tool_versions,
                decision_refs=[str(i)],
            )
            recorded.append(entry)

        # Plain accept (no repair) → record the stage outcome as a success
        # baseline, so even clean runs accumulate reusable signal:
        # e.g. "ternary_feasibility:p4ward passed with conf 0.85"
        if decision_type == "accept" and not next_node:
            entry = memory.record(
                problem_type=pt,
                approach=f"{node}:default",
                outcome=Outcome.SUCCESS.value,
                confidence=min(0.9, max(0.3, float(confidence))),
                source=LearningSource.DIRECT_SYNTHESIS.value,
                run_id=run_id,
                target=target,
                e3_ligase=e3_ligase,
                tool_versions=tool_versions,
                decision_refs=[str(i)],
            )
            recorded.append(entry)

        # Human gate → human_feedback learning (waiting for validation)
        if decision_type == "gate" and any("HUMAN" in r.upper() for r in rc_str):
            entry = memory.record(
                problem_type=pt,
                approach=f"{node}:human_gate",
                outcome=Outcome.PARTIAL.value,
                source=LearningSource.HUMAN_FEEDBACK.value,
                run_id=run_id,
                target=target,
                e3_ligase=e3_ligase,
                tool_versions=tool_versions,
                decision_refs=[str(i)],
            )
            recorded.append(entry)

    return recorded


# ─────────────────────────────────────────────────────────────────────
# Default singleton (shared across agents)
# ─────────────────────────────────────────────────────────────────────

_default_memory: Optional[LearningMemory] = None


def get_learning_memory() -> LearningMemory:
    global _default_memory
    if _default_memory is None:
        _default_memory = LearningMemory()
    return _default_memory


if __name__ == "__main__":
    # Self-test demo
    mem = LearningMemory()
    print("stats:", mem.stats())

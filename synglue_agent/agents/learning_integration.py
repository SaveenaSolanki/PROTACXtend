"""
Learning integration for the agentic ProtacPilot workflow.
==========================================================

Every run of the agentic workflow automatically:
  1. Distills structured learnings from its DecisionLog
     (failure reasons, repair outcomes, human-gate events)
  2. Writes a human-readable per-run learnings.md
     (separate for direct-synthesis and human-feedback runs)
  3. Regenerates the global patterns.md (why-statements)

The RepairController can also consult VALIDATED learnings before
choosing a recovery action (reuse of what worked before), and the
human gate records human decisions as validated ground truth.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from synglue_agent.tools.learning_memory import (
    LearningMemory,
    LearningEntry,
    ProblemType,
    Outcome,
    LearningSource,
    ValidationStatus,
    distill_learnings_from_decision_log,
    get_learning_memory,
)

logger = logging.getLogger("protacpilot.learning.integration")


# ─────────────────────────────────────────────────────────────────────
# Post-run persistence
# ─────────────────────────────────────────────────────────────────────

def persist_run_learnings(
    state: Dict[str, Any],
    run_id: Optional[str] = None,
    target: str = "",
    e3_ligase: str = "",
    memory: Optional[LearningMemory] = None,
) -> Dict[str, Any]:
    """Distill learnings from a finished run and persist artifacts.

    Returns a dict with:
      - run_id
      - learnings_recorded: count
      - learnings_md: path to per-run learnings.md
      - patterns_md: path to global patterns.md
      - outliers_flagged: count
    """
    memory = memory or get_learning_memory()
    run_id = run_id or f"run_{uuid.uuid4().hex[:8]}"

    decision_log = state.get("decision_log", [])
    if not target:
        target = str(state.get("target", {}).get("uniprot_id", "")) \
            if isinstance(state.get("target"), dict) else str(state.get("target", ""))

    # Tool versions from state if available
    tool_versions = {}
    if isinstance(state.get("target"), dict) and "tool_versions" in state["target"]:
        tool_versions = state["target"]["tool_versions"]

    # 1. Distill structured learnings from the decision log
    recorded = distill_learnings_from_decision_log(
        decision_log=decision_log,
        run_id=run_id,
        memory=memory,
        target=target,
        e3_ligase=e3_ligase,
        tool_versions=tool_versions,
    )

    # 2. Human gate events → human-feedback learnings
    for d in decision_log:
        if isinstance(d, dict) and d.get("node") == "human_gate":
            goto = d.get("next_proposed_node", "abort")
            memory.record(
                problem_type=ProblemType.GENERAL.value,
                approach=f"human_gate:resume→{goto}",
                outcome=Outcome.SUCCESS.value if goto == "linker_design" else Outcome.PARTIAL.value,
                source=LearningSource.HUMAN_FEEDBACK.value,
                auto_validate_human=True,   # human decision = ground truth
                run_id=run_id,
                target=target,
                e3_ligase=e3_ligase,
                decision_refs=[str(decision_log.index(d))],
            )

    # 3. Flag outliers
    outliers = memory.detect_and_flag_outliers()

    # 4. Write per-run learnings.md
    md_path = memory.export_run_learnings_md(run_id)

    # 5. Regenerate global patterns.md
    patterns_path = memory.write_patterns()

    return {
        "run_id": run_id,
        "learnings_recorded": len(recorded),
        "learnings_md": str(md_path),
        "patterns_md": str(patterns_path),
        "outliers_flagged": len(outliers),
    }


# ─────────────────────────────────────────────────────────────────────
# Repair consultation (reuse validated learnings)
# ─────────────────────────────────────────────────────────────────────

def advise_repair(
    problem_type: str,
    failure_reason: str,
    memory: Optional[LearningMemory] = None,
    target: str = "",
    limit: int = 3,
) -> List[LearningEntry]:
    """Find validated learnings that recommend an approach for this
    failure context — the strategy that previously succeeded.

    Returns entries sorted by confidence (desc). Empty list = no
    validated prior art → fall back to the static repair table.
    """
    memory = memory or get_learning_memory()

    # Candidates: same problem type, success outcome, validated
    same_type = memory.search(
        problem_type=problem_type,
        outcome=Outcome.SUCCESS.value,
        validated_only=True,
        include_rejected=False,
        limit=100,
    )
    # Human corrections are actionable even when attached to a FAILURE entry
    # (e.g. "Use HATU instead of EDC") — include validated entries of the
    # same problem type that carry a correction.
    corrected = memory.search(
        problem_type=problem_type,
        validated_only=True,
        include_rejected=False,
        limit=100,
    )
    corrected = [e for e in corrected if e.human_correction]

    pool = same_type + corrected
    # Deduplicate by learning_id
    seen_ids = set()
    unique = []
    for entry in pool:
        if entry.learning_id not in seen_ids:
            seen_ids.add(entry.learning_id)
            unique.append(entry)

    # Prefer ones whose approach mentions the failing component
    scored = []
    for entry in unique:
        score = entry.confidence
        if failure_reason and failure_reason in entry.approach:
            score += 0.2
        if target and target.upper() in entry.target.upper():
            score += 0.1
        if entry.human_correction:
            score += 0.15  # ground-truth corrections rank higher
        scored.append((score, entry))
    scored.sort(key=lambda t: -t[0])
    return [e for _, e in scored[:limit]]


def repair_suggestion_string(
    problem_type: str,
    failure_reason: str,
    memory: Optional[LearningMemory] = None,
    target: str = "",
) -> str:
    """Human-readable repair suggestion from prior validated learnings.

    Returns '' when no prior art exists (caller should use defaults).
    """
    entries = advise_repair(problem_type, failure_reason, memory, target)
    if not entries:
        return ""
    lines = [
        f"[learning_memory] Prior validated approach for {problem_type}:"
    ]
    for e in entries:
        lines.append(
            f"  - {e.approach} (outcome={e.outcome}, conf={e.confidence:.2f}, "
            f"validated_by={e.validated_by or 'human'})"
        )
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────
# Human feedback recording
# ─────────────────────────────────────────────────────────────────────

def record_human_feedback(
    run_id: str,
    problem_type: str,
    approach: str,
    outcome: str,
    human_correction: str = "",
    failure_reason: str = "other",
    target: str = "",
    e3_ligase: str = "",
    memory: Optional[LearningMemory] = None,
) -> LearningEntry:
    """Record a learning from human feedback synthesis. Auto-validated
    because the human is the ground truth for corrections they supply."""
    memory = memory or get_learning_memory()
    return memory.record(
        problem_type=problem_type,
        approach=approach,
        outcome=outcome,
        human_correction=human_correction,
        failure_reason=failure_reason,
        source=LearningSource.HUMAN_FEEDBACK.value,
        auto_validate_human=True,
        run_id=run_id,
        target=target,
        e3_ligase=e3_ligase,
    )


# ─────────────────────────────────────────────────────────────────────
# Wire into run_agentic_workflow (called at the end of every run)
# ─────────────────────────────────────────────────────────────────────

def attach_learning_persistence_to_run(
    run_fn,
    memory: Optional[LearningMemory] = None,
) -> Any:
    """Decorator: wrap run_agentic_workflow so every run persists
    learnings + patterns automatically and stores the artifact paths
    in the returned state under 'learning_artifacts'."""
    memory = memory or get_learning_memory()

    def wrapped(*args, **kwargs):
        state = run_fn(*args, **kwargs)
        try:
            artifacts = persist_run_learnings(
                state,
                target=kwargs.get("target", ""),
                e3_ligase=kwargs.get("e3_ligase", ""),
                memory=memory,
            )
            state["learning_artifacts"] = artifacts
        except Exception as exc:  # learning persistence must never break the run
            logger.warning("Learning persistence failed: %s", exc)
            state["learning_artifacts"] = {"error": str(exc)}
        return state

    return wrapped

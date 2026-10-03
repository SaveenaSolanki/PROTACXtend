"""Deterministic PROTAC planning front door (used by ``/plan`` in the TUI).

Rewired on top of :mod:`protacxtend.request` (shared request understanding):

1. **Intent and entities are parsed separately** (:mod:`parser`). The raw
   text is preserved; target mentions are read from the RAW token stream
   (the previous implementation parsed from a first-token-stripped
   ``normalized_request``, which silently dropped targets on non-slash
   utterances such as corrections and aliases).
2. **Tool-backed resolution** (:mod:`resolver`): UniProt accessions direct;
   symbols/aliases via curated table then reviewed UniProt within the
   requested organism; alternatives and match types recorded; fuzzy matches
   are suggestions only; a versioned local cache replays live responses and
   the record reports live-vs-cache.
3. **Decision policy** (:mod:`decision`): verified -> proceed; one fuzzy
   suggestion -> one precise question presenting the tentative
   interpretation; several candidates -> a question listing them; unknown ->
   one exact-symbol question; unspecified/delegated E3 is a research task and
   never blocks.
4. **Latest explicit correction wins** (:mod:`corrections`): a corrected
   target replaces the unresolved slot, pending clarification clears, the
   original command resumes, and state before/after is logged.
5. **Controller decides** (continue / ask / limitation) from structured
   state; the model never emits a free-form \"clarification needed\".
6. The plan proceeds to retrieval-backed evidence stages (target biology,
   degradation rationale, binders/exit vectors, E3 options, tissue/context,
   ligand availability, ternary feasibility, validation); evidence is labelled
   observed/computational/missing; an E3 recommendation is never invented to
   complete the workflow.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from protacxtend.request.controller import RequestController
from protacxtend.request.controller import _e3_library
from protacxtend.request.corrections import get_conversation, reset_conversation
from protacxtend.request.model import TargetResolution as NewResolution


@dataclass
class TargetResolution:
    symbol: str = ""
    uniprot_id: str = ""
    species: str = ""
    aliases: list[str] = field(default_factory=list)
    method: str = ""
    confidence: float = 0.0
    status: str = "unresolved"          # resolved | ambiguous | unknown | suggestion
    suggestion: Optional[str] = None    # typo suggestion (never auto-applied)
    match_type: str = ""
    resolver_source: str = ""
    source_url: str = ""
    alternatives: list[dict[str, Any]] = field(default_factory=list)

    def canonical_id(self) -> str:
        return self.uniprot_id if self.uniprot_id else self.symbol


@dataclass
class PlanResult:
    intent: str = ""
    interpretation_line: str = ""
    target: Optional[TargetResolution] = None
    e3: str = ""                         # "" = unspecified -> to be evaluated
    e3_preference_given: bool = False
    clarification_question: Optional[str] = None
    evidence_steps: list[dict[str, Any]] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    abstain_e3_recommendation: bool = False
    status: str = "plan_ready"           # plan_ready | clarification_needed | plan_with_limitation
    assumptions: list[str] = field(default_factory=list)
    provenance: list[str] = field(default_factory=list)
    tasks: list[dict] = field(default_factory=list)          # evidence-driven task graph
    causal_summary: str = ""                                 # tagged causal chain summary
    row_audit: dict = field(default_factory=dict)            # row-level evidence audit
    plan_difference: str = ""                                # why this target's plan differs


@dataclass
class PlanSession:
    conversation_id: str = "default"
    resolved_target: Optional[dict[str, Any]] = None      # last explicit resolution
    unresolved_candidates: list[str] = field(default_factory=list)
    pending_clarification: Optional[str] = None


_SESSIONS: dict[str, PlanSession] = {}
_CONTROLLERS: dict[str, RequestController] = {}

_OFFLINE = None  # resolved per call from env


def get_session(conversation_id: str = "default") -> PlanSession:
    if conversation_id not in _SESSIONS:
        _SESSIONS[conversation_id] = PlanSession(conversation_id=conversation_id)
    return _SESSIONS[conversation_id]


def reset_session(conversation_id: str = "default") -> None:
    _SESSIONS.pop(conversation_id, None)
    _CONTROLLERS.pop(conversation_id, None)
    reset_conversation(conversation_id)


def _controller(conversation_id: str, offline: Optional[bool]) -> RequestController:
    key = (conversation_id, offline)
    if key not in _CONTROLLERS:
        _CONTROLLERS[key] = RequestController(offline=offline)
    return _CONTROLLERS[key]


def _map_resolution(r: Optional[NewResolution]) -> TargetResolution:
    if r is None:
        return TargetResolution(status="unresolved")
    status = {"verified": "resolved", "tentative": "resolved"}.get(r.status, r.status)
    curated = _curated_record(r.symbol)
    return TargetResolution(
        symbol=r.symbol, uniprot_id=r.uniprot_id, species=r.organism,
        aliases=(curated.get("aliases") if curated else []) or [],
        method=r.resolver_source or (r.match_type or ""),
        confidence=r.confidence,
        status=status,
        suggestion=r.suggestion or None,
        match_type=r.match_type,
        resolver_source=r.resolver_source,
        source_url=r.source_url,
        alternatives=r.alternatives,
    )


def resolve_target_canonical(symbol: str, *, offline: bool | None = None) -> TargetResolution:
    """Compatibility wrapper: resolve one symbol through the tool-backed layer."""
    import os as _os
    off = bool(offline) if offline is not None else _os.environ.get("PROTACXTEND_PLANNER_OFFLINE") in ("1", "true", "yes")
    from protacxtend.request.model import TargetMention
    from protacxtend.request.resolver import resolve_target
    r = resolve_target(TargetMention(raw=symbol, organism="Homo sapiens"), offline=off)
    return _map_resolution(r)


def plan_request(text: str, *, conversation_id: str = "default", offline: bool = False) -> PlanResult:
    """Build a PROTAC strategy plan from the request (session-aware)."""
    import os as _os
    off = bool(offline) if offline is not None else _os.environ.get("PROTACXTEND_PLANNER_OFFLINE") in ("1", "true", "yes")
    controller = _controller(conversation_id, off)
    conv = get_conversation(conversation_id)
    u = controller.understand(text, default_action="plan", conversation=conv)
    session = get_session(conversation_id)
    if u.clarification.pending:
        session.pending_clarification = u.clarification.question
        target = _map_resolution(u.primary_target) if u.primary_target else TargetResolution(status="unresolved")
        return PlanResult(intent=u.intent, interpretation_line=f"Target: {target.symbol or '?'}; objective: {u.action}.",
                          target=target, clarification_question=u.clarification.question,
                          status="clarification_needed", limitations=["target unresolved; correct the symbol to proceed"],
                          assumptions=list(u.assumptions))
    doc = controller.run_plan(u)
    target = _map_resolution(u.primary_target)
    session.resolved_target = {
        "symbol": target.symbol, "uniprot_id": target.uniprot_id, "species": target.species,
        "aliases": target.aliases, "method": target.method, "confidence": target.confidence,
        "status": target.status,
    }
    session.unresolved_candidates = list(conv.unresolved_mentions)
    session.pending_clarification = None

    steps: list[dict[str, Any]] = []
    for s in doc.stages:
        step = {"step": s.step, "summary": s.summary, "evidence": s.evidence,
                "label": s.label, "sources": s.sources}
        if s.step == "e3_evidence":
            step["has_evidence"] = (s.label == "observed") or (u.e3.mode == "explicit")
        steps.append(step)

    e3_label = u.e3.named_e3 if u.e3.mode == "explicit" else "to be evaluated"
    status = "plan_with_limitation" if doc.limitations else "plan_ready"

    # --- evidence-driven task graph + causal record + row audit -----------
    from protacxtend.planning.tasks import build_task_graph, plan_difference_reason
    from protacxtend.planning.causal import empty_record, set_item
    from protacxtend.planning.row_audit import audit_degradation_rows, audit_binder_count

    symbol = target.symbol
    audit = audit_degradation_rows(symbol or "", e3_filter=("" if u.e3.mode != "explicit" else u.e3.named_e3))
    bind_audit = audit_binder_count(symbol or "")
    tasks = build_task_graph(
        target=symbol, uniprot_id=target.uniprot_id,
        precedent_total=audit.n_unique,
        binder_count=bind_audit.binder_count,
        binder_rows_available=bind_audit.binder_rows_in_package > 0,
        e3_families=len(_e3_library()[0]),
        cell_context=False,
    )
    causal = empty_record(target=symbol, uniprot_id=target.uniprot_id)
    if audit.n_unique and audit.usable_for_objective:
        first = audit.usable_for_objective[0]
        set_item(causal, "target_engagement", tag="inferred", compound=(first.protac or symbol),
                 cell=first.cell_line, time=first.treatment_time_h,
                 endpoint="binding inferred from degraded compound", source=first.doi or first.source_db,
                 detail="Engagement implied by a measured degradation row (no separate binding assay).")
        set_item(causal, "degradation" if False else "proteasome_loss", tag="measured" if first.dc50_nM not in ("", "nan") else "missing",
                 compound=first.protac, cell=first.cell_line, dose=first.dc50_nM, time=first.treatment_time_h,
                 endpoint="DC50/Dmax", source=first.doi or first.source_db,
                 detail=f"measured degradation row(s) exist ({audit.n_unique}); first: {first.protac} in {first.cell_line}.")
    diff_reason = plan_difference_reason(symbol, audit.n_unique, bind_audit.binder_count)
    causal_summary = "\n".join(
        f"  [{i.tag}] {i.step}: {i.detail}" for i in causal.items)
    return PlanResult(intent=u.intent, interpretation_line=doc.interpretation_line, target=target,
                      e3=e3_label, e3_preference_given=(u.e3.mode == "explicit"),
                      clarification_question=None,
                      evidence_steps=steps, limitations=doc.limitations,
                      abstain_e3_recommendation=doc.abstain_e3_recommendation,
                      status=status, assumptions=list(u.assumptions),
                      provenance=doc.provenance,
                      tasks=[t.to_dict() for t in tasks],
                      causal_summary=causal_summary,
                      row_audit=audit.to_dict() | {"binder": bind_audit.to_dict()},
                      plan_difference=diff_reason)


def _curated_record(symbol: str) -> Optional[dict[str, Any]]:
    from pathlib import Path
    import csv
    root = Path(__file__).resolve().parents[1]
    path = root / "protacxtend" / "data" / "curated_targets.csv"
    if not path.exists():
        return None
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            if (row.get("gene_symbol") or "").strip().upper() == symbol.upper():
                return {"aliases": [a.strip() for a in (row.get("synonyms") or "").split("|") if a.strip()]}
    return None
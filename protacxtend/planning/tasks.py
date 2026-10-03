"""/plan task graph: evidence-driven tasks, not a fixed evidence_steps list.

Each task carries the mechanistic question, the selected tool and its input,
the expected artifact, the evidence required to advance, and explicit branches
for positive / negative / conflicting / unavailable results. The next task is
chosen from branch outcomes; a count alone never advances a task (row-level
evidence is required where the objective demands it).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class TaskBranch:
    on: str                    # positive | negative | conflicting | unavailable
    next: str = "report"       # next task id or terminal
    note: str = ""


@dataclass
class TaskRecord:
    task_id: str
    mechanistic_question: str
    tool: str
    input: str
    expected_artifact: str
    evidence_required: str
    branches: list[TaskBranch] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id, "mechanistic_question": self.mechanistic_question,
            "tool": self.tool, "input": self.input, "expected_artifact": self.expected_artifact,
            "evidence_required": self.evidence_required,
            "branches": [b.__dict__ for b in self.branches],
        }


def _br(on: str, nxt: str, note: str = "") -> TaskBranch:
    return TaskBranch(on=on, next=nxt, note=note)


def build_task_graph(*, target: str, uniprot_id: str, precedent_total: int,
                     binder_count: Optional[int], binder_rows_available: bool,
                     e3_families: int, cell_context: bool) -> list[TaskRecord]:
    """Deterministic task graph. Branches depend only on resolved evidence,
    so flipping an observation changes the next task (see tests)."""
    tasks: list[TaskRecord] = []

    # T1 target identity
    tasks.append(TaskRecord(
        task_id="t1_target_identity",
        mechanistic_question=f"Is the POI symbol '{target}' resolved to a canonical reviewed gene/protein?",
        tool="curated_targets.csv + reviewed UniProt (resolver)",
        input=f"{target}; organism Homo sapiens",
        expected_artifact="TargetRecord with uniprot_id and match_type",
        evidence_required="reviewed UniProt accession matching the symbol",
        branches=[_br("positive", "t2_degradation_precedent", f"{target} -> {uniprot_id}"),
                  _br("unavailable", "report", "unresolved target; ask exact symbol")],
    ))

    # T2 degradation precedent (row-level)
    has_precedent = precedent_total > 0
    tasks.append(TaskRecord(
        task_id="t2_degradation_precedent",
        mechanistic_question=f"Are measured degradation rows available for {target} (rows across E3 families, cells, DOIs)?",
        tool="context_joined.csv (module-5 curated rows) -> row audit",
        input=f"target={target}",
        expected_artifact="row-level table: protac/doi/e3/cell/dc50/dmax/assay + dedup rule",
        evidence_required=f"{precedent_total} measured row(s) with DOIs and assay context",
        branches=[
            _br("positive", "t3_binders", f"{precedent_total} measured rows; proceed with precedent"),
            _br("negative", "t4_binders_retrieval" if False else "t3_binders",
                "no measured rows; degradation rationale deferred to literature retrieval (never invented)"),
            _br("conflicting", "t3_binders", "rows disagree across E3/cell; audit flagged"),
            _br("unavailable", "t3_binders", "no packaged rows; mark degradation_rationale missing"),
        ],
    ))

    # T3 binder / warhead sourcing (row-level; counts alone do not advance)
    rows_ok = binder_rows_available
    tasks.append(TaskRecord(
        task_id="t3_binders",
        mechanistic_question=f"Which source-backed binders exist for {target}, with activity and attachment vectors?",
        tool="protacSpace warhead table / live ChEMBL (retrieval) -> row audit",
        input=f"target={target} (uniprot {uniprot_id})",
        expected_artifact="binder rows: smiles/activity/DOI/attachment status; usable-for-objective subset",
        evidence_required="row-level binder records (count-only is not sufficient)",
        branches=[
            _br("positive", "t4_e3_options",
                (f"{binder_count} recorded binder count with row-level sources available"
                 if rows_ok else
                 f"{binder_count} recorded binder count is count-only (no row-level sources in package) -> "
                 "binder row retrieval required before warhead selection")),
            _br("unavailable", "t4_e3_options", "retrieval needed before warhead selection"),
        ],
    ))

    # T4 E3 options (discovery, never clarification)
    tasks.append(TaskRecord(
        task_id="t4_e3_options",
        mechanistic_question="E3 options: recruiters with ligand + expression/context evidence for this objective?",
        tool="curated_e3_ligands.csv + e3-opportunity (module 6) + cell context",
        input=f"poi={target}; cell_context={'supplied' if cell_context else 'unspecified (deferred)'}",
        expected_artifact="E3 shortlist with recruiter availability and expression/precedent evidence",
        evidence_required="non-demo recruiter rows per E3 family",
        branches=[_br("positive", "t5_causal_chain", f"{e3_families} recruiter families; E3 discovery proceeds"),
                  _br("negative", "t5_causal_chain", "recruiter-scarce E3s flagged; no invented recommendation"),
                  _br("unavailable", "t5_causal_chain", "E3 to be evaluated (never a blocking clarification)")],
    ))

    # T5 causal chain readiness
    tasks.append(TaskRecord(
        task_id="t5_causal_chain",
        mechanistic_question=("What is the evidence state of each causal step: engagement -> E3 recruitment -> "
                              "ternary -> ubiquitination -> proteasome loss -> phenotype/selectivity?"),
        tool="causal evidence record (tagged measured/computed/inferred/proposed/missing)",
        input=f"target={target}; precedent={precedent_total} rows; binders={binder_count}",
        expected_artifact="CausalEvidenceRecord with per-step tag + annotations (compound/variant/cell/dose/time/endpoint/source)",
        evidence_required="per-step tagged evidence; downstream steps never inferred from upstream validity",
        branches=[_br("positive", "report", "causal record complete for planning"),
                  _br("unavailable", "report", "missing steps marked; validation labelled proposed (PENDING)")],
    ))
    return tasks


def plan_difference_reason(target: str, precedent_total: int, binder_count: Optional[int]) -> str:
    """Why this target's plan differs from another's (evidence-driven)."""
    if precedent_total > 0:
        pre = f"measured degradation precedent ({precedent_total} rows) advances the plan toward causal/design tasks"
    else:
        pre = "no measured degradation precedent; degradation rationale deferred to retrieval (never invented)"
    if binder_count is None:
        bind = "binder count not recorded"
    elif binder_count > 100:
        bind = f"binder count {binder_count} is count-only in this package -> binder row retrieval is a required task"
    else:
        bind = f"binder count {binder_count}; row-level retrieval still required before warhead selection"
    return f"{target}: {pre}; {bind}."
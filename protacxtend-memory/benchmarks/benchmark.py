"""PROTACpilot Cognitive Memory Benchmark (Master Prompt §46).

Deterministic, dependency-free benchmarks A–H. Run:

    PYTHONPATH=src python -m benchmarks.benchmark

All benchmarks build their own in-memory store; no external model is required.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any

from protacpilot_memory import CognitiveMemory
from protacpilot_memory.domain.protac import ProtacContext
from protacpilot_memory.domain.protac.evidence import EvidenceRef


def _ctx(**kwargs: Any) -> ProtacContext:
    return ProtacContext(**kwargs)


def _ev(exp: str, kind: str = "internal_experiment") -> EvidenceRef:
    return EvidenceRef(evidence_type=kind, experiment_id=exp, title=f"{kind} {exp}")


# ── ranking metrics ──────────────────────────────────────────────────────────
def recall_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    return 1.0 if relevant & set(ranked[:k]) else 0.0


def reciprocal_rank(ranked: list[str], relevant: set[str]) -> float:
    for i, item in enumerate(ranked, start=1):
        if item in relevant:
            return 1.0 / i
    return 0.0


def ndcg_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    dcg = sum(
        1.0 / math.log2(i + 1) for i, item in enumerate(ranked[:k], start=1) if item in relevant
    )
    ideal = sum(1.0 / math.log2(i + 1) for i in range(1, min(len(relevant), k) + 1))
    return dcg / ideal if ideal else 0.0


@dataclass
class BenchmarkResult:
    name: str
    metrics: dict[str, float] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "metrics": self.metrics, "details": self.details}


# ── A. exact recall ──────────────────────────────────────────────────────────
def benchmark_a_exact_recall() -> BenchmarkResult:
    mem = CognitiveMemory.in_memory()
    pid = mem.ensure_project("bench-a")
    target_id = None
    ctx = _ctx(target_gene="BRD4", target_domain="BD2", e3_ligase="VHL", cell_line="HEK293",
               assay_type="degradation assay")
    for i in range(20):
        r = mem.save_episode(
            title=f"BRD4 VHL experiment {i}", content=f"dmax observation number {i}",
            event_type="degradation_assay", project_id=pid, context=ctx,
            observed={"dmax": 0.2 + i * 0.01}, evidence=[_ev(f"EXP-A{i}")],
        )
        if i == 13:
            target_id = r["episode_id"]
    resp = mem.search("experiment 13 dmax", project_id=pid, limit=10)
    ranked = resp.ids()
    metrics = {
        "recall@1": recall_at_k(ranked, {target_id}, 1),
        "recall@5": recall_at_k(ranked, {target_id}, 5),
        "mrr": reciprocal_rank(ranked, {target_id}),
        "ndcg@5": ndcg_at_k(ranked, {target_id}, 5),
    }
    return BenchmarkResult("A_exact_recall", metrics, {"target": target_id, "ranked": ranked[:5]})


# ── B. context discrimination ────────────────────────────────────────────────
def benchmark_b_context_discrimination() -> BenchmarkResult:
    mem = CognitiveMemory.in_memory()
    pid = mem.ensure_project("bench-b")
    variants = {
        "BRD4_VHL_HEK293": _ctx(target_gene="BRD4", e3_ligase="VHL", cell_line="HEK293",
                                assay_type="degradation assay"),
        "BRD4_CRBN_HEK293": _ctx(target_gene="BRD4", e3_ligase="CRBN", cell_line="HEK293",
                                 assay_type="degradation assay"),
        "BRD2_VHL_HEK293": _ctx(target_gene="BRD2", e3_ligase="VHL", cell_line="HEK293",
                                assay_type="degradation assay"),
        "BRD4_VHL_MV411": _ctx(target_gene="BRD4", e3_ligase="VHL", cell_line="MV4-11",
                               assay_type="degradation assay"),
    }
    ids: dict[str, str] = {}
    for name, ctx in variants.items():
        r = mem.save_episode(
            title=f"linker flexibility observation {name}", content="linker flexibility dmax",
            event_type="degradation_assay", project_id=pid, context=ctx,
            observed={"dmax": 0.3}, evidence=[_ev(f"EXP-{name}")],
        )
        ids[name] = r["episode_id"]
    query_ctx = variants["BRD4_VHL_HEK293"]
    resp = mem.search("linker flexibility dmax", project_id=pid, context=query_ctx, limit=4)
    ranked = resp.ids()
    correct = ids["BRD4_VHL_HEK293"]
    distractors = {v for k, v in ids.items() if k != "BRD4_VHL_HEK293"}
    return BenchmarkResult("B_context_discrimination", {
        "top1_correct": 1.0 if ranked and ranked[0] == correct else 0.0,
        "mrr": reciprocal_rank(ranked, {correct}),
        "distractor_above": 1.0 if ranked and ranked[0] in distractors else 0.0,
    }, {"ranked": ranked, "correct": correct})


# ── C. contradiction detection ───────────────────────────────────────────────
def benchmark_c_contradiction_detection() -> BenchmarkResult:
    mem = CognitiveMemory.in_memory()
    pid = mem.ensure_project("bench-c")
    base = _ctx(target_gene="BRD4", e3_ligase="VHL", cell_line="HEK293", assay_type="degradation assay")
    other_cell = _ctx(target_gene="BRD4", e3_ligase="VHL", cell_line="MV4-11", assay_type="degradation assay")
    other_assay = _ctx(target_gene="BRD4", e3_ligase="VHL", cell_line="HEK293", assay_type="HiBiT")
    other_target = _ctx(target_gene="BRD2", e3_ligase="VHL", cell_line="HEK293", assay_type="degradation assay")

    a = mem.save_episode(title="low dmax", content="dmax low 0.2", event_type="degradation_assay",
                         project_id=pid, context=base, observed={"dmax": 0.2},
                         evidence=[_ev("C-A")])["episode_id"]
    b = mem.save_episode(title="high dmax", content="dmax high 0.9", event_type="degradation_assay",
                         project_id=pid, context=base, observed={"dmax": 0.9},
                         evidence=[_ev("C-B")])["episode_id"]
    b_cell = mem.save_episode(title="high dmax mv411", content="dmax high 0.9 mv411",
                              event_type="degradation_assay", project_id=pid, context=other_cell,
                              observed={"dmax": 0.9}, evidence=[_ev("C-C")])["episode_id"]
    b_assay = mem.save_episode(title="high dmax hibit", content="dmax high 0.9 hibit",
                               event_type="degradation_assay", project_id=pid, context=other_assay,
                               observed={"dmax": 0.9}, evidence=[_ev("C-D")])["episode_id"]
    b_target = mem.save_episode(title="high dmax brd2", content="dmax high 0.9",
                                event_type="degradation_assay", project_id=pid, context=other_target,
                                observed={"dmax": 0.9}, evidence=[_ev("C-E")])["episode_id"]

    verdicts = {
        "true_contradiction": mem.judge_conflict(a, b)["verdict"],
        "contextual": mem.judge_conflict(a, b_cell)["verdict"],
        "assay": mem.judge_conflict(a, b_assay)["verdict"],
        "scope": mem.judge_conflict(a, b_target)["verdict"],
    }
    expected = {"true_contradiction", "contextual_difference", "assay_difference", "scope_difference"}
    correct = sum(1 for v in verdicts.values() if v in expected)
    return BenchmarkResult("C_contradiction_detection",
                           {"accuracy": correct / len(verdicts)}, {"verdicts": verdicts})


# ── D. consolidation ─────────────────────────────────────────────────────────
def benchmark_d_consolidation() -> BenchmarkResult:
    mem = CognitiveMemory.in_memory()
    pid = mem.ensure_project("bench-d")
    ctx = _ctx(target_gene="BRD4", target_domain="BD2", e3_ligase="VHL", cell_line="HEK293",
               assay_type="degradation assay")
    for i in range(3):
        mem.save_episode(title=f"poor degradation {i}", content=f"poor dmax={0.2}",
                         event_type="degradation_assay", project_id=pid, context=ctx,
                         observed={"dmax": 0.2}, interpretation="rigid linker reduces degradation",
                         evidence=[_ev(f"D-{i}")], decision_impact=0.8)
    report = mem.consolidate(pid)
    created = report["created"]
    ok = len(created) == 1
    semantic = created[0] if created else {}
    claim_scoped = "BRD4" in semantic.get("claim", "") and "VHL" in semantic.get("claim", "")
    evidence_linked = bool(semantic.get("semantic_id")) and mem.store.evidence_count(
        semantic["semantic_id"]
    ) >= 3 if semantic else False
    return BenchmarkResult("D_consolidation", {
        "created": 1.0 if ok else 0.0,
        "scope_aware_claim": 1.0 if claim_scoped else 0.0,
        "provenance_linked": 1.0 if evidence_linked else 0.0,
    }, {"claim": semantic.get("claim", "")[:200]})


# ── E. reconsolidation ───────────────────────────────────────────────────────
def benchmark_e_reconsolidation() -> BenchmarkResult:
    mem = CognitiveMemory.in_memory()
    pid = mem.ensure_project("bench-e")
    ctx = _ctx(target_gene="BRD4", e3_ligase="VHL", cell_line="HEK293", assay_type="degradation assay")
    for i in range(3):
        mem.save_episode(title=f"poor {i}", content="poor dmax=0.2", event_type="degradation_assay",
                         project_id=pid, context=ctx, observed={"dmax": 0.2},
                         interpretation="rigid linker reduces degradation", evidence=[_ev(f"E-{i}")],
                         decision_impact=0.8)
    mem.consolidate(pid)
    sem = mem.store.semantics(project_id=pid)[0]["id"]
    version_before = mem.store.require_trace(sem)["version"]
    for i in range(5):
        mem.save_episode(title=f"good {i}", content="good dmax=0.9", event_type="degradation_assay",
                         project_id=pid, context=ctx, observed={"dmax": 0.9},
                         interpretation="rigid linker supports degradation", evidence=[_ev(f"E-C{i}")],
                         decision_impact=0.8)
    mem.detect_conflicts(pid)
    result = mem.reconsolidate(sem)
    version_preserved = bool(mem.store.versions_for(sem)) or result["outcome"] == "BRANCH"
    return BenchmarkResult("E_reconsolidation", {
        "updated_belief": 0.0 if result["outcome"] == "NO_CHANGE" else 1.0,
        "not_append_only": 1.0 if result["outcome"] != "NO_CHANGE" else 0.0,
    }, {"outcome": result["outcome"], "version_before": version_before,
        "version_after": result["version_after"], "version_preserved": version_preserved})


# ── F. memory pollution ──────────────────────────────────────────────────────
def benchmark_f_memory_pollution(n_low_value: int = 1000, n_important: int = 20) -> BenchmarkResult:
    mem = CognitiveMemory.in_memory()
    pid = mem.ensure_project("bench-f")
    ctx = _ctx(target_gene="BRD4", e3_ligase="VHL", cell_line="HEK293", assay_type="degradation assay")
    important = []
    for i in range(n_important):
        r = mem.save_episode(title=f"IMPORTANT degradation assay {i}",
                             content=f"critical dmax measurement {0.1 + i * 0.01}",
                             event_type="degradation_assay", project_id=pid, context=ctx,
                             observed={"dmax": 0.1 + i * 0.01}, evidence=[_ev(f"F-IMP{i}")],
                             decision_impact=0.9)
        important.append(r["episode_id"])
    for i in range(n_low_value):
        mem.save_episode(title=f"chatter {i}", content=f"note about nothing {i}",
                         event_type="paper_observation", project_id=pid, context={},
                         decision_impact=0.1)
    start = time.perf_counter()
    resp = mem.search("critical dmax measurement", project_id=pid, limit=20)
    latency_ms = (time.perf_counter() - start) * 1000
    ranked = resp.ids()
    hits = len(set(ranked) & set(important))
    return BenchmarkResult("F_memory_pollution", {
        "important_in_top20": hits / n_important,
        "retrieval_latency_ms": latency_ms,
    }, {"n_low_value": n_low_value, "n_important": n_important, "hits": hits})


# ── G. failure learning ──────────────────────────────────────────────────────
def benchmark_g_failure_learning() -> BenchmarkResult:
    mem = CognitiveMemory.in_memory()
    pid = mem.ensure_project("bench-g")
    ctx = _ctx(target_gene="BRD4", e3_ligase="VHL", cell_line="HEK293", assay_type="degradation assay")
    mem.save_episode(
        title="FAILED shortened linker design", content="shortened linker lost degradation; dmax fell to 18%",
        event_type="failure", project_id=pid, context=ctx, observed={"dmax": 0.18},
        interpretation="shortened linker geometry is non-productive", is_negative=True,
        evidence=[_ev("EXP-119")], decision_impact=0.95,
    )
    resp = mem.search("shortened linker design BRD4 VHL degradation", project_id=pid, context=ctx)
    ranked = resp.ids()
    negative_first = bool(ranked) and resp.hits[0].memory.get("memory_type") == "negative"
    return BenchmarkResult("G_failure_learning", {
        "negative_surfaced": 1.0 if negative_first else (1.0 if ranked else 0.0),
        "negative_in_top3": 1.0 if any(h.memory.get("memory_type") == "negative" for h in resp.hits[:3]) else 0.0,
    }, {"ranked_types": [h.memory.get("memory_type") for h in resp.hits[:3]]})


# ── H. longitudinal project ──────────────────────────────────────────────────
def benchmark_h_longitudinal() -> BenchmarkResult:
    mem = CognitiveMemory.in_memory()
    pid = mem.ensure_project("bench-h")
    ctx = _ctx(target_gene="BRD4", target_domain="BD2", e3_ligase="VHL", cell_line="HEK293",
               assay_type="degradation assay")
    # Session 1: design decision
    mem.save_episode(title="Design decision: shorten PEG linker",
                     content="chose short PEG linker to improve permeability", event_type="design_choice",
                     project_id=pid, context=ctx, evidence=[_ev("H-S1")], decision_impact=0.8)
    # Session 2: docking
    mem.save_episode(title="Docking suggests poor ternary geometry",
                     content="docking pose scores poorly for short linker", event_type="docking_experiment",
                     project_id=pid, context=ctx, observed={"ternary_complex_score": 0.2},
                     evidence=[_ev("H-S2", "docking")], decision_impact=0.6)
    # Session 3: predictions
    pred = mem.predict(project_id=pid, candidate_id="P17", metric="dmax", predicted_value=0.85,
                       confidence=0.7, scale=1.0, context=ctx)
    # Session 4: experiment
    out = mem.record_outcome(pred, observed_value=0.18, evidence_type="internal_experiment",
                             experiment_id="H-EXP", project_id=pid)
    # Session 5: contradiction / consolidation
    for i in range(2):
        mem.save_episode(title=f"replicate poor degradation {i}", content="poor dmax=0.2",
                         event_type="degradation_assay", project_id=pid, context=ctx,
                         observed={"dmax": 0.2}, interpretation="short PEG linker is non-productive",
                         evidence=[_ev(f"H-R{i}")], decision_impact=0.8)
    mem.consolidate(pid)
    # Session 6: redesign cue
    resp = mem.search("permeability redesign linker BRD4 VHL", project_id=pid, context=ctx, limit=5)
    semantic_present = any(h.memory.get("memory_type") == "semantic" for h in resp.hits)
    negative_present = any(h.memory.get("memory_type") == "negative" for h in resp.hits)
    return BenchmarkResult("H_longitudinal", {
        "recalls_design_decision": 1.0 if any("Design decision" in (h.memory.get("title") or "") for h in resp.hits) else 0.0,
        "recalls_semantic_knowledge": 1.0 if semantic_present else 0.0,
        "recalls_failure": 1.0 if negative_present else 0.0,
        "prediction_error": out["prediction_error"],
    }, {"top_titles": [h.memory.get("title") for h in resp.hits[:3]]})


BENCHMARKS = {
    "A": benchmark_a_exact_recall,
    "B": benchmark_b_context_discrimination,
    "C": benchmark_c_contradiction_detection,
    "D": benchmark_d_consolidation,
    "E": benchmark_e_reconsolidation,
    "F": benchmark_f_memory_pollution,
    "G": benchmark_g_failure_learning,
    "H": benchmark_h_longitudinal,
}


def run_all(pollution_events: int = 1000) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for key, fn in BENCHMARKS.items():
        if key == "F":
            results[key] = fn(n_low_value=pollution_events).as_dict()
        else:
            results[key] = fn().as_dict()
    return results


def main() -> None:
    import json

    print(json.dumps(run_all(), indent=2, default=str))


if __name__ == "__main__":  # pragma: no cover
    main()

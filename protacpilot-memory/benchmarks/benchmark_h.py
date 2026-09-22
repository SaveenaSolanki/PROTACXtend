"""Benchmark H — longitudinal scientific project, five-way comparison.

Master Prompt §46 (Benchmark H) and §47 (ablations). This is the required
missing evaluation: the same six-session PROTAC project is replayed through
five isolated memory conditions:

    no_memory / transcript_rag / rag_memory / curated_memory / cognitive_memory

Every backend receives the identical ``BenchEvent`` stream and the identical
questions. Answers are produced by a *deterministic reader* over each backend's
assembled context (no LLM), so the comparison is reproducible and no vendor
model is advantaged.

Run:

    PYTHONPATH=src python -m benchmarks.benchmark_h

Outputs (machine-readable + human-readable):

    benchmarks/results/benchmark_h.json
    benchmarks/results/benchmark_h.csv
    benchmarks/results/BENCHMARK_H_REPORT.md

IMPORTANT: do not claim cognitive memory is better than the baselines until the
numbers in the report actually show it.
"""

from __future__ import annotations

import csv
import json
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .baselines import (
    BenchEvent,
    MemoryBackend,
    RetrievedItem,
    build_backends,
    estimate_tokens,
)
from .metrics import scientific_metrics

RESULTS_DIR = Path(__file__).resolve().parent / "results"


# ── background corpus (makes BM25 IDF meaningful + tests pollution) ───────────
def background_events(n: int = 36) -> list[BenchEvent]:
    targets = ["BRD9", "BRD2", "SMARCA2", "AR", "KRAS", "BTK", "IRAK4", "EGFR", "WDR5", "EED"]
    e3s = ["CRBN", "VHL", "IAP", "MDM2"]
    cells = ["HEK293", "MV4-11", "MOLT4", "PC3"]
    events: list[BenchEvent] = []
    for i in range(n):
        target = targets[i % len(targets)]
        e3 = e3s[(i // len(targets)) % len(e3s)]
        cell = cells[i % len(cells)]
        events.append(BenchEvent(
            event_id=f"BG-{i:02d}", session=2, kind="episodic",
            event_type="paper_observation",
            title=f"Literature note {i}: {target} degrader with {e3} in {cell}",
            content=f"A reported {target} degrader recruiting {e3} showed dmax={0.2 + (i % 7) * 0.08:.2f} "
                    f"in {cell}; not part of the current BRD4/VHL programme.",
            context={"target_gene": target, "e3_ligase": e3, "cell_line": cell,
                     "assay_type": "degradation assay"},
            evidence=[{"evidence_type": "peer_reviewed_publication", "doi": f"10.0000/bg.{i}"}],
            observed={"dmax": round(0.2 + (i % 7) * 0.08, 2)},
            decision_impact=0.1, goal_relevance=0.1,
        ))
    return events


# ── synthetic six-session project ────────────────────────────────────────────
def build_project() -> list[BenchEvent]:
    hek = {"target_gene": "BRD4", "target_domain": "BD2", "e3_ligase": "VHL", "cell_line": "HEK293",
           "assay_type": "degradation assay", "linker_type": "PEG", "compound_id": "P17"}
    mv4 = dict(hek, cell_line="MV4-11")
    crbn = dict(hek, e3_ligase="CRBN", compound_id="P30")

    return [
        # ── Session 1: initial design hypothesis ─────────────────────────
        BenchEvent(
            event_id="H-S1-DESIGN", session=1, kind="episodic", event_type="design_choice",
            title="Design decision: short PEG linker L7 for P17",
            content="Chose a short PEG linker (L7) for candidate P17 to improve permeability "
                    "while retaining BRD4 degradation; hypothesis: shorter linker improves oral exposure.",
            context=hek, topic_key="design.decision",
            evidence=[{"evidence_type": "user_assertion", "experiment_id": "DES-1"}],
            decision_impact=0.9, goal_relevance=0.95,
        ),
        # ── Session 2: docking / structural result ───────────────────────
        BenchEvent(
            event_id="H-S2-DOCKING", session=2, kind="episodic", event_type="docking_experiment",
            title="Docking of P17 with VHL predicts poor ternary geometry",
            content="Ternary docking of P17 (BRD4 BD2 + VHL) yields a low cooperativity pose; "
                    "the short PEG exit vector cannot span the ternary interface.",
            context=hek, observed={"ternary_complex_score": 0.21, "cooperativity": 0.18},
            evidence=[{"evidence_type": "docking", "experiment_id": "DOCK-77"}],
            interpretation="short PEG linker geometry is non-productive",
            decision_impact=0.7, goal_relevance=0.8,
        ),
        # ── Session 3: model prediction (stored before outcome) ──────────
        BenchEvent(
            event_id="H-S3-PRED", session=3, kind="episodic", event_type="prediction",
            title="Prediction: P17 dmax = 0.85",
            content="Model predicted high degradation for P17 despite the docking concern.",
            context=hek,
            prediction={"prediction_type": "numeric", "candidate_id": "P17", "metric": "dmax",
                        "predicted_value": 0.85, "confidence": 0.78, "scale": 1.0},
        ),
        # ── Session 4: experimental outcome + replicates ─────────────────
        BenchEvent(
            event_id="H-S4-OUTCOME", session=4, kind="negative", event_type="degradation_assay",
            title="P17 degradation assay (HEK293): dmax 18%",
            content="P17 was assayed in HEK293 with VHL: predicted dmax 0.85, observed dmax 0.18.",
            context=hek, observed={"dmax": 0.18, "dc50": 420.0},
            evidence=[{"evidence_type": "internal_experiment", "experiment_id": "EXP-142"}],
            interpretation="short PEG linker geometry is non-productive",
            is_negative=True, decision_impact=0.95, goal_relevance=0.9,
            outcome={"observed_value": 0.18, "evidence_type": "internal_experiment",
                     "experiment_id": "EXP-142"},
            related_prediction_event="H-S3-PRED",
        ),
        BenchEvent(
            event_id="H-S4-REP1", session=4, kind="episodic", event_type="degradation_assay",
            title="P21 degradation assay (HEK293): dmax 22%",
            content="A close analogue P21 with the same short PEG architecture degraded poorly in HEK293.",
            context=dict(hek, compound_id="P21"), observed={"dmax": 0.22},
            evidence=[{"evidence_type": "internal_experiment", "experiment_id": "EXP-143"}],
            interpretation="short PEG linker geometry is non-productive",
            is_negative=True, decision_impact=0.8,
        ),
        BenchEvent(
            event_id="H-S4-REP2", session=4, kind="episodic", event_type="degradation_assay",
            title="P24 degradation assay (HEK293): dmax 19%",
            content="A second analogue P24 with the short PEG architecture also degraded poorly in HEK293.",
            context=dict(hek, compound_id="P24"), observed={"dmax": 0.19},
            evidence=[{"evidence_type": "internal_experiment", "experiment_id": "EXP-144"}],
            interpretation="short PEG linker geometry is non-productive",
            is_negative=True, decision_impact=0.8,
        ),
        # distractor: same compound class, different E3
        BenchEvent(
            event_id="H-S4-CRBN", session=4, kind="episodic", event_type="degradation_assay",
            title="P30 degradation assay with CRBN (HEK293): dmax 55%",
            content="A CRBN-recruiting analogue P30 showed moderate degradation (dmax 0.55) in HEK293.",
            context=crbn, observed={"dmax": 0.55},
            evidence=[{"evidence_type": "internal_experiment", "experiment_id": "EXP-146"}],
            decision_impact=0.5,
        ),
        # ── Session 5: context-dependent / contradictory observation ─────
        BenchEvent(
            event_id="H-S5-MV411", session=5, kind="episodic", event_type="degradation_assay",
            title="P17 degradation in MV4-11 is high: dmax 71%",
            content="In the MV4-11 cell background P17 degraded well (dmax 0.71), contradicting the "
                    "HEK293 result; the linker rule is therefore not universal across cell lines.",
            context=mv4, observed={"dmax": 0.71},
            evidence=[{"evidence_type": "internal_experiment", "experiment_id": "EXP-145"}],
            decision_impact=0.9, goal_relevance=0.8,
        ),
        # ── Session 6: redesign decision + prospective task ──────────────
        BenchEvent(
            event_id="H-S6-REDESIGN", session=6, kind="episodic", event_type="design_choice",
            title="Redesign decision: replace short PEG L7 with a rigid exit-vector linker",
            content="Prioritise an alternative exit-vector (rigid) linker and advance candidate P34; "
                    "avoid repeating the failed short PEG geometry.",
            context=dict(hek, compound_id="P34", linker_type="rigid"),
            topic_key="design.decision",
            evidence=[{"evidence_type": "user_assertion", "experiment_id": "DES-2"}],
            decision_impact=0.95, goal_relevance=0.95,
        ),
        BenchEvent(
            event_id="H-S6-TASK", session=6, kind="prospective", event_type="design_choice",
            title="Outstanding validation: P17 permeability",
            content="Validate P17 permeability in Caco-2 before deprioritising the series.",
            context=hek, task="Validate P17 permeability in Caco-2",
            decision_impact=0.6, goal_relevance=0.8,
        ),
    ] + background_events()


# ── questions with gold labels ───────────────────────────────────────────────
@dataclass
class Question:
    qid: str
    capability: str
    text: str
    gold_events: list[str]
    answer_any: list[str] = field(default_factory=list)
    answer_all: list[str] = field(default_factory=list)
    quote: str | None = None
    context: dict[str, Any] | None = None
    k: int = 5
    stale_if_present: list[str] = field(default_factory=list)
    stale_if_absent: list[str] = field(default_factory=list)


def build_questions() -> list[Question]:
    hek = {"target_gene": "BRD4", "e3_ligase": "VHL", "cell_line": "HEK293"}
    return [
        Question(
            "Q1", "episodic_recall",
            "What Dmax was measured for candidate P17 in HEK293?",
            gold_events=["H-S4-OUTCOME"], answer_any=["0.18", "18%"], context=hek,
        ),
        Question(
            "Q2", "context_discrimination",
            "Did the P17 degradation failure occur with VHL or CRBN?",
            gold_events=["H-S4-OUTCOME"], answer_any=["vhl"], context=hek,
        ),
        Question(
            "Q3", "provenance",
            "What evidence supports the short-PEG linker hypothesis?",
            gold_events=["H-S2-DOCKING", "H-S4-OUTCOME", "H-S4-REP1", "H-S4-REP2"],
            answer_any=["exp-142", "exp-143", "exp-144", "dock-77"], context=hek,
        ),
        Question(
            "Q4", "contradiction",
            "Is the short-PEG linker rule universal across cell lines?",
            gold_events=["H-S5-MV411", "H-S4-OUTCOME"], answer_any=["mv4-11", "mv411"],
            context=hek,
            stale_if_present=["hek293"], stale_if_absent=["mv4-11", "mv411"],
        ),
        Question(
            "Q5", "temporal_update",
            "What did we initially predict for P17 and what was observed?",
            gold_events=["H-S4-OUTCOME"], answer_all=["0.85", "0.18"], context=hek,
            stale_if_present=["0.85"], stale_if_absent=["0.18"],
        ),
        Question(
            "Q6", "negative_transfer",
            "Does the new candidate P34 resemble a prior failed design?",
            gold_events=["H-S4-OUTCOME", "H-S6-REDESIGN"],
            answer_any=["short peg", "non-productive", "failed"], context=hek,
        ),
        Question(
            "Q7", "prospective",
            "What validation work remains outstanding?",
            gold_events=["H-S6-TASK"], answer_any=["permeability", "caco-2"], context=hek,
        ),
        Question(
            "Q8", "recommendation",
            "Which design should be prioritised: the short PEG L7 or an alternative exit-vector linker?",
            gold_events=["H-S6-REDESIGN", "H-S4-OUTCOME"],
            answer_any=["exit-vector", "exit vector", "rigid"], context=hek,
        ),
    ]


# ── deterministic reader (identical for all backends) ────────────────────────
def read_answer(assembled: str, question: Question) -> tuple[bool, dict[str, bool]]:
    text = (assembled or "").lower()
    any_ok = (not question.answer_any) or any(term.lower() in text for term in question.answer_any)
    all_ok = all(term.lower() in text for term in question.answer_all)
    quote_ok = question.quote is None or question.quote.lower() in text
    checks = {"answer_any": any_ok, "answer_all": all_ok, "quote": quote_ok}
    return (any_ok and all_ok and quote_ok), checks


def is_stale(assembled: str, question: Question) -> bool:
    text = (assembled or "").lower()
    if not question.stale_if_present:
        return False
    hit = any(term.lower() in text for term in question.stale_if_present)
    if not hit:
        return False
    return not any(term.lower() in text for term in question.stale_if_absent)


# ── ranking metrics ──────────────────────────────────────────────────────────
def _relevant(item: RetrievedItem, gold: set[str]) -> bool:
    return bool(set(item.source_events) & gold)


def recall_at_k(items: list[RetrievedItem], gold: set[str], k: int) -> float:
    return 1.0 if any(_relevant(it, gold) for it in items[:k]) else 0.0


def reciprocal_rank(items: list[RetrievedItem], gold: set[str]) -> float:
    for rank, item in enumerate(items, start=1):
        if _relevant(item, gold):
            return 1.0 / rank
    return 0.0


def ndcg_at_k(items: list[RetrievedItem], gold: set[str], k: int) -> float:
    gains = [1.0 if _relevant(it, gold) else 0.0 for it in items[:k]]
    dcg = sum(g / math.log2(i + 1) for i, g in enumerate(gains, start=1))
    ideal_hits = int(min(sum(gains), k))
    ideal = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_hits + 1))
    return dcg / ideal if ideal else 0.0


# ── condition runner ─────────────────────────────────────────────────────────
def run_condition(backend: MemoryBackend, events: list[BenchEvent], questions: list[Question]) -> dict[str, Any]:
    backend.reset()
    ingest_start = time.perf_counter()
    for event in events:
        backend.ingest(event)
    backend.finalize()
    ingest_ms = (time.perf_counter() - ingest_start) * 1000.0

    per_question: list[dict[str, Any]] = []
    for question in questions:
        gold = set(question.gold_events)
        start = time.perf_counter()
        items = backend.retrieve(question.text, context=question.context, k=question.k)
        retrieval_ms = (time.perf_counter() - start) * 1000.0
        start = time.perf_counter()
        assembled = backend.assemble(question.text, context=question.context, k=question.k)
        assembly_ms = (time.perf_counter() - start) * 1000.0
        correct, checks = read_answer(assembled, question)
        per_question.append({
            "qid": question.qid,
            "capability": question.capability,
            "query": question.text,
            "gold_events": list(question.gold_events),
            "expected_memory": list(question.gold_events),
            "recall@k": recall_at_k(items, gold, question.k),
            "mrr": reciprocal_rank(items, gold),
            "ndcg@k": ndcg_at_k(items, gold, question.k),
            "answer_correct": 1.0 if correct else 0.0,
            "stale_belief": 1.0 if is_stale(assembled, question) else 0.0,
            "tokens_injected": estimate_tokens(assembled),
            "retrieval_latency_ms": retrieval_ms,
            "assembly_latency_ms": assembly_ms,
            "retrieved_ids": [it.id for it in items],
            "retrieved_sources": [it.source_events for it in items],
            "retrieved_contexts": [it.context for it in items],
            "retrieved_text": assembled,
            "query_context": question.context or {},
            "contradiction_resolved": bool(correct) if question.capability == "contradiction" else None,
            "requires_provenance": question.capability in ("provenance", "recommendation"),
        })

    session = backend.session_context(k=8)
    session_text = session.get("text", "") if isinstance(session, dict) else ""

    def mean(key: str) -> float:
        return sum(q[key] for q in per_question) / len(per_question) if per_question else 0.0

    def mean_capability(capability: str) -> float:
        rows = [q for q in per_question if q["capability"] == capability]
        return sum(q["answer_correct"] for q in rows) / len(rows) if rows else 0.0

    aggregate = {
        "recall@k": mean("recall@k"),
        "mrr": mean("mrr"),
        "ndcg@k": mean("ndcg@k"),
        "factual_accuracy": mean("answer_correct"),
        "context_accuracy": mean_capability("context_discrimination"),
        "contradiction_accuracy": mean_capability("contradiction"),
        "provenance_accuracy": mean_capability("provenance"),
        "temporal_accuracy": mean_capability("temporal_update"),
        "negative_transfer_accuracy": mean_capability("negative_transfer"),
        "prospective_accuracy": mean_capability("prospective"),
        "recommendation_accuracy": mean_capability("recommendation"),
        "stale_belief_rate": mean("stale_belief"),
        "mean_tokens_injected": mean("tokens_injected"),
        "mean_retrieval_latency_ms": mean("retrieval_latency_ms"),
        "mean_assembly_latency_ms": mean("assembly_latency_ms"),
        "session_context_tokens": estimate_tokens(session_text),
        "ingest_latency_ms": ingest_ms,
    }
    aggregate.update(scientific_metrics(per_question))
    return {
        "backend": backend.name,
        "stats": backend.stats(),
        "aggregate": aggregate,
        "questions": per_question,
    }


def run_all(events: list[BenchEvent] | None = None, questions: list[Question] | None = None) -> dict[str, Any]:
    from protacpilot_memory.util import set_deterministic_ids

    set_deterministic_ids(True)
    events = events if events is not None else build_project()
    questions = questions if questions is not None else build_questions()
    conditions: dict[str, Any] = {}
    for name, backend in build_backends().items():
        conditions[name] = run_condition(backend, events, questions)
    return {
        "benchmark": "H_longitudinal_five_way",
        "n_events": len(events),
        "n_questions": len(questions),
        "conditions": conditions,
        "capabilities": sorted({q.capability for q in questions}),
    }


# ── output writers ───────────────────────────────────────────────────────────
def write_results(results: dict[str, Any], outdir: Path = RESULTS_DIR) -> dict[str, Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    json_path = outdir / "benchmark_h.json"
    csv_path = outdir / "benchmark_h.csv"
    md_path = outdir / "BENCHMARK_H_REPORT.md"

    json_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")

    metric_keys = list(next(iter(results["conditions"].values()))["aggregate"])
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["backend", *metric_keys])
        for name, condition in results["conditions"].items():
            writer.writerow([name, *[round(condition["aggregate"][k], 4) for k in metric_keys]])

    md_path.write_text(render_report(results), encoding="utf-8")
    return {"json": json_path, "csv": csv_path, "md": md_path}


def render_report(results: dict[str, Any]) -> str:
    names = list(results["conditions"])
    metric_keys = list(results["conditions"][names[0]]["aggregate"])
    lines = [
        "# Benchmark H — Longitudinal Scientific Project (five-way)",
        "",
        f"- Events: {results['n_events']}  |  Questions: {results['n_questions']}",
        "- Conditions: " + ", ".join(f"`{n}`" for n in names),
        "- Answers are produced by a deterministic reader over each backend's retrieved context (no LLM).",
        "",
        "## Aggregate metrics",
        "",
        "| metric | " + " | ".join(names) + " |",
        "|---|" + "|".join("---" for _ in names) + "|",
    ]
    for key in metric_keys:
        row = " | ".join(f"{results['conditions'][n]['aggregate'][key]:.4f}" for n in names)
        lines.append(f"| {key} | {row} |")

    lines += ["", "## Per-question accuracy by capability", "",
              "| capability | " + " | ".join(names) + " |",
              "|---|" + "|".join("---" for _ in names) + "|"]
    capabilities = results["capabilities"]
    for cap in capabilities:
        cells = []
        for n in names:
            rows = [q for q in results["conditions"][n]["questions"] if q["capability"] == cap]
            value = sum(q["answer_correct"] for q in rows) / len(rows) if rows else 0.0
            cells.append(f"{value:.2f}")
        lines.append(f"| {cap} | " + " | ".join(cells) + " |")

    lines += ["", "## Provenance of retrieved evidence", ""]
    for name in names:
        qrows = results["conditions"][name]["questions"]
        lines.append(f"- **{name}**: " + "; ".join(
            f"{q['qid']} -> {q['retrieved_sources']}" for q in qrows
        ))

    lines += [
        "",
        "> **Interpretation guard.** A higher score for `cognitive_memory` is only",
        "> meaningful where the numbers above show it. Where a baseline wins or ties,",
        "> that is reported without adjustment. Small question counts (8) do not",
        "> support inferential significance claims.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    results = run_all()
    paths = write_results(results)
    names = list(results["conditions"])
    print(f"Benchmark H — five-way ({results['n_events']} events, {results['n_questions']} questions)")
    header = f"{'metric':32s} " + " ".join(f"{n:>18s}" for n in names)
    print(header)
    for key in results["conditions"][names[0]]["aggregate"]:
        row = " ".join(f"{results['conditions'][n]['aggregate'][key]:>18.4f}" for n in names)
        print(f"{key:32s} {row}")
    print("written:", ", ".join(str(p) for p in paths.values()))


if __name__ == "__main__":  # pragma: no cover
    main()

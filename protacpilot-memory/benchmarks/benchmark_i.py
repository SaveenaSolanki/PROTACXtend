"""Benchmark I — PROTAC longitudinal failure-feedback (brief §8, §10).

The scientific question
-----------------------
When an initially plausible PROTAC fails *experimentally or mechanistically*,
does feeding the outcome back into memory change later candidate selection in
the right direction?

Each programme follows the required causal chain:

    design hypothesis → prediction → outcome → prediction error
    → negative episode → consolidation (semantic update) → redesign decision

The same stream is replayed through every memory condition (brief §6) and each
programme ends with a decision query whose answer is read deterministically.
We then measure the generic retrieval metrics plus the scientific metrics
(Repeated Error Rate, Context Contamination Rate, Provenance Fidelity,
Contradiction Resolution Accuracy, Longitudinal Decision Accuracy).

Run::

    PYTHONPATH=src python -m benchmarks.benchmark_i

Outputs (``benchmarks/results/``): ``benchmark_i.json``, ``benchmark_i.csv``,
``BENCHMARK_I_REPORT.md``, plus tidy per-task rows in ``benchmark_i_tidy.csv``
(and ``.parquet`` when pyarrow is available).
"""

from __future__ import annotations

import csv
import json
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from protacpilot_memory.config import ConsolidationConfig, MemoryConfig
from protacpilot_memory.util import set_deterministic_ids

from .baselines import (
    BenchEvent,
    CognitiveMemoryBackend,
    MemoryBackend,
    RetrievedItem,
    build_backends,
    estimate_tokens,
)
from .benchmark_h import (
    ndcg_at_k,
    recall_at_k,
    reciprocal_rank,
)
from .metrics import scientific_metrics

RESULTS_DIR = Path(__file__).resolve().parent / "results"

# Generic design-pattern markers used by the deterministic reader.
FAILURE_MARKERS = ("non-productive", "failed short peg", "poor degradation", "dmax 0.1", "dmax 0.2")
IMPROVED_MARKERS = ("rigid", "exit-vector", "exit vector")
FAILED_PATTERN_MARKERS = ("short peg", "short-peg")


@dataclass
class Program:
    program_id: str
    target: str
    e3: str
    cell: str
    events: list[BenchEvent]
    decision_query: str
    context: dict[str, Any]
    expected_direction: str = "rigid"


def _ctx(target: str, e3: str = "VHL", cell: str = "HEK293", **extra: Any) -> dict[str, Any]:
    base = {
        "project": "bench-i",
        "target_gene": target,
        "e3_ligase": e3,
        "cell_line": cell,
        "assay_type": "degradation assay",
        "experiment_type": "degradation_assay",
        "endpoint": "dmax",
        "linker_type": extra.pop("linker_type", "PEG"),
    }
    base.update(extra)
    return base


def build_programs() -> list[Program]:
    """Four programmes, each: plausible short-PEG design fails → redesign."""
    programmes: list[Program] = []
    targets = ["BRD4", "BRD9", "AR", "SMARCA2"]
    for index, target in enumerate(targets):
        tag = f"P{index}"
        short_ctx = _ctx(target, linker_type="PEG", compound_id=f"{tag}-A0")
        events: list[BenchEvent] = []

        # 1. plausible design hypothesis
        events.append(BenchEvent(
            event_id=f"{tag}-DESIGN", session=1, kind="episodic", event_type="design_choice",
            title=f"{target} design decision: short PEG linker for {tag}-A0",
            content=f"Chose a short PEG linker for {tag}-A0 to improve permeability while "
                    f"retaining {target} degradation; hypothesis: shorter linker improves exposure.",
            context=short_ctx, topic_key="design.decision",
            evidence=[{"evidence_type": "user_assertion", "experiment_id": f"{tag}-DES-1"}],
            decision_impact=0.9, goal_relevance=0.95,
        ))
        # 2. prediction before the outcome exists
        events.append(BenchEvent(
            event_id=f"{tag}-PRED", session=1, kind="episodic", event_type="prediction",
            title=f"Prediction: {tag}-A0 dmax = 0.85",
            content=f"Model predicted high {target} degradation for {tag}-A0.",
            context=short_ctx,
            prediction={"prediction_type": "numeric", "candidate_id": f"{tag}-A0",
                        "metric": "dmax", "predicted_value": 0.85, "confidence": 0.78, "scale": 1.0},
        ))
        # 3. experimental failure (outcome + prediction error + negative episode)
        failed_compounds = [f"{tag}-A{i}" for i in range(3)]
        observed = [0.16, 0.18, 0.20]
        for i, compound in enumerate(failed_compounds):
            ctx = _ctx(target, linker_type="PEG", compound_id=compound)
            event = BenchEvent(
                event_id=f"{tag}-FAIL{i}", session=2, kind="negative", event_type="degradation_assay",
                title=f"{compound} degradation assay ({target}): dmax {observed[i]:.2f}",
                content=f"{compound} with the short PEG architecture degraded {target} poorly "
                        f"in HEK293 (dmax {observed[i]:.2f}).",
                context=ctx, observed={"dmax": observed[i]},
                evidence=[{"evidence_type": "internal_experiment",
                           "experiment_id": f"{tag}-EXP-{i}"}],
                interpretation="short PEG linker geometry is non-productive",
                is_negative=True, decision_impact=0.9, goal_relevance=0.85,
            )
            if i == 0:
                event.outcome = {"observed_value": observed[i], "evidence_type": "internal_experiment",
                                 "experiment_id": f"{tag}-EXP-{i}"}
                event.related_prediction_event = f"{tag}-PRED"
            events.append(event)

        # 4. redesign decision (rigid exit-vector) — the correct scientific update
        rigid_ctx = _ctx(target, linker_type="rigid", compound_id=f"{tag}-B1")
        events.append(BenchEvent(
            event_id=f"{tag}-REDESIGN", session=3, kind="episodic", event_type="design_choice",
            title=f"{target} redesign: rigid exit-vector linker for {tag}-B1",
            content=f"Prioritise a rigid exit-vector linker for {tag}-B1 and avoid repeating the "
                    f"failed short PEG geometry; recommended alternative for {target}.",
            context=rigid_ctx, topic_key="design.decision",
            evidence=[{"evidence_type": "user_assertion", "experiment_id": f"{tag}-DES-2"}],
            decision_impact=0.95, goal_relevance=0.95,
        ))
        # 5. successful outcome of the redesign
        events.append(BenchEvent(
            event_id=f"{tag}-SUCCESS", session=3, kind="episodic", event_type="degradation_assay",
            title=f"{tag}-B1 degradation assay ({target}): dmax 0.78",
            content=f"The rigid exit-vector candidate {tag}-B1 degraded {target} well in HEK293 "
                    f"(dmax 0.78).",
            context=rigid_ctx, observed={"dmax": 0.78},
            evidence=[{"evidence_type": "internal_experiment", "experiment_id": f"{tag}-EXP-9"}],
            decision_impact=0.8, goal_relevance=0.9,
        ))

        programmes.append(Program(
            program_id=tag,
            target=target,
            e3="VHL",
            cell="HEK293",
            events=events,
            decision_query=(
                f"For {target}, should we advance the short PEG candidate {tag}-A0 or switch "
                f"to a rigid exit-vector linker?"
            ),
            context=_ctx(target, linker_type="PEG"),
        ))
    return programmes


# ── deterministic decision reader (identical across backends) ────────────────
@dataclass
class Decision:
    recommends_improved: bool
    recalls_failure: bool
    repeated_error: bool
    correct: bool
    direction: str


def read_decision(assembled: str, *, failure_retrieved: bool = False) -> Decision:
    text = (assembled or "").lower()
    improved = any(m in text for m in IMPROVED_MARKERS)
    failed_pattern = any(m in text for m in FAILED_PATTERN_MARKERS)
    # Correct: the failure memory was actually retrieved *and* the alternative
    # design is surfaced. Grounding in retrieved sources avoids the redesign
    # prose (“avoid repeating the failed short PEG geometry”) being mistaken for
    # an actual failure recall.
    correct = failure_retrieved and improved
    repeated = failed_pattern and not failure_retrieved
    if improved and not failed_pattern:
        direction = "rigid"
    elif failed_pattern and not improved:
        direction = "short_peg"
    elif improved and failed_pattern:
        direction = "rigid" if failure_retrieved else "ambiguous"
    else:
        direction = "none"
    return Decision(improved, failure_retrieved, repeated, correct, direction)


# ── audit the required causal chain for the cognitive backend ────────────────
def audit_chain(backend: MemoryBackend) -> dict[str, Any]:
    mem = getattr(backend, "_mem", None)
    if mem is None:
        return {"available": False}
    store = mem.store
    project = backend._project
    predictions = store.count("prediction_events", "project_id = ?", (project,))
    outcomes = store.count(
        "outcome_events",
        "prediction_id IN (SELECT id FROM prediction_events WHERE project_id = ?)",
        (project,),
    )
    outcomes_with_error = store.db.query(
        "SELECT o.prediction_error FROM outcome_events o "
        "JOIN prediction_events p ON p.id = o.prediction_id WHERE p.project_id = ?",
        (project,),
    )
    max_error = max((float(r["prediction_error"] or 0.0) for r in outcomes_with_error), default=0.0)
    negatives = store.count(
        "episodic_memories",
        "is_negative = 1 AND trace_id IN (SELECT id FROM memory_traces WHERE project_id = ?)",
        (project,),
    )
    semantics = store.count(
        "memory_traces", "memory_type = 'semantic' AND project_id = ?", (project,)
    )
    episodes = store.count("memory_traces", "project_id = ?", (project,))
    return {
        "available": True,
        "predictions": predictions,
        "outcomes": outcomes,
        "outcomes_with_prediction_error": sum(
            1 for r in outcomes_with_error if float(r["prediction_error"] or 0.0) > 0.0
        ),
        "max_prediction_error": max_error,
        "negative_episodes": negatives,
        "semantic_memories": semantics,
        "memory_traces": episodes,
        "chain_complete": bool(predictions and outcomes and max_error > 0.0 and negatives and semantics),
    }


# ── condition runner ─────────────────────────────────────────────────────────
def run_condition(
    backend: MemoryBackend,
    programmes: list[Program],
    *,
    k: int = 5,
) -> dict[str, Any]:
    backend.reset()
    events = [event for program in programmes for event in program.events]
    start = time.perf_counter()
    for event in events:
        backend.ingest(event)
    backend.finalize()
    ingest_ms = (time.perf_counter() - start) * 1000.0

    rows: list[dict[str, Any]] = []
    for program in programmes:
        gold = {f"{program.program_id}-FAIL0", f"{program.program_id}-REDESIGN"}
        t0 = time.perf_counter()
        items = backend.retrieve(program.decision_query, context=program.context, k=k)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        assembled = backend.assemble(program.decision_query, context=program.context, k=k)
        sources = [s for it in items for s in it.source_events]
        failure_retrieved = f"{program.program_id}-FAIL0" in sources
        redesign_retrieved = f"{program.program_id}-REDESIGN" in sources
        decision = read_decision(assembled, failure_retrieved=failure_retrieved)
        core_context = {
            key: program.context.get(key)
            for key in ("project", "target_gene", "e3_ligase", "cell_line")
            if program.context.get(key)
        }
        rows.append({
            "task_id": program.program_id,
            "capability": "longitudinal_decision",
            "query": program.decision_query,
            "query_context": core_context,
            "expected_candidate": "rigid",
            "expected_memory": [f"{program.program_id}-FAIL0", f"{program.program_id}-REDESIGN"],
            "recommended": decision.direction,
            "previously_failed": ["short_peg"],
            "recall@k": recall_at_k(items, gold, k),
            "mrr": reciprocal_rank(items, gold),
            "ndcg@k": ndcg_at_k(items, gold, k),
            "answer_correct": 1.0 if decision.correct else 0.0,
            "repeated_error": 1.0 if decision.repeated_error else 0.0,
            "recalls_failure": 1.0 if decision.recalls_failure else 0.0,
            "recommends_improved": 1.0 if decision.recommends_improved else 0.0,
            "retrieved_ids": [it.id for it in items],
            "retrieved_sources": [it.source_events for it in items],
            "retrieved_contexts": [it.context for it in items],
            "retrieved_text": assembled,
            "tokens_injected": estimate_tokens(assembled),
            "latency_ms": latency_ms,
            "failure_memory_retrieved": 1.0 if failure_retrieved else 0.0,
            "redesign_retrieved": 1.0 if redesign_retrieved else 0.0,
            "contradiction_resolved": bool(failure_retrieved and redesign_retrieved),
            "requires_provenance": True,
        })

    # Contradiction-resolution proxy: did the system surface both the failure
    # and the redesign (the two sides of the scientific update)?
    for row in rows:
        row["contradiction_resolved"] = bool(
            row["failure_memory_retrieved"] and row["redesign_retrieved"]
        )

    def mean(key: str) -> float:
        return sum(r[key] for r in rows) / len(rows) if rows else 0.0

    aggregate = {
        "recall@k": mean("recall@k"),
        "mrr": mean("mrr"),
        "ndcg@k": mean("ndcg@k"),
        "decision_accuracy": mean("answer_correct"),
        "repeated_error_rate": mean("repeated_error"),
        "failure_recall": mean("recalls_failure"),
        "improved_recommendation_rate": mean("recommends_improved"),
        "mean_tokens_injected": mean("tokens_injected"),
        "mean_latency_ms": mean("latency_ms"),
        "ingest_latency_ms": ingest_ms,
    }
    aggregate.update(scientific_metrics(rows))
    return {
        "backend": backend.name,
        "stats": backend.stats(),
        "aggregate": aggregate,
        "programs": rows,
        "chain": audit_chain(backend),
    }


def run_all(programmes: list[Program] | None = None) -> dict[str, Any]:
    set_deterministic_ids(True)
    programmes = programmes or build_programs()
    backends = build_backends()
    # Failure patterns must be able to consolidate into a scoped semantic claim for
    # the required prediction→outcome→error→negative→semantic→redesign chain.
    backends["cognitive_memory"] = CognitiveMemoryBackend(
        config=replace(
            MemoryConfig(),
            consolidation=replace(ConsolidationConfig(), include_negative=True),
        )
    )
    conditions: dict[str, Any] = {}
    for name, backend in backends.items():
        conditions[name] = run_condition(backend, programmes)
    return {
        "benchmark": "I_longitudinal_failure_feedback",
        "n_programs": len(programmes),
        "conditions": conditions,
        "capabilities": ["longitudinal_decision"],
    }


# ── output writers ───────────────────────────────────────────────────────────
METRIC_KEYS = [
    "recall@k", "mrr", "ndcg@k", "decision_accuracy", "failure_recall",
    "improved_recommendation_rate", "repeated_error_rate", "context_contamination_rate",
    "provenance_fidelity", "contradiction_resolution_accuracy", "longitudinal_decision_accuracy",
    "mean_tokens_injected", "mean_latency_ms",
]


def write_results(results: dict[str, Any], outdir: Path = RESULTS_DIR) -> dict[str, Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    json_path = outdir / "benchmark_i.json"
    csv_path = outdir / "benchmark_i.csv"
    md_path = outdir / "BENCHMARK_I_REPORT.md"
    tidy_path = outdir / "benchmark_i_tidy.csv"
    json_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")

    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["backend", *METRIC_KEYS])
        for name, cond in results["conditions"].items():
            writer.writerow([name, *[round(cond["aggregate"][m], 4) for m in METRIC_KEYS]])

    # tidy per-task rows (brief §11)
    tidy_fields = [
        "task_id", "memory_config", "seed", "query", "expected_memory", "retrieved_memory_ids",
        "rank", "latency_ms", "token_count", "context_compatibility", "correct",
    ]
    with tidy_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=tidy_fields, extrasaction="ignore")
        writer.writeheader()
        for name, cond in results["conditions"].items():
            for row in cond["programs"]:
                writer.writerow({
                    "task_id": row["task_id"],
                    "memory_config": name,
                    "seed": results.get("seed", 7),
                    "query": row["query"],
                    "expected_memory": row["expected_candidate"],
                    "retrieved_memory_ids": "|".join(row["retrieved_ids"]),
                    "rank": row.get("rank", ""),
                    "latency_ms": round(row["latency_ms"], 4),
                    "token_count": row["tokens_injected"],
                    "context_compatibility": "",
                    "correct": int(row["answer_correct"]),
                })
    md_path.write_text(render_report(results), encoding="utf-8")
    return {"json": json_path, "csv": csv_path, "md": md_path, "tidy": tidy_path}


def render_report(results: dict[str, Any]) -> str:
    names = list(results["conditions"])
    lines = [
        "# Benchmark I — PROTAC Longitudinal Failure Feedback",
        "",
        f"- Programmes: {results['n_programs']}  |  Conditions: " + ", ".join(f"`{n}`" for n in names),
        "- Each programme: plausible short-PEG design → prediction → experimental failure →",
        "  prediction error → negative episode → consolidation (semantic update) → redesigned",
        "  rigid exit-vector candidate. Answers are read deterministically (no LLM).",
        "",
        "## Aggregate metrics",
        "",
        "| metric | " + " | ".join(names) + " |",
        "|---|" + "|".join("---" for _ in names) + "|",
    ]
    for key in METRIC_KEYS:
        row = " | ".join(f"{results['conditions'][n]['aggregate'][key]:.4f}" for n in names)
        lines.append(f"| {key} | {row} |")

    lines += [
        "",
        "## Required causal chain (cognitive memory)",
        "",
        "| link | value |",
        "|---|---|",
    ]
    chain = results["conditions"].get("cognitive_memory", {}).get("chain", {})
    for key in ("predictions", "outcomes", "outcomes_with_prediction_error",
                "max_prediction_error", "negative_episodes", "semantic_memories", "chain_complete"):
        if key in chain:
            lines.append(f"| {key} | {chain[key]} |")

    lines += [
        "",
        "## Interpretation guard",
        "",
        "- `repeated_error_rate` is the fraction of decisions that still lean on the",
        "  failed design without recalling the failure; lower is better.",
        "- `longitudinal_decision_accuracy` requires both the failure and the redesign",
        "  alternative to be surfaced; it is stricter than `decision_accuracy`.",
        "- Where a baseline matches or beats cognitive memory, that is reported here",
        "  without adjustment. Four programmes cannot support significance claims.",
        "- This is a *computational engram* evaluation; no biological equivalence is claimed.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:  # pragma: no cover
    results = run_all()
    paths = write_results(results)
    names = list(results["conditions"])
    print(f"Benchmark I — longitudinal failure feedback ({results['n_programs']} programmes)")
    header = f"{'metric':34s} " + " ".join(f"{n:>18s}" for n in names)
    print(header)
    for key in METRIC_KEYS:
        row = " ".join(f"{results['conditions'][n]['aggregate'][key]:>18.4f}" for n in names)
        print(f"{key:34s} {row}")
    chain = results["conditions"]["cognitive_memory"]["chain"]
    print("chain:", {k: chain.get(k) for k in ("predictions", "outcomes", "negative_episodes",
                                                "semantic_memories", "chain_complete")})
    print("written:", ", ".join(str(p) for p in paths.values()))


if __name__ == "__main__":  # pragma: no cover
    main()

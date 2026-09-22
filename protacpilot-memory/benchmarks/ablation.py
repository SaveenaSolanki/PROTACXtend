"""Component-ablation framework for Benchmark H (Master Prompt §47).

Runs the same six-session project through the cognitive backend with exactly one
meaningful component neutralised per condition, and measures the effect against
the FULL system.

Design rules
------------
* One component changes per condition; every other parameter is held constant.
* Neutralisation must be *verified*, not merely asserted by config. Each spec
  carries a ``verify`` callable that inspects the database / retrieval output
  while the patch is still active and raises if the component is still live.
* We do not perform significance testing on 8 questions. Deltas are descriptive.

Some ablations neutralise a class-level function for the duration of the run
(e.g. entity candidate generation). This is deliberate: setting a reranking
weight to zero would not remove the component from *candidate generation*, which
would silently invalidate the ablation.

Outputs:

    benchmarks/results/ABLATION_RESULTS.json
    benchmarks/results/ABLATION_RESULTS.csv
    benchmarks/results/ABLATION_REPORT.md
"""

from __future__ import annotations

import csv
import json
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Iterator

from protacpilot_memory.cognitive import attention as attention_module
from protacpilot_memory.config import (
    CandidateConfig,
    ConfidenceConfig,
    DecayConfig,
    EncodingWeights,
    MemoryConfig,
    ReplayConfig,
    RetrievalWeights,
)
from protacpilot_memory.domain.protac import evidence as evidence_module
from protacpilot_memory.domain.protac.context import ProtacContext
from protacpilot_memory.retrieval.graph import GraphRetriever
from protacpilot_memory.store.store import MemoryStore

from .baselines import CognitiveMemoryBackend
from .benchmark_h import RESULTS_DIR, build_project, build_questions, run_condition
from .metrics import PROVENANCE_RE

# metrics compared against the FULL system
COMPARED_METRICS = [
    "recall@k",
    "mrr",
    "ndcg@k",
    "factual_accuracy",
    "context_accuracy",
    "contradiction_accuracy",
    "provenance_accuracy",
    "stale_belief_rate",
    "mean_tokens_injected",
    "mean_retrieval_latency_ms",
    "mean_assembly_latency_ms",
]


@contextmanager
def _patch(target: Any, attr: str, value: Any) -> Iterator[None]:
    original = getattr(target, attr)
    setattr(target, attr, value)
    try:
        yield
    finally:
        setattr(target, attr, original)


# ── verification helpers ─────────────────────────────────────────────────────
def _traces(backend: CognitiveMemoryBackend, memory_type: str | None = None) -> list[dict[str, Any]]:
    return backend._mem.store.list(
        project_id=backend._project, memory_type=memory_type,
        limit=10000, include_deleted=True,
    )


def _verify_prediction_error(backend: CognitiveMemoryBackend) -> None:
    surprises = [float(t.get("surprise") or 0.0) for t in _traces(backend)]
    assert surprises and max(surprises) == 0.0, f"surprise still present: {max(surprises)}"


def _verify_no_semantic(backend: CognitiveMemoryBackend) -> None:
    assert not _traces(backend, "semantic"), "semantic memories were still created"


def _verify_no_reconsolidation(backend: CognitiveMemoryBackend) -> None:
    n = backend._mem.store.count("reconsolidation_events", "semantic_memory_id IN "
                                 "(SELECT id FROM memory_traces WHERE project_id = ?)",
                                 (backend._project,))
    assert n == 0, f"reconsolidation events present: {n}"


def _verify_semantic_excluded(backend: CognitiveMemoryBackend) -> None:
    assert _traces(backend, "semantic"), "semantic layer absent; ablation not meaningful"
    hits = backend.retrieve("BRD4 VHL linker degradation trend permeability", k=10)
    assert all(h.kind != "semantic" for h in hits), "semantic memory still retrievable"


def _verify_equal_evidence(backend: CognitiveMemoryBackend) -> None:
    rows = backend._mem.store.db.query(
        "SELECT e.quality FROM evidence_items e JOIN memory_evidence me ON me.evidence_id = e.id "
        "JOIN memory_traces t ON t.id = me.memory_id WHERE t.project_id = ?",
        (backend._project,),
    )
    qualities = {round(float(r["quality"] or 0.0), 6) for r in rows}
    assert rows and qualities == {1.0}, f"evidence qualities not equalised: {qualities}"


def _verify_no_context_components(backend: CognitiveMemoryBackend) -> None:
    weights = backend._mem.config.retrieval
    assert weights.context == 0.0 and weights.entity == 0.0 and weights.graph == 0.0, \
        "context/entity/graph weights are not zero"
    # candidate generation must also be disabled, not just reweighted
    assert backend._mem.store.memories_for_entity_names(["BRD4", "VHL"]) == [], \
        "entity candidate generation still active"
    assert backend._mem.retriever.graph.expand(["any"], depth=1) == {}, \
        "graph expansion still active"
    response = backend._mem.search("BRD4 VHL linker degradation", project_id=backend._project, limit=5)
    assert response.generator_counts.get("graph", 0) == 0, "graph candidates still generated"


def _verify_no_decay(backend: CognitiveMemoryBackend) -> None:
    assert backend._mem.config.retrieval.strength == 0.0, "strength weight not zero"
    assert backend._mem.config.decay.strengthen_eta == 0.0, "strengthening not disabled"
    traces = _traces(backend)
    assert traces, "no traces to verify"
    decay = backend._mem.decay
    before = decay.effective_strength(traces[0])
    after = decay.strengthen(traces[0]["id"], useful=True)
    assert after <= before + 1e-9, f"strengthening still increases strength: {before} -> {after}"


def _verify_no_negative(backend: CognitiveMemoryBackend) -> None:
    assert not _traces(backend, "negative"), "negative memories were still created"


def _verify_no_prospective(backend: CognitiveMemoryBackend) -> None:
    assert not _traces(backend, "prospective"), "prospective memories were still created"


def _verify_constant_fingerprint(backend: CognitiveMemoryBackend) -> None:
    fingerprints = {
        t.get("context_fingerprint") for t in _traces(backend) if t.get("context_fingerprint")
    }
    assert fingerprints, "no fingerprints to verify"
    assert len(fingerprints) == 1, f"fingerprints not collapsed: {fingerprints}"


def _verify_no_provenance(backend: CognitiveMemoryBackend) -> None:
    hits = backend.retrieve("BRD4 VHL linker degradation dmax", k=10)
    assert hits, "no hits to verify provenance ablation"
    leaked = [h.text for h in hits if PROVENANCE_RE.search(h.text or "")]
    assert not leaked, f"provenance still surfaced: {leaked[:2]}"


def _verify_no_temporal(backend: CognitiveMemoryBackend) -> None:
    assert backend._mem.config.retrieval.temporal == 0.0, "temporal weight not zero"


def _verify_no_candidate_bounding(backend: CognitiveMemoryBackend) -> None:
    assert backend._mem.config.candidates.enabled is False, "candidate bounding still enabled"
    response = backend._mem.search(
        "BRD4 VHL linker degradation", project_id=backend._project, limit=5
    )
    counts = response.generator_counts
    assert counts.get("entity_total", 0) > 0, "no entity candidates to bound"
    assert counts.get("entity", 0) == counts.get("entity_total", 0), (
        f"unbounded run still truncated candidates: {counts}"
    )


def _verify_no_reranking(backend: CognitiveMemoryBackend) -> None:
    weights = backend._mem.config.retrieval
    for component in ("semantic", "entity", "graph", "context", "evidence", "confidence",
                      "strength", "goal", "temporal"):
        assert getattr(weights, component) == 0.0, f"reranking component {component} not zero"
    assert weights.lexical > 0.0, "lexical weight must remain for a lexical-only baseline"
    response = backend._mem.search(
        "BRD4 VHL linker degradation", project_id=backend._project, limit=5
    )
    assert response.hits, "no hits to verify reranking ablation"
    for hit in response.hits:
        assert abs(hit.score - hit.components["lexical"]) < 1e-9, (
            "score is not purely lexical; reranking still active"
        )


# ── ablation specs ───────────────────────────────────────────────────────────
@dataclass
class AblationSpec:
    key: str
    label: str
    description: str
    config: MemoryConfig | None = None
    flags: dict[str, Any] = field(default_factory=dict)
    patches: list[tuple[Any, str, Any]] = field(default_factory=list)
    verify: Callable[[CognitiveMemoryBackend], None] | None = None


def _evidenceless_retrieval_config() -> MemoryConfig:
    return replace(
        MemoryConfig(),
        retrieval=replace(RetrievalWeights(), evidence=0.0),
        confidence=replace(
            ConfidenceConfig(), quality_gain=0.0, independence_gain=0.0, replication_gain=0.0
        ),
    )


def build_ablations() -> list[AblationSpec]:
    return [
        AblationSpec("FULL", "Full system", "No component removed (reference condition)"),
        AblationSpec(
            "minus_prediction_error",
            "− prediction error",
            "Encoding surprise and replay prediction-error weighting removed",
            config=replace(
                MemoryConfig(),
                encoding=EncodingWeights(surprise=0.0),
                replay=ReplayConfig(prediction_error=0.0),
            ),
            patches=[(attention_module, "surprise_from_error", lambda error, confidence=0.5: 0.0)],
            verify=_verify_prediction_error,
        ),
        AblationSpec(
            "minus_consolidation",
            "− consolidation",
            "Episode→semantic consolidation disabled",
            flags={"skip_consolidation": True},
            verify=_verify_no_semantic,
        ),
        AblationSpec(
            "minus_reconsolidation",
            "− reconsolidation",
            "Conflict-driven belief revision disabled",
            flags={"skip_reconsolidation": True},
            verify=_verify_no_reconsolidation,
        ),
        AblationSpec(
            "minus_semantic_layer",
            "− episodic/semantic separation",
            "Semantic (generalised) memories excluded from retrieval",
            flags={"exclude_semantic": True},
            verify=_verify_semantic_excluded,
        ),
        AblationSpec(
            "minus_evidence_weighting",
            "− evidence weighting",
            "All evidence qualities equalised; evidence reranking removed",
            config=_evidenceless_retrieval_config(),
            patches=[(evidence_module, "evidence_quality", lambda evidence_type: 1.0)],
            verify=_verify_equal_evidence,
        ),
        AblationSpec(
            "minus_context_entity_graph",
            "− context/entity graph",
            "Context, entity-overlap and relation-graph components removed "
            "(weights zeroed *and* candidate generation disabled)",
            config=replace(
                MemoryConfig(),
                retrieval=replace(RetrievalWeights(), context=0.0, entity=0.0, graph=0.0),
            ),
            patches=[
                (MemoryStore, "memories_for_entity_names", lambda self, names: []),
                (GraphRetriever, "expand", lambda self, *a, **k: {}),
            ],
            verify=_verify_no_context_components,
        ),
        AblationSpec(
            "minus_adaptive_decay",
            "− adaptive decay/strengthening",
            "Strength component removed; use-dependent strengthening disabled",
            config=replace(
                MemoryConfig(),
                retrieval=replace(RetrievalWeights(), strength=0.0),
                decay=replace(
                    DecayConfig(),
                    strengthen_eta=0.0,
                    half_life_days={
                        key: 365000.0 for key in (
                            "semantic_validated", "semantic", "semantic_provisional", "episodic",
                            "negative", "hypothesis", "observation", "procedural", "prospective",
                        )
                    },
                ),
            ),
            verify=_verify_no_decay,
        ),
        AblationSpec(
            "minus_negative_memory",
            "− negative memory",
            "Failures stored as ordinary episodes; no negative-memory class",
            flags={"disable_negative": True},
            verify=_verify_no_negative,
        ),
        AblationSpec(
            "minus_prospective_memory",
            "− prospective memory",
            "Future intentions/tasks not recorded",
            flags={"disable_prospective": True},
            verify=_verify_no_prospective,
        ),
        AblationSpec(
            "minus_context_fingerprint",
            "− context fingerprint",
            "Pattern separation removed: every context fingerprint collapses to one value",
            patches=[(ProtacContext, "fingerprint", lambda self, source_type=None: "COLLAPSED")],
            verify=_verify_constant_fingerprint,
        ),
        AblationSpec(
            "minus_provenance",
            "− provenance",
            "Provenance identifiers not surfaced in retrieval; evidence reranking removed",
            config=replace(
                MemoryConfig(),
                retrieval=replace(RetrievalWeights(), evidence=0.0),
            ),
            patches=[(CognitiveMemoryBackend, "_evidence_text", lambda self, memory_id: "")],
            verify=_verify_no_provenance,
        ),
        AblationSpec(
            "minus_temporal_weighting",
            "− temporal weighting",
            "Recency component removed from reranking",
            config=replace(MemoryConfig(), retrieval=replace(RetrievalWeights(), temporal=0.0)),
            verify=_verify_no_temporal,
        ),
        AblationSpec(
            "minus_candidate_bounding",
            "− candidate bounding",
            "Entity candidate generation left unbounded (legacy behaviour)",
            config=replace(MemoryConfig(), candidates=CandidateConfig(enabled=False)),
            verify=_verify_no_candidate_bounding,
        ),
        AblationSpec(
            "minus_reranking",
            "− reranking",
            "Additive reranker neutralised: lexical scoring only",
            config=replace(
                MemoryConfig(),
                retrieval=replace(
                    RetrievalWeights(),
                    semantic=0.0, entity=0.0, graph=0.0, context=0.0,
                    evidence=0.0, confidence=0.0, strength=0.0, goal=0.0, temporal=0.0,
                ),
            ),
            verify=_verify_no_reranking,
        ),
    ]


# ── runner ───────────────────────────────────────────────────────────────────
def run_ablation(spec: AblationSpec, events=None, questions=None) -> dict[str, Any]:
    events = events if events is not None else build_project()
    questions = questions if questions is not None else build_questions()
    backend = CognitiveMemoryBackend(config=spec.config, flags=spec.flags)
    verified = True
    verify_error: str | None = None
    with ExitStack() as stack:
        for target, attr, value in spec.patches:
            stack.enter_context(_patch(target, attr, value))
        result = run_condition(backend, events, questions)
        if spec.verify is not None:
            try:
                spec.verify(backend)
            except AssertionError as exc:
                verified = False
                verify_error = str(exc)
    result["ablation"] = {
        "key": spec.key,
        "label": spec.label,
        "description": spec.description,
        "component_removed_verified": verified,
        "verification_error": verify_error,
    }
    return result


def run_all_ablations(events=None, questions=None) -> dict[str, Any]:
    from protacpilot_memory.util import set_deterministic_ids

    set_deterministic_ids(True)
    events = events if events is not None else build_project()
    questions = questions if questions is not None else build_questions()
    conditions = {spec.key: run_ablation(spec, events, questions) for spec in build_ablations()}
    full = conditions["FULL"]["aggregate"]

    comparisons: dict[str, Any] = {}
    for key, condition in conditions.items():
        if key == "FULL":
            continue
        deltas = {}
        for metric in COMPARED_METRICS:
            value = condition["aggregate"][metric]
            base = full[metric]
            absolute = value - base
            pct = (absolute / base * 100.0) if base else None
            deltas[metric] = {"full": base, "value": value, "delta": absolute, "pct_change": pct}
        comparisons[key] = deltas

    return {
        "benchmark": "ablation_framework",
        "n_events": len(events),
        "n_questions": len(questions),
        "metrics": COMPARED_METRICS,
        "conditions": conditions,
        "comparisons": comparisons,
    }


# ── output writers ───────────────────────────────────────────────────────────
def write_results(results: dict[str, Any], outdir: Path = RESULTS_DIR) -> dict[str, Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    json_path = outdir / "ABLATION_RESULTS.json"
    csv_path = outdir / "ABLATION_RESULTS.csv"
    md_path = outdir / "ABLATION_REPORT.md"

    json_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")

    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["condition", "verified", *COMPARED_METRICS])
        for key, condition in results["conditions"].items():
            writer.writerow([
                key,
                condition["ablation"]["component_removed_verified"],
                *[round(condition["aggregate"][m], 4) for m in COMPARED_METRICS],
            ])

    md_path.write_text(render_report(results), encoding="utf-8")
    return {"json": json_path, "csv": csv_path, "md": md_path}


def render_report(results: dict[str, Any]) -> str:
    lines = [
        "# Ablation Report — PROTACpilot Cognitive Memory",
        "",
        f"- Project: {results['n_events']} events, {results['n_questions']} questions",
        "- Each row removes exactly one component; deltas are relative to FULL.",
        "- `verified` means the removal was asserted against the live database, not assumed.",
        "- No significance testing is reported: 8 questions cannot support it.",
        "",
        "## Absolute metrics",
        "",
        "| condition | verified | " + " | ".join(COMPARED_METRICS) + " |",
        "|---|" + "|".join("---" for _ in range(len(COMPARED_METRICS) + 1)) + "|",
    ]
    for key, condition in results["conditions"].items():
        cells = [f"{condition['aggregate'][m]:.4f}" for m in COMPARED_METRICS]
        lines.append(f"| {key} | {condition['ablation']['component_removed_verified']} | "
                     + " | ".join(cells) + " |")

    lines += ["", "## Delta vs FULL", "",
              "| condition | metric | full | value | Δ | % |", "|---|---|---|---|---|---|"]
    for key, deltas in results["comparisons"].items():
        for metric, d in deltas.items():
            pct = "n/a" if d["pct_change"] is None else f"{d['pct_change']:+.1f}%"
            lines.append(
                f"| {key} | {metric} | {d['full']:.4f} | {d['value']:.4f} | "
                f"{d['delta']:+.4f} | {pct} |"
            )

    notes = [c["ablation"] for c in results["conditions"].values()
             if not c["ablation"]["component_removed_verified"]]
    if notes:
        lines += ["", "## Failed verifications", ""]
        for note in notes:
            lines.append(f"- `{note['key']}`: {note['verification_error']}")

    lines += [
        "",
        "> A near-zero delta does not mean a component is useless; it means this",
        "> 8-question synthetic benchmark does not exercise it. Components such as",
        "> prediction-error prioritisation and replay primarily affect longer-horizon",
        "> behaviour than single-shot retrieval.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:  # pragma: no cover
    results = run_all_ablations()
    paths = write_results(results)
    print("Ablation framework")
    print(f"{'condition':28s} verified  recall@k  factual  tokens  retr_ms")
    for key, condition in results["conditions"].items():
        a = condition["aggregate"]
        print(f"{key:28s} {str(condition['ablation']['component_removed_verified']):8s}"
              f"  {a['recall@k']:.3f}    {a['factual_accuracy']:.3f}"
              f"    {a['mean_tokens_injected']:.0f}   {a['mean_retrieval_latency_ms']:.2f}")
    print("written:", ", ".join(str(p) for p in paths.values()))


if __name__ == "__main__":  # pragma: no cover
    main()

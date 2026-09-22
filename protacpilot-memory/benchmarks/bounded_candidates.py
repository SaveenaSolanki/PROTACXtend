"""Bounded candidate generation — before/after benchmark at scale (brief §5).

Motivation
----------
Entity-overlap candidate generation is unbounded by default. At scale this
floods the reranker with weakly-relevant memories that share an entity
(``BRD4``, ``VHL``) but not the scientific context, and those candidates can
displace the gold memory. This harness measures the effect directly:

* **before** — ``CandidateConfig.enabled = False`` (legacy unbounded expansion)
* **after**  — ``CandidateConfig.enabled = True``  (project-scoped, context-ranked,
  truncated, context-gated entity candidates)

Both conditions use the *same* corpus, the *same* queries and the *same*
reranker; only candidate generation changes. Metrics: Recall@k, MRR, nDCG@k,
mean retrieval latency, injected tokens, and the candidate-set sizes.

The corpus is synthetic and built for speed (direct store writes; no LLM).

Run::

    PYTHONPATH=src python -m benchmarks.bounded_candidates          # n=10000
    PYTHONPATH=src python -m benchmarks.bounded_candidates --n 2000 --quick

Outputs (``benchmarks/results/``): ``bounded_candidates.json``,
``bounded_candidates.csv``, ``BOUNDED_CANDIDATES_REPORT.md``.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from protacpilot_memory import CognitiveMemory
from protacpilot_memory.config import CandidateConfig, MemoryConfig
from protacpilot_memory.domain.protac import (
    ProtacContext,
    detect_entities,
    entity_search_text,
)
from protacpilot_memory.util import set_deterministic_ids

from .baselines import estimate_tokens

RESULTS_DIR = Path(__file__).resolve().parent / "results"

TARGETS = ["BRD4", "BRD9", "BRD2", "SMARCA2", "AR", "KRAS", "BTK", "IRAK4", "EGFR", "WDR5"]
E3S = ["VHL", "CRBN", "IAP", "MDM2"]
CELLS = ["HEK293", "MV4-11", "MOLT4", "PC3", "A549"]
ENDPOINTS = ["dmax", "dc50", "ic50", "permeability"]
LINKERS = ["PEG", "rigid", "alkyl", "triazole", "piperazine"]


@dataclass
class MemorySpec:
    event_id: str
    title: str
    content: str
    context: dict[str, Any]
    project: str = "scale"
    is_gold: bool = False
    trace_id: str | None = None
    evidence_strength: float = 0.35
    confidence: float = 0.35
    memory_strength: float = 0.5
    goal_relevance: float = 0.5


@dataclass
class ScaleQuery:
    qid: str
    text: str
    context: dict[str, Any]
    gold_event_ids: list[str]
    gold_trace_ids: list[str] = field(default_factory=list)


def build_corpus(
    *,
    n_total: int = 10_000,
    n_gold: int = 12,
    n_distractors: int = 1_500,
    n_decoy: int = 1_500,
    seed: int = 7,
) -> tuple[list[MemorySpec], list[ScaleQuery]]:
    """Build a scale corpus: gold facts, entity-overlap distractors, filler.

    Distractors deliberately share the query entities (BRD4/VHL) and the query
    vocabulary but *not* the scientific context (different cell/compound/
    endpoint), which is exactly the weak-overlap regime this fix targets.
    **Decoys** are the same kind of memory stored under a *different project* but
    carrying stronger numerical signals; the legacy un-scoped entity expansion
    pulls them in where they can outrank the gold memory.
    """
    specs: list[MemorySpec] = []
    queries: list[ScaleQuery] = []

    # ── gold: distinct, context-specific facts ──────────────────────────────
    for i in range(n_gold):
        compound = f"G{i:03d}"
        linker = LINKERS[i % len(LINKERS)]
        ctx = ProtacContext(
            project="scale",
            target_gene="BRD4", e3_ligase="VHL", cell_line="HEK293",
            assay_type="degradation assay", experiment_type="degradation_assay",
            endpoint="dmax", compound_id=compound, linker_type=linker,
            construct="full-length", structural_context="ternary-interface",
        )
        dmax = round(0.80 - i * 0.01, 3)
        specs.append(MemorySpec(
            event_id=f"GOLD-{i:03d}",
            title=f"BRD4 VHL degradation assay {compound} {linker} linker dmax {dmax}",
            content=f"Internal experiment: {compound} with {linker} linker degraded BRD4 "
                    f"in HEK293 via VHL with dmax {dmax}.",
            context=ctx.to_dict(),
            is_gold=True,
            evidence_strength=0.35, confidence=0.35, memory_strength=0.4, goal_relevance=0.5,
        ))
        queries.append(ScaleQuery(
            qid=f"Q{i:03d}",
            text=f"BRD4 VHL degradation dmax linker flexibility for {compound}",
            context=ctx.to_dict(),
            gold_event_ids=[f"GOLD-{i:03d}"],
        ))

    # ── distractors: same entities/vocabulary, mismatched context ───────────
    for j in range(n_distractors):
        ctx = ProtacContext(
            project="scale",
            target_gene="BRD4", e3_ligase="VHL",
            cell_line=CELLS[j % len(CELLS)],
            assay_type="degradation assay", experiment_type="degradation_assay",
            endpoint=ENDPOINTS[j % len(ENDPOINTS)],
            compound_id=f"D{j:04d}", linker_type=LINKERS[j % len(LINKERS)],
        )
        specs.append(MemorySpec(
            event_id=f"DIST-{j:05d}",
            title=f"BRD4 VHL degradation dmax linker flexibility observation D{j:04d}",
            content=f"Background observation of BRD4 VHL degradation assay dmax and linker "
                    f"flexibility for an unrelated series ({CELLS[j % len(CELLS)]}).",
            context=ctx.to_dict(),
        ))

    # ── decoys: same entities + strong signals, but a different project ─────
    for j in range(n_decoy):
        ctx = ProtacContext(
            project="decoy",
            target_gene="BRD4", e3_ligase="VHL", cell_line="HEK293",
            assay_type="degradation assay", experiment_type="degradation_assay",
            endpoint="dmax", compound_id=f"X{j:04d}", linker_type=LINKERS[j % len(LINKERS)],
        )
        specs.append(MemorySpec(
            event_id=f"DECOY-{j:05d}",
            title=f"BRD4 VHL degradation dmax linker flexibility high-confidence X{j:04d}",
            content="Extremely strong BRD4 VHL degradation dmax linker flexibility result "
                    "from an unrelated programme.",
            context=ctx.to_dict(),
            project="decoy",
            evidence_strength=0.95, confidence=0.95, memory_strength=1.0, goal_relevance=0.95,
        ))

    # ── filler: other targets, no BRD4/VHL entity overlap ───────────────────
    n_filler = max(0, n_total - len(specs))
    for k in range(n_filler):
        target = TARGETS[1 + (k % (len(TARGETS) - 1))]
        ctx = ProtacContext(
            project="scale",
            target_gene=target, e3_ligase=E3S[k % len(E3S)],
            cell_line=CELLS[k % len(CELLS)],
            assay_type="degradation assay", compound_id=f"F{k:05d}",
        )
        specs.append(MemorySpec(
            event_id=f"FILL-{k:05d}",
            title=f"{target} degrader study {k}",
            content=f"Literature note for {target} with {E3S[k % len(E3S)]} in "
                    f"{CELLS[k % len(CELLS)]}; unrelated programme.",
            context=ctx.to_dict(),
        ))
    return specs, queries


def ingest_fast(mem: CognitiveMemory, project_id: str, specs: list[MemorySpec]) -> None:
    """Direct store writes (no attentional gate) so 10k memories stay fast.

    This is a *fixture loader*, not the production write path; it populates the
    same tables (traces + episodic satellite + entity links + context) so the
    real retrieval pipeline is exercised unchanged. Each spec may target its own
    project (``project_id`` is the default).
    """
    store = mem.store
    projects: dict[str, str] = {project_id: project_id}
    for spec in specs:
        target_project = projects.get(spec.project)
        if target_project is None:
            target_project = mem.ensure_project(spec.project)
            projects[spec.project] = target_project
        ctx = ProtacContext.from_dict(spec.context)
        fingerprint = ctx.fingerprint()
        entities = detect_entities(ctx)
        trace_id = store.add_episode(
            title=spec.title,
            content=spec.content,
            event_type="degradation_assay",
            project_id=target_project,
            context=spec.context,
            context_fingerprint=fingerprint,
            status="active",
            evidence_strength=spec.evidence_strength,
            confidence=spec.confidence,
            memory_strength=spec.memory_strength,
            goal_relevance=spec.goal_relevance,
            search_context=" ".join(filter(None, [ctx.target_gene, ctx.e3_ligase, ctx.cell_line])),
            search_entities=entity_search_text(entities),
        )
        for ref in entities:
            store.link_memory_entity(trace_id, ref)
        spec.trace_id = trace_id


def _rank_metrics(ranked_ids: list[str], gold: set[str], k: int) -> tuple[float, float, float]:
    import math

    recall = 1.0 if any(mid in gold for mid in ranked_ids[:k]) else 0.0
    mrr = 0.0
    for rank, mid in enumerate(ranked_ids, start=1):
        if mid in gold:
            mrr = 1.0 / rank
            break
    gains = [1.0 if mid in gold else 0.0 for mid in ranked_ids[:k]]
    dcg = sum(g / math.log2(i + 1) for i, g in enumerate(gains, start=1))
    ideal_hits = int(min(sum(gains), k))
    ideal = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_hits + 1))
    ndcg = dcg / ideal if ideal else 0.0
    return recall, mrr, ndcg


def run_condition(
    specs: list[MemorySpec],
    queries: list[ScaleQuery],
    *,
    enabled: bool,
    k: int = 5,
) -> dict[str, Any]:
    config = MemoryConfig(
        candidates=CandidateConfig(enabled=enabled, context_gate=enabled),
        max_search_results=k,
    )
    mem = CognitiveMemory.in_memory(config)
    project = mem.ensure_project("scale")
    ingest_start = time.perf_counter()
    ingest_fast(mem, project, specs)
    ingest_ms = (time.perf_counter() - ingest_start) * 1000.0

    rows: list[dict[str, Any]] = []
    by_event = {spec.event_id: spec.trace_id for spec in specs}
    for query in queries:
        query.gold_trace_ids = [by_event[e] for e in query.gold_event_ids if by_event.get(e)]
    for query in queries:
        gold = set(query.gold_trace_ids)
        start = time.perf_counter()
        response = mem.search(
            query.text, project_id=project, context=query.context, limit=k
        )
        latency_ms = (time.perf_counter() - start) * 1000.0
        ranked = [hit.id for hit in response.hits]
        recall, mrr, ndcg = _rank_metrics(ranked, gold, k)
        assembled = "\n".join(f"{h.memory.get('title','')} {h.memory.get('content','')}" for h in response.hits)
        rows.append({
            "qid": query.qid,
            "query": query.text,
            "query_context": query.context,
            "expected_memory": sorted(gold),
            "recall@k": recall,
            "mrr": mrr,
            "ndcg@k": ndcg,
            "latency_ms": latency_ms,
            "tokens": estimate_tokens(assembled),
            "retrieved_ids": ranked,
            "gold_rank": next((i for i, mid in enumerate(ranked, 1) if mid in gold), None),
            "candidate_total": response.generator_counts.get("entity_total", 0),
            "candidate_kept": response.generator_counts.get("entity", 0),
            "candidate_gated": response.generator_counts.get("entity_gated", 0),
            "candidate_lexical": response.generator_counts.get("lexical", 0),
        })
    mem.close()

    def mean(key: str) -> float:
        return sum(r[key] for r in rows) / len(rows) if rows else 0.0

    return {
        "condition": "after_bounded" if enabled else "before_unbounded",
        "n_memories": len(specs),
        "n_queries": len(queries),
        "ingest_latency_ms": ingest_ms,
        "aggregate": {
            "recall@k": mean("recall@k"),
            "mrr": mean("mrr"),
            "ndcg@k": mean("ndcg@k"),
            "mean_latency_ms": mean("latency_ms"),
            "mean_tokens": mean("tokens"),
            "mean_candidate_total": mean("candidate_total"),
            "mean_candidate_kept": mean("candidate_kept"),
            "mean_candidate_gated": mean("candidate_gated"),
        },
        "questions": rows,
    }


def run_all(
    *,
    n_total: int = 10_000,
    n_gold: int = 12,
    n_distractors: int = 1_500,
    n_decoy: int = 1_500,
    k: int = 5,
    seed: int = 7,
) -> dict[str, Any]:
    set_deterministic_ids(True)
    specs, queries = build_corpus(
        n_total=n_total, n_gold=n_gold, n_distractors=n_distractors,
        n_decoy=n_decoy, seed=seed,
    )
    before = run_condition(specs, queries, enabled=False, k=k)
    after = run_condition(specs, queries, enabled=True, k=k)
    return {
        "benchmark": "bounded_candidate_generation",
        "n_total": n_total,
        "n_gold": n_gold,
        "n_distractors": n_distractors,
        "n_decoy": n_decoy,
        "k": k,
        "seed": seed,
        "conditions": {"before_unbounded": before, "after_bounded": after},
        "delta": {
            metric: after["aggregate"][metric] - before["aggregate"][metric]
            for metric in before["aggregate"]
        },
    }


def write_results(results: dict[str, Any], outdir: Path = RESULTS_DIR) -> dict[str, Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    json_path = outdir / "bounded_candidates.json"
    csv_path = outdir / "bounded_candidates.csv"
    md_path = outdir / "BOUNDED_CANDIDATES_REPORT.md"
    json_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")

    metrics = list(results["conditions"]["before_unbounded"]["aggregate"])
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["condition", *metrics])
        for name, cond in results["conditions"].items():
            writer.writerow([name, *[round(cond["aggregate"][m], 4) for m in metrics]])

    md_path.write_text(render_report(results), encoding="utf-8")
    return {"json": json_path, "csv": csv_path, "md": md_path}


def render_report(results: dict[str, Any]) -> str:
    names = list(results["conditions"])
    metrics = list(results["conditions"][names[0]]["aggregate"])
    lines = [
        "# Bounded Candidate Generation — Before/After",
        "",
        f"- Corpus: {results['n_total']} memories "
        f"({results['n_gold']} gold, {results['n_distractors']} entity-overlap distractors)",
        f"- Queries: {results['conditions']['before_unbounded']['n_queries']}"
        f"  |  k = {results['k']}  |  seed = {results['seed']}",
        "- Only candidate generation changes; corpus, queries, reranker and context are identical.",
        "",
        "## Aggregate metrics",
        "",
        "| metric | before (unbounded) | after (bounded) | Δ |",
        "|---|---|---|---|",
    ]
    for m in metrics:
        b = results["conditions"]["before_unbounded"]["aggregate"][m]
        a = results["conditions"]["after_bounded"]["aggregate"][m]
        lines.append(f"| {m} | {b:.4f} | {a:.4f} | {a - b:+.4f} |")
    lines += [
        "",
        "## Interpretation",
        "",
        "- `mean_candidate_total` → `mean_candidate_kept` shows the bounding effect;",
        "  `mean_candidate_gated` counts entity-only candidates dropped for sharing no",
        "  known context coordinate with the query.",
        "- Bounding must **not** reduce Recall@k. A large drop in `mean_latency_ms`",
        "  with equal-or-better ranking metrics is the intended outcome.",
        "- This is a synthetic scale corpus; the same harness is the before/after",
        "  evidence the brief requires, not a claim about real-world PROTAC data.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:  # pragma: no cover
    parser = argparse.ArgumentParser(description="Bounded candidate generation before/after")
    parser.add_argument("--n", type=int, default=10_000, help="total memories")
    parser.add_argument("--gold", type=int, default=12)
    parser.add_argument("--distractors", type=int, default=1_500)
    parser.add_argument("--decoy", type=int, default=1_500, help="cross-project decoy memories")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--quick", action="store_true", help="small fast run")
    args = parser.parse_args()
    if args.quick:
        args.n, args.gold, args.distractors, args.decoy = 600, 6, 150, 150
    results = run_all(
        n_total=args.n, n_gold=args.gold, n_distractors=args.distractors,
        n_decoy=args.decoy, k=args.k,
    )
    paths = write_results(results)
    print(f"Bounded candidate generation — {results['n_total']} memories")
    print(f"{'metric':24s} {'before':>12s} {'after':>12s} {'delta':>12s}")
    for m, d in results["delta"].items():
        b = results["conditions"]["before_unbounded"]["aggregate"][m]
        a = results["conditions"]["after_bounded"]["aggregate"][m]
        print(f"{m:24s} {b:12.4f} {a:12.4f} {d:+12.4f}")
    print("written:", ", ".join(str(p) for p in paths.values()))


if __name__ == "__main__":  # pragma: no cover
    main()

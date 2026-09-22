"""Performance harness (Master Prompt §48).

Measures deterministic database / retrieval / cognitive-operation latency
separately from any model-dependent cost. There is no LLM in the loop here, so
every number is a *deterministic subsystem* number and must not be reported as
end-to-end agent latency.

Run:

    PYTHONPATH=src python -m benchmarks.performance
    PYTHONPATH=src python -m benchmarks.performance --include-50k

Outputs:

    benchmarks/results/performance.json
    benchmarks/results/performance.csv
    benchmarks/results/PERFORMANCE_REPORT.md
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from protacpilot_memory import CognitiveMemory
from protacpilot_memory.mcp.tools import CogToolRegistry
from protacpilot_memory.util import set_deterministic_ids

RESULTS_DIR = Path(__file__).resolve().parent / "results"
DEFAULT_SIZES = [100, 1000, 10000]
LARGE_SIZES = [50000]


# ── statistics ───────────────────────────────────────────────────────────────
def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (pct / 100.0) * (len(ordered) - 1)
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (rank - low)


def summarise(samples_ms: list[float]) -> dict[str, float]:
    if not samples_ms:
        return {"n": 0, "min_ms": 0.0, "median_ms": 0.0, "p95_ms": 0.0, "max_ms": 0.0}
    return {
        "n": len(samples_ms),
        "min_ms": min(samples_ms),
        "median_ms": statistics.median(samples_ms),
        "p95_ms": _percentile(samples_ms, 95),
        "max_ms": max(samples_ms),
    }


def _time_ms(fn: Callable[[], Any]) -> float:
    start = time.perf_counter()
    fn()
    return (time.perf_counter() - start) * 1000.0


def _time_samples(fn: Callable[[], Any], trials: int) -> list[float]:
    return [_time_ms(fn) for _ in range(trials)]


# ── synthetic corpus ─────────────────────────────────────────────────────────
_TARGETS = ["BRD4", "BRD2", "BRD9", "SMARCA2", "AR", "KRAS", "BTK", "IRAK4", "EGFR", "WDR5"]
_E3S = ["VHL", "CRBN", "IAP", "MDM2"]
_CELLS = ["HEK293", "MV4-11", "MOLT4", "PC3"]


def _populate(mem: CognitiveMemory, project: str, n: int) -> list[float]:
    """Ingest n synthetic events, returning per-event encode latency (ms)."""
    latencies: list[float] = []
    for i in range(n):
        target = _TARGETS[i % len(_TARGETS)]
        e3 = _E3S[(i // len(_TARGETS)) % len(_E3S)]
        cell = _CELLS[i % len(_CELLS)]
        start = time.perf_counter()
        mem.save_episode(
            title=f"perf event {i} {target} {e3}",
            content=f"Synthetic observation {i}: {target} degrader recruiting {e3} in {cell} "
                    f"with dmax={0.2 + (i % 7) * 0.05:.2f}.",
            event_type="degradation_assay",
            project_id=project,
            context={"target_gene": target, "e3_ligase": e3, "cell_line": cell,
                     "assay_type": "degradation assay"},
            observed={"dmax": round(0.2 + (i % 7) * 0.05, 2)},
            evidence=[{"evidence_type": "internal_experiment", "experiment_id": f"PERF-{i}"}],
            decision_impact=0.7, goal_relevance=0.6,
        )
        latencies.append((time.perf_counter() - start) * 1000.0)
    return latencies


def _queries() -> list[str]:
    return [
        "BRD4 VHL degradation dmax",
        "CRBN recruiter permeability",
        "linker geometry ternary complex",
        "SMARCA2 degrader HEK293",
        "KRAS PROTAC selectivity",
        "BRD9 compound series",
        "MV4-11 degradation assay",
        "IAP E3 ligand",
    ]


def measure_size(n_events: int, *, trials: int = 20) -> dict[str, Any]:
    set_deterministic_ids(True)
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / f"perf_{n_events}.db"
        mem = CognitiveMemory.open(db_path)
        project = mem.ensure_project("perf")
        registry = CogToolRegistry(mem)

        encode_latencies = _populate(mem, project, n_events)
        queries = _queries()

        fts_samples: list[float] = []
        hybrid_samples: list[float] = []
        context_samples: list[float] = []
        mcp_samples: list[float] = []
        for i in range(trials):
            q = queries[i % len(queries)]
            fts_samples.append(_time_ms(lambda q=q: mem.store.search_fts(q, project_id=project, limit=20)))
            hybrid_samples.append(_time_ms(lambda q=q: mem.search(q, project_id=project, limit=10)))
            context_samples.append(_time_ms(lambda: mem.context(project)))
            mcp_samples.append(_time_ms(lambda q=q: registry.call("cog_search", {"query": q, "project_id": project, "limit": 10})))

        consolidation_ms = _time_ms(lambda: mem.consolidate(project))
        replay_ms = _time_ms(lambda: mem.replay(project, trigger="manual"))
        reconsolidation_ms = _time_ms(lambda: mem.reconsolidation.run(project))

        assembled = mem.retriever.render_context(project)
        tokens = int(math.ceil(len(assembled) / 4.0))
        size_bytes = mem.db.size_bytes()
        stats = mem.stats()
        mem.close()

    return {
        "n_events": n_events,
        "db_size_bytes": size_bytes,
        "db_size_mb": round(size_bytes / (1024 * 1024), 3),
        "bytes_per_event": round(size_bytes / n_events, 1) if n_events else 0.0,
        "encode": summarise(encode_latencies),
        "fts_retrieval": summarise(fts_samples),
        "hybrid_retrieval": summarise(hybrid_samples),
        "context_assembly": summarise(context_samples),
        "mcp_roundtrip": summarise(mcp_samples),
        "consolidation_ms": consolidation_ms,
        "replay_ms": replay_ms,
        "reconsolidation_ms": reconsolidation_ms,
        "session_context_tokens": tokens,
        "semantic_memories": stats.get("semantic_memories", 0),
        "total_memories": stats.get("total_memories", 0),
    }


def run_all(sizes: list[int] | None = None, trials: int = 20) -> dict[str, Any]:
    sizes = sizes or DEFAULT_SIZES
    return {
        "benchmark": "performance",
        "sizes": sizes,
        "trials": trials,
        "note": (
            "All latencies are deterministic subsystem measurements (no LLM). "
            "They must not be reported as end-to-end agent latency."
        ),
        "results": [measure_size(n, trials=trials) for n in sizes],
    }


# ── output writers ───────────────────────────────────────────────────────────
LATENCY_FIELDS = ["encode", "fts_retrieval", "hybrid_retrieval", "context_assembly", "mcp_roundtrip"]


def write_results(results: dict[str, Any], outdir: Path = RESULTS_DIR) -> dict[str, Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    json_path = outdir / "performance.json"
    csv_path = outdir / "performance.csv"
    md_path = outdir / "PERFORMANCE_REPORT.md"

    json_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")

    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow([
            "n_events", "db_size_mb", "bytes_per_event",
            *[f"{field}_{stat}" for field in LATENCY_FIELDS for stat in ("median_ms", "p95_ms")],
            "consolidation_ms", "replay_ms", "reconsolidation_ms",
            "session_context_tokens", "semantic_memories",
        ])
        for row in results["results"]:
            writer.writerow([
                row["n_events"], row["db_size_mb"], row["bytes_per_event"],
                *[round(row[field][stat], 3) for field in LATENCY_FIELDS for stat in ("median_ms", "p95_ms")],
                round(row["consolidation_ms"], 3), round(row["replay_ms"], 3),
                round(row["reconsolidation_ms"], 3), row["session_context_tokens"],
                row["semantic_memories"],
            ])

    md_path.write_text(render_report(results), encoding="utf-8")
    return {"json": json_path, "csv": csv_path, "md": md_path}


def render_report(results: dict[str, Any]) -> str:
    lines = [
        "# Performance Report — PROTACpilot Cognitive Memory",
        "",
        "> Every latency below is a **deterministic subsystem** measurement. No LLM",
        "> is in the loop, so these are *not* end-to-end agent latencies. Percentiles",
        f"> are over {results['trials']} trials (retrieval/context) or all encode events.",
        "",
        "## Latency by memory size (ms)",
        "",
        "| N | encode median | encode p95 | FTS median | FTS p95 | hybrid median | hybrid p95 "
        "| context median | context p95 | MCP median | MCP p95 | consolidate | replay | reconsolidate |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in results["results"]:
        cells = [
            row["encode"]["median_ms"], row["encode"]["p95_ms"],
            row["fts_retrieval"]["median_ms"], row["fts_retrieval"]["p95_ms"],
            row["hybrid_retrieval"]["median_ms"], row["hybrid_retrieval"]["p95_ms"],
            row["context_assembly"]["median_ms"], row["context_assembly"]["p95_ms"],
            row["mcp_roundtrip"]["median_ms"], row["mcp_roundtrip"]["p95_ms"],
            row["consolidation_ms"], row["replay_ms"], row["reconsolidation_ms"],
        ]
        lines.append(f"| {row['n_events']} | " + " | ".join(f"{c:.2f}" for c in cells) + " |")

    lines += [
        "",
        "## Storage and context budget",
        "",
        "| N | DB size (MB) | bytes/event | session context tokens | semantic memories |",
        "|---|---|---|---|---|",
    ]
    for row in results["results"]:
        lines.append(
            f"| {row['n_events']} | {row['db_size_mb']} | {row['bytes_per_event']} | "
            f"{row['session_context_tokens']} | {row['semantic_memories']} |"
        )

    lines += [
        "",
        "## Interpretation notes",
        "",
        "- Encode latency includes the attentional gate, dedupe check, entity linking",
        "  and FTS indexing; it is the dominant write-path cost.",
        "- FTS retrieval is pure SQLite FTS5/BM25. Hybrid retrieval adds entity-overlap,",
        "  relation-graph expansion, optional semantic scoring and component reranking.",
        "- MCP round-trip wraps the registry call (argument marshalling + hybrid search).",
        "- Consolidation/replay/reconsolidation are single operations over the whole",
        "  project and are reported as one measurement, not per-memory.",
        "- 50k-event runs are opt-in (`--include-50k`) because ingestion is O(N) writes",
        "  and can take minutes.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:  # pragma: no cover
    parser = argparse.ArgumentParser(description="Cognitive memory performance harness")
    parser.add_argument("--include-50k", action="store_true", help="also run the 50,000-event size")
    parser.add_argument("--trials", type=int, default=20)
    args = parser.parse_args()
    sizes = DEFAULT_SIZES + (LARGE_SIZES if args.include_50k else [])
    results = run_all(sizes=sizes, trials=args.trials)
    paths = write_results(results)
    print(f"Performance harness: sizes={sizes} trials={args.trials}")
    print(f"{'N':>8} {'enc_med':>9} {'fts_med':>9} {'hyb_med':>9} {'ctx_med':>9} {'mcp_med':>9} {'MB':>8}")
    for row in results["results"]:
        print(f"{row['n_events']:>8} {row['encode']['median_ms']:>9.2f} "
              f"{row['fts_retrieval']['median_ms']:>9.2f} {row['hybrid_retrieval']['median_ms']:>9.2f} "
              f"{row['context_assembly']['median_ms']:>9.2f} {row['mcp_roundtrip']['median_ms']:>9.2f} "
              f"{row['db_size_mb']:>8.3f}")
    print("written:", ", ".join(str(p) for p in paths.values()))


if __name__ == "__main__":  # pragma: no cover
    main()

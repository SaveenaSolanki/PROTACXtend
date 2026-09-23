#!/usr/bin/env python
"""Host-benchmark delta: ingest PROTACXtend run records into cognitive memory.

This is the measurement companion to
``protacxtend/memory/cognitive_bridge.py`` (Master Prompt §46 Benchmark H /
§47 ablations).  It replays canonical host run artifacts through the adapter
and reports what memory buys you on the *host's own* records:

  * ingestion coverage   — runs / episodes / failure memories / predictions
  * self-recall@k + MRR  — can a run's own memory be retrieved from its objective?
  * context top-1        — does the scientific context pick the right run?
  * context-off ablation — the same query with context reranking disabled
  * latency / size       — encode and search cost, database footprint

Run it from the repo root::

    PYTHONPATH=protacpilot-memory/src python protacpilot-memory/benchmarks/host_bridge_delta.py
    python protacpilot-memory/benchmarks/host_bridge_delta.py --limit 20 --k 5 --json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
MEM_SRC = Path(__file__).resolve().parents[1] / "src"
for _p in (str(REPO_ROOT), str(MEM_SRC)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _rank_of(results: list[dict[str, Any]], target_id: str | None) -> int | None:
    if not target_id:
        return None
    for i, hit in enumerate(results, start=1):
        if hit.get("id") == target_id:
            return i
    return None


def _load_run_paths(args: argparse.Namespace) -> list[Path]:
    if args.runs:
        paths = [Path(p) for p in args.runs]
    else:
        paths = sorted((REPO_ROOT / "outputs" / "runs").glob("*/run.json"))
    paths = [p for p in paths if p.is_file()]
    if args.limit:
        paths = paths[: args.limit]
    return paths


def run(args: argparse.Namespace) -> dict[str, Any]:
    from protacxtend.memory.cognitive_bridge import (
        available,
        host_context_from_record,
        open_bridge,
    )

    if not available():
        raise SystemExit(
            "protacpilot_memory is not importable. Install it with "
            "`pip install -e protacpilot-memory` or set PYTHONPATH=protacpilot-memory/src"
        )

    bridge = open_bridge(project_name=args.project)
    paths = _load_run_paths(args)

    episode_by_run: dict[str, str] = {}
    failures_by_run: dict[str, list[str]] = {}
    context_by_run: dict[str, dict[str, Any]] = {}
    objective_by_run: dict[str, str] = {}
    encode_s = 0.0
    n_predictions = 0

    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        run_id = data.get("run_id") or path.parent.name
        t0 = time.perf_counter()
        out = bridge.ingest_run_record(data, predictions=args.predictions)
        encode_s += time.perf_counter() - t0
        ep = (out.get("episode") or {}).get("episode_id")
        if ep:
            episode_by_run[run_id] = ep
        fails = [f.get("episode_id") for f in out.get("failure_episodes", []) if f.get("episode_id")]
        if fails:
            failures_by_run[run_id] = fails
        context_by_run[run_id] = host_context_from_record(data)
        objective_by_run[run_id] = data.get("user_objective") or run_id
        n_predictions += out.get("n_predictions", 0)

    # ── retrieval probes ─────────────────────────────────────────────────────
    ranks: list[int] = []
    context_top1 = 0
    context_top1_off = 0
    probes = 0
    search_s = 0.0
    failure_hits = 0
    failure_probes = 0

    for run_id, episode_id in episode_by_run.items():
        query = objective_by_run.get(run_id) or run_id
        ctx = context_by_run.get(run_id)

        t0 = time.perf_counter()
        with_ctx = bridge.retrieve(query, host_context=ctx, limit=args.k)
        search_s += time.perf_counter() - t0

        rank = _rank_of(with_ctx.get("results", []), episode_id)
        if rank is not None:
            ranks.append(rank)
        probes += 1

        top1 = (with_ctx.get("results") or [{}])[0].get("id")
        if top1 == episode_id:
            context_top1 += 1

        no_ctx = bridge.retrieve(query, host_context=None, limit=args.k)
        top1_off = (no_ctx.get("results") or [{}])[0].get("id")
        if top1_off == episode_id:
            context_top1_off += 1

        if run_id in failures_by_run:
            failure_probes += 1
            fq = f"failed experiment repair {query}"
            fres = bridge.retrieve(fq, host_context=ctx, limit=args.k)
            returned = {h.get("id") for h in fres.get("results", [])}
            if returned & set(failures_by_run[run_id]):
                failure_hits += 1

    stats = bridge.stats()
    n = max(1, probes)
    recall_at_k = len(ranks) / n
    mrr = statistics.fmean(1.0 / r for r in ranks) if ranks else 0.0

    report = {
        "runs_requested": len(paths),
        "runs_ingested": len(episode_by_run),
        "episodes": stats.get("episodes"),
        "negative_episodes": stats.get("negative_episodes"),
        "predictions": stats.get("predictions"),
        "predictions_added": n_predictions,
        "db_size_bytes": stats.get("db_size_bytes"),
        "k": args.k,
        "self_recall_at_k": round(recall_at_k, 4),
        "mrr": round(mrr, 4),
        "context_top1": round(context_top1 / n, 4),
        "context_top1_off_ablation": round(context_top1_off / n, 4),
        "context_top1_delta": round((context_top1 - context_top1_off) / n, 4),
        "failure_recall_at_k": round(failure_hits / failure_probes, 4) if failure_probes else None,
        "failure_probes": failure_probes,
        "mean_search_ms": round(1000 * search_s / n, 3),
        "total_encode_ms": round(1000 * encode_s, 2),
        "predictions_enabled": bool(args.predictions),
    }
    bridge.close()
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Host-benchmark delta for cognitive memory")
    parser.add_argument("--runs", nargs="*", help="explicit run.json paths")
    parser.add_argument("--limit", type=int, default=50, help="max runs to ingest (0 = all)")
    parser.add_argument("--k", type=int, default=5, help="retrieval depth for recall@k")
    parser.add_argument("--project", default="host-delta", help="cognitive-memory project name")
    parser.add_argument("--predictions", dest="predictions", action="store_true", default=True)
    parser.add_argument("--no-predictions", dest="predictions", action="store_false")
    parser.add_argument("--json", action="store_true", help="emit JSON only")
    args = parser.parse_args()
    if args.limit == 0:
        args.limit = None

    report = run(args)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return

    print("Host-bridge cognitive-memory delta")
    print("=" * 40)
    width = max(len(k) for k in report)
    for key, value in report.items():
        print(f"{key:<{width}} : {value}")


if __name__ == "__main__":
    main()

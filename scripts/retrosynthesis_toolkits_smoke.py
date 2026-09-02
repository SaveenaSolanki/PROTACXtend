#!/usr/bin/env python3
"""
Retrosynthesis toolkits smoke/evidence runner — ASKCOS / AiZynthFinder /
RDKit + OpenNMT as working toolkits in PROTACpilot.

Produces honest per-engine evidence under outputs/retrosynthesis_toolkits/:

  * engine status report (availability + machine reasons, never fabricated)
  * per-engine run outcome for a probe molecule (default: aspirin)
  * multi-engine merged summary

Usage:
  python scripts/retrosynthesis_toolkits_smoke.py --smiles "CC(=O)Oc1ccccc1C(=O)O"
  python scripts/retrosynthesis_toolkits_smoke.py --engines aizynth,openmt   # offline/local only
  python scripts/retrosynthesis_toolkits_smoke.py --tree-search --offline    # status-only evidence

Exit code 0 even when engines are unavailable (evidence is honest, not rosy).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from synglue_agent.tools.retrosynthesis_engines import (  # noqa: E402
    ENGINE_CODES,
    engine_status_report,
    render_engine_status_report,
    run_engines,
)

DEFAULT_OUT = ROOT / "outputs" / "retrosynthesis_toolkits"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--smiles", default="CC(=O)Oc1ccccc1C(=O)O",
                    help="probe molecule (default aspirin)")
    ap.add_argument("--engines", default="askcos",
                    help="comma-separated engine codes (" + ",".join(ENGINE_CODES) + "); default askcos (live one-step)")
    ap.add_argument("--tree-search", action="store_true",
                    help="askcos engine: run full Retro* tree search (slower)")
    ap.add_argument("--no-buyables", action="store_true",
                    help="askcos engine: skip the buyables check on the top precursor")
    ap.add_argument("--offline", action="store_true",
                    help="never touch the network (status report only for askcos)")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="evidence output dir")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    engines = [e.strip() for e in args.engines.split(",") if e.strip()]

    evidence: dict = {
        "task": "retrosynthesis toolkit engines (working-toolkit evidence)",
        "smiles": args.smiles,
        "engines_requested": engines,
        "offline": args.offline,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }

    # 1. status report (honest availability)
    evidence["status_report"] = engine_status_report(skip_network=args.offline)
    print(render_engine_status_report(skip_network=args.offline))

    # 2. per-engine runs
    if not args.offline:
        askcos_mode = "tree" if args.tree_search else "one_step"
        summary = run_engines(
            args.smiles,
            engines=engines,
            askcos_mode=askcos_mode,
            askcos_check_buyables=not args.no_buyables,
        )
        evidence["summary"] = summary.model_dump()
        print("\nMerged multi-engine result:")
        print(f"  requested : {summary.engines_requested}")
        print(f"  available : {summary.engines_available}")
        print(f"  ran       : {summary.engines_ran}")
        print(f"  route     : {'FOUND via ' + summary.best_engine if summary.any_route_found else 'none'}")
        print(f"  routes    : {summary.routes}")
        print(f"  purchasable fraction: {summary.purchasable_fraction}")
        for o in summary.outcomes:
            status = "OK" if o.ran else f"UNAVAILABLE ({o.tool_failed})"
            print(f"  - {o.engine:7s} available={o.available} ran={o.ran} "
                  f"route_found={o.route_found} [{status}] latency={o.latency_s}s")

    report_path = out_dir / "evidence.json"
    report_path.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(f"\nEvidence written: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

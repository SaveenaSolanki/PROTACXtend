#!/usr/bin/env python3
"""Stage dispatcher for the full scientific-validation run.

Usage:
    python scripts/validation/run_stage.py <stage> [options]

Stages
------
freeze          write/refresh the frozen benchmark manifests
docking_shards  run the sharded 3-engine redocking benchmark + consensus
docking_merge   merge shards into the final docking summary
docking         single-process docking benchmark (small n / debugging)
pocket          expanded pocket benchmark
ppi             PPI LightDock + DockQ benchmark
ternary         ternary/PROTAC validation
energetics      GAFF2 MM/GBSA
fallback        real fallback execution test
reproducibility across-seed repeatability
runtime         runtime/resource consolidation
services        live remote-service verification
crosswalk       408 vs 367 component reconciliation
dimensions      capability-dimension matrix
claims          machine-readable claim table
figures         all validation figures
live_probe      live agent-tool/backend probe (sota/closure)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--shards", type=int, default=3)
    parser.add_argument("--seeds", type=int, default=3)
    args = parser.parse_args()
    stage = args.stage
    limit = args.limit or None

    if stage == "freeze":
        from protacxtend.validation.datasets import freeze_all
        print(freeze_all())
    elif stage == "docking":
        from protacxtend.validation import docking
        docking.run(limit=limit)
    elif stage == "docking_merge":
        from protacxtend.validation import docking
        out = ROOT / "results" / "benchmarks" / "docking"
        shard_dirs = sorted(out.glob("shard_*"))
        docking.merge(shard_dirs, out_dir=out)
    elif stage == "docking_shards":
        import json
        import subprocess
        from concurrent.futures import ThreadPoolExecutor
        from pathlib import Path

        from rdkit import Chem

        from protacxtend.validation.datasets import load

        complexes = load("docking_v1")["complexes"]
        out = ROOT / "results" / "benchmarks" / "docking"
        logs = out / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        cache = ROOT / "benchmark" / "frozen_cache"
        sizes = {}
        for f in cache.glob("*_crystal.sdf"):
            try:
                m = [x for x in Chem.SDMolSupplier(str(f), removeHs=True, sanitize=False) if x][0]
                sizes[f.stem.replace("_crystal", "")] = m.GetNumHeavyAtoms()
            except Exception:
                pass
        known = [c for c in complexes if c in sizes]
        known.sort(key=lambda c: sizes[c])
        diffdock_subset = known[:20]

        def _launch(name, engines, comps, gpu, extra_config=None):
            comp_file = Path("/tmp") / f"{name}_comps.json"
            comp_file.write_text(json.dumps(comps))
            driver = out / f"_driver_{name}.py"
            cfg = f"docking.ENGINE_CONFIG['diffdock']={extra_config}\n" if extra_config else ""
            driver.write_text(
                "import sys, os, json\n"
                f"sys.path.insert(0, {str(ROOT)!r})\n"
                f"os.environ['CUDA_VISIBLE_DEVICES']={gpu!r}\n"
                "from protacxtend.validation import docking\n"
                + cfg
                + f"comps=json.load(open({str(comp_file)!r}))\n"
                + f"docking.run(complexes=comps, engines={engines!r}, "
                  f"out_dir={str(out / name)!r}, tag={name!r})\n")
            with (logs / f"{name}.log").open("w") as fh:
                subprocess.run([sys.executable, "-u", str(driver)], cwd=str(ROOT),
                               stdout=fh, stderr=subprocess.STDOUT)

        def _primary():
            _launch("primary2", ["vina", "gnina"], complexes, "1")

        def _diffdock():
            _launch("diffdock2", ["diffdock"], diffdock_subset, "0",
                    {"n_poses": 5, "inference_steps": 10, "timeout": 2400})

        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda f: f(), [_primary, _diffdock]))
    elif stage == "docking_merge":
        import json

        from protacxtend.validation import docking
        from protacxtend.validation.io import write_summary_json

        base = ROOT / "results" / "benchmarks" / "docking"
        p2 = json.loads((base / "primary2/docking_summary_primary2.json").read_text())
        dd_payload = json.loads((base / "diffdock2/docking_rows_diffdock2.json").read_text())
        dd_rows = [r for r in dd_payload["rows"] if r.get("timestamp")]
        seen = set()
        dd = []
        for r in dd_rows:
            key = (r.get("structure_id"), r.get("engine"))
            if key in seen:
                continue
            seen.add(key)
            dd.append(r)
        dd_summary = docking._summary(dd, [], len({r["structure_id"] for r in dd}))
        docking.recompute_consensus(base / "primary2", base / "diffdock2", out_dir=base)
        cons = json.loads((base / "consensus_summary.json").read_text())
        final = {
            "dataset": "docking_v1", "n_curated_attempted": p2.get("n_curated_attempted"),
            "n_complexes_with_results": p2.get("n_complexes_with_results"),
            "n_failures": p2.get("n_failures"), "failure_outcomes": p2.get("failure_outcomes"),
            "host": p2.get("host"), "vina": p2.get("vina"), "gnina": p2.get("gnina"),
            "diffdock": dd_summary.get("diffdock"),
            "prospective_consensus": cons.get("two_engine"),
            "consensus_three_engine": cons.get("three_engine"),
            "oracle": p2.get("oracle"),
            "notes": "DiffDock run on the 20-complex sub-benchmark; three-engine consensus "
                     "coverage = " + str((cons.get("three_engine") or {}).get("n_with_pose")),
        }
        write_summary_json(base / "docking_summary.json", final)
    elif stage == "pocket":
        from protacxtend.validation import pocket
        pocket.run(limit=limit)
    elif stage == "ppi":
        from protacxtend.validation import ppi
        ppi.run(limit=limit)
    elif stage == "ternary":
        from protacxtend.validation import ternary
        ternary.run(limit=limit)
    elif stage == "energetics":
        from protacxtend.validation import energetics
        energetics.run(limit=limit)
    elif stage == "fallback":
        from protacxtend.validation import fallback
        fallback.run()
    elif stage == "reproducibility":
        from protacxtend.validation import reproducibility
        reproducibility.run(limit=limit or 5, seeds=args.seeds)
    elif stage == "runtime":
        from protacxtend.validation import runtime
        runtime.run()
    elif stage == "services":
        from protacxtend.validation import services
        services.run()
    elif stage == "crosswalk":
        from protacxtend.validation import crosswalk
        crosswalk.run()
    elif stage == "dimensions":
        from protacxtend.validation import dimensions
        dimensions.run()
    elif stage == "claims":
        from protacxtend.validation import claims
        claims.run()
    elif stage == "figures":
        from protacxtend.validation import figures
        figures.run()
    elif stage == "report":
        from protacxtend.validation import report
        report.run()
    elif stage == "live_probe":
        import subprocess
        subprocess.run([sys.executable, str(ROOT / "sota/closure/live_capability_probe.py")], cwd=str(ROOT))
    else:
        parser.error(f"unknown stage: {stage}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

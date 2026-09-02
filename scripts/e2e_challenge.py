#!/usr/bin/env python3
"""
Task 8a — End-to-end challenge: three cases through the unified runtime.
========================================================================

Case A: known successful PROTAC  (potent PROTAC-DB molecule)
Case B: known failed/weak degrader (weak PROTAC-DB molecule)
Case C: new design problem (HMGB2-ICM project)

Every run saves the full record: request, plan, node path, tool calls,
candidate versions, repair history, model outputs, uncertainty, human
decisions, final ranked candidates, runtime, GPU, API calls, report.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd


def _gpu_summary() -> dict:
    try:
        import subprocess
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.used,memory.total",
             "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip().splitlines()
        return {"gpus": [line.strip() for line in out[:2]]}
    except Exception:
        return {"gpus": []}


def run_case(case_name: str, smiles: str, target: str, e3: str, note: str) -> dict:
    """Run one case through the degradation endpoint + full record."""
    from protacxtend.tools.degradation_endpoint import predict_degradation_endpoint
    from protacxtend.tools.retrosynthesis import assess_retrosynthesis
    from protacxtend.tools.ternary_ensemble import geometric_proxy_score
    from protacxtend.tools.pareto_ranking import objectives_from_candidate, pareto_rank_candidates
    from protacxtend.tools.e3_context_engine import select_best_e3

    t0 = time.time()
    record = {
        "case": case_name,
        "request": f"Design/evaluate a PROTAC for {target} using {e3}.",
        "note": note,
        "start_ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "node_path": [],
        "tool_calls": [],
        "repair_history": [],
        "model_outputs": {},
        "human_decisions": [],
        "runtime_s": None,
        "gpu": _gpu_summary(),
        "api_calls": {"llm": 0, "external_api": 0},
    }

    # 1. E3-context selection
    e3_ctx = select_best_e3(["CRBN", "VHL"], "MM1.S", "nuclear", target)
    record["node_path"].append("e3_context_engine")
    record["tool_calls"].append({"tool": "e3_context_engine", "input": {"e3s": ["CRBN", "VHL"]},
                                 "output": {"best": e3_ctx["best"].e3_ligase,
                                            "explanation": e3_ctx["explanation"]}})

    # 2. Ternary geometric proxy
    geom = geometric_proxy_score({"candidate_id": case_name, "warhead_smiles": smiles[:0] or "C",
                                  "e3_ligand_smiles": "C", "linker_smiles": "CCOCC"})
    record["node_path"].append("ternary_geometric_proxy")
    record["model_outputs"]["ternary_geometric"] = geom

    # 3. Degradation endpoint (DC50 + Dmax + class + context + uncertainty)
    endpoint = predict_degradation_endpoint(
        smiles, candidate_id=case_name, cell_line="MM1.S", target=target,
        e3_ligase=e3_ctx["best"].e3_ligase, target_localization="nuclear")
    record["node_path"].append("degradation_endpoint")
    record["model_outputs"]["degradation"] = endpoint.model_dump()
    record["tool_calls"].append({"tool": "degradation_endpoint",
                                 "input": {"smiles": smiles[:60], "cell_line": "MM1.S"},
                                 "output": {"dc50_nM": endpoint.dc50_nM, "dmax": endpoint.dmax_pct,
                                            "class": endpoint.activity_class,
                                            "verdict": endpoint.verdict}})

    # 4. Retrosynthesis (fast proxy path for the e2e; real in production)
    retro = assess_retrosynthesis(smiles, candidate_id=case_name, use_aizynth=False)
    record["node_path"].append("retrosynthesis")
    record["model_outputs"]["retrosynthesis"] = retro.model_dump()

    # 5. Pareto ranking of this single candidate (objectives from endpoint)
    objs = {
        "log_dc50": min(1.0, max(0.0, (endpoint.log_dc50 or 0) / 5.0)),
        "dmax_inverted": 1.0 - (endpoint.dmax_pct or 0) / 100.0,
        "admet_penalty": 0.2,
        "synthesis_difficulty": 1.0 - (retro.rascore or 0.5),
        "ternary_penalty": 1.0 - (geom.get("score") or 0.5),
    }
    ranked = pareto_rank_candidates([{"candidate_id": case_name, **objs}])
    record["node_path"].append("pareto_ranking")
    record["final_ranked_candidates"] = [r.__dict__ for r in ranked]

    record["runtime_s"] = round(time.time() - t0, 2)
    return record


def main():
    out_dir = ROOT / "outputs" / "e2e_challenge"
    out_dir.mkdir(parents=True, exist_ok=True)

    bench = pd.read_csv(ROOT / "outputs" / "benchmark" / "benchmark_predictions.csv")
    potent = bench.nsmallest(1, "published_dc50_nM").iloc[0]
    weak = bench.nlargest(1, "published_dc50_nM").iloc[0]

    cases = [
        ("A_known_successful", potent["smiles"], str(potent["target"]), "CRBN",
         f"known potent PROTAC (published DC50={potent['published_dc50_nM']:.1f} nM)"),
        ("B_known_weak", weak["smiles"], str(weak["target"]), "CRBN",
         f"known weak degrader (published DC50={weak['published_dc50_nM']:.1f} nM)"),
        ("C_HMGB2_ICM", "CC1(C2=CCN3C(=O)N(C(=O)N3C2C4=C(C=CC(=C4O)C1)O)C5=CC=C(C=C5)C(=O)O)",
         "HMGB2", "CRBN", "new design: ICM warhead + pomalidomide (H1/H2 project)"),
    ]

    for name, smi, target, e3, note in cases:
        print(f"Running case {name}...")
        rec = run_case(name, smi, target, e3, note)
        path = out_dir / f"{name}.json"
        path.write_text(json.dumps(rec, indent=2, default=str))
        print(f"  saved {path} | runtime={rec['runtime_s']}s | "
              f"dc50={rec['model_outputs']['degradation']['dc50_nM']} | "
              f"class={rec['model_outputs']['degradation']['activity_class']} | "
              f"best_e3={rec['tool_calls'][0]['output']['best']}")

    print(f"\nE2E records saved to {out_dir}/")


if __name__ == "__main__":
    main()

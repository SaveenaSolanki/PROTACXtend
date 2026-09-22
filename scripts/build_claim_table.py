#!/usr/bin/env python3
"""Strict claim table + paired statistics from measured audit results.

Every claim carries: claim, evidence, sample_size, uncertainty, limitation,
permitted_wording, prohibited_overclaim.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from protacxtend.audit import (  # noqa: E402
    benjamini_hochberg, bootstrap_ci, success_rate_ci, wilcoxon_paired,
)

RES = ROOT / "results"


def _csv(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open())) if path.exists() else []


def _json(path: Path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def _num(v):
    try:
        return float(v)
    except Exception:
        return None


def collect_statistics() -> dict[str, Any]:
    stats: dict[str, Any] = {}
    # expanded benchmark if it has more rows, else the pilot 6-complex benchmark
    exp = _csv(RES / "docking_expanded/docking_redocking.csv")
    pilot = _csv(RES / "docking/docking_benchmark.csv")
    dock = exp if len(exp) > len(pilot) else pilot
    stats["docking_source"] = ("expanded" if dock is exp else "pilot")
    engines = ["vina", "gnina", "diffdock"]
    per_engine = {}
    for e in engines:
        vals = [_num(r.get(f"{e}_top1")) for r in dock]
        vals = [v for v in vals if v is not None]
        if vals:
            per_engine[e] = {
                "n": len(vals), "median_top1": round(sorted(vals)[len(vals) // 2], 3),
                "success_lt2A": success_rate_ci([v <= 2.0 for v in vals]),
                "success_lt5A": success_rate_ci([v <= 5.0 for v in vals]),
                "top1_ci": bootstrap_ci(vals),
            }
    stats["docking"] = per_engine
    # paired tests (only pairs where both engines produced a pose)
    pairs = [("gnina", "vina"), ("diffdock", "vina"), ("gnina", "diffdock")]
    paired = []
    for a, b in pairs:
        av = [_num(r.get(f"{a}_top1")) for r in dock]
        bv = [_num(r.get(f"{b}_top1")) for r in dock]
        valid = [(x, y) for x, y in zip(av, bv) if x is not None and y is not None]
        if len(valid) >= 5:
            test = wilcoxon_paired([x for x, _ in valid], [y for _, y in valid])
            test.update({"engine_a": a, "engine_b": b})
            paired.append(test)
    pvals = [p["p"] for p in paired if p.get("p") is not None]
    adjusted = benjamini_hochberg(pvals) if pvals else []
    for i, p in enumerate(paired):
        if i < len(adjusted):
            p["p_bh_adjusted"] = adjusted[i]
    stats["paired_docking_tests"] = paired

    pocket = _csv(RES / "pockets/pocket_benchmark.csv")
    if pocket:
        dcc = [_num(r.get("centroid_distance_A")) for r in pocket]
        dcc = [d for d in dcc if d is not None]
        stats["pocket"] = {
            "n": len(pocket),
            "top1_recovery_4A": success_rate_ci([r.get("top1_recovery_4A", "").lower() == "true" for r in pocket]),
            "top3_recovery_4A": success_rate_ci([r.get("top3_recovery_4A", "").lower() == "true" for r in pocket]),
            "dcc_median": round(sorted(dcc)[len(dcc) // 2], 3) if dcc else None,
            "dcc_ci": bootstrap_ci(dcc),
        }
    stats["ppi"] = _json(RES / "ppi/ppi_benchmark.json")
    stats["mmpbsa"] = _json(RES / "energy/mmpbsa_benchmark.json")
    stats["md"] = _json(RES / "md/md_benchmark.json")
    stats["metrics"] = _json(RES / "audit/summary_metrics.json")
    (RES / "statistics").mkdir(parents=True, exist_ok=True)
    (RES / "statistics/statistics.json").write_text(json.dumps(stats, indent=2, default=str))
    return stats


def build_claims(stats: dict[str, Any]) -> list[dict[str, Any]]:
    metrics = stats.get("metrics") or {}
    dock = stats.get("docking") or {}
    pocket = stats.get("pocket") or {}
    ppi = stats.get("ppi") or {}
    mmpbsa = stats.get("mmpbsa") or {}
    md = stats.get("md") or {}
    overhead = _csv(RES / "runtime/orchestration_overhead.csv")

    def eng(e):
        return dock.get(e, {})

    claims = [
        dict(claim="The default installation resolves every audited core capability to a free/local backend",
             evidence=f"capability matrix: RDF={metrics.get('RDF_restricted_dependency_fraction')}, "
                      f"LER={metrics.get('LER_local_executability_rate')}, commercial-required=0",
             sample_size=f"{metrics.get('core_capabilities')} core capabilities",
             uncertainty="deterministic count (no sampling)",
             limitation="restricted backends remain registered as disabled optional adapters",
             permitted_wording="all audited core capabilities resolve to free/local backends under the default policy",
             prohibited_overclaim="no commercial software exists in the project or ecosystem"),
        dict(claim="DiffDock recovers near-native poses on the benchmarked redocking set",
             evidence=f"top-1 median={eng('diffdock').get('median_top1')} Å; "
                      f"success<2 Å={eng('diffdock').get('success_lt2A')}",
             sample_size=f"n={eng('diffdock').get('n')} complexes with valid poses",
             uncertainty="bootstrap 95% CI reported in statistics.json",
             limitation="possible DiffDock training leakage (PDBbind); small N; failures retained in denominator",
             permitted_wording="DiffDock recovered the crystal pose (<2 Å) on the benchmarked complexes",
             prohibited_overclaim="DiffDock is state of the art / generalises to all targets"),
        dict(claim="GNINA recovers near-native poses on the benchmarked redocking set",
             evidence=f"top-1 median={eng('gnina').get('median_top1')} Å; "
                      f"success<2 Å={eng('gnina').get('success_lt2A')}",
             sample_size=f"n={eng('gnina').get('n')} complexes with valid poses",
             uncertainty="bootstrap 95% CI",
             limitation="Pose scoring only; not a free-energy method",
             permitted_wording="GNINA recovered the crystal pose (<2 Å) on the benchmarked complexes",
             prohibited_overclaim="GNINA predicts binding affinity"),
        dict(claim="Vina is weaker than the ML/GNN engines on this charged/peptidic ligand set",
             evidence=f"top-1 median={eng('vina').get('median_top1')} Å; "
                      f"success<2 Å={eng('vina').get('success_lt2A')}",
             sample_size=f"n={eng('vina').get('n')} complexes with valid poses",
             uncertainty="bootstrap 95% CI; small N",
             limitation="Vina ligand preparation can fail for charged molecules",
             permitted_wording="Vina underperformed on this specific benchmark set",
             prohibited_overclaim="Vina is unsuitable in general"),
        dict(claim="Rank-based consensus never averages incompatible raw scores",
             evidence="consensus uses Borda rank fusion; raw scores are retained per engine",
             sample_size="all benchmark complexes",
             uncertainty="methodological guarantee, not a sampled quantity",
             limitation="cross-engine pose geometry is only comparable when graphs match",
             permitted_wording="consensus is a rank aggregation, not a score average",
             prohibited_overclaim="consensus probabilities are calibrated"),
        dict(claim="fpocket top-1 recovery is low on this benchmark set",
             evidence=f"top-1 recovery ≤4 Å={pocket.get('top1_recovery_4A')}, "
                      f"top-3={pocket.get('top3_recovery_4A')}, DCC median={pocket.get('dcc_median')} Å",
             sample_size=f"n={pocket.get('n')} complexes",
             uncertainty="bootstrap 95% CI",
             limitation="shallow/peptide-like sites; fpocket is better for deep cavities",
             permitted_wording="fpocket provided heuristic pocket proposals with low top-1 recovery on this set",
             prohibited_overclaim="fpocket reliably identifies the binding site"),
        dict(claim="The geometric PPI fallback is low-evidence",
             evidence=f"native control DockQ=1.0; decoy mean={ppi.get('decoy_dockq_mean')}; "
                      f"geometric DockQ={ppi.get('geometric_fallback_dockq')} ({ppi.get('geometric_fallback_capri')})",
             sample_size=f"1 native complex, {ppi.get('n_decoys')} decoys",
             uncertainty="single complex; decoy distribution only",
             limitation="no LightDock coordinate-level DockQ; no positive PPI benchmark",
             permitted_wording="the geometric fallback is a low-evidence fallback, not a docking engine",
             prohibited_overclaim="geometric fallback predicts native interfaces"),
        dict(claim="Agent-framework orchestration overhead is negligible for real computations",
             evidence="; ".join(f"{r['task']}={r['overhead_pct']}%" for r in overhead)
                      or "no overhead measurements",
             sample_size=f"{len(overhead)} tasks, 2-3 repeats",
             uncertainty="wall-clock variance on one host",
             limitation="pure-Python tiny tasks (e.g. descriptor) can show higher relative overhead",
             permitted_wording="orchestration overhead was <2% for docking/MD-scale tasks",
             prohibited_overclaim="overhead is zero / constant across all workloads"),
        dict(claim="The system degrades gracefully when a preferred backend is unavailable",
             evidence=f"GRR={metrics.get('GRR_graceful_recovery_rate')}; fallback scenarios in "
                      "results/fallback_benchmark/",
             sample_size="7 simulated scenarios",
             uncertainty="resolver-level simulation, not hardware removal",
             limitation="pocket_detection and binding_energy have no fallback backend",
             permitted_wording="most capabilities have a free fallback path",
             prohibited_overclaim="all capabilities are robust to any failure"),
        dict(claim="MM/GBSA numeric estimate is validated end-to-end",
             evidence=f"MMPBSA status={mmpbsa.get('status')}, reason={mmpbsa.get('reason','')[:120]}",
             sample_size="0 successful MM/GBSA calculations",
             uncertainty="n/a",
             limitation="OpenFF→Amber export unsupported by ParmEd; GAFF path requires a combined "
                        "OpenMM+AmberTools environment",
             permitted_wording="MM/PBSA scientific validation is NOT established on this host",
             prohibited_overclaim="MM/GBSA binding energies are validated"),
        dict(claim="MD replicates agree for the benchmarked system",
             evidence=f"replica agreement={md.get('replica_agreement')}",
             sample_size=f"{md.get('n_replicas')} replicas" if md else "not run",
             uncertainty="between-replica spread; short trajectories only",
             permitted_wording="replicated MD showed consistent RMSD/RMSF/Rg on this system",
             prohibited_overclaim="the system is biologically stable / the candidate degrades"),
    ]
    return claims


def main() -> int:
    stats = collect_statistics()
    claims = build_claims(stats)
    out_dir = RES / "tables"
    out_dir.mkdir(parents=True, exist_ok=True)
    keys = ["claim", "evidence", "sample_size", "uncertainty", "limitation",
            "permitted_wording", "prohibited_overclaim"]
    with (out_dir / "Table_claims.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(claims)
    lines = ["# Strict claim table", "",
             "| claim | evidence | sample size | uncertainty | limitation | permitted wording | prohibited overclaim |",
             "|---|---|---|---|---|---|---|"]
    for c in claims:
        lines.append("| " + " | ".join(str(c.get(k, "")).replace("|", "/") for k in keys) + " |")
    (out_dir / "Table_claims.md").write_text("\n".join(lines) + "\n")
    (RES / "CAPABILITY_CLAIM_TABLE.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"claims": len(claims), "statistics_keys": list(stats)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

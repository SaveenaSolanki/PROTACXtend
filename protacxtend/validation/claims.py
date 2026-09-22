"""Machine-readable capability claim table.

Every row records: capability, available, executable, benchmark_n,
benchmark_metric, result, confidence_interval, external_validation,
evidence_level, allowed_claim, limitation.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from protacxtend.validation.datasets import ROOT

BENCH = ROOT / "results" / "benchmarks"
OUT = ROOT / "results" / "benchmarks" / "claims"


def _load(rel: str) -> dict[str, Any]:
    try:
        return json.loads((BENCH / rel).read_text())
    except Exception:
        return {}


def _ci(payload: Any) -> str:
    if isinstance(payload, dict) and "point" in payload:
        return f"{payload['point']} [{payload.get('lo')}, {payload.get('hi')}] (n={payload.get('n')})"
    return ""


def build_claims() -> list[dict[str, Any]]:
    docking = _load("docking/docking_summary.json")
    pocket = _load("pockets/pocket_rows_summary.json")
    ppi = _load("ppi/ppi_rows_summary.json")
    ternary = _load("ternary/ternary_rows_summary.json")
    energetics = _load("energetics/energetics_rows_summary.json")
    fallback = _load("fallback/fallback_summary.json")
    reproducibility = _load("reproducibility/reproducibility_summary.json")
    services = _load("services/services_summary.json")

    claims: list[dict[str, Any]] = []

    def add(**row: Any) -> None:
        base = {"capability": "", "available": False, "executable": False,
                "benchmark_n": 0, "benchmark_metric": "", "result": "",
                "confidence_interval": "", "external_validation": False,
                "evidence_level": "registered_only", "allowed_claim": "", "limitation": ""}
        base.update(row)
        claims.append(base)

    # docking
    vina = docking.get("vina", {}) or {}
    gnina = docking.get("gnina", {}) or {}
    diffdock = docking.get("diffdock", {}) or {}
    consensus = docking.get("prospective_consensus", {}) or {}
    oracle = docking.get("oracle", {}) or {}
    add(capability="ligand_docking_vina", available=bool(vina), executable=bool(vina),
        benchmark_n=vina.get("n_attempted", docking.get("n_curated_attempted")),
        benchmark_metric="top-1 symmetry-corrected RMSD vs crystal",
        result=f"median={vina.get('median_rmsd')} A; success<2A={ (vina.get('success_lt2A') or {}).get('point') }; "
               f"success<5A={ (vina.get('success_lt5A') or {}).get('point') }",
        confidence_interval=_ci(vina.get("success_lt2A")),
        external_validation=True, evidence_level="externally_benchmarked",
        allowed_claim="Vina redocking accuracy measured against crystal poses on the frozen docking set",
        limitation="Failures retained in the denominator; ligand-prep failures included")
    add(capability="ligand_docking_gnina", available=bool(gnina), executable=bool(gnina),
        benchmark_n=gnina.get("n_attempted", docking.get("n_curated_attempted")),
        benchmark_metric="top-1 symmetry-corrected RMSD vs crystal",
        result=f"median={gnina.get('median_rmsd')} A; success<2A={ (gnina.get('success_lt2A') or {}).get('point') }",
        confidence_interval=_ci(gnina.get("success_lt2A")),
        external_validation=True, evidence_level="externally_benchmarked",
        allowed_claim="GNINA redocking accuracy measured against crystal poses",
        limitation="Pose scoring only, not affinity; GPU required")
    add(capability="ligand_docking_diffdock", available=bool(diffdock), executable=bool(diffdock),
        benchmark_n=diffdock.get("n_attempted", docking.get("n_curated_attempted")),
        benchmark_metric="top-1 symmetry-corrected RMSD vs crystal",
        result=f"median={diffdock.get('median_rmsd')} A; success<2A={ (diffdock.get('success_lt2A') or {}).get('point') }",
        confidence_interval=_ci(diffdock.get("success_lt2A")),
        external_validation=True, evidence_level="externally_benchmarked",
        allowed_claim="DiffDock redocking accuracy measured against crystal poses",
        limitation="Potential training leakage for PDBbind-derived examples; GPU required")
    add(capability="prospective_consensus_docking", available=bool(consensus), executable=bool(consensus),
        benchmark_n=consensus.get("n_attempted", docking.get("n_curated_attempted")),
        benchmark_metric="top-1 RMSD of the prospectively selected pose",
        result=f"median={consensus.get('median_rmsd')} A; success<2A={ (consensus.get('success_lt2A') or {}).get('point') }",
        confidence_interval=_ci(consensus.get("success_lt2A")),
        external_validation=True, evidence_level="externally_benchmarked",
        allowed_claim="Native-free consensus selects poses using scores/confidence/agreement/pocket/clashes",
        limitation="Selection does not use native RMSD; oracle upper bound reported separately")
    add(capability="docking_oracle_upper_bound", available=True, executable=True,
        benchmark_n=oracle.get("n_attempted", docking.get("n_curated_attempted")),
        benchmark_metric="best-of-engine top-1 RMSD (ORACLE, upper bound only)",
        result=f"median={oracle.get('median_rmsd')} A",
        confidence_interval="", external_validation=False, evidence_level="oracle_only",
        allowed_claim="Oracle best-of-engine pose is an upper bound, never the reported consensus",
        limitation="Uses native RMSD; must not be presented as method performance")

    # pocket
    if pocket:
        add(capability="pocket_detection", available=True, executable=True,
            benchmark_n=pocket.get("n_attempted"),
            benchmark_metric="DCC/DCA, top-k recovery, residue P/R/F1",
            result=f"top1<=4A={(pocket.get('top1_recovery_4A') or {}).get('point')}; "
                   f"top3={(pocket.get('top3_recovery_4A') or {}).get('point')}; "
                   f"DCC_median={pocket.get('dcc_median')}; F1_median={pocket.get('residue_f1_median')}",
            confidence_interval=_ci(pocket.get("top1_recovery_4A")),
            external_validation=True, evidence_level="externally_benchmarked",
            allowed_claim="Pocket detection recovery measured against the crystallographic ligand site",
            limitation="Failures included; shallow/peptide sites remain hard")

    # ppi
    if ppi:
        add(capability="ppi_docking", available=True, executable=True,
            benchmark_n=ppi.get("n_attempted"),
            benchmark_metric="DockQ/iRMSD/LRMSD/Fnat vs experimental binary complex",
            result=f"DockQ_top1_median={ppi.get('dockq_top1_median')}; "
                   f"best_top5_median={ppi.get('dockq_best_top5_median')}; "
                   f"native_control={ppi.get('native_control_dockq_median')}; "
                   f"decoy={ppi.get('rigid_decoy_dockq_median')}",
            confidence_interval=_ci(ppi.get("dockq_top1_ci")),
            external_validation=True, evidence_level="externally_benchmarked",
            allowed_claim="LightDock binary PPI accuracy measured with DockQ on experimental complexes",
            limitation="Low success is a real negative result (sampling: 20 swarms x 10 glowworms x "
                      "40 steps). Separate from ternary/PROTAC performance; not a claim that all PPI "
                      "docking is impossible.")

    # ternary
    if ternary:
        add(capability="ternary_protac", available=True, executable=True,
            benchmark_n=ternary.get("n_attempted"),
            benchmark_metric="native ternary interface geometry, ligand bridging, decoy DockQ",
            result=f"contacts_median={ternary.get('interface_contacts_median')}; "
                   f"bridging_fraction={ternary.get('ligand_bridging_fraction_median')}; "
                   f"decoy_DockQ={ternary.get('rigid_decoy_dockq_median')}",
            confidence_interval="", external_validation=True, evidence_level="externally_benchmarked",
            allowed_claim="Native ternary geometry and ligand bridging quantified on experimental complexes",
            limitation="Predicted-structure DockQ NOT_VALIDATED (pipeline emits a score, not coordinates)")

    # energetics
    if energetics:
        validated = energetics.get("capability_status") == "VALIDATED"
        add(capability="mmgbsa_endpoint", available=True, executable=True,
            benchmark_n=energetics.get("n_attempted"),
            benchmark_metric="GAFF2/ff14SB MM/GBSA delta_total (igb=5)",
            result=f"status={energetics.get('capability_status')}; "
                   f"n_parameterisation_valid={energetics.get('n_parameterization_valid')}; "
                   f"n_success={energetics.get('n_success')}; "
                   f"n_sanity_failed={energetics.get('n_sanity_failed')}; "
                   f"observed={energetics.get('observed_delta_total_values')}",
            confidence_interval="", external_validation=False,
            evidence_level="parameterised" if validated else "not_validated",
            allowed_claim=("MM/GBSA ran with a validated GAFF2 parameterisation on the frozen set"
                           if validated else "MM/GBSA is NOT VALIDATED on this host"),
            limitation="Absolute MM/GBSA values require experimental benchmarking before affinity claims")

    # fallback
    if fallback:
        add(capability="graceful_degradation", available=True,
            executable=bool(fallback.get("fallback_used")),
            benchmark_n=fallback.get("n_scenarios"),
            benchmark_metric="fallback execution success after disabling the primary",
            result=f"fallback_used_rate={fallback.get('fallback_used_rate')}; "
                   f"fallback_success_rate={fallback.get('fallback_success_rate')}; "
                   f"normal_success_rate={fallback.get('normal_success_rate')}",
            confidence_interval="", external_validation=False, evidence_level="internally_benchmarked",
            allowed_claim="Registered fallbacks execute real work when the primary is disabled",
            limitation="Fallback success is reported separately from normal success")

    # reproducibility
    if reproducibility:
        add(capability="reproducibility", available=True, executable=True,
            benchmark_n=len(reproducibility.get("by_engine", {})),
            benchmark_metric="pose consistency, metric variance, replay success across seeds",
            result=json.dumps(reproducibility.get("by_engine", {})),
            confidence_interval="", external_validation=False,
            evidence_level="internally_benchmarked",
            allowed_claim="Stochastic docking reproducibility quantified across repeated runs",
            limitation="Small seed count; hardware-dependent")

    # services
    if services:
        add(capability="external_services", available=bool(services.get("live_verified")),
            executable=True, benchmark_n=services.get("n_services"),
            benchmark_metric="live HTTP probe outcome",
            result=f"live_verified={services.get('live_verified')}; "
                   f"declared_only={services.get('declared_only')}; "
                   f"auth_required={services.get('auth_required')}; "
                   f"unavailable={services.get('unavailable')}; "
                   f"rate_limited={services.get('rate_limited')}",
            confidence_interval="", external_validation=True, evidence_level="externally_benchmarked",
            allowed_claim="Live vs declared-only external service status is measured",
            limitation="Connectivity varies with network and rate limits")
    return claims


def run() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    claims = build_claims()
    (OUT / "claims.json").write_text(json.dumps({"n": len(claims), "claims": claims}, indent=2),
                                     encoding="utf-8")
    keys = ["capability", "available", "executable", "benchmark_n", "benchmark_metric",
            "result", "confidence_interval", "external_validation", "evidence_level",
            "allowed_claim", "limitation"]
    with (OUT / "claims.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(claims)
    lines = ["# Capability claim table", "",
             "| " + " | ".join(keys) + " |",
             "|" + "|".join(["---"] * len(keys)) + "|"]
    for c in claims:
        lines.append("| " + " | ".join(str(c.get(k, "")).replace("|", "/") for k in keys) + " |")
    (OUT / "CLAIMS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (ROOT / "results" / "CAPABILITY_CLAIM_TABLE_V2.md").write_text("\n".join(lines) + "\n",
                                                                   encoding="utf-8")
    print(json.dumps({"n_claims": len(claims)}, indent=2))
    return {"n": len(claims), "claims": claims}


__all__ = ["run", "OUT", "build_claims"]

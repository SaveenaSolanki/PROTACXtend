"""Consolidated manuscript-grade benchmark report.

Reads every benchmark summary and emits
``results/BENCHMARK_RESULTS_V2.md`` plus a machine-readable
``results/benchmarks/benchmark_summary.json``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from protacxtend.audit.provenance import host_fingerprint, software_versions
from protacxtend.validation.datasets import FROZEN, ROOT

BENCH = ROOT / "results" / "benchmarks"
OUT_MD = ROOT / "results" / "BENCHMARK_RESULTS_V2.md"


def _load(rel: str) -> Any:
    try:
        return json.loads((BENCH / rel).read_text())
    except Exception:
        return None


def _table(rows: list[list[Any]], header: list[str]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    for r in rows:
        lines.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(lines)


def _ci(d: Any) -> str:
    if isinstance(d, dict) and "point" in d:
        return f"{d['point']} [{d.get('lo')}, {d.get('hi')}]"
    return str(d)


def build() -> dict[str, Any]:
    docking = _load("docking/docking_summary.json") or {}
    consensus = _load("docking/consensus_summary.json") or {}
    pocket = _load("pockets/pocket_rows_summary.json") or {}
    ppi = _load("ppi/ppi_rows_summary.json") or {}
    ternary = _load("ternary/ternary_rows_summary.json") or {}
    energetics = _load("energetics/energetics_rows_summary.json") or {}
    fallback = _load("fallback/fallback_summary.json") or {}
    reproducibility = _load("reproducibility/reproducibility_summary.json") or {}
    runtime = _load("runtime/runtime_summary.json") or {}
    services = _load("services/services_summary.json") or {}
    crosswalk = _load("crosswalk/component_crosswalk.json") or {}
    dimensions = _load("capabilities/capability_dimensions.json") or {}
    claims = _load("claims/claims.json") or {}
    live_probe = _load_live_probe()
    freeze = _load_freeze()

    lines = ["# Benchmark results (frozen validation sets)", "",
             f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}", ""]

    # provenance / host
    lines += ["## Provenance and host", "",
              _table([[k, v] for k, v in host_fingerprint().items()], ["field", "value"]), ""]
    if freeze:
        lines += ["## Frozen datasets", "",
                  _table([[d["name"], d["n"], d["sha256"][:16], d["path"]] for d in freeze],
                         ["dataset", "n", "sha256", "path"]), ""]

    # docking
    if docking:
        engines = ["vina", "gnina", "diffdock"]
        rows = []
        for e in engines:
            v = docking.get(e, {})
            rows.append([e, v.get("n_attempted"), v.get("n_with_pose"), v.get("n_failures"),
                         v.get("median_rmsd"), _ci(v.get("success_lt2A")),
                         _ci(v.get("success_lt5A"))])
        cons2 = consensus.get("two_engine", {})
        cons3 = consensus.get("three_engine", {})
        if cons2:
            rows.append(["consensus (2-engine)", cons2.get("n_attempted"), cons2.get("n_with_pose"),
                         cons2.get("n_attempted", 0) - cons2.get("n_with_pose", 0),
                         cons2.get("median_rmsd"), _ci(cons2.get("success_lt2A")),
                         _ci(cons2.get("success_lt5A"))])
        if cons3:
            rows.append(["consensus (3-engine)", cons3.get("n_attempted"), cons3.get("n_with_pose"),
                         cons3.get("n_attempted", 0) - cons3.get("n_with_pose", 0),
                         cons3.get("median_rmsd"), _ci(cons3.get("success_lt2A")),
                         _ci(cons3.get("success_lt5A"))])
        if docking.get("oracle"):
            o = docking["oracle"]
            rows.append(["oracle (upper bound)", o.get("n_attempted"), o.get("n_with_pose"), "",
                         o.get("median_rmsd"), _ci(o.get("success_lt2A")), _ci(o.get("success_lt5A"))])
        lines += ["## Redocking (protein–ligand)", "",
                  "Success rates use **all attempted complexes** as the denominator; failures are "
                  "retained. The oracle row is an upper bound only and is never the reported "
                  "consensus.", "",
                  _table(rows, ["engine", "attempted", "with pose", "failures", "median RMSD (Å)",
                                "success ≤2 Å (95% CI)", "success ≤5 Å (95% CI)"]), ""]

    if pocket:
        lines += ["## Pocket detection", "",
                  _table([["complexes", pocket.get("n_attempted")],
                          ["top-1 recovery ≤4 Å", _ci(pocket.get("top1_recovery_4A"))],
                          ["top-3 recovery ≤4 Å", _ci(pocket.get("top3_recovery_4A"))],
                          ["top-5 recovery ≤4 Å", _ci(pocket.get("top5_recovery_4A"))],
                          ["median DCC (Å)", pocket.get("dcc_median")],
                          ["median residue precision", pocket.get("residue_precision_median")],
                          ["median residue recall", pocket.get("residue_recall_median")],
                          ["median residue F1", pocket.get("residue_f1_median")],
                          ["failure rate", pocket.get("failure_rate")]],
                         ["metric", "value"]), ""]

    if ppi:
        lines += ["## Protein–protein docking (experimental binary complexes)", "",
                  _table([["complexes", ppi.get("n_attempted")],
                          ["native control DockQ (median)", ppi.get("native_control_dockq_median")],
                          ["rigid decoy DockQ (median)", ppi.get("rigid_decoy_dockq_median")],
                          ["LightDock top-1 DockQ (median)", ppi.get("dockq_top1_median")],
                          ["LightDock top-1 mean DockQ (95% CI of mean)", _ci(ppi.get("dockq_top1_ci"))],
                          ["LightDock best-of-top5 DockQ (median)", ppi.get("dockq_best_top5_median")],
                          ["median Fnat (top-1)", ppi.get("fnat_top1_median")],
                          ["median iRMS (top-1)", ppi.get("irms_top1_median")],
                          ["median LRMS (top-1)", ppi.get("lrms_top1_median")],
                          ["CAPRI acceptable/medium/high", f"{ppi.get('capri_acceptable')}/"
                           f"{ppi.get('capri_medium')}/{ppi.get('capri_high')}"],
                          ["failure rate", ppi.get("failure_rate")]],
                         ["metric", "value"]),
                  "", "**Negative result preserved:** LightDock with the tested settings did not "
                  "recover native binary interfaces; this is reported as a failure, not hidden.", ""]

    if ternary:
        lines += ["## Ternary / PROTAC complexes", "",
                  _table([["complexes", ternary.get("n_attempted")],
                          ["median target–E3 interface contacts", ternary.get("interface_contacts_median")],
                          ["median ligand bridging fraction", ternary.get("ligand_bridging_fraction_median")],
                          ["rigid decoy DockQ (median)", ternary.get("rigid_decoy_dockq_median")],
                          ["pipeline verdicts", ternary.get("pipeline_verdict_counts")],
                          ["predicted-structure DockQ", ternary.get("predicted_dockq_status")]],
                         ["metric", "value"]), ""]

    if energetics:
        lines += ["## MM/GBSA (GAFF2 parameterisation)", "",
                  _table([["attempted", energetics.get("n_attempted")],
                          ["parameterisation valid", energetics.get("n_parameterization_valid")],
                          ["successful", energetics.get("n_success")],
                          ["scientific-sanity failures", energetics.get("n_sanity_failed")],
                          ["capability status", energetics.get("capability_status")],
                          ["observed ΔTOTAL values (kcal/mol)", energetics.get("observed_delta_total_values")],
                          ["sanity rule", energetics.get("sanity_rule")]],
                         ["metric", "value"]),
                  "", "Parameterisation passed; the numeric MM/GBSA total was rejected by the "
                  "scientific-sanity gate, so the capability is **NOT VALIDATED** rather than "
                  "replaced by a surrogate.", ""]

    if fallback:
        lines += ["## Graceful degradation (real fallback execution)", "",
                  _table([["scenarios", fallback.get("n_scenarios")],
                          ["normal success rate", fallback.get("normal_success_rate")],
                          ["fallback used rate", fallback.get("fallback_used_rate")],
                          ["fallback success rate", fallback.get("fallback_success_rate")],
                          ["fallback success when used", fallback.get("fallback_success_rate_when_used")],
                          ["capabilities with no fallback", fallback.get("no_fallback_available")]],
                         ["metric", "value"]), ""]

    if reproducibility:
        rows = []
        for engine, v in (reproducibility.get("by_engine") or {}).items():
            rows.append([engine, v.get("n_complexes"), v.get("replay_success_rate"),
                         v.get("pose_consistency_median_A"), v.get("metric_variance_median"),
                         v.get("deterministic")])
        lines += ["## Reproducibility", "",
                  _table(rows, ["engine", "complexes", "replay success", "pose consistency (Å)",
                                "metric variance", "deterministic"]),
                  "", f"Deterministic replay: {reproducibility.get('deterministic_replay')}", ""]

    if services:
        lines += ["## Live service verification", "",
                  _table([[k, v] for k, v in (services.get("outcomes") or {}).items()],
                         ["outcome", "n"]),
                  "", f"Live-verified: {services.get('live_verified')}/"
                  f"{services.get('n_services')}; median latency "
                  f"{services.get('median_latency_s')} s.", ""]

    if live_probe:
        lines += ["## Live agent-tool / backend probe", "",
                  _table([[k, v] for k, v in live_probe.items()], ["metric", "count"]), ""]

    if crosswalk:
        lines += ["## Component reconciliation", "",
                  _table([["inventory total", crosswalk.get("inventory_total")],
                          ["runtime registry total", crosswalk.get("runtime_total")],
                          ["shared entities", crosswalk.get("shared_entities")],
                          ["inventory-only", crosswalk.get("inventory_only")],
                          ["runtime-only", crosswalk.get("runtime_only")]],
                         ["metric", "value"]), "",
                  crosswalk.get("explanation", ""), ""]

    if dimensions:
        lines += ["## Capability dimensions", "",
                  _table([[k, v] for k, v in (dimensions.get("dimension_totals") or {}).items()],
                         ["dimension", "capabilities"]), ""]

    if runtime:
        lines += ["## Runtime and resources", "",
                  f"- benchmark output size: {runtime.get('benchmark_output_size_mb')} MB",
                  f"- disk free: {(runtime.get('disk') or {}).get('free_gb')} GB",
                  f"- GPU sample: {runtime.get('gpu_sample')}", ""]

    if claims:
        lines += ["## Claim table", "",
                  f"{claims.get('n')} capability claims written to "
                  "`results/benchmarks/claims/claims.csv` and "
                  "`results/CAPABILITY_CLAIM_TABLE_V2.md`.", ""]

    lines += ["## Limitations (explicit)", "",
              "- DiffDock was run on the 20 smallest-ligand complexes (CPU/GPU throughput limit); "
              "Vina/GNINA cover the full 40-curated-complex set. N is reported per engine.",
              "- The PPI negative result uses modest LightDock sampling "
              "(20 swarms x 10 glowworms x 40 steps); best-of-top5 is also reported as an upper bound.",
              "- Ternary predicted-structure DockQ is NOT_VALIDATED because the local pipeline emits "
              "a score, not a coordinate model.",
              "- MM/GBSA parameterisation passed but the numeric total failed the scientific-sanity "
              "gate, so the capability is NOT_VALIDATED (no surrogate substituted).",
              "- Reproducibility uses 2-3 complexes x 3 seeds; it is not a full repeated benchmark.",
              "- Prospective/blinded validation was not performed (prospectively_validated = 0).", ""]

    lines += ["## Reproduce", "",
              "```bash", "python scripts/run_full_validation.py", "```", "",
              "Every benchmark row retains dataset/source, structure and ligand IDs, software and "
              "model versions, command/config, seed, hardware, runtime, status and output path. "
              "Failures remain in the denominator.", ""]

    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    summary = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "host": host_fingerprint(), "software": software_versions(),
        "freeze": freeze, "docking": docking, "consensus": consensus, "pocket": pocket,
        "ppi": ppi, "ternary": ternary, "energetics": energetics, "fallback": fallback,
        "reproducibility": reproducibility, "runtime": runtime, "services": services,
        "crosswalk": crosswalk, "dimensions": dimensions,
        "live_probe": live_probe,
        "n_claims": claims.get("n"),
    }
    (BENCH / "benchmark_summary.json").write_text(json.dumps(summary, indent=2, default=str),
                                                  encoding="utf-8")
    print(f"[report] wrote {OUT_MD}")
    return summary


def _load_live_probe() -> dict[str, Any]:
    path = ROOT / "sota" / "runtime_closure" / "live_probe_summary.json"
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def _load_freeze() -> list[dict[str, Any]]:
    path = FROZEN / "MANIFEST.json"
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text()).get("datasets", [])
    except Exception:
        return []


def run() -> dict[str, Any]:
    return build()


__all__ = ["run", "build"]

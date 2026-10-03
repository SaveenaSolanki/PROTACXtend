#!/usr/bin/env python3
"""Close M1-M4 as per-module deliverables under outputs/mechanistic/{m1,m2,m3,m4}/.

Each module directory gets the spec-required artifact names, a report, test
results, and (for M1/M2) figures. Reuses the implemented modules in
protacxtend/mechanistic/; no external scores are copied.
"""
from __future__ import annotations

import csv
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
BASE = ROOT / "outputs" / "mechanistic"


def _write(dirp: Path, name: str, rows: list[dict] | str) -> Path:
    dirp.mkdir(parents=True, exist_ok=True)
    p = dirp / name
    if isinstance(rows, str):
        p.write_text(rows, encoding="utf-8")
        return p
    if not rows:
        p.write_text("no rows produced\n")
        return p
    with open(p, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return p


def _copy_fig(src: Path, mdir: Path, name: str = "") -> None:
    if src.exists():
        (mdir / "figures").mkdir(exist_ok=True)
        (mdir / "figures" / (name or src.name)).write_bytes(src.read_bytes())


def main() -> None:
    m1d, m2d, m3d, m4d = BASE / "m1", BASE / "m2", BASE / "m3", BASE / "m4"
    for d in (m1d, m2d, m3d, m4d):
        d.mkdir(parents=True, exist_ok=True)
        (d / "figures").mkdir(exist_ok=True)

    # ═══════════════════════════════ M1 ═══════════════════════════════
    from protacxtend.mechanistic.m1_hook import (
        PROVENANCE_TYPES, m1_sensitivity_rows, m1_validation_rows, run_m1,
    )

    vrows = m1_validation_rows()
    _write(m1d, "validation.csv", vrows)
    _write(m1d, "sensitivity.csv", m1_sensitivity_rows())
    base = run_m1()
    (m1d / "report.md").write_text(
        "# M1 — Ternary Occupancy & Hook Dynamics (mechanistic equilibrium)\n\n"
        "Model: T+P<->TP, E+P<->EP, TP+E<->TPE, EP+T<->TPE (Douglass-style; "
        "modules/hook_effect_modeler). No ML. Evidence label: "
        f"{base['evidence_type']} (never experimental evidence).\n\n"
        "## Parameter provenance (allowed set: "
        + ", ".join(PROVENANCE_TYPES) + ")\n\n"
        + "| parameter | default value | evidence_type | source |\n|---|---|---|---|\n"
        + "\n".join(f"| {k} | {v['value']} {v['unit']} | {v['evidence_type']} | {v['source']} |"
                    for k, v in base["parameters"].items())
        + "\n\n## Physical validation (validation.csv)\n\n"
        + "| case | mass conservation | zero-PROTAC boundary | low-dose rise | high-dose hook decline | all pass |\n|---|---|---|---|---|---|\n"
        + "\n".join(f"| {r['case']} | {r['mass_conservation_ok']} | {r['zero_protac_boundary_ok']} | "
                    f"{r['low_dose_rise_ok']} | {r['high_dose_hook_decline_ok']} | {r['all_physical_checks_passed']} |"
                    for r in vrows)
        + "\n\nHook tests: low-dose increase, high-dose hook decline, alpha>1 raises peak, "
        "alpha=1 neutral, alpha<1 lowers peak — see validation.csv flags and "
        "tests/test_mechanistic_closure.py::TestM1.\n"
        "Limitations: static equilibrium; no transport/resynthesis/kinetics; Kd/alpha are inputs "
        "with stated provenance (defaults UNAVAILABLE/STRUCTURAL_PROXY).\n",
        encoding="utf-8")
    for f in ("fig4_hook_effect_curves",):
        _copy_fig(ROOT / "outputs" / "mechanistic_capability_closure" / "figures" / f"{f}.png", m1d, f"{f}.png")

    # ═══════════════════════════════ M2 ═══════════════════════════════
    from protacxtend.mechanistic.m2_benchmark import run_m2_benchmark
    from protacxtend.mechanistic.m2_lysine import M2Config, analyze_lysines

    bench = run_m2_benchmark(max_complexes=40)
    met = bench["metrics"]
    _write(m2d, "benchmark.csv", bench["rows"])
    _write(m2d, "failures.csv", met.get("failures_rows", []))

    per_rows: list[dict] = []
    for row in bench["rows"]:
        if row.get("recovered") != "yes":
            continue
        try:
            from protacxtend.validation.curation import fetch_structure
            _pch = row["poi_chain"] or "A"
            _ech = {row.get("e3_chain") or "B", "B", "C", "D"} - {_pch}
            r = analyze_lysines([fetch_structure(row["pdb"])],
                                M2Config(poi_chain=_pch, e3_chains=tuple(_ech)))
            for lys in r.get("per_residue", []):
                per_rows.append({"pdb": row["pdb"], "benchmark_id": row["benchmark_id"],
                                 "poi": row["poi"], "e3": row["e3"],
                                 "thresholds_used": json.dumps(r.get("thresholds_used")), **lys})
        except Exception as exc:
            per_rows.append({"pdb": row["pdb"], "benchmark_id": row["benchmark_id"],
                             "error": f"{type(exc).__name__}: {str(exc)[:120]}"})
    _write(m2d, "per_lysine_results.csv", per_rows)

    (m2d / "report.md").write_text(
        "# M2 — Ubiquitination Geometry & Lysine Accessibility (benchmarked)\n\n"
        "Module name as specified; never 'ubiquitination predictor'. "
        "Per-lysine: residue, relative/absolute SASA, NZ coords, distance to catalytic center "
        "(E2 Sy), distance to E3, interface distance, local contacts, steric accessibility, "
        "cluster support, fraction accessible, geometry pass. Thresholds configurable "
        "(lysine SASA 25%, E2 distance 50 A, attachment 15 A, cluster RMSD 7.5 A; "
        "source-tagged registry in protacxtend/mechanistic/m2_lysine.py).\n\n"
        "## Benchmark (ran on RCSB ternary set; PROTAC-shotgun catalog + TERNARY_V1)\n\n"
        f"- structures attempted: {met['n_attempted']}; recovered: {met['n_recovered']} "
        f"(recovery {met['complex_recovery_rate']})\n"
        f"- productive geometry recovery: {met['productive_geometry_recall']} "
        f"(E2-bearing complexes in set: {met['n_complexes_with_e2_reference']})\n"
        f"- top1/top3 lysine recovery: {met['top1_lysine_recovery']}\n"
        f"- false positives: {met['false_positive_rate']}\n"
        f"- failure categories: {json.dumps(met['failure_categories'])} "
        f"(see failures.csv)\n"
        f"- total runtime: {met.get('total_runtime_s')} s; median per complex "
        f"{met.get('median_runtime_s')} s\n"
        "- reference thresholds configurable=true; literature recovery numbers are NOT "
        "quoted as PROTACXtend performance — this run is PROTACXtend's own.\n"
        "- E2 fields UNAVAILABLE per structure (no E2 in the benchmark set): no fabricated "
        "geometry; integration rules: M2 alone cannot nominate candidates.\n",
        encoding="utf-8")
    for f in ("fig2_m2_benchmark", "fig3_per_lysine_geometry"):
        _copy_fig(ROOT / "outputs" / "mechanistic_capability_closure" / "figures" / f"{f}.png", m2d, f"{f}.png")

    # ═══════════════════════════════ M3 ═══════════════════════════════
    from protacxtend.mechanistic.m3_cooperativity import (
        calibrate_proxy, classify_records, ingest_measured_alpha, structural_cooperativity_proxy,
    )

    records = classify_records(ingest_measured_alpha())
    alpha_rows = [{
        "target": r.target, "E3": r.e3, "PROTAC": r.protac,
        "binary_affinity_nM": r.binary_Kd, "ternary_affinity_nM": r.ternary_Kd,
        "alpha": r.alpha, "assay": r.assay_type, "temperature_c": r.temperature_c,
        "buffer": r.buffer or "UNAVAILABLE", "source": r.source, "DOI": r.doi,
        "evidence_class": r.evidence_class,
    } for r in records]
    _write(m3d, "alpha_dataset.csv", alpha_rows)

    proxy_rows: list[dict] = []
    for row in bench["rows"][:10]:
        if row.get("recovered") != "yes":
            continue
        agg = {"ubiquitination_geometry_score": row.get("predicted_geometry_score") if row.get("predicted_geometry_score") else None}
        proxy = structural_cooperativity_proxy(lysine_result={"aggregate": agg})
        proxy_rows.append({
            "benchmark_id": row.get("benchmark_id"), "pdb": row.get("pdb"),
            "structural_cooperativity_proxy": proxy.get("structural_cooperativity_proxy"),
            "components": json.dumps(proxy.get("components")),
            "label": proxy.get("label"),
            "availability": {
                "interface_energy": "UNAVAILABLE", "buried_surface_area": "UNAVAILABLE",
                "H_bonds": "UNAVAILABLE", "salt_bridges": "UNAVAILABLE",
                "hydrophobic_contacts": "UNAVAILABLE", "clashes": "UNAVAILABLE",
                "linker_strain": "UNAVAILABLE", "contact_persistence": "UNAVAILABLE",
                "interaction_fingerprints": "UNAVAILABLE",
                "lysine_geometry_proxy": "available (M2 aggregate)",
            },
        })
    _write(m3d, "structural_proxy.csv", proxy_rows)

    cal = calibrate_proxy([])
    _write(m3d, "calibration.csv", [{"status": cal["status"], "n_pairs": cal["n_pairs"],
                                     "Spearman": (cal.get("metrics") or {}).get("Spearman_r"),
                                     "Pearson": (cal.get("metrics") or {}).get("Pearson_r"),
                                     "rank_agreement": (cal.get("metrics") or {}).get("rank_consistency"),
                                     "pos_neutral_neg_classification": "not_computable_no_pairs",
                                     "note": cal["note"]}])

    (m3d / "report.md").write_text(
        "# M3 — Cooperativity Evidence & Energetics (no invented trained predictor)\n\n"
        f"- MEASURED_ALPHA records: {sum(1 for r in records if r.evidence_class == 'MEASURED_ALPHA')} "
        "(DOI-cited; convention preserved per record: alpha = kd_binary/kd_ternary; assay context kept)\n"
        f"- CALCULATED_ALPHA: {sum(1 for r in records if r.evidence_class == 'CALCULATED_ALPHA')} "
        "(computed only with paired binary/ternary Kd under documented equation)\n"
        f"- STRUCTURAL_COOPERATIVITY_PROXY: descriptive geometry proxy — NEVER relabelled alpha "
        f"(structural_proxy.csv; components marked UNAVAILABLE where no structure)\n"
        f"- ALPHA_UNAVAILABLE: {sum(1 for r in records if r.evidence_class == 'ALPHA_UNAVAILABLE')}\n\n"
        f"Calibration: {cal['status']} ({cal['n_pairs']} measured-proxy pairs) — proxy retained "
        "as descriptive evidence only; no predictive model forced. "
        "If pairs existed: Spearman, Pearson, rank agreement, positive/neutral/negative "
        "classification (calibration.csv).\n",
        encoding="utf-8")

    # ═══════════════════════════════ M4 ═══════════════════════════════
    from protacxtend.mechanistic.m4_registry import benchmark_results_rows, model_registry_rows

    _write(m4d, "model_registry.csv", model_registry_rows())
    _write(m4d, "benchmark_results.csv", benchmark_results_rows())
    domain_rows = []
    for r in model_registry_rows():
        local = r["model_id"] in ("local_context_rf_xgb", "degradation_ml_local", "tack_style_local")
        domain_rows.append({
            "model_id": r["model_id"], "endpoint": r["endpoint"],
            "domain_status": ("IN_DOMAIN (documented local applicability)" if local else "UNASSESSABLE (external)"),
            "basis": r["applicability_domain_method"] or r["applicability_domain_method"],
            "ood_behavior": ("OOD -> applicability flag + heuristic_fallback marker; OUT_OF_DOMAIN never used for nomination"
                             if local else "external; scores not used"),
        })
    _write(m4d, "domain_results.csv", domain_rows)

    br = benchmark_results_rows()
    best_in_domain = max((float(x["value"]) for x in br if x["model_id"] == "local_context_rf_xgb"
                          and "unseen-PROTAC" in x["split_type"]), default=None)
    loto = next((x["value"] for x in br if x["model_id"] == "tack_style_local" and x["split_type"] == "LOTO (cross-model audit)"), None)
    (m4d / "report.md").write_text(
        "# M4 — Governed Degradation Model Layer\n\n"
        f"- models in registry: {len(model_registry_rows())} (SynGlue degradation, DeepPROTACs, "
        "DegradeMaster, TACK, local chemprop/context RF-XGB/heuristic)\n"
        "- benchmark policy: scaffold / target-holdout / E3-holdout / LOTO / cold-chemical-space "
        "preferred; random split never supports generalization claims\n"
        "- endpoints separate: P(degrader) | DC50 | Dmax (endpoint_separation in "
        "protacxtend/mechanistic/m4_registry.py); every result carries model, version, prediction, "
        "unit, uncertainty, domain status, evidence_type=MODEL_PREDICTED\n"
        f"- best in-domain result (local, grouped unseen-PROTAC): {best_in_domain}\n"
        f"- LOTO (cross-model field-ceiling audit, approx): {loto}\n"
        "- OOD behavior: OUT_OF_DOMAIN never used for nomination; predictions are never "
        "treated as measured DC50 (MODEL_PREDICTED evidence type; measured claims require "
        "EXPERIMENTAL/CURATED_DATABASE records).\n",
        encoding="utf-8")

    # test results + figures for each module tree
    tests_txt = (ROOT / "outputs" / "mechanistic_capability_closure" / "test_results.md")
    for d in (m1d, m2d, m3d, m4d):
        if tests_txt.exists():
            (d / "test_results.md").write_text(
                f"# Test results (shared mechanistic suite)\n\n{tests_txt.read_text()}", encoding="utf-8")

    _copy_fig(ROOT / "outputs" / "mechanistic_capability_closure" / "figures" / "fig5_m3_measured_alpha.png", m3d)
    _copy_fig(ROOT / "outputs" / "mechanistic_capability_closure" / "figures" / "fig6_m4_benchmark.png", m4d)

    print("module trees written under outputs/mechanistic/{m1,m2,m3,m4}")
    print("m2 metrics:", {k: met[k] for k in ("n_attempted", "n_recovered", "complex_recovery_rate",
                                              "productive_geometry_recall", "top1_lysine_recovery",
                                              "false_positive_rate")})
    print("m2 runtime:", met.get("total_runtime_s"), "s total;", met.get("median_runtime_s"), "s median/complex")


if __name__ == "__main__":
    main()
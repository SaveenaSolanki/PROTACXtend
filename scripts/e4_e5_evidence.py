#!/usr/bin/env python
"""E4/E5 evidence-tier assembly.

E4 (mechanistic links) and E5 (TPD design) require independent expert scoring,
which the agent cannot supply. This script assembles the *reviewable* datasets,
computes only the objective, evidence-tier facts that code/data permit, and
leaves all scientific scores null.

Outputs:
  results/closure/e5_evidence_records.csv   per record: target/E3/compound tier
  results/closure/e4_reviewer_packet.csv    0/1/2 rubric template, unscored
  results/closure/e4_e5_status.json         achieved N, scored N, limitations
  results/closure/fig5_e4_e5_evidence_tiers.png/pdf
  results/closure/BRD4_VHL_NO_GO.md
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "closure"
DATA = ROOT / "protacxtend" / "data"


def _rows(name):
    p = DATA / name
    if not p.exists():
        return []
    return list(csv.DictReader(p.open(encoding="utf-8")))


def _is_demo(src: str) -> bool:
    return str(src).lower().startswith("local_demo") or "demo" in str(src).lower()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    warheads = _rows("curated_warheads.csv")
    e3 = _rows("curated_e3_ligands.csv")
    targets = _rows("curated_targets.csv")
    known = _rows("known_protac_smiles.csv") + _rows("protacdb_local.csv")

    records = []
    for w in warheads:
        records.append({"record_type": "warhead", "id": w.get("name"), "target": w.get("target"),
                        "e3": "", "smiles": w.get("smiles"), "evidence_tier": "demo_fixture" if _is_demo(w.get("source")) else "source_backed",
                        "source": w.get("source"), "doi": "", "measured_dc50": "",
                        "attachment_supported": False})
    for l in e3:
        t = "demo_fixture" if _is_demo(l.get("source")) else "source_backed"
        records.append({"record_type": "e3_ligand", "id": l.get("name"), "target": "",
                        "e3": l.get("e3_ligase"), "smiles": l.get("smiles"), "evidence_tier": t,
                        "source": l.get("source"), "doi": l.get("article_doi", ""),
                        "measured_dc50": "", "attachment_supported": bool(l.get("article_doi"))})
    for p in known:
        records.append({"record_type": "known_protac", "id": p.get("name") or p.get("protac_id"),
                        "target": p.get("target"), "e3": p.get("e3_ligase"), "smiles": p.get("smiles"),
                        "evidence_tier": "demo_fixture" if _is_demo(p.get("source")) else "source_backed",
                        "source": p.get("source"), "doi": p.get("doi", ""),
                        "measured_dc50": p.get("dc50_nm", ""), "attachment_supported": False})

    with (OUT / "e5_evidence_records.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(records[0].keys()))
        w.writeheader(); w.writerows(records)

    tiers = Counter(r["evidence_tier"] for r in records)
    typeof = Counter(r["record_type"] for r in records)

    # design candidates from the repaired run: attachment is hypothetical
    design = []
    repro = ROOT / "benchmark_results" / "closed48" / "reproduced_current" / "heldout_results.json"
    if repro.exists():
        for r in json.loads(repro.read_text()):
            if r.get("capability") == "DESIGN" and r.get("n_candidates"):
                design.append({"case_id": r["case_id"], "outcome": r["outcome"],
                               "n_candidates": r["n_candidates"],
                               "attachment_hypothesis": r.get("attachment_hypothesis", False)})

    status = {
        "E4": {
            "question": "Does the system justify disease->target->modality->E3/warhead->experiment with a falsifiable experiment and appropriate no-go?",
            "achieved_N_reviewable_contexts": len(targets),
            "scored_N": 0,
            "status": "reviewer packet assembled; mechanistic-link scores null (two blinded experts required)",
            "reviewer_packet": "e4_reviewer_packet.csv",
            "rubric": "0 incorrect/unsupported · 1 partially supported · 2 supported and context-correct",
        },
        "E5": {
            "question": "Does specialized chemistry/structure reasoning improve target/E3 ranking, exit-vector support, linker validity, ternary plausibility and measured degradation?",
            "achieved_N_records": len(records),
            "record_types": dict(typeof),
            "evidence_tiers": dict(tiers),
            "source_backed_records": tiers.get("source_backed", 0),
            "demo_fixture_records": tiers.get("demo_fixture", 0),
            "measured_dc50_labels": sum(1 for r in records if str(r["measured_dc50"]).strip()),
            "independently_supported_exit_vectors": sum(1 for r in records if r["attachment_supported"]),
            "design_candidates": design,
            "scored_N": 0,
            "status": "objective tiers computed; ranking/MAE/calibration null (no assay-specific measured labels)",
        },
        "limitations": [
            "All curated warheads are demo fixtures (0 source-backed) -> no independent exit-vector support.",
            "No assay-specific measured DC50/Dmax labels exist in the packaged data -> ranking/MAE not computable.",
            "Design candidates use hypothetical [*:1]/[*:2] attachment markers; require chemist review.",
            "E4/E5 scientific scores require two independent blinded experts; left null.",
        ],
    }
    (OUT / "e4_e5_status.json").write_text(json.dumps(status, indent=2))

    # E4 reviewer packet (unscored)
    with (OUT / "e4_reviewer_packet.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["link_id", "case_or_context", "disease", "target", "e3", "modality",
                    "mechanistic_link", "reviewer_1_0_1_2", "reviewer_2_0_1_2", "adjudicated_0_1_2", "notes"])
        link = ["disease_mechanism->target", "target->modality", "modality->E3", "E3->warhead",
                "warhead->linker", "complex->ubiquitination", "ubiquitination->degradation",
                "degradation->selectivity", "strategy->falsifying_experiment"]
        for t in targets[:12]:
            for l in link:
                w.writerow([f"{t.get('gene_symbol','')}:{l}", t.get("gene_symbol", ""), "", t.get("gene_symbol", ""),
                            "", "", l, "", "", "", ""])

    # figure: evidence tiers
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from protacxtend.validation.closure_figures import apply_style, save_square, style_axes
        apply_style()
        fig, ax = plt.subplots()
        cats = ["source_backed", "demo_fixture"]
        vals = [tiers.get(c, 0) for c in cats]
        ax.bar(cats, vals, color=["#1B9E77", "#D95F02"])
        for i, v in enumerate(vals):
            ax.text(i, v + 1, str(v), ha="center", fontsize=9)
        style_axes(ax, xlabel="Evidence tier", ylabel="Curated records (n)",
                   title="E5 evidence tiers — design/ranking scores PENDING review")
        save_square(fig, OUT / "fig5_e4_e5_evidence_tiers.png", dpi=600, pdf=True)
    except Exception as exc:  # noqa: BLE001
        print("figure skipped:", exc)

    (OUT / "BRD4_VHL_NO_GO.md").write_text(
        "# BRD4–VHL — no-go / abstention example\n\n"
        "In SCIENTIFIC mode the packaged warhead table is **6/6 demo fixtures**; the\n"
        "canonical engine therefore finds no source-backed, derivatizable BRD4 warhead\n"
        "and abstains rather than assembling a PROTAC from an unvalidated attachment\n"
        "vector. Real ChEMBL binders are retrieved but have no validated exit vector.\n\n"
        "- warhead support: 0/6 source-backed\n"
        "- exit-vector support: none independent\n"
        "- E3 side: source-backed VHL ligands exist (VH032/VH298/VHL_ligand_*, DOI-backed)\n"
        "- decision: **no-go until a source-backed BRD4 warhead with a validated exit\n"
        "  vector is supplied and reviewed by a chemist.**\n", encoding="utf-8")

    print(json.dumps({"records": len(records), "tiers": dict(tiers), "types": dict(typeof),
                      "design_candidates": len(design)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

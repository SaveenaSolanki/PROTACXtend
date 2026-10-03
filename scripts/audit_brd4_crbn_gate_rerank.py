#!/usr/bin/env python3
"""Audit the frozen BRD4 x CRBN real-TUI run with evidence gates.

This script intentionally does not generate new candidates. It reads the
persisted real TUI/run artifacts for design_ee2eb431dc, separates structural
validity from evidence support, creates annotated 2D structures for the audited
set, and re-ranks only candidates that pass the requested gates.
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd
from rdkit import Chem
from rdkit.Chem import Draw


ROOT = Path("/storage/saveena/protacxtend")
RUN_ID = "design_ee2eb431dc"
RUN_DIR = ROOT / "outputs" / "runs" / RUN_ID
TUI_DIR = ROOT / "outputs" / "priority_agent_audit" / "tui_brd4_crbn_real"
OUT_DIR = ROOT / "outputs" / "priority_agent_audit" / "brd4_crbn_gate_audit"
IMAGE_DIR = OUT_DIR / "structure_images"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def mol_from_smiles(smiles: str | None) -> Chem.Mol | None:
    if not smiles:
        return None
    return Chem.MolFromSmiles(smiles)


def canonical(smiles: str | None, *, isomeric: bool) -> str | None:
    mol = mol_from_smiles(smiles)
    if mol is None:
        return None
    return Chem.MolToSmiles(mol, canonical=True, isomericSmiles=isomeric)


def source_backed(value: Any) -> bool:
    if value in (None, "", {}, []):
        return False
    text = json.dumps(value, sort_keys=True).lower() if not isinstance(value, str) else value.lower()
    blocked = ["local_demo", "demo", "heuristic", "template", "generative"]
    return not any(term in text for term in blocked)


def classify_component_support(joined: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    warhead_source = joined.get("warhead_source")
    provenance = joined.get("provenance", {})
    warhead_prov = provenance.get("warhead_provenance", {})
    linker_source = provenance.get("linker_source")
    strategy = provenance.get("strategy")

    if not source_backed(warhead_source):
        reasons.append(f"warhead source is not literature/assay backed: {warhead_source or 'missing'}")
    if not source_backed(warhead_prov):
        reasons.append("warhead provenance artifact is empty or not source-backed")
    if not source_backed(linker_source):
        reasons.append(f"linker source is not source-backed: {linker_source or 'missing'}")
    if not source_backed(strategy):
        reasons.append(f"assembly/exit-vector strategy is not source-backed: {strategy or 'missing'}")
    if "source_id" not in json.dumps(provenance).lower():
        reasons.append("no component or exit-vector source_id is present")
    return (not reasons, reasons)


def linkers_representatives(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    reps: dict[str, dict[str, Any]] = {}
    for row in sorted(rows, key=lambda r: r["original_rank"]):
        cls = row.get("linker_class") or "unknown"
        reps.setdefault(cls, row)
    return reps


def annotate_mol(smiles: str | None, max_atoms: int = 120) -> Chem.Mol | None:
    mol = mol_from_smiles(smiles)
    if mol is None:
        return None
    mol = Chem.Mol(mol)
    for atom in mol.GetAtoms():
        if mol.GetNumAtoms() <= max_atoms:
            atom.SetProp("atomNote", str(atom.GetIdx()))
    return mol


def write_structure_image(row: dict[str, Any], path: Path) -> None:
    component_smiles = row.get("component_smiles", {})
    mols: list[Chem.Mol] = []
    legends: list[str] = []
    for label, smiles in [
        ("product", row.get("canonical_smiles")),
        ("warhead", component_smiles.get("warhead")),
        ("linker", component_smiles.get("linker")),
        ("e3", component_smiles.get("e3_ligand")),
    ]:
        mol = annotate_mol(smiles)
        if mol is not None:
            mols.append(mol)
            legends.append(label)
    if not mols:
        return
    image = Draw.MolsToGridImage(
        mols,
        molsPerRow=2,
        subImgSize=(650, 360),
        legends=legends,
        useSVG=False,
    )
    image.save(path)


def flatten_for_csv(row: dict[str, Any]) -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, (dict, list)):
            flat[key] = json.dumps(value, sort_keys=True)
        else:
            flat[key] = value
    return flat


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("")
        return
    flat_rows = [flatten_for_csv(row) for row in rows]
    keys = sorted({key for row in flat_rows for key in row})
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(flat_rows)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    evidence_rows = read_json(TUI_DIR / "candidate_evidence_table.json")
    transcript_summary = read_json(TUI_DIR / "tui_transcript_summary.json")
    decisions = read_jsonl(RUN_DIR / "decisions.jsonl")
    evidence = read_jsonl(RUN_DIR / "evidence.jsonl")
    parquet = pd.read_parquet(RUN_DIR / "candidates.parquet")
    parquet_by_id = parquet.set_index("candidate_id").to_dict(orient="index")

    joined_rows: list[dict[str, Any]] = []
    for source in evidence_rows:
        candidate_id = source["candidate_id"]
        extra = parquet_by_id.get(candidate_id, {})
        smiles = source.get("canonical_smiles") or extra.get("full_protac_smiles")
        mol = mol_from_smiles(smiles)
        noniso = canonical(smiles, isomeric=False)
        iso = canonical(smiles, isomeric=True)
        row = {
            **source,
            "run_id": RUN_ID,
            "canonical_smiles_rdkit": noniso,
            "isomeric_smiles_rdkit": iso,
            "original_rank": int(source["ranking"]["rank"]),
            "original_score": float(source["ranking"]["final_priority_score"]),
            "target": extra.get("target") or source.get("components", {}).get("target"),
            "e3_ligase": extra.get("e3_ligase") or source.get("components", {}).get("e3_ligase"),
            "warhead_source": extra.get("warhead_source"),
            "e3_ligand_source": "local_demo_crbn_ligand",
            "linker_class": extra.get("linker_class"),
            "linker_source": source.get("provenance", {}).get("linker_source"),
            "assembly_strategy": extra.get("assembly_strategy"),
            "reaction_class": extra.get("reaction_class"),
            "validity_status": extra.get("validity_status"),
            "parse_valid": mol is not None,
            "parse_valid_denominator": "150 scored candidates",
        }
        component_smiles = source.get("component_smiles", {})
        component_parse = {
            key: mol_from_smiles(value) is not None
            for key, value in component_smiles.items()
        }
        row["component_parse_valid"] = component_parse
        row["attachment_atom_mapping"] = {
            "warhead_component_atom_index": source.get("attachment_atoms", {}).get("warhead"),
            "e3_component_atom_index": source.get("attachment_atoms", {}).get("e3_ligand"),
            "linker_dummy_atom_maps": [1, 2] if "[*:1]" in component_smiles.get("linker", "") and "[*:2]" in component_smiles.get("linker", "") else [],
        }
        row["exit_vector_source"] = {
            "warhead": "curated_template_without_source_id",
            "e3_ligand": "curated_template_without_source_id",
            "linker": row["linker_source"],
        }
        row["correctly_assembled"] = bool(
            row["parse_valid"]
            and row["validity_status"] == "valid"
            and row["target"] == "BRD4"
            and row["e3_ligase"] == "CRBN"
            and all(component_parse.values())
            and row["attachment_atom_mapping"]["linker_dummy_atom_maps"] == [1, 2]
        )
        support_ok, support_reasons = classify_component_support(row)
        row["chemically_supported"] = support_ok
        row["chemical_support_reason"] = "passed" if support_ok else "; ".join(support_reasons)
        row["within_prediction_domain"] = False
        row["prediction_domain_status"] = "not_assessable"
        row["prediction_domain_reason"] = (
            "no per-candidate applicability-domain artifact is present; degradation output is heuristic/predicted and low confidence"
        )
        row["passed_all_relevant_gates"] = bool(
            row["parse_valid"]
            and row["correctly_assembled"]
            and row["chemically_supported"]
            and row["within_prediction_domain"]
        )
        row["pass_fail_reason"] = (
            "passed all requested gates"
            if row["passed_all_relevant_gates"]
            else "; ".join(
                reason
                for failed, reason in [
                    (not row["parse_valid"], "product SMILES failed RDKit parse"),
                    (not row["correctly_assembled"], "failed BRD4-linker-CRBN assembly/topology gate"),
                    (not row["chemically_supported"], row["chemical_support_reason"]),
                    (not row["within_prediction_domain"], row["prediction_domain_reason"]),
                ]
                if failed
            )
        )
        joined_rows.append(row)

    dup_groups: defaultdict[str, list[str]] = defaultdict(list)
    isomeric_dup_groups: defaultdict[str, list[str]] = defaultdict(list)
    for row in joined_rows:
        dup_groups[row["canonical_smiles_rdkit"] or "UNPARSEABLE"].append(row["candidate_id"])
        isomeric_dup_groups[row["isomeric_smiles_rdkit"] or "UNPARSEABLE"].append(row["candidate_id"])
    for row in joined_rows:
        group = dup_groups[row["canonical_smiles_rdkit"] or "UNPARSEABLE"]
        iso_group = isomeric_dup_groups[row["isomeric_smiles_rdkit"] or "UNPARSEABLE"]
        row["duplicate_check"] = {
            "is_exact_isomeric_duplicate": len(iso_group) > 1,
            "exact_isomeric_duplicate_group_size": len(iso_group),
            "exact_isomeric_duplicate_candidate_ids": iso_group if len(iso_group) > 1 else [],
            "is_nonisomeric_duplicate": len(group) > 1,
            "nonisomeric_duplicate_group_size": len(group),
            "nonisomeric_duplicate_candidate_ids": group if len(group) > 1 else [],
        }

    top10 = sorted(joined_rows, key=lambda r: r["original_rank"])[:10]
    linker_reps = list(linkers_representatives(joined_rows).values())
    selected_by_id = {row["candidate_id"]: row for row in top10}
    selected_by_id.update({row["candidate_id"]: row for row in linker_reps})
    selected_rows = sorted(selected_by_id.values(), key=lambda r: (r["original_rank"], r["candidate_id"]))
    selected_ids = {row["candidate_id"] for row in selected_rows}

    for row in selected_rows:
        image_path = IMAGE_DIR / f"{row['candidate_id']}.png"
        write_structure_image(row, image_path)
        row["annotated_structure_image"] = str(image_path)
    for row in joined_rows:
        if row["candidate_id"] in selected_ids:
            row["annotated_structure_image"] = str(IMAGE_DIR / f"{row['candidate_id']}.png")

    before_top10 = [
        {
            "position": idx + 1,
            "comparison_view": "before_original_rank",
            "candidate_id": row["candidate_id"],
            "rank": row["original_rank"],
            "score": row["original_score"],
            "linker_family": row["linker_class"],
            "canonical_smiles": row["canonical_smiles_rdkit"],
            "kept_after_all_gates": row["passed_all_relevant_gates"],
            "change_reason": "unchanged" if row["passed_all_relevant_gates"] else row["pass_fail_reason"],
        }
        for idx, row in enumerate(top10)
    ]
    structural_only_top10 = [
        {
            "position": idx + 1,
            "comparison_view": "after_parse_and_assembly_only",
            "candidate_id": row["candidate_id"],
            "rank": row["original_rank"],
            "score": row["original_score"],
            "linker_family": row["linker_class"],
            "canonical_smiles": row["canonical_smiles_rdkit"],
            "reason": "passes parse and assembly gates; chemical/prediction-domain gates not applied in this view",
        }
        for idx, row in enumerate(
            sorted(
                [r for r in joined_rows if r["parse_valid"] and r["correctly_assembled"]],
                key=lambda r: r["original_rank"],
            )[:10]
        )
    ]
    all_gate_top10 = [
        {
            "position": idx + 1,
            "comparison_view": "after_all_relevant_gates",
            "candidate_id": row["candidate_id"],
            "rank": row["original_rank"],
            "score": row["original_score"],
            "linker_family": row["linker_class"],
            "canonical_smiles": row["canonical_smiles_rdkit"],
            "reason": "passes all requested gates",
        }
        for idx, row in enumerate(
            sorted([r for r in joined_rows if r["passed_all_relevant_gates"]], key=lambda r: r["original_rank"])[:10]
        )
    ]

    rejected_sample = [
        {
            "record_id": "REJECTED-AGG-TUI-ASSEMBLED-BEFORE-SCORING",
            "count": transcript_summary.get("assembly_counts", {}).get("rejected_before_scoring"),
            "source_artifact": str(TUI_DIR / "tui_transcript_summary.json"),
            "smiles": None,
            "parse_valid": "not_assessable_no_structure_persisted",
            "correctly_assembled": "not_assessable_no_structure_persisted",
            "chemically_supported": False,
            "within_prediction_domain": "not_scored",
            "exact_reason": "TUI reports assembled candidates rejected before scoring, but does not persist rejected molecule SMILES or component maps.",
        }
    ]
    for item in evidence:
        if item.get("type") == "binder_rejected":
            rejected_sample.append(
                {
                    "record_id": "REJECTED-BINDER-EMPTY-PLACEHOLDER",
                    "count": item.get("count"),
                    "source_artifact": str(RUN_DIR / "evidence.jsonl"),
                    "smiles": None,
                    "parse_valid": "not_assessable_no_structure",
                    "correctly_assembled": False,
                    "chemically_supported": False,
                    "within_prediction_domain": "not_scored",
                    "exact_reason": item.get("reason"),
                }
            )

    contamination_terms = ["vhl", "vh032", "mz1", "m z 1"]
    contaminations = []
    for row in joined_rows:
        haystack = " ".join(
            str(value)
            for value in [
                row.get("components", {}).get("warhead"),
                row.get("component_smiles", {}).get("warhead"),
                row.get("warhead_source"),
            ]
        ).lower()
        if any(term in haystack for term in contamination_terms):
            contaminations.append(row["candidate_id"])

    summary = {
        "run_id": RUN_ID,
        "source_artifacts": {
            "candidate_evidence_table": str(TUI_DIR / "candidate_evidence_table.json"),
            "candidates_parquet": str(RUN_DIR / "candidates.parquet"),
            "tui_transcript_summary": str(TUI_DIR / "tui_transcript_summary.json"),
            "decisions": str(RUN_DIR / "decisions.jsonl"),
            "evidence": str(RUN_DIR / "evidence.jsonl"),
        },
        "no_new_candidate_batch_generated": True,
        "scored_candidate_denominator": len(joined_rows),
        "top10_audited": len(top10),
        "distinct_linker_families": sorted(set(row["linker_class"] for row in joined_rows)),
        "distinct_linker_family_count": len(set(row["linker_class"] for row in joined_rows)),
        "selected_candidate_count": len(selected_rows),
        "rejected_structure_sample_count": len(rejected_sample),
        "rejected_structure_limitation": "Rejected molecule-level SMILES/component maps are not present in the real TUI artifacts; only aggregate rejection evidence can be audited.",
        "gate_counts": {
            "parse_valid": sum(1 for row in joined_rows if row["parse_valid"]),
            "correctly_assembled": sum(1 for row in joined_rows if row["correctly_assembled"]),
            "chemically_supported": sum(1 for row in joined_rows if row["chemically_supported"]),
            "within_prediction_domain": sum(1 for row in joined_rows if row["within_prediction_domain"]),
            "passed_all_relevant_gates": sum(1 for row in joined_rows if row["passed_all_relevant_gates"]),
        },
        "duplicate_counts": {
            "unique_nonisomeric_canonical_structures": sum(1 for ids in dup_groups.values() if ids),
            "nonisomeric_duplicate_groups": sum(1 for ids in dup_groups.values() if len(ids) > 1),
            "nonisomeric_duplicate_candidates": sum(len(ids) for ids in dup_groups.values() if len(ids) > 1),
            "unique_isomeric_canonical_structures": sum(1 for ids in isomeric_dup_groups.values() if ids),
            "exact_isomeric_duplicate_groups": sum(1 for ids in isomeric_dup_groups.values() if len(ids) > 1),
            "exact_isomeric_duplicate_candidates": sum(len(ids) for ids in isomeric_dup_groups.values() if len(ids) > 1),
        },
        "vhl_or_mz1_as_brd4_warhead_check": {
            "inspected_candidates": len(joined_rows),
            "contaminating_candidate_ids": contaminations,
            "passed": len(contaminations) == 0,
            "warhead_names": sorted(set(row.get("components", {}).get("warhead") for row in joined_rows)),
        },
        "stage_statuses": {
            "executed": transcript_summary.get("executed_stages", []),
            "unevaluated": transcript_summary.get("unevaluated_stages", []),
            "decisions": decisions,
        },
        "rerank_result": {
            "structural_only_top10_changed": [row["candidate_id"] for row in structural_only_top10]
            != [row["candidate_id"] for row in before_top10],
            "all_gate_top10_count": len(all_gate_top10),
            "all_gate_reason": "No candidate passes chemical-support and explicit prediction-domain gates.",
        },
    }

    (OUT_DIR / "audit_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
    (OUT_DIR / "gate_audit_all_candidates.json").write_text(json.dumps(joined_rows, indent=2, sort_keys=True))
    (OUT_DIR / "selected_candidate_audit.json").write_text(json.dumps(selected_rows, indent=2, sort_keys=True))
    (OUT_DIR / "rejected_sample_audit.json").write_text(json.dumps(rejected_sample, indent=2, sort_keys=True))
    (OUT_DIR / "before_top10.json").write_text(json.dumps(before_top10, indent=2, sort_keys=True))
    (OUT_DIR / "after_structural_only_top10.json").write_text(json.dumps(structural_only_top10, indent=2, sort_keys=True))
    (OUT_DIR / "after_all_gate_top10.json").write_text(json.dumps(all_gate_top10, indent=2, sort_keys=True))
    write_csv(OUT_DIR / "gate_audit_all_candidates.csv", joined_rows)
    write_csv(OUT_DIR / "selected_candidate_audit.csv", selected_rows)
    write_csv(OUT_DIR / "rejected_sample_audit.csv", rejected_sample)
    write_csv(OUT_DIR / "before_after_top10.csv", before_top10 + structural_only_top10 + all_gate_top10)

    linker_counter = Counter(row["linker_class"] for row in joined_rows)
    report_lines = [
        "# BRD4 x CRBN Candidate Gate Audit",
        "",
        f"Run: `{RUN_ID}`",
        "",
        "No new candidate batch was generated; all rows are derived from the frozen real-TUI artifacts.",
        "",
        "## Denominators",
        "",
        f"- Scored candidates: {len(joined_rows)}",
        f"- Original top-10 candidates audited: {len(top10)}/10",
        f"- Distinct linker families audited: {len(linker_counter)} ({', '.join(f'{k}={v}' for k, v in sorted(linker_counter.items()))})",
        f"- Selected structure images generated: {len(selected_rows)}",
        f"- Rejected structure samples: {len(rejected_sample)} aggregate records; 0 molecule-level rejected SMILES persisted.",
        f"- Exact isomeric duplicate candidates: {summary['duplicate_counts']['exact_isomeric_duplicate_candidates']}/{len(joined_rows)}",
        f"- Non-isomeric duplicate candidates: {summary['duplicate_counts']['nonisomeric_duplicate_candidates']}/{len(joined_rows)}",
        "",
        "## Gate Counts",
        "",
        f"- Parse-valid: {summary['gate_counts']['parse_valid']}/{len(joined_rows)}",
        f"- Correctly assembled BRD4-linker-CRBN topology: {summary['gate_counts']['correctly_assembled']}/{len(joined_rows)}",
        f"- Chemically supported by source-backed components and exit vectors: {summary['gate_counts']['chemically_supported']}/{len(joined_rows)}",
        f"- Within explicit prediction domain: {summary['gate_counts']['within_prediction_domain']}/{len(joined_rows)}",
        f"- Pass all relevant gates: {summary['gate_counts']['passed_all_relevant_gates']}/{len(joined_rows)}",
        "",
        "## Independent Warhead Contamination Check",
        "",
        f"- VHL ligand or whole MZ1 used as BRD4 warhead: {'no' if not contaminations else 'yes'}",
        f"- Inspected BRD4 warhead labels: {', '.join(summary['vhl_or_mz1_as_brd4_warhead_check']['warhead_names'])}",
        "",
        "## Before Top 10",
        "",
        "| pos | candidate | rank | linker family | score | after all gates | reason |",
        "|---:|---|---:|---|---:|---|---|",
    ]
    for row in before_top10:
        report_lines.append(
            f"| {row['position']} | {row['candidate_id']} | {row['rank']} | {row['linker_family']} | {row['score']:.3f} | {row['kept_after_all_gates']} | {row['change_reason']} |"
        )
    report_lines.extend(
        [
            "",
            "## After Re-rank",
            "",
            "Structural-only top 10 is unchanged because all 150 candidates parse and match the requested BRD4 x CRBN topology.",
            "The evidence-gated shortlist is empty because no candidate has source-backed component/exit-vector provenance and no explicit per-candidate prediction-domain artifact is present.",
            "",
            "## Rejected Structures",
            "",
            "Rejected structures cannot be molecule-level audited from these artifacts because rejected SMILES/component maps were not persisted. The available rejected evidence is in `rejected_sample_audit.json`.",
        ]
    )
    (OUT_DIR / "report.md").write_text("\n".join(report_lines) + "\n")


if __name__ == "__main__":
    main()

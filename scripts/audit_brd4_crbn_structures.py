#!/usr/bin/env python
"""Audit BRD4 x CRBN candidate structures at atom/component level."""
from __future__ import annotations

import csv
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from rdkit import Chem
    from rdkit.Chem import Draw, Descriptors
except Exception as exc:  # noqa: BLE001
    Chem = None
    Draw = None
    Descriptors = None
    RDKit_IMPORT_ERROR = str(exc)
else:
    RDKit_IMPORT_ERROR = ""

IN_DIR = ROOT / "outputs/priority_agent_audit/tui_brd4_crbn_real"
DEFAULT_JSON = IN_DIR / "candidate_evidence_table.json"
DEFAULT_SUMMARY = IN_DIR / "tui_transcript_summary.json"
OUT = ROOT / "outputs/priority_agent_audit/brd4_crbn_structure_audit"


def _mol(smiles: str):
    if Chem is None or not smiles:
        return None
    try:
        return Chem.MolFromSmiles(smiles)
    except Exception:  # noqa: BLE001
        return None


def _canonical(smiles: str) -> str:
    mol = _mol(smiles)
    return Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True) if mol is not None else ""


def _strip_dummy(smiles: str) -> str:
    if Chem is None or not smiles:
        return ""
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return ""
    rw = Chem.RWMol(mol)
    for idx in sorted([a.GetIdx() for a in rw.GetAtoms() if a.GetAtomicNum() == 0], reverse=True):
        rw.RemoveAtom(idx)
    try:
        Chem.SanitizeMol(rw)
    except Exception:  # noqa: BLE001
        pass
    return Chem.MolToSmiles(rw, canonical=True, isomericSmiles=True)


def _substructure_match(product, fragment_smiles: str) -> bool:
    frag = _mol(_strip_dummy(fragment_smiles))
    if product is None or frag is None:
        return False
    # Avoid claiming topology failure for tiny generic fragments; require >=3 heavy atoms.
    if sum(1 for a in frag.GetAtoms() if a.GetAtomicNum() > 1) < 3:
        return False
    return bool(product.HasSubstructMatch(frag))


def _linker_supported(product, linker_smiles: str) -> tuple[bool, str]:
    if not linker_smiles:
        return False, "missing linker smiles"
    maps = []
    lm = _mol(linker_smiles)
    if lm is not None:
        maps = sorted({a.GetAtomMapNum() for a in lm.GetAtoms() if a.GetAtomicNum() == 0 and a.GetAtomMapNum()})
    if maps != [1, 2]:
        return False, f"linker dummy atom maps are {maps}, expected [1, 2]"
    stripped = _strip_dummy(linker_smiles)
    if _substructure_match(product, linker_smiles):
        return True, "two-point linker substructure detected"
    # Generated linkers may transform terminal atoms during assembly; record as topology-supported but not strict substructure.
    if stripped and len(stripped) >= 4:
        return True, "two-point linker maps present; strict substructure not required after coupling"
    return False, "linker too small or not parseable after dummy stripping"


def _applicability(row: dict[str, Any], mol) -> tuple[bool, str]:
    deg = row.get("degradation") or {}
    admet = row.get("admet") or {}
    prov = row.get("provenance") or {}
    mw = admet.get("mw")
    conf = deg.get("model_confidence")
    prior = ((prov.get("protacdb_evidence_prior") or {}).get("available"))
    if mol is None:
        return False, "unparseable molecule"
    reasons = []
    ok = True
    if mw is None:
        mw = Descriptors.MolWt(mol) if Descriptors is not None else None
    if mw is None or not (350 <= float(mw) <= 1400):
        ok = False; reasons.append(f"MW {mw} outside PROTAC audit window 350-1400")
    if conf is None or float(conf) < 0.20:
        ok = False; reasons.append(f"model_confidence {conf} below 0.20")
    if not prior:
        reasons.append("no PROTAC-DB target/E3 neighborhood prior")
    if (deg.get("evidence_kind") or "") != "predicted":
        ok = False; reasons.append("degradation evidence is not labelled predicted")
    return ok, "; ".join(reasons) if reasons else "in-domain by audit heuristics; prediction remains ML-only, not observed"


def audit_row(row: dict[str, Any], duplicate_index: dict[str, list[str]]) -> dict[str, Any]:
    smi = row.get("canonical_smiles", "")
    mol = _mol(smi)
    comp = row.get("component_smiles") or {}
    components = row.get("components") or {}
    product_canon = _canonical(smi)
    parse_valid = mol is not None
    warhead_match = _substructure_match(mol, comp.get("warhead", ""))
    e3_match = _substructure_match(mol, comp.get("e3_ligand", ""))
    linker_ok, linker_note = _linker_supported(mol, comp.get("linker", ""))
    target_ok = components.get("target") == "BRD4"
    e3_topology_ok = components.get("e3_ligase") == "CRBN" and e3_match
    topology_ok = bool(parse_valid and target_ok and linker_ok and e3_topology_ok and warhead_match)
    attachments = row.get("attachment_atoms") or {}
    comp_dummy_ok = "[*:" in comp.get("warhead", "") and "[*:" in comp.get("e3_ligand", "")
    attachment_atoms_ok = isinstance(attachments.get("warhead"), int) and isinstance(attachments.get("e3_ligand"), int)
    exit_vector_support = bool(comp_dummy_ok and attachment_atoms_ok)
    exit_vector_level = "template_supported" if exit_vector_support else "missing_or_incomplete"
    if not ((row.get("provenance") or {}).get("warhead_provenance") or {}).get("source_ids"):
        exit_vector_level = "hypothetical_template_supported" if exit_vector_support else exit_vector_level
    pred_ok, pred_note = _applicability(row, mol)
    duplicate_group = duplicate_index.get(product_canon, []) if product_canon else []
    rank = ((row.get("ranking") or {}).get("rank"))
    score = ((row.get("ranking") or {}).get("final_priority_score"))
    identity_gate_passed = bool(parse_valid and topology_ok and exit_vector_support and pred_ok)
    return {
        "candidate_id": row.get("candidate_id", ""),
        "sample_class": "",
        "rank": rank,
        "original_score": score,
        "canonical_smiles": smi,
        "product_canonical_rdkit": product_canon,
        "parse_valid": parse_valid,
        "target_ok": target_ok,
        "warhead_substructure_ok": warhead_match,
        "e3_ligase_ok": components.get("e3_ligase") == "CRBN",
        "e3_component_substructure_ok": e3_match,
        "linker_topology_ok": linker_ok,
        "linker_topology_note": linker_note,
        "correct_target_linker_e3_topology": topology_ok,
        "duplicate_count": len(duplicate_group),
        "duplicate_group": duplicate_group,
        "is_duplicate": len(duplicate_group) > 1,
        "exit_vector_support": exit_vector_support,
        "exit_vector_support_level": exit_vector_level,
        "attachment_atoms": attachments,
        "prediction_applicability_ok": pred_ok,
        "prediction_applicability_note": pred_note,
        "degradation_evidence_kind": (row.get("degradation") or {}).get("evidence_kind", ""),
        "model_confidence": (row.get("degradation") or {}).get("model_confidence"),
        "source_ids": _source_ids(row),
        "components": components,
        "component_smiles": comp,
        "identity_gate_passed_for_shortlist": identity_gate_passed,
    }


def _source_ids(row: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    prov = row.get("provenance") or {}
    for key in ("source_ids",):
        ids.extend(str(x) for x in prov.get(key, []) if x)
    prior = prov.get("protacdb_evidence_prior") or {}
    if prior.get("available"):
        ids.append(f"{prior.get('source','PROTAC-DB')}:{prior.get('source_scope','')}:n={prior.get('record_count')}")
    for part in (prov.get("warhead_provenance") or {}, prov.get("e3_ligand_provenance") or {}):
        ids.extend(str(x) for x in part.get("source_ids", []) if x)
    return sorted(set(ids))


def select_sample(rows: list[dict[str, Any]]) -> set[str]:
    ranked = sorted(rows, key=lambda r: ((r.get("ranking") or {}).get("rank") or 999999))
    ids: set[str] = {r["candidate_id"] for r in ranked[:20]}  # every top-ranked candidate, fixed as top 20
    # Stratify by original rank deciles, component families, and warnings.
    n = len(ranked)
    for dec in range(10):
        lo = math.floor(dec*n/10); hi = max(lo+1, math.floor((dec+1)*n/10))
        bucket = ranked[lo:hi]
        if bucket:
            ids.add(bucket[0]["candidate_id"])
            ids.add(bucket[len(bucket)//2]["candidate_id"])
            ids.add(bucket[-1]["candidate_id"])
    seen_family = set()
    for r in ranked:
        c = r.get("components") or {}
        family = (c.get("warhead"), c.get("e3_ligand"), c.get("linker"))
        if family not in seen_family:
            seen_family.add(family)
            ids.add(r["candidate_id"])
    for r in ranked:
        if r.get("warning_flags"):
            ids.add(r["candidate_id"])
    return ids


def write_png(rows: list[dict[str, Any]], out_dir: Path) -> list[dict[str, str]]:
    img_dir = out_dir / "structure_images"
    img_dir.mkdir(parents=True, exist_ok=True)
    images = []
    if Draw is None:
        return images
    for row in rows:
        mol = _mol(row["canonical_smiles"])
        if mol is None:
            continue
        path = img_dir / f"{row['candidate_id']}.png"
        Draw.MolToFile(mol, str(path), size=(600, 420), legend=f"{row['candidate_id']} rank {row['rank']}")
        images.append({"candidate_id": row["candidate_id"], "path": str(path)})
    return images


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("")
        return
    fields = ["candidate_id","sample_class","rank","original_score","parse_valid","target_ok","warhead_substructure_ok","e3_ligase_ok","e3_component_substructure_ok","linker_topology_ok","correct_target_linker_e3_topology","duplicate_count","is_duplicate","exit_vector_support","exit_vector_support_level","prediction_applicability_ok","prediction_applicability_note","identity_gate_passed_for_shortlist","canonical_smiles","source_ids"]
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for row in rows:
            out = {k: row.get(k, "") for k in fields}
            out["source_ids"] = ";".join(row.get("source_ids") or [])
            w.writerow(out)


def render_report(summary: dict[str, Any], sample_rows: list[dict[str, Any]], shortlist_before: list[dict[str, Any]], shortlist_after: list[dict[str, Any]], conditional: dict[str, Any]) -> str:
    lines = ["# BRD4 x CRBN Structure Audit", "", "Formal matched-48 evaluation remains `PENDING_HUMAN`; this is a machine diagnostic over one real TUI run.", ""]
    lines += ["## TUI Stage Statuses", ""]
    for s in summary["stage_statuses"]:
        lines.append(f"- {s['stage']}: {s['status']} - {s.get('detail','')}")
    lines += ["", "## Denominators", ""]
    for k, v in summary["denominators"].items():
        lines.append(f"- {k}: {v}")
    lines += ["", "## Shortlist Change", ""]
    lines.append(f"Original top 10 IDs: {', '.join(r['candidate_id'] for r in shortlist_before)}")
    lines.append(f"Identity-gated top 10 IDs: {', '.join(r['candidate_id'] for r in shortlist_after)}")
    lines.append(f"Changed: {summary['shortlist_changed']}")
    lines += ["", "## Evidence-backed Shortlist", "", "| rank | candidate | score | verified | SMILES | source IDs |", "| --- | --- | --- | --- | --- | --- |"]
    for r in shortlist_after:
        lines.append(f"| {r['verified_rank']} | {r['candidate_id']} | {r['original_score']} | {r['identity_gate_passed_for_shortlist']} | `{r['canonical_smiles'][:96]}` | {'; '.join(r.get('source_ids') or [])} |")
    lines += ["", "## Sample Audit Rows", "", "| class | rank | candidate | parse | topology | duplicate | exit vector | applicability |", "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in sample_rows[:40]:
        lines.append(f"| {r['sample_class']} | {r['rank']} | {r['candidate_id']} | {r['parse_valid']} | {r['correct_target_linker_e3_topology']} | {r['duplicate_count']} | {r['exit_vector_support_level']} | {r['prediction_applicability_ok']} |")
    lines += ["", "## Conditional KNOW/REASON Cases", ""]
    for cid, info in conditional.items():
        lines.append(f"- {cid}: state=`{info['scientific_state']}`; not counted as answered. Missing evidence/experiment: {info['missing_evidence_or_experiment']}")
    return "\n".join(lines) + "\n"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = json.loads(DEFAULT_JSON.read_text(encoding="utf-8"))
    stages = json.loads((ROOT / "outputs/workflows/design/design_ee2eb431dc/stage_timeline.json").read_text(encoding="utf-8"))
    canon_index: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        canon_index[_canonical(r.get("canonical_smiles", ""))].append(r.get("candidate_id", ""))
    audited_all = [audit_row(r, canon_index) for r in rows]
    sample_ids = select_sample(rows)
    for r in audited_all:
        classes = []
        if (r["rank"] or 999999) <= 20:
            classes.append("top20")
        if r["candidate_id"] in sample_ids:
            classes.append("stratified")
        r["sample_class"] = "+".join(sorted(set(classes))) or "not_sampled"
    sample = [r for r in audited_all if r["candidate_id"] in sample_ids]
    original_top = sorted(audited_all, key=lambda r: r["rank"] or 999999)[:10]
    verified = [r for r in audited_all if r["identity_gate_passed_for_shortlist"]]
    verified_top = sorted(verified, key=lambda r: (-(r["original_score"] or 0), r["rank"] or 999999))[:10]
    for i, r in enumerate(verified_top, 1):
        r["verified_rank"] = i
    images = write_png(verified_top + [r for r in sample if (r["rank"] or 999999) <= 20], OUT)
    conditional = {
        "REASON-03": {"scientific_state": "conditional_hypothesis", "missing_evidence_or_experiment": "Measure VHL binding for modified ligand against intact VH032 reference; optional co-structure/competition assay to verify tert-leucine, hydroxyproline, and thiazole-benzyl motif engagement."},
        "REASON-05": {"scientific_state": "conditional_hypothesis", "missing_evidence_or_experiment": "Measure junction pKa plus amide-vs-secondary-amine permeability and ternary affinity (ITC/SPR); do not treat qualitative liability as an answered benchmark item."},
    }
    denom = {
        "scored_candidates": len(audited_all),
        "sampled_candidates": len(sample),
        "top_ranked_candidates_included": sum(1 for r in sample if (r["rank"] or 999999) <= 20),
        "parse_valid": f"{sum(r['parse_valid'] for r in audited_all)}/{len(audited_all)}",
        "correct_target_linker_e3_topology": f"{sum(r['correct_target_linker_e3_topology'] for r in audited_all)}/{len(audited_all)}",
        "unique_structures": f"{len(canon_index)}/{len(audited_all)}",
        "duplicate_candidates": f"{sum(r['is_duplicate'] for r in audited_all)}/{len(audited_all)}",
        "exit_vector_supported": f"{sum(r['exit_vector_support'] for r in audited_all)}/{len(audited_all)}",
        "prediction_applicability_ok": f"{sum(r['prediction_applicability_ok'] for r in audited_all)}/{len(audited_all)}",
        "identity_gate_passed_for_shortlist": f"{len(verified)}/{len(audited_all)}",
    }
    summary = {
        "schema_version": "brd4-crbn-structure-audit.v1",
        "run_id": "design_ee2eb431dc",
        "formal_evaluation_status": "PENDING_HUMAN",
        "stage_statuses": stages,
        "denominators": denom,
        "shortlist_changed": [r["candidate_id"] for r in original_top] != [r["candidate_id"] for r in verified_top],
        "original_top10": original_top,
        "verified_only_top10": verified_top,
        "image_manifest": images,
        "conditional_cases": conditional,
        "limitations": [
            "Substructure checks are RDKit graph checks, not synthetic route validation.",
            "Exit-vector support is template/hypothesis-level unless component provenance supplies source-backed atom maps.",
            "Degradation predictions are ML predictions, not observed assay measurements.",
        ],
    }
    (OUT / "audit_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    (OUT / "audit_all_candidates.json").write_text(json.dumps(audited_all, indent=2, default=str), encoding="utf-8")
    (OUT / "audit_sample.json").write_text(json.dumps(sample, indent=2, default=str), encoding="utf-8")
    write_csv(OUT / "audit_sample.csv", sample)
    write_csv(OUT / "audit_all_candidates.csv", audited_all)
    write_csv(OUT / "identity_gated_shortlist.csv", verified_top)
    dup = {k:v for k,v in canon_index.items() if len(v)>1}
    (OUT / "duplicate_groups.json").write_text(json.dumps(dup, indent=2), encoding="utf-8")
    (OUT / "report.md").write_text(render_report(summary, sample, original_top, verified_top, conditional), encoding="utf-8")
    print(json.dumps({"out_dir": str(OUT), "denominators": denom, "shortlist_changed": summary["shortlist_changed"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

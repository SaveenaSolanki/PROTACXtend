#!/usr/bin/env python3
"""Independent candidate-structure validation for the BRD4 × CRBN slice run.

Re-validates every assembled candidate from the persisted engine artifacts
using a FRESH RDKit pass (parse -> canonical -> InChIKey -> formula/MW ->
component-substructure census -> stereochemistry -> dedup). The engine's own
validation stage is also reported; this is an independent verification layer,
not a re-implementation.

Outputs:
  outputs/brd4_crbn_vslice/run/brd4_crbn_vslice_v1/structure_validation.json
  outputs/brd4_crbn_vslice/run/brd4_crbn_vslice_v1/structure_validation.csv
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from rdkit import Chem
from rdkit.Chem import Crippen, Descriptors, Lipinski, rdMolDescriptors
from rdkit.Chem import RWMol
from rdkit.Chem.inchi import MolToInchiKey

REPO = Path("/storage/saveena/protacxtend")
RUN_ID = "brd4_crbn_vslice_v1"
WF = REPO / "outputs" / "workflows" / "design" / RUN_ID
OUT_DIR = REPO / "tui_dev" / "outputs" / "brd4_crbn_vslice" / "run" / RUN_ID
OUT_DIR.mkdir(parents=True, exist_ok=True)


def canon(smiles: str) -> tuple[str | None, str | None, dict]:
    """Return (canonical_smiles, inchi_key, info) or (None, None, error-info)."""
    info: dict = {}
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None, None, {"parse": "failed"}
    info["atoms"] = mol.GetNumAtoms()
    info["heavy_atoms"] = mol.GetNumHeavyAtoms()
    info["stereocenters"] = len(Chem.FindMolChiralCenters(mol, includeUnassigned=True, useLegacyImplementation=False))
    info["rotatable_bonds"] = Descriptors.NumRotatableBonds(mol)
    info["mw_exact"] = round(Descriptors.MolWt(mol), 2)
    info["formula"] = rdMolDescriptors.CalcMolFormula(mol)
    info["tpsa"] = round(Descriptors.TPSA(mol), 1)
    info["logp"] = round(Crippen.MolLogP(mol), 2)
    info["hbd"] = Lipinski.NumHDonors(mol)
    info["hba"] = Lipinski.NumHAcceptors(mol)
    try:
        c = Chem.MolToSmiles(mol)
        key = MolToInchiKey(mol)
    except Exception as exc:  # noqa: BLE001
        return None, None, {"canon_failed": str(exc)}
    # round-trip: canonical must re-parse
    rt = Chem.MolFromSmiles(c)
    info["roundtrip_parse"] = rt is not None
    return c, key, info


def component_check(candidate_smiles: str, *fragments: str) -> dict:
    """Component-substructure census with attachment-dummy handling.

    Fragments from the evidence table carry attachment dummies (e.g. [*:1]).
    We report two tiers:
      full_frag_match — the fragment matches as-is (dummy wildcard);
      core_present — the fragment with its dummy atom(s) removed matches
                     (component CORE is present in the assembled product).
    """
    out: dict = {}
    mol = Chem.MolFromSmiles(candidate_smiles)
    if mol is None:
        return {"parse_failed": True}
    for i, frag in enumerate(fragments):
        if not frag:
            out[f"frag{i}"] = "not_supplied"
            continue
        fmol = Chem.MolFromSmiles(frag)
        if fmol is None:
            out[f"frag{i}"] = "unparseable_fragment"
            continue
        full_match = mol.HasSubstructMatch(fmol, useChirality=False)
        # Dummy-stripped core: remove dummy atoms one at a time (RDKit keeps
        # the remaining ring/chain bonds and adds implicit H to the neighbor).
        core = None
        rw = RWMol(fmol)
        dummy_idx = [a.GetIdx() for a in rw.GetAtoms() if a.GetAtomicNum() == 0]
        for idx in sorted(dummy_idx, reverse=True):
            rw.RemoveAtom(idx)
        rw = rw.GetMol()
        try:
            core_smi = Chem.MolToSmiles(rw)
            core_mol = Chem.MolFromSmiles(core_smi)
            core = core_mol is not None and mol.HasSubstructMatch(core_mol, useChirality=False)
        except Exception:  # noqa: BLE001
            core = None
        out[f"frag{i}"] = {
            "full_frag_match": bool(full_match),
            "core_present": bool(core) if core is not None else None,
            "core_smiles": core_smi if core is not None else "",
        }
    return out
    return out


def main() -> None:
    rows = json.loads((WF / "candidate_evidence.json").read_text())
    print(f"candidates in evidence table: {len(rows)}", flush=True)

    output_rows = []
    failures = {"parse_failed": [], "roundtrip_failed": [], "inchi_missing": []}
    seen_keys: dict[str, int] = {}

    for r in rows:
        cid = r["candidate_id"]
        engine_smiles = r.get("canonical_smiles") or ""
        c, key, info = canon(engine_smiles)
        comp = r.get("components") or {}
        comp_smiles = r.get("component_smiles") or {}
        subs = component_check(engine_smiles,
                               comp_smiles.get("warhead") or "",
                               comp_smiles.get("e3_ligand") or "",
                               comp_smiles.get("linker") or "")
        engine_valid = (r.get("validity") or "") if "validity" in r else "valid"
        rec = {
            "candidate_id": cid,
            "engine_smiles": engine_smiles,
            "independent_parse": bool(c),
            "canonical_smiles": c,
            "inchi_key": key,
            "roundtrip_parse": info.get("roundtrip_parse", False) if c else False,
            "formula": info.get("formula") if c else None,
            "mw_exact": info.get("mw_exact") if c else None,
            "atoms": info.get("atoms") if c else None,
            "heavy_atoms": info.get("heavy_atoms") if c else None,
            "stereocenters": info.get("stereocenters") if c else None,
            "rotatable_bonds": info.get("rotatable_bonds") if c else None,
            "tpsa": info.get("tpsa") if c else None,
            "logp": info.get("logp") if c else None,
            "hbd": info.get("hbd") if c else None,
            "hba": info.get("hba") if c else None,
            "engine_valid_flag": engine_valid,
            "component_census": subs,
            "warning_flags": r.get("warning_flags") or [],
            "provenance_strategy": (r.get("provenance") or {}).get("strategy"),
            "provenance_warhead_verified": bool((r.get("provenance") or {}).get("warhead_provenance")),
        }
        if c is None:
            failures["parse_failed"].append(cid)
        elif not info.get("roundtrip_parse"):
            failures["roundtrip_failed"].append(cid)
        if key:
            seen_keys[key] = seen_keys.get(key, 0) + 1
        else:
            failures["inchi_missing"].append(cid)
        output_rows.append(rec)

    dups = {k: v for k, v in seen_keys.items() if v > 1}

    def frag_hit(r: dict, idx: int) -> bool | None:
        v = r["component_census"].get(f"frag{idx}")
        return v.get("core_present") if isinstance(v, dict) else None

    summary = {
        "run_id": RUN_ID,
        "source": str(WF / "candidate_evidence.json"),
        "n_candidates": len(output_rows),
        "n_independent_parse_ok": sum(1 for r in output_rows if r["independent_parse"]),
        "n_roundtrip_ok": sum(1 for r in output_rows if r["roundtrip_parse"]),
        "n_unique_inchikeys": len(seen_keys),
        "n_duplicate_inchikey_groups": len(dups),
        "duplicate_groups": {k: {"count": v, "ids": [r["candidate_id"] for r in output_rows if r["inchi_key"] == k][:6]} for k, v in dups.items()},
        "failures": failures,
        "component_census": {
            "warhead_core_present": sum(1 for r in output_rows if frag_hit(r, 0) is True),
            "e3_ligand_core_present": sum(1 for r in output_rows if frag_hit(r, 1) is True),
            "linker_core_present": sum(1 for r in output_rows if frag_hit(r, 2) is True),
            "warhead_full_match": sum(1 for r in output_rows if isinstance(r["component_census"].get("frag0"), dict) and r["component_census"]["frag0"]["full_frag_match"]),
            "e3_ligand_full_match": sum(1 for r in output_rows if isinstance(r["component_census"].get("frag1"), dict) and r["component_census"]["frag1"]["full_frag_match"]),
            "linker_full_match": sum(1 for r in output_rows if isinstance(r["component_census"].get("frag2"), dict) and r["component_census"]["frag2"]["full_frag_match"]),
            "not_supplied": sum(1 for r in output_rows if "not_supplied" in r["component_census"].values()),
            "unparseable_fragment": sum(1 for r in output_rows if "unparseable_fragment" in r["component_census"].values()),
        },
        "provenance_census": {
            "curated_template": sum(1 for r in output_rows if r["provenance_strategy"] == "curated_template"),
            "warhead_provenance_verified": sum(1 for r in output_rows if r["provenance_warhead_verified"]),
        },
        "stereocenter_census": {
            "with_stereocenters": sum(1 for r in output_rows if (r["stereocenters"] or 0) > 0),
            "without_stereocenters": sum(1 for r in output_rows if r["stereocenters"] == 0),
        },
        "note": ("Independent RDKit validation layer over the engine's persisted candidate "
                 "evidence; chemical validity is NOT biological activity. Component cores "
                 "are checked with attachment dummies stripped; full-fragment matches require "
                 "the assembled product to contain the component as-is."),
    }

    (OUT_DIR / "structure_validation.json").write_text(json.dumps({
        "summary": summary, "candidates": output_rows}, indent=2, default=str))

    fieldnames = [k for k in output_rows[0] if k not in ("component_census", "warning_flags", "provenance_strategy", "provenance_warhead_verified")]
    with (OUT_DIR / "structure_validation.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["candidate_id", "independent_parse", "canonical_smiles",
                                          "inchi_key", "formula", "mw_exact", "stereocenters",
                                          "component_warhead", "component_e3_ligand", "component_linker",
                                          "engine_valid_flag"])
        w.writeheader()
        for r in output_rows:
            w.writerow({
                "candidate_id": r["candidate_id"],
                "independent_parse": r["independent_parse"],
                "canonical_smiles": r["canonical_smiles"] or "",
                "inchi_key": r["inchi_key"] or "",
                "formula": r["formula"] or "",
                "mw_exact": r["mw_exact"] or "",
                "stereocenters": r["stereocenters"] if r["stereocenters"] is not None else "",
                "component_warhead": (r["component_census"].get("frag0") or {}).get("core_present") if isinstance(r["component_census"].get("frag0"), dict) else r["component_census"].get("frag0"),
                "component_e3_ligand": (r["component_census"].get("frag1") or {}).get("core_present") if isinstance(r["component_census"].get("frag1"), dict) else r["component_census"].get("frag1"),
                "component_linker": (r["component_census"].get("frag2") or {}).get("core_present") if isinstance(r["component_census"].get("frag2"), dict) else r["component_census"].get("frag2"),
                "engine_valid_flag": r["engine_valid_flag"],
            })

    print(json.dumps(summary, indent=2, default=str))
    print(f"wrote {OUT_DIR / 'structure_validation.json'}")


if __name__ == "__main__":
    main()
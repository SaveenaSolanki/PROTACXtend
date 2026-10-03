#!/usr/bin/env python
"""Build ``protacxtend/data/verified_components.json`` from real PROTACs.

Source of truth: the repo's own PROTAC-DB export
(``data/protac_repos/repos/PROTAC-Degradation-Predictor/data/PROTAC-Degradation-DB.csv``),
rows for MZ1 / dBET1 / MT-802.

For each PROTAC the linker is located by a per-PROTAC SMARTS; the two bonds
flanking the linker are cut, giving warhead + linker + E3-ligand fragments.
Identity is verified by re-zipping the fragments with RDKit ``molzip`` and
checking the InChIKey equals the source PROTAC's InChIKey. A build that fails
the identity check is refused.

Every stored component carries: canonical + isomeric SMILES, InChIKey, mapped
attachment atom, source (PROTAC/DOI/PDB), target/E3, applicability limits, and
``verified`` is only True when the identity check passed.

Run::

    python scripts/build_verified_components.py
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any

from rdkit import Chem
from rdkit.Chem import Descriptors
from rdkit.Chem.inchi import MolToInchiKey

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data/protac_repos/repos/PROTAC-Degradation-Predictor/data/PROTAC-Degradation-DB.csv"
OUT = ROOT / "protacxtend/data/verified_components.json"

# Per-PROTAC linker SMARTS. The match's first and last atoms define the two
# linker junctions; the atoms bonded to them outside the match are the component
# attachment atoms.
PROTACS: list[dict[str, Any]] = [
    {
        "name": "MZ1", "target_filter": "O60885", "role": "BRD4-VHL",
        "linker_smarts": "[CX3](=O)[CH2][OX2][CH2][CH2][OX2][CH2][CH2][OX2][CH2][CH2][NX3][CX3]=O",
        "e3_smarts": "[CX4]1C[C@H](O)C[NX3]1",  # hydroxyproline (VHL)
        "warhead_name": "MZ1 BRD4 ligand (JQ1 triazolodiazepine)",
        "e3_name": "MZ1 VHL ligand (VH032)",
        "linker_name": "MZ1 PEG3 linker",
        # Attribution correction: the PROTAC-DB row cites a later comparison study
        # (10.1021/acs.jmedchem.6b01912). The MZ1 discovery paper is Zengerle,
        # Chan & Ciulli 2015; the PDB 5T35 ternary structure is Gadd et al. 2017.
        "discovery_doi": "10.1021/acschembio.5b00216",
        "discovery_citation": "Zengerle, Chan & Ciulli, ACS Chem Biol 2015 (MZ1), DOI 10.1021/acschembio.5b00216",
        "structure_doi": "10.1038/nchembio.2329",
        "structure_citation": "Gadd et al., Nat Chem Biol 2017 (PDB 5T35), DOI 10.1038/nchembio.2329",
        "db_row_doi_note": "PROTAC-DB row cites 10.1021/acs.jmedchem.6b01912 (later comparison study), not the MZ1 discovery paper",
        "applicability": {"warhead": ["BRD4 BD1/BD2", "BET family; selectivity not implied"],
                          "e3_ligand": ["VHL VBC complex", "not CRBN"],
                          "linker": ["rigid-length PEG3; not a general linker library"]},
    },
    {
        "name": "dBET1", "target_filter": "O60885", "role": "BRD4-CRBN",
        "linker_smarts": "[CX3](=O)[NX3][CH2][CH2][CH2][CH2][NX3][CX3](=O)[CH2][OX2]",
        "e3_smarts": "C1CCC(=O)NC1=O",  # glutarimide (CRBN)
        "warhead_name": "dBET1 BRD4 ligand (JQ1 triazolodiazepine)",
        "e3_name": "dBET1 CRBN ligand (pomalidomide-type)",
        "linker_name": "dBET1 alkyl-amide linker",
        "applicability": {"warhead": ["BRD4 BD1/BD2", "BET family; selectivity not implied"],
                          "e3_ligand": ["CRBN thalidomide-binding domain", "not VHL"],
                          "linker": ["alkyl/diamide linker; not a general linker library"]},
    },
    {
        "name": "MT-802", "target_filter": "Q06187", "role": "BTK-CRBN",
        "linker_smarts": "[CH2][CH2][OX2][CH2][CH2][OX2][CH2][CX3](=O)[NX3]",
        "e3_smarts": "C1CCC(=O)NC1=O",  # glutarimide (CRBN)
        "warhead_name": "MT-802 BTK ligand (pyrimidine-phenyl)",
        "e3_name": "MT-802 CRBN ligand (pomalidomide-type)",
        "linker_name": "MT-802 PEG2-amide linker",
        "applicability": {"warhead": ["BTK kinase domain", "not a BET bromodomain"],
                          "e3_ligand": ["CRBN thalidomide-binding domain", "not VHL"],
                          "linker": ["short PEG2-amide linker; not a general linker library"]},
    },
]


def _load_rows() -> list[dict[str, str]]:
    with CSV_PATH.open(newline="", encoding="utf-8", errors="replace") as fh:
        return list(csv.DictReader(fh))


def _row_for(rows: list[dict[str, str]], name: str, uniprot: str) -> dict[str, str] | None:
    for row in rows:
        if (row.get("Name") or "").strip() == name and (row.get("Uniprot") or "").strip() == uniprot:
            return row
    return None


def _assign_dummy_maps(mol: Chem.Mol, mapping: dict[int, int]) -> Chem.Mol:
    """Set map numbers on dummy atoms and clear isotopes."""
    rw = Chem.RWMol(mol)
    for atom in rw.GetAtoms():
        if atom.GetAtomicNum() == 0:
            atom.SetIsotope(0)
            atom.SetAtomMapNum(mapping.get(atom.GetIdx(), 1))
    return rw.GetMol()


def _capped_inchikey(smiles: str) -> str:
    """InChIKey of the fragment with its attachment dummy replaced by H."""
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return ""
    rw = Chem.RWMol(mol)
    for atom in rw.GetAtoms():
        if atom.GetAtomicNum() == 0:
            atom.SetAtomicNum(1)
            atom.SetIsotope(0)
            atom.SetAtomMapNum(0)
    try:
        capped = rw.GetMol()
        Chem.SanitizeMol(capped)
        return MolToInchiKey(capped)
    except Exception:  # noqa: BLE001
        return ""


def _decompose(smiles: str, spec: dict[str, Any]) -> dict[str, Any]:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise SystemExit(f"{spec['name']}: SMILES did not parse")
    linker_smarts = Chem.MolFromSmarts(spec["linker_smarts"])
    match = mol.GetSubstructMatch(linker_smarts)
    if not match:
        raise SystemExit(f"{spec['name']}: linker SMARTS did not match; refusing to guess cuts")
    first, last = match[0], match[-1]

    def _junction(anchor_candidates):
        """Find (anchor_in_match, component_atom) for a linker junction.

        Walks the match from the given end and returns the first anchor with a
        non-oxygen neighbour outside the match (so a terminal carbonyl oxygen is
        skipped and the junction N/C is used).
        """
        for anchor in anchor_candidates:
            outs = [n.GetIdx() for n in mol.GetAtomWithIdx(anchor).GetNeighbors()
                    if n.GetIdx() not in match]
            non_oxygen = [i for i in outs if mol.GetAtomWithIdx(i).GetSymbol() != "O"]
            if non_oxygen:
                return anchor, non_oxygen[0]
        return None, None

    left_anchor, left_junction = _junction(match)
    right_anchor, right_junction = _junction(reversed(match))
    if left_junction is None or right_junction is None:
        raise SystemExit(f"{spec['name']}: could not locate both linker junctions")
    cut_pairs = [(left_anchor, left_junction), (right_anchor, right_junction)]
    cut_bonds = [mol.GetBondBetweenAtoms(a, b).GetIdx() for a, b in cut_pairs]
    fragmented = Chem.FragmentOnBonds(mol, cut_bonds, addDummies=True)
    pieces = list(Chem.GetMolFrags(fragmented, asMols=True, sanitizeFrags=True))
    if len(pieces) != 3:
        raise SystemExit(f"{spec['name']}: expected 3 fragments, got {len(pieces)}")

    e3_pattern = Chem.MolFromSmarts(spec["e3_smarts"])
    e3 = next((p for p in pieces if p.HasSubstructMatch(e3_pattern)), None)
    linker = next((p for p in pieces
                   if p is not e3 and sum(1 for a in p.GetAtoms() if a.GetAtomicNum() == 0) == 2), None)
    warhead = next((p for p in pieces if p is not e3 and p is not linker), None)
    if warhead is None or e3 is None or linker is None:
        raise SystemExit(f"{spec['name']}: could not assign warhead/linker/e3 roles")

    # Assign map numbers so molzip can re-zip: linker dummy next to the warhead
    # side and the warhead dummy share map 1; linker dummy next to the e3 side
    # and the e3 dummy share map 2.
    warhead_dummy = [a.GetIdx() for a in warhead.GetAtoms() if a.GetAtomicNum() == 0][0]
    e3_dummy = [a.GetIdx() for a in e3.GetAtoms() if a.GetAtomicNum() == 0][0]
    linker_dummies = [a.GetIdx() for a in linker.GetAtoms() if a.GetAtomicNum() == 0]

    # ``FragmentOnBonds`` stores the removed partner atom's original index as the
    # dummy's isotope. Use the per-fragment original-index tuples to decide which
    # linker dummy connects to the warhead (map 1) vs the E3 ligand (map 2).
    idx_lists = Chem.GetMolFrags(fragmented, asMols=False)
    warhead_i = next(i for i, p in enumerate(pieces) if p is warhead)
    e3_i = next(i for i, p in enumerate(pieces) if p is e3)
    warhead_atoms = set(idx_lists[warhead_i])
    e3_atoms = set(idx_lists[e3_i])
    linker_map: dict[int, int] = {}
    for dummy in linker_dummies:
        partner = linker.GetAtomWithIdx(dummy).GetIsotope()
        if partner in warhead_atoms:
            linker_map[dummy] = 1
        elif partner in e3_atoms:
            linker_map[dummy] = 2
        else:
            # Fallback: a carbon neighbour is the warhead side.
            nb = linker.GetAtomWithIdx(dummy).GetNeighbors()[0]
            linker_map[dummy] = 1 if nb.GetSymbol() == "C" else 2

    warhead_mapped = _assign_dummy_maps(warhead, {warhead_dummy: 1})
    e3_mapped = _assign_dummy_maps(e3, {e3_dummy: 2})
    linker_mapped = _assign_dummy_maps(linker, linker_map)

    # Identity check via molzip.
    zipped = Chem.molzip(Chem.CombineMols(Chem.CombineMols(warhead_mapped, linker_mapped), e3_mapped))
    zipped_key = MolToInchiKey(zipped)
    source_key = MolToInchiKey(mol)
    identity_ok = zipped_key == source_key
    if not identity_ok:
        raise SystemExit(
            f"{spec['name']}: split/reassembly identity FAILED ({zipped_key} != {source_key}); "
            "component build refused"
        )

    # Normalise to the toolbox assembly convention: warhead [*:1], e3 [*:1],
    # linker warhead-side [*:1] and e3-side [*:2].
    def _toolbox_maps(m: Chem.Mol, mapping: dict[int, int]) -> Chem.Mol:
        rw = Chem.RWMol(m)
        for a in rw.GetAtoms():
            if a.GetAtomicNum() == 0 and a.GetIdx() in mapping:
                a.SetAtomMapNum(mapping[a.GetIdx()])
        return rw.GetMol()

    warhead_out = _toolbox_maps(warhead_mapped, {warhead_dummy: 1})
    e3_out = _toolbox_maps(e3_mapped, {e3_dummy: 1})
    linker_out = _toolbox_maps(linker_mapped, linker_map)
    return {
        "warhead": Chem.MolToSmiles(warhead_out, isomericSmiles=True),
        "linker": Chem.MolToSmiles(linker_out, isomericSmiles=True),
        "e3_ligand": Chem.MolToSmiles(e3_out, isomericSmiles=True),
        "identity_ok": identity_ok,
        "source_inchikey": source_key,
        "source_smiles": Chem.MolToSmiles(mol, isomericSmiles=True),
        "source_mw": round(Descriptors.MolWt(mol), 3),
    }


def _assay_fields(row: dict[str, str]) -> dict[str, Any]:
    """Source-linked experimental assay fields; missing stays 'not_reported'."""

    def val(key: str) -> Any:
        raw = (row.get(key) or "").strip()
        return raw if raw else "not_reported"

    return {
        "dc50_nM": val("DC50 (nM)"),
        "dmax_percent": val("Dmax (%)"),
        "cell_line": val("Cell Type"),
        "treatment_time_h": val("Treatment Time (h)"),
        "assay": val("Assay (DC50/Dmax)"),
        "article_doi": val("Article DOI"),
        "database": val("Database"),
        "pdb": val("PDB"),
        "molecular_formula": val("Molecular Formula"),
        "source_inchikey": val("InChI Key"),
        "source": "PROTAC-DB (PROTAC-Degradation-DB.csv)",
        "note": "Measurements are as reported by PROTAC-DB; missing fields are not_reported and are never filled by predictions.",
    }


def main() -> int:
    rows = _load_rows()
    components: list[dict[str, Any]] = []
    references: list[dict[str, Any]] = []
    for spec in PROTACS:
        row = _row_for(rows, spec["name"], spec["target_filter"])
        if row is None:
            raise SystemExit(f"{spec['name']}: source row not found in PROTAC-DB export")
        frags = _decompose(row["Smiles"].strip(), spec)
        target = (row.get("Target") or "").strip()
        e3_ligase = (row.get("E3 Ligase") or "").strip()
        db_doi = (row.get("Article DOI") or "").strip()
        primary_doi = spec.get("discovery_doi") or db_doi
        citation = spec.get("discovery_citation", "")
        structure_doi = spec.get("structure_doi", "")
        source = f"PROTAC-DB {spec['name']}; " + (citation or f"DOI {primary_doi}")
        if structure_doi:
            source += f"; structure DOI {structure_doi}"
        if row.get("PDB"):
            source += f"; PDB {row['PDB']}"
        for role, comp_id, name, extra in [
            ("warhead", f"{target}_{spec['name']}_warhead", spec["warhead_name"],
             {"target": target}),
            ("e3_ligand", f"{e3_ligase}_{spec['name']}_ligand", spec["e3_name"],
             {"e3_ligase": e3_ligase}),
            ("linker", f"{spec['name']}_linker", spec["linker_name"], {}),
        ]:
            smiles = frags[role]
            components.append({
                "component_id": comp_id,
                "role": role,
                "name": name,
                "smiles": smiles,
                "canonical_smiles": Chem.MolToSmiles(Chem.MolFromSmiles(smiles), isomericSmiles=False),
                "isomeric_smiles": smiles,
                "inchikey": _capped_inchikey(smiles),
                "inchikey_note": "InChIKey of the attachment-hydrogen (capped) fragment",
                "attachment_atom_map": 1 if role != "linker" else "1(warhead)/2(e3)",
                "source": source,
                "source_protac": spec["name"],
                "applicability": spec["applicability"].get(role, []),
                "verified": True,
                "identity_check": "molzip reassembly reproduces source InChIKey",
                **extra,
            })
        references.append({
            "name": spec["name"],
            "role": spec["role"],
            "smiles": frags["source_smiles"],
            "canonical_smiles": Chem.MolToSmiles(Chem.MolFromSmiles(frags["source_smiles"]), isomericSmiles=False),
            "inchikey": frags["source_inchikey"],
            "mw": frags["source_mw"],
            "pdb": (row.get("PDB") or "not_reported").strip() or "not_reported",
            "doi": primary_doi or "not_reported",
            "db_row_doi": db_doi or "not_reported",
            "citation": citation,
            "structure_doi": structure_doi,
            "attribution_note": spec.get("db_row_doi_note", ""),
            "source_table": "data/protac_repos/repos/PROTAC-Degradation-Predictor/data/PROTAC-Degradation-DB.csv",
            "assays": _assay_fields(row),
        })

    payload = {
        "schema": "verified_components.v2",
        "note": ("Real, atom-mapped PROTAC components derived from curated structures of KNOWN "
                 "compounds (MZ1 / dBET1 / MT-802). These are reconstruction references, never novel "
                 "designs. Every component passed a split/reassembly InChIKey identity check. "
                 "MZ1 attribution corrected to the discovery paper 10.1021/acschembio.5b00216 and "
                 "structure 10.1038/nchembio.2329 (PDB 5T35); the PROTAC-DB row DOI "
                 "10.1021/acs.jmedchem.6b01912 is a later comparison study."),
        "assembly_convention": "warhead [*:1]; linker [*:1]->warhead, [*:2]->E3; E3 ligand [*:1]",
        "components": components,
        "references": references,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {OUT}")
    for ref in references:
        print(f"  {ref['name']} ({ref['role']}): InChIKey {ref['inchikey']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

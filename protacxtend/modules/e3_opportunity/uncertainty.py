"""Uncertainty / OOD composition (Module 6).

Every prediction carries per-axis evidence flags. Missing evidence is a
feature, never filled in:
* molecular OOD: warhead provided but dissimilar to known recruiter ligands
  of the E3 (ECFP4 Tanimoto); no warhead -> 'no_warhead' (not OOD, but
  no-molecular-evidence).
* target OOD: POI gene absent from the curated precedent/localization tables.
* E3 OOD: candidate not in the catalog / without expression gene.
* cell-context OOD: unmapped cell line or no DepMap profile.
* missing structural evidence / missing recruiter evidence flags.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

from protacxtend.modules.e3_opportunity import context, localization
from protacxtend.modules.e3_opportunity.e3_catalog import CATALOG
from protacxtend.modules.e3_opportunity.structure import e3_structural_evidence


def mol_tanimoto_max(warhead: str, ligand_smiles: list[str]) -> float | None:
    try:
        from rdkit import Chem, DataStructs
        from rdkit.Chem import AllChem
        m1 = Chem.MolFromSmiles(warhead)
        if m1 is None:
            return None
        fp1 = AllChem.GetMorganFingerprintAsBitVect(m1, 2, 1024)
        best = None
        for smi in ligand_smiles:
            m2 = Chem.MolFromSmiles(smi)
            if m2 is None:
                continue
            fp2 = AllChem.GetMorganFingerprintAsBitVect(m2, 2, 1024)
            t = DataStructs.TanimotoSimilarity(fp1, fp2)
            best = t if best is None else max(best, t)
        return best
    except Exception:
        return None


def compose(poi_gene: str | None, e3_gene: str, cell_line: str | None,
            warhead: str | None, poi_structure: str | None,
            precedent_n: int) -> dict[str, Any]:
    flags: dict[str, Any] = {}
    # target OOD
    known_target = bool(poi_gene and (
        len(localization.compartments(poi_gene)) > 0))
    flags["target_unseen"] = bool(not known_target)
    # E3 OOD
    e3_known = e3_gene in CATALOG
    flags["e3_unseen"] = bool(not e3_known)
    # cell-context OOD
    if cell_line:
        cm = context.map_cell(cell_line)
        ctx = context.context_scores(poi_gene, cell_line, None, e3_gene)
        flags["cell_unmapped"] = bool(not cm["mapped"])
        flags["cell_no_expression"] = bool(ctx.get("score") is None)
    else:
        flags["cell_unmapped"] = True
        flags["cell_no_expression"] = True
    # molecular OOD
    if warhead:
        from protacxtend.modules.e3_opportunity.recruiters import recruiters
        rec = recruiters()
        smis = [str(s) for s in rec.loc[rec["e3_gene"] == e3_gene, "smiles"]
                .dropna()]
        t = mol_tanimoto_max(warhead, smis) if smis else None
        flags["warhead_similarity_max_tanimoto"] = (
            None if t is None else round(float(t), 3))
        flags["molecular_ood"] = bool(t is not None and t < 0.3)
    else:
        flags["molecular_ood"] = False
        flags["no_warhead_evidence"] = True
    # structural / recruiter evidence
    se = e3_structural_evidence(e3_gene)
    flags["missing_structural_evidence"] = bool(not se["has_curated_complex"])
    flags["poi_structure_missing"] = bool(not poi_structure)
    flags["missing_recruiter_evidence"] = bool(precedent_n == 0)
    flags["precedent_rows"] = int(precedent_n)
    # compose
    hard = [k for k, v in flags.items()
            if k.endswith("_unseen") and v] or []
    missing = [k for k in flags if k.startswith("missing_") and flags[k]]
    return {"flags": flags,
            "structural_missing": bool(flags["missing_structural_evidence"]),
            "recruiter_missing": bool(flags["missing_recruiter_evidence"]),
            "hard_ood": hard,
            "evidence_gaps": missing}

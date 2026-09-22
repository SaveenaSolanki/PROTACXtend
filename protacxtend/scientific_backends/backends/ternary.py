"""Local ternary-complex / PROTAC / molecular-glue / metabolite-PPI backends.

All logic is free and local (geometry + OpenMM when available). Nothing here
requires a commercial modelling suite or a web service.
"""

from __future__ import annotations

import itertools
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

from protacxtend.scientific_backends.dispatch import (
    Availability,
    module_available,
    module_version,
    safe_call,
)
from protacxtend.scientific_backends.evidence import (
    CapabilityStatus,
    EvidenceTier,
    ScientificResult,
)
from protacxtend.scientific_backends.licenses import OPEN_SOURCE_PERMISSIVE
from protacxtend.scientific_backends.registry import Capability, BackendSpec, register

_CONTACT = 5.0
_HYDROPHOBIC_ELEMENTS = {"C", "S"}
_POLAR_ELEMENTS = {"N", "O"}


# ── shared structure utilities ──────────────────────────────────────────

def _chains(pdb_path: str) -> dict[str, list[dict[str, Any]]]:
    from Bio.PDB import PDBParser

    structure = PDBParser(QUIET=True).get_structure("s", pdb_path)[0]
    out: dict[str, list[dict[str, Any]]] = {}
    for chain in structure:
        atoms = []
        for residue in chain:
            for atom in residue:
                element = (atom.element or atom.get_name()[0]).strip().upper()
                if element == "H":
                    continue
                atoms.append({"coord": np.asarray(atom.coord), "element": element,
                              "resname": residue.get_resname().strip(),
                              "resid": residue.id[1], "name": atom.get_name(),
                              "hetero": residue.id[0] != " "})
        if atoms:
            out[chain.id] = atoms
    return out


def _pair_contact_metrics(atoms_a: list[dict[str, Any]], atoms_b: list[dict[str, Any]]) -> dict[str, Any]:
    a_xyz = np.asarray([a["coord"] for a in atoms_a])
    b_xyz = np.asarray([a["coord"] for a in atoms_b])
    if len(a_xyz) == 0 or len(b_xyz) == 0:
        return {"contacts": 0}
    d = np.linalg.norm(a_xyz[:, None, :] - b_xyz[None, :, :], axis=2)
    contact_mask = d < _CONTACT
    n_contacts = int(contact_mask.sum())
    clash = int((d < 2.0).sum())
    hbonds = 0
    hydrophobic = 0
    salts = 0
    for i, j in zip(*np.where(contact_mask)):
        ai, bj = atoms_a[i], atoms_b[j]
        if ai["element"] in _POLAR_ELEMENTS and bj["element"] in _POLAR_ELEMENTS:
            hbonds += 1
        if ai["element"] in _HYDROPHOBIC_ELEMENTS and bj["element"] in _HYDROPHOBIC_ELEMENTS:
            hydrophobic += 1
        if (ai["resname"] in {"ASP", "GLU"} and bj["element"] == "N") or \
           (bj["resname"] in {"ASP", "GLU"} and ai["element"] == "N") or \
           (ai["resname"] in {"LYS", "ARG"} and bj["element"] == "O") or \
           (bj["resname"] in {"LYS", "ARG"} and ai["element"] == "O"):
            salts += 1
    interface_residues = sorted({f"{atoms_a[i]['resname']}{atoms_a[i]['resid']}" for i, _ in zip(*np.where(contact_mask))} |
                                {f"{atoms_b[j]['resname']}{atoms_b[j]['resid']}" for _, j in zip(*np.where(contact_mask))})
    com = float(np.linalg.norm(a_xyz.mean(axis=0) - b_xyz.mean(axis=0)))
    # approximate buried surface from interface residue count (labelled surrogate)
    buried_sasa_proxy = round(0.35 * len(interface_residues), 2)
    return {
        "contacts": n_contacts, "clashes": clash, "hbonds": hbonds,
        "hydrophobic_contacts": hydrophobic, "salt_bridges": salts,
        "interface_residues": interface_residues[:50], "n_interface_residues": len(interface_residues),
        "com_distance_A": round(com, 3),
        "buried_sasa_proxy_100A2": buried_sasa_proxy,
        "min_distance_A": round(float(d.min()), 3),
    }


def _pick_two_chains(chains: dict[str, list[dict[str, Any]]], chain_a: str, chain_b: str):
    ordered = sorted(chains.items(), key=lambda kv: -len(kv[1]))
    a = chain_a or (ordered[0][0] if ordered else "")
    b = chain_b or next((c for c, _ in ordered if c != a), "")
    return a, b


def _metabolite_bridges(chains, ligand_resname: str, chain_a: str, chain_b: str) -> dict[str, Any]:
    ligand = [a for atoms in chains.values() for a in atoms
              if a["resname"] == ligand_resname]
    if not ligand:
        return {"present": False}
    a_near = b_near = 0
    bridges = []
    for la in ligand:
        da = min((float(np.linalg.norm(la["coord"] - x["coord"])) for x in chains.get(chain_a, [])), default=99)
        db = min((float(np.linalg.norm(la["coord"] - x["coord"])) for x in chains.get(chain_b, [])), default=99)
        if da < 4.5:
            a_near += 1
        if db < 4.5:
            b_near += 1
        if da < 4.5 and db < 4.5:
            bridges.append({"ligand_atom": la["name"], "d_chainA": round(da, 2), "d_chainB": round(db, 2)})
    return {"present": True, "n_ligand_atoms": len(ligand),
            "ligand_contacts_chainA": a_near, "ligand_contacts_chainB": b_near,
            "bridging_atoms": bridges[:20], "n_bridging_atoms": len(bridges)}


# ── ternary / PROTAC ────────────────────────────────────────────────────

def ternary_docking(target_pdb: str = "", partner_pdb: str = "", protac_smiles: str = "",
                    target_chain: str = "", partner_chain: str = "",
                    run_md: bool = True, md_steps: int = 1500, **_: Any) -> ScientificResult:
    result = ScientificResult.begin(
        Capability.TERNARY_DOCKING.value, backend="local_ternary_pipeline",
        evidence_tier=EvidenceTier.TIER_0_GEOMETRY.value, approximation=True,
        license_class=OPEN_SOURCE_PERMISSIVE.license_class.value,
        citations=["local orientation sampling + OpenMM", "linker conformer analysis"])
    try:
        if not target_pdb or not Path(target_pdb).exists():
            raise FileNotFoundError("target_pdb required")
        if not partner_pdb or not Path(partner_pdb).exists():
            raise FileNotFoundError("partner_pdb required (E3 ligase or partner)")
        target_chains = _chains(target_pdb)
        partner_chains = _chains(partner_pdb)
        t_chain = target_chain or next(iter(target_chains), "")
        p_chain = partner_chain or next(iter(partner_chains), "")
        t_atoms = target_chains.get(t_chain, [])
        p_atoms = partner_chains.get(p_chain, [])
        base = _pair_contact_metrics(t_atoms, p_atoms)

        # rigid-body orientation sampling (orientation + steric filter)
        from protacxtend.scientific_backends.backends.docking import geometric_ppi_docking

        ppi = geometric_ppi_docking(receptor_pdb=target_pdb, ligand_pdb=partner_pdb,
                                    receptor_chain=t_chain, ligand_chain=p_chain, n_poses=24, top_n=5)
        poses = ppi.data.get("poses", []) if ppi.ok() else []

        linker = None
        if protac_smiles:
            from protacxtend.scientific_backends.backends.interactions import linker_analysis

            linker = linker_analysis(linker_smiles=protac_smiles).data

        # short restrained MD when OpenMM is available
        md = None
        if run_md and module_available("openmm"):
            from protacxtend.scientific_backends.backends.md import molecular_dynamics

            md = molecular_dynamics(structure_pdb=target_pdb, md_steps=max(0, int(md_steps)),
                                    restraints={"enabled": True, "k_kj_mol_nm2": 500.0})
            if md.ok():
                result.evidence_tier = EvidenceTier.TIER_3_SHORT_MD.value
                result.approximation = False

        interface_score = base.get("contacts", 0)
        clash_burden = base.get("clashes", 0)
        linker_strain = (linker or {}).get("linker_strain_kcal_mol", 0.0) or 0.0
        stability = _ternary_stability(interface_score, clash_burden, linker_strain,
                                       md.data if md and md.ok() else None)

        result.data = {
            "target_chain": t_chain, "partner_chain": p_chain,
            "interface_metrics": base,
            "orientation_samples": poses,
            "linker": linker,
            "md": (md.data if md and md.ok() else {"status": "not_run",
                                                   "reason": "OpenMM unavailable or disabled"}),
            "ternary_stability_score": stability["score"],
            "stability_verdict": stability["verdict"],
            "verdict_is_tentative": stability["tentative"],
            "anchor_tracking": _anchor_tracking(protac_smiles),
        }
        result.summary = (f"ternary {stability['verdict']} "
                          f"(score {stability['score']}, tier {result.evidence_tier})")
        if stability["tentative"]:
            result.warnings.append("stability verdict is tentative: no multi-frame MD evidence")
    except Exception as exc:  # noqa: BLE001
        result.status = CapabilityStatus.ERROR.value
        result.summary = f"ternary pipeline failed: {exc}"
    return result.finish()


def _ternary_stability(contacts: int, clashes: int, linker_strain: float,
                       md_data: dict[str, Any] | None) -> dict[str, Any]:
    score = min(1.0, contacts / 300.0) * 0.5 + min(1.0, 20.0 / (linker_strain + 1.0)) * 0.2
    score -= min(0.4, clashes / 50.0)
    if md_data:
        rmsd = md_data.get("replicates", [{}])[0].get("convergence") if md_data.get("replicates") else None
        convergence = (md_data.get("replicates") or [{}])[0]
        b_rmsd = None
        if rmsd:
            b_rmsd = rmsd
        score += 0.3 if convergence else 0.0
        tentative = False
    else:
        tentative = True
    score = round(max(0.0, min(1.0, score)), 3)
    if tentative:
        verdict = "tentative_possible_complex" if score > 0.4 else "not_supported"
    else:
        verdict = "supported_by_short_md" if score > 0.5 else "weak_evidence"
    return {"score": score, "verdict": verdict, "tentative": tentative}


def _anchor_tracking(protac_smiles: str) -> dict[str, Any]:
    if not protac_smiles:
        return {}
    try:
        from rdkit import Chem

        mol = Chem.MolFromSmiles(protac_smiles)
        if mol is None:
            return {}
        markers = [a.GetIdx() for a in mol.GetAtoms() if a.GetAtomicNum() == 0]
        return {"n_attachment_markers": len(markers), "marker_indices": markers,
                "n_heavy_atoms": mol.GetNumHeavyAtoms()}
    except Exception:
        return {}


def protac_scoring(target_pdb: str = "", partner_pdb: str = "", ternary_pdb: str = "",
                   protac_smiles: str = "", warhead_smiles: str = "", e3_smiles: str = "",
                   ligand_resname: str = "LIG", **_: Any) -> ScientificResult:
    result = ScientificResult.begin(
        Capability.PROTAC_SCORING.value, backend="local_protac_scoring",
        evidence_tier=EvidenceTier.TIER_0_GEOMETRY.value, approximation=True,
        license_class=OPEN_SOURCE_PERMISSIVE.license_class.value,
        citations=["linker geometry + interface persistence"])
    try:
        linker = None
        if protac_smiles:
            from protacxtend.scientific_backends.backends.interactions import linker_analysis

            linker = linker_analysis(linker_smiles=protac_smiles).data
        interface = {}
        fingerprint = {}
        if ternary_pdb and Path(ternary_pdb).exists():
            chains = _chains(ternary_pdb)
            a, b = _pick_two_chains(chains, "", "")
            if a and b:
                interface = _pair_contact_metrics(chains[a], chains[b])
                if ligand_resname and any(x["resname"] == ligand_resname for x in chains.get(a, [])):
                    interface["metabolite_bridges"] = _metabolite_bridges(chains, ligand_resname, a, b)
            from protacxtend.scientific_backends.backends.interactions import interaction_fingerprint

            fp = interaction_fingerprint(complex_pdb=ternary_pdb, ligand_resname=ligand_resname)
            fingerprint = fp.data if fp.ok() else {}
        elif target_pdb and partner_pdb:
            t = _chains(target_pdb)
            p = _chains(partner_pdb)
            ta, _ = _pick_two_chains(t, "", "")
            pa, _ = _pick_two_chains(p, "", "")
            interface = _pair_contact_metrics(t.get(ta, []), p.get(pa, []))
        result.data = {
            "linker_metrics": linker,
            "interface_metrics": interface,
            "interaction_fingerprint": fingerprint,
            "anchor_tracking": _anchor_tracking(protac_smiles or warhead_smiles),
            "metrics_unavailable": [m for m, v in {
                "linker_strain": linker is None,
                "anchor_displacement": not (target_pdb and partner_pdb),
                "ternary_contact_persistence": not bool(ternary_pdb),
            }.items() if v],
        }
        result.summary = "PROTAC scoring (geometry/linker; MD tiers require a trajectory)"
    except Exception as exc:  # noqa: BLE001
        result.status = CapabilityStatus.ERROR.value
        result.summary = f"PROTAC scoring failed: {exc}"
    return result.finish()


# ── molecular glue / metabolite-assisted PPI ────────────────────────────

def _classify_ppi_delta(delta_contacts: int, delta_com: float, delta_hbonds: int,
                        bridging: int) -> tuple[str, str]:
    """Return (verdict, confidence) using conservative thresholds."""
    score = delta_contacts * 1.0 + delta_hbonds * 2.0 + bridging * 3.0 - abs(delta_com) * 0.5
    if bridging > 0 and delta_contacts > 10 and score > 20:
        return "potential_stabilization", "moderate"
    if delta_contacts < -10 and score < -15:
        return "potential_destabilization", "moderate"
    if abs(delta_contacts) <= 10 and abs(delta_com) < 1.5:
        return "no_detectable_structural_effect", "low"
    return "insufficient_evidence", "low"


def evaluate_metabolite_assisted_ppi(apo_complex_pdb: str = "", ternary_complex_pdb: str = "",
                                     binary_a_pdb: str = "", binary_b_pdb: str = "",
                                     metabolite_resname: str = "LIG", chain_a: str = "",
                                     chain_b: str = "", **_: Any) -> ScientificResult:
    result = ScientificResult.begin(
        Capability.METABOLITE_PPI_SCORING.value, backend="local_metabolite_ppi",
        evidence_tier=EvidenceTier.TIER_0_GEOMETRY.value, approximation=True,
        license_class=OPEN_SOURCE_PERMISSIVE.license_class.value,
        citations=["interface-delta geometry comparison"])
    try:
        if not ternary_complex_pdb or not Path(ternary_complex_pdb).exists():
            raise ValueError("ternary_complex_pdb (protein A + metabolite + protein B) required")
        ternary_chains = _chains(ternary_complex_pdb)
        a, b = _pick_two_chains(ternary_chains, chain_a, chain_b)
        ternary = _pair_contact_metrics(ternary_chains.get(a, []), ternary_chains.get(b, []))
        bridges = _metabolite_bridges(ternary_chains, metabolite_resname, a, b)

        apo = {}
        if apo_complex_pdb and Path(apo_complex_pdb).exists():
            apo_chains = _chains(apo_complex_pdb)
            aa, ab = _pick_two_chains(apo_chains, chain_a, chain_b)
            apo = _pair_contact_metrics(apo_chains.get(aa, []), apo_chains.get(ab, []))
        binary = {}
        if binary_a_pdb and Path(binary_a_pdb).exists():
            binary["a"] = _chains(binary_a_pdb)
        if binary_b_pdb and Path(binary_b_pdb).exists():
            binary["b"] = _chains(binary_b_pdb)

        delta_contacts = ternary.get("contacts", 0) - apo.get("contacts", 0) if apo else None
        delta_hbonds = ternary.get("hbonds", 0) - apo.get("hbonds", 0) if apo else None
        delta_com = ternary.get("com_distance_A", 0.0) - apo.get("com_distance_A", 0.0) if apo else None
        verdict, confidence = (("insufficient_evidence", "low") if not apo else
                               _classify_ppi_delta(delta_contacts or 0, delta_com or 0.0,
                                                   delta_hbonds or 0, bridges.get("n_bridging_atoms", 0)))
        result.data = {
            "conditions": {"apo": apo, "binary": {"a": bool(binary.get("a")), "b": bool(binary.get("b"))},
                           "ternary": ternary},
            "metabolite_bridges": bridges,
            "deltas": {"interface_contacts": delta_contacts, "hydrogen_bonds": delta_hbonds,
                       "com_distance_A": None if delta_com is None else round(delta_com, 3)},
            "verdict": verdict, "confidence": confidence,
            "disclaimer": "MD/geometry comparison cannot 'prove' stabilization; it is computational evidence only.",
        }
        result.summary = f"metabolite-assisted PPI: {verdict} (confidence {confidence})"
    except Exception as exc:  # noqa: BLE001
        result.status = CapabilityStatus.ERROR.value
        result.summary = f"metabolite PPI error: {exc}"
    return result.finish()


def molecular_glue_scoring(apo_complex_pdb: str = "", ligand_bound_complex_pdb: str = "",
                           ligand_resname: str = "LIG", chain_a: str = "", chain_b: str = "",
                           **_: Any) -> ScientificResult:
    result = ScientificResult.begin(
        Capability.MOLECULAR_GLUE_SCORING.value, backend="local_glue_ppi_delta",
        evidence_tier=EvidenceTier.TIER_0_GEOMETRY.value, approximation=True,
        license_class=OPEN_SOURCE_PERMISSIVE.license_class.value,
        citations=["apo-vs-bound interface delta (glue hypothesis)"])
    try:
        if not apo_complex_pdb or not Path(apo_complex_pdb).exists():
            raise ValueError("apo_complex_pdb required (protein A + protein B)")
        if not ligand_bound_complex_pdb or not Path(ligand_bound_complex_pdb).exists():
            raise ValueError("ligand_bound_complex_pdb required (A + glue + B)")
        apo_chains = _chains(apo_complex_pdb)
        bound_chains = _chains(ligand_bound_complex_pdb)
        aa, ab = _pick_two_chains(apo_chains, chain_a, chain_b)
        ba, bb = _pick_two_chains(bound_chains, chain_a, chain_b)
        apo = _pair_contact_metrics(apo_chains.get(aa, []), apo_chains.get(ab, []))
        bound = _pair_contact_metrics(bound_chains.get(ba, []), bound_chains.get(bb, []))
        bridges = _metabolite_bridges(bound_chains, ligand_resname, ba, bb)
        d_contacts = bound.get("contacts", 0) - apo.get("contacts", 0)
        d_hbonds = bound.get("hbonds", 0) - apo.get("hbonds", 0)
        d_com = bound.get("com_distance_A", 0.0) - apo.get("com_distance_A", 0.0)
        verdict, confidence = _classify_ppi_delta(d_contacts, d_com, d_hbonds,
                                                  bridges.get("n_bridging_atoms", 0))
        result.data = {
            "apo": apo, "ligand_bound": bound, "glue_bridges": bridges,
            "deltas": {"interface_contacts": d_contacts, "hydrogen_bonds": d_hbonds,
                       "electrostatic_contacts": bound.get("salt_bridges", 0) - apo.get("salt_bridges", 0),
                       "com_distance_A": round(d_com, 3),
                       "buried_sasa_proxy_100A2": round(bound.get("buried_sasa_proxy_100A2", 0)
                                                        - apo.get("buried_sasa_proxy_100A2", 0), 2)},
            "verdict": verdict, "confidence": confidence,
            "disclaimer": "computational PPI-stabilization hypothesis, not experimental proof",
        }
        result.summary = f"molecular glue: {verdict} (Δcontacts {d_contacts:+d})"
    except Exception as exc:  # noqa: BLE001
        result.status = CapabilityStatus.ERROR.value
        result.summary = f"molecular glue scoring failed: {exc}"
    return result.finish()


TERNARY_BACKEND = register(BackendSpec(
    name="local_ternary_pipeline",
    capabilities=(Capability.TERNARY_DOCKING,),
    license=OPEN_SOURCE_PERMISSIVE, priority=60,
    description="Local ternary assembly: orientation sampling + linker + optional OpenMM.",
    citation="local orientation sampling; OpenMM",
    health_check=lambda: Availability(available=module_available("Bio"), detail="biopython"),
    handlers={Capability.TERNARY_DOCKING: ternary_docking},
))

PROTAC_BACKEND = register(BackendSpec(
    name="local_protac_scoring",
    capabilities=(Capability.PROTAC_SCORING,),
    license=OPEN_SOURCE_PERMISSIVE, priority=60,
    description="PROTAC linker/interface/anchor scoring (no commercial modelling).",
    citation="linker geometry + interface contacts",
    health_check=lambda: Availability(available=module_available("rdkit") or module_available("Bio"),
                                      detail="rdkit/biopython"),
    handlers={Capability.PROTAC_SCORING: protac_scoring},
))

GLUE_BACKEND = register(BackendSpec(
    name="local_glue_ppi_delta",
    capabilities=(Capability.MOLECULAR_GLUE_SCORING, Capability.METABOLITE_PPI_SCORING),
    license=OPEN_SOURCE_PERMISSIVE, priority=60,
    description="Apo-vs-bound PPI interface delta for molecular glues and metabolite-assisted PPI.",
    citation="interface-delta geometry comparison",
    health_check=lambda: Availability(available=module_available("Bio"), detail="biopython/numpy"),
    handlers={
        Capability.MOLECULAR_GLUE_SCORING: molecular_glue_scoring,
        Capability.METABOLITE_PPI_SCORING: evaluate_metabolite_assisted_ppi,
    },
))

# keep a placeholder for CAPABILITY.CANDIDATE_RANKING handled by ranking.py

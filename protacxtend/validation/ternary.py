"""Ternary / PROTAC complex validation (kept separate from binary PPI).

Each experimentally resolved ternary complex is curated *by the ligand*: the two
protein chains that contact the PROTAC most are taken as the target and E3
partners.  We report native ternary geometry, interface recovery, ligand
placement, clashes and DockQ (native control + rigid decoy).  Predicted-structure
DockQ is reported only if the local pipeline actually emits a coordinate model;
otherwise the row is explicit that it was not produced.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import numpy as np

from protacxtend.audit import dockq, success_rate_ci
from protacxtend.audit.provenance import host_fingerprint
from protacxtend.validation.curation import _BLOCK, fetch_structure
from protacxtend.validation.datasets import TERNARY_V1, ROOT
from protacxtend.validation.io import RowWriter, write_summary_json

OUT = ROOT / "results" / "benchmarks" / "ternary"
CONTACT = 5.0


def _atoms_by_chain(pdb_path: str) -> dict[str, list[dict[str, Any]]]:
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
                atoms.append({"coord": np.asarray(atom.coord, float), "element": element,
                              "resname": residue.get_resname().strip(), "resid": residue.id[1],
                              "name": atom.get_name(), "hetero": residue.id[0] != " "})
        if atoms:
            out[chain.id] = atoms
    return out


def curate_ternary(pdb_id: str) -> dict[str, Any]:
    pdb_file = fetch_structure(pdb_id)
    chains = _atoms_by_chain(str(pdb_file))
    ligands = {c: [a for a in atoms if a["hetero"] and a["resname"] not in _BLOCK]
               for c, atoms in chains.items()}
    all_lig = [(c, a) for c, atoms in ligands.items() for a in atoms]
    if not all_lig:
        raise RuntimeError("no ligand-like hetero atoms")
    lig_xyz = np.asarray([a["coord"] for _c, a in all_lig], float)
    het_names = {a["resname"] for _c, a in all_lig}
    # per protein chain: number of ligand contacts
    protein = {c: [a for a in atoms if not a["hetero"]] for c, atoms in chains.items()}
    contact_counts = {}
    for c, atoms in protein.items():
        if not atoms:
            continue
        xyz = np.asarray([a["coord"] for a in atoms], float)
        d = np.linalg.norm(xyz[:, None, :] - lig_xyz[None, :, :], axis=2)
        contact_counts[c] = int((d < CONTACT).sum())
    ranked = sorted(contact_counts.items(), key=lambda kv: -kv[1])
    ranked = [(c, n) for c, n in ranked if n > 0]
    if len(ranked) < 2:
        raise RuntimeError(f"fewer than two ligand-contacting protein chains ({len(ranked)})")
    target_chain, e3_chain = ranked[0][0], ranked[1][0]
    ligand_atoms = [a for c, a in all_lig if c in {target_chain, e3_chain}]
    return {"pdb_id": pdb_id, "native_pdb": str(pdb_file), "target_chain": target_chain,
            "e3_chain": e3_chain, "ligand_het": sorted(het_names),
            "n_ligand_atoms": len(ligand_atoms),
            "ligand_coords": np.asarray([a["coord"] for a in ligand_atoms], float),
            "target_atoms": protein[target_chain], "e3_atoms": protein[e3_chain],
            "contact_counts": contact_counts}


def _pair_metrics(a: list[dict[str, Any]], b: list[dict[str, Any]]) -> dict[str, Any]:
    if not a or not b:
        return {"contacts": 0, "clashes": 0, "n_interface_residues": 0}
    ax = np.asarray([x["coord"] for x in a], float)
    bx = np.asarray([x["coord"] for x in b], float)
    d = np.linalg.norm(ax[:, None, :] - bx[None, :, :], axis=2)
    mask = d < CONTACT
    ii, jj = np.where(mask)
    interface = {f"{a[i]['resname']}{a[i]['resid']}" for i in ii} | \
                {f"{b[j]['resname']}{b[j]['resid']}" for j in jj}
    return {
        "contacts": int(mask.sum()),
        "clashes": int((d < 2.0).sum()),
        "n_interface_residues": len(interface),
        "com_distance_A": round(float(np.linalg.norm(ax.mean(0) - bx.mean(0))), 3),
        "min_distance_A": round(float(d.min()), 3),
    }


def _ligand_placement(lig_coords: np.ndarray, target, e3) -> dict[str, Any]:
    tx = np.asarray([a["coord"] for a in target], float)
    ex = np.asarray([a["coord"] for a in e3], float)
    dt = np.linalg.norm(lig_coords[:, None, :] - tx[None, :, :], axis=2).min(1)
    de = np.linalg.norm(lig_coords[:, None, :] - ex[None, :, :], axis=2).min(1)
    bridging = int(((dt < 4.5) & (de < 4.5)).sum())
    return {
        "ligand_atoms_contact_target": int((dt < 4.5).sum()),
        "ligand_atoms_contact_e3": int((de < 4.5).sum()),
        "ligand_bridging_atoms": bridging,
        "ligand_bridging_fraction": round(bridging / max(1, len(lig_coords)), 3),
        "ligand_min_dist_target": round(float(dt.min()), 3),
        "ligand_min_dist_e3": round(float(de.min()), 3),
    }


def _decoy_dockq(native, target_chain: str, e3_chain: str, seed: int = 7) -> float | None:
    import copy

    rng = np.random.default_rng(seed)
    model = copy.deepcopy(native)
    chain = model[e3_chain]
    coords = np.asarray([a.coord for a in chain.get_atoms()], float)
    center = coords.mean(0)
    axis = rng.normal(size=3)
    axis /= np.linalg.norm(axis)
    angle = rng.uniform(0, 2 * np.pi)
    K = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
    R = np.eye(3) + np.sin(angle) * K + (1 - np.cos(angle)) * (K @ K)
    moved = (coords - center) @ R.T + center + rng.normal(scale=9.0, size=3)
    for atom, xyz in zip(chain.get_atoms(), moved):
        atom.set_coord(xyz.astype(np.float32))
    return dockq(native, model, target_chain, e3_chain).get("dockq")


def run(complexes: list[dict[str, Any]] | None = None, *, limit: int | None = None) -> dict[str, Any]:
    complexes = complexes or TERNARY_V1["complexes"]
    if limit:
        complexes = complexes[:limit]
    OUT.mkdir(parents=True, exist_ok=True)
    row = RowWriter("ternary_rows", OUT)
    failures: list[dict[str, Any]] = []
    n_curated = 0
    from Bio.PDB import PDBParser

    for entry in complexes:
        pdb_id = entry["pdb"] if isinstance(entry, dict) else entry
        started = time.time()
        try:
            info = curate_ternary(pdb_id)
            n_curated += 1
        except Exception as exc:  # noqa: BLE001
            failures.append(row.failure(structure_id=pdb_id, stage="curation",
                                        outcome="REJECTED_INPUT", reason=str(exc)[:200]))
            print(f"[ternary] {pdb_id} curation fail: {exc}")
            continue
        native = PDBParser(QUIET=True).get_structure(pdb_id, info["native_pdb"])[0]
        t_chain, e_chain = info["target_chain"], info["e3_chain"]
        control = dockq(native, native, t_chain, e_chain)
        decoy = _decoy_dockq(native, t_chain, e_chain)
        interface = _pair_metrics(info["target_atoms"], info["e3_atoms"])
        placement = _ligand_placement(info["ligand_coords"], info["target_atoms"], info["e3_atoms"])
        # run the local ternary pipeline (scoring) on the separated partners
        pipeline: dict[str, Any] = {}
        try:
            target_pdb = OUT / "partner_structures" / pdb_id / "target.pdb"
            e3_pdb = OUT / "partner_structures" / pdb_id / "e3.pdb"
            _write_chain(info["native_pdb"], t_chain, target_pdb)
            _write_chain(info["native_pdb"], e_chain, e3_pdb)
            from protacxtend.scientific_backends.backends.ternary import ternary_docking

            res = ternary_docking(target_pdb=str(target_pdb), partner_pdb=str(e3_pdb),
                                  target_chain=t_chain, partner_chain=e_chain, run_md=False)
            pipeline = {"status": res.status, "backend": res.backend, "summary": res.summary,
                        "stability_verdict": res.data.get("stability_verdict"),
                        "stability_score": res.data.get("ternary_stability_score"),
                        "interface_metrics": res.data.get("interface_metrics")}
        except Exception as exc:  # noqa: BLE001
            pipeline = {"status": "error", "summary": str(exc)[:200]}
        row.add({
            "benchmark": "ternary", "structure_id": pdb_id, "ligand_id": ";".join(info["ligand_het"]),
            "target_chain": t_chain, "e3_chain": e_chain,
            "n_ligand_atoms": info["n_ligand_atoms"],
            "status": "success", "success": True,
            "dockq_native_control": control.get("dockq"), "capri_native_control": control.get("capri"),
            "dockq_rigid_decoy": decoy,
            "interface_contacts": interface["contacts"], "interface_clashes": interface["clashes"],
            "interface_residues": interface["n_interface_residues"],
            "interface_com_distance_A": interface.get("com_distance_A"),
            **placement,
            "pipeline_status": pipeline.get("status"),
            "pipeline_verdict": pipeline.get("stability_verdict"),
            "pipeline_score": pipeline.get("stability_score"),
            "pipeline_summary": (pipeline.get("summary") or "")[:200],
            "dockq_predicted": None,
            "dockq_predicted_note": "local pipeline emits a score, not a coordinate model; "
                                    "predicted-structure DockQ not produced",
            "runtime_s": round(time.time() - started, 3),
            **row.provenance(dataset=TERNARY_V1["name"], source=TERNARY_V1["source"],
                             structure_id=pdb_id, ligand_id=";".join(info["ligand_het"]),
                             software="local_ternary_pipeline",
                             model="geometric_orientation_search",
                             command="ternary_docking", output_path=str(OUT)),
        })
        print(f"[ternary] {pdb_id}: contacts={interface['contacts']} "
              f"bridging={placement['ligand_bridging_atoms']} decoy_dockq={decoy} "
              f"verdict={pipeline.get('stability_verdict')}")
    summary = _summary(row.rows, len(complexes))
    row.finalize(summary)
    write_summary_json(OUT / "failures.json", {"n": len(failures), "failures": failures})
    print("\n" + str(summary))
    return summary


def _write_chain(native_pdb: str, chain_id: str, dest: Path) -> None:
    from Bio.PDB import PDBIO, PDBParser, Select

    structure = PDBParser(QUIET=True).get_structure("s", native_pdb)

    class _Ch(Select):
        def accept_chain(self, c):
            return c.id == chain_id

        def accept_residue(self, r):
            return r.id[0] == " "

    dest.parent.mkdir(parents=True, exist_ok=True)
    io = PDBIO()
    io.set_structure(structure)
    io.save(str(dest), _Ch())


def _summary(rows: list[dict[str, Any]], n_attempted: int) -> dict[str, Any]:
    contacts = [r.get("interface_contacts") for r in rows if r.get("interface_contacts") is not None]
    bridging = [r["ligand_bridging_fraction"] for r in rows if r.get("ligand_bridging_fraction") is not None]
    decoys = [r["dockq_rigid_decoy"] for r in rows if isinstance(r.get("dockq_rigid_decoy"), (int, float))]
    verdicts: dict[str, int] = {}
    for r in rows:
        if r.get("interface_contacts") is None:
            continue
        verdicts[str(r.get("pipeline_verdict"))] = verdicts.get(str(r.get("pipeline_verdict")), 0) + 1
    return {
        "dataset": TERNARY_V1["name"], "n_attempted": n_attempted,
        "n_evaluated": sum(1 for r in rows if r.get("interface_contacts") is not None),
        "failure_rate": round(1 - sum(1 for r in rows if r.get("interface_contacts") is not None)
                              / n_attempted, 4) if n_attempted else None,
        "interface_contacts_median": round(float(np.median(contacts)), 1) if contacts else None,
        "ligand_bridging_fraction_median": round(float(np.median(bridging)), 3) if bridging else None,
        "rigid_decoy_dockq_median": round(float(np.median(decoys)), 3) if decoys else None,
        "native_control_dockq": 1.0,
        "pipeline_verdict_counts": verdicts,
        "predicted_dockq_status": "NOT_VALIDATED (pipeline does not emit coordinates)",
        "host": host_fingerprint(),
    }


__all__ = ["run", "OUT", "curate_ternary"]

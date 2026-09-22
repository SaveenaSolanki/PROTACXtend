"""Frozen, versioned benchmark datasets.

The benchmark sets are declared here and written to
``benchmark/frozen/<name>.json`` with a SHA-256 so that a software update cannot
silently change the test population.  Curation downloads from RCSB and fails
loudly (the failure is recorded, never dropped).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
FROZEN = ROOT / "benchmark" / "frozen"
CACHE = ROOT / "benchmark" / "frozen_cache"

# ── protein–ligand redocking (drug-like, single-site) ───────────────────
DOCKING_V1 = {
    "name": "docking_v1",
    "description": "Protein–ligand redocking set: drug-like single-site complexes from RCSB.",
    "source": "RCSB PDB",
    "complexes": [
        # DiffDock example complexes (flagged for possible train leakage)
        "1a46", "1cbr", "6ahs", "6moa", "6o5u", "6w70",
        # kinases / proteases / nuclear receptors
        "3ert", "1iep", "1m17", "1xkk", "1hvr", "1d4p",
        "4dfr", "1stp", "3ptb", "1fkb", "1ake", "1bcu",
        "2ito", "3k5v", "4ivc", "2zff", "1s3v", "1oyt",
        "3fur", "2rgp", "1uto", "4llx", "1z95", "3gpo",
        # additional classic drug-like complexes (not DiffDock examples)
        "1p38", "1eve", "1fkj", "1cbx", "1tmn", "1rnt",
        "2cmd", "3hvt", "1dhf", "1qpe", "4phv", "1aaq",
    ],
    "diffdock_example_ids": [
        "1a46", "1cbr", "6ahs", "6moa", "6o5u", "6w70",
    ],
}

# ── pocket detection (same proteins, ligand defines the true site) ──────
POCKET_V1 = {
    "name": "pocket_v1",
    "description": "Pocket-detection set: known ligand-binding site from each holo complex.",
    "source": "RCSB PDB",
    "complexes": DOCKING_V1["complexes"],
}

# ── protein–protein docking (experimental binary complexes) ─────────────
# Curated from the protein–protein docking benchmark tradition; each entry is a
# two-chain experimental binary complex.  Curation takes the two largest
# protein chains and records them explicitly.
PPI_V1 = {
    "name": "ppi_v1",
    "description": "Experimental binary protein–protein complexes (two-chain).",
    "source": "RCSB PDB",
    "complexes": [
        "1ppe", "1cgi", "1avx", "1ay7", "1buh", "1d6r", "1dfj", "1eaw",
        "1ewy", "1f34", "1fsk", "1gcq", "1ghq", "1gla", "1h9d", "1he1",
        "1i2m", "1ibr", "1j2j", "1jtg", "1kac", "1ktz", "1mah", "1mda",
        "1n8o", "1oc0", "1r0r", "1rv6", "1tmq", "1udi", "1wej", "1wq1",
        "1xd3", "1yvb", "2a9k", "2abz", "2b42", "2hrk", "2i9b", "2j0t",
        "2mta", "2o8v", "2oob", "2pcc", "2sic", "2sni", "2uuy", "3aad",
        "3cph", "3f1p", "3k75", "7cei",
    ],
}

# ── ternary / PROTAC complexes (experimentally resolved) ────────────────
# Each entry: PDB id with an experimentally resolved PROTAC/ternary assembly,
# plus the target chain, E3-ligase chain and ligand HET code where known.
# Curation is deliberately conservative and records what it actually found.
TERNARY_V1 = {
    "name": "ternary_v1",
    "description": "Experimentally resolved PROTAC/ternary complexes (target–ligand–E3).",
    "source": "RCSB PDB",
    "complexes": [
        {"pdb": "5t35", "target_chain": "A", "e3_chain": "B", "ligand": "8XW",
         "note": "MZ1/VHL/BRD4 ternary"},
        {"pdb": "6bn7", "target_chain": "A", "e3_chain": "B", "ligand": "", "note": "VHL ternary"},
        {"pdb": "6bn8", "target_chain": "A", "e3_chain": "B", "ligand": "", "note": "VHL ternary"},
        {"pdb": "6bn9", "target_chain": "A", "e3_chain": "B", "ligand": "", "note": "VHL ternary"},
        {"pdb": "6bnb", "target_chain": "A", "e3_chain": "B", "ligand": "", "note": "VHL ternary"},
        {"pdb": "6boy", "target_chain": "A", "e3_chain": "B", "ligand": "", "note": "CRBN ternary"},
        {"pdb": "6hax", "target_chain": "A", "e3_chain": "B", "ligand": "", "note": "ternary"},
        {"pdb": "6hay", "target_chain": "A", "e3_chain": "B", "ligand": "", "note": "ternary"},
        {"pdb": "6hr2", "target_chain": "A", "e3_chain": "B", "ligand": "", "note": "ternary"},
        {"pdb": "5v7q", "target_chain": "A", "e3_chain": "B", "ligand": "", "note": "ternary"},
        {"pdb": "6zhc", "target_chain": "A", "e3_chain": "B", "ligand": "", "note": "ternary"},
        {"pdb": "7khh", "target_chain": "A", "e3_chain": "B", "ligand": "", "note": "ternary"},
    ],
}

# ── energetics (small, gold-standard ligand set for MM/GBSA) ────────────
ENERGETICS_V1 = {
    "name": "energetics_v1",
    "description": "Small-ligand protein–ligand set for MM/GBSA parameterisation validation.",
    "source": "RCSB PDB",
    # deliberately small ligands so AM1-BCC (sqm) parameterisation is tractable
    "complexes": ["3ptb", "1stp", "1cbx", "1bcu", "1cbr"],
}


def _write(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    import hashlib

    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"name": payload["name"], "path": str(path.relative_to(ROOT)),
            "sha256": digest, "n": len(payload.get("complexes", []))}


def structure_checksums() -> dict[str, str]:
    """SHA-256 of every cached structure used by the frozen benchmarks."""
    import hashlib

    out: dict[str, str] = {}
    for path in sorted(CACHE.glob("*")):
        if not path.is_file():
            continue
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(chunk)
        out[str(path.relative_to(CACHE))] = h.hexdigest()
    return out


def freeze_all() -> dict[str, Any]:
    """Write (or refresh) every frozen manifest and the master checksum file."""
    FROZEN.mkdir(parents=True, exist_ok=True)
    entries = [
        _write(FROZEN / "docking_v1.json", DOCKING_V1),
        _write(FROZEN / "pocket_v1.json", POCKET_V1),
        _write(FROZEN / "ppi_v1.json", PPI_V1),
        _write(FROZEN / "ternary_v1.json", TERNARY_V1),
        _write(FROZEN / "energetics_v1.json", ENERGETICS_V1),
    ]
    checksums = structure_checksums()
    checksum_path = FROZEN / "STRUCTURE_CHECKSUMS.json"
    checksum_path.write_text(json.dumps(checksums, indent=2, sort_keys=True), encoding="utf-8")
    manifest = {"version": "1.0.0", "datasets": entries,
                "structure_checksums": {"path": str(checksum_path.relative_to(ROOT)),
                                        "n_files": len(checksums)}}
    (FROZEN / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def load(name: str) -> dict[str, Any]:
    path = FROZEN / f"{name}.json"
    if not path.exists():
        freeze_all()
    return json.loads(path.read_text())


__all__ = [
    "DOCKING_V1", "POCKET_V1", "PPI_V1", "TERNARY_V1", "ENERGETICS_V1",
    "freeze_all", "load", "structure_checksums", "FROZEN", "CACHE", "ROOT",
]

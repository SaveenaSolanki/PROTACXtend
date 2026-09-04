"""Module 2 tests — Lysine Ubiquitination Feasibility Scorer.

Uses synthetic PDB fixtures (deterministic geometry, not scientific claims):
  * one POI chain 'A' carrying two lysines at controlled distances from the
    E2 catalytic Cys, and an occluder atom to control SASA
  * one E2 chain 'B' with a catalytic cysteine

Includes an analytic Shrake-Rupley check (single isolated atom SASA) and
hand-computed geometry checks.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from protacxtend.modules.lysine_ubiquitination_feasibility import (
    LysineScorerError,
    read_pdb,
    score_lysine_ubiquitination,
)
from protacxtend.modules.lysine_ubiquitination_feasibility.core import (
    shrake_rupley_sasa,
)

R = {"C": 1.7, "N": 1.55, "O": 1.52, "S": 1.8}


def _pdb(rows: list[tuple], path: Path) -> Path:
    lines = []
    serial = 1
    for chain, resname, resseq, name, x, y, z in rows:
        elem = name[0] if len(name) == 1 else name[:1]
        lines.append(
            f"ATOM  {serial:5d} {name:>4s} {resname:>3s} {chain}{resseq:4d}    "
            f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00 20.00          {elem:>2s}")
        serial += 1
    lines.append("END")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _fixture(tmp_path: Path, *, occluder: bool = True, n_poses: int = 1) -> list[Path]:
    """Chain A: LYS100 NZ at (0,0,0); LYS200 NZ at (30,0,0) (far).
    Occluder N at (1.9,0,0) partially shields LYS100 NZ when enabled.
    Chain B (E2): catalytic CYS85 SG at (8,0,0)."""
    paths = []
    for pose in range(n_poses):
        rows = [
            # backbone anchors keep angle/geometry defined
            ("A", "LYS", 100, "CA", 0.0, -3.8, 0.0),
            ("A", "LYS", 100, "CB", 0.0, -1.5, 0.0),
            ("A", "LYS", 100, "NZ", 0.0, 0.0, 0.0),
            ("A", "LYS", 200, "CA", 30.0, -3.8, 0.0),
            ("A", "LYS", 200, "CB", 30.0, -1.5, 0.0),
            ("A", "LYS", 200, "NZ", 30.0, 0.0, 0.0),
        ]
        if occluder:
            rows.append(("A", "GLY", 300, "N", 3.4, 0.0, 0.0))
            rows.append(("A", "GLY", 300, "CA", 3.4, -1.2, 0.0))
        rows += [("B", "CYS", 85, "CB", 8.0, -1.5, 0.0),
                 ("B", "CYS", 85, "SG", 8.0, 0.0, 0.0)]
        paths.append(_pdb(rows, tmp_path / f"pose{pose}.pdb"))
    return paths


class TestPdbAndSasa:
    def test_read_pdb_counts_atoms(self, tmp_path):
        p = _fixture(tmp_path, n_poses=1)[0]
        atoms = read_pdb(p)
        assert atoms and all(a.element != "H" for a in atoms)

    def test_analytic_isolated_atom_sasa(self):
        """Shrake-Rupley on one isolated C atom: SASA ~ 4*pi*(1.7+1.4)^2."""
        import numpy as np

        from protacxtend.modules.lysine_ubiquitination_feasibility.core import Atom
        atom = Atom(1, "C", "ALA", "A", 1, 0.0, 0.0, 0.0, "C")
        got = shrake_rupley_sasa([atom], probe=1.4, n_dots=960, radii=R)
        expected = 4.0 * math.pi * 3.1 ** 2
        assert got[0] == pytest.approx(expected, rel=0.01)

    def test_occlusion_reduces_sasa(self):
        import numpy as np

        from protacxtend.modules.lysine_ubiquitination_feasibility.core import Atom
        a = Atom(1, "NZ", "LYS", "A", 100, 0.0, 0.0, 0.0, "N")
        occ = Atom(2, "N", "GLY", "A", 300, 1.9, 0.0, 0.0, "N")
        bare = shrake_rupley_sasa([a], 1.4, 960, R)[0]
        shielded = shrake_rupley_sasa([a, occ], 1.4, 960, R)[0]
        assert shielded < bare


class TestScorer:
    def test_ranks_proximal_lysine_first_and_productive(self, tmp_path):
        paths = _fixture(tmp_path)
        out = score_lysine_ubiquitination(
            [str(p) for p in paths], poi_chain="A",
            e2_catalytic={"chain": "B", "residue_number": 85},
            distance_cutoff_angstrom=15.0, sasa_cutoff_angstrom2=1.0,
            orientation_cutoff_deg=150.0, n_sasa_dots=96)
        assert out.status == "SUPPORTED"
        top = out.ranked_lysines[0]
        assert top.residue_number == 100
        assert top.mean_distance_angstrom == pytest.approx(8.0, rel=0.05)
        assert top.productive_pose_fraction == 1.0
        # far lysine at 30 A is not productive at this cutoff
        far = next(r for r in out.ranked_lysines if r.residue_number == 200)
        assert far.mean_distance_angstrom > 20.0
        assert all(not g.productive for g in far.pose_geometries)

    def test_ensemble_consistency_across_poses(self, tmp_path):
        paths = _fixture(tmp_path, n_poses=3)
        out = score_lysine_ubiquitination(
            [str(p) for p in paths], poi_chain="A",
            e2_catalytic={"chain": "B", "residue_number": 85},
            distance_cutoff_angstrom=15.0, sasa_cutoff_angstrom2=1.0,
            orientation_cutoff_deg=150.0, n_sasa_dots=96)
        assert out.n_poses == 3
        assert out.productive_pose_fraction == 1.0
        for lys in out.ranked_lysines:
            assert len(lys.pose_geometries) == 3
        top = out.ranked_lysines[0]
        assert top.ensemble_mean_score > 0.6

    def test_missing_e2_refuses_geometry(self, tmp_path):
        rows = [("A", "LYS", 100, "NZ", 0.0, 0.0, 0.0),
                ("B", "GLY", 1, "CA", 5.0, 0.0, 0.0)]  # no catalytic Cys
        p = _pdb(rows, tmp_path / "no_e2.pdb")
        with pytest.raises(LysineScorerError, match="E2 catalytic cysteine"):
            score_lysine_ubiquitination([str(p)], poi_chain="A",
                                        e2_catalytic={"chain": "B", "residue_number": 85})

    def test_missing_file_rejected(self, tmp_path):
        with pytest.raises(LysineScorerError):
            score_lysine_ubiquitination([str(tmp_path / "nope.pdb")], poi_chain="A",
                                        e2_catalytic={"chain": "B", "residue_number": 85})

    def test_schema_metadata_and_limits(self, tmp_path):
        paths = _fixture(tmp_path)
        out = score_lysine_ubiquitination([str(p) for p in paths], poi_chain="A",
                                          e2_catalytic={"chain": "B", "residue_number": 85},
                                          distance_cutoff_angstrom=15.0,
                                          sasa_cutoff_angstrom2=1.0,
                                          orientation_cutoff_deg=150.0, n_sasa_dots=96)
        assert out.model.startswith("lysine_ubiquitination_feasibility-v")
        assert out.ubiquitination_feasibility_score >= 0.0
        assert out.ubiquitination_feasibility_score <= 1.0
        assert out.features["n_sasa_dots"] == 96

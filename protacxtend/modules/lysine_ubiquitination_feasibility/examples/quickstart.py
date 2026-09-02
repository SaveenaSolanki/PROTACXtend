"""Module 2 quickstart — Lysine Ubiquitination Feasibility demo.

Builds a small synthetic ternary-like pose (2 POI lysines + E2 catalytic Cys)
and runs the scorer. Geometry here is illustrative, not a scientific claim.

Usage: python -m protacxtend.modules.lysine_ubiquitination_feasibility.examples.quickstart
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from protacxtend.modules.lysine_ubiquitination_feasibility import (
    score_lysine_ubiquitination,
)
from protacxtend.tools.lysine_ubiquitination_tool import run_lysine_ubiquitination


def _write_pose(path: Path, shift: float = 0.0) -> None:
    rows = [
        ("A", "LYS", 100, "CA", 0.0 + shift, -3.8, 0.0),
        ("A", "LYS", 100, "CB", 0.0 + shift, -1.5, 0.0),
        ("A", "LYS", 100, "NZ", 0.0 + shift, 0.0, 0.0),
        ("A", "LYS", 200, "CA", 30.0 + shift, -3.8, 0.0),
        ("A", "LYS", 200, "CB", 30.0 + shift, -1.5, 0.0),
        ("A", "LYS", 200, "NZ", 30.0 + shift, 0.0, 0.0),
        ("B", "CYS", 85, "CB", 8.0, -1.5, 0.0),
        ("B", "CYS", 85, "SG", 8.0, 0.0, 0.0),
    ]
    lines, serial = [], 1
    for chain, res, rseq, name, x, y, z in rows:
        elem = name[0]
        lines.append(f"ATOM  {serial:5d} {name:>4s} {res:>3s} {chain}{rseq:4d}    "
                     f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00 20.00          {elem:>2s}")
        serial += 1
    lines.append("END")
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        poses = []
        for i in range(2):
            p = Path(td) / f"pose{i}.pdb"
            _write_pose(p, shift=0.3 * i)
            poses.append(str(p))
        r = score_lysine_ubiquitination(
            poses, poi_chain="A",
            e2_catalytic={"chain": "B", "residue_number": 85},
            distance_cutoff_angstrom=15.0, sasa_cutoff_angstrom2=1.0,
            orientation_cutoff_deg=150.0)
        print("Lysine Ubiquitination Feasibility demo (synthetic 2-pose ensemble)")
        print("  status:", r.status, "| n_poses:", r.n_poses, "| n_lysines:", r.n_lysines)
        print("  feasibility score:", r.ubiquitination_feasibility_score,
              f"({r.feasibility_label})")
        print("  productive-pose fraction:", r.productive_pose_fraction)
        for lys in r.ranked_lysines:
            print(f"  LYS {lys.residue_number}: score {lys.ensemble_mean_score:.3f} "
                  f"prod {lys.productive_pose_fraction:.2f} dist "
                  f"{lys.mean_distance_angstrom:.1f} A NZ-SASA {lys.mean_sasa_angstrom2:.0f} A2")

        # agent tool JSON path
        tool = run_lysine_ubiquitination({"structure_paths": poses[:1], "poi_chain": "A",
                                          "e2_catalytic": {"chain": "B", "residue_number": 85}})
        print("\nAgent tool success:", tool["success"], "| error:", tool["error"] or "none")


if __name__ == "__main__":
    main()

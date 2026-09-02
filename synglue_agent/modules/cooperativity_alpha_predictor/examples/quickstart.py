"""Module 3 quickstart — Cooperativity predictor (surrogate mode demo)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from synglue_agent.modules.cooperativity_alpha_predictor import (
    CooperativityEvidenceError,
    audit_records,
    load_records,
    predict_cooperativity,
)
from synglue_agent.tools.cooperativity_alpha_tool import run_cooperativity_predictor


def _pose(path: Path, chain: str) -> None:
    rows = [
        ("A", "LEU", 11, "CB", 4.0, 1.4, 0.0), ("A", "ALA", 12, "CB", 0.0, 3.2, 0.0),
        ("B", "LEU", 41, "CB", 3.0, 6.4, 0.0), ("B", "GLU", 42, "OE1", 0.0, 6.6, 0.0),
    ] if chain == "A" else [
        ("B", "LEU", 41, "CB", 3.0, 6.4, 0.0), ("B", "GLU", 42, "OE1", 0.0, 6.6, 0.0),
        ("A", "LEU", 11, "CB", 4.0, 1.4, 0.0), ("A", "ALA", 12, "CB", 0.0, 3.2, 0.0),
    ]
    lines, serial = [], 1
    for ch, res, rseq, name, x, y, z in rows:
        elem = name[0]
        lines.append(f"ATOM  {serial:5d} {name:>4s} {res:>3s} {ch}{rseq:4d}    "
                     f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00 20.00          {elem:>2s}")
        serial += 1
    lines.append("END")
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    print("Cooperativity predictor — data audit:")
    audit = audit_records(load_records())
    print("  records:", audit["records"])
    print("  conclusion:", audit["conclusion"][:140])

    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "pose.pdb"
        _pose(p, "A")
        r = predict_cooperativity(protac="MZ1", poi="BRD4", e3="VHL",
                                  ternary_structure=str(p), poi_chain="A", e3_chain="B",
                                  smiles="CC(C)(C)C(=O)Nc1ccc(C(F)(F)F)cc1")
        ev = r.feature_evidence
        print("\nCooperativity prediction (structural surrogate mode):")
        print("  model kind:", r.model_kind)
        print("  predicted_alpha:", r.predicted_alpha, "| class:", r.cooperativity_class)
        print("  structure available:", r.structure_available)
        print("  feasibility score:", ev.cooperativity_feasibility_score)
        print("  interface: BSA", ev.interface.buried_surface_area_angstrom2,
              "A2 | contacts", ev.interface.intermolecular_contacts,
              "| Hbond(proxy)", ev.interface.putative_hbonds,
              "| clashes", ev.interface.steric_clashes)
        print("  molecular descriptors available:", ev.molecular.available)
        print("  uncertainty:", r.uncertainty["kind"])
        print("  limitation[0]:", r.limitations[0][:120])
        print("  agent tool success:",
              run_cooperativity_predictor({"ternary_structure": str(p), "poi_chain": "A",
                                           "e3_chain": "B"})["success"])

        # explicit-failure behaviour (no evidence)
        try:
            predict_cooperativity(protac="x", poi="BRD4", e3="VHL")
            print("ERROR: expected failure did not trigger")
        except CooperativityEvidenceError as exc:
            print("  no-evidence ->", str(exc)[:90])


if __name__ == "__main__":
    main()

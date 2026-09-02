from protacxtend.backend.schemas import CandidateRecord, TernaryFeasibilityResult
from protacxtend.tools.protac_toolbox import ProtacDesignToolbox
from protacxtend.tools.structural_scoring import parse_pdb_atoms, score_ternary_pose_for_candidate


def _pdb_atom(serial, name, resname, chain, resid, x, y, z, element):
    return (
        f"ATOM  {serial:5d} {name:<4} {resname:>3} {chain}{resid:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00 20.00          {element:>2}\n"
    )


def _write_tiny_ternary_pose(tmp_path):
    pose = tmp_path / "tiny_ternary_pose.pdb"
    pose.write_text(
        "".join(
            [
                _pdb_atom(1, "N", "LYS", "A", 12, 0.0, 0.0, 0.0, "N"),
                _pdb_atom(2, "CA", "LYS", "A", 12, 0.8, 0.0, 0.0, "C"),
                _pdb_atom(3, "CB", "LYS", "A", 12, 1.5, 0.0, 0.0, "C"),
                _pdb_atom(4, "NZ", "LYS", "A", 12, 20.0, 0.0, 0.0, "N"),
                _pdb_atom(5, "N", "GLY", "B", 40, 4.2, 0.0, 0.0, "N"),
                _pdb_atom(6, "CA", "GLY", "B", 40, 4.8, 0.0, 0.0, "C"),
                _pdb_atom(7, "O", "GLY", "B", 40, 5.0, 1.0, 0.0, "O"),
                _pdb_atom(8, "CB", "ALA", "B", 41, 35.0, 0.0, 0.0, "C"),
                "END\n",
            ]
        ),
        encoding="utf-8",
    )
    return pose


def _candidate(candidate_id="pose-cand", pose=None):
    provenance = {"target_chain": "A", "e3_chain": "B"}
    if pose:
        provenance["ternary_pose_pdb"] = str(pose)
    return CandidateRecord(
        candidate_id=candidate_id,
        target="BRD4",
        e3_ligase="CRBN",
        linker_smiles="CCOCC",
        full_protac_smiles="CCOCCN",
        synthetic_feasibility_score=0.7,
        rotatable_bonds=12,
        provenance=provenance,
    )


def test_pose_parser_and_structural_score(tmp_path):
    pose = _write_tiny_ternary_pose(tmp_path)

    atoms = parse_pdb_atoms(pose)
    score = score_ternary_pose_for_candidate("pose-cand", pose, smiles="CCOCCN", target_chain="A", e3_chain="B")

    assert len(atoms) == 8
    assert score.backend == "local_pose_geometry_experimental_v0.1"
    assert score.interface_contact_count > 0
    assert score.nearest_lysine == "LYS12:A"
    assert score.productive_lysine_count >= 1
    assert score.real_structural_score > 0.45


def test_toolbox_ternary_feasibility_uses_pose_backed_backend(tmp_path):
    pose = _write_tiny_ternary_pose(tmp_path)
    toolbox = ProtacDesignToolbox()

    result = toolbox.assess_ternary_feasibility([_candidate(pose=pose)], target_record=None)[0]

    assert result.docking_status == "pose_backed_structural_scoring"
    assert result.structure_availability == "ternary_pose_file"
    assert result.structural_backend == "local_pose_geometry_experimental_v0.1"
    assert result.real_structural_score is not None
    assert result.productive_lysine_count >= 1
    assert result.proceed_to_expensive_modeling


def test_toolbox_ternary_feasibility_labels_proxy_when_no_pose():
    toolbox = ProtacDesignToolbox()

    result = toolbox.assess_ternary_feasibility([_candidate()], target_record=None)[0]

    assert result.structural_backend == "geometry_proxy_stub"
    assert result.real_structural_score is None
    assert result.docking_status == "not_run_stub_available"
    assert result.structural_warnings


def test_cooperativity_consumes_pose_backed_structural_fields():
    toolbox = ProtacDesignToolbox()
    candidate = _candidate()
    ternary = TernaryFeasibilityResult(
        candidate_id="pose-cand",
        ternary_plausibility_score=0.72,
        fast_geometry_feasibility_score=0.7,
        linker_reachability_score=0.6,
        docking_status="pose_backed_structural_scoring",
        interface_quality_score=0.9,
        lysine_geometry_score=0.8,
        linker_strain_score=0.7,
        real_structural_score=0.82,
        structural_confidence=0.85,
    )

    coop = toolbox.predict_cooperativity([candidate], [ternary])[0]

    assert coop.interface_contact_score == 0.9
    assert coop.lysine_geometry_score == 0.8
    assert coop.linker_strain_score == 0.7
    assert "pose-structural-score" in coop.model_version
    assert "measured alpha" in (coop.warning or "")

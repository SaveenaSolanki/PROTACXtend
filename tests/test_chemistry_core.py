from protacxtend.tools.chemistry_core import (
    analyze_protac_like_properties,
    canonicalize_smiles,
    compute_descriptors,
    detect_attachment_points,
    generate_2d_molblock,
    generate_3d_conformer,
    substructure_search,
    tanimoto_similarity,
    validate_smiles,
)


def test_valid_smiles_canonicalization():
    result = canonicalize_smiles("CCO")
    assert result.valid is True
    assert result.canonical_smiles is not None
    assert result.error is None


def test_invalid_smiles_returns_error():
    result = validate_smiles("C1CC")
    assert result.valid is False
    assert result.error is not None


def test_multi_fragment_salt_and_largest_fragment():
    result = canonicalize_smiles("CCO.Cl", largest_fragment=True)
    assert result.valid is True
    assert result.fragments and result.fragments > 1
    assert result.largest_fragment_smiles is not None
    assert result.warnings


def test_descriptor_calculation():
    result = compute_descriptors("CCO")
    assert result.descriptor_status == "success"
    assert result.mw > 0
    assert result.tpsa >= 0
    assert isinstance(result.logp, float)


def test_tanimoto_similarity():
    same = tanimoto_similarity("CCO", "CCO")
    different = tanimoto_similarity("CCO", "c1ccccc1")
    assert same["status"] == "success"
    assert same["similarity"] == 1.0
    assert different["status"] == "success"
    assert 0 <= different["similarity"] <= 1


def test_substructure_search():
    result = substructure_search("CCO", "[OX2H]")
    assert result.matched is True
    assert result.num_matches >= 1
    assert result.atom_indices


def test_attachment_detection():
    result = detect_attachment_points("[*:1]CCO[*:2]")
    assert result["num_dummy_atoms"] == 2
    assert result["has_valid_two_point_attachment"] is True
    assert result["atom_map_numbers"] == [1, 2]


def test_protac_like_warnings_trigger():
    long_chain = "C" * 35
    result = analyze_protac_like_properties(long_chain)
    assert result.valid is True
    assert result.excessive_rotatable_bonds_warning or result.protac_size_warning
    assert result.medicinal_chemistry_notes


def test_2d_molblock():
    result = generate_2d_molblock("CCO")
    assert result["status"] == "success"
    assert "M  END" in result["molblock"]


def test_3d_conformer_does_not_crash():
    result = generate_3d_conformer("CCO")
    assert result["status"] in {"success", "failed"}
    if result["status"] == "success":
        assert result["conformer_id"] is not None
        assert "M  END" in result["molblock"]
    else:
        assert result["error"]


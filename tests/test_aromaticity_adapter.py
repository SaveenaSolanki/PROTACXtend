from synglue_agent.tools.aromaticity_adapter import (
    aromaticity_summary,
    detect_aromaticity_backend,
    rdkit_aromaticity_summary,
)


def test_detect_aromaticity_backend_shape():
    result = detect_aromaticity_backend()
    assert "selected_backend" in result
    assert "status" in result
    assert result["selected_backend"] in {"aromaticity_core", "rdkit", "none"}


def test_rdkit_aromaticity_summary_benzene():
    result = rdkit_aromaticity_summary("c1ccccc1")
    assert result["status"] == "success"
    assert result["backend"] == "rdkit"
    assert result["aromatic_ring_count"] >= 1


def test_aromaticity_summary_fallback_or_core_does_not_crash():
    result = aromaticity_summary("c1ccccc1")
    assert result["status"] == "success"
    assert result["backend"] in {"aromaticity_core", "rdkit_fallback"}
    assert result["aromatic_ring_count"] >= 1


def test_invalid_smiles_returns_failed_status():
    result = aromaticity_summary("C1CC")
    assert result["status"] == "failed"
    assert result["error"] is not None


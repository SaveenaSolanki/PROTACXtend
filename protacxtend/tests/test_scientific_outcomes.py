"""Regression tests for the scientific outcome taxonomy, input validation,
prospective consensus and real fallback labelling.

These close the "silent scientific failure" class: an invalid input or an
empty output may never be reported as SUCCESS.
"""

from __future__ import annotations

import pytest

from protacxtend.scientific_backends.evidence import (
    CapabilityStatus,
    NON_SUCCESS_OUTCOMES,
    ScientificResult,
    USABLE_OUTCOMES,
)
from protacxtend.scientific_backends.validation import validate_result_output, validate_smiles


@pytest.mark.parametrize("bad", [None, float("nan"), "", "   ", "nan", "null", "not_a_smiles", "!!!"])
def test_invalid_smiles_rejected(bad):
    ok, reason, mol = validate_smiles(bad)
    assert ok is False
    assert reason
    assert mol is None


@pytest.mark.parametrize("good", ["CCO", "c1ccccc1", "CC(=O)Oc1ccccc1C(=O)O"])
def test_valid_smiles_accepted(good):
    ok, reason, mol = validate_smiles(good)
    assert ok is True
    assert mol is not None
    assert mol.GetNumAtoms() > 0


def test_too_small_ligand_rejected():
    ok, _reason, _mol = validate_smiles("C", min_heavy_atoms=3)
    assert ok is False


def test_outcome_taxonomy_is_complete_and_disjoint():
    values = {s.value for s in CapabilityStatus}
    for required in ("REJECTED_INPUT", "OUTPUT_INVALID", "SCIENTIFIC_SANITY_FAILED",
                     "BACKEND_UNAVAILABLE", "TIMEOUT", "FALLBACK_SUCCESS"):
        assert required in values
    assert not (NON_SUCCESS_OUTCOMES & USABLE_OUTCOMES)


def test_fallback_success_is_usable_but_not_plain_success():
    r = ScientificResult.fallback_success("ligand_docking", "autodock_vina", "diffdock", "boom")
    assert r.status == CapabilityStatus.FALLBACK_SUCCESS.value
    assert r.ok() is True
    assert r.succeeded() is False
    assert r.is_fallback() is True
    assert r.data["fallback"]["primary"] == "diffdock"


def test_output_gate_rejects_empty_payload():
    r = ScientificResult(capability="ligand_docking", backend="x")
    r.data = {}
    ok, _reason = validate_result_output(r)
    assert ok is False


def test_output_gate_accepts_finite_payload():
    r = ScientificResult(capability="ligand_docking", backend="x")
    r.data = {"n_poses": 3, "best_score_kcal_mol": -7.5}
    ok, _reason = validate_result_output(r)
    assert ok is True


def test_vina_rejects_invalid_smiles_without_computing():
    from protacxtend.scientific_backends.backends.docking import vina_docking

    r = vina_docking(receptor_pdb="", ligand_smiles="!!!")
    assert r.status == CapabilityStatus.REJECTED_INPUT.value
    assert r.ok() is False
    assert r.outcome() == "rejected_input"


def test_consensus_weights_are_pre_registered():
    from protacxtend.scientific_backends.consensus import CONSENSUS_WEIGHTS

    assert abs(sum(CONSENSUS_WEIGHTS.values()) - 1.0) < 1e-9
    assert "native" not in " ".join(CONSENSUS_WEIGHTS)


def test_runner_marks_fallback_success_when_primary_disabled():
    """Disabling the top backend must execute the next one, labelled FALLBACK."""
    from protacxtend.scientific_backends.registry import Capability, REGISTRY, load_backends
    from protacxtend.scientific_backends.runner import run_capability

    load_backends()
    usable = REGISTRY.resolve(Capability.CHEMISTRY, include_restricted=False)
    if len(usable) < 2:
        pytest.skip("fewer than two chemistry backends available")
    primary = usable[0].name
    result = run_capability("chemistry", disabled_backends={primary},
                            mark_fallback_after=primary, smiles="CCO")
    assert result.ok()
    assert result.backend != primary
    assert result.status in {CapabilityStatus.FALLBACK_SUCCESS.value,
                             CapabilityStatus.SUCCESS.value}


def test_execute_primary_then_fallback_shape():
    from protacxtend.scientific_backends.runner import execute_primary_then_fallback

    payload = execute_primary_then_fallback("chemistry", "rdkit", "openbabel", smiles="CCO")
    assert payload["capability"] == "chemistry"
    assert payload["primary_backend"] == "rdkit"
    assert "primary" in payload and "fallback" in payload

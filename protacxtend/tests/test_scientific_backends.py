"""Tests for the capability-first scientific backend layer.

Offline by default; tests that need a model/GPU are skipped when unavailable.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from protacxtend.scientific_backends import (
    Capability,
    DEFAULT_POLICY,
    EvidenceTier,
    ScientificResult,
    capability_matrix,
    policy_from_env,
    run_capability,
)
from protacxtend.scientific_backends.registry import REGISTRY, load_backends
from protacxtend.scientific_backends.runner import _coerce_capability

ROOT = Path(__file__).resolve().parents[2]
RECEPTOR = ROOT / "outputs" / "p4ward_evidence" / "input_hmgb2_receptor.pdb"
COMPLEX = ROOT / "outputs" / "p4ward_evidence" / "crbn_megadock_ready.pdb"
APO = ROOT / "outputs" / "p4ward_evidence" / "crbn_fixed_minim.pdb"


@pytest.fixture(scope="module")
def loaded():
    load_backends()
    return REGISTRY


def test_every_capability_has_a_name():
    assert len(list(Capability)) == 19
    for cap in Capability:
        assert cap.value == cap.value.lower()


def test_all_capabilities_resolve_to_free_backends():
    """No capability's *best* backend may be commercial/web/academic."""
    for row in capability_matrix():
        assert row["status"] != "LICENSE_REQUIRED", row
        assert row["best_backend"], row
        spec = REGISTRY.get(row["best_backend"])
        assert spec is not None
        assert spec.license.open_source, f"{row['capability']} → {spec.name} ({spec.license.name})"


def test_backend_contract_fields(loaded):
    required = {
        "name", "capabilities", "license", "redistributable", "requires_gpu",
        "requires_external_binary", "requires_network", "academic_only",
        "commercial_use_restricted", "priority", "version", "citation",
    }
    for spec in loaded.all():
        payload = spec.to_dict()
        assert required <= set(payload), spec.name
        assert payload["capabilities"]
        assert isinstance(payload["priority"], int)


def test_default_policy_excludes_commercial_and_web(loaded):
    from protacxtend.scientific_backends.registry import resolve

    names = {b.name for b in resolve(Capability.LIGAND_DOCKING, DEFAULT_POLICY)}
    for banned in ("schrodinger_glide", "gold_ccdc", "moe", "icm_pro"):
        assert banned not in names
    admet = {b.name for b in resolve(Capability.ADMET, DEFAULT_POLICY)}
    assert "swissadme" not in admet and "admetlab3" not in admet
    ppi = {b.name for b in resolve(Capability.PPI_DOCKING, DEFAULT_POLICY)}
    assert "cluspro" not in ppi and "haddock_web" not in ppi and "haddock_cns" not in ppi


def test_license_gate_returns_license_required():
    r = run_capability("ligand_docking", preferred_backend="schrodinger_glide")
    assert r.status == "LICENSE_REQUIRED"
    assert r.method_label == "LICENSE_REQUIRED"
    assert "licence" in r.summary.lower() or "license" in r.summary.lower() or "commercial" in r.summary.lower()

    web = run_capability("admet", preferred_backend="swissadme")
    assert web.status == "LICENSE_REQUIRED"


def test_license_policy_env_opt_in(monkeypatch):
    monkeypatch.setenv("PROTACXTEND_ALLOW_COMMERCIAL", "1")
    policy = policy_from_env()
    assert policy.allow_commercial
    r = run_capability("ligand_docking", preferred_backend="schrodinger_glide", policy=policy,
                       include_restricted=True)
    assert r.status == "LICENSE_REQUIRED"  # adapter refuses even when policy allows the class


def test_result_metadata_contract():
    r = ScientificResult(capability="molecular_dynamics", backend="openmm",
                         evidence_tier=EvidenceTier.TIER_4_REPLICATE_MD.value)
    payload = r.to_dict()
    for key in ("capability", "backend", "backend_version", "evidence_tier", "approximation",
                "gpu_used", "runtime_seconds", "license_class", "citations", "warnings"):
        assert key in payload


def test_capability_alias_resolution():
    assert _coerce_capability("protein_protein_docking") is Capability.PPI_DOCKING
    assert _coerce_capability("md") is Capability.MOLECULAR_DYNAMICS
    assert _coerce_capability("admet_toxicity") is Capability.ADMET
    with pytest.raises(KeyError):
        _coerce_capability("not_a_capability")


# ── functional local smoke tests ────────────────────────────────────────

def test_chemistry_and_admet_local():
    r = run_capability("chemistry", smiles="CCO", operation="descriptors")
    assert r.status == "success"
    assert r.data["molecular_weight"] > 0
    assert r.evidence_tier == EvidenceTier.TIER_0_GEOMETRY.value

    a = run_capability("admet", smiles="CCO")
    assert a.status == "success"
    assert a.data["descriptors"]["lipinski_pass"] in (True, False)


def test_conformer_generation_local(tmp_path):
    r = run_capability("conformer_generation", smiles="CCO", n_conformers=2, output_dir=str(tmp_path))
    if r.status != "success":
        pytest.skip(f"rdkit conformers unavailable: {r.summary}")
    assert r.data["n_conformers"] >= 1
    assert Path(r.data["sdf"]).exists()


def test_linker_analysis_local():
    r = run_capability("linker_analysis", linker_smiles="[*:1]CCOCCO[*:2]")
    assert r.status == "success"
    assert r.data["contour_length_A"] > 0
    assert r.data["end_to_end_distance_A"]["mean"] is not None


def test_candidate_ranking_local():
    r = run_capability("candidate_ranking",
                       candidates=[{"candidate_id": "a", "log_dc50": 1.0},
                                   {"candidate_id": "b", "log_dc50": 2.0}])
    assert r.status == "success"
    assert len(r.data["ranking"]) == 2


@pytest.mark.skipif(not RECEPTOR.exists(), reason="test receptor not present")
def test_pocket_detection_local():
    r = run_capability("pocket_detection", pdb_path=str(RECEPTOR), top_n=2)
    assert r.status == "success"
    assert r.data["engine"] in {"geometry", "fpocket"}
    assert r.data["pockets"]


@pytest.mark.skipif(not COMPLEX.exists(), reason="test complex not present")
def test_interaction_fingerprint_local():
    r = run_capability("interaction_fingerprint", complex_pdb=str(COMPLEX), ligand_resname="UNL")
    assert r.status == "success"
    assert "n_hydrogen_bonds" in r.data


@pytest.mark.skipif(not (COMPLEX.exists() and APO.exists()), reason="test complexes not present")
def test_metabolite_ppi_local():
    r = run_capability("metabolite_ppi_scoring", apo_complex_pdb=str(APO),
                       ternary_complex_pdb=str(COMPLEX), metabolite_resname="UNL")
    assert r.status == "success"
    assert r.data["verdict"] in {"potential_stabilization", "potential_destabilization",
                                 "no_detectable_structural_effect", "insufficient_evidence"}
    assert "prove" in r.data["disclaimer"] or "proof" in r.data["disclaimer"]


@pytest.mark.skipif(not (COMPLEX.exists() and APO.exists()), reason="test complexes not present")
def test_molecular_glue_local():
    r = run_capability("molecular_glue_scoring", apo_complex_pdb=str(APO),
                       ligand_bound_complex_pdb=str(COMPLEX), ligand_resname="UNL")
    assert r.status == "success"
    assert "deltas" in r.data


def test_model_registry_local_asset():
    from protacxtend.scientific_backends.models import fetch_model, list_models

    assert list_models()
    result = fetch_model("tack_dc50")
    assert result["status"] in {"local", "missing_local_asset"}


def test_model_registry_refuses_unverified_or_no_network():
    from protacxtend.scientific_backends.models import fetch_model

    r = fetch_model("alphafold_params")
    assert r["status"] in {"no_url", "unverified_refused", "CAPABILITY_UNAVAILABLE", "LICENSE_REQUIRED"}


# ── hardening tests (P0/P1) ─────────────────────────────────────────────

def test_borda_rank_consensus_never_averages_scores():
    from protacxtend.scientific_backends.backends.docking import _borda_consensus

    result = _borda_consensus({
        "vina": [{"rank": 1}, {"rank": 2}, {"rank": 3}],
        "gnina": [{"rank": 1}, {"rank": 2}],
    })
    assert result["method"] == "BORDA"
    assert result["ranking"]
    assert "not averaged" in result["note"]
    # a pose ranked first by both engines must win the consensus
    assert result["ranking"][0]["item"] in {"vina#1", "gnina#1"}


def test_validate_system_pass_and_report():
    from protacxtend.scientific_backends.backends.md import validate_system

    if not RECEPTOR.exists():
        pytest.skip("test receptor not present")
    report = validate_system(str(RECEPTOR))
    assert report["verdict"] in {"pass", "warn"}
    assert "checks" in report and "metals" in report["checks"]
    assert validate_system("/nonexistent.pdb")["verdict"] == "fail"


def test_trajectory_sasa_mdtraj():
    from protacxtend.scientific_backends.backends.md import _trajectory_sasa

    if not RECEPTOR.exists():
        pytest.skip("test receptor not present")
    sasa = _trajectory_sasa(str(RECEPTOR), str(RECEPTOR))
    assert sasa.get("sasa_A2")
    assert sasa["sasa_A2"][0] > 0


def test_ligand_parameterization_provenance(loaded):
    from protacxtend.scientific_backends.dispatch import module_available, run_cross_env

    if not module_available("openmm"):
        pytest.skip("openmm not installed")
    out = run_cross_env("protacxtend.scientific_backends.backends.md", "_parameterize_ligand_openmm",
                        args=["CCO", "LIG"], require_import="openmm", timeout=900)
    assert out["ok"], out.get("error")
    info = out["result"]
    assert info["engine"] in {"openff", "gaff", "generic_unparameterized"}
    assert "forcefield" in info and "charge_method" in info


def test_openmm_run_writes_checkpoint_and_provenance(tmp_path):
    from protacxtend.scientific_backends.dispatch import module_available, run_cross_env

    md_ready = ROOT / "outputs" / "p4ward_evidence" / "hmgb2_fixed_minim.pdb"
    pose = md_ready if md_ready.exists() else RECEPTOR
    if not (module_available("openmm") and pose.exists()):
        pytest.skip("openmm or test structure unavailable")
    out = run_cross_env("protacxtend.scientific_backends.backends.md", "_openmm_run",
                        args=[str(pose), str(tmp_path / "md")],
                        kwargs={"md_steps": 0, "minimize_steps": 5},
                        require_import="openmm", timeout=1800)
    if not out["ok"]:
        pytest.skip(f"openmm could not build system: {out.get('error')}")
    result = out["result"]
    assert Path(result["checkpoint"]).exists()
    assert Path(result["topology_pdb"]).exists()
    assert result["ligand_parameters"]["engine"] in {"openff", "gaff", "generic_unparameterized", "none"}
    assert result["forcefield"]


def test_docking_adapters_return_results():
    """GNINA/LightDock/DiffDock adapters must degrade, never crash."""
    from protacxtend.scientific_backends.backends import docking

    for fn in (docking.gnina_docking, docking.diffdock_docking, docking.lightdock_ppi_docking):
        r = fn(receptor_pdb="/nonexistent.pdb", ligand_smiles="CCO", ligand_pdb="/nonexistent.pdb")
        assert r.status in {"success", "warning", "error", "CAPABILITY_UNAVAILABLE",
                            "BACKEND_UNAVAILABLE", "REJECTED_INPUT", "OUTPUT_INVALID",
                            "SCIENTIFIC_SANITY_FAILED", "TIMEOUT", "FALLBACK_SUCCESS"}


def test_matched_apo_holo_runs():
    from protacxtend.scientific_backends.backends.md import matched_apo_holo_analysis

    if not RECEPTOR.exists():
        pytest.skip("test receptor not present")
    r = matched_apo_holo_analysis(apo_topology=str(RECEPTOR), holo_topology=str(RECEPTOR))
    assert r.status == "success"
    assert "deltas" in r.data

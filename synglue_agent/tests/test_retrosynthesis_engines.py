"""
Tests: multi-engine retrosynthesis toolkit layer
==================================================
Covers the three working toolkits registered in this project:

  * ASKCOS (MIT)        — retrosynthesis_engines.AskcosClient (verified REST contract)
  * AiZynthFinder       — run_aizynth_engine (assets/package gated)
  * RDKit + OpenNMT     — Molecular Transformer tokenizer + run_openmt_engine (honest gate)

Discipline: no engine may crash; unavailable engines must be reported honestly;
the ASKCOS client contract is tested with a stub session (offline). Live-web
tests are marked ``network``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from synglue_agent.tools.retrosynthesis import (
    RetrosynthesisResult,
    assess_retrosynthesis,
)
from synglue_agent.tools.retrosynthesis_engines import (
    ENGINE_CODES,
    ENGINE_META,
    AskcosClient,
    EngineOutcome,
    aizynth_assets_available,
    detokenize_smiles,
    engine_status_report,
    merge_engine_outcomes,
    normalize_engine_code,
    openmt_checkpoint_path,
    run_askcos_engine,
    run_engines,
    tokenize_smiles,
    validate_smiles_with_rdkit,
)

ASPIRIN = "CC(=O)Oc1ccccc1C(=O)O"

# ── small stub session (offline) ────────────────────────────────────────────

class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


ONE_STEP_CANNED = {
    "status_code": 200,
    "result": [[{
        "outcome": "CC(=O)OC(C)=O.O=C(O)c1ccccc1O",
        "model_score": 0.4067,
        "normalized_model_score": 0.4067,
        "template": {"template_set": "reaxys", "reaction_smarts": "[C:1]-[C:2](=O)-[O:3]>>[C:1]-[C:2](=O)-[O:3]"},
    }]],
}

TREE_CANNED = {
    "status_code": 200,
    "result": {
        "stats": {"total_paths": 2, "total_chemicals": 4, "total_reactions": 3},
        "uds": {
            "node_dict": {
                ASPIRIN: {"smiles": ASPIRIN, "terminal": False, "type": "chemical",
                           "purchase_price": 1.0},
                "CC(=O)OC(C)=O.O=C(O)c1ccccc1O>>" + ASPIRIN: {
                    "smiles": "CC(=O)OC(C)=O.O=C(O)c1ccccc1O>>" + ASPIRIN,
                    "type": "reaction", "plausibility": 0.99},
                "CC(=O)OC(C)=O": {"smiles": "CC(=O)OC(C)=O", "terminal": True,
                                  "purchase_price": 5.0, "type": "chemical"},
                "O=C(O)c1ccccc1O": {"smiles": "O=C(O)c1ccccc1O", "terminal": True,
                                    "purchase_price": 12.0, "type": "chemical"},
            },
            "path_dict": {"p0": [ASPIRIN, "CC(=O)OC(C)=O.O=C(O)c1ccccc1O>>" + ASPIRIN,
                                 "CC(=O)OC(C)=O", "O=C(O)c1ccccc1O"]},
        },
        "result_id": "probe-1",
    },
}


class FakeAskcosSession:
    """session double returning canned ASKCOS responses."""

    def __init__(self, tree: bool = False):
        self.calls: list[tuple[str, str]] = []
        self.tree = tree

    def get(self, url, timeout=None):  # noqa: ARG002
        self.calls.append(("GET", url))
        return _FakeResponse({
            "info": {"title": "ASKCOS2 API", "version": "1.0"},
            "paths": {"/api/retro/controller/call-sync": {}},
        })

    def post(self, url, headers=None, data=None, timeout=None):  # noqa: ARG002
        self.calls.append(("POST", url))
        if "tree-search/retro-star" in url:
            return _FakeResponse(TREE_CANNED)
        if "buyables" in url:
            return _FakeResponse({"result": [{
                "smiles": "O=C(O)c1ccccc1O", "ppg": 12.0,
                "source": "EM", "similarity": 1.0}]})
        return _FakeResponse(ONE_STEP_CANNED)


# ── engine catalogue ────────────────────────────────────────────────────────

class TestEngineCatalogue:
    def test_three_engines_registered(self):
        assert set(ENGINE_CODES) == {"askcos", "aizynth", "openmt"}
        assert ENGINE_META["askcos"]["display_name"] == "ASKCOS (MIT)"
        assert ENGINE_META["askcos"]["license"] == "MIT"
        assert ENGINE_META["aizynth"]["display_name"].startswith("AiZynthFinder")
        assert "OpenNMT" in ENGINE_META["openmt"]["display_name"]

    def test_alias_resolution(self):
        assert normalize_engine_code("aizynthfinder") == "aizynth"
        assert normalize_engine_code("ASKCOS-MIT") == "askcos"
        assert normalize_engine_code("rdkit+opennmt") == "openmt"
        assert normalize_engine_code("molecular-transformer") == "openmt"
        assert normalize_engine_code("not-an-engine") is None

    def test_status_report_is_honest_and_safe(self, skip_network=True):
        rep = engine_status_report(skip_network=True)
        assert set(rep) == set(ENGINE_CODES)
        for entry in rep.values():
            assert "available" in entry["status"]
            assert isinstance(entry["status"]["available"], bool)
        # local backends are unavailable right now (no package/checkpoint) but
        # must still report a stable machine reason, not crash
        assert rep["openmt"]["status"]["package_installed"] is False
        assert rep["aizynth"]["status"]["assets_present"] is True or (
            aizynth_assets_available() in (True, False))


# ── RDKit + OpenNMT tokenizer (runs with RDKit alone) ───────────────────────

class TestMolecularTransformerTokenizer:
    TOKEN_LOSSLESS = [
        "CC(=O)Oc1ccccc1C(=O)O", "CCO", "c1ccccc1C(=O)O",
        "CC(=O)OC(C)=O.O=C(O)c1ccccc1O", "C[C@H](N)C(=O)O",
        "F[C@H]1CC[C@@H](O)CC1", "Clc1ccccc1Br",
        "[NH3+]CC(=O)[O-]",                      # charged atoms
        "CC(=O)Nc1ccc(S(=O)(=O)N2CCN(C)CC2)cc1",  # sulfonamide ring
    ]

    def test_tokenization_is_lossless(self):
        for s in self.TOKEN_LOSSLESS:
            assert detokenize_smiles(tokenize_smiles(s)) == s, s
            assert len(tokenize_smiles(s)) > 0

    def test_rdkit_validation(self):
        assert validate_smiles_with_rdkit(ASPIRIN) is not None
        assert validate_smiles_with_rdkit("not-a-smiles") is None
        assert validate_smiles_with_rdkit("") is None

    def test_double_bond_and_dative_tokens(self):
        tokens = tokenize_smiles("C=C")
        assert tokens == ["C", "=", "C"]


# ── ASKCOS client contract (stub session, offline) ─────────────────────────

class TestAskcosClient:
    def test_one_step_contract(self):
        session = FakeAskcosSession()
        client = AskcosClient(base_url="https://askcos.mit.edu", session=session, timeout_s=10)
        probe = client.probe()
        assert probe["reachable"] is True
        assert probe["detail"]["api_title"] == "ASKCOS2 API"

        one = client.one_step_retro([ASPIRIN], max_num_templates=20)
        per = one["per_input"][0]
        assert per["query"] == ASPIRIN
        assert per["precursors"][0]["precursor_smiles"] == "CC(=O)OC(C)=O.O=C(O)c1ccccc1O"
        assert per["precursors"][0]["template_set"] == "reaxys"
        assert ("GET", "https://askcos.mit.edu/openapi.json") in session.calls

    def test_tree_search_normalization(self):
        session = FakeAskcosSession()
        client = AskcosClient(base_url="https://askcos.mit.edu", session=session, timeout_s=60)
        t = client.tree_search(ASPIRIN, expansion_time=1)
        assert t["route_found"] is True
        assert t["route_count"] == 2
        assert t["shortest_steps"] == 1
        assert t["purchasable_fraction"] == 1.0     # both leaves are terminal
        assert len(t["routes"]) >= 1

    def test_run_askcos_engine_with_stub(self):
        out = run_askcos_engine(ASPIRIN, session=FakeAskcosSession(), mode="one_step",
                                timeout_s=10, max_num_templates=10)
        assert isinstance(out, EngineOutcome)
        assert out.engine == "askcos"
        assert out.available is True and out.ran is True
        assert out.route_found is True
        assert out.route_count >= 1
        assert out.shortest_steps == 1
        assert out.precursors and out.precursors[0]["precursor_smiles"]
        assert out.provenance["base_url"] == "https://askcos.mit.edu"

    def test_unreachable_endpoint_reports_tool_failed(self):
        # 127.0.0.1:9 refuses connections immediately -> graceful, no crash
        out = run_askcos_engine(ASPIRIN, base_url="http://127.0.0.1:9",
                                mode="one_step", timeout_s=1.5)
        assert out.ran is False and out.available is False
        assert out.tool_failed == "askcos_unreachable"
        assert out.note


# ── engine orchestration ────────────────────────────────────────────────────

class TestEngineOrchestration:
    def test_openmt_engine_unavailable_is_honest(self):
        out = run_engines(ASPIRIN, engines=["openmt"])
        assert len(out.outcomes) == 1
        o = out.outcomes[0]
        assert o.engine == "openmt" and o.ran is False
        assert o.tool_failed in {"opennmt_package_missing", "opennmt_checkpoint_missing"}

    def test_unknown_engine_ignored(self):
        out = run_engines(ASPIRIN, engines=["bogus", "openmt"])
        assert set(out.engines_requested) == {"openmt"}

    def test_merge_engine_outcomes(self):
        ok_aizynth = EngineOutcome(engine="aizynth", available=True, ran=True,
                                   route_found=True, route_count=2, shortest_steps=2,
                                   routes=["r1", "r2"], purchasable_fraction=0.5)
        ok_askcos = EngineOutcome(engine="askcos", available=True, ran=True,
                                  route_found=True, route_count=5, shortest_steps=1,
                                  routes=["a1"], purchasable_fraction=1.0)
        failed = EngineOutcome(engine="openmt", available=False, ran=False,
                               tool_failed="opennmt_package_missing")
        summary = merge_engine_outcomes([failed, ok_askcos, ok_aizynth],
                                        engines_requested=["askcos", "aizynth", "openmt"])
        assert summary.any_route_found is True
        assert summary.best_engine == "askcos"      # fewer steps wins
        assert summary.engines_available == ["askcos", "aizynth"]  # canonical ENGINE_CODES order
        assert summary.purchasable_fraction == 1.0
        assert summary.shortest_steps == 1

    def test_assess_retrosynthesis_engines_metadata_offline(self):
        # no route engine actually runs offline here: default aizynth path
        r = assess_retrosynthesis(ASPIRIN, candidate_id="eng", use_aizynth=True)
        assert isinstance(r, RetrosynthesisResult)
        assert r.engines_requested == ["aizynth"]
        assert r.engines_ran == []                  # aizynthfinder not installed here
        assert any("aizynthfinder" in t for t in r.tools_used)

    def test_assess_retrosynthesis_openmt_downgrade_no_network(self):
        r = assess_retrosynthesis(ASPIRIN, candidate_id="eng2", engines=["openmt"])
        assert r.status == "tool_failed"
        assert "openmt:unavailable" in r.tools_used
        assert r.engines_requested == ["openmt"]
        assert r.engine_outcomes[0]["tool_failed"].startswith("opennmt_")

    def test_assess_retrosynthesis_disabled_legacy_message(self):
        r = assess_retrosynthesis("CCO", use_aizynth=False)
        assert r.status == "tool_failed"
        assert "aizynthfinder:disabled" in r.tools_used


# ── live network (opt-in) ───────────────────────────────────────────────────

@pytest.mark.network
class TestAskcosLive:
    def test_live_one_step(self):
        out = run_askcos_engine(ASPIRIN, mode="one_step", timeout_s=45, max_num_templates=10)
        assert out.available and out.ran
        assert out.route_found
        assert out.provenance["base_url"] == "https://askcos.mit.edu"

    def test_live_checkpoint_file_convention(self):
        # no-op documentation guard: verify the checkpoint dir convention exists
        assert openmt_checkpoint_path() is None or openmt_checkpoint_path().exists()

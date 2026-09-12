"""Host adapter tests: PROTACXtend run records → cognitive memory.

These exercise the pure mapping helpers without the cognitive package and the
end-to-end bridge when ``protacpilot_memory`` is importable (it is discovered
from the sibling ``protacpilot-memory/src`` checkout).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from protacxtend.memory import cognitive_bridge as cb  # noqa: E402


def _record(**overrides):
    rec = {
        "run_id": "run_test_1",
        "user_objective": "Design VHL-recruiting PROTACs against BRD4 BD2 with PEG linkers",
        "parsed_objective": {
            "target_name": "BRD4",
            "target_domain": "BD2",
            "e3": "VHL",
            "cell_line": "HEK293",
            "preferred_linker_types": ["PEG"],
            "raw_request": "Design VHL PROTAC against BRD4",
            "objectives": ["degradation"],
        },
        "evidence_records": [
            {"type": "binder", "name": "BRD4-BD2 compact binder", "source": "chembl"},
            {"type": "binder", "name": "BRD4-BD2 compact binder", "source": "chembl"},  # duplicate
            {"type": "evidence_degradation", "value": {"dmax": 0.8}},
        ],
        "final_candidates": [
            {"candidate_id": "cand_0", "log_dc50": -7.2, "dmax_inverted": 0.3},
            {"candidate_id": "cand_1", "log_dc50": "-6.1", "dmax_inverted": None},
        ],
        "candidates_generated": 2,
        "candidates_valid": 2,
        "routing_path": ["planner", "linker_generation", "ranking"],
        "tools_executed": ["linker_generation", "ranking"],
        "errors": [],
        "warnings": [],
        "repair_events": [],
        "runtime_seconds": 1.5,
        "llm_calls": 3,
        "llm_failures": 0,
        "reproducibility_hash": "deadbeef",
    }
    rec.update(overrides)
    return rec


# ── pure mapping ─────────────────────────────────────────────────────────────
class TestContextMapping:
    def test_maps_host_parsed_objective(self):
        ctx = cb.host_context_from_record(_record())
        assert ctx["target_gene"] == "BRD4"
        assert ctx["target_domain"] == "BD2"
        assert ctx["e3_ligase"] == "VHL"
        assert ctx["cell_line"] == "HEK293"
        assert ctx["linker_type"] == "PEG"
        assert ctx["extra"]["raw_request"]

    def test_accepts_pydantic_like_object(self):
        class FakeModel:
            def model_dump(self):
                return _record()

        ctx = cb.host_context_from_record(FakeModel())
        assert ctx["target_gene"] == "BRD4"

    def test_target_uniprot_and_e3_ligase_variants(self):
        rec = _record(parsed_objective={
            "target_uniprot_id": "O60885", "e3_ligase": "CRBN", "assay_context": "HiBiT",
        })
        ctx = cb.host_context_from_record(rec)
        assert ctx["target_uniprot"] == "O60885"
        assert ctx["e3_ligase"] == "CRBN"
        assert ctx["assay_type"] == "HiBiT"


class TestEvidenceMapping:
    def test_type_mapping_and_dedup(self):
        refs = cb.host_evidence_from_record(_record())
        assert len(refs) == 2  # duplicate binder collapsed
        types = {r["evidence_type"] for r in refs}
        assert "curated_database" in types
        assert "ml_prediction" in types

    def test_limit_respected(self):
        rec = _record(evidence_records=[{"type": "binder", "name": f"b{i}"} for i in range(100)])
        assert len(cb.host_evidence_from_record(rec, limit=10)) == 10


class TestPredictionMapping:
    def test_extracts_numeric_metrics(self):
        preds = cb.host_predictions_from_record(_record())
        by_metric = {(p["candidate_id"], p["metric"]): p for p in preds}
        assert by_metric[("cand_0", "log_dc50")]["predicted_value"] == -7.2
        assert by_metric[("cand_1", "log_dc50")]["predicted_value"] == -6.1
        assert ("cand_1", "dmax_inverted") not in by_metric

    def test_custom_metrics(self):
        preds = cb.host_predictions_from_record(_record(), metrics=["log_dc50"])
        assert {p["metric"] for p in preds} == {"log_dc50"}


class TestEpisodePayload:
    def test_payload_shape(self):
        payload = cb.run_episode_payload(_record())
        assert payload["event_type"] == "procedure_run"
        assert payload["context"]["target_gene"] == "BRD4"
        assert payload["source"]["run_id"] == "run_test_1"
        assert payload["observed"]["candidates_valid"] == 2
        assert payload["is_negative"] is False

    def test_failure_payloads(self):
        rec = _record(errors=["docking failed"], repair_events=[
            {"node": "RepairController", "reason_codes": ["RETRY_ALTERNATE_LINKER"], "confidence": 0.6}
        ])
        payloads = cb.failure_episode_payloads(rec)
        assert len(payloads) == 2
        assert all(p["is_negative"] for p in payloads)
        assert any("RETRY_ALTERNATE_LINKER" in p["title"] for p in payloads)


# ── opt-in gating ────────────────────────────────────────────────────────────
class TestOptIn:
    def test_maybe_ingest_disabled_by_default(self, monkeypatch):
        monkeypatch.delenv(cb.ENABLE_ENV, raising=False)
        out = cb.maybe_ingest(_record())
        assert out["enabled"] is False

    def test_maybe_retrieve_disabled_by_default(self, monkeypatch):
        monkeypatch.delenv(cb.ENABLE_ENV, raising=False)
        out = cb.maybe_retrieve("anything")
        assert out["enabled"] is False and out["results"] == []


# ── end-to-end (requires protacpilot_memory) ─────────────────────────────────
requires_memory = pytest.mark.skipif(
    not cb.available(), reason="protacpilot_memory not importable"
)


@requires_memory
class TestBridgeEndToEnd:
    @pytest.fixture
    def bridge(self):
        import protacpilot_memory

        mem = protacpilot_memory.CognitiveMemory.in_memory()
        b = cb.CognitiveMemoryBridge(mem, project_name="bridge-test")
        yield b
        mem.close()

    def test_ingest_encodes_episode_and_predictions(self, bridge):
        out = bridge.ingest_run_record(_record())
        assert out["enabled"] is True
        assert out["episode"]["episode_id"], out["episode"]
        assert out["n_predictions"] == 3  # 2 x log_dc50 + 1 x dmax_inverted

    def test_ingest_creates_negative_memories(self, bridge):
        rec = _record(errors=["assembly failed"],
                      repair_events=[{"node": "RepairController",
                                      "reason_codes": ["RETRY_ALTERNATE_LINKER"]}])
        out = bridge.ingest_run_record(rec)
        assert out["n_failure_episodes"] == 2

    def test_retrieve_returns_ingested_run(self, bridge):
        bridge.ingest_run_record(_record())
        result = bridge.retrieve(
            "BRD4 VHL PEG degradation",
            host_context={"target_gene": "BRD4", "target_domain": "BD2", "e3_ligase": "VHL"},
            limit=5,
        )
        assert result["enabled"] is True
        assert result["results"]
        blob = json.dumps(result["results"])
        assert "run_test_1" in blob or "BRD4" in blob

    def test_prompt_context_is_prompt_ready(self, bridge):
        bridge.ingest_run_record(_record())
        ctx = bridge.prompt_context("BRD4 VHL degradation", limit=3)
        assert ctx["enabled"] is True
        assert isinstance(ctx["text"], str) and ctx["text"]

    def test_candidate_outcome_roundtrip(self, bridge):
        bridge.ingest_run_record(_record())
        out = bridge.record_candidate_outcome("cand_0", "log_dc50", observed_value=-6.0)
        assert out["ok"] is True
        assert out["outcome"]["prediction_error"] is not None

    def test_ingest_run_file(self, bridge, tmp_path):
        run_dir = tmp_path / "run_test_1"
        run_dir.mkdir()
        (run_dir / "run.json").write_text(json.dumps(_record()), encoding="utf-8")
        out = bridge.ingest_run_dir(run_dir)
        assert out["enabled"] is True and out["run_id"] == "run_test_1"

    def test_stats(self, bridge):
        bridge.ingest_run_record(_record())
        stats = bridge.stats()
        assert stats["enabled"] is True

"""Gate B regression tests — scientific-mode propagation and protein identity.

These lock down the two severity-1 findings from ``todo_audit/``:

* ``F-03`` SCIENTIFIC mode must not build a strategy from ``local_demo_*``
  warheads/E3 ligands, on either the agent path or the canonical path.
* ``F-04`` BRD4 must resolve to the reviewed UniProt accession ``O60885``
  (never the fragment ``M0QZD9``).

Fast and offline: the canonical tests inject a fake engine state; the target
resolver test reads the packaged curated table.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from protacxtend.canonical import CanonicalOrchestrator  # noqa: E402
from protacxtend.runtime import modes  # noqa: E402
from protacxtend.tools.protac_toolbox import ProtacDesignToolbox  # noqa: E402
from protacxtend.agents.warhead_agent import WarheadSelectionAgent  # noqa: E402
from protacxtend.agents.e3_agent import E3LigandSelectionAgent  # noqa: E402
from protacxtend.backend.schemas import ParsedObjective, WorkflowState  # noqa: E402


def _state(target: str = "BRD4", e3: str = "VHL") -> WorkflowState:
    state = WorkflowState(user_request=f"degrade {target}")
    state.parsed_objective = ParsedObjective(target_name=target, e3_ligase=e3)
    return state


def _fake_engine_state(warhead_source: str) -> dict:
    return {
        "parsed_objective": {"target_name": "BRD4", "e3": "VHL"},
        "target_record": {"target_name": "BRD4", "uniprot_id": "O60885", "structures": ["2OSS"]},
        "retrieved_binders": [{"name": "JQ1", "smiles": "CC1", "source": warhead_source}],
        "selected_e3_ligands": [{"e3_ligase": "VHL", "name": "VH032"}],
        "selected_warheads": [{"name": "JQ1", "smiles": "CC1", "source": warhead_source}],
        "generated_linkers": [{"name": "PEG3", "smiles": "[*:1]CCOCC[*:2]"}],
        "assembled_candidates": [{"candidate_id": "c1", "full_protac_smiles": "CC1CCOCC"}],
        "valid_candidates": [{"candidate_id": "c1", "full_protac_smiles": "CC1CCOCC"}],
        "novelty_results": [{"candidate_id": "c1", "is_novel": True}],
        "degradation_predictions": [
            {"candidate_id": "c1", "log_dc50": 2.1, "dmax": 0.8, "model_version": "chemprop-v1"}
        ],
        "admet_predictions": [{"candidate_id": "c1", "overall_admet_penalty": 0.2}],
        "applicability_domain_results": [{"domain_status": "in_domain"}],
        "final_ranked_candidates": [
            {"candidate_id": "c1", "full_protac_smiles": "CC1CCOCC", "final_priority_score": 0.9}
        ],
    }


# ── F-03: demo rows are mode-gated at the data layer ──────────────────

def test_scientific_curated_warheads_drop_demo_rows():
    with modes.execution_mode("scientific"):
        rows = ProtacDesignToolbox().load_curated_warheads()
    assert rows == []
    assert not any(modes.is_demo_source(r.get("source")) for r in rows)


def test_demo_curated_warheads_keep_demo_rows():
    with modes.execution_mode("demo"):
        rows = ProtacDesignToolbox().load_curated_warheads()
    assert rows
    assert any(modes.is_demo_source(r.get("source")) for r in rows)


def test_scientific_e3_ligands_are_source_backed():
    with modes.execution_mode("scientific"):
        rows = ProtacDesignToolbox().load_curated_e3_ligands()
    assert rows
    assert not any(modes.is_demo_source(r.get("source")) for r in rows)


def test_scientific_warhead_agent_abstains_for_brd4():
    with modes.execution_mode("scientific"):
        state = _state("BRD4")
        WarheadSelectionAgent().run(state)
    assert state.selected_warheads == []
    assert any("No warheads selected" in e for e in state.errors)


def test_scientific_e3_agent_uses_real_ligands():
    with modes.execution_mode("scientific"):
        state = _state("BRD4", "VHL")
        E3LigandSelectionAgent().run(state)
    assert state.selected_e3_ligands
    assert all(not modes.is_demo_source(l.source) for l in state.selected_e3_ligands)


def test_demo_warhead_agent_still_selects_demo_warheads():
    state = _state("BRD4")
    WarheadSelectionAgent().run(state)
    assert state.selected_warheads
    assert any(modes.is_demo_source(w.source) for w in state.selected_warheads)


# ── F-03: canonical path records mode and drops leaked demo warheads ──

def test_scientific_strategy_records_execution_mode():
    with modes.execution_mode("scientific"):
        result = CanonicalOrchestrator().review_engine_state(
            "Design a VHL PROTAC against BRD4",
            _fake_engine_state("local_demo_jq1_like_warhead"),
            run_id="gateb-mode",
        )
    assert result.strategy.execution_mode == "scientific"
    assert result.strategy.run_manifest.execution_mode == "scientific"


def test_scientific_strategy_drops_demo_warheads_from_engine_state():
    with modes.execution_mode("scientific"):
        result = CanonicalOrchestrator().review_engine_state(
            "Design a VHL PROTAC against BRD4",
            _fake_engine_state("local_demo_jq1_like_warhead"),
            run_id="gateb-drop",
        )
    assert result.strategy.warheads == []
    assert any("demo-sourced warhead" in w for w in result.strategy.warnings)


def test_demo_strategy_keeps_demo_warheads():
    with modes.execution_mode("demo"):
        result = CanonicalOrchestrator().review_engine_state(
            "Design a VHL PROTAC against BRD4",
            _fake_engine_state("local_demo_jq1_like_warhead"),
            run_id="gateb-demo",
        )
    assert result.strategy.execution_mode == "demo"
    assert result.strategy.warheads


# ── F-04: reviewed protein identity ───────────────────────────────────

def test_target_resolver_prefers_curated_reviewed_accession():
    from protacxtend.agents.target_agent import TargetResolverAgent

    state = _state("BRD4")
    TargetResolverAgent().run(state)
    record = state.target_record
    assert record is not None
    assert record.uniprot_id == "O60885"
    assert record.uniprot_id != "M0QZD9"
    assert record.organism.lower().startswith("human")
    assert "2OSS" in record.structures
    assert record.external_ids.get("uniprot_tier") == "curated"
    assert record.known_binder_count > 0


def test_target_resolver_unknown_gene_does_not_crash(monkeypatch):
    from protacxtend.agents import target_agent
    from protacxtend.agents.target_agent import TargetResolverAgent

    agent = TargetResolverAgent()
    monkeypatch.setattr(agent, "_from_uniprot_client", lambda *a, **k: None)
    monkeypatch.setattr(agent, "_from_raw_uniprot", lambda *a, **k: None)
    state = _state("ZZZNOTAGENE")
    agent.run(state)
    assert state.target_record is None
    assert any("Could not resolve" in e for e in state.errors)

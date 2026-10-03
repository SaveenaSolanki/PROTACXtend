from __future__ import annotations

import urllib.error

from protacxtend.agents.binder_agent import TargetBinderRetrievalAgent
from protacxtend.backend.schemas import BinderRecord, ParsedObjective, TargetRecord, WorkflowState
from protacxtend.runtime.modes import RetrievalDeadlineExceeded


def _state() -> WorkflowState:
    state = WorkflowState(user_request="retrieve BRD4 binders")
    state.parsed_objective = ParsedObjective(target_name="BRD4")
    state.target_record = TargetRecord(target_name="BRD4", gene_symbol="BRD4", uniprot_id="O60885")
    return state


def _binder(name: str = "JQ1") -> BinderRecord:
    return BinderRecord(
        name=name,
        target="BRD4",
        smiles="COc1cc2c(cc1c1c(C)onc1C)cc(c(=O)n2Cc1ccccn1)",
        p_activity=8.0,
        source="test_source",
        metadata={"evidence_type": "measured_activity"},
    )


def _patch_fallbacks(monkeypatch, agent: TargetBinderRetrievalAgent, cited=None, local=None):
    monkeypatch.setattr(agent, "_load_cited_local_binders", lambda *args: list(cited or []))
    monkeypatch.setattr(agent, "_load_local_binders", lambda *args: list(local or []))


def test_normal_retrieval_records_success_telemetry(monkeypatch):
    agent = TargetBinderRetrievalAgent()
    monkeypatch.setattr(agent, "_search_chembl", lambda *args: ([_binder()], True))
    monkeypatch.setattr(agent, "_enrich_from_pubchem", lambda binders: ([], False))
    monkeypatch.setattr(agent, "_search_bindingdb", lambda *args: ([], False))
    _patch_fallbacks(monkeypatch, agent)

    state = agent._execute(_state())

    assert state.retrieved_binders
    assert state.execution_status == "SUCCESS"
    assert state.evidence_status == "VERIFIED_BINDER_FOUND"
    assert state.answer_status == "ANSWERABLE"
    chembl = next(row for row in state.retrieval_telemetry if row["source"] == "ChEMBL")
    assert chembl["final_status"] == "SUCCESS"
    assert chembl["records_returned"] == 1


def test_single_source_timeout_allows_partial_success(monkeypatch):
    agent = TargetBinderRetrievalAgent()
    monkeypatch.setattr(agent, "_search_chembl", lambda *args: (_ for _ in ()).throw(RetrievalDeadlineExceeded("slow")))
    monkeypatch.setattr(agent, "_search_bindingdb", lambda *args: ([_binder("BDB")], True))
    _patch_fallbacks(monkeypatch, agent)

    state = agent._execute(_state())

    assert state.retrieved_binders
    assert state.execution_status == "PARTIAL_SUCCESS"
    assert state.evidence_status == "VERIFIED_BINDER_FOUND"
    assert state.answer_status == "ANSWERABLE"
    statuses = {row["source"]: row["final_status"] for row in state.retrieval_telemetry}
    assert statuses["ChEMBL"] == "SOURCE_TIMEOUT"
    assert statuses["BindingDB"] == "SUCCESS"


def test_all_source_timeout_is_undetermined_not_no_binder(monkeypatch):
    agent = TargetBinderRetrievalAgent()
    monkeypatch.setattr(agent, "_search_chembl", lambda *args: (_ for _ in ()).throw(RetrievalDeadlineExceeded("slow")))
    monkeypatch.setattr(agent, "_search_bindingdb", lambda *args: (_ for _ in ()).throw(RetrievalDeadlineExceeded("slow")))
    _patch_fallbacks(monkeypatch, agent)

    state = agent._execute(_state())

    assert state.retrieved_binders == []
    assert state.execution_status == "SOURCE_TIMEOUT"
    assert state.evidence_status == "UNDETERMINED"
    assert state.answer_status == "ABSTAIN"
    assert state.retrieval_status != "empty"


def test_cache_fallback_records_fallback_success(monkeypatch):
    agent = TargetBinderRetrievalAgent()
    monkeypatch.setattr(agent, "_search_chembl", lambda *args: (_ for _ in ()).throw(urllib.error.URLError("down")))
    monkeypatch.setattr(agent, "_search_bindingdb", lambda *args: ([], False))
    _patch_fallbacks(monkeypatch, agent, cited=[_binder("cited")])

    state = agent._execute(_state())

    assert state.retrieved_binders
    assert state.execution_status == "PARTIAL_SUCCESS"
    assert any(row["fallback_used"] == "citation_tagged_local_warhead_db" for row in state.retrieval_telemetry)


def test_rate_limit_fallback_is_typed(monkeypatch):
    agent = TargetBinderRetrievalAgent()
    err = urllib.error.HTTPError("https://chembl", 429, "rate", {}, None)
    monkeypatch.setattr(agent, "_search_chembl", lambda *args: (_ for _ in ()).throw(err))
    monkeypatch.setattr(agent, "_search_bindingdb", lambda *args: ([], False))
    _patch_fallbacks(monkeypatch, agent)

    state = agent._execute(_state())

    assert state.execution_status == "SOURCE_RATE_LIMITED"
    assert state.evidence_status == "UNDETERMINED"
    assert state.answer_status == "ABSTAIN"
    assert any(row["final_status"] == "SOURCE_RATE_LIMITED" for row in state.retrieval_telemetry)


def test_empty_source_becomes_no_verified_binder_only_when_sources_work(monkeypatch):
    agent = TargetBinderRetrievalAgent()
    monkeypatch.setattr(agent, "_search_chembl", lambda *args: ([], False))
    monkeypatch.setattr(agent, "_search_bindingdb", lambda *args: ([], False))
    _patch_fallbacks(monkeypatch, agent)

    state = agent._execute(_state())

    assert state.execution_status == "NO_VERIFIED_BINDER"
    assert state.evidence_status == "NO_VERIFIED_BINDER"
    assert state.answer_status == "ABSTAIN"
    assert all(row["final_status"] == "SOURCE_EMPTY" for row in state.retrieval_telemetry)


def test_network_unavailable_is_not_no_binder(monkeypatch):
    agent = TargetBinderRetrievalAgent()
    monkeypatch.setattr(agent, "_search_chembl", lambda *args: (_ for _ in ()).throw(urllib.error.URLError("dns")))
    monkeypatch.setattr(agent, "_search_bindingdb", lambda *args: (_ for _ in ()).throw(OSError("offline")))
    _patch_fallbacks(monkeypatch, agent)

    state = agent._execute(_state())

    assert state.execution_status == "SOURCE_UNAVAILABLE"
    assert state.evidence_status == "UNDETERMINED"
    assert state.answer_status == "ABSTAIN"
    assert state.retrieval_status != "empty"

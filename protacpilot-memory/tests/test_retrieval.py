"""Hybrid retrieval, explainability, progressive disclosure, feedback."""

from __future__ import annotations

from helpers import brd4_vhl, ev


def _add(mem, project, context, target_tag, dmax=0.3):
    return mem.save_episode(
        title=f"linker flexibility dmax {target_tag}",
        content="flexible PEG linker dmax observation",
        event_type="degradation_assay", project_id=project, context=context,
        observed={"dmax": dmax}, evidence=[ev(f"R-{target_tag}")], decision_impact=0.8,
    )["episode_id"]


def test_context_discrimination_ranks_correct_target_first(mem, project):
    brd4_id = _add(mem, project, brd4_vhl(), "brd4")
    brd2_id = _add(mem, project, brd4_vhl(target_gene="BRD2"), "brd2")
    crbn_id = _add(mem, project, brd4_vhl(e3_ligase="CRBN"), "crbn")
    resp = mem.search("linker flexibility dmax", project_id=project, context=brd4_vhl(), limit=5)
    ranked = resp.ids()
    assert ranked[0] == brd4_id
    assert ranked.index(brd4_id) < ranked.index(brd2_id)
    assert ranked.index(brd4_id) < ranked.index(crbn_id)


def test_retrieval_is_explainable(mem, project):
    mem.save_episode(
        title="BRD4 VHL dmax observation", content="dmax low with rigid linker",
        event_type="degradation_assay", project_id=project, context=brd4_vhl(),
        observed={"dmax": 0.2}, evidence=[ev("X-1")], decision_impact=0.8,
    )
    resp = mem.search("BRD4 rigid linker dmax", project_id=project, context=brd4_vhl())
    assert resp.hits
    top = resp.hits[0]
    assert top.why_retrieved
    assert "context" in top.components and "lexical" in top.components
    assert top.matched_entities or top.matched_context


def test_progressive_layers(mem, project):
    episode_id = _add(mem, project, brd4_vhl(), "prog")
    compact = mem.retriever.progressive.compact(mem.store.require_trace(episode_id))
    assert compact["id"] == episode_id and "preview" in compact
    packet = mem.packet(episode_id)
    assert "OBSERVATION" in packet and "INTERPRETATION" in packet
    raw = mem.evidence(episode_id)
    assert "evidence_items" in raw and raw["evidence_items"]
    timeline = mem.timeline(episode_id)
    assert "anchor" in timeline


def test_use_dependent_strengthening(mem, project):
    episode_id = _add(mem, project, brd4_vhl(), "fb")
    resp = mem.search("linker flexibility dmax fb", project_id=project, context=brd4_vhl())
    assert episode_id in resp.ids()
    result = mem.feedback(episode_id, useful=True, used_for="accepted recommendation")
    assert result["memory_strength"] > 0
    trace = mem.store.require_trace(episode_id)
    assert trace["successful_retrieval_count"] == 1
    assert trace["retrieval_count"] >= 1


def test_irrelevant_retrieval_does_not_strengthen(mem, project):
    episode_id = _add(mem, project, brd4_vhl(), "irr")
    mem.search("unrelated query about synthesis routes", project_id=project)
    mem.feedback(episode_id, useful=False)
    trace = mem.store.require_trace(episode_id)
    assert trace["successful_retrieval_count"] == 0


def test_semantic_backend_is_optional_and_labelled(mem, project):
    resp = mem.search("anything", project_id=project)
    assert resp.semantic_backend == "disabled"

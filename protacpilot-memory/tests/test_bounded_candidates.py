"""Bounded candidate generation (brief §4/§5)."""

from __future__ import annotations

from dataclasses import replace

from protacpilot_memory import CognitiveMemory
from protacpilot_memory.config import CandidateConfig, MemoryConfig
from protacpilot_memory.domain.protac import ProtacContext, detect_entities, entity_search_text
from protacpilot_memory.retrieval.candidates import CandidateGenerator, contexts_for_memories


def _store_episode(mem, project, *, title, context, entities=True):
    ctx = ProtacContext.from_dict(context)
    trace_id = mem.store.add_episode(
        title=title, content=title, event_type="degradation_assay",
        project_id=project, context=context, context_fingerprint=ctx.fingerprint(),
        search_entities=entity_search_text(detect_entities(ctx)) if entities else None,
    )
    if entities:
        for ref in detect_entities(ctx):
            mem.store.link_memory_entity(trace_id, ref)
    return trace_id


def test_contexts_for_memories_loads_episodic_context(mem, project):
    memory_id = _store_episode(
        mem, project,
        title="BRD4 assay",
        context=ProtacContext(target_gene="BRD4", e3_ligase="VHL").to_dict(),
    )
    contexts = contexts_for_memories(mem.store, [memory_id])
    assert contexts[memory_id]["target_gene"] == "BRD4"


def test_bounded_generation_is_project_scoped(mem):
    project_a = mem.ensure_project("alpha")
    project_b = mem.ensure_project("beta")
    for project in (project_a, project_b):
        for i in range(3):
            _store_episode(
                mem, project, title=f"BRD4 VHL episode {i}",
                context=ProtacContext(target_gene="BRD4", e3_ligase="VHL").to_dict(),
            )
    generator = CandidateGenerator(mem.store, replace(MemoryConfig(), candidates=CandidateConfig()))
    bounded = generator.build(
        lexical={}, entity_names={"BRD4", "VHL"},
        query_context=ProtacContext(target_gene="BRD4", e3_ligase="VHL").to_dict(),
        project_id=project_a, limit=5,
    )
    assert bounded.entity, "no entity candidates kept"
    allowed = set(mem.store.project_memory_ids(project_a))
    assert set(bounded.entity) <= allowed

    legacy = generator.build_unbounded(
        lexical={}, entity_names={"BRD4", "VHL"}, project_id=project_a,
    )
    assert len(legacy.entity) > len(bounded.entity), "legacy expansion should be larger"


def test_context_gate_drops_entity_only_non_overlapping(mem):
    project = mem.ensure_project("gate")
    # Candidate linked to the BRD4 entity but whose context defines only a cell
    # that conflicts with the query cell and shares no query coordinate.
    from protacpilot_memory.domain.protac.normalization import make_entity_ref

    trace_id = _store_episode(
        mem, project, title="unrelated BRD4-linked note",
        context=ProtacContext(cell_line="MV4-11").to_dict(),
    )
    ref = make_entity_ref("Target", "BRD4", "target")
    assert ref is not None
    mem.store.link_memory_entity(trace_id, ref)
    generator = CandidateGenerator(
        mem.store, replace(MemoryConfig(), candidates=CandidateConfig(context_gate=True, max_entity_candidates=10))
    )
    query_context = ProtacContext(target_gene="BRD4", e3_ligase="VHL", cell_line="HEK293").to_dict()
    bounded = generator.build(
        lexical={}, entity_names={"BRD4"}, query_context=query_context,
        project_id=project, limit=5,
    )
    assert bounded.entity_gated >= 1
    assert not bounded.entity


def test_metadata_of_generic_relation_is_ignored_when_missing():
    """A response with no entity names must not raise."""
    mem = CognitiveMemory.in_memory()
    try:
        project = mem.ensure_project("empty")
        generator = CandidateGenerator(mem.store)
        bounded = generator.build(
            lexical={}, entity_names=set(), query_context=None, project_id=project, limit=5,
        )
        assert bounded.entity == {} and bounded.entity_total == 0
    finally:
        mem.close()


def test_bounded_candidates_benchmark_quick_run():
    from benchmarks import bounded_candidates as B

    results = B.run_all(n_total=160, n_gold=4, n_distractors=20, n_decoy=20, k=5)
    before = results["conditions"]["before_unbounded"]["aggregate"]
    after = results["conditions"]["after_bounded"]["aggregate"]
    assert after["mean_candidate_kept"] <= 60
    assert before["mean_candidate_kept"] >= after["mean_candidate_kept"]
    # bounding must not destroy ranking quality
    assert after["recall@k"] >= before["recall@k"] - 1e-9
    assert results["delta"]["mean_latency_ms"] <= 0.0 or after["mean_latency_ms"] < 200

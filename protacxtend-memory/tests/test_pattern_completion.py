"""Pattern-completion tests (Sprint V4 / Master Prompt §15).

These test whether cue-driven associative reconstruction recovers the *correct
scientific path*, not merely that the function returns a non-empty structure.

The canonical chain under test:

    design decision (BRD4/VHL, short PEG L7)
        -> docking ternary prediction (P17)
        -> EXP-142 outcome (poor degradation)
        -> redesign decision (replace L7)
"""

from __future__ import annotations

import pytest
from protacpilot_memory.domain.protac import ProtacContext


def _ctx(**overrides):
    base = dict(target_gene="BRD4", target_domain="BD2", e3_ligase="VHL", cell_line="HEK293",
                assay_type="degradation assay", linker_type="PEG", compound_id="P17")
    base.update(overrides)
    return ProtacContext(**base)


@pytest.fixture
def chain(mem, project):
    """Build the BRD4/VHL/P17 chain plus a CRBN branch and a disconnected memory."""
    ids: dict[str, str] = {}

    ids["design"] = mem.save_episode(
        title="Design decision: short PEG linker L7 for P17",
        content="Chose short PEG linker L7 for P17 to improve permeability.",
        event_type="design_choice", project_id=project, context=_ctx(),
        evidence=[{"evidence_type": "user_assertion", "experiment_id": "DES-1"}],
        decision_impact=0.95, goal_relevance=0.95,
    )["episode_id"]
    ids["docking"] = mem.save_episode(
        title="Ternary docking prediction for P17 with VHL",
        content="Docking predicts non-productive ternary geometry for the short PEG exit vector.",
        event_type="docking_experiment", project_id=project, context=_ctx(),
        observed={"ternary_complex_score": 0.21},
        evidence=[{"evidence_type": "docking", "experiment_id": "DOCK-77"}],
        interpretation="short PEG geometry is non-productive", decision_impact=0.8,
        goal_relevance=0.7,
    )["episode_id"]
    ids["outcome"] = mem.save_episode(
        title="EXP-142: P17 poor degradation dmax 18%",
        content="P17 degradation assay showed dmax 18 percent with VHL in HEK293.",
        event_type="degradation_assay", project_id=project, context=_ctx(),
        observed={"dmax": 0.18},
        evidence=[{"evidence_type": "internal_experiment", "experiment_id": "EXP-142"}],
        interpretation="short PEG linker is non-productive",
        is_negative=True, decision_impact=0.95, goal_relevance=0.9,
    )["episode_id"]
    ids["redesign"] = mem.save_episode(
        title="Redesign decision: replace short PEG L7 with rigid exit vector",
        content="Replace L7 with a rigid alternative exit-vector linker; advance P34.",
        event_type="design_choice", project_id=project,
        context=_ctx(linker_type="rigid", compound_id="P34"),
        evidence=[{"evidence_type": "user_assertion", "experiment_id": "DES-2"}],
        decision_impact=0.95, goal_relevance=0.95,
    )["episode_id"]

    # explicit scientific relations forming the chain
    mem.compare(ids["docking"], ids["design"], "refines", rationale="docking refines the design hypothesis")
    mem.compare(ids["outcome"], ids["docking"], "predicted", rationale="docking predicted the outcome")
    mem.compare(ids["redesign"], ids["outcome"], "caused_decision", rationale="failure drove the redesign")

    # CRBN branch: same compound, different E3
    ids["crbn"] = mem.save_episode(
        title="P17 with CRBN shows moderate degradation dmax 55%",
        content="A CRBN-recruiting P17 analogue degraded moderately in HEK293.",
        event_type="degradation_assay", project_id=project, context=_ctx(e3_ligase="CRBN"),
        observed={"dmax": 0.55},
        evidence=[{"evidence_type": "internal_experiment", "experiment_id": "EXP-200"}],
        decision_impact=0.6,
    )["episode_id"]

    # same compound, different cell background
    ids["mv411"] = mem.save_episode(
        title="P17 in MV4-11 shows high degradation dmax 71%",
        content="In MV4-11, P17 degraded well (dmax 71 percent), context-dependent.",
        event_type="degradation_assay", project_id=project, context=_ctx(cell_line="MV4-11"),
        observed={"dmax": 0.71},
        evidence=[{"evidence_type": "internal_experiment", "experiment_id": "EXP-201"}],
        decision_impact=0.8,
    )["episode_id"]

    # disconnected memory (no relations, distinct topic)
    ids["orphan"] = mem.save_episode(
        title="Unrelated kinase selectivity note for compound Z9",
        content="Compound Z9 shows off-target kinase selectivity that needs follow-up.",
        event_type="paper_observation", project_id=project,
        context=ProtacContext(target_gene="EGFR", compound_id="Z9"),
        evidence=[{"evidence_type": "peer_reviewed_publication", "doi": "10.1/orphan"}],
        decision_impact=0.5,
    )["episode_id"]

    # conflicting branch: an alternative redesign that contradicts the first
    ids["redesign2"] = mem.save_episode(
        title="Alternative redesign: retain L7 but increase linker length",
        content="An alternative proposes lengthening L7 rather than replacing it with a rigid vector.",
        event_type="design_choice", project_id=project, context=_ctx(linker_type="PEG-long"),
        observed={"linker_length": 12},
        evidence=[{"evidence_type": "structural_observation", "experiment_id": "DES-3"}],
        decision_impact=0.9, goal_relevance=0.9,
    )["episode_id"]
    mem.compare(ids["redesign2"], ids["redesign"], "contradicts",
                rationale="competing remedies for the same failure")

    assert all(ids.values()), {k: v for k, v in ids.items() if not v}
    return ids


def _node_ids(result):
    return {n["id"] for n in result["nodes"]}


def _edge_set(result):
    return {(e["source"], e["target"], e["relation"]) for e in result["edges"]}


def _edge_set_undirected(result):
    out = set()
    for e in result["edges"]:
        out.add((e["source"], e["target"], e["relation"]))
        out.add((e["target"], e["source"], e["relation"]))
    return out


def test_partial_cue_reconstructs_chain(mem, project, chain):
    result = mem.pattern_complete("BRD4 P17 short PEG linker degradation", project_id=project, depth=2)
    ids = _node_ids(result)
    # the core scientific path must be reconstructed
    assert chain["design"] in ids
    assert chain["docking"] in ids
    assert chain["outcome"] in ids
    assert chain["redesign"] in ids


def test_reconstruction_contains_the_causal_edges(mem, project, chain):
    result = mem.pattern_complete("BRD4 P17 linker degradation", project_id=project, depth=3)
    edges = _edge_set(result)
    # edges may be traversed in either direction
    assert (chain["outcome"], chain["docking"], "predicted") in edges
    assert (chain["redesign"], chain["outcome"], "caused_decision") in edges
    assert (chain["docking"], chain["design"], "refines") in edges


def test_narrative_is_traceable(mem, project, chain):
    result = mem.pattern_complete("BRD4 P17 poor degradation", project_id=project, depth=2)
    narrative = "\n".join(result["narrative"])
    assert "EXP-142" in narrative
    assert "Redesign" in narrative
    # every chain node id in the narrative must exist in the node set
    for node in result["chain"]:
        assert node["id"] in _node_ids(result)


def test_incorrect_e3_cue_ranks_the_correct_e3_first(mem, project, chain):
    result = mem.pattern_complete("P17 CRBN degradation", project_id=project, depth=2)
    ids = _node_ids(result)
    assert chain["crbn"] in ids
    # the CRBN memory is the primary (top-ranked) seed, not the VHL outcome
    top = result["nodes"][0]
    assert top["id"] == chain["crbn"]
    assert top["role"] == "seed"


def test_same_compound_different_context_stay_distinct(mem, project, chain):
    result = mem.pattern_complete("P17 degradation HEK293 MV4-11", project_id=project, depth=1)
    ids = _node_ids(result)
    assert chain["outcome"] in ids
    assert chain["mv411"] in ids
    assert chain["outcome"] != chain["mv411"]
    # both are present as separate nodes with their own status/type
    types = {n["id"]: n["type"] for n in result["nodes"]}
    assert types[chain["outcome"]] == "negative"
    assert types[chain["mv411"]] == "episodic"


def test_disconnected_memory_yields_no_phantom_edges(mem, project, chain):
    result = mem.pattern_complete("Z9 off-target kinase selectivity", project_id=project, depth=2)
    ids = _node_ids(result)
    assert chain["orphan"] in ids
    # the orphan has no relations, so it must not be linked to the BRD4 chain
    edges = _edge_set_undirected(result)
    assert not any(chain["orphan"] in (s, t) for s, t, _ in edges)


def test_conflicting_branch_surfaces_both_sides(mem, project, chain):
    result = mem.pattern_complete("redesign linker P17 failure", project_id=project, depth=2)
    ids = _node_ids(result)
    assert chain["redesign"] in ids
    assert chain["redesign2"] in ids
    edges = _edge_set_undirected(result)
    assert (chain["redesign"], chain["redesign2"], "contradicts") in edges


def test_chain_is_chronological(mem, project, chain):
    result = mem.pattern_complete("BRD4 P17 ternary degradation", project_id=project, depth=2)
    created = [(n.get("created_at") or "", n["id"]) for n in result["chain"]]
    assert created == sorted(created)

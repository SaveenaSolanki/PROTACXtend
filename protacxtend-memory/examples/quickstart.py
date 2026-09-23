"""Runnable end-to-end example for PROTACpilot Cognitive Memory.

    cd protacpilot-memory
    PYTHONPATH=src python examples/quickstart.py
"""

from __future__ import annotations

from protacpilot_memory import CognitiveMemory
from protacpilot_memory.domain.protac import ProtacContext
from protacpilot_memory.domain.protac.evidence import EvidenceRef


def main() -> None:
    mem = CognitiveMemory.open("./quickstart.db")
    project = mem.ensure_project("brd4-vhl", "BRD4/VHL linker optimization")
    session = mem.start_session(project, goal="Improve permeability while retaining BRD4 degradation")
    mem.remember_working(session, "current_target", "BRD4", project_id=project, goal_relevance=0.95)

    ctx = ProtacContext(
        target_gene="BRD4", target_domain="BD2", e3_ligase="VHL",
        cell_line="HEK293", assay_type="degradation assay",
        linker_type="PEG", compound_id="P17",
    )

    # 1. Prediction stored before the outcome exists.
    prediction = mem.predict(
        project_id=project, session_id=session, candidate_id="P17",
        metric="dmax", predicted_value=0.89, confidence=0.78, scale=1.0,
        context=ctx, assumptions=["rigid linker preserves ternary geometry"],
    )

    # 2. Outcome recorded -> deterministic prediction error -> episodic memory.
    outcome = mem.record_outcome(
        prediction, observed_value=0.22, evidence_type="internal_experiment",
        experiment_id="EXP-119", project_id=project, session_id=session,
    )
    print(f"prediction error: {outcome['prediction_error']:.2f} ({outcome['error_method']})")
    print(f"encoded episode : {outcome['episode']['episode_id']} "
          f"(surprise={outcome['episode']['surprise']:.2f})")

    # 3. Replicated experiments.
    for i, value in enumerate([0.18, 0.25, 0.21]):
        mem.save_episode(
            title=f"BRD4/VHL PEG linker replicate {i}",
            content=f"short PEG linker architecture; observed dmax={value}",
            event_type="degradation_assay", project_id=project, session_id=session,
            context=ctx, observed={"dmax": value},
            interpretation="short PEG linker geometry reduces productive ternary complex",
            evidence=[EvidenceRef(evidence_type="internal_experiment", experiment_id=f"EXP-12{i}")],
            decision_impact=0.8,
        )

    # 4. Consolidate into a scoped, provisional semantic claim.
    report = mem.consolidate(project)
    for created in report["created"]:
        print(f"\nsemantic {created['semantic_id']} (conf={created['confidence']:.2f})")
        print(created["claim"])

    # 5. Retrieve with a hybrid, explainable search.
    hits = mem.search("BRD4 VHL linker flexibility dmax", project_id=project, context=ctx)
    print("\ntop hits:")
    for hit in hits.hits[:3]:
        print(f"  {hit.id} [{hit.memory['memory_type']}] score={hit.score:.3f} "
              f"why={hit.why_retrieved}")

    # 6. Counterfactual analysis of the failed prediction (separate artifact).
    analysis = mem.counterfactual(prediction, project_id=project)
    print(f"\ncounterfactual: {analysis['questionable_assumption']}")

    # 7. End-of-session cognitive handoff.
    handoff = mem.end_session(session, next_steps=["Test an alternative exit vector/linker geometry"])
    print(f"\nhandoff: {handoff['handoff']}")

    # 8. Audit.
    audit = mem.audit(project)
    print(f"\naudit severity: {audit['severity']} {audit['summary']}")
    mem.close()


if __name__ == "__main__":
    main()

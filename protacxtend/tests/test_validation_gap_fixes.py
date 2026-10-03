"""Regressions for the validation_gap_v1 failure modes.

Root causes found by auditing v1 (48-row run at
``benchmark_results/validation_gap_v1``):

1. 35/48 cases aborted at ``resolve_target`` with
   "TargetResolverAgent: No target name provided." because that message was a
   terminal stop for every capability. KNOW/REASON/DISCOVER cases and DESIGN
   cases that supply their own components do not need a resolved UniProt target,
   so the stop is now capability-aware. A *provided but unresolvable* target
   must still abort (fail closed).
2. DISCOVER cases that produced no answer and no evidence were labelled
   ``conditional_hypothesis`` / ``completed`` — an unsupported continuation.
   They are now ``unresolved`` / ``abstained``.
"""

from __future__ import annotations

import unittest

from protacxtend.agents.graph import LocalSynGlueWorkflowGraph
from protacxtend.agents.scientific_states import ScientificState
from protacxtend.agents.structured_run import _scientific_state
from protacxtend.backend.schemas import WorkflowState


def _state(capability: str, *, answer=None, evidence=None, error=None) -> WorkflowState:
    st = WorkflowState()
    st.design_plan["structured_seed"] = {"capability": capability}
    st.scientific_answer = {"answer": answer or "", "evidence": evidence or []}
    if error:
        st.errors.append(error)
    return st


class TerminalStopTests(unittest.TestCase):
    def test_no_target_name_does_not_stop_know_reason_discover(self) -> None:
        graph = LocalSynGlueWorkflowGraph()
        for cap in ("KNOW", "REASON", "DISCOVER"):
            st = _state(cap, error="TargetResolverAgent: No target name provided.")
            self.assertFalse(graph._should_stop(st), f"{cap} should continue")

    def test_design_fails_closed_on_unresolvable_target(self) -> None:
        graph = LocalSynGlueWorkflowGraph()
        st = _state("DESIGN", error="TargetResolverAgent: Could not resolve 'BRD' to a reviewed UniProt entry.")
        self.assertTrue(graph._should_stop(st))

    def test_know_reason_discover_continue_on_unresolvable_target(self) -> None:
        # These capabilities can still answer/abstain via the answer agent when
        # a target is named but not resolvable; the answer agent owns abstention.
        graph = LocalSynGlueWorkflowGraph()
        for cap in ("KNOW", "REASON", "DISCOVER"):
            st = _state(cap, error="TargetResolverAgent: Could not resolve 'BRD' to a reviewed UniProt entry.")
            self.assertFalse(graph._should_stop(st), cap)

    def test_supplied_components_do_not_stop_design(self) -> None:
        graph = LocalSynGlueWorkflowGraph()
        st = _state("DESIGN", error="TargetResolverAgent: No target name provided.")
        st.design_plan["structured_seed"]["warhead_supplied"] = True
        self.assertFalse(graph._should_stop(st))


class EmptyAnswerStateTests(unittest.TestCase):
    def test_empty_answer_no_evidence_is_unresolved(self) -> None:
        st = _state("DISCOVER")
        state = _scientific_state("DISCOVER", st, [], abstained=False, entities={})
        self.assertEqual(state, ScientificState.UNRESOLVED)

    def test_answered_hypothesis_is_still_conditional(self) -> None:
        st = _state("DISCOVER", answer="Ranking requires the supplied table.")
        state = _scientific_state("DISCOVER", st, [], abstained=False, entities={})
        self.assertEqual(state, ScientificState.CONDITIONAL_HYPOTHESIS)

    def test_design_brief_is_not_unresolved(self) -> None:
        st = _state("DESIGN")
        state = _scientific_state("DESIGN", st, [], abstained=False, entities={})
        self.assertEqual(state, ScientificState.JUSTIFIED_NO_GO)  # no brief flag -> no-go


class EvidencePropagationTests(unittest.TestCase):
    def test_tool_errors_are_not_evidence(self) -> None:
        from protacxtend.agents.structured_run import _sourced_evidence

        items = [
            {"tool": "predict_cell_context", "error": "MissingScientificInput"},
            {"kind": "retrieved", "source": "uniprot/curated", "summary": "BRD4 -> O60885"},
            {"source": "e3_registry", "summary": "CRBN"},
            "not-a-dict",
            {},
        ]
        kept = _sourced_evidence(items)
        self.assertEqual(len(kept), 2)
        self.assertTrue(all("error" not in e for e in kept))


if __name__ == "__main__":
    unittest.main()

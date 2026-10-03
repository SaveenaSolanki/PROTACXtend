"""Guards against silent target mis-resolution and empty-binder counting.

Regression evidence (run_e4e21ccd): the request "BRD$-VHL" parsed to target
"BRD"; the resolver accepted the first UniProt full-text hit for "BRD", which
is RLBP1 (P12271, Retinaldehyde-binding protein 1) — not BRD4 (O60885). The
run then built BRD4 warheads while labelling every candidate target "RLBP1".
"""

from __future__ import annotations

import logging
import unittest

from protacxtend.agents.graph import LocalSynGlueWorkflowGraph
from protacxtend.agents.target_agent import TargetResolverAgent, query_matches_hit
from protacxtend.backend.schemas import BinderRecord, TargetRecord, WorkflowState
from protacxtend.run_records import build_agent_run_record


class QueryMatchGuardTests(unittest.TestCase):
    def test_short_token_does_not_match_unrelated_protein(self) -> None:
        # The exact production failure: "BRD" must not resolve to RLBP1.
        self.assertFalse(query_matches_hit(
            "BRD", ["RLBP1", "Retinaldehyde-binding protein 1", "CRALBP"]))

    def test_short_token_does_not_match_prefix_of_gene(self) -> None:
        self.assertFalse(query_matches_hit(
            "BRD", ["BRD4", "Bromodomain-containing protein 4"]))

    def test_exact_gene_and_name_resolve(self) -> None:
        self.assertTrue(query_matches_hit(
            "BRD4", ["BRD4", "Bromodomain-containing protein 4", "HUNK1"]))
        self.assertTrue(query_matches_hit(
            "Bromodomain-containing protein 4",
            ["BRD4", "Bromodomain-containing protein 4"]))

    def test_empty_query_never_matches(self) -> None:
        self.assertFalse(query_matches_hit("", ["BRD4"]))


class TargetResolverAbstainsOnMismatchTests(unittest.TestCase):
    def setUp(self) -> None:
        logging.disable(logging.WARNING)
        self.agent = TargetResolverAgent()

    def tearDown(self) -> None:
        logging.disable(logging.NOTSET)

    def _patch(self, record):
        import protacxtend.backend.uniprot_client as uc

        original = uc.resolve_target_via_uniprot
        uc.resolve_target_via_uniprot = lambda query, **kw: (record, {"source_url": "test"})
        self.addCleanup(setattr, uc, "resolve_target_via_uniprot", original)

    def test_mismatched_hit_is_rejected(self) -> None:
        self._patch(TargetRecord(
            target_name="Retinaldehyde-binding protein 1", gene_symbol="RLBP1",
            uniprot_id="P12271", organism="human", synonyms=["CRALBP"]))
        self.assertIsNone(self.agent._from_uniprot_client("BRD", TargetRecord))

    def test_matching_hit_is_accepted(self) -> None:
        self._patch(TargetRecord(
            target_name="Bromodomain-containing protein 4", gene_symbol="BRD4",
            uniprot_id="O60885", organism="human", synonyms=["HUNK1"]))
        rec = self.agent._from_uniprot_client("BRD4", TargetRecord)
        self.assertIsNotNone(rec)
        self.assertEqual(rec.uniprot_id, "O60885")


class EmptyBinderContractTests(unittest.TestCase):
    def _record(self, binders):
        result = {"state": {"retrieved_binders": binders}, "summary": {}}
        return build_agent_run_record(result, "run_test", "test", 1.0)

    def test_empty_placeholders_are_not_counted_as_binders(self) -> None:
        rec = self._record([
            BinderRecord(name="", smiles="", source="?"),  # empty placeholder
            BinderRecord(name="", smiles="", source="?"),
        ])
        binders = [e for e in rec.evidence_records if e.get("type") == "binder"]
        rejected = [e for e in rec.evidence_records if e.get("type") == "binder_rejected"]
        self.assertEqual(binders, [])
        self.assertEqual(sum(r["count"] for r in rejected), 2)

    def test_binder_with_structure_and_identity_survives(self) -> None:
        rec = self._record([
            BinderRecord(name="JQ1", target="BRD4", source="ChEMBL",
                         smiles="CC1=C(C(=O)N(C2CCN(CC2)C)C3=NN=C(S3)C4=CC=C(Cl)C=C4)C5=C(N1)C=CC=C5"),
        ])
        binders = [e for e in rec.evidence_records if e.get("type") == "binder"]
        self.assertEqual(len(binders), 1)
        self.assertEqual(binders[0]["name"], "JQ1")
        self.assertEqual(binders[0]["source"], "ChEMBL")
        self.assertTrue(binders[0]["has_structure"])


class WorkflowAbstainsOnUnresolvedTargetTests(unittest.TestCase):
    def test_resolution_failure_is_terminal(self) -> None:
        graph = LocalSynGlueWorkflowGraph()
        state = WorkflowState()
        state.errors.append(
            "TargetResolverAgent: Could not resolve 'BRD' to a reviewed UniProt entry.")
        self.assertTrue(graph._should_stop(state))

    def test_unrelated_error_does_not_stop(self) -> None:
        graph = LocalSynGlueWorkflowGraph()
        state = WorkflowState()
        state.errors.append("some transient warning")
        self.assertFalse(graph._should_stop(state))


if __name__ == "__main__":
    unittest.main()

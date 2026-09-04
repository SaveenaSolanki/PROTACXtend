from protacxtend.agentic.provenance import ProvenanceBuilder
from protacxtend.backend.schemas import CandidateRecord, DegradationPrediction, WorkflowState

import unittest


class AgenticProvenanceTests(unittest.TestCase):
    def test_candidate_provenance_records_model_and_sources(self):
        state = WorkflowState(
            valid_candidates=[
                CandidateRecord(
                    candidate_id="c1",
                    warhead_source="local",
                    e3_ligand_name="CRBN_ligand",
                    linker_name="PEG2",
                    assembly_strategy="template",
                    validity_status="valid",
                )
            ],
            degradation_predictions=[DegradationPrediction(candidate_id="c1", model_version="SynGlue-demo-heuristic-v0.1")],
        )
        prov = ProvenanceBuilder().build_candidate_provenance(state)
        self.assertEqual(prov[0].candidate_id, "c1")
        self.assertEqual(prov[0].degradation_model_version, "SynGlue-demo-heuristic-v0.1")
        self.assertEqual(prov[0].rdkit_validation_status, "valid")

from protacxtend.agentic.learning import LearningAgent
from protacxtend.backend.schemas import CandidateRecord, ParsedObjective, WorkflowState

import tempfile
import unittest
from pathlib import Path


class AgenticLearningTests(unittest.TestCase):
    def test_memory_records_are_written(self):
        with tempfile.TemporaryDirectory() as tempdir:
            memory_path = Path(tempdir) / "memory.jsonl"
            state = WorkflowState(
                user_request="Design CRBN PROTACs for BRD4.",
                parsed_objective=ParsedObjective(target_name="BRD4", e3_ligase="CRBN"),
                assembled_candidates=[CandidateRecord(candidate_id="c1")],
                valid_candidates=[CandidateRecord(candidate_id="c1", warhead_name="w", linker_class="PEG")],
            )
            record = LearningAgent(memory_path=memory_path).store_from_workflow("run-test", state.user_request, state)
            self.assertTrue(memory_path.exists())
            self.assertEqual(record.target, "BRD4")
            hits = LearningAgent(memory_path=memory_path).retrieve_similar_runs("BRD4", "CRBN")
            self.assertTrue(hits)
            self.assertEqual(hits[0]["run_id"], "run-test")

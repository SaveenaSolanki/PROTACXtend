from protacxtend.agentic.perception import PerceptionAgent


import unittest


class AgenticPerceptionTests(unittest.TestCase):
    def test_perception_collects_context_without_inventing_data(self):
        state = PerceptionAgent().run("Design CRBN PROTACs for BRD4. Generate 3 candidates with low hERG risk.")
        self.assertTrue(state.raw_request)
        self.assertEqual(state.detected_entities["target_name"].upper(), "BRD4")
        self.assertIn("curated_targets.csv", state.available_local_data)
        self.assertIn("rdkit", state.available_tools)
        self.assertIn("degradation", state.available_models)
        self.assertIn("warhead_smiles_or_known_binder_source", state.missing_information)

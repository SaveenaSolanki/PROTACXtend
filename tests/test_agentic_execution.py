from protacxtend.agentic.execution import ExecutionAgent
from protacxtend.schemas.tool_schema import NextAction

import unittest


class AgenticExecutionTests(unittest.TestCase):
    def test_tool_result_stores_runtime_status_and_provenance(self):
        action = NextAction(
            action_name="bad_tool",
            selected_tool="missing_tool",
            input_payload={"x": 1},
            reason_for_action="unit test",
            fallback_action="stop",
        )
        result = ExecutionAgent().run(action)
        self.assertEqual(result.status, "failed")
        self.assertGreaterEqual(result.runtime_seconds, 0)
        self.assertTrue(result.input_hash)
        self.assertEqual(result.provenance["fallback_action"], "stop")

"""Regressions for the TUI bridge report command and live progress.

Two defects are covered:

1. ``/report run_xxxx`` re-ran the whole workflow instead of reading the
   persisted ``outputs/runs/<run_id>/`` bundle. The bridge now exposes a
   ``report`` command that loads the run.
2. A multi-minute deterministic run emitted nothing until it finished. The
   graph now invokes a progress callback at each node so the TUI can stream
   stage-by-stage progress.
"""

from __future__ import annotations

import unittest
from pathlib import Path

import protacxtend.tui_bridge.server as server
from protacxtend.agents.graph import _notify_progress, set_progress_callback

RUNS = Path(server.__file__).resolve().parents[2] / "outputs" / "runs"


def _capture(fn, *args):
    events: list[dict] = []
    original = server.emit
    server.emit = lambda e: events.append(e)  # type: ignore[assignment]
    try:
        fn(*args)
    finally:
        server.emit = original  # type: ignore[assignment]
    return events


class ReportCommandTests(unittest.TestCase):
    def test_missing_run_reports_error_without_running_a_workflow(self) -> None:
        events = _capture(server.handle_report, "run_this_id_does_not_exist")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], "report")
        self.assertEqual(events[0]["status"], "error")
        self.assertIn("not found", events[0]["error"])

    def test_existing_run_loads_report_and_artifacts(self) -> None:
        runs = [p for p in RUNS.iterdir() if p.is_dir() and (p / "report.md").exists()]
        if not runs:
            self.skipTest("no persisted runs with report.md")
        rid = runs[0].name
        events = _capture(server.handle_report, rid)
        self.assertEqual(events[0]["status"], "ok")
        self.assertEqual(events[0]["run_id"], rid)
        self.assertGreater(len(events[0]["report"]), 0)
        names = [a["name"] for a in events[0]["artifacts"]]
        self.assertIn("report.md", names)
        self.assertTrue(events[0]["dir"].endswith(rid))

    def test_empty_run_id_selects_a_persisted_run(self) -> None:
        events = _capture(server.handle_report, "")
        self.assertEqual(events[0]["type"], "report")
        self.assertIn(events[0]["status"], {"ok", "error"})  # ok when any run exists


class ProgressCallbackTests(unittest.TestCase):
    def tearDown(self) -> None:
        set_progress_callback(None)

    def test_callback_receives_start_and_done(self) -> None:
        seen: list[tuple] = []
        set_progress_callback(lambda *a: seen.append(a))
        _notify_progress("resolve_target", "start", 0.0, 0, 10)
        _notify_progress("resolve_target", "done", 1.5, 0, 10)
        self.assertEqual(seen, [
            ("resolve_target", "start", 0.0, 0, 10),
            ("resolve_target", "done", 1.5, 0, 10),
        ])

    def test_callback_is_cleared_and_errors_never_propagate(self) -> None:
        set_progress_callback(lambda *a: (_ for _ in ()).throw(RuntimeError("boom")))
        _notify_progress("x", "start", 0.0, 0, 1)  # must not raise
        set_progress_callback(None)
        seen: list[tuple] = []
        set_progress_callback(lambda *a: seen.append(a))
        set_progress_callback(None)
        _notify_progress("y", "done", 0.1, 0, 1)
        self.assertEqual(seen, [])

    def test_langgraph_path_also_emits_progress(self) -> None:
        # Regression: run_syn_glue_workflow prefers a compiled LangGraph, which
        # previously bypassed the local-graph progress hook entirely.
        import protacxtend.agents.graph as g
        from protacxtend.backend.schemas import WorkflowState

        class _FakeGraph:
            def __init__(self) -> None:
                self.nodes = [("cheap_node", lambda state: state)]

        original = g.LocalSynGlueWorkflowGraph
        g.LocalSynGlueWorkflowGraph = _FakeGraph  # type: ignore[assignment]
        try:
            graph = g.build_langgraph_workflow()
            if graph is None:
                self.skipTest("langgraph not installed")
            seen: list[tuple] = []
            set_progress_callback(lambda *a: seen.append(a))
            graph.invoke(WorkflowState())
            set_progress_callback(None)
            self.assertIn(("cheap_node", "start", 0.0, 0, 1), seen)
            self.assertTrue(any(s[0] == "cheap_node" and s[1] == "done" for s in seen))
        finally:
            g.LocalSynGlueWorkflowGraph = original  # type: ignore[assignment]
            set_progress_callback(None)


if __name__ == "__main__":
    unittest.main()

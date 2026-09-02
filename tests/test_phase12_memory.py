"""Phase 12 memory/RAG tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from synglue_agent.memory import literature_rag, run_memory


class Phase12MemoryTests(unittest.TestCase):
    def _patch_memory_paths(self, root: Path):
        run_dir = root / "run_store"
        lit_dir = root / "literature_store"
        return patch.multiple(
            run_memory,
            RUN_MEMORY_DIR=run_dir,
            RUN_JSONL_PATH=run_dir / "runs.jsonl",
            RUN_SQLITE_PATH=run_dir / "runs.sqlite3",
        ), patch.multiple(
            literature_rag,
            LIT_DIR=lit_dir,
            LIT_JSONL_PATH=lit_dir / "literature_chunks.jsonl",
            LIT_SQLITE_PATH=lit_dir / "literature.sqlite3",
        )

    def test_store_and_retrieve_run_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            p1, p2 = self._patch_memory_paths(Path(directory))
            with p1, p2:
                run_memory.store_run_result(
                    run_id="run-1",
                    query="Design BRD4 CRBN protac",
                    candidates=[{"candidate_id": "C1", "target": "BRD4", "e3_ligase": "CRBN", "synthetic_feasibility_score": 0.8}],
                    report="Report body",
                )
                out = run_memory.retrieve_target_memory("BRD4")
                self.assertTrue(out["success"])
                self.assertFalse(out["empty"])
                self.assertEqual(out["results"][0]["run_id"], "run-1")

    def test_empty_memory_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            p1, p2 = self._patch_memory_paths(Path(directory))
            with p1, p2:
                out = run_memory.retrieve_target_memory("BRD4")
                self.assertTrue(out["success"])
                self.assertTrue(out["empty"])
                self.assertEqual(out["results"], [])

    def test_failed_linker_memory_after_failed_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            p1, p2 = self._patch_memory_paths(Path(directory))
            with p1, p2:
                run_memory.store_run_result(
                    run_id="run-2",
                    query="Design BRD4 CRBN protac",
                    candidates=[
                        {
                            "candidate_id": "C2",
                            "target": "BRD4",
                            "e3_ligase": "CRBN",
                            "warning_flags": ["linker_generation_failed"],
                        }
                    ],
                    report="Failed linker report",
                )
                out = run_memory.retrieve_failed_linker_memory(target="BRD4", e3="CRBN")
                self.assertTrue(out["success"])
                self.assertFalse(out["empty"])
                self.assertEqual(out["results"][0]["run_id"], "run-2")

    def test_rag_search_returns_source_linked_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            p1, p2 = self._patch_memory_paths(Path(directory))
            with p1, p2:
                text = (
                    "PROTAC degradation depends on target engagement, linker geometry, and E3 ligase compatibility. "
                    "BRD4 degraders with CRBN have been studied extensively."
                )
                idx = literature_rag.index_literature_document(text)
                self.assertTrue(idx["success"])
                hits = literature_rag.search_literature("BRD4 degrader CRBN", top_k=3)
                self.assertTrue(hits["success"])
                self.assertFalse(hits["empty"])
                first = hits["results"][0]
                self.assertIn("source", first)
                self.assertIn("document_id", first)
                summary = literature_rag.summarize_retrieved_context(hits["results"])
                self.assertTrue(summary["success"])
                self.assertFalse(summary["empty"])
                self.assertTrue(summary["citations"])


if __name__ == "__main__":
    unittest.main()

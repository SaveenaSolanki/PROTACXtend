import json
from pathlib import Path

from scripts.prepare_matched48_gold_pending_packet import build_packet, write_packet


def test_matched48_packet_blocks_scores_until_expert_gold():
    packet = build_packet(Path("gold_answers_v1.jsonl"))
    assert packet["case_count"] == 48
    assert packet["gold_status"] == "PENDING_HUMAN"
    assert packet["passed_evaluation"] is False
    assert packet["task_level_results"] == []
    assert packet["abstention_handling"] == "abstentions retained; PENDING_HUMAN is not a pass"
    assert {a["arm"] for a in packet["evaluation_arms"]} == {
        "full_agent", "deterministic", "retrieval_only", "llm_only", "tool_only"
    }
    assert all(a["status"] == "blocked_pending_expert_gold" for a in packet["evaluation_arms"])


def test_matched48_packet_artifacts_are_written(tmp_path):
    out = write_packet(tmp_path, Path("gold_answers_v1.jsonl"))
    status = json.loads(Path(out["status"]).read_text())
    assert status["gold_status"] == "PENDING_HUMAN"
    assert "PENDING_HUMAN" in Path(out["report"]).read_text()

"""Dev-only response fixtures for Sprint 2B.

Response kinds cover: perfect, partial, incorrect, hallucinated, missing,
malformed, timeout, tool_failure. These fixtures NEVER overlap with the 48
frozen benchmark cases (task ids are DEV-*).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "benchmark" / "dev_fixtures"

KINDS = ["perfect", "partial", "incorrect", "hallucinated", "missing",
         "malformed", "timeout", "tool_failure"]


def _ensure_fixtures_dir() -> Path:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    (FIXTURES_DIR / "README.md").write_text(
        "# dev_fixtures\nDevelopment-only responses for runner/scoring tests.\n"
        "None of these overlap the 48 frozen benchmark cases (DEV-* ids only).\n")
    return FIXTURES_DIR


DEFAULTS: Dict[str, Dict[str, Any]] = {
    "perfect": {"status": "ok", "raw": "DEV-PERFECT response with correct structured answer.",
                "answer": {"target": "Q60885"}, "tool_calls": 2, "tokens_in": 120,
                "tokens_out": 60, "cost_usd": 0.001},
    "partial": {"status": "partial", "raw": "DEV-PARTIAL: one mandatory element missing.",
                "answer": {"target": None}, "tool_calls": 1, "tokens_in": 90,
                "tokens_out": 40, "cost_usd": 0.0008},
    "incorrect": {"status": "ok", "raw": "DEV-INCORRECT wrong answer.", "answer": {"target": "P99999"},
                  "tool_calls": 1, "tokens_in": 70, "tokens_out": 30, "cost_usd": 0.0005},
    "hallucinated": {"status": "ok", "raw": "DEV-HALLUCINATED cites fabricated DOI 10.9999/nonexistent.",
                     "answer": {"citation": "10.9999/nonexistent"}, "tool_calls": 0,
                     "tokens_in": 60, "tokens_out": 50, "cost_usd": 0.0004},
    "missing": {"status": "ok", "raw": "DEV-MISSING no deliverable produced.", "answer": None,
                "tool_calls": 0, "tokens_in": 40, "tokens_out": 10, "cost_usd": 0.0002},
    "malformed": {"status": "malformed", "raw": "{not valid json", "error": "unparseable payload",
                  "tool_calls": 0, "tokens_in": 30, "tokens_out": 5, "cost_usd": 0.0001},
    "timeout": {"status": "timeout", "raw": "", "error": "budget exceeded",
                "tool_calls": 1, "tokens_in": 50, "tokens_out": 0, "cost_usd": 0.0003},
    "tool_failure": {"status": "tool_failure", "raw": "", "error": "permitted tool crashed",
                     "tool_calls": 3, "tokens_in": 80, "tokens_out": 20, "cost_usd": 0.0006},
}


def ensure_fixtures(write_files: bool = True) -> Dict[str, Dict[str, Any]]:
    """Register (and optionally persist) the standard dev fixture responses."""
    fixtures: Dict[str, Dict[str, Any]] = {}
    for kind in KINDS:
        body = dict(DEFAULTS[kind])
        body["fixture_kind"] = kind
        body["fixture_name"] = f"DEV-{kind}"
        fixtures[kind] = body
        if write_files:
            d = _ensure_fixtures_dir()
            (d / f"DEV-{kind}.json").write_text(json.dumps(body, indent=2) + "\n")
    return fixtures


def load_fixture_response(kind: str, name: str | None = None) -> Dict[str, Any]:
    if kind not in KINDS:
        raise ValueError(f"unknown fixture kind {kind!r}")
    path = FIXTURES_DIR / f"DEV-{kind}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    # fall back to defaults without writing (e.g., tests in tmp trees)
    return dict(DEFAULTS[kind], fixture_kind=kind,
                fixture_name=name or f"DEV-{kind}")

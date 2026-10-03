"""In-process TUI engine executor.

The Textual TUI drives the SAME bridge handlers the Node TUI calls over JSONL
(``protacxtend.tui_bridge.server.handle_command``), but captures events
in-process via :func:`protacxtend.tui_bridge.events.capture_events` — no
stdout protocol, no terminal corruption, no second implementation.

Every command therefore runs the existing engines: ``/design`` ->
``run_command("design", …)`` -> ``workflows.designer.run_design`` ->
``run_protacpilot`` (capability=DESIGN); ``/plan`` -> the planner;
``/investigate`` -> the research contract; ``/reason`` -> the diagnose engine;
``/run`` -> handle_run; chat -> the ConversationalAgent; and so on.
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path
from typing import Any, Iterator

from protacxtend.tui_bridge.events import capture_events

PROJECT_ROOT = Path(__file__).resolve().parents[2]

#: event types that terminate an answer expected by the TUI per command
FINAL_EVENT_TYPES = {
    "research_answer", "plan_answer", "plan_complete", "diagnosis_answer",
    "chat_answer", "chat_complete", "results", "run_complete", "explain",
    "status", "compare_result", "investigate_answer", "error",
}

#: preference order when several typed answers fire (e.g. plan_answer +
#: plan_complete): the richer payload wins for rendering.
ANSWER_PRIORITY = [
    "research_answer", "plan_answer", "diagnosis_answer", "chat_answer",
    "results", "explain", "status", "compare_result", "investigate_answer",
    "run_complete", "plan_complete", "chat_complete", "error",
]

#: Textual TUI verb -> bridge command name (single source for the input bar)
COMMAND_MAP = {
    "plan": "plan",
    "design": "design",
    "run": "run",
    "investigate": "investigate",
    "reason": "reason",
    "compare": "compare",
    "evidence": "evidence",
    "structure": "structure",
    "selectivity": "selectivity",
    "degradation": "degradation",
    "admet": "admet",
    "synthesis": "synthesis",
    "experiment": "experiment",
    "optimize": "optimize",
    "explain": "explain",
    "report": "report",
    "validate": "validate",
    "ask": "chat",
    "chat": "chat",
    "status": "status",
    "doctor": "doctor",
    "skills": "skills",
    "agents": "agents",
    "workflows": "workflows",
    "databases": "databases",
    "generator": "generator",
    "retrosynthesis": "retrosynthesis",
    "docking": "docking",
    "stereo": "stereo",
    "clear": "chat_reset",
    "ping": "ping",
}


def parse_input(text: str) -> tuple[str, str]:
    """Split a TUI line into (bridge_command, request_args).

    Leading slash is optional; unknown verbs fall back to chat so free text
    stays conversational (exactly like the Node TUI)."""
    t = (text or "").strip()
    if not t:
        return "", ""
    if t.startswith("/"):
        parts = t[1:].split(None, 1)
        verb = parts[0].lower() if parts else ""
        args = parts[1] if len(parts) > 1 else ""
    else:
        verb, args = "chat", t
    if verb in ("exit", "quit", "q"):
        return "quit", ""
    return COMMAND_MAP.get(verb, "chat"), args


def execute_command(cmd: str, args: str = "", *, offline: bool = True,
                    conversation_id: str = "tui-default",
                    extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run one bridge command in-process.

    Returns ``{"cmd", "events", "answer", "error"}`` where ``answer`` is the
    last typed final event for the command (or None when the handler produced
    none, e.g. ``chat_reset``/``workflows``/``agents``)."""
    prior = os.environ.get("PROTACXTEND_PLANNER_OFFLINE", None)
    os.environ["PROTACXTEND_PLANNER_OFFLINE"] = "1" if offline else "0"
    prev_cwd = Path.cwd()
    try:
        with contextlib.chdir(PROJECT_ROOT):
            from protacxtend.tui_bridge import events as _events_mod
            from protacxtend.tui_bridge import server as _server_mod
            from protacxtend.tui_bridge.server import handle_command

            payload: dict[str, Any] = {"cmd": cmd, "request": args}
            if conversation_id:
                payload["conversation_id"] = conversation_id
            if extra:
                payload.update(extra)
            if cmd == "investigate":
                # plan-task executor (explicit task id) or research contract
                payload["task"] = payload.get("task", "")
            with capture_events() as events:
                # Immunity against foreign monkeypatches of server.emit (some
                # test modules replace it and never restore): pin the real
                # emitter for the duration and restore whatever was there.
                _orig_emit = _server_mod.emit
                _server_mod.emit = _events_mod.emit
                try:
                    handle_command(cmd, payload)
                finally:
                    _server_mod.emit = _orig_emit
    finally:
        if prior is None:
            os.environ.pop("PROTACXTEND_PLANNER_OFFLINE", None)
        else:
            os.environ["PROTACXTEND_PLANNER_OFFLINE"] = prior
        prev_cwd  # noqa: B018 - cwd restored by contextlib.chdir

    answer = None
    for typ in ANSWER_PRIORITY:
        last = None
        for ev in events:
            if ev.get("type") == typ:
                last = ev
        if last is not None:
            answer = last
            break
    return {"cmd": cmd, "events": events, "answer": answer}


def summarize(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Compact honest summary of an event stream for log display."""
    stages: list[dict[str, Any]] = []
    for ev in events:
        t = ev.get("type")
        if t == "progress":
            stages.append({"stage": ev.get("stage"), "status": ev.get("status"),
                           "detail": ev.get("detail")})
        elif t == "research_answer" and ev.get("stage_timeline"):
            for s in ev["stage_timeline"]:
                stages.append(dict(s))
    executed = [s for s in stages if s.get("status") == "executed"]
    unevaluated = [s for s in stages if s.get("status") == "unevaluated"]
    failed = [s for s in stages if s.get("status") in ("failed", "error")]
    return {
        "n_stages": len(stages),
        "executed": [s.get("stage") for s in executed],
        "unevaluated": [s.get("stage") for s in unevaluated],
        "failed": [s.get("stage") for s in failed],
    }
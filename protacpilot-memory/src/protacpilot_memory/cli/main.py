"""`ppmemory` command-line interface (Master Prompt §31, §55)."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from ..api import CognitiveMemory


def _json_load(value: str | None) -> Any:
    if not value:
        return None
    return json.loads(value)


def _print(payload: Any) -> None:
    print(json.dumps(payload, default=str, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ppmemory", description="PROTACpilot Cognitive Memory CLI")
    parser.add_argument("--db", help="database path (default: ~/.protacpilot-memory/memory.db)")
    parser.add_argument("--config", help="TOML config path")
    parser.add_argument("--project", help="project name or id")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="initialise the store and run migrations")
    sub.add_parser("doctor", help="store health diagnostics")
    sub.add_parser("stats", help="memory statistics")
    sub.add_parser("tools", help="list MCP tools")

    p = sub.add_parser("project", help="resolve/create the current project")
    p.add_argument("--name")
    p.add_argument("--description")

    p = sub.add_parser("session-start", help="start a session")
    p.add_argument("--goal")

    p = sub.add_parser("session-end", help="end a session (cognitive handoff)")
    p.add_argument("session_id")
    p.add_argument("--summary")
    p.add_argument("--next-step", action="append", default=[])

    p = sub.add_parser("encode", help="encode an episodic memory")
    p.add_argument("--title", required=True)
    p.add_argument("--content", required=True)
    p.add_argument("--event-type", default="experiment")
    p.add_argument("--context", help="JSON PROTAC context")
    p.add_argument("--observed", help="JSON observed values")
    p.add_argument("--interpretation")
    p.add_argument("--negative", action="store_true")
    p.add_argument("--session-id")

    p = sub.add_parser("search", help="hybrid memory search")
    p.add_argument("query")
    p.add_argument("--context", help="JSON PROTAC context")
    p.add_argument("--limit", type=int)

    p = sub.add_parser("recall", help="search + neighbourhood")
    p.add_argument("query")

    p = sub.add_parser("get", help="full memory packet")
    p.add_argument("memory_id")

    p = sub.add_parser("context", help="session-start cognitive context")
    p.add_argument("--session-id")

    p = sub.add_parser("timeline", help="chronological neighbourhood")
    p.add_argument("memory_id")
    p.add_argument("--window", type=int, default=5)

    p = sub.add_parser("neighbors", help="associative neighbours")
    p.add_argument("memory_id")
    p.add_argument("--depth", type=int, default=1)

    p = sub.add_parser("predict", help="store a prediction before its outcome")
    p.add_argument("--type", dest="prediction_type", default="numeric")
    p.add_argument("--candidate")
    p.add_argument("--metric")
    p.add_argument("--value", type=float)
    p.add_argument("--class", dest="predicted_class")
    p.add_argument("--probability", type=float)
    p.add_argument("--confidence", type=float, default=0.5)
    p.add_argument("--scale", type=float)
    p.add_argument("--context", help="JSON PROTAC context")
    p.add_argument("--session-id")

    p = sub.add_parser("outcome", help="record an outcome for a prediction")
    p.add_argument("prediction_id")
    p.add_argument("--value", type=float)
    p.add_argument("--class", dest="observed_class")
    p.add_argument("--evidence-type", default="internal_experiment")
    p.add_argument("--experiment-id")
    p.add_argument("--session-id")
    p.add_argument("--no-encode", action="store_true")

    p = sub.add_parser("consolidate", help="run consolidation")
    p.add_argument("--session-id")

    p = sub.add_parser("replay", help="run memory replay")
    p.add_argument("--trigger", default="manual")
    p.add_argument("--session-id")

    p = sub.add_parser("reconsolidate", help="reconsolidate a semantic memory")
    p.add_argument("semantic_id")
    p.add_argument("--trigger", default="manual")

    p = sub.add_parser("audit", help="run the memory audit")

    p = sub.add_parser("feedback", help="record retrieval usefulness")
    p.add_argument("memory_id")
    p.add_argument("--useful", choices=["yes", "no"], required=True)
    p.add_argument("--used-for")

    p = sub.add_parser("task-add", help="add a task")
    p.add_argument("title")
    p.add_argument("--related-memory")
    p.add_argument("--due")

    p = sub.add_parser("task-resolve", help="resolve a task")
    p.add_argument("task_id")
    p.add_argument("--status", default="done")

    p = sub.add_parser("future", help="create a prospective memory")
    p.add_argument("title")
    p.add_argument("--related-memory")
    p.add_argument("--due")

    sub.add_parser("mcp", help="run the MCP stdio server")

    p = sub.add_parser("serve-http", help="run the HTTP JSON server")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "mcp":
        from ..mcp.server import serve_stdio

        serve_stdio(CognitiveMemory.open(args.db))
        return 0
    if args.command == "serve-http":
        from ..server.api import serve_http

        serve_http(CognitiveMemory.open(args.db), host=args.host, port=args.port)
        return 0

    memory = CognitiveMemory.open(args.db)
    project_id = None
    if args.project:
        project_id = memory.store.get_project(args.project)["id"] if memory.store.get_project(args.project) else memory.ensure_project(args.project)

    try:
        if args.command == "init":
            _print(memory.doctor())
        elif args.command == "doctor":
            _print(memory.doctor())
        elif args.command == "stats":
            _print(memory.stats())
        elif args.command == "tools":
            from ..mcp.tools import CogToolRegistry

            _print({"tools": CogToolRegistry(memory).list_tools()})
        elif args.command == "project":
            _print(memory.current_project(args.name or args.project))
        elif args.command == "session-start":
            session = memory.start_session(project_id, args.goal)
            _print({"session_id": session, "project_id": project_id})
        elif args.command == "session-end":
            _print(memory.end_session(args.session_id, summary=args.summary, next_steps=args.next_step))
        elif args.command == "encode":
            _print(memory.encode(
                title=args.title, content=args.content, event_type=args.event_type,
                project_id=project_id, session_id=args.session_id,
                context=_json_load(args.context), observed=_json_load(args.observed) or {},
                interpretation=args.interpretation, is_negative=args.negative,
            ))
        elif args.command == "search":
            _print(memory.search_dict(args.query, project_id=project_id,
                                      context=_json_load(args.context), limit=args.limit))
        elif args.command == "recall":
            _print(memory.recall(args.query, project_id=project_id))
        elif args.command == "get":
            _print(memory.get(args.memory_id))
        elif args.command == "context":
            _print(memory.context(project_id, args.session_id))
        elif args.command == "timeline":
            _print(memory.timeline(args.memory_id, args.window))
        elif args.command == "neighbors":
            _print(memory.neighbors(args.memory_id, args.depth))
        elif args.command == "predict":
            _print({"prediction_id": memory.predict(
                prediction_type=args.prediction_type, project_id=project_id,
                session_id=args.session_id, candidate_id=args.candidate, metric=args.metric,
                predicted_value=args.value, predicted_class=args.predicted_class,
                predicted_probability=args.probability, confidence=args.confidence,
                scale=args.scale, context=_json_load(args.context),
            )})
        elif args.command == "outcome":
            _print(memory.record_outcome(
                args.prediction_id, observed_value=args.value, observed_class=args.observed_class,
                evidence_type=args.evidence_type, experiment_id=args.experiment_id,
                session_id=args.session_id, project_id=project_id, encode=not args.no_encode,
            ))
        elif args.command == "consolidate":
            _print(memory.consolidate(project_id, args.session_id))
        elif args.command == "replay":
            _print(memory.replay(project_id, trigger=args.trigger, session_id=args.session_id))
        elif args.command == "reconsolidate":
            _print(memory.reconsolidate(args.semantic_id, trigger=args.trigger))
        elif args.command == "audit":
            _print(memory.audit(project_id))
        elif args.command == "feedback":
            _print(memory.feedback(args.memory_id, useful=args.useful == "yes", used_for=args.used_for))
        elif args.command == "task-add":
            _print({"task_id": memory.task_add(args.title, project_id=project_id,
                                               related_memory_id=args.related_memory, due_at=args.due)})
        elif args.command == "task-resolve":
            _print(memory.task_resolve(args.task_id, args.status))
        elif args.command == "future":
            _print({"prospective_id": memory.future(title=args.title, project_id=project_id,
                                                    related_memory_id=args.related_memory, due_at=args.due)})
        else:  # pragma: no cover - argparse requires a command
            parser_error = f"unknown command: {args.command}"
            print(parser_error, file=sys.stderr)
            return 2
    finally:
        if args.command not in {"mcp", "serve-http"}:
            memory.close()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

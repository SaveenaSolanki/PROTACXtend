"""Command-line interface for PROTACXtend."""

from __future__ import annotations

import argparse
import os
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from protacxtend import __version__
from protacxtend.agents.runtime import run_protacpilot, summarize_run
from protacxtend.backend.main import run_workflow_from_request, summarize_state, write_outputs
from protacxtend.backend.mode_router import run_mode
from protacxtend.backend.schemas import model_to_dict

try:  # pragma: no cover - fallback is exercised when rich is unavailable.
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    RICH_AVAILABLE = True
except Exception:  # pragma: no cover
    Console = None
    Panel = None
    Table = None
    Text = None
    RICH_AVAILABLE = False

try:  # pragma: no cover - fallback is exercised when prompt_toolkit is unavailable.
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import WordCompleter

    PROMPT_TOOLKIT_AVAILABLE = True
except Exception:  # pragma: no cover
    PromptSession = None
    WordCompleter = None
    PROMPT_TOOLKIT_AVAILABLE = False


PROJECT_ROOT = Path(__file__).resolve().parents[1]

CAPABILITIES: list[dict[str, str]] = [
    {
        "name": "Interactive terminal interface",
        "status": "available",
        "detail": "No-argument PROTACXtend opens a prompt with slash commands, scenarios, status, and run handoff.",
    },
    {
        "name": "Print/plan mode",
        "status": "available",
        "detail": "PROTACXtend -p \"Design ...\" returns a fast JSON plan and runtime estimate.",
    },
    {
        "name": "Scenario guide",
        "status": "available",
        "detail": "PROTACXtend scenarios shows common command patterns and expected runtime.",
    },
    {
        "name": "Scientific workflow run",
        "status": "available",
        "detail": "PROTACXtend \"Design ...\" runs the agentic PROTAC design workflow.",
    },
    {
        "name": "KNOW-REASON-DESIGN-DISCOVER contract",
        "status": "available",
        "detail": "PROTACXtend contract exposes scientific state, action cards, critique, dossiers, benchmarks, and model gates.",
    },
    {
        "name": "SMILES validation",
        "status": "available",
        "detail": "PROTACXtend validate --smiles CCO runs RDKit descriptors plus local scoring hooks.",
    },
    {
        "name": "terminal UI",
        "status": "available",
        "detail": "PROTACXtend (no args) or PROTACXtend tui opens a full-screen terminal UI with agent pipeline, model system, and live workflow log.",
    },
    {
        "name": "Frontend launcher",
        "status": "available",
        "detail": "PROTACXtend ui starts the Streamlit scientist workspace.",
    },
    {
        "name": "API launcher",
        "status": "available",
        "detail": "PROTACXtend api starts the FastAPI backend.",
    },
    {
        "name": "Retrosynthesis toolkits (ASKCOS / AiZynthFinder / RDKit+OpenNMT)",
        "status": "available",
        "detail": "Working engines behind run_retrosynthesis — protacxtend/tools/retrosynthesis_engines.py; "
                   "see scripts/retrosynthesis_toolkits_smoke.py and outputs/retrosynthesis_toolkits/evidence.json.",
    },
    {
        "name": "RPC/SDK parity",
        "status": "planned",
        "detail": "The backend functions exist, but a Pi-style stdin/stdout RPC protocol is not implemented yet.",
    },
]

SCENARIOS: list[dict[str, str]] = [
    {
        "name": "status",
        "command": "PROTACXtend status",
        "time": "1-3 seconds",
        "use": "Check installation, backend paths, and dependency availability.",
    },
    {
        "name": "validate",
        "command": 'PROTACXtend validate --smiles "CCO"',
        "time": "2-5 seconds",
        "use": "RDKit validation, descriptors, ADMET proxy, and degradation stub for one SMILES.",
    },
    {
        "name": "plan",
        "command": 'PROTACXtend -p "Design CRBN PROTACs for BRD4 degradation"',
        "time": "1-3 seconds",
        "use": "Pi-style print mode: show the planned workflow and estimated runtime without running design.",
    },
    {
        "name": "full_design",
        "command": 'PROTACXtend "Design CRBN PROTACs for BRD4 degradation"',
        "time": "2-8 minutes locally; longer if model loading or external tools are enabled",
        "use": "Run the full agentic scientific workflow.",
    },
    {
        "name": "deterministic_design",
        "command": 'PROTACXtend run "Design CRBN PROTACs for BRD4 degradation" --mode deterministic',
        "time": "2-6 minutes locally in the current repo state",
        "use": "Run the deterministic graph directly.",
    },
    {
        "name": "tui",
        "command": "PROTACXtend tui",
        "time": "Instant open; design jobs run inside the terminal UI",
        "use": "Launch the terminal interface with agent pipeline, model system, and live workflow log.",
    },
    {
        "name": "ui",
        "command": "PROTACXtend ui",
        "time": "5-15 seconds to boot; design jobs still take workflow time",
        "use": "Start the Streamlit scientist workspace.",
    },
    {
        "name": "api",
        "command": "PROTACXtend api",
        "time": "3-10 seconds to boot",
        "use": "Start the FastAPI backend.",
    },
]


def _console() -> Any:
    return Console() if RICH_AVAILABLE and Console is not None else None


def _print_json(payload: Any) -> None:
    print(json.dumps(model_to_dict(payload), indent=2))


def _request_from_parts(parts: list[str] | None, default: str = "") -> str:
    return " ".join(parts or []).strip() or default


def _estimate_for_request(request: str, mode: str = "agentic") -> dict[str, Any]:
    text = request.lower()
    wants_structure = any(term in text for term in ["structure", "ternary", "dock", "p4ward", "pose"])
    wants_many = any(term in text for term in ["100", "200", "large", "library", "screen"])
    base = "2-8 minutes"
    if mode == "deterministic":
        base = "2-6 minutes"
    if wants_structure:
        base = "10-60+ minutes if pose generation/docking is enabled; 2-8 minutes for proxy-only structural scoring"
    if wants_many:
        base = "8-30+ minutes depending on candidate count and model/tool availability"
    return {
        "request": request,
        "mode": mode,
        "estimated_runtime": base,
        "why": [
            "The command runs a scientific workflow, not a lightweight chat-only agent loop.",
            "Runtime depends on candidate count, RDKit/model loading, PROTAC-DB evidence lookup, TACK compatibility checks, and optional structural modeling.",
            "P4ward/Rosetta/docking-backed structural scenarios can move from minutes to hours.",
        ],
    }


def _print_plan(args: argparse.Namespace) -> int:
    request = _request_from_parts(args.request, "Design CRBN PROTACs for BRD4 degradation.")
    payload = _estimate_for_request(request, mode=args.mode)
    payload["workflow"] = [
        "parse objective",
        "bound search space",
        "select target binders, warheads, E3 ligands, exit vectors, and linkers",
        "construct and validate candidates",
        "score cell context, ADMET, novelty, applicability domain, degradation",
        "rank, diversify, review, evolve, select structural finalists",
        "score ternary/cooperativity/hook effect",
        "write report, memory, and active-learning update",
    ]
    _print_json(payload)
    return 0


def _render_banner() -> None:
    console = _console()
    if not console:
        print("PROTACXtend")
        print("Agentic PROTAC design CLI. Type /help or \\help, /capabilities, /scenarios, /status, /exit.")
        return
    title = Text("PROTACXtend", style="bold orange1")
    body = Text()
    body.append("Agentic PROTAC design terminal interface\n", style="bold")
    body.append("On a TTY, ", style="bold")
    body.append("PROTACXtend", style="bold green")
    body.append(" opens the terminal UI. In fallback mode:\n")
    body.append("Type a design request, or use slash/backslash commands: ")
    body.append("/help", style="bold cyan")
    body.append(" ")
    body.append("\\help", style="bold cyan")
    body.append(", ")
    body.append("/capabilities", style="bold cyan")
    body.append(", ")
    body.append("/scenarios", style="bold cyan")
    body.append(", ")
    body.append("/status", style="bold cyan")
    body.append(", ")
    body.append("/tui", style="bold green")
    body.append(", ")
    body.append("/exit", style="bold cyan")
    body.append(".")
    console.print(Panel(body, title=title, border_style="orange1"))


def _render_capabilities(json_output: bool = False) -> None:
    payload = {"capabilities": CAPABILITIES}
    if json_output or not RICH_AVAILABLE or Table is None:
        _print_json(payload)
        return
    console = _console()
    table = Table(title="PROTACXtend capabilities", show_lines=False)
    table.add_column("Capability", style="bold")
    table.add_column("Status")
    table.add_column("Detail")
    for item in CAPABILITIES:
        status_style = "green" if item["status"] == "available" else "yellow"
        table.add_row(item["name"], f"[{status_style}]{item['status']}[/{status_style}]", item["detail"])
    console.print(table)


def _render_scenarios(json_output: bool = False) -> None:
    payload = {"scenarios": SCENARIOS}
    if json_output:
        _print_json(payload)
        return
    if not RICH_AVAILABLE or Table is None:
        for item in SCENARIOS:
            print(f"{item['name']}: {item['command']}")
            print(f"  time: {item['time']}")
            print(f"  use:  {item['use']}")
        return
    console = _console()
    table = Table(title="PROTACXtend scenarios", show_lines=True)
    table.add_column("Scenario", style="bold orange1", no_wrap=True)
    table.add_column("Command", style="cyan")
    table.add_column("Typical time", style="green")
    table.add_column("Use")
    for item in SCENARIOS:
        table.add_row(item["name"], item["command"], item["time"], item["use"])
    console.print(table)


def _scenarios_command(args: argparse.Namespace) -> int:
    _render_scenarios(json_output=bool(args.json))
    return 0


def _capabilities_command(args: argparse.Namespace) -> int:
    from protacxtend.runtime.registry import build_registry, find, summary, trace

    name = getattr(args, "name", None)
    recs = build_registry()
    if name:
        import json as _json
        if getattr(args, "run", False):
            from protacxtend.runtime.executor import run_capability
            params = _json.loads(args.params) if getattr(args, "params", "") else {}
            payload = run_capability(name, params)
        else:
            payload = trace(recs, name)
        # compact single-line JSON so machine callers (e2e audit) can parse it
        print(_json.dumps(payload, default=str))
        return 0
    if bool(getattr(args, "json", False)) or not RICH_AVAILABLE or Table is None:
        _print_json({"summary": summary(recs), "capabilities": [r.to_row() for r in recs]})
        return 0
    console = _console()
    table = Table(title="PROTACxtend canonical capability registry", show_lines=False)
    table.add_column("Kind", style="bold")
    table.add_column("Count")
    for kind, n in sorted(summary(recs)["by_kind"].items()):
        table.add_row(kind, str(n))
    console.print(table)
    return 0


def _install_command(args: argparse.Namespace) -> int:
    """Install an APPROVED, pinned capability recipe into an isolated env."""
    from protacxtend.runtime import acquisition as acq
    from protacxtend.runtime.recipes import list_recipes

    if getattr(args, "list", False) or not getattr(args, "name", ""):
        _print_json({"approved_recipes": list_recipes()})
        return 0
    allow = bool(getattr(args, "allow", False))
    result = acq.install(args.name, allow=allow, dry_run=not allow)
    _print_json(result)
    return 0 if (result.get("success") or result.get("state") == "PLANNED") else 1


def _audit_command(args: argparse.Namespace) -> int:
    """Execute the complete runtime capability audit suite."""
    from protacxtend.runtime.audit import run_audit

    audit = run_audit(e2e_n=int(getattr(args, "e2e", 50)),
                      install_sample=not getattr(args, "no_install", False),
                      budget_s=float(getattr(args, "budget", 1800)))
    if bool(getattr(args, "json", False)):
        _print_json(audit)
    else:
        print(f"audit written to results/audit/ ({', '.join(audit['files'])})")
        print(f"  registry: {audit['registry']['summary']['total']} capabilities")
        for k in ("capability_audit", "tool_audit", "tui_api_web_audit",
                  "service_database_audit", "installation_audit"):
            print(f"  {k}: {audit[k]}")
        print(f"  end_to_end: {audit['end_to_end']}")
        print(f"  elapsed: {audit['elapsed_s']}s")
    return 0


def _toolkit_command(args: argparse.Namespace) -> int:
    """Provision, verify and document the external scientific toolkit."""
    import json as _json

    from protacxtend.toolkit import catalog, provision
    from protacxtend.toolkit.environments import toolkit_envs

    action = getattr(args, "action", "plan")
    as_json = bool(getattr(args, "json", False))

    if action == "envs":
        envs = [e.to_dict() for e in toolkit_envs()]
        if as_json:
            print(_json.dumps(envs, indent=2))
        else:
            for e in envs:
                print(f"{e['name']:<16} {e['kind']:<8} {e['python']}")
        return 0

    if action == "plan":
        plans = catalog.plan_all_tools()
        summary = catalog.summarize_plans(plans)
        if as_json:
            print(_json.dumps({"summary": summary, "plans": plans}, indent=2))
        else:
            print("Toolkit provisioning summary:")
            for method, count in summary.items():
                print(f"  {method:<12} {count}")
            print()
            print(f"{'tool':<28}{'method':<10}{'auto':<6}command/reason")
            for p in plans:
                detail = p["command"] or p["reason"]
                print(f"{p['tool_name']:<28}{p['method']:<10}{'yes' if p['auto_installable'] else 'no':<6}{detail[:60]}")
        return 0

    if action == "provision":
        mode = getattr(args, "mode", "check")
        categories = [c for c in (getattr(args, "categories", "") or "").split(",") if c]
        rows = provision.provision_batch(
            [getattr(args, "tool", "")] if getattr(args, "tool", "") else None,
            mode=mode, categories=categories or None,
            max_tools=int(getattr(args, "max", 0) or 0),
        )
        if as_json:
            print(_json.dumps(rows, indent=2, default=str))
        else:
            for r in rows:
                flag = "OK " if r.get("success") or r.get("verified") else "-- "
                print(f"{flag}{r['tool_name']:<28}{r['method']:<10}{r.get('version_after') or r.get('version_before') or '':<34}{(r.get('detail') or '')[:50]}")
        return 0

    if action == "verify":
        rows = []
        for row in provision.manifest_table():
            if row["installed"]:
                rows.append(provision.verify_tool(row["tool_name"]))
        if as_json:
            print(_json.dumps(rows, indent=2, default=str))
        else:
            for r in rows:
                flag = "OK " if r["verified"] else "!! "
                print(f"{flag}{r['tool_name']:<28}{r['method']:<12}{r['env']:<14}{r.get('version','')[:40]}")
        return 0

    if action == "manifest":
        rows = provision.manifest_table()
        if as_json:
            print(_json.dumps(rows, indent=2, default=str))
        else:
            for r in rows:
                print(f"{r['tool_name']:<28}{'installed' if r['installed'] else 'missing':<12}"
                      f"{'callable' if r['callable'] else '':<10}{r['version'][:34]}")
        return 0

    if action == "truth":
        from protacxtend.toolkit.truth import write_truth

        xlsx, md = write_truth(compute_hash=not getattr(args, "fast", False))
        print(f"Toolkit truth written:\n  {xlsx}\n  {md}")
        return 0

    print(f"Unknown toolkit action: {action}")
    return 2


def _escalation_command(args: argparse.Namespace) -> int:
    """Failure diagnosis, external fallback resolution and audit."""
    import json as _json

    from protacxtend.escalation import (
        build_escalation_report,
        get_ledgers,
        resolve_candidates,
        resolve_tool,
    )
    from protacxtend.escalation.registry import DynamicToolRegistry
    from protacxtend.escalation.installer import InstallManager

    action = getattr(args, "action", "status")
    capability = getattr(args, "capability", "") or ""
    tool = getattr(args, "tool", "") or ""
    mode = getattr(args, "mode", "check") or "check"
    as_json = bool(getattr(args, "json", False))
    ledgers = get_ledgers()

    if action == "status":
        payload = {"ledger_paths": ledgers.paths(), "counts": ledgers.counts()}
        if as_json:
            print(_json.dumps(payload, indent=2))
        else:
            print("Escalation ledgers:")
            for k, v in payload["ledger_paths"].items():
                print(f"  {k}: {v}")
            print("Counts:", payload["counts"])
        return 0

    if action == "audit":
        report = build_escalation_report()
        if as_json:
            print(_json.dumps(report, indent=2, default=str))
        else:
            from protacxtend.escalation.report import render_markdown

            print(render_markdown(report))
        return 0

    if action == "capabilities":
        from protacxtend.escalation.report import capability_readiness

        rows = capability_readiness()
        if as_json:
            print(_json.dumps(rows, indent=2))
        else:
            print(f"{'capability':<32}{'installed':>10}{'installable':>12}{'web':>6}  {'readiness':<12}best")
            for r in rows:
                print(f"{r['capability']:<32}{r['installed']:>10}{r['installable']:>12}"
                      f"{r['web_fallbacks']:>6}  {r['readiness']:<12}{r['best_candidate']}")
        return 0

    if action == "resolve":
        if not capability:
            print("Provide --capability <name>")
            return 2
        rows = [c.to_dict() for c in resolve_candidates(capability)]
        print(_json.dumps(rows, indent=2) if as_json else "\n".join(
            f"{c['tool_name']:<28} installed={c['installed']!s:<5} status={c['status']:<28} method={c['install_method']}"
            for c in rows
        ))
        return 0

    if action == "registry":
        reg = DynamicToolRegistry(ledgers=ledgers)
        rows = reg.list()
        print(_json.dumps(rows, indent=2) if as_json else "\n".join(
            f"{r['tool_name']:<28} v{r.get('version',''):<24} {','.join(r.get('capabilities', []))}"
            for r in rows
        ) or "(dynamic registry empty)")
        return 0

    if action == "clear-registry":
        DynamicToolRegistry(ledgers=ledgers).clear()
        print("Dynamic registry cleared.")
        return 0

    if action == "install":
        if not tool:
            print("Provide --tool <toolkit tool name>")
            return 2
        candidate = resolve_tool(tool, capability)
        if candidate is None:
            print(f"Tool '{tool}' is not in the toolkit registry.")
            return 2
        manager = InstallManager(ledgers)
        plan = manager.plan(candidate)
        if mode in {"check", "dry_run"} and not candidate.installed:
            record = manager.install(candidate, allow=(mode == "install"))
        else:
            record = manager.check(candidate)
        payload = {"plan": plan, "candidate": candidate.to_dict(), "record": record.to_dict()}
        print(_json.dumps(payload, indent=2) if as_json else
              f"tool={candidate.tool_name}\nmethod={plan['install_method']}\ncommand={plan['command']}\n"
              f"action={record.action}\nsuccess={record.success}\nversion={record.version_after or candidate.version}")
        return 0

    print(f"Unknown escalation action: {action}")
    return 2


def _normalize_interactive_prompt(prompt: str) -> str:
    if prompt.startswith("\\"):
        return "/" + prompt[1:]
    return prompt


def _print_workflow_hint(command: str, request: str = "") -> None:
    topic = command.strip("/\\").lower()
    prompts = {
        "design": "Design and rank PROTAC candidates with bounded linker/E3/warhead search.",
        "evidence": "Retrieve PROTAC-DB, literature, affinity, degradation, permeability, and PK evidence.",
        "structure": "Score ternary feasibility, lysine reach, interface geometry, linker strain, and docking readiness.",
        "cellcontext": "Score target and E3 abundance in a cell-line-specific context.",
        "rank": "Run multi-objective ranking with degradation, ADMET, novelty, context, and uncertainty.",
        "learn": "Register experimental feedback for active-learning, validation, promotion, and rollback.",
        "report": "Create a scientist-facing report with candidates, caveats, evidence, and next experiments.",
    }
    payload = {
        "command": command,
        "description": prompts.get(topic, "PROTACXtend workflow shortcut."),
        "request": request or "No specific request supplied.",
        "next": f"Use /run {request}" if request else f"Use /{topic} <your task> or /run <your full design request>.",
    }
    _print_json(payload)


def _interactive_command() -> int:
    """Launch the terminal UI when on a TTY, else fallback."""
    # First-run: open the setup wizard when no provider is configured (unless
    # already handled by the main() gate or explicitly skipped).
    import os as _os
    if _os.environ.get("PROTACXTEND_SETUP_HANDLED") != "1":
        try:
            from protacxtend.llm.setup_wizard import first_run_gate
            first_run_gate(ask=input, out=print)
        except Exception as exc:  # never block the UI on setup problems
            print(f"(llm setup skipped: {exc})")
    if sys.stdin.isatty():
        try:
            from protacxtend.tui.app import launch_tui
            launch_tui()
            return 0
        except ImportError as exc:
            print(f"TUI requires 'textual': {exc}", file=sys.stderr)
            print("Install with: pip install textual rich", file=sys.stderr)
        except Exception as exc:
            print(f"TUI failed: {exc}", file=sys.stderr)
    return _interactive_command_fallback()


def _interactive_command_fallback() -> int:
    """Fallback: simple text-based interactive mode when TUI is unavailable."""
    _render_banner()
    completer = None
    session = None
    if PROMPT_TOOLKIT_AVAILABLE and PromptSession is not None and WordCompleter is not None:
        completer = WordCompleter(
            [
                "/help",
                "\\help",
                "/status",
                "\\status",
                "/capabilities",
                "\\capabilities",
                "/scenarios",
                "\\scenarios",
                "/plan",
                "\\plan",
                "/run",
                "\\run",
                "/design",
                "\\design",
                "/evidence",
                "\\evidence",
                "/structure",
                "\\structure",
                "/cellcontext",
                "\\cellcontext",
                "/rank",
                "\\rank",
                "/learn",
                "\\learn",
                "/report",
                "\\report",
                "/contract",
                "\\contract",
                "/models",
                "\\models",
                "/benchmarks",
                "\\benchmarks",
                "/validate",
                "\\validate",
                "/tui",
                "\\tui",
                "/ui",
                "\\ui",
                "/api",
                "\\api",
                "/exit",
                "\\exit",
            ],
            ignore_case=True,
        )
        session = PromptSession(completer=completer)
    while True:
        try:
            if session is not None:
                prompt = session.prompt("PROTACXtend> ").strip()
            else:
                prompt = input("PROTACXtend> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not prompt:
            continue
        prompt = _normalize_interactive_prompt(prompt)
        if prompt in {"/exit", "exit", "quit", "/quit"}:
            return 0
        if prompt in {"/help", "help"}:
            build_parser().print_help()
            continue
        if prompt == "/status":
            _status_command(argparse.Namespace())
            continue
        if prompt == "/scenarios":
            _render_scenarios()
            continue
        if prompt == "/capabilities":
            _render_capabilities()
            continue
        if prompt.startswith("/plan "):
            _print_plan(argparse.Namespace(request=[prompt.removeprefix("/plan ").strip()], mode="agentic"))
            continue
        if prompt == "/contract" or prompt.startswith("/contract "):
            _mode_command("contract", argparse.Namespace(request=[prompt.removeprefix("/contract").strip()], section="summary"))
            continue
        if prompt == "/models" or prompt.startswith("/models "):
            _mode_command("contract", argparse.Namespace(request=[prompt.removeprefix("/models").strip()], section="models"))
            continue
        if prompt == "/benchmarks" or prompt.startswith("/benchmarks "):
            _mode_command("contract", argparse.Namespace(request=[prompt.removeprefix("/benchmarks").strip()], section="benchmarks"))
            continue
        shortcut = next(
            (
                item
                for item in ["/evidence", "/structure", "/cellcontext", "/rank", "/learn", "/report"]
                if prompt == item or prompt.startswith(f"{item} ")
            ),
            "",
        )
        if shortcut:
            _print_workflow_hint(shortcut, prompt.removeprefix(shortcut).strip())
            continue
        if prompt.startswith("/design "):
            prompt = prompt.removeprefix("/design ").strip()
        elif prompt == "/design":
            _print_workflow_hint("/design")
            continue
        if prompt.startswith("/validate "):
            _mode_command("validate", argparse.Namespace(smiles=prompt.removeprefix("/validate ").strip()))
            continue
        if prompt == "/tui":
            print("Launching terminal UI...")
            _tui_command(argparse.Namespace(request=[]))
            continue
        if prompt == "/ui":
            print("Starting Streamlit UI. Press Ctrl+C to stop it.")
            _ui_command(argparse.Namespace(host="0.0.0.0", port=8501, headless=True))
            continue
        if prompt == "/api":
            print("Starting FastAPI backend. Press Ctrl+C to stop it.")
            _api_command(argparse.Namespace(host="0.0.0.0", port=8001, reload=False))
            continue
        if prompt.startswith("/run "):
            prompt = prompt.removeprefix("/run ").strip()
        estimate = _estimate_for_request(prompt)
        console = _console()
        if console and Panel is not None:
            console.print(Panel(f"Estimated full workflow time: {estimate['estimated_runtime']}\nUse /plan {prompt} for a fast plan-only view.", title="Run estimate", border_style="yellow"))
        else:
            print(f"Estimated full workflow time: {estimate['estimated_runtime']}")
        answer = input("Run full workflow now? [y/N] ").strip().lower()
        if answer in {"y", "yes"}:
            _run_command(argparse.Namespace(request=[prompt], mode="agentic", run_id="", persistent=False, llm_enabled=False, json=False))
        else:
            print("Skipped. Use PROTACXtend -p \"...\" for a plan-only estimate.")


def _run_command(args: argparse.Namespace) -> int:
    request = _request_from_parts(args.request, "Design CRBN PROTACs for BRD4 degradation.")
    estimate = _estimate_for_request(request, mode=args.mode)
    print(
        f"PROTACXtend running {args.mode} workflow. Estimated time: {estimate['estimated_runtime']}. "
        "Use -p for instant plan-only mode.",
        file=sys.stderr,
    )
    config: dict[str, Any] = {
        "persistent": bool(args.persistent),
        "llm_enabled": bool(args.llm_enabled),
    }
    if args.run_id:
        config["run_id"] = args.run_id
    result = run_protacpilot(request, mode=args.mode, config=config)
    if args.json:
        _print_json(result)
    else:
        print(summarize_run(result))
        artifacts = result.get("artifacts") or {}
        if artifacts:
            _print_json({"artifacts": artifacts})
    return 0


def _design_command(args: argparse.Namespace) -> int:
    request = _request_from_parts(args.request, "Design CRBN PROTACs for BRD4 degradation.")
    state = run_workflow_from_request(request)
    paths = write_outputs(state, args.stem)
    _print_json({"summary": summarize_state(state), "outputs": paths})
    return 0


def _strategy_command(args: argparse.Namespace) -> int:
    """Run the canonical control plane and emit a typed TherapeuticStrategy.

    This is the single consolidated entry point: the deterministic graph and
    the legacy agentic layer are execution engines reached *through* the
    canonical ToolExecutor, not parallel front doors.
    """
    from protacxtend.canonical import run_canonical

    request = _request_from_parts(args.request, "Design CRBN PROTACs for BRD4 degradation.")
    result = run_canonical(request, config={"engine": args.engine})
    strategy = result.strategy
    out_dir = PROJECT_ROOT / "outputs" / "strategies"
    out_dir.mkdir(parents=True, exist_ok=True)
    identifier = strategy.strategy_id or result.run_id or "strategy"
    strategy_path = out_dir / f"{identifier}.strategy.json"
    manifest_path = out_dir / f"{identifier}.manifest.json"
    strategy_path.write_text(
        json.dumps(strategy.model_dump(), indent=2, default=str), encoding="utf-8")
    manifest_path.write_text(
        json.dumps(strategy.run_manifest.model_dump(), indent=2, default=str), encoding="utf-8")
    payload = {
        "run_id": result.run_id,
        "status": result.status,
        "strategy": str(strategy_path),
        "manifest": str(manifest_path),
        "stopping_state": strategy.stopping_state,
        "critic": result.critic.model_dump(),
    }
    if args.json:
        _print_json(payload)
    else:
        print(f"run_id:   {result.run_id}")
        print(f"status:   {result.status}")
        print(f"strategy: {strategy_path}")
        print(f"manifest: {manifest_path}")
    return 0


def _mode_command(mode: str, args: argparse.Namespace) -> int:
    payload: dict[str, Any] = {"mode": mode}
    if getattr(args, "request", None):
        payload["request"] = _request_from_parts(args.request)
    if getattr(args, "query", None):
        payload["query"] = _request_from_parts(args.query)
    for key in [
        "smiles",
        "target_uniprot_id",
        "e3_uniprot_id",
        "backend",
        "top_k",
        "section",
        "evidence_cutoff_date",
        "pose",
        "target_chain",
        "e3_chain",
        "candidate_id",
        "target",
        "e3",
        "cell",
        "poi",
        "action",
        "method_ids",
        "target_conc_nM",
        "e3_conc_nM",
        "kd_target_nM",
        "kd_e3_nM",
        "alpha",
        "degradation_rate",
        "resynthesis_rate",
        "predictions",
        "candidates",
        "feedback",
        "batch_size",
        "run_id",
    ]:
        value = getattr(args, key, None)
        if value not in (None, ""):
            payload[key] = value
    _print_json(run_mode(payload))
    return 0


def _tui_command(args: argparse.Namespace) -> int:
    """Launch the terminal UI."""
    try:
        from protacxtend.tui.app import launch_tui
        request = _request_from_parts(args.request) if args.request else None
        launch_tui(request)
        return 0
    except ImportError as exc:
        print(f"TUI requires 'textual': {exc}", file=sys.stderr)
        print("Install with: pip install textual rich", file=sys.stderr)
        return 1


def _ui_command(args: argparse.Namespace) -> int:
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(PROJECT_ROOT / "protacxtend" / "app" / "streamlit_app.py"),
        "--server.address",
        args.host,
        "--server.port",
        str(args.port),
    ]
    if args.headless:
        cmd += ["--server.headless", "true"]
    return subprocess.call(cmd, cwd=PROJECT_ROOT)


def _api_command(args: argparse.Namespace) -> int:
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "protacxtend.backend.api_routes:get_app",
        "--factory",
        "--host",
        args.host,
        "--port",
        str(args.port),
    ]
    if args.reload:
        cmd.append("--reload")
    return subprocess.call(cmd, cwd=PROJECT_ROOT)


def _status_command(args: argparse.Namespace) -> int:
    deps = ["rdkit", "pandas", "streamlit", "fastapi", "uvicorn", "pydantic", "sklearn"]
    payload = {
        "name": "PROTACXtend",
        "version": __version__,
        "project_root": str(PROJECT_ROOT),
        "frontend": {
            "command": "PROTACXtend ui",
            "url": "http://localhost:8501",
            "entrypoint": "protacxtend/app/streamlit_app.py",
        },
        "api": {
            "command": "PROTACXtend api",
            "url": "http://localhost:8001/docs",
            "entrypoint": "protacxtend/backend/api_routes.py",
        },
        "dependencies": {name: bool(importlib.util.find_spec(name)) for name in deps},
    }
    if getattr(args, "json", False) or not RICH_AVAILABLE or Table is None:
        _print_json(payload)
        return 0
    console = _console()
    table = Table(title="PROTACXtend status")
    table.add_column("Area", style="bold orange1")
    table.add_column("Value")
    table.add_row("Version", payload["version"])
    table.add_row("Project root", payload["project_root"])
    table.add_row("Frontend", f"{payload['frontend']['url']} ({payload['frontend']['command']})")
    table.add_row("API", f"{payload['api']['url']} ({payload['api']['command']})")
    for name, available in payload["dependencies"].items():
        table.add_row(f"Dependency: {name}", "available" if available else "missing")
    console.print(table)
    return 0




# ── LLM backend + assistant chat ───────────────────────────────────────

def _print_llm_status(out=print) -> None:
    from protacxtend.llm.setup import read_config
    info = read_config()
    h = info["health"]
    out("")
    out(f"  provider   {info['provider']}")
    out(f"  model      {info['model']}")
    out(f"  base_url   {info['base_url']}")
    out(f"  api_key    {'set' if info['api_key_set'] else 'not set'}")
    out(f"  health     {'OK (' + str(h.get('n_models')) + ' models visible)' if h.get('ok') else 'UNREACHABLE: ' + str(h.get('error', ''))}")
    if info.get("config_file"):
        out(f"  config     {info['config_file']}")
    out("")


def _llm_command(args: argparse.Namespace) -> int:
    from protacxtend.llm.providers import get_config
    if getattr(args, "setup", False):
        from protacxtend.llm.setup_wizard import run_setup
        run_setup(ask=input, out=print)
        _print_llm_status()
        return 0
    if args.provider or args.model or args.base_url or args.api_key:
        from protacxtend.llm.setup import apply_config
        try:
            if args.api_key and not (args.provider or get_config().provider):
                raise ValueError("provider required (protacxtend setup) before an API key can be saved")
            apply_config(provider=args.provider or get_config().provider,
                         model=args.model or "",
                         base_url=args.base_url or "",
                         api_key=args.api_key or "")
        except ValueError as exc:
            print(f"llm: {exc}")
            return 1
    _print_llm_status()
    return 0


def _chat_command(args: argparse.Namespace) -> int:
    """Pi-style conversational scientific agent (tools → graph handoff)."""
    import os
    from protacxtend.agentic.chat_agent import ConversationalAgent, ClarificationNeeded
    from protacxtend.agentic.registry import TOOL_SPECS
    from protacxtend.llm.providers import USER_CONFIG_PATH, get_config

    if not os.environ.get("PROTACPILOT_LLM_PROVIDER") and not USER_CONFIG_PATH.exists():
        from protacxtend.llm.setup_wizard import run_setup
        run_setup(ask=input, out=print)

    cfg = get_config()
    if not cfg.provider:
        print("chat: no LLM provider configured — run `protacxtend setup` first.", file=sys.stderr)
        return 2
    agent = ConversationalAgent(cfg)

    def banner() -> str:
        from protacxtend.llm.chat_client import backend_banner
        return backend_banner(cfg)

    def print_run(run) -> None:
        for ev in run.events:
            print("  " + ev.render())

    def finish(run, newline=True) -> None:
        print_run(run)
        k = (run.summary or {}).get("kind")
        if k == "answer":
            print("\n" + str(run.summary.get("answer", "")))
        elif k == "handoff":
            print("\n" + str(run.summary.get("answer", "")))
        elif k == "clarification":
            print("\n" + str(run.summary.get("question", "")))
        elif k == "error":
            print("\n[error] " + str(run.summary.get("error", "unknown")))

    def fresh_agent() -> None:
        nonlocal agent
        agent = ConversationalAgent(get_config())

    message = " ".join(getattr(args, "message", None) or [])
    if message:
        try:
            run = agent.turn(message, ask=None if not sys.stdin.isatty() else input)
        except ClarificationNeeded as need:
            print("\nACTION REQUIRED — " + need.question)
            return 2
        finish(run)
        return 0

    print("")
    print("  PROTACXtend agent — " + banner())
    print("  ask scientifically · /llm switch backend · /tools · /agents · /status · /clear · /help · /exit")
    print("")
    while True:
        try:
            line = input("PROTACXtend> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye")
            return 0
        if not line:
            continue
        low = line.lower()
        if low in ("/exit", "/quit", "exit", "quit"):
            return 0
        if low in ("/clear", "clear"):
            fresh_agent()
            print("(session cleared)")
            continue
        if low in ("/help", "help", "?"):
            print("  /llm /model set NAME   switch backend / model (shared config)")
            print("  /tools                 show the strict tool registry")
            print("  /agents                deterministic specialist agents (under the graph)")
            print("  /run <objective>       force a full workflow handoff")
            print("  /status                active provider + health")
            print("  /clear /exit           session controls")
            continue
        if low in ("/llm", "/model"):
            from protacxtend.llm.setup_wizard import run_setup
            run_setup(ask=input, out=print)
            fresh_agent()
            print("  → " + banner())
            continue
        if low.startswith("/model set ") or low.startswith("/models set "):
            name = line.split("set", 1)[1].strip()
            from protacxtend.llm.setup import apply_config
            try:
                apply_config(provider=cfg.provider, model=name)
                fresh_agent()
                print("  → model set to " + name)
            except Exception as exc:
                print("  model set failed: " + str(exc))
            continue
        if low in ("/models", "model") or low == "/model status":
            _print_llm_status()
            continue
        if low in ("/tools", "tools"):
            for sp in TOOL_SPECS:
                print(f"  {sp['name']:<28} [{sp['readiness']}] {sp['kind']} · {sp['evidence_type']}")
            continue
        if low in ("/agents", "agents"):
            print("  deterministic specialist agents live inside the SynGlue graph:")
            print("  Supervisor · Planner · Target · Binder · Warhead · E3 · Exit Vector · Linker ·")
            print("  Construction · Ternary · ADMET · Prediction · Cell Context · Ranking · Report")
            continue
        if low.startswith("/run "):
            line = "Design: " + line[5:].strip()
        text = line
        print("")
        try:
            run = agent.turn(text, ask=input)
        except ClarificationNeeded as need:
            print("\nACTION REQUIRED — " + need.question)
            continue
        finish(run)



def _runtime_command(args: argparse.Namespace) -> int:
    from protacxtend.pi_launcher import print_runtime_status
    return print_runtime_status()



def _pilot_command(args: argparse.Namespace) -> int:
    """PROTACpilot structural workflow — registered engines run, externals block honestly."""
    from protacxtend.workflows.pilot_runner import run_protacpilot_pipeline
    ctx = {"target": args.target or "", "e3": args.e3 or "", "protac_smiles": args.smiles or "",
           "objective": " ".join(args.request or [])}

    def emit(evt) -> None:
        line = f"[{evt.get('kind')}] {evt.get('stage','')} {evt.get('name')} ({evt.get('status')}) → {evt.get('summary')}"
        print("  " + line)

    result = run_protacpilot_pipeline(ctx, emit)
    print("")
    print(f"PROTACpilot pipeline: {result['status']}")
    print(f"  steps executed: {len(result['results'])}")
    if getattr(args, "requirements", False):
        from protacxtend.workflows.pilot_runner import protac_model_requirements
        print(protac_model_requirements())
    if result.get("blocked_at"):
        detail = "NOT AVAILABLE — no fabrication"
        if result["blocked_at"] == "ternary_generator":
            detail += " · PROTAC-Model deps required (add --requirements for exact install steps)"
        print(f"  blocked at: {result['blocked_at']} ({detail})")
    return 0


def _auth_command(args: argparse.Namespace) -> int:
    """protacxtend auth login|status|logout — API keys are never printed."""
    from protacxtend.llm import manager
    sub = (args.auth_cmd or "status").lower()
    provider = (args.provider or "").strip() or None
    try:
        if sub == "login":
            from protacxtend.llm.providers import get_config
            cfg = get_config()
            if not provider:
                if cfg.provider:
                    provider = cfg.provider
                else:
                    raise ValueError(
                        "provider required — choose one: protacxtend provider list"
                        " (or pass --provider NAME)")
            if args.key_stdin:
                api_key = sys.stdin.readline().strip()
            else:
                import getpass
                api_key = getpass.getpass("API key (hidden): ").strip()
            if not api_key and not manager.PROVIDER_META[provider].local and provider != "openai_compatible":
                raise ValueError(f"API key required for provider '{provider}'")
            result = manager.login(provider, api_key,
                                   model=args.model or None, base_url=args.base_url or None)
            # Auth check: probe the endpoint with the stored key (no inference).
            probe = manager.probe_connection()
            if args.json:
                print(json.dumps({**result, "auth_probe": probe}, indent=2))
            else:
                auth_note = ("✓" if probe.get("ok") else "!")
                print(f"\u2713 logged in \u2014 provider={result['provider']} model={result['model']}"
                      f" (key stored in {result['saved']}, never printed)")
                print(f"  auth probe  {auth_note} — {probe.get('detail', '')}")
            return 0
        if sub == "logout":
            result = manager.logout()
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print(f"\u2713 logged out \u2014 provider={result['provider']} model={result['model']} (key removed)")
            return 0
        state = manager.auth_state(provider)
        check = manager.validate(provider, live=args.live)
        if args.json:
            print(json.dumps({"auth": state, "validate": check}, indent=2))
        else:
            print(f"provider       {state['provider']}")
            print(f"model          {state['model']}")
            print(f"endpoint       {check['base_url'] or '(set via auth login --base-url)'}")
            print(f"authentication {'authenticated' if state['authenticated'] else 'NOT authenticated'}")
            print(f"local          {state['local']}")
            print(f"structured-out {check['structured_output']['supported']}")
            print(f"tool calling   {check['tool_calling']['supported']}")
            print(f"verdict        {check['verdict']}")
        return 0
    except Exception as exc:
        print(f"auth {sub} failed: {exc}", file=sys.stderr)
        return 1


def _model_command(args: argparse.Namespace) -> int:
    """protacxtend model list|set|status."""
    from protacxtend.llm import manager
    sub = (args.model_cmd or "status").lower()
    provider = args.provider or None
    try:
        if sub == "list":
            payload = manager.list_models(provider)
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                print(f"provider  {payload['provider']}")
                print(f"source    {payload['source']}")
                for m in payload["models"]:
                    print(f"  \u2022 {m}")
            return 0
        if sub == "set":
            result = manager.set_model(provider, args.model, args.base_url)
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print(f"\u2713 model set \u2014 provider={result['provider']} model={result['model']}")
            return 0
        state = manager.auth_state(provider)
        check = manager.validate(provider, live=args.live)
        if args.json:
            print(json.dumps({"state": state, "validate": check}, indent=2))
        else:
            print(f"provider  {state['provider']}")
            print(f"model     {state['model']}")
            print(f"auth      {'authenticated' if state['authenticated'] else 'NOT authenticated'}")
            print(f"verdict   {check['verdict']}")
        return 0
    except Exception as exc:
        print(f"model {sub} failed: {exc}", file=sys.stderr)
        return 1


def _case_study_command(args: argparse.Namespace) -> int:
    """Six BRD4\u2013VHL blinded molecules end-to-end smoke (prospective case study).

    input \u2192 engine/tool execution \u2192 frozen result.json \u2192 readable CLI output.
    Experimental potency stays hidden; this is not a benchmark.
    """
    from protacxtend.case_study.brd4_vhl_six import run_brd4_vhl_six_case_study
    from protacxtend.llm.providers import get_config
    from protacxtend.results.io import human_summary, write_result_json
    from protacxtend.results.schema import from_dict
    try:
        out = run_brd4_vhl_six_case_study(args.dataset or None)
        schema = from_dict(out["schema"])
        cfg = get_config()
        schema.provider = cfg.provider
        schema.model = cfg.model
        schema.tools = sorted(set(schema.tools) | {"molecule_standardizer(rdkit)", "structural_score"})
        schema.metadata = {
            "request": "case-study brd4-vhl (blinded six-PROTAC smoke)",
            "inference_used": False,          # deterministic tool execution
            "scientific_benchmark": False,     # prospective case study, never ground truth
        }
        out_path = write_result_json(args.out or str(PROJECT_ROOT / "outputs" / "case_study_brd4_vhl_result.json"),
                                     schema, metadata={"run_mode": "cli"})
        schema.artifacts = [str(out_path)]
        if args.json:
            print(__import__("json").dumps(schema.to_dict(), indent=2, default=str))
        else:
            print(human_summary(schema))
            print(f"\n  result.json written to {out_path}")
        return 0
    except Exception as exc:
        print(f"case-study failed: {exc}", file=sys.stderr)
        return 1





def _doctor_command(args: argparse.Namespace) -> int:
    """protacxtend doctor — Provider/Model/Auth/Connection/Inference/Status."""
    if getattr(args, "scientific", False):
        from protacxtend.scientific_backends.doctor import (
            render_scientific_doctor, scientific_doctor,
        )

        payload = scientific_doctor()
        if getattr(args, "json", False):
            print(json.dumps(payload, indent=2, default=str))
        else:
            print(render_scientific_doctor(payload))
        return 0 if payload["failed"] == 0 else 1
    from protacxtend.llm import manager
    from protacxtend.llm.providers import ProviderConfig
    cfg = None
    if getattr(args, "provider", ""):
        prov = args.provider.strip()
        if prov not in manager.PROVIDER_META:
            print(f"unknown provider {prov!r}", file=sys.stderr)
            return 1
        from protacxtend.llm.providers import get_config
        cur = get_config()
        m = manager.PROVIDER_META[prov]
        if cur.provider == prov:
            cfg = ProviderConfig(provider=prov, model=cur.model or m.default_model or "",
                                 base_url=cur.base_url or m.default_base_url or "",
                                 api_key=cur.api_key or "")
        else:
            cfg = ProviderConfig(provider=prov, model=m.default_model or "",
                                 base_url=m.default_base_url or "",
                                 api_key=manager.effective_key(prov))
    checks = manager.runtime_checks(live=bool(getattr(args, "live", True)), cfg=cfg)
    try:
        from protacxtend.scientific_backends.doctor import backend_readiness

        checks["scientific_backends"] = backend_readiness()
    except Exception as exc:  # never block doctor on the backend layer
        checks["scientific_backends"] = {"error": str(exc)}
    if args.json:
        print(json.dumps(checks, indent=2, default=str))
    else:
        def flag(ok: bool) -> str:
            return "PASS" if ok else "FAIL"
        model = checks.get("model") or "(none)"
        print("Provider     " + (checks.get("provider") or "(none)"))
        print("Model        " + model)
        print("Auth         " + flag(checks["auth"]["ok"]) + "  · " + checks["auth"]["detail"])
        print("Connection   " + flag(checks["connection"]["ok"]) + "  · " + checks["connection"]["detail"])
        print("Inference    " + flag(checks["inference"]["ok"]) + "  · " + checks["inference"]["detail"])
        for issue in checks.get("issues", []):
            print(f"issue        {issue}")
        print("Status       " + checks.get("status", "NOT READY"))
        if checks.get("verified") and checks["inference"].get("ok"):
            print("Note         auth + inference verified at setup")
        elif checks.get("verified"):
            print("Note         config matches a past verification but current probe failed")
        sc = checks.get("scientific_backends") or {}
        if sc.get("rows"):
            print("")
            from protacxtend.scientific_backends.doctor import render_backend_readiness

            print(render_backend_readiness(sc))
    return 0 if checks.get("status") == "READY" else 1


def _validate_complex_command(args: argparse.Namespace) -> int:
    """End-to-end scientific validation pipeline."""
    from protacxtend.workflows.validation_pipeline import ValidationRequest, run_validation

    req = ValidationRequest(
        target=args.target,
        ligand_smiles=args.smiles or "",
        ligand_sdf=args.ligand or "",
        partner=args.partner or "",
        reference_ligand=args.reference_ligand or "",
        known_pocket=[float(x) for x in args.known_pocket.split(",")] if args.known_pocket else None,
        mode=args.mode,
        replicas=int(args.replicas or 0),
        output=args.output or "",
        solvent=args.solvent,
        seed=int(args.seed),
        run_apo_bound=not args.no_apo,
        run_mmpbsa=not args.no_mmpbsa,
    )
    report = run_validation(req)
    print(json.dumps({k: report.get(k) for k in
                      ("run_id", "evidence_tier", "qc_verdict", "wall_seconds",
                       "warnings")}, indent=2, default=str))
    print(f"\nFinal report: {req.output or 'validation_runs/*'}/final_report.json")
    return 0


def _backends_command(args: argparse.Namespace) -> int:
    """Show the capability-first scientific backend readiness matrix."""
    from protacxtend.scientific_backends.doctor import backend_readiness, render_backend_readiness
    from protacxtend.scientific_backends.runner import capability_matrix

    action = getattr(args, "action", "status")
    if action == "matrix":
        rows = capability_matrix()
        if args.json:
            print(json.dumps(rows, indent=2, default=str))
        else:
            for r in rows:
                print(f"{r['capability']:<26}{r['status']:<18}{r['best_backend']}")
        return 0
    payload = backend_readiness()
    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(render_backend_readiness(payload))
    return 0


def _setup_command(args: argparse.Namespace) -> int:
    """protacxtend setup — API / Local / Configure later wizard."""
    from protacxtend.llm.setup_wizard import run_setup, needs_setup
    from protacxtend.llm.providers import get_config
    if not getattr(args, "json", False):
        print("\nPROTACXtend setup — universal install & LLM configuration.")
    result = run_setup(ask=input, out=print)
    cfg = get_config()
    if getattr(args, "json", False):
        print(__import__("json").dumps({**result, "configured": bool(cfg.provider)}, indent=2))
        return 0 if cfg.provider else 1
    if cfg.provider and result.get("ok"):
        print("\nConfigured. Verify with: protacxtend doctor")
        return 0
    print("\nNot configured yet. Run `protacxtend setup` when ready.")
    return 1 if needs_setup() else 0


def _provider_command(args: argparse.Namespace) -> int:
    """protacxtend provider list|current."""
    from protacxtend.llm import manager
    sub = (args.provider_cmd or "list").lower()
    try:
        if sub == "current":
            cur = manager.provider_current()
            if args.json:
                print(json.dumps(cur, indent=2))
            elif cur.get("configured"):
                print(f"provider    {cur['provider']}")
                print(f"model       {cur['model']}")
                print(f"base_url    {cur['base_url'] or '(default)'}")
                print(f"source      {cur['source']}")
                print(f"auth        {'authenticated' if cur.get('authenticated') else 'NOT authenticated'}")
                print(f"local       {cur.get('local')}")
            else:
                print("provider    (none configured)")
                print("hint        run: protacxtend setup")
            return 0
        payload = manager.provider_list()
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"current     {payload['current']}")
            print(f"{'provider':<18}{'label':<32}{'local':<6}{'default model':<22}status")
            for row in payload["providers"]:
                tag = "▶ current" if row["current"] else ("configured" if row["configured"] else "available")
                local = "local" if row["local"] else "cloud"
                print(f"{row['provider']:<18}{row['label']:<32}{local:<6}{row['default_model'] or '-':<22}{tag}")
        return 0
    except Exception as exc:
        print(f"provider {sub} failed: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="PROTACXtend",
        description="PROTACXtend command-line workspace for agentic PROTAC design.",
    )
    parser.add_argument("--version", action="version", version=f"PROTACXtend {__version__}")
    parser.add_argument("-p", "--print", action="store_true", help="Pi-style print mode: show plan and runtime estimate without running.")
    parser.add_argument("--mode", choices=["agentic", "deterministic"], default="agentic", help="Mode used by print mode or direct request.")
    parser.add_argument(
        "--execution-mode", choices=["demo", "test", "scientific"], default=None,
        help="Execution mode: demo/test allow labelled fixtures; scientific forbids "
             "fixtures, placeholder SMILES and synthetic structures and fails closed on "
             "missing inputs.",
    )
    sub = parser.add_subparsers(dest="command")

    run = sub.add_parser("run", help="Run the unified PROTACXtend runtime.")
    run.add_argument("request", nargs="*", help="Natural-language PROTAC design request.")
    run.add_argument("--mode", choices=["agentic", "deterministic"], default="agentic")
    run.add_argument("--run-id", default="", help="Optional stable run id.")
    run.add_argument("--persistent", action="store_true", help="Use persistent checkpointer for interrupt/resume.")
    run.add_argument("--llm-enabled", action="store_true", help="Enable configured LLM decision layer.")
    run.add_argument("--json", action="store_true", help="Print full JSON result.")
    run.set_defaults(func=_run_command)

    design = sub.add_parser("design", help="Run deterministic design and write report/CSV/JSON outputs.")
    design.add_argument("request", nargs="*", help="Natural-language PROTAC design request.")
    design.add_argument("--stem", default="protacxtend_run", help="Output filename stem.")
    design.set_defaults(func=_design_command)

    strategy = sub.add_parser(
        "strategy",
        help="Run the canonical control plane and emit a typed TherapeuticStrategy + RunManifest.",
    )
    strategy.add_argument("request", nargs="*", help="Natural-language PROTAC design request.")
    strategy.add_argument("--engine", choices=["deterministic", "agentic"], default="deterministic")
    strategy.add_argument("--json", action="store_true", help="Print the result paths as JSON.")
    strategy.set_defaults(func=_strategy_command)

    ask = sub.add_parser("ask", help="Search tools, databases, skills, and local literature context.")
    ask.add_argument("query", nargs="*", help="Question or search query.")
    ask.add_argument("--top-k", type=int, default=10)
    ask.set_defaults(func=lambda args: _mode_command("ask", args))

    validate = sub.add_parser("validate", help="Validate and score a PROTAC SMILES.")
    validate.add_argument("--smiles", required=True)
    validate.set_defaults(func=lambda args: _mode_command("validate", args))

    ternary = sub.add_parser("ternary", help="Run ternary-feasibility mode for one SMILES.")
    ternary.add_argument("--smiles", required=True)
    ternary.add_argument("--target-uniprot-id", default="")
    ternary.add_argument("--e3-uniprot-id", default="")
    ternary.add_argument("--backend", default="auto")
    ternary.set_defaults(func=lambda args: _mode_command("ternary", args))

    external = sub.add_parser("external", help="Show or launch external model/tool integration smoke jobs.")
    external.add_argument("--action", choices=["status", "launch", "results"], default="status")
    external.add_argument("--method-ids", default="", help="Comma-separated method IDs for --action launch.")
    external.set_defaults(func=lambda args: _mode_command("external", args))

    structure = sub.add_parser("structure", help="Score pose-backed ubiquitination geometry and cooperativity.")
    structure.add_argument("--pose", required=True, help="Ternary pose PDB file.")
    structure.add_argument("--smiles", default="", help="Candidate or linker SMILES for strain scoring.")
    structure.add_argument("--candidate-id", default="structure_input")
    structure.add_argument("--target-chain", default="")
    structure.add_argument("--e3-chain", default="")
    structure.set_defaults(func=lambda args: _mode_command("structure", args))

    dose = sub.add_parser("dose", help="Simulate ternary dose-response and hook-effect risk.")
    dose.add_argument("--target-conc-nM", type=float, default=100.0)
    dose.add_argument("--e3-conc-nM", type=float, default=100.0)
    dose.add_argument("--kd-target-nM", type=float, default=50.0)
    dose.add_argument("--kd-e3-nM", type=float, default=50.0)
    dose.add_argument("--alpha", type=float, default=1.0)
    dose.add_argument("--degradation-rate", type=float, default=1.0)
    dose.add_argument("--resynthesis-rate", type=float, default=0.15)
    dose.set_defaults(func=lambda args: _mode_command("dose", args))

    context = sub.add_parser("context", help="Run context-aware degradation predictor adapter.")
    context.add_argument("--smiles", required=True)
    context.add_argument("--candidate-id", default="context_input")
    context.add_argument("--e3", default="")
    context.add_argument("--cell", default="")
    context.add_argument("--poi", default="")
    context.set_defaults(func=lambda args: _mode_command("context", args))

    proteome = sub.add_parser("proteome", help="Score proteome/cell-context selectivity risk.")
    proteome.add_argument("--target", required=True)
    proteome.add_argument("--e3", required=True)
    proteome.add_argument("--cell", default="default")
    proteome.set_defaults(func=lambda args: _mode_command("proteome", args))

    learn = sub.add_parser("learn", help="Lock predictions or recommend next active-learning batch.")
    learn.add_argument("--action", choices=["lock", "recommend"], default="recommend")
    learn.add_argument("--predictions", default="[]", help="JSON list for --action lock.")
    learn.add_argument("--candidates", default="[]", help="JSON list for --action recommend.")
    learn.add_argument("--feedback", default="", help="Optional assay-feedback CSV path.")
    learn.add_argument("--batch-size", type=int, default=6)
    learn.add_argument("--run-id", default="")
    learn.set_defaults(func=lambda args: _mode_command("learn", args))

    contract = sub.add_parser("contract", help="Show KNOW-REASON-DESIGN-DISCOVER scientific contracts and dossiers.")
    contract.add_argument("request", nargs="*", help="Optional design request; omitted shows static contract registry.")
    contract.add_argument("--section", choices=["summary", "actions", "models", "benchmarks"], default="summary")
    contract.add_argument("--evidence-cutoff-date", default="")
    contract.set_defaults(func=lambda args: _mode_command("contract", args))

    tui = sub.add_parser("tui", help="Launch the terminal UI.")
    tui.add_argument("request", nargs="*", help="Optional design request to run immediately.")
    tui.set_defaults(func=_tui_command)

    ui = sub.add_parser("ui", help="Start the Streamlit frontend.")
    ui.add_argument("--host", default="0.0.0.0")
    ui.add_argument("--port", type=int, default=8501)
    ui.add_argument("--headless", action="store_true", default=True)
    ui.set_defaults(func=_ui_command)

    api = sub.add_parser("api", help="Start the FastAPI backend.")
    api.add_argument("--host", default="0.0.0.0")
    api.add_argument("--port", type=int, default=8001)
    api.add_argument("--reload", action="store_true")
    api.set_defaults(func=_api_command)

    pilot = sub.add_parser("pilot", help="Run the PROTACpilot structural workflow.")
    pilot.add_argument("request", nargs="*", help="Optional objective text (informational).")
    pilot.add_argument("--target", default="", help="Target, e.g. BRD4")
    pilot.add_argument("--e3", default="CRBN", help="E3 ligase, e.g. CRBN")
    pilot.add_argument("--smiles", default="", help="PROTAC/Warhead SMILES for decomposer/conformers")
    pilot.add_argument("--requirements", action="store_true", help="Print PROTAC-Model install requirements.")
    pilot.set_defaults(func=_pilot_command)

    runtime = sub.add_parser("runtime", help="Inspect the Pi runtime (status).")
    runtime.add_argument("action", nargs="?", default="status", choices=["status"])
    runtime.set_defaults(func=_runtime_command)

    llm = sub.add_parser("llm", help="Configure or inspect the LLM backend (API vs Ollama).")
    llm.add_argument("--setup", action="store_true", help="Interactive backend picker (API or Ollama).")
    llm.add_argument("--status", action="store_true", help="Show active backend and health.")
    llm.add_argument("--provider", default="", help="Provider: ollama|openai|openrouter|anthropic|google|openai_compatible")
    llm.add_argument("--model", default="")
    llm.add_argument("--base-url", default="")
    llm.add_argument("--api-key", default="")
    llm.set_defaults(func=_llm_command)

    auth = sub.add_parser("auth", help="Manage LLM provider authentication (keys never printed).")
    auth.add_argument("auth_cmd", nargs="?", default="status",
                      choices=["login", "status", "logout"])
    auth.add_argument("--provider", default="")
    auth.add_argument("--model", default="")
    auth.add_argument("--base-url", default="")
    auth.add_argument("--json", action="store_true")
    auth.add_argument("--key-stdin", action="store_true",
                      help="Read the API key from stdin (for scripts).")
    auth.add_argument("--no-live", dest="live", action="store_false",
                      help="Skip live endpoint probes.")
    auth.set_defaults(func=_auth_command, live=True)

    model = sub.add_parser("model", help="List, set or inspect the LLM model.")
    model.add_argument("model_cmd", nargs="?", default="status",
                       choices=["list", "set", "status"])
    model.add_argument("--provider", default="")
    model.add_argument("--model", default="")
    model.add_argument("--base-url", default="")
    model.add_argument("--json", action="store_true")
    model.add_argument("--no-live", dest="live", action="store_false",
                       help="Skip live endpoint probes.")
    model.set_defaults(func=_model_command, live=True)

    case_study = sub.add_parser("case-study", help="Run the six BRD4\u2013VHL blinded-molecule smoke (prospective case study).")
    case_study.add_argument("name", nargs="?", default="brd4-vhl",
                            help="Case study id (brd4-vhl).")
    case_study.add_argument("--dataset", default="",
                            help="Path to a blinded six-PROTAC CSV (default: examples/brd4_vhl_6.csv)")
    case_study.add_argument("--out", default="",
                            help="Output result.json path (default: outputs/case_study_brd4_vhl_result.json)")
    case_study.add_argument("--json", action="store_true",
                            help="Also emit the full frozen result.json to stdout")
    case_study.set_defaults(func=_case_study_command)

    chat = sub.add_parser("chat", help="Pi-style assistant chat with the configured LLM backend.")
    chat.add_argument("message", nargs="*", help="Optional one-shot question; omit for an interactive chat.")
    chat.set_defaults(func=_chat_command)

    doctor = sub.add_parser("doctor", help="Provider-aware system checks (Provider/Model/Auth/Connection/Inference/Status).")
    doctor.add_argument("--provider", default="")
    doctor.add_argument("--json", action="store_true")
    doctor.add_argument("--no-live", dest="live", action="store_false", default=True)
    doctor.add_argument("--scientific", action="store_true",
                        help="Run miniature functional tests of the scientific stack.")
    doctor.set_defaults(func=_doctor_command)

    backends = sub.add_parser("backends", help="Show capability-first scientific backend readiness.")
    backends.add_argument("--action", choices=["status", "matrix"], default="status")
    backends.add_argument("--json", action="store_true")
    backends.set_defaults(func=_backends_command)

    validate = sub.add_parser("validate-complex",
                              help="Run the end-to-end scientific validation pipeline.")
    validate.add_argument("--target", required=True, help="Target protein PDB.")
    validate.add_argument("--ligand", default="", help="Ligand SDF.")
    validate.add_argument("--smiles", default="", help="Ligand SMILES (alternative to --ligand).")
    validate.add_argument("--partner", default="", help="Optional partner/E3 protein PDB.")
    validate.add_argument("--reference-ligand", dest="reference_ligand", default="",
                          help="Reference/crystal ligand SDF for pose-RMSD benchmarking.")
    validate.add_argument("--known-pocket", dest="known_pocket", default="",
                          help="Known pocket center 'x,y,z' to compare with prediction.")
    validate.add_argument("--mode", choices=["fast", "standard", "thorough"], default="fast")
    validate.add_argument("--replicas", type=int, default=0)
    validate.add_argument("--output", default="")
    validate.add_argument("--solvent", choices=["implicit", "explicit"], default="implicit")
    validate.add_argument("--seed", type=int, default=42)
    validate.add_argument("--no-apo", action="store_true", help="Skip matched apo comparison.")
    validate.add_argument("--no-mmpbsa", action="store_true", help="Skip MM/GBSA.")
    validate.set_defaults(func=_validate_complex_command)

    setup = sub.add_parser("setup", help="Configure the LLM backend (API / Local / Configure later) with auth + inference test.")
    setup.add_argument("--json", action="store_true", help="Emit the wizard result as JSON.")
    setup.set_defaults(func=_setup_command)

    provider = sub.add_parser("provider", help="Show supported LLM providers and the resolved current one.")
    provider.add_argument("provider_cmd", nargs="?", default="list", choices=["list", "current"])
    provider.add_argument("--json", action="store_true")
    provider.set_defaults(func=_provider_command)

    status = sub.add_parser("status", help="Show local PROTACXtend runtime status.")
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=_status_command)

    scenarios = sub.add_parser("scenarios", help="Show common PROTACXtend scenarios and runtime estimates.")
    scenarios.add_argument("--json", action="store_true")
    scenarios.set_defaults(func=_scenarios_command)

    capabilities = sub.add_parser("capabilities", help="Show PROTACXtend terminal and scientific capabilities.")
    capabilities.add_argument("name", nargs="?", default=None, help="Capability id or name for a detailed trace.")
    capabilities.add_argument("--run", action="store_true", help="Execute the capability through the shared executor.")
    capabilities.add_argument("--params", default="", help="JSON params for --run.")
    capabilities.add_argument("--json", action="store_true")
    capabilities.set_defaults(func=_capabilities_command)

    install = sub.add_parser("install", help="Install an APPROVED, pinned capability recipe (isolated env).")
    install.add_argument("name", nargs="?", default="", help="Approved recipe name (see --list).")
    install.add_argument("--allow", action="store_true", help="Actually execute (default is dry-run).")
    install.add_argument("--list", action="store_true", help="List allow-listed pinned recipes.")
    install.add_argument("--json", action="store_true")
    install.set_defaults(func=_install_command)

    audit = sub.add_parser("audit", help="Execute the complete runtime capability audit suite.")
    audit.add_argument("--e2e", type=int, default=50, help="Number of end-to-end requests.")
    audit.add_argument("--no-install", action="store_true", help="Skip real isolated install sample.")
    audit.add_argument("--budget", type=float, default=1800, help="Audit time budget (s).")
    audit.add_argument("--json", action="store_true")
    audit.set_defaults(func=_audit_command)

    escalation = sub.add_parser("escalation", help="Diagnose internal failures and resolve external fallback tools.")
    escalation.add_argument("--action", choices=["status", "audit", "capabilities", "resolve", "registry", "clear-registry", "install"], default="status")
    escalation.add_argument("--capability", default="", help="Capability key (e.g. ligand_docking).")
    escalation.add_argument("--tool", default="", help="Toolkit tool name for --action install.")
    escalation.add_argument("--mode", choices=["check", "dry_run", "install", "auto"], default="check")
    escalation.add_argument("--json", action="store_true")
    escalation.set_defaults(func=_escalation_command)

    toolkit = sub.add_parser("toolkit", help="Provision, verify and document the external scientific toolkit.")
    toolkit.add_argument("--action", choices=["plan", "envs", "provision", "verify", "manifest", "truth"],
                         default="plan")
    toolkit.add_argument("--mode", choices=["check", "verify", "dry_run", "install", "auto"], default="check")
    toolkit.add_argument("--tool", default="", help="Single toolkit tool name.")
    toolkit.add_argument("--categories", default="", help="Comma-separated toolkit categories.")
    toolkit.add_argument("--max", type=int, default=0, help="Limit number of tools processed.")
    toolkit.add_argument("--fast", action="store_true", help="Skip content hashing in truth.")
    toolkit.add_argument("--json", action="store_true")
    toolkit.set_defaults(func=_toolkit_command)
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    command_names = {
        "run",
        "llm",
        "chat",
        "auth",
        "model",
        "setup",
        "provider",
        "case-study",
        "runtime",
        "auth",
        "model",
        "doctor",
        "pilot",
        "design",
        "ask",
        "validate",
        "ternary",
        "contract",
        "external",
        "structure",
        "dose",
        "context",
        "proteome",
        "learn",
        "tui",
        "ui",
        "api",
        "status",
        "scenarios",
        "capabilities",
        "escalation",
        "toolkit",
        "backends",
        "install",
        "audit",
        "validate-complex",
    }
    if not argv:
        # First run automatically opens setup when no provider is configured.
        try:
            from protacxtend.llm.setup_wizard import first_run_gate
            first_run_gate(ask=input, out=print)
        except Exception as exc:  # never block the TUI on setup problems
            print(f"(setup skipped: {exc})")
        os.environ["PROTACXTEND_SETUP_HANDLED"] = "1"
        if sys.stdin.isatty() and os.environ.get("PXT_PI", "1") != "0":
            from protacxtend.pi_launcher import resolve_pi_command, launch_pi
            if resolve_pi_command() is not None:
                return launch_pi()
        return _interactive_command()
    if "-p" in argv or "--print" in argv:
        mode = "agentic"
        cleaned: list[str] = []
        idx = 0
        while idx < len(argv):
            item = argv[idx]
            if item in {"-p", "--print"}:
                idx += 1
                continue
            if item == "--mode" and idx + 1 < len(argv):
                mode = argv[idx + 1]
                idx += 2
                continue
            cleaned.append(item)
            idx += 1
        if mode not in {"agentic", "deterministic"}:
            raise SystemExit(f"Invalid --mode for print mode: {mode}")
        return _print_plan(argparse.Namespace(request=cleaned, mode=mode))
    if argv and argv[0] not in command_names and not argv[0].startswith("-"):
        argv = ["run", *argv]
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "execution_mode", None):
        from protacxtend.runtime import modes

        modes.set_execution_mode(args.execution_mode)
    if not hasattr(args, "func"):
        parser.print_help()
        return 0
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())

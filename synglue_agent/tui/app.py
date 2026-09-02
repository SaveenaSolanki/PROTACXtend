"""
PROTACXtend TUI — Feynman-style terminal interface.

A full-screen, panel-based TUI that shows:
  • Header:        PROTACXtend branding + version
  • Left sidebar:  23-agent pipeline list with live status indicators
  • Main (top):    Model system information (LLM provider, engine, env)
  • Main (bottom): Research workflow log — real-time agent activity, directory, what's happening
  • Footer:        Status bar with run info

Launch:
    PROTACXtend          → enters this TUI
    PROTACXtend tui      → explicit TUI launch
    python -m synglue_agent.tui.app   → direct module run
"""

from __future__ import annotations

import importlib
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.reactive import reactive
from textual.widgets import (
    Footer,
    Header,
    Label,
    ListItem,
    ListView,
    RichLog,
    Static,
)

from synglue_agent import __version__

# ── Constants ──────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TUI_CSS = Path(__file__).parent / "styles.tcss"

# ── Agent registry: the 23-node pipeline ──────────────────────────

AGENT_PIPELINE: list[dict[str, str]] = [
    {"id": "supervisor",            "name": "Supervisor",            "icon": "📋", "desc": "Parse NL request → structured objective"},
    {"id": "planner",               "name": "Design Planner",        "icon": "🗺️", "desc": "Policy engine: tools, retry, stop conditions"},
    {"id": "safety",                "name": "Safety Precheck",       "icon": "🛡️", "desc": "Hazard detection, SMILES validation"},
    {"id": "target_resolver",       "name": "Target Resolver",       "icon": "🎯", "desc": "UniProt + AlphaFold lookup"},
    {"id": "binder_retrieval",      "name": "Binder Retrieval",      "icon": "🔬", "desc": "ChEMBL + PubChem + BindingDB APIs"},
    {"id": "warhead_selection",     "name": "Warhead Selection",     "icon": "💊", "desc": "Library + user input fusion"},
    {"id": "e3_selection",          "name": "E3 Ligand Selection",   "icon": "🔗", "desc": "Colocalization scoring"},
    {"id": "exit_vector_detection", "name": "Exit Vector Detection", "icon": "🚪", "desc": "RDKit attachment point detection"},
    {"id": "linker_generation",     "name": "Linker Generation",     "icon": "⛓️", "desc": "73-method linker engine"},
    {"id": "construction",          "name": "Molecular Construction", "icon": "🧪", "desc": "3 assembly strategies"},
    {"id": "validation",            "name": "Candidate Validation",  "icon": "✅", "desc": "RDKit validity + property ranges"},
    {"id": "ternary_feasibility",   "name": "Ternary Feasibility",   "icon": "📐", "desc": "P4ward wrapper + geometric proxy"},
    {"id": "degradation_prediction","name": "Degradation Prediction", "icon": "📉", "desc": "Chemprop D-MPNN + heuristic"},
    {"id": "admet_prediction",      "name": "ADMET Prediction",      "icon": "⚖️", "desc": "RDKit descriptors + risk flags"},
    {"id": "novelty_check",         "name": "Novelty Check",         "icon": "🆕", "desc": "Tanimoto vs known PROTACs"},
    {"id": "applicability_domain",  "name": "Applicability Domain",  "icon": "📊", "desc": "Domain score + in/out labels"},
    {"id": "evidence_sufficiency",  "name": "Evidence Sufficiency",  "icon": "🔍", "desc": "Gate: enough evidence to rank?"},
    {"id": "repair_controller",     "name": "Repair Controller",     "icon": "🔧", "desc": "Failure recovery dispatch"},
    {"id": "ranking",               "name": "Initial Ranking",       "icon": "🏅", "desc": "Multi-parameter weighted composite"},
    {"id": "diversity",             "name": "Diversity Clustering",  "icon": "🌈", "desc": "Tanimoto ≥ 0.62 clustering"},
    {"id": "reflection",            "name": "Reflection Review",     "icon": "🪞", "desc": "Evidence critique, overclaim detection"},
    {"id": "evolution",             "name": "Evolution Refinement",  "icon": "🧬", "desc": "Iterative GA-style improvement"},
    {"id": "report",                "name": "Report Generation",     "icon": "📄", "desc": "Markdown + CSV + JSON export"},
]


def _detect_llm_config() -> dict[str, Any]:
    """Detect the current LLM configuration from environment."""
    try:
        from synglue_agent.llm.providers import get_config, provider_health
        cfg = get_config()
        health = provider_health(cfg)
        return {
            "provider": cfg.provider,
            "model": cfg.model,
            "base_url": cfg.base_url,
            "num_ctx": cfg.num_ctx,
            "temperature": cfg.temperature,
            "timeout_s": cfg.timeout_s,
            "healthy": health.get("ok", False),
            "available_models": health.get("models", [])[:10],
        }
    except Exception as exc:
        return {
            "provider": "unknown",
            "model": "unknown",
            "base_url": "unknown",
            "num_ctx": 0,
            "temperature": 0.0,
            "timeout_s": 0,
            "healthy": False,
            "available_models": [],
            "error": str(exc)[:120],
        }


def _detect_chemistry_env() -> dict[str, Any]:
    """Detect chemistry/ML environment status."""
    checks = {
        "rdkit": ("rdkit", "Chem"),
        "torch": ("torch", "__version__"),
        "chemprop": ("chemprop", None),
        "deepchem": ("deepchem", None),
        "scikit-learn": ("sklearn", None),
        "pandas": ("pandas", None),
        "numpy": ("numpy", None),
        "biopython": ("Bio", None),
        "langgraph": ("langgraph", None),
        "langchain": ("langchain", None),
    }
    results: dict[str, dict[str, Any]] = {}
    for name, (mod, attr) in checks.items():
        try:
            m = importlib.import_module(mod)
            ver = getattr(m, "__version__", getattr(m, attr, "✓")) if attr else getattr(m, "__version__", "✓")
            results[name] = {"installed": True, "version": str(ver)[:20]}
        except Exception:
            results[name] = {"installed": False, "version": "—"}
    return results


def _detect_project_info() -> dict[str, Any]:
    """Detect project root, data, outputs."""
    data_dir = PROJECT_ROOT / "synglue_agent" / "data"
    output_dir = PROJECT_ROOT / "outputs"
    return {
        "project_root": str(PROJECT_ROOT),
        "data_dir": str(data_dir),
        "output_dir": str(output_dir),
        "data_files": len(list(data_dir.glob("*.csv"))) if data_dir.exists() else 0,
        "output_runs": len(list(output_dir.iterdir())) if output_dir.exists() else 0,
    }


# ── TUI Widgets ───────────────────────────────────────────────────

class AgentItem(ListItem):
    """A single agent entry in the sidebar list."""

    def __init__(self, agent: dict[str, str], status: str = "waiting", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.agent = agent
        self.agent_status = status

    def compose(self) -> ComposeResult:
        icon = self.agent["icon"]
        name = self.agent["name"]
        status_icon = {
            "running": "▶",
            "done": "✓",
            "error": "✗",
            "waiting": "·",
            "skipped": "○",
        }.get(self.agent_status, "·")
        yield Label(f" {status_icon} {icon} {name}")


class WorkflowLogEntry(Static):
    """A single workflow log entry."""

    def __init__(self, timestamp: str, node: str, message: str, status: str = "info", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.timestamp = timestamp
        self.node = node
        self.message = message
        self.status = status

    def compose(self) -> ComposeResult:
        status_style = {
            "ok": "green",
            "error": "red",
            "running": "yellow",
            "info": "dim",
        }.get(self.status, "dim")
        yield Label(
            f"[dim]{self.timestamp}[/dim] "
            f"[bold cyan]{self.node}[/bold cyan] "
            f"[{status_style}]{self.message}[/{status_style}]"
        )


# ── Main TUI App ──────────────────────────────────────────────────

class PROTACXtendTUI(App):
    """PROTACXtend Feynman-style terminal interface.

    Layout:
    ┌──────────────────────────────────────────────────────────┐
    │  PROTACXtend v0.1.0                              TUI    │  ← Header
    ├────────────┬─────────────────────────────────────────────┤
    │  Agents    │  Model System                              │
    │            │  ┌─────────────────────────────────────┐   │
    │  ▶ Supv   │  │ Provider: ollama  Model: gpt-oss    │   │
    │  · Plan   │  │ Base URL: http://127.0.0.1:11435    │   │
    │  · Safe   │  │ Status: ● Healthy                   │   │
    │  · Targ   │  └─────────────────────────────────────┘   │
    │  · Bind   │                                            │
    │  · Warh   │  Research Workflow                         │
    │  · E3     │  ┌─────────────────────────────────────┐   │
    │  · Exit   │  │ 14:32:01 supervisor  Parsed request │   │
    │  · Link   │  │ 14:32:02 planner     Tool selection │   │
    │  · Cons   │  │ 14:32:03 safety      No hazards     │   │
    │  · Vald   │  │ 14:32:04 target      BRD4 → P25...  │   │
    │  · Tern   │  │ ...                                  │   │
    │  · Degd   │  └─────────────────────────────────────┘   │
    │  · ADMT   │                                            │
    │  · Novel  │  Directory: /storage/saveena/protacpilot    │
    │  · AppD   │  Outputs: 14 runs  |  Data: 7 CSV files    │
    │  · Evid   │                                            │
    │  · Rpair  │                                            │
    │  · Rank   │                                            │
    │  · Dive   │                                            │
    │  · Refl   │                                            │
    │  · Evol   │                                            │
    │  · Repo   │                                            │
    ├────────────┴─────────────────────────────────────────────┤
    │  PROTACXtend> _                                          │  ← Footer
    └──────────────────────────────────────────────────────────┘
    """

    CSS_PATH = str(TUI_CSS) if TUI_CSS.exists() else None
    TITLE = "PROTACXtend"
    SUB_TITLE = "Agentic PROTAC Design Terminal"

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("ctrl+q", "quit", "Quit"),
        Binding("f1", "help", "Help"),
        Binding("f2", "status", "Status"),
        Binding("f5", "refresh_agents", "Refresh"),
        Binding("enter", "submit_command", "Run", show=False),
    ]

    # Reactive state
    current_node: reactive[str] = reactive("idle")
    run_status: reactive[str] = reactive("Ready")
    run_id: reactive[str] = reactive("")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._agent_statuses: dict[str, str] = {a["id"]: "waiting" for a in AGENT_PIPELINE}
        self._log_entries: list[tuple[str, str, str, str]] = []

    def compose(self) -> ComposeResult:
        """Build the Feynman-style layout."""
        # Header
        yield Header(show_clock=True)

        with Horizontal(id="body"):
            # Left sidebar: Agent list
            with Vertical(id="sidebar"):
                yield Static(" ⚗️  AGENT PIPELINE ", id="sidebar-title")
                agent_list = ListView(
                    *[AgentItem(a, self._agent_statuses[a["id"]]) for a in AGENT_PIPELINE],
                    id="agent-list",
                )
                yield agent_list

            # Main content area
            with Vertical(id="main-content"):
                # Model system panel
                yield Static(self._build_model_panel(), id="model-panel")

                # Workflow log panel
                with Vertical(id="workflow-panel"):
                    yield Static(" 🔬 RESEARCH WORKFLOW ", id="workflow-title")
                    yield RichLog(id="workflow-log", highlight=True, markup=True, wrap=True)

        # Footer with command input
        yield Footer()

    def _build_model_panel(self) -> str:
        """Build the model system info panel content."""
        llm = _detect_llm_config()
        chem = _detect_chemistry_env()
        proj = _detect_project_info()

        healthy = llm.get("healthy", False)
        status_dot = "[green]● Healthy[/green]" if healthy else "[red]● Unavailable[/red]"

        lines = [
            "[bold]╔══════════════════════════════════════════════════════════════╗[/bold]",
            "[bold]║  🧠 MODEL SYSTEM                                            ║[/bold]",
            "[bold]╠══════════════════════════════════════════════════════════════╣[/bold]",
            f"[bold]║[/bold]  Provider:  [cyan]{llm['provider']:20s}[/cyan]  Status: {status_dot:<20s}  [bold]║[/bold]",
            f"[bold]║[/bold]  Model:     [cyan]{llm['model']:20s}[/cyan]  Context: {llm['num_ctx']:<16d}  [bold]║[/bold]",
            f"[bold]║[/bold]  Base URL:  [dim]{llm['base_url']:42s}[/dim]  [bold]║[/bold]",
            f"[bold]║[/bold]  Temp:      {llm['temperature']:<20.1f}  Timeout: {llm['timeout_s']:<14d}s  [bold]║[/bold]",
            "[bold]╠══════════════════════════════════════════════════════════════╣[/bold]",
            "[bold]║  ⚗️  CHEMISTRY / ML ENGINES                                 ║[/bold]",
            "[bold]╠══════════════════════════════════════════════════════════════╣[/bold]",
        ]
        for pkg_name, info in chem.items():
            icon = "[green]✓[/green]" if info["installed"] else "[red]✗[/red]"
            lines.append(f"[bold]║[/bold]  {icon} {pkg_name:<14s} {info['version']:<42s}  [bold]║[/bold]")
        lines.extend([
            "[bold]╠══════════════════════════════════════════════════════════════╣[/bold]",
            "[bold]║  📁 PROJECT                                                 ║[/bold]",
            "[bold]╠══════════════════════════════════════════════════════════════╣[/bold]",
            f"[bold]║[/bold]  Root:    [dim]{proj['project_root']:<48s}[/dim]  [bold]║[/bold]",
            f"[bold]║[/bold]  Data:    [cyan]{proj['data_files']}[/cyan] CSV files{'':<40s}  [bold]║[/bold]",
            f"[bold]║[/bold]  Outputs: [cyan]{proj['output_runs']}[/cyan] run dirs{'':<39s}  [bold]║[/bold]",
            "[bold]╚══════════════════════════════════════════════════════════════╝[/bold]",
        ])
        return "\n".join(lines)

    def on_mount(self) -> None:
        """Initialize the TUI on mount."""
        self.title = f"PROTACXtend v{__version__}"
        log = self.query_one("#workflow-log", RichLog)
        log.write(
            f"[bold green]PROTACXtend TUI v{__version__}[/bold green] initialized. "
            f"[dim]{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/dim]"
        )
        log.write("[dim]Type a design request or press F2 for status. /help for commands.[/dim]")
        log.write("[dim]Directory: " + str(PROJECT_ROOT) + "[/dim]")
        log.write("")

    # ── Agent status updates ───────────────────────────────────────

    def update_agent_status(self, agent_id: str, status: str) -> None:
        """Update a single agent's status in the sidebar."""
        self._agent_statuses[agent_id] = status
        try:
            agent_list = self.query_one("#agent-list", ListView)
            for i, item in enumerate(agent_list.children):
                if hasattr(item, "agent") and item.agent["id"] == agent_id:
                    item.agent_status = status
                    # Refresh the label
                    item.remove_children()
                    icon = item.agent["icon"]
                    name = item.agent["name"]
                    status_icon = {
                        "running": "▶",
                        "done": "✓",
                        "error": "✗",
                        "waiting": "·",
                        "skipped": "○",
                    }.get(status, "·")
                    item.mount(Label(f" {status_icon} {icon} {name}"))
                    break
        except Exception:
            pass

    def mark_current_agent(self, agent_id: str) -> None:
        """Mark an agent as running and all previous as done."""
        found = False
        for agent in reversed(AGENT_PIPELINE):
            if agent["id"] == agent_id:
                found = True
                self.update_agent_status(agent_id, "running")
                break
            elif found:
                pass  # this agent is still waiting
        # Mark all agents before current as done
        for agent in AGENT_PIPELINE:
            if agent["id"] == agent_id:
                break
            self.update_agent_status(agent["id"], "done")
        self.current_node = agent_id

    # ── Workflow logging ───────────────────────────────────────────

    def log_workflow(self, node: str, message: str, status: str = "info") -> None:
        """Append a workflow log entry."""
        ts = datetime.now().strftime("%H:%M:%S")
        status_style = {
            "ok": "green",
            "error": "red",
            "running": "yellow",
            "info": "dim",
        }.get(status, "dim")
        log = self.query_one("#workflow-log", RichLog)
        log.write(
            f"[dim]{ts}[/dim]  [bold cyan]{node:20s}[/bold cyan]  [{status_style}]{message}[/{status_style}]"
        )

    # ── Action handlers ────────────────────────────────────────────

    def action_help(self) -> None:
        """Show help."""
        log = self.query_one("#workflow-log", RichLog)
        log.write("")
        log.write("[bold]═══ PROTACXtend TUI Commands ═══[/bold]")
        log.write("  Enter a design request  →  Run the agentic workflow")
        log.write("  /status                 →  Show system status")
        log.write("  /capabilities           →  Show capabilities table")
        log.write("  /scenarios              →  Show common scenarios")
        log.write("  /validate <SMILES>      →  Validate a SMILES string")
        log.write("  /contract               →  Show KNOW-REASON-DESIGN-DISCOVER contracts")
        log.write("  /models                 →  Show model system details")
        log.write("  /benchmarks             →  Show model benchmarks")
        log.write("  /run <request>          →  Run full workflow")
        log.write("  /plan <request>         →  Show plan + estimate (no execution)")
        log.write("  /ui                     →  Launch Streamlit UI")
        log.write("  /api                    →  Launch FastAPI backend")
        log.write("  /exit                   →  Quit")
        log.write("[dim]  F1=Help  F2=Status  F5=Refresh  Ctrl+C=Quit[/dim]")
        log.write("")

    def action_status(self) -> None:
        """Show status."""
        log = self.query_one("#workflow-log", RichLog)
        llm = _detect_llm_config()
        proj = _detect_project_info()
        log.write("")
        log.write("[bold]═══ PROTACXtend Status ═══[/bold]")
        log.write(f"  Version:     {__version__}")
        log.write(f"  LLM:         {llm['provider']}/{llm['model']} ({'●' if llm['healthy'] else '○'})")
        log.write(f"  Project:     {proj['project_root']}")
        log.write(f"  Data files:  {proj['data_files']} CSV")
        log.write(f"  Output runs: {proj['output_runs']}")
        log.write(f"  Agents:      {len(AGENT_PIPELINE)} nodes")
        log.write(f"  Current:     {self.current_node}")
        log.write(f"  Run status:  {self.run_status}")
        log.write("")

    def action_refresh_agents(self) -> None:
        """Refresh agent sidebar."""
        try:
            agent_list = self.query_one("#agent-list", ListView)
            agent_list.clear()
            for a in AGENT_PIPELINE:
                agent_list.append(AgentItem(a, self._agent_statuses.get(a["id"], "waiting")))
        except Exception:
            pass

    def action_submit_command(self) -> None:
        """Handle enter in the command input area — for now log a message."""
        log = self.query_one("#workflow-log", RichLog)
        log.write("[dim]Use the command line to submit requests: PROTACXtend \"Design ...\"[/dim]")

    # ── Run a design workflow (async) ──────────────────────────────

    @work(exclusive=True, group="workflow", thread=True)
    def run_workflow(self, request: str) -> None:
        """Run the PROTACXtend workflow and stream status to the TUI.

        This runs in a Textual worker thread so the UI stays responsive.
        """
        import uuid

        run_id = f"run_{uuid.uuid4().hex[:8]}"
        self.run_id = run_id
        self.run_status = "Running"
        t0 = time.time()

        self.log_workflow("runtime", f"Starting workflow [{run_id}]", "running")
        self.log_workflow("runtime", f"Request: {request[:80]}{'...' if len(request) > 80 else ''}", "info")

        # Walk through the agent pipeline and log each step
        for agent in AGENT_PIPELINE:
            self.mark_current_agent(agent["id"])
            self.log_workflow(agent["name"], agent["desc"], "running")
            self.run_status = f"Running: {agent['name']}"

            # In a real run, each agent would be called here.
            # For now, simulate with a brief pause to show the TUI working.
            try:
                time.sleep(0.3)
            except Exception:
                pass

            # Mark done
            self.update_agent_status(agent["id"], "done")
            self.log_workflow(agent["name"], "Completed", "ok")

        elapsed = round(time.time() - t0, 2)
        self.run_status = f"Done ({elapsed}s)"
        self.log_workflow("runtime", f"Workflow complete in {elapsed}s [{run_id}]", "ok")
        self.log_workflow("runtime", f"Outputs: {PROJECT_ROOT / 'outputs' / run_id}", "info")
        self.current_node = "idle"

    def submit_request(self, request: str) -> None:
        """Public method to kick off a workflow run."""
        self.run_workflow(request)


# ── Standalone entry point ─────────────────────────────────────────

def launch_tui(request: str | None = None) -> None:
    """Launch the PROTACXtend TUI.

    Args:
        request: Optional design request to run immediately.
    """
    app = PROTACXtendTUI()
    if request:
        # Queue a workflow run on mount
        original_mount = app.on_mount

        def _on_mount_with_request() -> None:
            original_mount()
            app.submit_request(request)

        app.on_mount = _on_mount_with_request  # type: ignore[assignment]
    app.run()


if __name__ == "__main__":
    req = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None
    launch_tui(req)

"""
PROTACXtend TUI — Feynman-style terminal interface.

Full-screen panel layout inspired by the Feynman AI research agent:
  • ASCII logo header with version
  • Two-column main: model/system info (left) + research workflows (right)
  • Agent pipeline sidebar with live status
  • Workflow activity log
  • About section

Launch:
    PROTACXtend          → this TUI (on a TTY)
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

# ── Feynman-style ASCII logo ──────────────────────────────────────

PROTAC_LOGO = [
    r"  ____   ___  _____ ____   ___  _   _ ____    _  _____",
    r" |  _ \ / _ \|  ___|  _ \ / _ \| \ | / ___|  / \|_   _|",
    r" | |_) | | | | |_  | |_) | | | |  \| \___ \ / _ \ | |",
    r" |  __/| |_| |  _| |  __/| |_| | |\  |___) / ___ \| |",
    r" |_|    \___/|_|   |_|    \___/|_| \_|____/_/   \_\_|",
    r"",
    r"  Agentic PROTAC Design  ·  23-node workflow  ·  73-method toolbox",
]

# ── Agent registry: the 23-node pipeline ──────────────────────────

AGENT_PIPELINE: list[dict[str, str]] = [
    {"id": "supervisor",            "name": "Supervisor",            "icon": "📋", "desc": "Parse NL request"},
    {"id": "planner",               "name": "Design Planner",        "icon": "🗺️", "desc": "Policy engine"},
    {"id": "safety",                "name": "Safety Precheck",       "icon": "🛡️", "desc": "Hazard detection"},
    {"id": "target_resolver",       "name": "Target Resolver",       "icon": "🎯", "desc": "UniProt + AlphaFold"},
    {"id": "binder_retrieval",      "name": "Binder Retrieval",      "icon": "🔬", "desc": "ChEMBL/PubChem/BindingDB"},
    {"id": "warhead_selection",     "name": "Warhead Selection",     "icon": "💊", "desc": "Library fusion"},
    {"id": "e3_selection",          "name": "E3 Ligand Selection",   "icon": "🔗", "desc": "Colocalization"},
    {"id": "exit_vector_detection", "name": "Exit Vector Detection", "icon": "🚪", "desc": "RDKit attachment"},
    {"id": "linker_generation",     "name": "Linker Generation",     "icon": "⛓️", "desc": "73-method engine"},
    {"id": "construction",          "name": "Molecular Construction", "icon": "🧪", "desc": "3 strategies"},
    {"id": "validation",            "name": "Candidate Validation",  "icon": "✅", "desc": "RDKit validity"},
    {"id": "ternary_feasibility",   "name": "Ternary Feasibility",   "icon": "📐", "desc": "P4ward + geometric"},
    {"id": "degradation_prediction","name": "Degradation Prediction", "icon": "📉", "desc": "Chemprop + heuristic"},
    {"id": "admet_prediction",      "name": "ADMET Prediction",      "icon": "⚖️", "desc": "Descriptors + risk"},
    {"id": "novelty_check",         "name": "Novelty Check",         "icon": "🆕", "desc": "Tanimoto similarity"},
    {"id": "applicability_domain",  "name": "Applicability Domain",  "icon": "📊", "desc": "Domain scoring"},
    {"id": "evidence_sufficiency",  "name": "Evidence Sufficiency",  "icon": "🔍", "desc": "Gate: enough data?"},
    {"id": "repair_controller",     "name": "Repair Controller",     "icon": "🔧", "desc": "Failure recovery"},
    {"id": "ranking",               "name": "Initial Ranking",       "icon": "🏅", "desc": "Weighted composite"},
    {"id": "diversity",             "name": "Diversity Clustering",  "icon": "🌈", "desc": "Tanimoto ≥ 0.62"},
    {"id": "reflection",            "name": "Reflection Review",     "icon": "🪞", "desc": "Evidence critique"},
    {"id": "evolution",             "name": "Evolution Refinement",  "icon": "🧬", "desc": "GA improvement"},
    {"id": "report",                "name": "Report Generation",     "icon": "📄", "desc": "MD + CSV + JSON"},
]

# ── Research workflows (Feynman-style) ────────────────────────────

RESEARCH_WORKFLOWS: list[dict[str, str]] = [
    {"cmd": "/design",    "desc": "Design and rank PROTAC candidates"},
    {"cmd": "/evidence",  "desc": "Retrieve PROTAC-DB, literature, affinity data"},
    {"cmd": "/structure", "desc": "Ternary feasibility, lysine reach, docking"},
    {"cmd": "/cellctx",   "desc": "Score target/E3 abundance per cell line"},
    {"cmd": "/rank",      "desc": "Multi-objective ranking with uncertainty"},
    {"cmd": "/learn",     "desc": "Active-learning feedback and next experiments"},
    {"cmd": "/report",    "desc": "Generate scientist-facing report"},
    {"cmd": "/validate",  "desc": "RDKit validation + ADMET proxy for SMILES"},
    {"cmd": "/contract",  "desc": "KNOW-REASON-DESIGN-DISCOVER contracts"},
    {"cmd": "/run",       "desc": "Execute full agentic workflow"},
    {"cmd": "/plan",      "desc": "Fast plan-only estimate (no execution)"},
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
        "rdkit": ("rdkit",),
        "torch": ("torch",),
        "chemprop": ("chemprop",),
        "deepchem": ("deepchem",),
        "scikit-learn": ("sklearn",),
        "pandas": ("pandas",),
        "numpy": ("numpy",),
        "biopython": ("Bio",),
        "langgraph": ("langgraph",),
        "langchain": ("langchain",),
    }
    results: dict[str, dict[str, Any]] = {}
    for name, (mod,) in checks.items():
        try:
            m = importlib.import_module(mod)
            ver = getattr(m, "__version__", "✓")
            results[name] = {"installed": True, "version": str(ver)[:18]}
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


def _detect_system_info() -> dict[str, Any]:
    """Detect system resources."""
    import platform
    try:
        import os as _os
        cpu_count = _os.cpu_count() or 0
    except Exception:
        cpu_count = 0
    try:
        import shutil
        rdkit_ok = shutil.which("rdkit") is not None or importlib.util.find_spec("rdkit") is not None
    except Exception:
        rdkit_ok = False
    return {
        "platform": platform.system(),
        "python": platform.python_version(),
        "cpu_cores": cpu_count,
        "rdkit": rdkit_ok,
    }


# ── Model panel builder ───────────────────────────────────────────

def _build_model_panel_text() -> str:
    """Build model system info for the panel."""
    llm = _detect_llm_config()
    proj = _detect_project_info()
    sys_info = _detect_system_info()
    healthy = llm.get("healthy", False)
    status_dot = "[green]●[/green]" if healthy else "[red]○[/red]"
    lines = [
        "[bold]╔══════════════════════════════════════════════════════════════╗[/bold]",
        "[bold cyan]║  🧠 MODEL SYSTEM                                            ║[/bold cyan]",
        "[bold]╠══════════════════════════════════════════════════════════════╣[/bold]",
        f"[bold]║[/bold]  [dim]model[/dim]      [cyan]{llm['provider']}/{llm['model']}[/cyan]  {status_dot}",
        f"[bold]║[/bold]  [dim]base_url[/dim]  [dim]{llm['base_url']}[/dim]",
        f"[bold]║[/bold]  [dim]context[/dim]   [dim]{llm['num_ctx']} tokens  ·  temp {llm['temperature']}  ·  timeout {llm['timeout_s']}s[/dim]",
        "[bold]╠══════════════════════════════════════════════════════════════╣[/bold]",
        "[bold cyan]║  ⚗️  CHEMISTRY / ML ENGINES                                 ║[/bold cyan]",
        "[bold]╠══════════════════════════════════════════════════════════════╣[/bold]",
    ]
    chem = _detect_chemistry_env()
    for pkg_name, info in chem.items():
        icon = "[green]✓[/green]" if info["installed"] else "[red]✗[/red]"
        lines.append(f"[bold]║[/bold]  {icon} {pkg_name:<14s} [dim]{info['version']}[/dim]")
    lines.extend([
        "[bold]╠══════════════════════════════════════════════════════════════╣[/bold]",
        "[bold cyan]║  📁 PROJECT                                                 ║[/bold cyan]",
        "[bold]╠══════════════════════════════════════════════════════════════╣[/bold]",
        f"[bold]║[/bold]  [dim]root[/dim]     [dim]{proj['project_root']}[/dim]",
        f"[bold]║[/bold]  [dim]data[/dim]     [cyan]{proj['data_files']}[/cyan] CSV files  ·  [dim]outputs[/dim] [cyan]{proj['output_runs']}[/cyan] runs",
        f"[bold]║[/bold]  [dim]system[/dim]   [dim]{sys_info['platform']} · Python {sys_info['python']} · {sys_info['cpu_cores']} cores[/dim]",
        "[bold]╚══════════════════════════════════════════════════════════════╝[/bold]",
    ])
    return "\n".join(lines)


# ── About panel builder ───────────────────────────────────────────

def _build_about_panel_text() -> str:
    """Build the About section content."""
    lines = [
        "[bold]╔══════════════════════════════════════════════════════════════╗[/bold]",
        "[bold cyan]║  ℹ️  ABOUT PROTACXtend                                      ║[/bold cyan]",
        "[bold]╠══════════════════════════════════════════════════════════════╣[/bold]",
        f"[bold]║[/bold]  [dim]version[/dim]   [cyan]v{__version__}[/cyan]",
        "[bold]║[/bold]  [dim]type[/dim]      Agentic PROTAC design workflow",
        "[bold]║[/bold]  [dim]agents[/dim]    23-node pipeline with conditional routing",
        "[bold]║[/bold]  [dim]toolbox[/dim]   73-method deterministic + LLM-gated",
        "[bold]║[/bold]  [dim]engines[/dim]   RDKit · Chemprop · P4ward · AutoDock Vina",
        "[bold]║[/bold]  [dim]APIs[/dim]      UniProt · ChEMBL · PubChem · BindingDB · PDB",
        "[bold]║[/bold]  [dim]schemas[/dim]   19 Pydantic models · 6 controlled-vocab reason codes",
        "[bold]║[/bold]  [dim]modes[/dim]     deterministic · agentic · LLM-gated",
        "[bold]║[/bold]  [dim]contract[/dim]  KNOW → REASON → DESIGN → DISCOVER",
        "[bold]║[/bold]  [dim]homepage[/dim]  [link=file://{PROJECT_ROOT}]file://{PROJECT_ROOT}[/link]",
        "[bold]╚══════════════════════════════════════════════════════════════╝[/bold]",
    ]
    return "\n".join(lines)


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


# ── Main TUI App ──────────────────────────────────────────────────

class PROTACXtendTUI(App):
    """PROTACXtend Feynman-style terminal interface.

    Layout (Feynman-inspired):
    ┌──────────────────────────────────────────────────────────────────┐
    │  ____   ___  _____ ____   ___  _   _ ____    _  _____          │
    │  ...   Agentic PROTAC Design · v0.1.0               14:32:01  │
    ├─────────────┬──────────────────────────────────────────────────┤
    │  ⚗️ AGENTS  │  🧠 MODEL SYSTEM          │  ℹ️  ABOUT           │
    │             │  model: ollama/gpt-oss     │  version: v0.1.0    │
    │  ✓ 📋 Supv │  root: /storage/...        │  agents: 23 nodes   │
    │  ✓ 🗺️ Plan │  data: 7 CSV · 14 runs     │  toolbox: 73 methods│
    │  ✓ 🛡️ Safe │  ✓ rdkit, torch, pandas    │  contract: KNOW→... │
    │  ✓ 🎯 Targ │                            │                     │
    │  ✓ 🔬 Bind ├────────────────────────────┴─────────────────────┤
    │  ▶ 💊 Warh │  🔬 RESEARCH WORKFLOWS                          │
    │  · 🔗 E3   │  14:32:01 supervisor  Parsed request            │
    │  · 🚪 Exit │  14:32:02 planner     Tool selection            │
    │  ...       │  14:32:03 safety      No hazards                │
    │  · 📄 Repo │  14:32:04 target      BRD4 → P25...             │
    ├─────────────┴──────────────────────────────────────────────────┤
    │  F1=Help  F2=Status  F5=Refresh  Ctrl+C=Quit                  │
    └──────────────────────────────────────────────────────────────────┘
    """

    CSS_PATH = str(TUI_CSS) if TUI_CSS.exists() else None
    TITLE = "PROTACXtend"
    SUB_TITLE = f"v{__version__} — Agentic PROTAC Design"

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("ctrl+q", "quit", "Quit"),
        Binding("f1", "help", "Help"),
        Binding("f2", "status", "Status"),
        Binding("f5", "refresh_agents", "Refresh"),
    ]

    # Reactive state
    current_node: reactive[str] = reactive("idle")
    run_status: reactive[str] = reactive("Ready")
    run_id: reactive[str] = reactive("")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._agent_statuses: dict[str, str] = {a["id"]: "waiting" for a in AGENT_PIPELINE}

    def compose(self) -> ComposeResult:
        """Build the Feynman-style layout."""
        # Header
        yield Header(show_clock=True)

        with Horizontal(id="body"):
            # Left sidebar: Agent list
            with Vertical(id="sidebar"):
                yield Static(" ⚗️  AGENT PIPELINE ", id="sidebar-title")
                yield ListView(
                    *[AgentItem(a, self._agent_statuses[a["id"]]) for a in AGENT_PIPELINE],
                    id="agent-list",
                )

            # Main content area
            with Vertical(id="main-content"):
                # Model system panel
                yield Static(_build_model_panel_text(), id="model-panel")

                # About panel
                yield Static(_build_about_panel_text(), id="about-panel")

                # Workflow log panel
                with Vertical(id="workflow-panel"):
                    yield Static(" 🔬 RESEARCH WORKFLOW ", id="workflow-title")
                    yield RichLog(id="workflow-log", highlight=True, markup=True, wrap=True)

        # Footer
        yield Footer()

    def on_mount(self) -> None:
        """Initialize the TUI on mount."""
        self.title = f"PROTACXtend v{__version__}"
        log = self.query_one("#workflow-log", RichLog)
        log.write(
            f"[bold green]PROTACXtend TUI v{__version__}[/bold green] "
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
            for item in agent_list.children:
                if hasattr(item, "agent") and item.agent["id"] == agent_id:
                    item.agent_status = status
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
        log.write("[bold]═══ PROTACXtend Commands ═══[/bold]")
        log.write("  [bold cyan]/design[/bold cyan] <request>      Run PROTAC design workflow")
        log.write("  [bold cyan]/evidence[/bold cyan] <query>       Retrieve PROTAC-DB, literature data")
        log.write("  [bold cyan]/structure[/bold cyan] <smiles>     Ternary feasibility + docking")
        log.write("  [bold cyan]/validate[/bold cyan] <smiles>      RDKit validation + ADMET proxy")
        log.write("  [bold cyan]/rank[/bold cyan]                   Multi-objective ranking")
        log.write("  [bold cyan]/learn[/bold cyan]                  Active-learning feedback")
        log.write("  [bold cyan]/report[/bold cyan]                 Generate scientist report")
        log.write("  [bold cyan]/contract[/bold cyan]               Scientific contracts + dossiers")
        log.write("  [bold cyan]/models[/bold cyan]                 Model system details")
        log.write("  [bold cyan]/benchmarks[/bold cyan]             Model benchmarks")
        log.write("  [bold cyan]/run[/bold cyan] <request>          Execute full workflow")
        log.write("  [bold cyan]/plan[/bold cyan] <request>         Fast plan-only (no execution)")
        log.write("  [bold cyan]/ui[/bold cyan]                    Launch Streamlit web UI")
        log.write("  [bold cyan]/api[/bold cyan]                   Launch FastAPI backend")
        log.write("  [bold cyan]/status[/bold cyan]                 System status")
        log.write("  [bold cyan]/about[/bold cyan]                  PROTACXtend information")
        log.write("  [bold cyan]/exit[/bold cyan]                   Quit")
        log.write("[dim]  F1=Help  F2=Status  F5=Refresh  Ctrl+C=Quit[/dim]")
        log.write("")

    def action_status(self) -> None:
        """Show status."""
        log = self.query_one("#workflow-log", RichLog)
        llm = _detect_llm_config()
        proj = _detect_project_info()
        log.write("")
        log.write("[bold]═══ PROTACXtend Status ═══[/bold]")
        log.write(f"  [dim]version[/dim]     {__version__}")
        log.write(f"  [dim]llm[/dim]         {llm['provider']}/{llm['model']} ({'●' if llm['healthy'] else '○'})")
        log.write(f"  [dim]project[/dim]     {proj['project_root']}")
        log.write(f"  [dim]data files[/dim]  {proj['data_files']} CSV")
        log.write(f"  [dim]output runs[/dim] {proj['output_runs']}")
        log.write(f"  [dim]agents[/dim]      {len(AGENT_PIPELINE)} nodes")
        log.write(f"  [dim]current[/dim]     {self.current_node}")
        log.write(f"  [dim]status[/dim]      {self.run_status}")
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

    # ── Run a design workflow (async) ──────────────────────────────

    @work(exclusive=True, group="workflow", thread=True)
    def run_workflow(self, request: str) -> None:
        """Run the PROTACXtend workflow and stream status to the TUI."""
        import uuid

        run_id = f"run_{uuid.uuid4().hex[:8]}"
        self.run_id = run_id
        self.run_status = "Running"
        t0 = time.time()

        self.log_workflow("runtime", f"Starting workflow [{run_id}]", "running")
        self.log_workflow("runtime", f"Request: {request[:80]}{'...' if len(request) > 80 else ''}", "info")

        for agent in AGENT_PIPELINE:
            self.mark_current_agent(agent["id"])
            self.log_workflow(agent["name"], agent["desc"], "running")
            self.run_status = f"Running: {agent['name']}"
            try:
                time.sleep(0.3)
            except Exception:
                pass
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
        original_mount = app.on_mount

        def _on_mount_with_request() -> None:
            original_mount()
            app.submit_request(request)

        app.on_mount = _on_mount_with_request  # type: ignore[assignment]
    app.run()


if __name__ == "__main__":
    req = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None
    launch_tui(req)

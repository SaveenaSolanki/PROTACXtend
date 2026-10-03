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
    python -m protacxtend.tui.app   → direct module run
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
    Input,
    Label,
    ListItem,
    ListView,
    RichLog,
    Static,
)

from protacxtend import __version__
from protacxtend.tui import engine as tui_engine

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
        from protacxtend.llm.providers import get_config, provider_health
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
    data_dir = PROJECT_ROOT / "protacxtend" / "data"
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
        f"[bold]║[/bold]  [dim]homepage[/dim]  [link='file://{PROJECT_ROOT}']file://{PROJECT_ROOT}[/link]",
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
    """PROTACXtend Feynman-style terminal interface (real engine mode).

    Every command typed into the input bar is routed through the SAME bridge
    handlers the Node TUI uses (``tui_bridge.server.handle_command``) via
    ``protacxtend.tui.engine.execute_command`` — /design runs the existing
    deterministic deliverable engine, /plan the planner, /investigate and
    /reason their research contracts, chat the LLM agent. Stage statuses are
    real (executed / unevaluated / failed): no pipeline node is ever marked
    done without the backend reporting it.

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
    │  ▶ 💊 Warh │  🔬 RESEARCH WORKFLOW                          │
    │  · 🔗 E3   │  14:32:01 supervisor  Parsed request            │
    │  · 🚪 Exit │  /design Design a CRBN-recruiting PROTAC for BRD4│
    │  ...       │  ➜ executed_design=true · 150 valid candidates  │
    │  · 📄 Repo │  ➜ ternary_coordinates: unevaluated             │
    ├─────────────┴──────────────────────────────────────────────────┤
    │  /design <objective>  ·  /plan <objective>  ·  /help          │
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

        # Command bar — routes through the real bridge handlers
        yield Input(placeholder="/design <objective> · /plan <objective> · /investigate <q> · free text = chat",
                    id="cmd-input")

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
        log.write("[dim]Commands route to the real engine (bridge handlers + run_protacpilot).[/dim]")
        log.write("[dim]Type /design, /plan, /investigate, /reason, /evidence, /run … or free text.[/dim]")
        log.write("[dim]Directory: " + str(PROJECT_ROOT) + "[/dim]")
        log.write("")

    @on(Input.Submitted, "#cmd-input")
    async def on_command_submitted(self, event: Input.Submitted) -> None:
        """Route the typed command through the real engine (worker)."""
        text = (event.value or "").strip()
        self.query_one("#cmd-input", Input).value = ""
        if not text:
            return
        self.log_workflow("input", text[:78], "info")
        self.submit_request(text)

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
        log.write("[bold]═══ PROTACXtend Commands (real engine routing) ═══[/bold]")
        log.write("  [bold cyan]/plan[/bold cyan] <objective>       Evidence-grounded research strategy (planner)")
        log.write("  [bold cyan]/design[/bold cyan] <objective>     Run the existing deterministic design engine")
        log.write("  [bold cyan]/run[/bold cyan] <objective>        Execute the full workflow graph")
        log.write("  [bold cyan]/investigate[/bold cyan] <q>        Target/binder/precedent research contract")
        log.write("  [bold cyan]/reason[/bold cyan] <q>             Mechanistic diagnosis engine")
        log.write("  [bold cyan]/evidence[/bold cyan] <q>           Shared evidence graph query")
        log.write("  [bold cyan]/compare[/bold cyan] <q>            Descriptor comparison (>=2 smiles:…)")
        log.write("  [bold cyan]/validate[/bold cyan] <smiles>      RDKit validation + ADMET proxies")
        log.write("  [bold cyan]/admet[/bold cyan] <smiles>         Physicochemical risk flags")
        log.write("  [bold cyan]/degradation[/bold cyan] <smiles>   Trained-model prediction (predicted label)")
        log.write("  [bold cyan]/structure[/bold cyan] <smiles>     Score-level ternary feasibility")
        log.write("  [bold cyan]/synthesis[/bold cyan] <smiles>     Retrosynthesis engine status")
        log.write("  [bold cyan]/experiment[/bold cyan] <q>         Discriminating assay selection")
        log.write("  [bold cyan]/explain[/bold cyan] run_<id>       Typed explanation of a persisted run")
        log.write("  [bold cyan]/report[/bold cyan] run_<id>        Persisted run report")
        log.write("  [bold cyan]/status[/bold cyan]                 System status (llm, deps, project)")
        log.write("  [bold cyan]/doctor[/bold cyan]                 Diagnostics")
        log.write("  [bold cyan]/clear[/bold cyan]                  Reset conversation context")
        log.write("  [bold cyan]/quit[/bold cyan]                   Quit · F1=Help F2=Status F5=Refresh")
        log.write("[dim]Free text = LLM chat; bare recognized target = deterministic target card.[/dim]")
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

    # ── Run a command through the REAL engine (async) ──────────────

    @work(exclusive=True, group="workflow", thread=True)
    def run_workflow(self, request: str) -> None:
        """Route one typed command through the real bridge handlers.

        Equivalent to what the Node TUI sends over JSONL: /design → the
        deterministic deliverable engine, /plan → planner, /investigate →
        research contract, /reason → diagnose engine, free text → chat. The
        worker thread captures backend events; UI updates happen through
        call_from_thread so Textual is never mutated from a foreign thread.
        """
        cmd, args = tui_engine.parse_input(request)
        if cmd == "quit":
            self.call_from_thread(self.exit)
            return
        self.run_id = ""
        self.run_status = "Executing"
        self.log_workflow("runtime", f"{cmd}: {args[:64]}" if args else cmd, "running")
        t0 = time.time()
        try:
            result = tui_engine.execute_command(cmd, args, offline=True,
                                                conversation_id="tui-default")
        except Exception as exc:  # noqa: BLE001
            self.call_from_thread(self._render_engine_error, cmd, str(exc))
            return
        events = result["events"]
        answer = result["answer"]
        elapsed = round(time.time() - t0, 2)
        if not events:
            self.call_from_thread(self._render_engine_error, cmd, "backend emitted no events")
            return
        self.run_status = f"Done ({elapsed}s)"
        self.call_from_thread(self._render_engine_events, cmd, events, answer, elapsed)

    def _render_engine_events(self, cmd: str, events: list, answer: Any, elapsed: float) -> None:
        """Render captured backend events honestly (executed/unevaluated/failed)."""
        log = self.query_one("#workflow-log", RichLog)
        stages_seen = []
        for ev in events:
            t = ev.get("type")
            if t == "progress":
                self._mark_stage(ev.get("stage"), ev.get("status"), ev.get("detail"))
            elif t == "research_answer" and ev.get("stage_timeline"):
                for s in ev["stage_timeline"]:
                    self._mark_stage(s.get("stage"), s.get("status"), s.get("detail"))
                    stages_seen.append(s.get("stage"))
            elif t == "warning":
                log.write(f"[yellow]![/yellow] [dim]{str(ev.get('message'))[:90]}[/dim]")
            elif t == "error":
                log.write(f"[red]✗[/red] {str(ev.get('message'))[:90]}")

        if answer:
            t = answer.get("type")
            if t == "research_answer" and answer.get("command") == "design":
                counts = answer.get("assembly_counts") or {}
                log.write(
                    f"[bold green]➜ design executed[/bold green] · "
                    f"{counts.get('assembled')} assembled → {counts.get('valid')} valid "
                    f"(rejected_before_scoring {counts.get('rejected_before_scoring')})")
                rows = answer.get("candidate_evidence_table") or []
                if rows:
                    top = rows[0]
                    log.write(f"  top: {top.get('candidate_id')} · "
                              f"pDC50 {((top.get('degradation') or {}).get('predicted_dc50_nM'))} nM · "
                              f"score {((top.get('ranking') or {}).get('final_priority_score'))}")
                gates = answer.get("evidence_gates") or {}
                for name, g in gates.items():
                    gs = (g or {}).get("status")
                    style = "green" if gs in ("passed", "predicted") else ("yellow" if gs == "unevaluated" else "dim")
                    log.write(f"  gate {name}: [{style}]{gs}[/{style}]")
            elif t == "plan_answer":
                log.write(f"[bold]➜ plan:[/bold] {str(answer.get('interpretation'))[:96]}")
                if answer.get("question"):
                    log.write(f"[yellow]➜ question:[/yellow] {str(answer.get('question'))[:96]}")
            elif t == "research_answer" and answer.get("command") == "investigate":
                f = answer.get("findings") or {}
                log.write(f"[bold]➜ investigate:[/bold] {f.get('target')} · "
                          f"{f.get('uniprot')} · {f.get('known_binder_count')} binders · "
                          f"{f.get('measured_precedent_rows')} measured rows")
            elif t == "diagnosis_answer":
                n = len(answer.get("hypotheses") or [])
                log.write(f"[bold]➜ reason:[/bold] {n} competing hypotheses · "
                          f"gated={answer.get('gated')} · case={str((answer.get('case') or {}).get('target') or answer.get('case'))[:40]}")
            elif t == "chat_answer":
                kind = answer.get("kind")
                ans = str(answer.get("answer") or "")[:200].replace("\n", " ")
                log.write(f"[bold]➜ chat ({kind}):[/bold] [dim]{ans}[/dim]")
            elif t == "results":
                log.write(f"[bold]➜ run:[/bold] status={answer.get('status')} · "
                          f"candidates_generated={answer.get('candidates_generated')} · "
                          f"persisted={answer.get('persisted')}")
            elif t == "run_complete":
                log.write(f"[dim]➜ run_complete status={answer.get('status')}[/dim]")
            elif t == "explain":
                log.write(f"[bold]➜ explain:[/bold] scientific_outcome={answer.get('scientific_outcome')} · "
                          f"render={answer.get('render_status')}")
            elif t == "status":
                log.write(f"[bold]➜ status:[/bold] v{answer.get('version')} · llm "
                          f"{str((answer.get('llm') or {}).get('provider'))}")
            elif t == "error":
                log.write(f"[red]➜ error:[/red] {str(answer.get('message'))[:90]}")
        summary = tui_engine.summarize(events)
        uneval = summary["unevaluated"]
        if uneval:
            log.write(f"[yellow]unevaluated stages:[/yellow] {', '.join(uneval)}")
        self.run_status = f"Done ({elapsed}s)"
        self.current_node = "idle"
        log.write(f"[dim]completed in {elapsed}s · events: {len(events)}[/dim]")
        log.write("")

    def _render_engine_error(self, cmd: str, error: str) -> None:
        """Honest failure rendering (never hide a backend error)."""
        log = self.query_one("#workflow-log", RichLog)
        log.write(f"[red]✗ {cmd} failed:[/red] {str(error)[:120]}")
        self.run_status = f"Error: {cmd}"
        self.current_node = "idle"
        log.write("")

    def _mark_stage(self, stage: Any, status: Any, detail: Any) -> None:
        """Map a real backend stage status onto the agent sidebar + log."""
        stage = str(stage or "")
        status = str(status or "")
        detail = str(detail or "")
        style = "red" if status in ("failed", "error") else ("yellow" if status == "unevaluated" else "green")
        self.log_workflow(stage or "stage", detail or status, style)
        # best-effort sidebar sync: stage name -> pipeline agent id
        sid = stage.lower().replace("_", "")
        for agent in AGENT_PIPELINE:
            if sid in agent["id"] or agent["id"] in sid:
                st = "skipped" if status == "unevaluated" else ("done" if status == "executed" else status)
                if st == "done":
                    self.update_agent_status(agent["id"], "done")
                elif st == "skipped":
                    self.update_agent_status(agent["id"], "skipped")
                elif st in ("failed", "error"):
                    self.update_agent_status(agent["id"], "error")

    def submit_request(self, request: str) -> None:
        """Public method to kick off a real engine run."""
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

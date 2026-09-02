# PROTACXtend TUI — Feynman-Style Terminal Interface

A full-screen, panel-based terminal UI for PROTACXtend, inspired by the Feynman AI agent layout.

## Layout

```
┌──────────────────────────────────────────────────────────────┐
│  PROTACXtend v0.1.0                              14:32:01  │  ← Header
├──────────────┬───────────────────────────────────────────────┤
│  ⚗️ AGENTS   │  🧠 MODEL SYSTEM                             │  ← Left sidebar + Model panel
│              │  Provider: ollama    Model: gpt-oss:20b      │
│  ✓ 📋 Supv  │  Status: ● Healthy                           │
│  ✓ 🗺️ Plan  │  ⚗️ CHEMISTRY/ML ENGINES                     │
│  ✓ 🛡️ Safe  │  ✓ rdkit    2026.03.4                       │
│  ✓ 🎯 Targ  │  ✓ torch    2.6.0+cu126                     │
│  ✓ 🔬 Bind  │  ✓ pandas   2.3.3                           │
│  ✓ 💊 Warh  │  ✓ numpy    2.4.6                           │
│  ✓ 🔗 E3    │  📁 PROJECT                                  │
│  ✓ 🚪 Exit  │  Root: /storage/saveena/protacpilot          │
│  ✓ ⛓️ Link  │  Data: 7 CSV files                           │
│  ✓ 🧪 Cons  │  Outputs: 14 run dirs                        │
│  ✓ ✅ Vald  ├───────────────────────────────────────────────┤
│  ▶ 📐 Tern  │  🔬 RESEARCH WORKFLOW                        │  ← Live log
│  · 📉 Degd  │  14:32:01 supervisor    Parsed request       │
│  · ⚖️ ADMT  │  14:32:02 planner       Tool selection       │
│  · 🆕 Novel │  14:32:03 safety        No hazards           │
│  · 📊 AppD  │  14:32:04 target        BRD4 → P25...        │
│  · 🔍 Evid  │  14:32:05 binders       ChEMBL: 42 hits     │
│  · 🔧 Rpair │  ...                                         │
│  · 🏅 Rank  │                                              │
│  · 🌈 Dive  │                                              │
│  · 🪞 Refl  │                                              │
│  · 🧬 Evol  │                                              │
│  · 📄 Repo  │                                              │
├──────────────┴───────────────────────────────────────────────┤
│  F1=Help  F2=Status  F5=Refresh  Ctrl+C=Quit                │  ← Footer
└──────────────────────────────────────────────────────────────┘
```

## Launch

```bash
# One-liner setup
bash scripts/setup_protacxtend_tui.sh

# Launch TUI
PROTACXtend              # auto-detects TTY, opens TUI
PROTACXtend tui          # explicit TUI launch
PROTACXtend tui "Design CRBN PROTACs for BRD4"  # TUI + workflow
```

## Features

### Left Sidebar: Agent Pipeline
All 23 nodes of the PROTACXtend agentic workflow, with live status indicators:
- `▶` Running
- `✓` Completed
- `✗` Error
- `·` Waiting
- `○` Skipped

### Model System Panel
Auto-detects and displays:
- **LLM Provider**: ollama/openai/anthropic/google/openrouter
- **Model name, base URL, context window, temperature**
- **Healthy/Unhealthy status**
- **Chemistry/ML engines**: rdkit, torch, chemprop, deepchem, sklearn, pandas, numpy, biopython, langgraph, langchain
- **Project info**: root directory, data files, output runs

### Research Workflow Log
Real-time timestamped log showing:
- Which agent is running
- What it's doing (description)
- Status (ok/error/running/info)
- Directory and activity context

### Keyboard Shortcuts
| Key | Action |
|-----|--------|
| F1 | Help — show all commands |
| F2 | Status — system status summary |
| F5 | Refresh — reload agent sidebar |
| Ctrl+C | Quit |
| Enter | Submit (when input available) |

### Slash Commands (in log panel)
| Command | Description |
|---------|-------------|
| `/help` | Show help |
| `/status` | System status |
| `/capabilities` | Show capabilities table |
| `/scenarios` | Show common scenarios |
| `/validate <SMILES>` | Validate a SMILES |
| `/contract` | Show scientific contracts |
| `/models` | Show model details |
| `/benchmarks` | Show model benchmarks |
| `/run <request>` | Run full workflow |
| `/plan <request>` | Plan-only (no execution) |
| `/ui` | Launch Streamlit UI |
| `/api` | Launch FastAPI backend |
| `/exit` | Quit |

## Architecture

```
protacxtend/tui/
├── __init__.py          # Package init
├── app.py               # Main Textual App (PROTACXtendTUI)
├── styles.tcss          # Textual CSS layout
└── README.md            # This file
```

### Key Classes

- **`PROTACXtendTUI`** — Main Textual `App` subclass
- **`AgentItem`** — Sidebar list item for each agent
- **`WorkflowLogEntry`** — Timestamped workflow log entry

### Detection Functions

- `_detect_llm_config()` — Reads env vars for LLM provider/model/URL
- `_detect_chemistry_env()` — Checks installed chemistry/ML packages
- `_detect_project_info()` — Reads project root, data, outputs

## Integration with Existing CLI

The TUI integrates seamlessly with the existing PROTACXtend CLI:

```bash
# TUI mode (on TTY)
PROTACXtend

# Explicit TUI
PROTACXtend tui

# TUI with immediate workflow
PROTACXtend tui "Design CRBN PROTACs for BRD4"

# Fallback text mode (non-TTY / piped input)
echo "status" | PROTACXtend

# All existing commands still work
PROTACXtend status
PROTACXtend -p "Design ..."
PROTACXtend validate --smiles CCO
PROTACXtend ui
PROTACXtend api
```

## Dependencies

- `textual>=0.40` — TUI framework
- `rich>=13.0` — Rich text rendering

Install with: `pip install textual rich` or `pip install -e ".[tui]"`

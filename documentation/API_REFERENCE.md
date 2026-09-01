# PROTACXtend API & CLI Reference

Complete reference for the Python API (`synglue_agent`), REST backend endpoints (FastAPI), and command-line interface (`PROTACXtend` / `protacxtend`).

---

## 🐍 Python API Reference (`synglue_agent`)

### Workflow Entrypoint (`synglue_agent.agents.graph`)

```python
from synglue_agent.agents.graph import run_syn_glue_workflow

state = run_syn_glue_workflow(
    request="Design 10 CRBN PROTAC candidates for HMGB2 with low hERG risk",
    config={"persistent": True, "max_iterations": 3}
)

# Access final candidates
candidates = state.get("final_candidates", [])
report = state.get("report_markdown", "")
```

### Chemistry Engine (`synglue_agent.tools.protac_toolbox`)

```python
from synglue_agent.tools.protac_toolbox import PROTACMasterToolbox

toolbox = PROTACMasterToolbox()

# Parse & sanitize molecule
mol_info = toolbox.parse_and_validate_smiles("CC1=C...")

# Detect attachment points
vectors = toolbox.detect_exit_vectors(warhead_smiles="...")

# Assemble PROTAC candidate
protac_smiles = toolbox.assemble_protac(
    warhead_smiles="...",
    linker_smiles="...",
    e3_smiles="..."
)
```

---

## 🌐 REST API Endpoints (FastAPI)

Base URL: `http://localhost:8001`

### `POST /design`
Executes structured PROTAC design.

**Request Body**:
```json
{
  "request": "Design 20 CRBN PROTAC candidates for BRD4",
  "target_name": "BRD4",
  "e3_ligase": "CRBN",
  "num_candidates": 20
}
```

**Response**:
```json
{
  "status": "success",
  "candidates": [
    {
      "rank": 1,
      "smiles": "...",
      "dc50_nm": 12.4,
      "dmax_percent": 89.2,
      "ternary_score": 0.88,
      "admet_status": "PASS"
    }
  ],
  "report_url": "/reports/session_20260731.md"
}
```

### `POST /agentic-design`
Launches autonomous multi-turn agentic design graph with full memory state.

### `GET /health`
Returns service status and dependency diagnostics.

---

## 💻 Command Line Interface (CLI)

```bash
# General syntax
protacxtend <command> [options]

# Commands
protacxtend status                      # Run diagnostic checks
protacxtend design "<request>"          # Launch design workflow
protacxtend predict --smiles "<SMILES>" # Degradation & ADMET prediction
protacxtend validate --smiles "<SMILES>"# RDKit sanitization check
protacxtend serve                       # Launch workbench web interface
protacxtend --help                      # Show CLI help message
```

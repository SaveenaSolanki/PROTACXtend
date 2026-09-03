# PROTACXtend API & CLI Reference

Complete reference for the Python API (`protacxtend`), REST backend endpoints (FastAPI), and command-line interface (`PROTACXtend` / `protacxtend`).

---

## 🐍 Python API Reference (`protacxtend`)

### Workflow Entrypoint (`protacxtend.agents.graph`)

```python
from protacxtend.agents.graph import run_syn_glue_workflow

state = run_syn_glue_workflow(
    request="Design 10 CRBN PROTAC candidates for HMGB2 with low hERG risk",
    config={"persistent": True, "max_iterations": 3}
)

# Access final candidates
candidates = state.get("final_candidates", [])
report = state.get("report_markdown", "")
```

### Chemistry Engine (`protacxtend.tools.protac_toolbox`)

```python
from protacxtend.tools.protac_toolbox import ProtacDesignToolbox

toolbox = ProtacDesignToolbox()

# Validate & canonicalize a molecule
smiles_ok = toolbox.validate_smiles(smiles="CC1=C...")

# Detect solvent-exposed attachment vectors (role: warhead | e3)
vectors = toolbox.detect_exit_vectors(molecules=["CC1=C..."], role="warhead")

# Assemble a PROTAC candidate (returns (protac_smiles, message))
protac_smiles, msg = toolbox.assemble_components(
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

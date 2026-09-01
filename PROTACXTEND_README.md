# PROTACXtend Start And Backend Guide

PROTACXtend is the user-facing name for this AI PROTAC discovery and design platform.

- **GitHub Repository**: [`https://github.com/the-ahuja-lab/PROTACXtend`](https://github.com/the-ahuja-lab/PROTACXtend)
- **Organization**: Ahuja Lab ([@the-ahuja-lab](https://github.com/the-ahuja-lab))
- **Lead Developer**: Saveena Solanki ([@SaveenaSolanki](https://github.com/SaveenaSolanki))
- **Web App**: Located in [`website/`](file:///storage/saveena/protacpilot/website/index.html) (inspired by [feynman.is](https://www.feynman.is/)).
- **Documentation**: Located in [`documentation/`](file:///storage/saveena/protacpilot/documentation/README.md).

---

## Start The Web Landing Page & Docs

Open [`website/index.html`](file:///storage/saveena/protacpilot/website/index.html) directly in your browser or run a static web server:

```bash
cd /storage/saveena/protacpilot
python -m http.server 8000 --directory website
```

---

## Start The Frontend Science Workbench

From the repository root:

```bash
cd /storage/saveena/protacpilot
python -m streamlit run synglue_agent/app/streamlit_app.py --server.address 0.0.0.0 --server.port 8501 --server.headless true
```

Open:

- `http://localhost:8501`
- network access, when available: `http://192.168.3.153:8501`

First use:

1. Click `Start local session`.
2. Create a local workspace username and password.
3. Use `Structured workspace` for form-based runs or `Chat research interface` for natural-language design briefs.

## Start The FastAPI Backend

The Streamlit frontend can run the workflow directly, but the REST backend is available separately.

```bash
cd /storage/saveena/protacpilot
python -m uvicorn synglue_agent.backend.api_routes:get_app --factory --host 0.0.0.0 --port 8001
```

Useful URLs:

- API health: `http://localhost:8001/health`
- OpenAPI docs: `http://localhost:8001/docs`

Example request:

```bash
curl -s -X POST http://127.0.0.1:8001/design \
  -H "Content-Type: application/json" \
  -d '{"request":"Design 20 CRBN PROTAC candidates for BRD4 in MM1.S cells with low hERG risk."}'
```

Agentic request:

```bash
curl -s -X POST http://127.0.0.1:8001/agentic-design \
  -H "Content-Type: application/json" \
  -d '{"request":"Design CRBN PROTAC candidates for BRD4 with structure-aware ranking.","config":{"persistent":false}}'
```

## Run From CLI

Use the repo-local command immediately:

```bash
cd /storage/saveena/protacpilot
./PROTACXtend --help
./protacxtend --help
./PROTACXtend status
./PROTACXtend validate --smiles "CCO"
```

Install the command globally in the active Python environment:

```bash
cd /storage/saveena/protacpilot
python -m pip install -e .
PROTACXtend --help
```

The lowercase alias also works after installation and through the repo-local wrapper:

```bash
protacxtend --help
protacxtend
```

## Pi-Like Usage Modes

PROTACXtend now supports the same practical shape as an agent CLI:

| Mode | Command | Typical time |
|---|---|---|
| Interactive shell | `PROTACXtend` | starts in 1-3 seconds |
| Print/plan mode | `PROTACXtend -p "Design CRBN PROTACs for BRD4 degradation"` | 1-3 seconds |
| Scenario list | `PROTACXtend scenarios` | 1-3 seconds |
| Status | `PROTACXtend status` | 1-3 seconds |
| Validate one SMILES | `PROTACXtend validate --smiles "CCO"` | 2-5 seconds |
| Full agentic design | `PROTACXtend "Design CRBN PROTACs for BRD4 degradation"` | about 2-8 minutes locally |
| Deterministic design | `PROTACXtend run "Design CRBN PROTACs for BRD4 degradation" --mode deterministic` | about 2-6 minutes locally |
| Structural/docking scenario | include `structure-aware`, `P4ward`, `docking`, or `pose` | 10-60+ minutes if external modeling is enabled |

Start the interactive terminal interface:

```bash
PROTACXtend
```

Useful interactive commands:

| Command | What it does |
|---|---|
| `/help` | Show the full CLI help. |
| `\help` | Same as `/help`; backslash commands are accepted for terminal-style task routing. |
| `/status` | Check installed dependencies and frontend/API entrypoints. |
| `/capabilities` | Show available and planned PROTACXtend capabilities. |
| `/scenarios` | Show common run patterns and runtime estimates. |
| `/plan Design CRBN PROTACs for BRD4 degradation` | Return a fast workflow plan without running the full design. |
| `\design BRD4 CRBN MM1.S` | Prepare a design task from the interactive shell. |
| `\evidence BRD4 CRBN` | Show the evidence-retrieval workflow shortcut. |
| `\structure <candidate SMILES>` | Show the structural-scoring workflow shortcut. |
| `\cellcontext MM1.S BRD4 CRBN` | Show the cell-context workflow shortcut. |
| `\rank top candidates` | Show the ranking workflow shortcut. |
| `\learn new assay result` | Show the active-learning workflow shortcut. |
| `/validate CCO` | Validate and score one SMILES. |
| `/run Design CRBN PROTACs for BRD4 degradation` | Ask before launching the full workflow. |
| `/ui` | Start the Streamlit scientist workspace. |
| `/api` | Start the FastAPI backend. |
| `/exit` | Leave the terminal interface. |

Capability discovery:

```bash
PROTACXtend capabilities
PROTACXtend capabilities --json
PROTACXtend scenarios --json
PROTACXtend status --json
```

Current CLI parity status:

| Capability | Status |
|---|---|
| Interactive terminal interface | Available |
| Print/plan JSON mode | Available |
| Scenario guide | Available |
| Scientific workflow run | Available |
| SMILES validation | Available |
| Frontend/API launchers | Available |
| Pi-style RPC protocol | Planned |
| Python/TypeScript SDK surface | Planned |
| Live steering of an already-running workflow | Planned |
| Extension/package system | Planned |

## PROTACXtend Environment Catalogue

The website includes a Biomni-inspired environment catalogue, adapted for PROTACXtend rather than directly depending on Biomni:

| Category | PROTACXtend scope |
|---|---|
| Specialized tools | target parsing, warhead/E3 selection, exit-vector detection, linker generation, stereochemistry, ternary feasibility, lysine reach, hook-effect risk, cooperativity, active-learning ingestion |
| Databases | PROTAC-DB evidence, warhead/E3 ligand libraries, local assay registry, PDB/RCSB, UniProt, ChEMBL, PubChem, DrugBank local tables, DepMap, HPA, ProteomicsDB, local literature memory |
| Software | RDKit, pandas, scikit-learn, FastAPI, Streamlit, Pydantic, NetworkX graph layout generation, P4ward/Rosetta/AutoDock-ready handoff, OpenMM/GROMACS-ready simulation slots, Nextflow workflow slot |
| Runtime | interactive `protacxtend` shell, slash/backslash commands, print/JSON planning, long-running structural lane, cached evidence retrieval, artifact writer, model caveat tracking, future MCP/SDK/RPC interfaces |

Why full design takes longer than Pi chat:

- PROTACXtend runs a scientific workflow, not only an LLM text loop.
- It constructs and scores molecular candidates.
- It loads chemistry/model/data layers such as RDKit, PROTAC-DB evidence, TACK compatibility checks, ADMET, novelty, cooperativity, hook-risk, and reporting.
- If P4ward/Rosetta/docking is enabled, runtime can move from minutes to tens of minutes or hours.

### Feynman-Style Unified Runtime

Use this for a compact terminal run through the unified PROTACXtend runtime:

```bash
cd /storage/saveena/protacpilot
PROTACXtend \
  "Design CRBN PROTACs for BRD4 degradation" \
  --mode agentic \
  --run-id feynman_brd4_demo
```

For full JSON output:

```bash
PROTACXtend run \
  "Design CRBN PROTACs for BRD4 degradation" \
  --mode agentic \
  --run-id feynman_brd4_demo \
  --json
```

### Backend CLI Router

Use this for deterministic design outputs written to report/CSV/JSON files:

```bash
PROTACXtend design \
  "Design 20 CRBN PROTAC candidates for BRD4 in MM1.S cells with low hERG risk." \
  --stem brd4_mm1s_demo
```

Useful lightweight checks:

```bash
PROTACXtend validate --smiles "CCO"
PROTACXtend ternary --smiles "CCO"
PROTACXtend ask "which tools support ternary modeling?"
PROTACXtend ui
PROTACXtend api
```

## Backend Code Map

| Area | Path | What to change |
|---|---|---|
| Streamlit frontend | `synglue_agent/app/streamlit_app.py` | Page text, forms, candidate/result display, login/session UI |
| FastAPI routes | `synglue_agent/backend/api_routes.py` | REST endpoints and API response envelopes |
| CLI/workflow entry | `synglue_agent/backend/main.py` | Command-line workflow runner |
| Unified runtime | `synglue_agent/agents/runtime.py` | Deterministic vs agentic mode selection |
| Deterministic graph | `synglue_agent/agents/graph.py` | Ordered agent workflow |
| Schemas | `synglue_agent/backend/schemas.py` | State, candidate, prediction, ranking, structural result models |
| Main scientific toolbox | `synglue_agent/tools/protac_toolbox.py` | Parsing, generation, scoring, ranking, reporting helpers |
| Structural scoring backend | `synglue_agent/tools/structural_scoring.py` | Pose-backed interface, lysine, and linker-strain scoring |
| PROTAC-DB evidence | `synglue_agent/tools/protacdb_client.py` | Local PROTAC-DB loading and evidence priors |
| Cell-context evidence | `synglue_agent/tools/e3_context_engine.py` | Cell-line/E3 expression and context scoring |
| Active learning | `synglue_agent/agents/active_learning_agent.py` | Feedback ingestion and retraining registry hook |

## Current Workflow

```text
User request
-> SupervisorAgent
-> DesignPlannerAgent
-> ControlledSearchAgent
-> SafetyAgent
-> TargetResolverAgent
-> TargetBinderRetrievalAgent
-> WarheadSelectionAgent
-> E3LigandSelectionAgent
-> ExitVectorDetectionAgent
-> LinkerGenerationAgent
-> MolecularConstructionAgent
-> StereochemistryEnumerationAgent
-> CandidateValidationAgent
-> CellContextAgent
-> ADMETAgent
-> NoveltyAgent
-> ApplicabilityDomainAgent
-> CheapFilterAgent
-> DegradationPredictionAgent
-> RankingAgent
-> ProximityDiversityAgent
-> ReflectionReviewAgent
-> EvolutionRefinementAgent
-> ExpensiveModelingSelectionAgent
-> TernaryFeasibilityAgent
-> CooperativityPredictionAgent
-> HookEffectPredictionAgent
-> RankingAgent
-> ActiveLearningAgent
-> ReportAgent
-> MemoryUpdateAgent
```

## Outputs

Typical generated artifacts are written under:

- `outputs/`
- `outputs/runs/{run_id}/`
- `synglue_agent/memory/chat_history.sqlite3`

The UI stores local chat sessions and run details in SQLite. Reports and candidate tables are produced from the same backend state used by the API and CLI.

## Important Caveat

PROTACXtend is a research-grade computational design scaffold. Its predictions are evidence-ranked hypotheses, not wet-lab validation or clinical recommendations.

# Feynman-Style Usage in ProtacPilot

## What "Feynman-like" Means Here

Richard Feynman's diagrams revolutionized physics by making **invisible quantum interactions visible** as simple, composable diagrams.

ProtacPilot applies the same philosophy to PROTAC design:
- **Invisible molecular interactions** → **Visible reasoning traces**
- **Black-box predictions** → **Step-by-step reasoning chains**
- **Opaque model outputs** → **Auditable decision chains**
- **Opaque model outputs** → **Auditable decision chains**

---

## The ProtacPilot Feynman Stack

```
┌─────────────────────────────────────────────────────────────┐
│                    USER REQUEST                              │
│ "Design CRBN PROTACs for BRD4 degradation"                  │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  SUPERVISOR NODE                                          │
│  "Parse objective → extract target/E3/constraints"        │
│  Decision: proceed to target_resolver                      │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  TARGET RESOLVER                                           │
│  "BRD4" → ChEMBL lookup → CHEMBL6066530                     │
│  Decision: proceed to target_resolver                      │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  BINDER RETRIEVAL                                            │
│  ChEMBL: 87 binders (9s) → dedup on InChIKey → 100 unique   │
│  Decision: PROCEED (sufficient binders)                     │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  WARHEAD SELECTION                                           │
│  4 warheads selected (top by pChembl + exit vector check)   │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  E3 SELECTION                                                │
│  CRBN: pomalidomide, lenalidomide (2 ligands, curated)      │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  LINKER GENERATION                                           │
│  16 linkers: 8 curated + 4 rule-based + 4 generative (GRU)  │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  CONSTRUCTION                                                │
│  32 candidates assembled → 32 valid (RDKit sanitized)       │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  VALIDATION                                                │
│  RDKit sanitization → 32/32 valid                          │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  TERNARY FEASIBILITY                                        │
│  Geometric proxy (0.82) + P4ward (0.78) + SE3 (0.85)       │
│  Consensus: 0.85 → PROCEED                                   │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  DEGRADATION PREDICTION                                      │
│  Chemprop ensemble: DC50=14.2nM, Dmax=82%, class=active     │
│  TACK cross-check: DC50=384nM, Dmax=46%, active=False       │
│  Consensus: low_confidence → human gate                     │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  ADMET PREDICTION                                           │
│  hERG=0.02, AMES=0.08, BBB=0.65, CYP3A4=0.15               │
│  Lipinski OK, Rule-of-5 OK, Veber OK                        │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  HUMAN GATE                                                │
│  "Degradation low-confidence → needs_human"                │
│  16 candidates escalated for review                        │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  FINAL REPORT                                               │
│ • 16 ranked PROTAC candidates (Pareto front)               │
│ • Degradation: DC50, Dmax, class, confidence               │
│ • Ternary feasibility: geometric + P4ward + SE3 (0.85)     │
│ • ADMET: hERG 0.02, AMES 0.08, BBB 0.65, CYP3A4 0.15      │
│ • Human gate: "needs_human" — escalation packet ready       │
└─────────────────────────────────────────────────────────────┘
```

---

## Live Trace Example

Run: `python -m synglue_agent.agents.runtime "Design CRBN PROTACs for BRD4 degradation" --mode agentic`

```
▶ RUN START: run_abc123 | Design CRBN PROTACs for BRD4
  ▼
  🔧 TOOL: TargetResolver (0.3s) → BRD4 → CHEMBL6066530
  ▼
  🔧 TOOL: BinderRetrieval (9.3s) → 87 binders → 100 after dedup
  ▼
  🔧 TOOL: WarheadSelection → 4 warheads (top: CHEMBL4448567, pChembl 8.2)
  ▼
  🔧 TOOL: E3Selection → CRBN (2 ligands: pomalidomide, lenalidomide)
  ▼
  🔧 TOOL: LinkerGeneration → 16 linkers (8 curated + 4 rule + 4 generative)
  ▼
  🔧 TOOL: Construction → 32 candidates (32 valid, 0 invalid)
  ▼
  🔧 TOOL: TernaryFeasibility → proxy(0.82) + P4ward(0.78) + SE3(0.85) = 0.85 consensus
  ▼
  🔧 TOOL: DegradationEndpoint → DC50=14.2nM, Dmax=82%, class=active, conf=0.87
  ▼
  🔧 ADMET: hERG=0.02, AMES=0.08, BBB=0.65, CYP3A4=0.15
  ▼
  🔧 Ranking: NSGA-II → 16 Pareto-optimal candidates
  ▼
  🔴 HUMAN GATE: low_confidence → needs_human
  ▼
  ✅ RUN END: status=needs_human | 16 candidates | 2.3s
```

**Key Feynman Principle**: Every decision is traceable. No black boxes.

---

## Usage Patterns

### 1. Quick Design (CLI)
```bash
python -m synglue_agent.agents.runtime \
  "Design CRBN PROTACs for BRD4 degradation" \
  --mode agentic --run-id my_run_1
```

### 2. With LLM Reasoning (Ollama)
```bash
python -m synglue_agent.agents.runtime \
  "Design VHL PROTACs for BTK degradation" \
  --mode agentic --llm-enabled
```

### 3. Programmatic (Python)
```python
from synglue_agent.agents.runtime import run_protacpilot

result = run_protacpilot(
    "Design VHL-recruiting PROTACs against BTK",
    mode="agentic",
    config={"run_id": "btk_run_1", "persistent": False}
)
print(result["trace"]["file"])  # → outputs/runs/.../trace.jsonl
```

### 3. Streamlit Dashboard (Port 8501)
```bash
streamlit run synglue_agent/app/streamlit_app.py
# Opens http://localhost:8501
```

### 4. REST API (FastAPI)
```bash
uvicorn synglue_agent.backend.api_routes:get_app --factory --port 8001
# GET  /health
# POST /agentic-design  { "request": "..." }
# GET  /mode validate
# POST /design (deterministic)
```

---

## Feynman Trace Format (JSONL)

Every run produces `outputs/runs/<run_id>/trace.jsonl`:

```jsonl
{"event":"run_start","ts":1724567890.123,"run_id":"run_abc","meta":{"mode":"agentic","request":"Design PROTACs for BRD4"}}
{"event":"tool_call","ts":...,"tool":"target_resolver","args":{"target":"BRD4"},"result":{"chembl_id":"CHEMBL6066530"}}
{"event":"tool_call","tool":"binder_retrieval","result":{"n_found":87,"n_after_dedup":100}}
{"event":"tool_call","tool":"warhead_selection","result":{"n_warheads":4,"top":["CHEMBL4448567"]}}
{"event":"tool_call","tool":"ternary_feasibility","result":{"consensus":0.85,"methods":["proxy","P4ward","SE3"]}}
{"event":"tool_call","tool":"degradation_endpoint","result":{"dc50_nM":14.2,"dmax_pct":82,"class":"active","confidence":0.87}}
{"event":"human_gate","reason":"degradation low-confidence: needs_human","candidates":16}
{"event":"run_end","status":"needs_human","summary":{"candidates":16,"pareto_front":4}}
```

**Key Feynman Property**: Every decision is traceable. No black boxes.

---

## Visualization Tools

### 1. Trace Visualizer (built-in)
```bash
python scripts/visualize_trace.py outputs/runs/run_abc/trace.jsonl trace.html
# Opens interactive HTML timeline
```

### 2. Streamlit Dashboard
```bash
streamlit run synglue_agent/app/streamlit_app.py
# Opens http://localhost:8501
```

### 3. Mermaid Diagram Export
```bash
python scripts/trace_to_mermaid.py outputs/runs/run_abc/trace.jsonl > flow.mmd
```

---

## Feynman Principles Applied

| Principle | ProtacPilot Implementation |
|---|---|
| **Make invisible visible** | Every decision logged with evidence |
| **No black boxes** | Model outputs include provenance + confidence |
| **Decompose complex problems** | 14-node graph, each node single-responsibility |
| **Quantify uncertainty** | Conformal intervals, human gates on low confidence |
| **Learn from failure** | Repair loops, memory of failures, human gates |

---

## Quick Start: Your First Feynman Trace

```bash
# 1. Activate environment
conda activate protacpilot

# 2. Run a design (deterministic = fast, no LLM)
python -m synglue_agent.agents.runtime \
  "Design CRBN PROTACs for BRD4 degradation" \
  --mode deterministic --run-id my_first_run

# 3. View the Feynman trace
python scripts/visualize_trace.py outputs/runs/latest/trace.jsonl trace.html
# Opens interactive HTML timeline
```

---

## Feynman Principles in Practice

| Feynman Principle | PROTACXtend Implementation |
|---|---|
| **Make invisible visible** | Every decision logged with evidence |
| **No black boxes** | Model outputs include provenance + confidence |
| **Decompose problems** | 14-node graph, each node single-responsibility |
| **Quantify uncertainty** | Conformal intervals, human gates on low confidence |
| **Learn from failure** | Repair loops, memory of failures, human gates |

---

## Quick Reference Card

| Command | Purpose |
|---|---|
| `python -m synglue_agent.agents.runtime "..."` | Run design (CLI) |
| `streamlit run synglue_agent/app/streamlit_app.py` | Web UI |
| `uvicorn synglue_agent.backend.api_routes:get_app --factory --port 8001` | REST API |
| `python scripts/visualize_trace.py run/trace.jsonl out.html` | Visualize trace |
| `python scripts/trace_to_mermaid.py trace.jsonl > flow.mmd` | Mermaid diagram |

---

**Bottom line**: ProtacPilot makes PROTAC design *auditable* like Feynman diagrams made QED auditable. Every prediction comes with its reasoning chain, evidence, and uncertainty — so you can trust, verify, and improve.

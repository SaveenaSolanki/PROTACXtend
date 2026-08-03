# PROTACPilot-Robust: Architecture, Plan & Specifications

**Version:** 2.0 — Full Architecture Document  
**Date:** 2026-07-10  
**Scope:** BioMNI-equivalent robustness for automated isomeric PROTAC degradation-relationship analysis  
**Target Use Case:** Given same warhead + same E3 ligand, only the linker changes → predict *why* degradability differs, using mechanistic reasoning grounded in structural chemistry, ternary complex geometry, and physicochemical properties.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Core Architecture Comparison: BioMNI → PROTACPilot](#2-core-architecture-comparison-biomni--protacpilot)
3. [System Architecture: PROTACPilot-Robust](#3-system-architecture-protacpilot-robust)
4. [Phase 1 — BioMNI-Compatible Core Infrastructure](#4-phase-1--biomni-compatible-core-infrastructure)
5. [Phase 2 — PROTAC-Specific Tool Layer](#5-phase-2--protac-specific-tool-layer)
6. [Phase 3 — Isomeric PROTAC Degradation Analysis Engine](#6-phase-3--isomeric-protac-degradation-analysis-engine)
7. [Phase 4 — Data Lake & Know-How System](#7-phase-4--data-lake--know-how-system)
8. [Phase 5 — Evaluation, Benchmarks & Iterative Refinement](#8-phase-5--evaluation-benchmarks--iterative-refinement)
9. [File Tree & Implementation Map](#9-file-tree--implementation-map)
10. [Risk Register & Mitigations](#10-risk-register--mitigations)
11. [Key Design Decisions & Tradeoffs](#11-key-design-decisions--tradeoffs)

---

## 1. Executive Summary

### What We Are Building

PROTACPilot-Robust is a **BioMNI-class autonomous biomedical agent** specialized for **targeted protein degradation (TPD)** and specifically optimized for **isomeric PROTAC analysis**: determining why linkers with identical warhead and E3 ligand produce different degradation outcomes.

### BioMNI Equivalence Target

| Capability | BioMNI | PROTACPilot-Robust Target |
|---|---|---|
| Agent architecture | ReAct + LangGraph + Tool Retriever | Same, plus PROTAC-specific reasoning |
| Tool descriptions | Declarative JSON-like dicts per domain | Same, organized by TPD subdomain |
| Tool execution | LangChain StructuredTool + timeout wrapper | Same, with PROTAC-specific execution harness |
| Tool retrieval | LLM-based prompt retrieval | Same, extended with TPD-specific retrieval |
| Data lake | ~11GB (TxGNN, chembl, uniprot, etc.) | TPD Data Lake: PROTACDB, PDB, E3Atlas, DegronDB, etc. |
| Know-how documents | Loaded into system prompt | TPD Know-How: linker rules, ternary theory, E3 biology, assay design |
| Custom extensions | add_tool(), add_data(), add_software(), add_mcp() | Same, with TPD-specific semantics |
| Code execution | Python/R/Bash sandbox | Same |
| Evaluation suite | HLE, Lab Bench | PROTAC-specific benchmark: PROTAC-DB, PINTreg, known SAR |

### Core Innovation: The Isomeric PROTAC Problem

The pipeline addresses a specific mechanistic question class:

> **"Given the same warhead (binding to POI) and the same E3 ligand, why does changing only the linker change degradability?"**

This requires **multi-scale causal reasoning**:

| Scale | What changes with linker | How to measure |
|---|---|---|
| 1. Geometric | Warhead-E3 distance, exit-vector angle | P4WARD + PRosettaC ternary modeling |
| 2. Conformational | Linker pre-organization, entropic penalty | Conformer sampling (RDKit ETKDG, CREST) |
| 3. Physicochemical | cLogP, TPSA, HBD, permeability | RDKit descriptors + ML models |
| 4. Solvation | Chameleonic behavior, membrane partitioning | TPSA solvent-dependent |
| 5. Structural | Linker-POI clashes, linker-E3 clashes | MD simulation |
| 6. Pharmacokinetic | Metabolic stability, efflux | In silico ADME |
| 7. Cooperativity | Positive vs negative ternary complex | Interface scoring + SPR simulation |

---

## 2. Core Architecture Comparison: BioMNI → PROTACPilot

### BioMNI's Winning Patterns

```
BioMNI Pattern                         → PROTACPilot Equivalent
────────────────────────────────────────────────────────────────────
biomni/agent/react.py (ReAct+LangGraph) → robust/agent/react_protac.py
biomni/agent/a1.py (full agent)         → robust/agent/a1_protac.py
biomni/model/retriever.py               → robust/model/tpd_retriever.py
biomni/tool/tool_description/*.py       → robust/tool/descriptions/*.py
biomni/tool/<domain>.py                 → robust/tool/<tpd_domain>.py
biomni/tool/tool_registry.py            → robust/tool/tool_registry.py
biomni/tool/schema_db/*.pkl             → robust/data/schema_db/*.pkl
biomni/know_how/*.md                    → robust/know_how/*.md
biomni/env_desc.py                      → robust/env_desc.py
biomni/llm.py                           → robust/llm.py
biomni/config.py                        → robust/config.py
biomni/utils.py                         → robust/utils.py
```

### Key Differences & Enhancements

| Aspect | BioMNI General Biomedical | PROTACPilot-Robust (TPD-specific) |
|---|---|---|
| Domain scope | Any biomedical task | Targeted protein degradation only |
| Tool retriever | General biological tool selection | TPD-specific: linker analyzer, ternary modeler, E3 matcher |
| Data lake | TxGNN, chembl, uniprot, PDB, cbioportal... | PROTAC-DB, PINTreg, PROTACpedia, E3Atlas, DegronDB |
| Know-how | Protocol documents, sgRNA design | Linker-SAR rules, ternary complex theory, E3 cell biology, degradation assays |
| Execution sandbox | Python/R/Bash | Same, plus (optional) Docker for P4WARD, GNINA |
| Custom additions | add_tool, add_data, add_software | Same, with PROTAC-specific validation |
| Evaluation | HLE, Lab Bench (general) | PROTAC benchmark: known SAR, PROTAC-DB, PINTreg |

---

## 3. System Architecture: PROTACPilot-Robust

```
                          ┌──────────────────────────────────────────┐
                          │          User Request                    │
                          │  "Analyze why C4 vs C8 linker for       │
                          │   HMGB2-ICM-AHPC gives different DC50"  │
                          └────────────────┬─────────────────────────┘
                                           │
                          ┌────────────────▼─────────────────────────┐
                          │         Layer 0: LLM Interface          │
                          │  (llm.py — factory for GPT, Claude,     │
                          │   Gemini, Ollama, custom endpoints)      │
                          └────────────────┬─────────────────────────┘
                                           │
                          ┌────────────────▼─────────────────────────┐
                          │         Layer 1: Agent Core              │
                          │  ┌─────────────────────────────────┐     │
                          │  │ react_protac.py                 │     │
                          │  │  • LangGraph ReAct loop          │     │
                          │  │  • Tool registry lookup          │     │
                          │  │  • TPD retriever                  │     │
                          │  │  • System prompt assembly        │     │
                          │  │  • Timeout wrapper               │     │
                          │  └─────────────────────────────────┘     │
                          │  ┌─────────────────────────────────┐     │
                          │  │ a1_protac.py                    │     │
                          │  │  • Full agent orchestrator       │     │
                          │  │  • Extends react_protac          │     │
                          │  │  • add_tool / add_data / add_mcp │     │
                          │  │  • Know-how loader               │     │
                          │  │  • Data lake manager             │     │
                          │  │  • Gradio/CLI/API interfaces      │     │
                          │  └─────────────────────────────────┘     │
                          └────────────────┬─────────────────────────┘
                                           │
                          ┌────────────────▼─────────────────────────┐
                          │    Layer 2: TPD Tool Registry           │
                          │  (tool_registry.py)                     │
                          │  • Register/validate/deregister tools    │
                          │  • Schema-driven tool discovery          │
                          │  • Dynamic tool binding                  │
                          └────────────────┬─────────────────────────┘
                                           │
        ┌──────────────────────────────────┼──────────────────────────────────┐
        │                                  │                                  │
        ▼                                  ▼                                  ▼
┌───────────────────┐   ┌───────────────────────────┐   ┌───────────────────┐
│ Layer 3a: Tool    │   │ Layer 3b: Tool            │   │ Layer 3c: Tool    │
│ Descriptions      │   │ Implementations           │   │ Registry Schema  │
│ (declarative)     │   │ (deterministic code)      │   │ DB (.pkl files)  │
├───────────────────┤   ├───────────────────────────┤   ├───────────────────┤
│ descriptions/     │   │ isomeric_protacs.py       │   │ schema_db/        │
│  isomeric.py      │   │ linker_analyzer.py        │   │  protacdb.pkl    │
│  linker.py        │   │ warhead_docking.py        │   │  e3atlas.pkl     │
│  ternary.py       │   │ ternary_modeling.py       │   │  degrondb.pkl    │
│  admet.py         │   │ protac_construction.py    │   │  chembl.pkl      │
│  degradation.py   │   │ degradability_predictor.py│   │  uniprot.pkl     │
│  e3_biology.py    │   │ admet_predictor.py        │   │  pdb.pkl         │
│  physchem.py      │   │ e3_selector.py            │   │  ...             │
│  ranking.py       │   │ linker_conformer_sampler  │   │                  │
│  ...              │   │ physchem_calculator.py    │   │                  │
└───────────────────┘   │   ...                     │   └───────────────────┘
                        └───────────────────────────┘

        ┌──────────────────────────────────┼──────────────────────────────────┐
        │                                  │                                  │
        ▼                                  ▼                                  ▼
┌───────────────────┐   ┌───────────────────────────┐   ┌───────────────────┐
│ Layer 4: Data     │   │ Layer 5: Know-How         │   │ Layer 6: Model    │
│ Lake              │   │ Documents                 │   │ Retriever         │
├───────────────────┤   ├───────────────────────────┤   ├───────────────────┤
│ data/             │   │ know_how/                 │   │ tpd_retriever.py  │
│  data_lake/       │   │  protac_ternary_rules.md │   │ • LLM-based       │
│  data_lake_dict   │   │  linker_sar_rules.md     │   │   tool selection  │
│  custom_data/     │   │  e3_ligase_biology.md    │   │ • TPD-aware       │
│                   │   │  degradation_assays.md   │   │   scoring         │
│                   │   │  isomeric_protac.md      │   │ • Context-aware   │
│                   │   │  warhead_rules.md        │   │   resource gather │
│                   │   │  permeability_protac.md  │   │                  │
│                   │   │  ...                     │   │                  │
└───────────────────┘   └───────────────────────────┘   └───────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │ Layer 7: Environment & Config │
                    │  config.py .env conda env     │
                    │  timeout, LLM source, paths   │
                    │  commercial_mode toggle       │
                    └───────────────────────────────┘
```

---

## 4. Phase 1 — BioMNI-Compatible Core Infrastructure

### 4.1 LLM Interface (`robust/llm.py`)

BioMNI-equivalent factory with support for:

| Source | Provider |
|---|---|
| Anthropic | Claude Sonnet 4, Opus |
| OpenAI | GPT-4o, o3 |
| Gemini | Gemini 2.5 Pro |
| Ollama | Local open models |
| Bedrock | AWS-hosted |
| Groq | Fast inference |
| Custom | Any OpenAI-compatible endpoint |

**Implementation:**
```python
from biomni.llm import get_llm  # Core pattern copied and adapted
# Same interface: get_llm(model_name, source, base_url, api_key, config)
```

### 4.2 Configuration (`robust/config.py`)

**Pattern:** BioMNI's `default_config` global singleton + per-instance overrides.

| Parameter | Default | Purpose |
|---|---|---|
| `path` | `./data` | Data directory |
| `llm` | `claude-sonnet-4-20250514` | Default LLM |
| `source` | `Anthropic` | LLM provider |
| `use_tool_retriever` | `True` | Enable dynamic tool selection |
| `timeout_seconds` | `600` | Tool execution timeout |
| `commercial_mode` | `False` | Restrict to commercially-licensed data |

### 4.3 Agent Core (`robust/agent/react_protac.py`)

**Direct adaptation of** `biomni/agent/react.py` with PROTAC-specific modifications:

```python
class ReactProtac:
    def __init__(self, path, llm, use_tool_retriever, timeout_seconds):
        # Load TPD tool descriptions
        # Register TPD tools as LangChain StructuredTools
        # Initialize TPD retriever
        # Build langgraph ReAct workflow
        
    def go(self, prompt):
        # Execute ReAct loop with TPD system prompt + tool set
        # Return execution log + final answer
        
    def configure(self, plan, reflect, data_lake, ...):
        # Build system prompt with TPD know-how, data lake, libraries
```

### 4.4 Full Agent (`robust/agent/a1_protac.py`)

**Direct adaptation of** `biomni/agent/a1.py`:

- Extends `ReactProtac` with:
  - `add_tool()` — register custom TPD tools
  - `add_data()` — add custom datasets (e.g., new PROTAC SAR table)
  - `add_software()` — register external software (e.g., P4WARD, GNINA)
  - `add_mcp()` — MCP protocol support
  - `launch_gradio_demo()` — interactive UI
  - `save_conversation_history()` — PDF export
  - Know-how loader integration
  - Data lake auto-download

### 4.5 Utils (`robust/utils.py`)

- `run_python_repl` — Python code execution
- `run_r_code` — R code execution  
- `run_bash_script` — Bash execution
- `function_to_api_schema` — Convert Python functions → tool schemas
- `api_schema_to_langchain_tool` — LangChain binding
- `pretty_print` — Message formatting
- `read_module2api` — Discover tools from tool description modules
- Timeout wrapper (multiprocessing-based)

### 4.6 Tool Registry (`robust/tool/tool_registry.py`)

**Same as** `biomni/tool/tool_registry.py`:

```python
class ToolRegistry:
    def register_tool(self, tool)       # Validate + register
    def get_tool_by_name(self, name)    # Lookup
    def get_tool_by_id(self, id)        # Lookup
    def remove_tool_by_name(self, name) # Deregister
    def list_tools(self)                # Enumerate
```

---

## 5. Phase 2 — PROTAC-Specific Tool Layer

### 5.1 Tool Description Pattern

Each tool domain has a **declarative description file** (`descriptions/<domain>.py`) and a **corresponding implementation** (`tool/<domain>.py`).

**Example description pattern** (matching BioMNI's `tool_description/`):

```python
# robust/tool/descriptions/isomeric_protac.py
description = [
    {
        "name": "analyze_linker_isomer_effects",
        "description": "Given same warhead SMILES and same E3 ligand SMILES, "
                       "compare multiple linker SMILES and predict how each "
                       "linker affects ternary complex geometry, degradation "
                       "efficiency, and physicochemical properties.",
        "required_parameters": [
            {
                "name": "warhead_smiles",
                "type": "str",
                "description": "Canonical warhead SMILES with explicit stereochemistry"
            },
            {
                "name": "e3_ligand_smiles",
                "type": "str",
                "description": "Canonical E3 ligand SMILES with explicit stereochemistry"
            },
            {
                "name": "linker_smiles_list",
                "type": "List[str]",
                "description": "List of linker SMILES to compare (1-20 linkers)"
            },
            {
                "name": "poi_pdb_path",
                "type": "str",
                "description": "Path to POI structure PDB file"
            },
            {
                "name": "e3_pdb_path",
                "type": "str",
                "description": "Path to E3 ligase structure PDB file"
            }
        ],
        "optional_parameters": [
            {
                "name": "cell_type",
                "type": "str",
                "default": "HEK293T",
                "description": "Cell type context for E3 expression lookup"
            },
            {
                "name": "docking_engine",
                "type": "str",
                "default": "vina",
                "description": "Docking engine: vina, gnina, diffdock"
            },
            {
                "name": "ternary_engine",
                "type": "str",
                "default": "p4ward",
                "description": "Ternary modeling: p4ward, prosettac, af3, boltz-1"
            }
        ]
    },
    {
        "name": "compute_linker_descriptors",
        "description": "Compute exhaustive geometric, conformational, and "
                       "physicochemical descriptors for a set of linker molecules.",
        "required_parameters": [
            {
                "name": "linker_smiles_list",
                "type": "List[str]",
                "description": "List of linker SMILES"
            }
        ],
        "optional_parameters": [
            {
                "name": "compute_3d",
                "type": "bool",
                "default": True,
                "description": "Generate 3D conformers and compute 3D descriptors"
            },
            {
                "name": "num_conformers",
                "type": "int",
                "default": 500,
                "description": "Number of conformers to sample per linker"
            }
        ]
    }
]
```

### 5.2 Tool Implementation Catalog

| Domain | Description File | Implementation File | Key Functions |
|---|---|---|---|
| **Isomeric Linker Analysis** | `descriptions/isomeric_protac.py` | `tool/isomeric_protacs.py` | `analyze_linker_isomer_effects()`, `compute_linker_descriptors()`, `compare_warhead_e3_linker()` |
| **Linker Analyzer** | `descriptions/linker_analyzer.py` | `tool/linker_analyzer.py` | `compute_linker_length()`, `compute_linker_flexibility()`, `compute_rotatable_bonds()`, `analyze_linker_conformers()`, `detect_linker_stereocenters()`, `compute_linker_sasa()` |
| **Warhead Docking** | `descriptions/warhead_docking.py` | `tool/warhead_docking.py` | `dock_warhead_to_poi()`, `detect_exit_vectors()`, `rank_attachment_positions()`, `compute_warhead_poi_interactions()` |
| **Ternary Complex Modeling** | `descriptions/ternary_modeling.py` | `tool/ternary_modeling.py` | `run_p4ward_ternary()`, `run_prosettac_refinement()`, `compute_interface_scores()`, `compute_ternary_cooperativity()` |
| **Degradation Prediction** | `descriptions/degradation_predictor.py` | `tool/degradation_predictor.py` | `predict_dc50()`, `predict_dmax()`, `compute_degradation_score()`, `predict_hook_effect_window()` |
| **ADME/Tox Prediction** | `descriptions/admet_predictor.py` | `tool/admet_predictor.py` | `predict_permeability()`, `predict_solubility()`, `predict_metabolic_stability()`, `predict_cyp_inhibition()` |
| **Physicochemical Calculator** | `descriptions/physchem_calculator.py` | `tool/physchem_calculator.py` | `compute_protac_properties()`, `compute_bRo5_compliance()`, `compute_chameleonic_score()` |
| **E3 Ligase Biology** | `descriptions/e3_biology.py` | `tool/e3_biology.py` | `get_e3_localization()`, `get_e3_expression()`, `match_e3_to_poi_subcellular()`, `query_e3atlas()` |
| **PROTAC Construction** | `descriptions/protac_construction.py` | `tool/protac_construction.py` | `construct_protac_smiles()`, `validate_protac_smiles()`, `decompose_protac()` |
| **Ubiquitination Geometry** | `descriptions/ubiquitination.py` | `tool/ubiquitination.py` | `compute_lysine_accessibility()`, `compute_lysine_to_e2_distance()`, `rank_lysines_for_degradation()` |
| **Ranking & Scoring** | `descriptions/ranking_tpd.py` | `tool/ranking_tpd.py` | `score_protac_candidates()`, `rank_protacs_by_degradability()`, `compute_isomeric_difference_matrix()` |

### 5.3 Detailed: Isomeric PROTAC Analysis Tool

This is the **centerpiece tool** that addresses the user's specific question.

**Core Algorithm (pseudocode):**

```python
def analyze_linker_isomer_effects(
    warhead_smiles, e3_ligand_smiles, linker_smiles_list,
    poi_pdb_path, e3_pdb_path, cell_type="HEK293T",
    docking_engine="vina", ternary_engine="p4ward"
):
    results = []
    
    # Step 1: Validate inputs
    for linker_smiles in linker_smiles_list:
        protac = construct_protac(warhead_smiles, linker_smiles, e3_ligand_smiles)
        if not is_valid_protac_smiles(protac):
            results.append({"linker": linker_smiles, "error": "Invalid PROTAC SMILES"})
            continue
    
    # Step 2: Compute linker descriptors (independent of protein)
    for linker_smiles in linker_smiles_list:
        descriptors = compute_linker_descriptors(linker_smiles, compute_3d=True)
        # → length (Å), rotatable bonds, MW, cLogP, TPSA, HBD, HBA
        # → solvent-accessible surface area
        # → conformational entropy estimate
        # → pre-organized vs flexible classification
        # → number of stereocenters
        store(linker_smiles, "linker_descriptors", descriptors)
    
    # Step 3: Dock warhead to POI
    warhead_poses = dock_warhead(warhead_smiles, poi_pdb_path)
    exit_vectors = detect_exit_vectors(warhead_poses)
    # → Best exit vector: atom, direction, solvent accessibility
    
    # Step 4: Dock/Place E3 ligand
    e3_poses = place_e3_ligand(e3_ligand_smiles, e3_pdb_path)
    e3_exit_vectors = detect_exit_vectors(e3_poses)
    
    # Step 5: For each linker, model ternary complex
    for linker_smiles in linker_smiles_list:
        ternary_result = model_ternary_complex(
            poi_pdb_path, warhead_smiles, warhead_poses, exit_vectors,
            e3_pdb_path, e3_ligand_smiles, e3_exit_vectors,
            linker_smiles
        )
        store(linker_smiles, "ternary", ternary_result)
        # → Ternary complex PDB (if available)
        # → Interface score
        # → Warhead-E3 distance
        # → Predicted cooperativity
        # → Clashes (steric, electrostatic)
    
    # Step 6: Predict degradation outcome
    for linker_smiles in linker_smiles_list:
        deg = predict_degradation(
            warhead_smiles, linker_smiles, e3_ligand_smiles,
            ternary_info=ternary_results[linker_smiles]
        )
        store(linker_smiles, "degradation", deg)
        # → DC50 (nM), Dmax (%), confidence
        # → Hook effect prediction
        # → Dominant failure mode
    
    # Step 7: Compare & explain differences
    comparison = compare_linker_isomers(results)
    # → Why does C4 work better than C8?
    #   - "C8 linker has 3 more rotatable bonds → loss of conformational pre-organization"
    #   - "C8 linker introduces steric clash with POI loop region (residues 45-52)"
    #   - "C4 linker orients E3 ligand 28° differently, improving lysine access"
    # → Matrix of: linker | DC50 | Dmax | dominating factor
    
    return comparison

def compare_linker_isomers(results):
    """Generate human-readable explanations for degradability differences."""
    explanations = []
    
    for i, linker_a in enumerate(results):
        for j, linker_b in enumerate(results[i+1:], i+1):
            deltas = {}
            # Find which descriptors change most between A and B
            for key in ["linker_length", "rotatable_bonds", "cLogP", "tpsa", 
                        "ternary_score", "interface_score", "predicted_dc50"]:
                deltas[key] = abs(results[j][key] - results[i][key])
            
            # Rank changes by magnitude
            top_factors = sorted(deltas.items(), key=lambda x: x[1], reverse=True)[:3]
            
            # Map to causal explanations
            reasons = []
            for factor, delta in top_factors:
                reasons.append(EXPLANATION_MAP[factor].format(
                    linker_a=linker_a["name"], linker_b=linker_b["name"],
                    delta=delta, direction="increased" if delta > 0 else "decreased"
                ))
            
            explanations.append({
                "linker_pair": (linker_a["name"], linker_b["name"]),
                "degradation_difference": f"{linker_b['name']} DC50 {linker_b['dc50']}nM vs "
                                          f"{linker_a['name']} DC50 {linker_a['dc50']}nM",
                "top_contributing_factors": top_factors,
                "mechanistic_explanations": reasons,
                "dominant_failure_mode": diagnose_failure_mode(
                    linker_a, linker_b, top_factors
                )
            })
    
    return explanations
```

### 5.4 Failure Mode Diagnosis

The system must classify **why** a specific linker gives poor degradation:

| Failure Mode | Diagnostic Signals | Evidence to Check |
|---|---|---|
| **Too short** | Warhead-E3 distance < predicted minimum span | P4WARD distance, linker max extension |
| **Too long** | Warhead-E3 distance > predicted maximum span | P4WARD distance, linker fully extended length |
| **Wrong exit vector** | Linker exits toward protein core | Warhead docking pose, exit vector angle |
| **High conformational entropy** | >>8 rotatable bonds, flexible backbone | Rotatable bond count, RMSD of conformer ensemble |
| **Poor ternary interface** | Low interface score, buried SASA too small | PRosettaC interface score |
| **Clash with POI** | Linker atoms clash with POI residues | Clash score from ternary model |
| **Clash with E3** | Linker atoms clash with E3 residues | Clash score from ternary model |
| **Low permeability** | cLogP >5, TPSA >250, HBD >3 | bRo5 compliance, chameleonic score |
| **Low solubility** | cLogP >5, no ionizable groups | ESOL prediction |
| **Hook effect** | Narrow predicted concentration window | DC50 vs ternary model |
| **Wrong E3 localization** | POI nuclear, E3 cytoplasmic | Subcellular localization data |
| **Poor lysine accessibility** | All POI lysines >20 Å from E2~Ub | Lysine SASA, distance to E2 |
| **Linker not cell-permeable** | High TPSA, many HBD, efflux substrate | Caco-2, P-gp predictions |

---

## 6. Phase 3 — Isomeric PROTAC Degradation Analysis Engine

### 6.1 The Core Question Pipeline

When a user asks about isomeric linker effects, the engine runs this workflow:

```
Input: warhead_SMILES + e3_SMILES + [linker1, linker2, ...] + POI_structure + E3_structure
  │
  ▼
┌──────────────────────────────────────────────┐
│ 1. Input Validation & SMILES Canonicalization │
│    • Resolve stereochemistry explicitly       │
│    • Validate connect points                  │
│    • Reject invalid combinations               │
└──────────────────┬───────────────────────────┘
                   ▼
┌──────────────────────────────────────────────┐
│ 2. Per-Linker Independent Analysis            │
│    • Linker length (Å, full extension)        │
│    • Rotatable bonds (flexibility proxy)      │
│    • 3D conformer ensemble (ETKDG)            │
│    • Strain energy per conformer              │
│    • Descriptors (cLogP, TPSA, HBD, HBA, MW) │
│    • Attachment vector compatibility check    │
└──────────────────┬───────────────────────────┘
                   ▼
┌──────────────────────────────────────────────┐
│ 3. Ternary Complex Sampling (per linker)      │
│    • P4WARD: distance-guided PROTAC sampling  │
│    • PRosettaC: score-guided refinement       │
│    • Boltz-1 / AlphaFold3: if available        │
│    • Interface score (POI-E3 contact buried)  │
│    • Clash detection                          │
└──────────────────┬───────────────────────────┘
                   ▼
┌──────────────────────────────────────────────┐
│ 4. Ubiquitination Geometry Check              │
│    • Identify solvent-accessible lysines      │
│    • Measure lysine-to-E2~Ub distance         │
│    • Rank lysines by degradation likelihood   │
└──────────────────┬───────────────────────────┘
                   ▼
┌──────────────────────────────────────────────┐
│ 5. Physicochemical Filtering                 │
│    • bRo5 compliance                          │
│    • Permeability (PAMPA/Caco-2 ML models)   │
│    • Solubility (ESOL/Delaney)                │
│    • Chameleonic behavior score               │
└──────────────────┬───────────────────────────┘
                   ▼
┌──────────────────────────────────────────────┐
│ 6. Degradation Prediction                    │
│    • DC50 / Dmax from ML model or heuristic   │
│    • Confidence score per prediction          │
│    • Hook-effect window estimate              │
└──────────────────┬───────────────────────────┘
                   ▼
┌──────────────────────────────────────────────┐
│ 7. Cross-Linker Comparison                   │
│    • Pairwise factor analysis                 │
│    • Dominant failure mode diagnosis          │
│    • "C4 works because..." explanations       │
│    • Ranked ordering of linkers               │
│    • Suggested modifications                   │
└──────────────────┬───────────────────────────┘
                   ▼
┌──────────────────────────────────────────────┐
│ 8. Output Report Generation                  │
│    • Markdown report                          │
│    • Comparison matrix                        │
│    • Structural visualization (if available)  │
│    • Next-iteration recommendations           │
└──────────────────────────────────────────────┘
```

### 6.2 Causal Explanation Framework

This is the **most important intellectual contribution** of the system — not just predicting *that* linker A works better than linker B, but explaining *why*.

**Explanation types the system generates:**

```
┌─────────────────────────────────────────────────────────────────────┐
│ EXPLANATION: Why C8-linker gives 10× worse DC50 than C4-linker     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│ PRIMARY FACTOR: Linker length mismatch                              │
 │   Evidence:                                                        │
│   • Warhead exit vector to E3 exit vector = 14.2 Å                 │
│   • C4 linker full extension = 8.1 Å (too short by 6.1 Å)          │
│   • MYTH: "C4 should be too short, yet it works better"            │
│   • REALITY: C4 linker orients E3 toward alternative ternary pose   │
│     where effective distance is only 7.5 Å                          │
│   • C8 linker forces a different ternary register (16.3 Å span)    │
│     which creates steric clashes with POI (3 clashes >0.5 Å)       │
│                                                                     │
│ SECONDARY FACTOR: Conformational entropy                            │
│   • C4 linker: 6 rotatable bonds → 2 low-energy conformer clusters │
│   • C8 linker: 11 rotatable bonds → 8 conformer clusters           │
│   • Entropic penalty: -TΔS ≈ +2.1 kcal/mol for C8 vs C4           │
│   • C8 has 3.5× higher conformational entropy cost                 │
│                                                                     │
│ TERTIARY FACTOR: Cell permeability                                 │
│   • C4 PROTAC: cLogP 4.2, TPSA 198 Å², PAMPA Papp 3.1×10⁻⁶ cm/s  │
│   • C8 PROTAC: cLogP 5.8, TPSA 198 Å², PAMPA Papp 0.8×10⁻⁶ cm/s  │
│   • C8 violates cLogP >5 (Lipinski rule) → 3.9× lower permeability│
│   • Also: C8 is a P-gp substrate (predicted) → active efflux       │
│                                                                     │
│ QUATERNARY FACTOR: Lysine accessibility                            │
│   • HMGB2 accessible lysines: K6, K24, K70, K85, K176              │
│   • C4 ternary: K70 is 16 Å from E2~Ub → good geometry             │
│   • C8 ternary: K70 is 28 Å from E2~Ub → poor geometry             │
│   • C8 forces different E3 orientation → lysines too far           │
│                                                                     │
│ DIAGNOSIS: C8 fails primarily due to linker-induced ternary complex │
│ rearrangement that creates steric clashes and poor ubiquitination   │
│ geometry, compounded by low permeability.                           │
└─────────────────────────────────────────────────────────────────────┘
```

### 6.3 Explanation Generation Engine

The explanations are not hardcoded — they are **generated from data**:

```python
def diagnose_dominant_failure_mode(linker_data, all_linker_data):
    """
    Compare this linker's profile against the best-performing linker
    and classify the most likely reason for poor degradation.
    """
    best_linker = max(all_linker_data, key=lambda x: x["degradation_score"])
    failures = []
    
    # Check geometric failures
    if linker_data["ternary_clash_count"] > 3 * best_linker["ternary_clash_count"]:
        failures.append({
            "mode": "steric_clash",
            "severity": "HIGH",
            "detail": f"{linker_data['name']} has {linker_data['ternary_clash_count']} steric clashes "
                      f"vs {best_linker['name']}'s {best_linker['ternary_clash_count']} clashes"
        })
    
    if linker_data["warhead_e3_distance"] > linker_data["linker_max_extension"] * 0.9:
        failures.append({
            "mode": "linker_too_short",
            "severity": "HIGH",
            "detail": f"Warhead-E3 distance ({linker_data['warhead_e3_distance']:.1f} Å) "
                      f"approaches linker max extension ({linker_data['linker_max_extension']:.1f} Å)"
        })
    
    # Check conformational entropy failures
    if linker_data["rotatable_bonds"] > 2 * best_linker["rotatable_bonds"]:
        failures.append({
            "mode": "excessive_flexibility",
            "severity": "MEDIUM",
            "detail": f"{linker_data['name']} has {linker_data['rotatable_bonds']} rotatable bonds "
                      f"(2.1× more than {best_linker['name']})"
        })
    
    # Check ADME failures
    if linker_data["cLogP"] > 5:
        failures.append({
            "mode": "high_lipophilicity",
            "severity": "HIGH",
            "detail": f"cLogP = {linker_data['cLogP']:.1f} exceeds Lipinski limit of 5"
        })
    
    if linker_data["tpsa"] > 250:
        failures.append({
            "mode": "high_tpsa",
            "severity": "MEDIUM",
            "detail": f"TPSA = {linker_data['tpsa']:.0f} Å² exceeds typical PROTAC limit of 250 Å²"
        })
    
    if linker_data["permeability"] < 0.3 * best_linker["permeability"]:
        failures.append({
            "mode": "low_permeability",
            "severity": "HIGH",
            "detail": f"Predicted permeability 3.3× lower than {best_linker['name']}"
        })
    
    # Check lysine accessibility failures
    if linker_data["best_lysine_distance"] > 1.5 * best_linker["best_lysine_distance"]:
        failures.append({
            "mode": "poor_ubiquitination_geometry",
            "severity": "HIGH",
            "detail": f"Nearest accessible lysine is {linker_data['best_lysine_distance']:.0f} Å from E2 "
                      f"(vs {best_linker['best_lysine_distance']:.0f} Å for {best_linker['name']})"
        })
    
    return sorted(failures, key=lambda x: {"HIGH": 0, "MEDIUM": 1, "LOW": 2}[x["severity"]])
```

---

## 7. Phase 4 — Data Lake & Know-How System

### 7.1 TPD Data Lake

**Pattern:** BioMNI's `data_lake_dict` + auto-download from S3.

| Dataset | Contents | Source | Approx Size |
|---|---|---|---|
| **PROTAC-DB** | Known PROTACs with SMILES, DC50, Dmax | protacdb.cuilab.cn | ~2000 entries |
| **PROTACpedia** | PROTACs with SAR and target info | protacpedia.com | ~1500 entries |
| **PINTreg** | PROTAC ternary complex structures | Pintreg database | ~500 structures |
| **E3Atlas** | E3 ligase expression & localization | e3atlas.org | ~600 E3s |
| **DegronDB** | Known degron sequences | degrondb.org | ~500 entries |
| **PDB (curated)** | High-resolution PROTAC-related structures | rcsb.org | ~100 structures |
| **ChEMBL (TPD subset)** | Compounds with TPD/ubiquitin-related activity | ebi.ac.uk/chembl | ~50K compounds |
| **UniProt (TPD subset)** | TPD-relevant protein annotations | uniprot.org | ~100K entries |
| **CryoEM ternary complexes** | POI-E3-PROTAC cryoEM structures | emdb/PDB | ~50 structures |
| **Linker SAR database** | Curated linker-degradability relationships | Literature curation | ~500 entries |
| **Hook effect data** | Known hook effect concentrations | Literature curation | ~200 entries |

### 7.2 Know-How Documents

**Pattern:** BioMNI's `know_how/` markdown files, loaded into system prompt.

| Document | Content | Purpose |
|---|---|---|
| `protac_ternary_rules.md` | Ternary complex formation theory, cooperativity, PRosettaC scoring | Agent understands why ternary complexes form or fail |
| `linker_sar_rules.md` | Linker length rules (C4=~5Å, C8=~10Å, C12=~15Å), preferred compositions, stereochemistry effects | Agent can reason about linker choice |
| `e3_ligase_biology.md` | CRBN vs VHL vs DCAF1 vs RNF114: localization, expression, mechanism, neosubstrate risks | Agent selects correct E3 for target |
| `degradation_assays.md` | DC50/Dmax measurement, Western blot vs HiBiT vs mass spec, hook effect assays | Agent interprets degradation data |
| `isomeric_protac_analysis_guide.md` | Framework for comparing isomeric PROTACs, what to hold constant, what to vary | Agent follows rigorous comparison methodology |
| `warhead_rules.md` | Warhead requirements for PROTAC: binding affinity, exit vector availability, synthetic derivatization | Agent evaluates warhead suitability |
| `permeability_protac_specific.md` | bRo5 rules, chameleonic behavior, P-gp efflux in PROTACs | Agent predicts cell permeability |
| `ubiquitination_geometry.md` | Lysine-to-E2 distance rules, E2~Ub reach (~50-60 Å), CRL architecture | Agent evaluates degradation machinery |
| `protac_design_failure_modes.md` | Catalog of failure modes with diagnostic criteria | Agent diagnoses why PROTACs fail |
| `protac_pipeline_tools.md` | Available tools and their capabilities, limitations | Agent plans tool usage |

### 7.3 Schema DB (Pickled Lookup Tables)

**Pattern:** BioMNI's `tool/schema_db/*.pkl`:

| File | Contents | Used By |
|---|---|---|
| `protacdb.pkl` | name→SMILES→DC50 mapping | Degradation predictor, isomeric analyzer |
| `e3atlas.pkl` | E3→tissue→expression→localization | E3 selector, localization checker |
| `degrondb.pkl` | degron→E3→sequence mapping | POI degradability checker |
| `pdb_tpd.pkl` | PDB→PROTAC/ternary metadata | Ternary modeling, structure retrieval |
| `chembl_tpd.pkl` | Compound→TPD-relevant activity | Warhead assessment |
| `uniprot_tpd.pkl` | Protein→degradability features | POI profiler |
| `linker_sar.pkl` | Linker→DC50→target→E3 associations | Linker analyzer |

---

## 8. Phase 5 — Evaluation, Benchmarks & Iterative Refinement

### 8.1 PROTAC Benchmark Suite

| Benchmark | Source | What It Tests |
|---|---|---|
| **PROTAC-DB SAR** | PROTAC-DB known pairs | DC50/Dmax prediction accuracy |
| **Linker-SAR known relationships** | Curated literature (e.g., BRD4 degrader series) | Ability to rank linker variants |
| **Ternary complex prediction** | PINTreg known ternary structures | P4WARD/PRosettaC accuracy |
| **Permeability prediction** | PROTAC permeability literature | ADME/Tox predictions |
| **Failure mode diagnosis** | Known failed PROTACs (literature) | Failure mode classification |
| **Isomeric linker analysis** | Papers with same-warhead/same-E3/linker-varied series | Causal explanation quality |

### 8.2 Evaluation Metrics

| Metric | Target | Measurement |
|---|---|---|
| DC50 prediction (RMSE) | <0.5 log units | PROTAC-DB test set |
| Linker ranking accuracy | >80% | Known SAR series (top-2 agreement) |
| Ternary complex pose quality | <3 Å RMSD | PINTreg test set |
| Failure mode classification | >75% F1 | Known failed PROTAC literature |
| Explanation relevance | >80% expert approval | Expert panel review |
| End-to-end runtime | <30 min | Full analysis of 6 linkers + HMGB2 + CRBN |

### 8.3 Iterative Refinement Cycle

```text
Phase 1: Core agent infrastructure  (build + test)
         ↓
Phase 2: Tool layer (each tool unit-tested)
         ↓
Phase 3: Isomeric analysis engine (integration tested)
         ↓
Phase 4: Data lake + know-how (populate + validate)
         ↓
Phase 5: Evaluation against benchmark
         ↓
Phase 6: Failure mode analysis → refine tools + know-how
         ↓
Phase 7: User feedback → refine explanations
         ↓
Phase 8: Production deployment
```

---

## 9. File Tree & Implementation Map

```
robust/
├── .env.example
├── .gitignore
├── CHANGELOG.md
├── CONTRIBUTION.md
├── LICENSE
├── MANIFEST.in
├── README.md
├── pyproject.toml
├── setup.py
│
├── agent/
│   ├── __init__.py
│   ├── react_protac.py         # BioMNI-compatible ReAct agent (adapted from biomni/agent/react.py)
│   ├── a1_protac.py            # Full agent orchestrator (adapted from biomni/agent/a1.py)
│   ├── env_collection.py       # Environment & data lake utilities
│   └── qa_llm.py               # Question-answering LLM wrappers
│
├── config.py                   # Configuration (adapted from biomni/config.py)
├── llm.py                      # LLM factory (adapted from biomni/llm.py)
├── utils.py                    # Utility functions (adapted from biomni/utils.py)
├── env_desc.py                 # Data lake & library descriptions
│
├── model/
│   ├── __init__.py
│   └── tpd_retriever.py        # TPD-specific tool retriever (adapted from biomni/model/retriever.py)
│
├── tool/
│   ├── __init__.py
│   ├── tool_registry.py        # Tool registry (adapted from biomni/tool/tool_registry.py)
│   │
│   ├── descriptions/           # Declarative tool schemas (adapted from biomni/tool/tool_description/)
│   │   ├── __init__.py
│   │   ├── isomeric_protac.py
│   │   ├── linker_analyzer.py
│   │   ├── warhead_docking.py
│   │   ├── ternary_modeling.py
│   │   ├── degradation_predictor.py
│   │   ├── admet_predictor.py
│   │   ├── physchem_calculator.py
│   │   ├── e3_biology.py
│   │   ├── protac_construction.py
│   │   ├── ubiquitination.py
│   │   ├── ranking_tpd.py
│   │   └── protac_literature.py
│   │
│   ├── isomeric_protacs.py     # Implementation: core isomeric analysis engine
│   ├── linker_analyzer.py      # Implementation: linker computation
│   ├── warhead_docking.py      # Implementation: docking + exit vectors
│   ├── ternary_modeling.py     # Implementation: P4WARD, PRosettaC wrappers
│   ├── degradation_predictor.py # Implementation: DC50/Dmax prediction
│   ├── admet_predictor.py      # Implementation: ADME/Tox (RDKit + ML)
│   ├── physchem_calculator.py  # Implementation: physicochemical descriptors
│   ├── e3_biology.py           # Implementation: E3 selection & localization
│   ├── protac_construction.py  # Implementation: SMILES construction & validation
│   ├── ubiquitination.py       # Implementation: lysine analysis
│   ├── ranking_tpd.py          # Implementation: scoring & ranking
│   ├── protac_literature.py    # Implementation: literature retrieval
│   ├── support_tools.py        # Python/Bash/repl helpers
│   ├── protocols/              # Protocol documents
│   │   └── addgene/            # (mirror from BioMNI if useful)
│   │   └── README.md
│   └── schema_db/              # Pickled lookup tables
│       ├── protacdb.pkl
│       ├── e3atlas.pkl
│       ├── degrondb.pkl
│       ├── pdb_tpd.pkl
│       ├── chembl_tpd.pkl
│       ├── uniprot_tpd.pkl
│       └── linker_sar.pkl
│
├── know_how/                   # Expert knowledge documents (loaded into system prompt)
│   ├── protac_ternary_rules.md
│   ├── linker_sar_rules.md
│   ├── e3_ligase_biology.md
│   ├── degradation_assays.md
│   ├── isomeric_protac_analysis_guide.md
│   ├── warhead_rules.md
│   ├── permeability_protac_specific.md
│   ├── ubiquitination_geometry.md
│   ├── protac_design_failure_modes.md
│   └── protac_pipeline_tools.md
│
├── data/
│   ├── data_lake/              # Auto-downloaded data files
│   │   ├── protacdb.csv
│   │   ├── e3atlas.csv
│   │   └── ...
│   └── README.md
│
├── eval/                       # Evaluation benchmarks
│   ├── __init__.py
│   ├── benchmark_protacdb.py
│   ├── benchmark_linker_sar.py
│   ├── benchmark_ternary.py
│   └── benchmark_isomeric.py
│
├── outputs/                    # Generated outputs
│   └── README.md
│
└── tests/                      # Unit tests
    ├── __init__.py
    ├── test_react_protac.py
    ├── test_a1_protac.py
    ├── test_isomeric_protacs.py
    ├── test_linker_analyzer.py
    ├── test_warhead_docking.py
    ├── test_ternary_modeling.py
    ├── test_degradation_predictor.py
    ├── test_admet_predictor.py
    ├── test_e3_biology.py
    ├── test_ubiquitination.py
    ├── test_tpd_retriever.py
    └── test_config.py
```

---

## 10. Risk Register & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **P4WARD/PRosettaC not installed** | HIGH | HIGH | Graceful fallback to distance-based heuristic + clear warning; Docker detection |
| **No GPU for ternary modeling** | MEDIUM | MEDIUM | CPU-only fallback with reduced accuracy; document limitations |
| **PROTAC-DB data quality issues** | MEDIUM | MEDIUM | Cross-reference with PROTACpedia; confidence scoring |
| **Linker SAR data sparse for new targets** | HIGH | MEDIUM | Use physics-based descriptors as priors; uncertainty quantification |
| **LLM hallucinates explanations** | MEDIUM | HIGH | All explanations must cite specific evidence (descriptor values, model outputs); ReAct loop with verification |
| **BioMNI API changes** | LOW | HIGH | Pin BioMNI version; vendor as separate pip dependency or fork critical files |
| **Cell permeability prediction unreliable** | HIGH | MEDIUM | Use consensus across multiple models; report confidence |
| **MD simulations too slow** | HIGH | LOW | Skip MD by default; make it optional; use conformer sampling as fast proxy |

---

## 11. Key Design Decisions & Tradeoffs

### Decision 1: Extend BioMNI vs Reimplement from Scratch

**Choice:** Reimplement the core agent architecture (ReAct + LangGraph + tool descriptions + retriever) as a standalone `robust/` package, **inspired by** BioMNI's patterns but independent.

**Rationale:**
- BioMNI's `pip install biomni` works but its massive dependency tree (11GB data lake, many bio tools) adds overhead
- PROTACPilot needs TPD-specific tool descriptions, not general biomedical ones
- A standalone package keeps the dependency footprint manageable
- The architecture patterns (declarative descriptions, LangGraph ReAct, tool registry, tool retriever) are clean and replicable

### Decision 2: LangGraph vs Custom ReAct

**Choice:** LangGraph for workflow orchestration, with a deterministic fallback (like BioMNI's `react.py`).

**Rationale:**
- LangGraph provides: state management, conditional edges, recursion control, checkpointing
- Deterministic fallback (list of nodes) ensures the system works without LangGraph
- This matches BioMNI's dual approach

### Decision 3: Heuristic vs ML for Degradation Prediction

**Choice:** Hybrid — ML model when available, heuristic fallback when not, always with uncertainty quantification.

**Rationale:**
- Published ML models for PROTAC degradation prediction are still limited
- Physics-based heuristics (linker length, flexibility, ternary geometry) provide interpretable baselines
- Uncertainty quantification prevents overconfident predictions

### Decision 4: Explanation Generation

**Choice:** Structured, data-driven explanations (not free-form LLM output).

**Rationale:** Every claim in the explanation must trace to a specific computed value (linker length, clash count, DC50, etc.). This prevents hallucination and makes the reasoning auditable. LLM is used only to *format* the explanation, not to *generate* it.

### Decision 5: Docker vs Native for External Tools

**Choice:** Detect and use native tools first; fall back to Docker; document tool status clearly.

**Rationale:**
- Installing P4WARD, GNINA, OpenBabel natively is fragile
- Docker provides reproducibility
- But Docker may not be available in all environments
- BioMNI's approach of subprocess execution with timeout guards is the right pattern

### Decision 6: Data Storage

**Choice:** Pickled lookup tables (`schema_db/*.pkl`) for fast agent access, plus CSV/JSON for human readability.

**Rationale:**
- BioMNI's `.pkl` approach is fast for agent tools
- CSV/JSON exports allow external validation
- Auto-download from S3 (like BioMNI) reduces repo size

---

## Appendix A: Key Implementation Milestones

| Milestone | Deliverable | Dependencies | Effort Estimate |
|---|---|---|---|
| M1: Core agent infrastructure | `react_protac.py`, `a1_protac.py`, `config.py`, `llm.py`, `utils.py`, `tool_registry.py` | None | 5-7 days |
| M2: TPD tool descriptions | All `descriptions/*.py` files | M1 | 3-4 days |
| M3: TPD tool implementations | All `tool/*.py` implementations (placeholder heuristics initially) | M1 | 7-10 days |
| M4: Isomeric analysis engine | `tool/isomeric_protacs.py` full implementation | M3 | 4-5 days |
| M5: TPD retriever | `model/tpd_retriever.py` | M1 | 2-3 days |
| M6: Data lake population | All `schema_db/*.pkl` + S3 scripts | None | 3-5 days |
| M7: Know-how documents | All `know_how/*.md` | None | 3-4 days |
| M8: Evaluation framework | `eval/benchmark_*.py` | M3 | 2-3 days |
| M9: Integration & end-to-end testing | Working end-to-end pipeline | M1-M8 | 3-5 days |
| M10: User testing & refinement | Based on real isomeric PROTAC problems | M9 | Ongoing |

**Total estimated time:** 32-46 person-days for first working version.

## Appendix B: Quick-Start Demonstration

After building M1-M4, the intended user experience is:

```python
from robust.agent import A1Protac

agent = A1Protac(path='./data', llm='claude-sonnet-4-20250514')

# User request with isomeric PROTAC analysis
result = agent.go("""
Analyze why these 6 HMGB2 PROTACs have different degradation activity.
Warhead: Inflachromene (SMILES: CC1(C2=CCN3C...))
E3 ligand: AHPC (pomalidomide)
Linkers (same warhead + same E3, only linker changes):
  C4: OCCCC(=O)
  C6: OCCCCCC(=O)
  C8: OCCCCCCCC(=O)
  PEG3: OCCOCCOCC(=O)
  PEG4: OCCOCCOCCOCC(=O)
  C4-piperazine: OCCN1CCN(CC1)C(=O)

For each PROTAC, predict DC50, Dmax, and explain WHY the linker choice
leads to the observed degradation difference. Focus on:
1. Ternary complex geometry changes
2. Linker conformational entropy
3. Cell permeability differences
4. Ubiquitination geometry
5. Dominant failure mode for each linker
""")

# Output: structured comparison with explanations per linker pair
```

---

*This document is a living plan. Each phase will be updated with implementation details, test results, and lessons learned as the project progresses.*

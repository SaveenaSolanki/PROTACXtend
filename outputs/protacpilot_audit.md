# PROTACPilot Audit — Current State vs What's Needed for a Generalized Automated Workflow

**Audit date:** 2026-06-30  
**Project root:** `/storage/saveena/protacpilot`  
**Scope:** 17 agents, 50+ tools, data files, orchestration, schemas, tests  
**Grading rubric:** `not present` → `stub/heuristic` → `demo_data_only` → `executable_not_tested` → `executable_verified` → `production`

---

## 1. Executive Summary

**What you have:** An exceptionally well-architected agentic scaffold with:
- 17 specialist agents with clear responsibilities
- A linear state-machine workflow graph (LangGraph-compatible fallback)
- Multi-layer agentic control (perception → reasoning → goals → decisions → execution → critique → learning → orchestration)
- Comprehensive schemas for candidates, evidence, provenance, tools, and memory
- RDKit integration for basic chemistry operations
- Truthfulness protections (tool_status, evidence_type, limitation fields on every score)
- Demo data files for E3 ligands, linkers, warheads, targets, and known PROTACs
- Streamlit UI + FastAPI backend + CLI entry points

**What's missing for a generalized automated PROTAC design pipeline:**

| Category | Present | Missing |
|---|---|---|
| **Workflow orchestration** | ✅ 23-node graph | ❌ No iteration/feedback loop when all candidates fail |
| **POI analysis** | ✅ Target resolver (UniProt wrapper) | ❌ No binding-site detection, lysine scanning, DEGRADOMAP score |
| **Warhead docking** | ⚠️ Stub exit-vector detection | ❌ No actual docking (Vina/GNINA), no binding-mode prediction, no MM-GBSA |
| **E3 ligase selection** | ⚠️ 7 hardcoded demo ligands | ❌ No E3Atlas integration, no subcellular colocalization logic, no tissue expression matching |
| **Linker design** | ⚠️ 12 curated demo linkers | ❌ No generative design, no length prediction from exit-vector distance, no conformer sampling |
| **Ternary complex modeling** | ❌ Ternary feasibility = geometry proxy stub | ❌ No P4ward, no PRosettaC, no AF3, no protein-protein docking |
| **Ubiquitination geometry** | ❌ Not present | ❌ No CRL model, no lysine occlusion check, no E2~Ub distance measurement |
| **Physicochemical filtering** | ⚠️ RDKit descriptors only | ❌ No ML permeability model, no chameleonic behavior score, no bRo5-specific filters |
| **Activity prediction** | ⚠️ Heuristic DC50/Dmax fallback | ❌ No trained ML model, no uncertainty quantification, no applicability domain |
| **Iteration / failure diagnosis** | ❌ Not present | ❌ No automated root-cause analysis, no design-of-next-cycle logic |
| **Experimental feedback loop** | ❌ Not present | ❌ No mechanism to ingest experimental results and retrain |

**Overall readiness:** The pipeline is ~15% toward a generalized automated system. The architecture is ~90% complete; the computational engine is ~5% complete.

---

## 2. Module-by-Module Gap Analysis

Reference: *PROTACPilot Generalized Architecture* (`outputs/protacpilot_generalized_architecture.md`)

### M1: POI Profiler

| What's Needed | What Exists | Gap |
|---|---|---|
| Structure retrieval (AlphaFold/PDB) | `alphafold_client.py` — wraps AF API | Not tested with actual HMGB2 workflow |
| Binding site detection | ❌ Not present | Need FPocket/SiteMap |
| Lysine scanner + SASA | ❌ Not present | Need FreeSASA + occlusion logic |
| Subcellular localization | ❌ Not present | Need Deeploc2 or UniProp annotation |
| Degradability score | ❌ Not present | Need DegradoMap integration |

### M2: Warhead Analyzer

| What's Needed | What Exists | Gap |
|---|---|---|
| Conformer generation | ✅ `generate_ligand_conformers()` in ternary_feasibility.py (RDKit ETKDG) | Works but not integrated into warhead selection |
| Docking to POI | ❌ Stub only | No Vina/GNINA/Glide wrapper |
| Exit vector enumeration | ⚠️ `exit_vector_detector.py` | Curated CSV only; not computed from docking poses |
| Pose clustering | ❌ Not present | Butina clustering needed |

### M3: E3 Ligase Selector

| What's Needed | What Exists | Gap |
|---|---|---|
| E3 ligand library | ✅ 7 ligands in `curated_e3_ligands.csv` | Only demo data; missing pomalidomide, lenalidomide, VH032 |
| Exit vector per ligand | ✅ `curated_exit_vector_map.csv` | Same limitation |
| Subcellular colocalization | ❌ Not present | Hardcoded logic needed |
| Tissue expression matching | ❌ Not present | Need E3Atlas/GTEx integration |
| Prior-success lookup | ❌ Not present | Need literature mining |

### M4: Linker Generator

| What's Needed | What Exists | Gap |
|---|---|---|
| Linker library | ⚠️ 12 linkers in `curated_linkers.csv` | Missing C10, C12, C14 lengths; no longer PEG chains |
| Length prediction from exit-vector distance | ❌ Not present | Core missing feature |
| Generative design | ❌ Not present | Link-INVENT/REINVENT not integrated |
| Conformer sampling | ❌ Only in ternary_feasibility.py stub | Not connected to linker selection |

### M5: Ternary Complex Modeler

| What's Needed | What Exists | Gap |
|---|---|---|
| Protein-protein docking | ❌ Not present | No Megadock/PatchDock |
| PROTAC-constrained sampling | ❌ Not present | **P4ward is the biggest missing piece** |
| Multi-linker screening | ❌ Not present | P4ward handles this natively |
| TC refinement (PRosettaC/AF3) | ❌ Not present | No webservice wrapper |

### M6: Ubiquitination Geometry

| What's Needed | What Exists | Gap |
|---|---|---|
| CRL model builder | ❌ Not present | Need PDB-based assembly |
| Lysine occlusion detection | ❌ Not present | The core geometric filter |
| E2~Ub distance measurement | ❌ Not present | The primary ubiquitination feasibility metric |

### M7: Physicochemical Filter

| What's Needed | What Exists | Gap |
|---|---|---|
| 2D descriptors | ✅ `analyze_protac_like_properties()` in toolbox | Uses RDKit; accurate enough for bRo5 flags |
| Permeability ML model | ❌ Not present | Heuristic only |
| Chameleonic behavior score | ❌ Not present | Requires conformer ensemble in implicit membrane |

### M8: ML Activity Predictor

| What's Needed | What Exists | Gap |
|---|---|---|
| DC50 prediction | ⚠️ `degradation_predictor.py` | Heuristic fallback; no trained model loaded |
| Dmax prediction | ⚠️ Same | Heuristic; no model |
| Uncertainty quantification | ❌ Not present | Monte Carlo dropout not implemented |
| Applicability domain | ⚠️ `applicability_domain.py` | Returns 1.0 or 0.0 based on model existence |

### Iteration / Failure Diagnosis

| What's Needed | What Exists | Gap |
|---|---|---|
| Automated root-cause analysis | ❌ Not present | No "linker too short" / "wrong E3" / "exit vector wrong" logic |
| Design-of-next-cycle | ❌ Not present | No "try longer linker" / "switch E3" automated recommendations |
| Experimental feedback | ❌ Not present | No data ingestion mechanism |

---

## 3. The Critical Path — What to Build First

### Tier 0 (P0): Core Computational Engine — Without This the Pipeline Cannot Run

```
Priority 1: P4ward integration
  Why: This is the single most impactful component. P4ward does protein-protein
  docking, PROTAC-constrained linker sampling, CRL model filtering (lysine
  accessibility), and TC scoring. Without it, you cannot predict ternary complexes.
  Effort: ~2 weeks to Dockerize and wrap
  
Priority 2: Warhead docking pipeline
  Why: You cannot design a PROTAC without knowing where the warhead binds and
  which exit vector points to solvent. Docking is the prerequisite for everything.
  Effort: ~1 week to integrate Vina/GNINA
  
Priority 3: E3 selector with subcellular logic
  Why: Currently 7 hardcoded demo ligands. Need pomalidomide, lenalidomide, 
  VH032, and the colocalization decision tree.
  Effort: ~3 days to build the knowledge base + logic
  
Priority 4: Extended linker library + length prediction
  Why: 12 demo linkers are insufficient. Need C10–C14 PEG and alkyl variants,
  and the predictive module that computes required length from exit-vector distance.
  Effort: ~3 days to enumerate + 2 days for predictive logic
```

**Estimated time to Tier 0 completion:** 4–5 weeks with one computational chemist + one engineer

### Tier 1 (P1): Enhanced Computational Fidelity

```
Priority 5: PRosettaC refinement wrapper
  Why: P4ward gives initial poses; PRosettaC refines them to higher accuracy.
  Effort: ~1 week to wrap webservice
  
Priority 6: CRL model + lysine occlusion module
  Why: Needed to predict whether ubiquitination is geometrically possible.
  Builds on P4ward's built-in lysine filter.
  Effort: ~1 week

Priority 7: Binding site detection (FPocket/SiteMap)
  Why: Essential for targets without known binding pockets.
  Effort: ~3 days

Priority 8: Generative linker design
  Why: To go beyond the fixed linker library and explore novel chemistries.
  Can use Link-INVENT or train a custom model.
  Effort: 2–4 weeks depending on approach
```

**Estimated time to Tier 1 completion:** +6–8 weeks from Tier 0

### Tier 2 (P2): ML + Iteration Layer

```
Priority 9: DC50/Dmax ML model training
  Why: Heuristic degradation prediction is not trustworthy. Need a trained
  model with uncertainty.
  Effort: 4–6 weeks (data curation + training + validation)

Priority 10: Automated failure diagnosis
  Why: The system must tell the user WHY their PROTACs failed and what to try next.
  Effort: 2 weeks to build the rule engine

Priority 11: Permeability ML model
  Why: bRo5 permeability is the #1 reason PROTACs fail in cells.
  Effort: 3–4 weeks

Priority 12: Experimental feedback loop
  Why: To close the design–make–test cycle and improve over time.
  Effort: 2 weeks
```

**Estimated time to Tier 2 completion:** +12–16 weeks from Tier 1

### Tier 3 (P3): Production Hardening

```
Priority 13: Patent/novelty search
Priority 14: Retrosynthesis planning
Priority 15: Multi-E3 expansion (DCAF1, RNF114, FEM1B)
Priority 16: Knowledge graph for cross-target learning
Priority 17: Web interface improvements
Priority 18: Batch/cloud deployment
```

---

## 4. What Exists That Works Today

These components are **executable and usable as-is**:

| Component | File | What It Does |
|---|---|---|
| RDKit validation | `rdkit_validator.py`, `chemistry_core.py` | SMILES parsing, property calculation, molecular standardizer |
| Ligand conformer generation | `ternary_feasibility.py` → `generate_ligand_conformers()` | RDKit ETKDG → SDF output |
| E3 ligand curation | `e3_selector.py` + `curated_e3_ligands.csv` | 7 ligands across 4 E3s with exit-vector metadata |
| Linker curation | `linker_generator.py` + `curated_linkers.csv` | 12 linkers across 7 classes with properties |
| Target resolution | `target_agent.py` + `alphafold_client.py` | UniProt ID → AlphaFold structure |
| Workflow graph | `graph.py` → `LocalSynGlueWorkflowGraph` | 23-node linear state machine |
| Agentic orchestration | `agentic/orchestration.py` | 7-layer control + provenance tracking |
| ADME descriptors | `admet_predictors.py` | RDKit-based 2D descriptor calculation |
| Candidate construction | `molecular_constructor.py` | SMILES concatenation with linkers |
| Report generation | `report_generator.py` | Markdown + CSV + JSON output |
| Truthfulness framework | `schemas/candidate_schema.py` | Provenance fields on every score |
| Streamlit UI | `app/streamlit_app.py` | Interactive research workspace |
| FastAPI backend | `backend/api_routes.py` | REST endpoints |
| Test suite | `tests/*.py` | 15+ test files covering agentic and tool modules |

## 5. What Needs the Most Engineering Effort

| Module | Effort Estimate | Reason |
|---|---|---|
| **P4ward integration** (Docker + Python wrapper) | 2 weeks | Dependency chain: Megadock, OpenMM, RXDock, RDKit; needs containerization |
| **Warhead docking** (Vina/GNINA) | 1 week | Integration + pose analysis + exit-vector extraction |
| **DC50/Dmax ML model** | 5 weeks | Data curation from PROTAC-DB + featurization + training + validation |
| **Generative linker design** | 3 weeks | RL agent setup + reward function design + integration |
| **Automated failure diagnosis** | 2 weeks | Rule engine + decision tree implementation |
| **Chameleonic permeability model** | 3 weeks | Conformer generation in implicit solvent/membrane + ML model |
| **PRosettaC webservice wrapper** | 1 week | API client for the webserver |

---

## 6. Quick Wins (Can Be Done in 1–2 Days)

These are small improvements with high impact:

| Task | File(s) | Impact |
|---|---|---|
| Add pomalidomide, lenalidomide, VH032 to E3 ligand CSV | `curated_e3_ligands.csv` | Better CRBN/VHL coverage |
| Add C10, C12, C14 PEG and alkyl linkers | `curated_linkers.csv` | Critical missing lengths for nuclear targets |
| Add HMGB2 as a demo target | `curated_targets.csv` | Immediate test case |
| Connect exit-vector detection to warhead selection output | `exit_vector_detector.py` | Feeds the linker generation step |
| Add a `--diagnose` flag that runs the failure decision tree | New file | Automated "why did my PROTAC fail?" output |
| Add subcellular colocalization field to E3 ligand CSV | `curated_e3_ligands.csv` | Enables basic E3 recommendation |

---

## 7. How to Get from Here to "Give It a POI and Get a PROTAC"

The gap between the current state and a generalized automated pipeline can be summarized as:

**Today:** A user provides a natural-language objective → the system runs 23 agentic steps using heuristic proxies and demo data → outputs a candidate list with truthfulness-labeled scores → the user must judge whether the output is meaningful.

**Goal:** A user provides a POI identifier + warhead SMILES → the system runs 8 physics-based computational modules → iterates if all candidates fail → outputs a ranked set of PROTACs with predicted DC50, Dmax, permeability, and a failure diagnosis → the user synthesizes and tests the top 3.

### The Minimum Viable Product (MVP) Definition

A PROTACPilot MVP should be able to answer these six questions for any POI–warhead pair:

| Question | Current Status | MVP Target |
|---|---|---|
| 1. Where does the warhead bind? (exit vector) | Stub — relies on curated data | ✅ Vina/GNINA docking with pose analysis |
| 2. Which E3 should I use? | 7 hardcoded ligands | ✅ Colocalization + expression logic |
| 3. What linker length/composition? | 12 curated linkers | ✅ P4ward will try all viable lengths |
| 4. Does a stable ternary complex form? | Geometry-proxy stub | ✅ P4ward TC model |
| 5. Can E2~Ub reach a lysine? | Not checked | ✅ P4ward CRL filter |
| 6. Will it get into cells? | RDKit descriptors | ✅ bRo5 score + chameleonic proxy |

### The MVP Build Order

```
Week 1-2:   Integrate Vina/GNINA for warhead docking + exit vector detection
Week 3-4:   Build P4ward Docker image + Python wrapper
Week 5:     Connect warhead docking → exit vector → P4ward input
Week 6:     Extend E3 ligand library + add subcellular logic
Week 7:     Extend linker library (add C10–C14)
Week 8:     Add failure diagnosis rules engine
Week 9-12:  Test on 3 targets: HMGB2 (nuclear), BRD4 (nuclear, known), EGFR (cytoplasmic)
Week 13-14: Fix bugs found during testing
Week 15:    MVP release

→ At this point the pipeline can accept any POI+warhead and output ranked PROTACs.
```

---

## 8. Architecture Diagram — What Maps to What

```
PROPOSED MODULE          EXISTING CODE                    GAP
────────────────────     ────────────────────────────     ──────────────────────
M1: POI Profiler         target_agent.py +                No binding site
                         alphafold_client.py             detection, lysine scan,
                                                          degradability score

M2: Warhead Analyzer     warhead_agent.py +               No docking;
                         exit_vector_detector.py          exit_vector = curated CSV
                                                          only

M3: E3 Selector          e3_agent.py +                    7 demo ligands only;
                         e3_selector.py                   no subcellular logic

M4: Linker Generator     linker_agent.py +                12 curated linkers only;
                         linker_generator.py              no generative design

M5: TC Modeler           ternary_agent.py +               ❌ NO REAL ENGINE
                         ternary_feasibility.py           (geometry-proxy stub)

M6: Ubiquitination       ❌ Not present                   ❌ Not present
    Geometry

M7: Physicochemical      admet_agent.py +                 RDKit only; no ML
    Filter                admet_predictors.py              permeability model

M8: Activity Predictor   prediction_agent.py +            Heuristic fallback;
                         degradation_predictor.py         no trained model

Iteration / Diagnosis     ❌ Not present                   ❌ Not present
```

---

## 9. The Single Most Important Decision

**Should you invest in building P4ward integration first, or in training an ML activity predictor first?**

**Answer: P4ward, by a wide margin.**

Here's why:
1. P4ward provides physical insight (ternary complex geometry, lysine accessibility) that no ML model can learn from the current PROTAC-DB (which has only ~2000 compounds with heterogeneous assay data).
2. P4ward can screen multiple linkers per run (built-in multi-linker mode), which is exactly what you need for the HMGB2 case.
3. P4ward works without training data — it's physics-based. You can use it immediately for any novel target.
4. An ML model trained on PROTAC-DB would have poor coverage for nuclear chromatin proteins like HMGB2 because most PROTAC-DB compounds target cytoplasmic or nuclear-shuttling proteins (BRD4, AR, ER).
5. P4ward's output (TC models + accessible lysine identification) feeds directly into the failure diagnosis module.

**ML should come second**, once you have built up enough data from your own P4ward runs to train a domain-specific model.

---

## 10. Immediate Next Steps (Start Tomorrow)

| # | Task | File to Create/Edit | Estimated Time |
|---|---|---|---|
| 1 | Add pomalidomide, lenalidomide, VH032 to E3 ligand CSV | `curated_e3_ligands.csv` | 30 min |
| 2 | Add C10, C12, C14, C16 PEG and alkyl linkers | `curated_linkers.csv` | 1 h |
| 3 | Add HMGB2, BRD4, EGFR to curated targets | `curated_targets.csv` | 30 min |
| 4 | Write `FailureDiagnosisEngine` class — rule-based decision tree | New file: `tools/failure_diagnosis.py` | 1 day |
| 5 | Write `P4wardDockerWrapper` — calls P4ward via Docker | New file: `tools/p4ward_wrapper.py` | 2 days (includes Docker image build) |
| 6 | Connect warhead exit vector → P4ward input | Modify `exit_vector_agent.py` → `ternary_agent.py` | 1 day |
| 7 | Add subcellular colocalization to E3 selection | Modify `e3_selector.py` | 1 day |
| 8 | Add `--diagnose` CLI flag to `main.py` | `backend/main.py` | 2 h |
| 9 | Run end-to-end on HMGB2–ICM test case | Integration test | 1 day (after P4ward ready) |
| 10 | Add the iteration loop (if all fail → try longer linker + CRBN) | Modify `graph.py` | 2 days |

---

## 11. Summary Table

| Area | Status | What's Needed |
|---|---|---|
| **Agent architecture** | ✅ Excellent | Few changes |
| **Schemas & provenance** | ✅ Excellent | Few changes |
| **Orchestration** | ✅ Good | Add iteration loop |
| **POI analysis** | ⚠️ Partial | Docking, binding site, lysine scan |
| **Warhead analysis** | ⚠️ Partial | Docking integration |
| **E3 selection** | ⚠️ Partial | Real E3 ligand library + subcellular logic |
| **Linker design** | ⚠️ Partial | Extended library + length prediction + generation |
| **TC modeling** | ❌ Missing | **P4ward integration (highest priority)** |
| **Ubiquitination check** | ❌ Missing | CRL model + lysine occlusion |
| **Physicochemical filters** | ⚠️ Partial | ML permeability model |
| **Activity prediction** | ⚠️ Partial | Trained ML model |
| **Failure diagnosis** | ❌ Missing | Rule engine + iteration |
| **Experimental feedback** | ❌ Missing | Data ingestion |
| **Web/API/UI** | ✅ Good | Few changes |
| **Tests** | ✅ Good | Expand as modules are built |

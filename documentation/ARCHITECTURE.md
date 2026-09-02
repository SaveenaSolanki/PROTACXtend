# PROTACXtend Architecture & the Scientific Contract

**PROTACXtend** implements a governed, auditable **agent graph**: a **23-node core scientific
workflow** (objective parsing → discovery → component-aware assembly → evaluation →
reflection/ranking) plus **8 controlled-search and feedback extensions**
(expensive-modeling selection, ternary / cooperativity / hook-effect gates, final ranking,
active-learning update, report, memory) = **31 documented agent nodes** registered in
`synglue_agent/agents/graph.py`. The production path walks the registered nodes in sequence
and stops only at terminal evidence or error gates.

---

## The scientific-contract philosophy

Traditional PROTAC design models operate as opaque black boxes — taking inputs and outputting SMILES strings without explaining *why* a particular linker length was chosen or *how* ternary complex geometry was evaluated.

PROTACXtend transforms every stage into an explicit decision chain:
- **Invisible interactions** → **Visible reasoning traces**
- **Black-box predictions** → **Step-by-step decision chains**
- **Opaque outputs** → **Auditable evidence trails & human escalation gates**

Every executed scientific step records its input, output, evidence source, tool/model
version, confidence, applicability-domain status, warning state and limitation.

```
┌─────────────────────────────────────────────────────────────┐
│                    USER REQUEST                              │
│ "Design CRBN PROTACs for BRD4 degradation"                  │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  SUPERVISOR NODE                                            │
│  "Parse objective → extract target/E3/constraints"          │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  TARGET RESOLVER (UniProt & AlphaFold API)                  │
│  "BRD4" → ChEMBL lookup → CHEMBL6066530                     │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  BINDER RETRIEVAL (ChEMBL + PubChem + BindingDB)            │
│  87 binders found → dedup on InChIKey → 100 unique          │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  WARHEAD SELECTION & EXIT VECTOR DETECTION                   │
│  4 top warheads selected by pChembl + exit vector check     │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  E3 LIGAND SELECTION (CRBN / VHL / IAP / MDM2)              │
│  CRBN: pomalidomide, lenalidomide (2 curated ligands)       │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  LINKER GENERATION (73-method engine: curated, rules, GRU)  │
│  16 linkers: 8 curated + 4 rule-based + 4 generative        │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  MOLECULAR CONSTRUCTION & STEREOCHEMISTRY                   │
│  32 candidates assembled → RDKit sanitized & stereoisomers  │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  TERNARY COMPLEX FEASIBILITY (P4ward + SE(3) Proxy)         │
│  Geometric proxy score: 0.85 → PROCEED                       │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  DEGRADATION PREDICTION (Chemprop Ensemble + TACK)          │
│  Chemprop DC50=14.2nM, Dmax=82%, class=active               │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  ADMET & SAFETY RISK EVALUATION                              │
│  hERG=0.02, AMES=0.08, BBB=0.65, Lipinski & Veber OK       │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  HUMAN ESCALATION GATE & FINAL REPORT GENERATION            │
│  16 ranked candidates output with markdown report + CSV/JSON│
└────────────────────────┴────────────────────────────────────┘
```

---

## 🧱 23-Node Agentic Inventory

PROTACXtend organizes its workflow into 23 specialized agent nodes defined under `synglue_agent/agents/`:

| # | Node Name | Agent Class | Function & Responsibility |
|---|-----------|-------------|---------------------------|
| 1 | `parse_user_request` | `SupervisorAgent` | Extracts target, E3 ligase, cell line, and constraints from natural language. |
| 2 | `create_design_plan` | `DesignPlannerAgent` | Policy engine setting iteration depth, tool selection, and retry thresholds. |
| 3 | `safety_precheck` | `SafetyAgent` | Screens SMILES for hazardous substructures and reactivity flags. |
| 4 | `resolve_target` | `TargetResolverAgent` | Queries UniProt, ChEMBL, and AlphaFold DB for target protein metadata. |
| 5 | `retrieve_target_binders` | `TargetBinderRetrievalAgent` | Pulls bioactivity data from ChEMBL, PubChem, and BindingDB APIs. |
| 6 | `select_warheads` | `WarheadSelectionAgent` | Filters binders based on pChembl values, selectivity, and attachment points. |
| 7 | `select_e3_ligands` | `E3LigandSelectionAgent` | Selects E3 ligase recruiters (pomalidomide, VHL ligands, etc.). |
| 8 | `detect_exit_vectors` | `ExitVectorDetectionAgent` | RDKit-based detection of solvent-exposed attachment vectors. |
| 9 | `generate_linkers` | `LinkerGenerationAgent` | Generates linkers using 73-method toolbox (curated, rule-based, GRU). |
| 10 | `construct_protacs` | `MolecularConstructionAgent` | Assembles warhead, linker, and E3 ligand via reaction/concatenation strategies. |
| 11 | `validate_protacs` | `CandidateValidationAgent` | Sanitizes molecules and checks physicochemical parameter ranges. |
| 12 | `predict_degradation` | `DegradationPredictionAgent` | Chemprop deep learning ensemble + TACK model for $DC_{50}$ and $D_{\max}$. |
| 13 | `predict_admet` | `ADMETAgent` | Computes hERG inhibition, AMES mutagenicity, BBB permeability, and Lipinski flags. |
| 14 | `check_novelty` | `NoveltyAgent` | Calculates Tanimoto similarity against 485,329 known PROTAC structures. |
| 15 | `assess_applicability_domain` | `ApplicabilityDomainAgent` | Evaluates model confidence boundaries and flags out-of-domain structures. |
| 16 | `initial_ranking` | `RankingAgent` | Computes initial multi-objective composite score across affinity and properties. |
| 17 | `diversity_clustering` | `ProximityDiversityAgent` | Performs Taylor-Butina clustering ($T \ge 0.62$) to ensure structural diversity. |
| 18 | `reflection_review` | `ReflectionReviewAgent` | Audits reasoning steps for overclaiming or conflicting predictions. |
| 19 | `evolution_refinement` | `EvolutionRefinementAgent` | Executes genetic algorithm operations to optimize linker length and composition. |
| 20 | `optional_ternary_feasibility` | `TernaryFeasibilityAgent` | Docking simulation using P4ward and SE(3) equivariant geometric scoring. |
| 21 | `final_ranking` | `RankingAgent` | Re-ranks Pareto front using integrated ternary complex stability data. |
| 22 | `generate_report` | `ReportAgent` | Generates structured Markdown reports, CSV spreadsheets, and JSON payloads. |
| 23 | `update_memory` | `MemoryUpdateAgent` | Persists session history and reasoning graphs to disk for future runs. |

---

## 🛠️ Master Toolbox Architecture (`protac_toolbox.py`)

The engine is backed by a **73-method master toolbox** spanning:
1. **RDKit Chemistry Core**: SMILES sanitization, InChIKey indexing, tautomer generation, exit vector mapping.
2. **Stereochemistry Engine**: Chiral center resolution, E/Z geometry control, stereoisomer enumeration.
3. **Linker Scanner**: Systematic $N \times M$ linker attachment scanning and conformational flexibility scoring.
4. **P4ward Wrapper**: 3D ternary complex docking simulation via containerized P4ward pipeline.
5. **ADMET & Safety**: Filter rules for Pan-Assay Interference Compounds (PAINS) and reactive groups.

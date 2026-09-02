# PROTACXtend Missing Modules Build Specification

This document converts the remaining PROTACXtend research gaps into buildable
software modules. These modules are not optional polish: together they are the
technical path from evidence-ranked PROTAC suggestions to a credible
design-test-learn system.

Important boundary: these modules do not "solve" the NP-hard PROTAC design
problem by exhaustive search. They make it tractable by bounded generation,
physics/biology-aware pruning, calibrated uncertainty, experimental feedback,
and explicit abstention when evidence is weak.

## Executive Decision

The roadmap has two lanes:

1. Reuse reproducible state-of-the-art components first.
2. Build genuinely novel PROTACXtend-native degrader capabilities after those
   baselines are wrapped, tested, and gated.

### External-First Integration Order

| Order | Component | Role | Decision |
| --- | --- | --- | --- |
| 1 | PROTAC-Degradation-Predictor | Immediate context-aware degradation baseline | Integrate first |
| 2 | RP-PROTAC | Uncertainty/OOD and ranking comparator | Audit, then integrate |
| 3 | Deep-QSP Hook model | Mechanistic ternary dose-response and hook-effect simulator | Integrate/adapt |
| 4 | PROTACFold | Ternary structure-generation branch | Audit, then wrap |
| 5 | PROTAC ternary benchmark | Structural validation harness | Adopt as gate |
| 6 | SynPROTAC | Synthesis-constrained generation baseline | Audit, then integrate |

### PROTACXtend-Native Build Order

| Missing module | Start from | Need new code? | Decision | Build order |
| --- | --- | --- | --- | --- |
| Ubiquitination Geometry Scorer | Bai et al. JBC 2022 + ternary structures | Yes | Build | 1 |
| Cooperativity Potential Model | Wurz 2023 + Ma 2025 + interface features | Yes | Build | 2 |
| Proteome-Context Selectivity Model | Public quantitative degradation proteomics | Yes | Build as research module | 3 |
| Design-Test-Learn Optimizer | SynPROTAC + Bayesian optimization | Yes for feedback loop | Build after experimental pipeline | 4 |
| E3 Recruiter Discovery Engine | RNF4/FEM1B experimental frameworks | Yes, largely new | Later | 5 |

The Ternary Dose-Response Simulator and Context-Aware Degradation Predictor are
still needed, but their first versions should be integration layers around
external/reproducible baselines before PROTACXtend trains or claims a novel
model.

## Shared Contracts

Every module must produce structured output. No module should return only a
single score.

### Common Input

```json
{
  "candidate_id": "string",
  "target": "BRD4",
  "e3": "CRBN",
  "cell_line": "MM1.S",
  "protac_smiles": "string",
  "warhead_smiles": "string",
  "recruiter_smiles": "string",
  "linker_smiles": "string",
  "ternary_poses": ["path/to/pose.pdb"],
  "evidence_bundle_id": "string"
}
```

### Common Output

```json
{
  "module": "ubiquitination_geometry",
  "version": "0.1.0",
  "status": "SUPPORTED | REVISE | REJECT | INSUFFICIENT EVIDENCE",
  "score": 0.0,
  "confidence": 0.0,
  "features": {},
  "evidence": [],
  "warnings": [],
  "failure_modes": [],
  "next_actions": []
}
```

## 1. Ubiquitination Geometry Scorer

### Purpose

Score whether a ternary POI-PROTAC-E3 pose is geometrically competent for
ubiquitin transfer. Good ternary binding is not enough; the target protein must
present accessible lysines in a productive orientation relative to the E3/E2
catalytic machinery.

### Required Inputs

- Ternary pose ensemble: POI, PROTAC, CRBN or VHL complex.
- E3 complex template:
  - CRBN: CRL4A-DDB1-CRBN-RBX1/E2 proxy when available.
  - VHL: CRL2-VHL-ElonginB/C-CUL2-RBX1/E2 proxy when available.
- POI lysine annotations:
  - residue index
  - solvent accessibility
  - disorder/flexibility
  - conservation
  - known ubiquitination sites if available
- PROTAC linker exit atom mapping.

### Core Features

| Feature | Meaning |
| --- | --- |
| `min_lysine_to_e2_cys_distance_a` | Closest accessible POI lysine to E2 catalytic cysteine/proxy |
| `num_accessible_lysines_within_cutoff` | Count of surface-exposed POI lysines in geometric reach |
| `lysine_sasa_mean` | Mean solvent accessibility of reachable lysines |
| `poi_e3_interface_area_a2` | Protein-protein buried/contact surface |
| `lysine_orientation_score` | Whether side-chain direction is compatible with transfer |
| `linker_exit_vector_alignment` | Whether linker exits toward productive POI/E3 interface |
| `pose_cluster_support` | Number of independent poses supporting the same geometry |
| `steric_clash_score` | Clash penalty around ligase/E2/ubiquitin path |

### Algorithm

1. Load pose with Biopython/MDAnalysis.
2. Identify POI chain, E3 chain, ligand, and optional E2/cullin template chains.
3. Superpose ternary pose onto an E3-complex template.
4. Enumerate POI lysines.
5. Compute lysine solvent accessibility using FreeSASA or DSSP.
6. Compute distance from lysine NZ atom to E2 catalytic cysteine or E2 proxy.
7. Penalize inaccessible lysines, chain breaks, clashes, missing residues, and
   unsupported chain assignment.
8. Aggregate across pose ensemble:
   - best pose score
   - median pose score
   - cluster support
   - uncertainty from pose disagreement
9. Return `SUPPORTED` only if multiple criteria pass; otherwise return
   `REVISE` or `INSUFFICIENT EVIDENCE`.

### First Implementation Files

- `synglue_agent/tools/ubiquitination_geometry.py`
- `synglue_agent/schemas/ubiquitination_geometry.py`
- `tests/test_ubiquitination_geometry.py`

### Minimum Viable Test

- Synthetic pose with one exposed lysine near E2 proxy returns high score.
- Pose with no lysine in reach returns `REVISE`.
- Pose missing E2/cullin template returns `INSUFFICIENT EVIDENCE`, not a fake
  negative.

## 2. Ternary Dose-Response Simulator

### Purpose

Predict dose-response shape, including the hook effect, from binary binding,
ternary affinity/cooperativity, protein abundance, and degradation turnover.

### Required Inputs

- Target concentration estimate.
- E3 concentration estimate.
- PROTAC dose grid.
- Binary affinities:
  - PROTAC-target Kd
  - PROTAC-E3 Kd
- Ternary affinity or cooperativity alpha.
- Degradation and resynthesis rates.
- Optional measured DC50/Dmax time-course labels.

### Core Outputs

| Output | Meaning |
| --- | --- |
| `dc50_pred` | Simulated concentration for 50% degradation |
| `dmax_pred` | Maximum simulated degradation |
| `hook_concentration` | Concentration where ternary complex begins falling |
| `ternary_peak_concentration` | Dose where productive ternary complex is maximal |
| `dose_window_width` | Robust concentration interval for activity |
| `parameter_sensitivity` | Parameters driving uncertainty |

### Algorithm

1. Implement reversible equilibrium model:
   - target + PROTAC
   - E3 + PROTAC
   - target + PROTAC + E3
2. Add cooperativity alpha as ternary stabilization/destabilization.
3. Convert ternary complex abundance into degradation rate.
4. Simulate over time and concentration grid.
5. Fit observed curves when data exists.
6. Report hook risk and experimental dose suggestions.

### First Implementation Files

- `synglue_agent/tools/dose_response_simulator.py`
- `synglue_agent/schemas/dose_response.py`
- `tests/test_dose_response_simulator.py`

### Integration Decision

Integrate first as a deterministic mechanistic simulator. Treat deep/QSP code as
a reference implementation or optional backend, but keep PROTACXtend's core API
independent.

## 3. Cooperativity Potential Model

### Purpose

Estimate whether a candidate is likely to form a stabilizing or destabilizing
ternary complex before measured alpha/Kd exists.

### Required Inputs

- Ternary pose ensemble.
- Protein-protein interface contacts.
- Linker conformation.
- Binary binding evidence.
- Optional measured alpha or ternary Kd.

### Core Features

| Feature | Meaning |
| --- | --- |
| `interface_bsa_a2` | Buried surface area between POI and E3 |
| `interface_hbond_count` | Polar stabilizing contacts |
| `salt_bridge_count` | Charge-complementary contacts |
| `hydrophobic_contact_count` | Hydrophobic packing |
| `electrostatic_complementarity` | Surface charge fit |
| `frustrated_contact_fraction` | Destabilizing interface contacts |
| `linker_strain_kcal_mol` | Conformational strain penalty |
| `pose_entropy_proxy` | Pose diversity/uncertainty |
| `binary_affinity_balance` | Whether one binary arm dominates too strongly |

### Algorithm

1. Compute interface contacts for each pose.
2. Estimate local energetic frustration or a simpler contact conflict proxy.
3. Add linker strain from conformer energy above low-energy ensemble.
4. Estimate cooperativity potential:
   - positive if interface is stable and linker strain is modest
   - negative if frustrated contacts, clashes, or linker strain dominate
5. Calibrate against measured alpha/ternary Kd when data exists.
6. Return uncertainty high for novel POI/E3/linker regions.

### First Implementation Files

- `synglue_agent/tools/cooperativity_potential.py`
- `synglue_agent/schemas/cooperativity.py`
- `tests/test_cooperativity_potential.py`

## 4. Context-Aware Degradation Predictor

### Purpose

Predict degradation activity using molecule, target, E3, and cell-line context,
with calibrated uncertainty and explicit out-of-domain flags.

### Required Inputs

- PROTAC SMILES and decomposition.
- Target sequence or embedding.
- E3 identity.
- Cell line.
- PROTAC-DB/TACK/proprietary labels:
  - DC50
  - Dmax
  - binary activity
  - cell type
  - assay type
- Permeability/ADMET descriptors.
- Structural scores from modules 1 and 3.

### Outputs

| Output | Meaning |
| --- | --- |
| `p_active` | Probability of meaningful degradation |
| `pdc50_pred` | Potency estimate when model is calibrated enough |
| `dmax_pred` | Max degradation estimate |
| `uncertainty` | Ensemble/calibration uncertainty |
| `ood_flags` | Novel target, scaffold, cell, E3, or linker space |
| `calibration_bin` | Reliability bucket |

### Algorithm

1. Wrap existing PROTAC-Degradation-Predictor/DeepPROTACs baselines.
2. Add TACK-like local model interface for DC50/Dmax/activity.
3. Use scaffold split, leave-target-out, and leave-cell-out validation.
4. Add Platt/isotonic calibration where labels support it.
5. Never promote a model if uncertainty does not correlate with error.

### First Implementation Files

- `synglue_agent/tools/context_degradation_predictor.py`
- `synglue_agent/models/model_registry.py`
- `tests/test_context_degradation_predictor.py`

## 5. Proteome-Context Selectivity Model

### Purpose

Estimate selectivity and off-target degradation risk in a cell context. A
PROTAC can degrade the intended POI yet still be poor if it broadly perturbs the
proteome or depends on context not present in the desired disease state.

### Required Inputs

- Quantitative degradation proteomics datasets.
- Cell-line proteomics/transcriptomics.
- Target/E3 expression.
- Known neo-substrates and resistance annotations.
- Candidate structural/evidence features.

### Outputs

| Output | Meaning |
| --- | --- |
| `selectivity_score` | Intended target specificity estimate |
| `off_target_risk` | Broad degradation/liability estimate |
| `context_dependency` | Sensitivity to target/E3 abundance |
| `proteome_warning` | Human-readable caveats |

### Algorithm

1. Load public degradation proteomics into a normalized table.
2. Map proteins to UniProt IDs and cell lines to standard identifiers.
3. Compute target/E3 abundance priors.
4. Estimate degradation selectivity using similar target/recruiter/linker
   evidence.
5. Report warnings when no matching cell/proteome data exists.

### First Implementation Files

- `synglue_agent/tools/proteome_selectivity.py`
- `synglue_agent/data_loaders/proteome_context.py`
- `tests/test_proteome_selectivity.py`

## 6. Design-Test-Learn Optimizer

### Purpose

Close the active-learning loop: choose candidates, lock hypotheses, collect
experimental outcomes, update rankings, and recommend the next batch.

### Required Inputs

- Candidate dossier.
- Experiment dossier.
- Locked pre-experiment predictions.
- Assay results:
  - DC50/Dmax
  - WB evidence
  - ternary Kd/alpha
  - NanoBRET/HiBiT
  - PAMPA/Caco-2
  - proteomics
- Budget and synthesis constraints.

### Outputs

| Output | Meaning |
| --- | --- |
| `next_batch` | Candidates to make/test next |
| `expected_information_gain` | Why this batch is useful |
| `decision_change_probability` | Chance result changes ranking |
| `model_update_record` | What changed after feedback |
| `rollback_pointer` | Previous model/version if update fails |

### Algorithm

1. Lock prediction JSON before experiments.
2. Ingest assay results through schema validation.
3. Compare observed vs predicted outcomes.
4. Diagnose failure mode:
   - binding failure
   - ternary failure
   - lysine geometry failure
   - hook-effect failure
   - permeability failure
   - cell-context failure
5. Use Bayesian optimization or batch Thompson sampling for next candidates.
6. Promote model update only after validation gates pass.

### First Implementation Files

- `synglue_agent/learning/design_test_learn.py`
- `synglue_agent/learning/experiment_registry.py`
- `tests/test_design_test_learn.py`

## 7. E3 Recruiter Discovery Engine

### Purpose

Expand beyond CRBN/VHL by designing a framework for new E3 recruiters. This is
important but should come after the core CRBN/VHL pipeline is reliable.

### Required Inputs

- E3 expression and essentiality.
- Ligandability pockets.
- Chemoproteomics hits.
- Covalent fragment screens.
- E3 dependency validation assays.
- RNF4/FEM1B-style experimental evidence.

### Outputs

| Output | Meaning |
| --- | --- |
| `e3_priority_score` | Whether this ligase is worth recruiter discovery |
| `recruiter_evidence_grade` | Ligand evidence strength |
| `assay_plan` | Required validation ladder |
| `do_not_use_reason` | Explicit stop reason |

### Algorithm

1. Rank E3s by biological context, expression, tractability, and safety.
2. Identify known ligands/fragments.
3. Propose recruiter validation ladder:
   - direct binding
   - competition
   - ternary formation
   - proteasome dependence
   - E3 knockout/rescue
4. Only promote an E3 after dependency evidence exists.

### First Implementation Files

- `synglue_agent/tools/e3_recruiter_discovery.py`
- `synglue_agent/schemas/e3_recruiter.py`
- `tests/test_e3_recruiter_discovery.py`

## Unified Ranking Formula

Candidate ranking should combine module outputs without hiding uncertainty:

```text
rank_score =
  0.18 * evidence_quality
+ 0.16 * degradation_prediction
+ 0.14 * ternary_geometry
+ 0.14 * cooperativity_potential
+ 0.12 * ubiquitination_geometry
+ 0.10 * permeability_admet
+ 0.08 * cell_context_fit
+ 0.05 * selectivity
+ 0.03 * synthesis_feasibility
- uncertainty_penalty
- contradiction_penalty
```

Hard stops override the formula:

- No plausible target binder: `REJECT`.
- No usable E3 recruiter: `REVISE`.
- No structural/ternary evidence for finalist: `INSUFFICIENT EVIDENCE`.
- Strong hook-effect risk with narrow dose window: `REVISE`.
- Poor permeability and no rescue strategy: `REVISE`.
- Missing measured evidence for experimental claim: downgrade to `PREDICTED`,
  never mark `MEASURED`.

## Build Milestones

### Milestone A: Structural Scoring Core

Deliver:

- `ubiquitination_geometry.py`
- `cooperativity_potential.py`
- PDB/pose fixtures
- structural scoring tests
- CLI:
  - `protacxtend structure score-ubiquitination`
  - `protacxtend structure score-cooperativity`

Exit gate:

- Scores toy/synthetic fixtures correctly.
- Handles missing chains/templates without crashing.
- Produces JSON with features, warnings, and status.

### Milestone B: Dose and Degradation Calibration

Deliver:

- `dose_response_simulator.py`
- `context_degradation_predictor.py`
- calibrated model registry hooks
- dose-response plots for reports

Exit gate:

- Simulates bell-shaped hook curves.
- Fits simple synthetic curves.
- Reports uncertainty and OOD flags.

### Milestone C: Experimental Backend

Deliver:

- experiment registry
- locked prediction artifacts
- feedback ingestion
- design-test-learn optimizer

Exit gate:

- Can ingest a real assay CSV.
- Can compare prediction vs measured result.
- Can recommend next batch with rationale.

### Milestone D: Proteome and E3 Expansion

Deliver:

- proteome selectivity loader
- E3 recruiter priority engine
- E3 validation assay plans

Exit gate:

- Produces context-specific selectivity warnings.
- Does not recommend novel E3 use without validation evidence.

## Implementation Priority for Next Pass

Start with external-first integration. This makes PROTACXtend scientifically
grounded before it adds new native models:

1. Wrap PROTAC-Degradation-Predictor behind the model registry.
2. Add RP-PROTAC as an audited uncertainty/OOD comparator.
3. Integrate/adapt the Deep-QSP Hook model for dose-response simulation.
4. Wrap PROTACFold as a gated ternary-structure branch.
5. Add the PROTAC ternary benchmark as the acceptance test for structural
   methods.
6. Add SynPROTAC as the synthesis-aware generation baseline.

Then build the native structural and learning modules:

1. Ubiquitination Geometry Scorer.
2. Cooperativity Potential Model.
3. Proteome-Context Selectivity Model.
4. Design-Test-Learn Optimizer.

The first native module remains Ubiquitination Geometry because it unlocks the
structural NP-hard part directly:

1. Create schema and module.
2. Support PDB/mmCIF pose reading.
3. Add chain-role assignment.
4. Add lysine enumeration and accessibility.
5. Add distance-to-E2-proxy scoring.
6. Add pose ensemble aggregation.
7. Add CLI/API/report integration.
8. Add tests with synthetic fixtures.

## References Checked

- Bai et al., "Modeling the CRL4A ligase complex to predict target protein
  ubiquitination induced by cereblon-recruiting PROTACs", JBC 2022:
  https://pubmed.ncbi.nlm.nih.gov/35101445/
- Bai et al. full text, JBC:
  https://www.jbc.org/article/S0021-9258(22)00093-X/fulltext
- Wurz et al., "Affinity and cooperativity modulate ternary complex formation
  to drive targeted protein degradation", Nature Communications 2023:
  https://pubmed.ncbi.nlm.nih.gov/37429875/
- Ma et al., "Frustration in the protein-protein interface plays a central role
  in the cooperativity of PROTAC ternary complexes", Nature Communications 2025:
  https://pubmed.ncbi.nlm.nih.gov/41022846/
- Ribes et al., PROTAC-Degradation-Predictor GitHub:
  https://github.com/ribesstefano/PROTAC-Degradation-Predictor
- Ribes et al., "Modeling PROTAC Degradation Activity with Machine Learning",
  2024:
  https://arxiv.org/abs/2406.02637
- DeepTernary, SE(3)-equivariant ternary complex prediction, 2025:
  https://arxiv.org/abs/2502.18875
- Coarse-grained alchemical cooperativity modeling, 2022:
  https://arxiv.org/abs/2208.06446

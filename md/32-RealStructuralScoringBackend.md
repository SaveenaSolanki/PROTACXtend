# Real Structural Scoring Backend Plan

## Goal

Convert PROTACXtend structural ranking from mostly proxy scoring into a pose-backed, metric-backed, uncertainty-labeled structural evidence layer.

This does not solve PROTAC design exhaustively. It makes the NP-hard ternary search tractable by running expensive structural scoring only on selected finalists and by preserving evidence provenance.

## Core Principle

PROTAC structural scoring must distinguish three evidence levels:

1. `proxy_only`
   - No ternary pose file exists.
   - Use cheap linker geometry and PROTAC-DB priors only.

2. `pose_backed_experimental`
   - A ternary PDB pose exists from P4ward, PRosettaC, HADDOCK, AlphaFold-Multimer, or manual modeling.
   - Compute contact, clash, lysine, and linker-strain metrics.

3. `calibrated`
   - Pose-backed metrics have been calibrated against measured degradation, ternary Kd/alpha, lysine mapping, or dose-response data.
   - This is not yet complete.

## One-By-One Build Steps

### Step 1: Local Pose-Backed Structural Scorer

Status: implemented as experimental backend.

Inputs:

- candidate_id
- ternary_pose_pdb
- target_chain, default `A`
- e3_chain, default `B`
- full_protac_smiles or linker_smiles

Outputs:

- interface contact count
- polar contact count
- steric clash count
- buried-SASA proxy
- nearest target lysine to E3 chain
- accessible/productive lysine count
- linker conformer strain proxy
- real structural consensus score
- backend label and warnings

Implementation:

- `synglue_agent/tools/structural_scoring.py`
- integrated into `ProtacDesignToolbox.assess_ternary_feasibility`
- surfaced in `TernaryFeasibilityResult`

### Step 2: P4ward Pose Integration

Status: partially scaffolded.

Use P4ward for finalist-only ternary generation.

Required third-party backend:

- P4ward
- Docker or local P4ward install
- MEGADOCK dependency
- OpenBabel
- RDKit

Important license note:

- P4ward/MEGADOCK path may be non-commercial depending on dependency licensing. Keep this visible in reports.

Implementation target:

- parse P4ward output pose files into `candidate.provenance["ternary_pose_pdb"]`
- run `score_ternary_pose_for_candidate`
- write `outputs/structural_runs/{run_id}/structural_consensus.json`

### Step 3: Interface Scoring Upgrade

Status: lightweight contact/clash proxy implemented; Rosetta upgrade pending.

Current local metrics:

- all heavy-atom contacts between target and E3 chains
- polar contacts
- steric clashes
- buried-SASA proxy from contact density

Recommended third-party upgrade:

- Rosetta InterfaceAnalyzer

Why:

- better interface energy
- buried unsatisfied polar metrics
- dG separated by interface
- packing/statistical quality

### Step 4: Lysine Geometry Upgrade

Status: local distance/accessibility proxy implemented.

Current local metrics:

- finds target-chain lysine NZ atoms
- measures nearest distance to E3 chain
- estimates whether lysine is exposed enough and within productive transfer window

Recommended upgrade:

- include full CRL/ubiquitin geometry for CRBN and VHL
- use lysine SASA from FreeSASA or Bio.PDB Shrake-Rupley
- eventually calibrate lysine windows against known productive degraders

### Step 5: Linker Strain Upgrade

Status: RDKit ETKDG/UFF conformer-energy proxy implemented.

Current local metrics:

- embed multiple conformers
- optimize with UFF
- use energy spread and rotatable-bond burden as strain proxy

Recommended upgrade:

- compare bound linker end-to-end distance from the modeled pose against relaxed conformer ensemble
- use MMFF when parameterized
- keep OpenBabel fallback for unusual chemistry

### Step 6: Consensus And Ranking Integration

Status: first integration implemented.

Score:

```text
real_structural_score =
  0.34 * interface_quality_score
+ 0.31 * lysine_geometry_score
+ 0.20 * linker_strain_score
+ 0.15 * interface_contact_presence
```

Ranking uses this through a conservative blend into `TernaryFeasibilityResult.ternary_plausibility_score`.

Cooperativity uses it through:

- interface_contact_score
- lysine_geometry_score
- linker_strain_score
- ternary_geometry_score

### Step 7: Calibration

Status: pending.

Required data:

- measured ternary Kd/alpha
- measured DC50/Dmax
- lysine mutation or ubiquitination-site evidence
- PAMPA/Caco-2 permeability
- dose-response curves for hook-effect fitting

Existing hooks:

- `cooperativity_calibration.csv`
- `hook_effect_calibration.csv`
- active-learning registry
- PROTAC-DB evidence priors

## Third-Party Tool Priority

1. P4ward: ternary pose generation.
2. Rosetta InterfaceAnalyzer: real interface energy and buried surface metrics.
3. RDKit ETKDG/UFF/MMFF: ligand/linker conformer strain.
4. FreeSASA or Bio.PDB: lysine/accessibility/SASA.
5. PRosettaC: independent PROTAC-specific modeling comparator.
6. HADDOCK3: restrained protein-protein docking fallback.
7. GNINA/Vina: binary ligand docking, useful upstream but not sufficient alone.

## Validation Set

Start with four cases:

- known BRD4-VHL ternary-positive example
- known BRD4-CRBN ternary-positive example
- weak/failed linker example
- impossible geometry synthetic example

Do not use PROTAC-DB as the whole truth. It is one partial evidence source.

## Current Limitations

- Local structural scorer needs a valid ternary pose PDB.
- Chain IDs must be known or inferable.
- Lysine geometry is approximate until a full CRL/ubiquitin model is included.
- Linker strain is conformer-energy proxy unless bound linker atoms are mapped.
- Rosetta/P4ward/PRosettaC/HADDOCK are not bundled executables.

## Why This Is Not Fully Solved Yet

The structural problem is not one decision. It is a coupled search over:

- target-warhead binary binding pose
- E3-ligand binary binding pose
- target/E3 protein-protein docking orientation
- linker conformer ensemble
- induced-fit protein side-chain/backbone changes
- lysine-to-E2/ubiquitin catalytic geometry
- productive ternary lifetime and cooperativity

Exact global optimization across this whole state space is not practical. Simplified protein-folding models have formal NP-hard results, and PROTAC ternary modeling adds flexible-ligand docking, protein-protein docking, induced fit, and experimental degradation biology on top. So the engineering target is not exhaustive proof of the best pose. The target is a bounded, evidence-ranked finalist workflow with clear uncertainty.

## Research Summary

- PRosettaC is a Rosetta-based PROTAC ternary modeling protocol that alternates protein-protein and PROTAC conformational sampling. It is useful but still benchmark-dependent.
- A 2024 benchmark compared PRosettaC, MOE, and ICM for experimentally observed PROTAC ternary structures, showing that PROTAC-specific tools can generate useful pose sets but not perfect universal answers.
- P4ward is a newer automated pipeline that takes binary complexes plus PROTAC structures and produces ternary models and summary tables. It is the best next integration target for open finalist-scale pose generation.
- HADDOCK3 is useful as an information-driven protein-protein docking fallback when restraints or known binding/interface hints exist.
- Rosetta InterfaceAnalyzer is appropriate for post-hoc protein-protein interface energy, buried surface area, and interface-quality metrics, but it does not score the protein-ligand part alone.
- DeepTernary and related SE(3)-equivariant models are promising for fast ternary prediction, but they still need local packaging, benchmark validation, and careful domain checks before promotion into ranking.
- PROTAC-DB is evidence-rich but incomplete. Absence from PROTAC-DB is not negative evidence, and PROTAC-DB should calibrate priors rather than define the whole PROTAC world.

## Resolution Roadmap

### Milestone A: Pose-Backed Local Structural Scoring

Status: implemented.

Done:

- PDB parser
- interface contact/clash scoring
- lysine distance/accessibility scoring
- RDKit linker strain proxy
- schema/report/ranking/cooperativity integration
- regression tests with synthetic ternary pose

Remaining:

- write structural scoring JSON artifacts per run
- add score-threshold explanations to report narratives

### Milestone B: P4ward Finalist Runner

Goal: generate ternary pose PDBs automatically for only the selected finalists.

Implementation:

- add `P4wardRunner`
- detect local executable or Docker image
- input binary target-warhead and E3-ligand complexes
- run top N finalists from `expensive_modeling_candidate_ids`
- attach best pose path to `candidate.provenance["ternary_pose_pdb"]`
- call local structural scorer
- store all pose scores, not just the best pose

Success criteria:

- P4ward absent gives a clean caveat, not a crash
- P4ward present produces pose-backed `TernaryFeasibilityResult`
- top-pose and ensemble-score are both exported

### Milestone C: Rosetta InterfaceAnalyzer

Goal: replace local contact-count interface proxy with real protein-protein interface metrics.

Implementation:

- add optional `RosettaInterfaceAnalyzerRunner`
- parse dG_separated, buried SASA, shape complementarity if available, unsatisfied polar metrics
- map into `interface_quality_score`
- keep local contact score as fallback

Success criteria:

- report shows Rosetta metrics when executable exists
- ranking labels interface evidence as Rosetta-backed

### Milestone D: Lysine Geometry With CRL/E2/Ubiquitin Context

Goal: move beyond nearest-E3 distance to catalytic plausibility.

Implementation:

- model or template CRBN/VHL Cullin-RBX1-E2/ubiquitin geometry
- compute target lysine distance/orientation to ubiquitin donor site
- compute lysine SASA using FreeSASA or Bio.PDB Shrake-Rupley
- score multiple lysines and expose best productive lysine

Success criteria:

- candidates with good binding but impossible lysine geometry are penalized
- report names the most plausible ubiquitination lysine

### Milestone E: Linker End-To-End Strain From Bound Pose

Goal: compare actual bound linker geometry to relaxed conformer ensemble.

Implementation:

- identify linker attachment atoms or map ligand handles
- measure bound end-to-end distance and torsion stress
- compare to RDKit/MMFF conformer ensemble distribution
- penalize poses only reachable by high-strain linker conformers

Success criteria:

- tiny linker changes can move score for physically meaningful reasons
- stereoisomer-specific structural scoring becomes possible

### Milestone F: Calibration And Active Learning

Goal: convert structural metrics into calibrated degradation priors.

Implementation:

- assemble measured DC50/Dmax, ternary Kd/alpha, permeability, lysine evidence, and hook curves
- train calibration model with uncertainty
- validate on held-out target/E3/linker families
- promote only if validation beats current proxy
- keep rollback artifact

Success criteria:

- model has held-out performance report
- failed predictions feed active-learning queues
- reports separate calibrated evidence from heuristic proxy

## Source Links

- P4ward paper: https://pubs.acs.org/doi/abs/10.1021/acs.jcim.5c00614
- P4ward GitHub: https://github.com/SKTeamLab/P4ward
- PRosettaC paper: https://pmc.ncbi.nlm.nih.gov/articles/PMC7592117/
- 2024 PROTAC ternary benchmark: https://pubs.acs.org/doi/10.1021/acs.jcim.4c00426
- HADDOCK3 manual: https://www.bonvinlab.org/haddock3-user-manual/
- Rosetta InterfaceAnalyzer docs: https://docs.rosettacommons.org/docs/latest/application_documentation/analysis/interface-analyzer
- DeepTernary paper: https://www.nature.com/articles/s41467-025-61272-5

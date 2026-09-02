# PROTACPilot: A Generalized, Automated Architecture for End-to-End PROTAC Design

**Version:** 1.0 — Architecture & Design Document
**Date:** 2026-06-30
**Scope:** Universal pipeline from protein-of-interest to computationally validated PROTAC candidate

---

## 0. The Core Insight: Why Generalization Is Possible

Every PROTAC design problem reduces to the same six questions:

1. **Where does my warhead bind?** → Binding site & exit vector on the POI
2. **Which E3 ligase should I use?** → Subcellular colocalization, expression, prior art
3. **What linker length/composition connects them?** → Distance between exit vectors + conformational sampling
4. **Does a stable ternary complex form?** → PPI prediction + scoring + cooperativity
5. **Can the E2~Ub reach a surface lysine?** → Geometric filtering
6. **Will the PROTAC get into cells?** → Physicochemical property prediction

These six steps are **identical in structure** across all POI–warhead–E3 combinations. They differ only in the specific protein structures, ligand SMILES, and numerical thresholds. This means the pipeline can be built once and parameterized per target.

---

## 1. System Architecture Overview

```
                          ┌─────────────────────────────┐
                          │        User Input Layer      │
                          │  POI ID/PDB  Warhead SMILES  │
                          │  (optional: E3 preference)   │
                          └──────────────┬──────────────┘
                                         ▼
               ┌─────────────────────────────────────────────┐
               │        Module 1: POI Profiler               │
               │  • Structure retriever (AF/PDB/ESMFold)    │
               │  • binding site detector (FPocket/SiteMap) │
               │  • lysine scanner + surface accessibility   │
               │  • subcellular localization predictor       │
               │  • degradability score (DegradoMap-like)    │
               └──────────────────┬──────────────────────────┘
                                  ▼
               ┌─────────────────────────────────────────────┐
               │   Module 2: Warhead Analyzer               │
               │  • conformer generation (ETKDG/OMEGA)      │
               │  • rigid + induced-fit docking to POI      │
               │  • exit vector enumeration & ranking        │
               │  • pose clustering & consensus scoring      │
               └──────────────────┬──────────────────────────┘
                                  ▼
               ┌─────────────────────────────────────────────┐
               │   Module 3: E3 Ligase Selector             │
               │  • E3Atlas / ELITE integration             │
               │  • subcellular colocalization scoring       │
               │  • tissue expression matching               │
               │  • prior-success database lookup            │
               │  • returns: CRBN, VHL, DCAF1, RNF114, ...  │
               └──────────────────┬──────────────────────────┘
                                  ▼
               ┌─────────────────────────────────────────────┐
               │   Module 4: Linker Generator               │
               │  • length prediction from exit-vector dist  │
               │  • generative linker design (Link-INVENT)   │
               │  • library traversal (alkyl, PEG, mixed)    │
               │  • stereochemistry-aware enumeration        │
               └──────────────────┬──────────────────────────┘
                                  ▼
               ┌─────────────────────────────────────────────┐
               │   Module 5: Ternary Complex Modeler        │
               │  • protein-protein docking (Megadock)       │
               │  • PROTAC-constrained sampling (P4ward)     │
               │  • multi-linker screening                   │
               │  • PRosettaC refinement for top hits        │
               └──────────────────┬──────────────────────────┘
                                  ▼
               ┌─────────────────────────────────────────────┐
               │   Module 6: Ubiquitination Geometry Check   │
               │  • CRL model builder (Cullin+RING+E2~Ub)    │
               │  • lysine occlusion detection               │
               │  • distances from each lysine to E2~Ub      │
               │  • MD refinement for top candidates         │
               └──────────────────┬──────────────────────────┘
                                  ▼
               ┌─────────────────────────────────────────────┐
               │   Module 7: Physicochemical Filter          │
               │  • MW, cLogP, TPSA, HBD, HBA, RotB          │
               │  • bRo5-space evaluation                    │
               │  • permeability prediction (ML model)       │
               │  • solubility prediction                    │
               │  • chameleonic behavior score               │
               └──────────────────┬──────────────────────────┘
                                  ▼
               ┌─────────────────────────────────────────────┐
               │   Module 8: Activity Predictor (ML)        │
               │  • PROTACable-style graph transformer       │
               │  • DC50 / Dmax prediction                   │
               │  • uncertainty quantification               │
               └──────────────────┬──────────────────────────┘
                                  ▼
               ┌─────────────────────────────────────────────┐
               │        Output Layer                         │
               │  • ranked PROTAC candidates + SMILES        │
               │  • predicted TC structures (PDB)            │
               │  • degradation probability                  │
               │  • failure diagnosis report                  │
               │  • next-iteration recommendations           │
               └─────────────────────────────────────────────┘
```

---

## 2. Module-by-Module Specification

### Module 1: POI Profiler

**Input:** UniProt ID, PDB ID, or uploaded structure file
**Output:** POI report (binding sites, lysine map, localization, degradability)

| Submodule | Method | Output |
|---|---|---|
| Structure retrieval | AlphaFold DB → PDB; fallback: ESMFold | Full-length POI structure |
| Domain parsing | InterProScan, UniProt annotation | Domain boundaries |
| Binding site detection | FPocket + SiteMap + P2Rank (consensus) | Ranked binding pockets (volume, depth, SASA) |
| Lysine scanner | In-house: enumerate all Lys; compute relative SSA via FreeSASA | List of Lys residues with SSA, secondary structure, B-factor |
| Lysine accessibility | Geometric occlusion check (P4ward-style) | Accessible Lys list (SASA > 30 Å², not buried) |
| Subcellular localization | Deeploc 2.0 or UniProt annotation | Nuclear/cytoplasmic/mitochondrial |
| Degradability score | DegradoMap (GNN) or random forest | Score 0–1 (probability of being PROTAC-degradable) |

**Implementation notes:**
- The lysine scanner is critical. The output feeds into Module 6.
- Use the POI sequence to check for known degrons (C2H2 ZF for CRBN, etc.).
- For targets without known structure, run ESMFold or AlphaFold immediately.

### Module 2: Warhead Analyzer

**Input:** Warhead SMILES (with explicit stereochemistry) + POI structure + binding pocket
**Output:** Docking poses ranked by score, with exit vectors annotated

| Submodule | Method | Output |
|---|---|---|
| Conformer generation | RDKit ETKDG (500 conformers) or OMEGA | Multi-conformer warhead library |
| Rigid docking | AutoDock Vina / GNINA (consensus) | Top 100 poses |
| Induced-fit docking | Schrödinger IFD or DiffDock | Refined poses with receptor flexibility |
| Exit vector analysis | In-house: for each pose, compute vector from warhead center-of-mass to the solvent-exposed atom furthest from the protein surface | Ranked exit vectors with direction and solvent exposure score |
| Pose clustering | Butina clustering (RMSD 2 Å) | Cluster representatives |
| Consensus scoring | Rank-by-rank voting across docking programs | Final ranked pose list |

**Critical feature:** The exit vector is the most underappreciated variable in PROTAC design. The pipeline must:
1. For each docking pose, identify which heavy atoms of the warhead are solvent-accessible and not involved in protein contacts.
2. Rank attachment positions by: (a) solvent accessibility, (b) vector pointing away from protein, (c) synthetic accessibility of the modified warhead.
3. If no solvent-exposed attachment point exists → warn user that this warhead is unsuitable for PROTAC (flag for alternative warhead search).

### Module 3: E3 Ligase Selector

**Input:** POI subcellular localization + available E3 ligands + optional tissue/cell line context
**Output:** Ranked E3 ligase list with rationale

**Core logic — this is the key decision engine:**

```
For each E3 ligase in the database (CRBN, VHL, DCAF1, RNF114, FEM1B, DCAF16, Mdm2, IAP, KEAP1, etc.):

1. Subcellular colocalization score:
   - Does the E3 localize to the same compartment as the POI?
   - CRBN: nuclear + cytoplasmic (KPNB1-import) → score 1.0 for nuclear POIs
   - VHL: predominantly cytoplasmic → score 0.3 for nuclear, 1.0 for cytoplasmic
   - DCAF1: nuclear → score 1.0 for nuclear
   - RNF114: cytoplasmic + plasma membrane → score 0.5 for nuclear

2. Expression match:
   - Query E3Atlas / GTEx for tissue expression
   - Match against POI expression (from Human Protein Atlas)
   - Score = Pearson correlation of tissue expression profiles

3. Prior success:
   - Literature mining for this E3 with similar POI class (nuclear, transcription factor, chromatin, kinase, etc.)
   - Success rate = # of degraders / # of attempts

4. Ligand availability:
   - Is a high-affinity small-molecule ligand known for this E3?
   - CRBN: thalidomide, pomalidomide, lenalidomide → YES
   - VHL: AHPC, VH032 → YES
   - DCAF1: compound 1 (2024) → emerging
   - RNF114: EN219 → emerging

5. Final ranking: weighted sum of above scores
   (default weights: colocalization 0.4, expression 0.2, prior success 0.2, ligand availability 0.2)
```

**E3 ligand library (hardcoded):**

| E3 | Ligand | MW | cLogP | Exit vector(s) | Notes |
|---|---|---|---|---|---|
| CRBN | Thalidomide | 258 | 0.5 | 4-position (phthalimide) | Racemizes; neosubstrate risk |
| CRBN | Pomalidomide | 273 | 0.7 | 4-position | Higher CRBN affinity than thalidomide; still neosubstrate risk |
| CRBN | Lenalidomide | 259 | 0.1 | 3-position (free NH2) | Different exit vector; fewer neosubstrates |
| VHL | AHPC (VH032) | 480 | 1.8 | 4-OH of hydroxyproline | Clean E3; high polarity |
| VHL | VH032-NH2 | 479 | 1.5 | Amide N-alkylation | Alternative exit vector |
| DCAF1 | Compound 1 (BMS) | ~450 | ~2 | Piperidine N | Emerging; no neosubstrate issues known |
| RNF114 | EN219 | ~400 | ~2 | Acrylamide warhead | Covalent; different mechanism |

### Module 4: Linker Generator

**Input:** Warhead exit vector + E3 ligand exit vector + predicted distance between them
**Output:** Ranked set of linker SMILES

**Step A — Length prediction:**

1. From Module 2: the warhead exit vector defines an origin and direction on the POI surface.
2. From Module 3: the E3 ligand exit vector defines a direction from the E3 surface.
3. The distance between these two points in a hypothetical ternary complex is estimated as: 
   `d_required = d_exit_to_surface(POI) + d_cleft + d_surface_to_exit(E3)`
   where d_cleft is the expected gap between POI and E3 surfaces (typically 5–15 Å).
4. Initial estimate: `d_required ≈ 8–20 Å`, depending on pocket depth and surface curvature.

**Step B — Generative design:**

Using Link-INVENT or a fine-tuned REINVENT model:

```
Input: fragment_A (warhead with exit vector functionalized) + 
        fragment_B (E3 ligand with exit vector functionalized) +
        target_length_range (from Step A)

Process:
  RL agent proposes linker fragments that connect A and B.
  Reward function = f(span_match, synthetic_accessibility, druglikeness, 
                       rotatable_bond_penalty)
  
Output: top 100 linker SMILES
```

**Step C — Library traversal (fallback if generative model unavailable):**

Pre-enumerated linker library categorized by length and composition:

| Category | Length (atoms) | Examples | Use case |
|---|---|---|---|
| Ultra-short | 2–4 | C2, C3, C4 alkyl, PEG1 | Very shallow pockets |
| Short | 5–7 | C5, C6, PEG2 | Close-proximity TCs |
| Medium | 8–10 | C8, PEG3, C6-PEG2 | Most common TCs |
| Long | 11–14 | C10, PEG4, C8-PEG3 | Deep pockets, large proteins |
| Extra-long | 15–20 | C12-PEG4, PEG6 | Nuclear targets, chromatin-associated |
| Rigid | 6–12 (constrained) | Piperazine, triazole, spirocycles | Pre-organization for positive cooperativity |

Each linker is fully enumerated with explicit stereochemistry. PEG linkers are preferred for permeability; mixed alkyl-PEG for solubility balance.

### Module 5: Ternary Complex Modeler

**Input:** POI structure, E3 structure, warhead + E3 ligand + linker SMILES
**Output:** Ranked TC models with scores

**Primary engine: P4ward** (open-source, fast, 76.5% hit rate)

```
P4ward pipeline (automated):
1. Protein preparation (OpenMM minimization)
2. Protein-protein docking (Megadock) → 54,000 poses
3. Distance filter (exit vectors must be within linker's max span)
4. Lysine occlusion filter (≥1 accessible Lys within 60 Å of Ubq C-term)
5. PROTAC conformer sampling (RDKit, constrained by ligand positions)
6. Protein-PROTAC interaction rescoring (RXDock)
7. Trend clustering
8. Final ranking by combined PPI + PPI score
```

**Refinement step** (for top 10 candidates):

PRosettaC or AlphaFold 3 for higher accuracy. PRosettaC is preferred per the 2025 benchmark (outperforms AF3 for PROTAC TCs).

**Key scoring metrics:**

| Metric | Target Range | Source |
|---|---|---|
| Interface Score (Isc) | < −5 Rosetta units | PRosettaC |
| Shape complementarity (Sc) | > 0.6 | Rosetta |
| Buried surface area (BSA) | > 800 Å² | PISA |
| Linker strain energy | < 5 kcal/mol | RDKit MMFF |
| Interface energy (ΔG) | < −5 kcal/mol | MM-PBSA |

### Module 6: Ubiquitination Geometry Check

**Input:** TC model (POI + E3 + PROTAC + CRL model)
**Output:** Feasibility score for each candidate

**CRL model construction:**

1. Retrieve or build the full Cullin–RING–E2~Ub assembly:
   - CUL2–RBX1–E2~Ub for VHL (PDB: 5N4W, 4W9H-based homology)
   - CUL4A/4B–RBX1–DDB1–CRBN–E2~Ub for CRBN (PDB: 6BOY, 4TZ4-based homology)
2. Align the E3 substrate receptor into the CRL complex.
3. The E2~Ub active site is located on the E2 (UBE2R1/UBE2D3), ~50 Å from the substrate receptor.

**Lysine accessibility check:**

For each surface lysine on the POI (from Module 1):

1. Calculate distance from Lys Cε to the Gly76 C-terminal carbon of Ub (in E2~Ub).
2. **If distance < 20 Å → Likely ubiquitination site** (direct reach within catalytic cleft)
3. **If distance 20–30 Å → Possible** (requires conformational flexibility)
4. **If distance > 30 Å → Unlikely** (even with flexibility)

Apply occlusion check: trace a vector from Lys Cε to Ub Gly76. If any POI backbone atoms are within 5 Å of this vector, the lysine is occluded.

**Final feasible lysine count:** ≥1 accessible Lys within 25 Å of E2~Ub = geometry feasible.

### Module 7: Physicochemical Filter

**Input:** PROTAC SMILES
**Output:** Permeability/solubility score + ADME flags

**Standard properties:**

| Property | bRo5 Alert | Optimal for PROTACs |
|---|---|---|
| MW (Da) | > 1000 | 700–900 |
| cLogP | > 7 | 2–5 (CRBN); 3–6 (VHL) |
| TPSA (Å²) | > 200 | 100–180 |
| HBD | > 3 | 1–3 |
| HBA | > 10 | 5–9 |
| Rotatable bonds | > 15 | 8–14 |
| Fsp³ | < 0.3 | > 0.4 |

**Chameleonic behavior score:**

Recent work (2025) shows that CRBN-based PROTACs with aromatic-rich linkers can fold via intramolecular hydrophobic collapse, reducing TPSA in the membrane. Score this by:

1. Generate low-energy conformers in implicit water (ε=80) and implicit membrane (ε=2–4).
2. Measure the ratio of TPSA(water) / TPSA(membrane). Ratio > 1.3 suggests chameleonic behavior.
3. This is a positive feature for CRBN PROTACs, less relevant for VHL.

**Permeability ML model:**

Train a gradient-boosted or GNN model on the PROTAC permeability dataset (likely from the *Predictive Modeling of PROTAC Cell Permeability* paper, ACS Omega, 2023, or the more recent bRo5 permeability models). Features: molecular graph, 2D descriptors, and 3D conformational descriptors (radius of gyration, solvent-accessible surface area in folded vs extended states).

### Module 8: ML Activity Predictor

**Input:** PROTAC SMILES + POI features + E3 features
**Output:** Predicted DC50 (nM) + Dmax (%) + uncertainty

**Model architecture (inspired by PROTACable):**

1. **Encoder:** SE(3)-equivariant graph transformer that takes:
   - PROTAC molecular graph (atoms + bonds)
   - 3D conformer coordinates (from MMFF minimization)
   - POI pocket features (optional, from encoder of pocket residues)
   - E3 surface features (optional)
2. **Prediction head:** Multi-task output
   - DC50 (log nM) — regression
   - Dmax (%) — regression (0–100)
   - Degradation probability — classification (degrader vs non-degrader)
3. **Uncertainty:** Monte Carlo dropout or evidential regression

**Training data:**
- PROTAC-DB (≥2000 PROTACs with activity data)
- Internal data from collaborators
- Augmented with negative data (synthesized but inactive PROTACs)

**Crucial note:** This model is only reliable when predicting within the training distribution. For novel warhead–E3 pairs, the model should signal high uncertainty and the pipeline should fall back to physics-based scoring.

---

## 3. Integration and Orchestration

### Workflow Manager

The entire pipeline is orchestrated by a Python workflow manager with the following logic:

```
protacpilot run \
  --poi P26583 \                    # UniProt ID for HMGB2
  --warhead "CC1(C2=CCN3..." \      # Inflachromene SMILES
  --e3 CRBN                         # optional: force a specific E3
  --cell-line "HEK293T"             # optional: cell context
  --output ./protacpilot_output/
```

### Iterative Loop (The Key to Generalization)

```
┌────────────────────────────────────────────────────────┐
│                    ITERATIVE LOOP                      │
│                                                        │
│  Round 1: Run M1–M8 with default parameters            │
│  → Output: top 10 PROTAC candidates + failure report   │
│                                                        │
│  If NO candidates pass all filters:                    │
│  ├─ M2: try different exit vectors on warhead          │
│  ├─ M3: switch E3 ligase (CRBN ↔ VHL ↔ DCAF1)         │
│  ├─ M4: extend linker length range                     │
│  ├─ M5: use AF3 instead of P4ward for TC               │
│  └─ M7: relax bRo5 constraints                         │
│                                                        │
│  If candidates exist but all fail M6 (no lysine reach): │
│  ├─ M4: try longer, more flexible linkers              │
│  ├─ M3: try CRBN (has different CRL geometry)          │
│  └─ Report: "Target may not be degradable via this      │
│              warhead. Consider alternative warheads."    │
│                                                        │
│  If candidates pass all filters → Output for synthesis  │
│                                                        │
│  After experimental feedback:                          │
│  ├─ Degradation observed → M8: retrain model           │
│  └─ No degradation → M5: refine TC model with MD       │
│                                                        │
└────────────────────────────────────────────────────────┘
```

### Caching and Knowledge Base

- Each run's results are stored in a SQLite database.
- Over time, the system builds a **knowledge graph**:
  - POI → predicted best E3 ligase
  - Warhead → preferred exit vector
  - Linker length → success rate by E3
  - These statistics improve the prior-success terms in Module 3.

---

## 4. The HMGB2–Inflachromene Case Study: Generalized Diagnosis

Running the HMGB2 case through the generalized pipeline would automatically produce:

```
PROTACPilot Run Report — HMGB2 (P26583) / Inflachromene
================================================================

MODULE 1: POI Profiler
  Localization: nuclear (score 0.97)
  Lysine count: 20 surface-exposed (SASA > 30 Å²)
  Degradability score (DegradoMap): 0.72 / 1.0 (degradable)
  → Target is likely degradable in principle

MODULE 2: Warhead Analyzer
  ICM binding mode: predicted on Box A surface (DNA-binding cleft)
  Exit vectors available: 3 (positions 7-OH, phenyl 4-position, N-methyl)
  Best exit vector: 7-OH (synthetic accessibility: moderate)
  → Docking score: −6.2 kcal/mol (moderate; µM affinity expected)

MODULE 3: E3 Ligase Selector
  Recommended: CRBN (colocalization score 1.0)
  Also viable: VHL (score 0.3 for nuclear; would require cytoplasmic HMGB2)
  Best ligand: pomalidomide (higher CRBN affinity than thalidomide)
  → Switching from AHPC/VHL to pomalidomide/CRBN strongly recommended

MODULE 4: Linker Generator
  Required length: 12–16 Å (ICM is recessed in DNA-binding cleft)
  Current C4/C6/C8: INSUFFICIENT (max effective span ~10 Å)
  Recommended: C10-PEG4 or C12-PEG3-alkyl
  → Generating 50 linker candidates...

MODULE 5: Ternary Complex Modeling
  P4ward run: 6/6 current PROTACs → NO stable TC predicted
                   (linker too short for all)
  New candidates (C12-PEG4, pomalidomide): 3/10 → stable TC predicted
  → Table below.

MODULE 6: Ubiquitination Geometry Check
  Best candidate: HMGB2_K152 → E2~Ub distance 18.7 Å (FEASIBLE)
  Also: K90, K146, K154 within 25 Å

MODULE 7: Physicochemical Filter
  C12-PEG4-pomalidomide-ICM: MW 892, cLogP 4.2, TPSA 168, HBD 2
  → Passes bRo5 filter (flagged for moderate permeability)
  → Chameleonic score: 1.4 (favorable folding behavior)

MODULE 8: Activity Predictor
  Predicted DC50: 87 nM (CI: 32–240 nM)
  Predicted Dmax: 72% (CI: 55–85%)
  Confidence: MEDIUM (novel warhead–E3 pair)

ITERATION 1 RECOMMENDATION:
  ┌─────────────────────────────────────────────────────────┐
  │ Synthesize: ICM–(C12-PEG4)–Pomalidomide                │
  │ Alt: ICM–(C10-PEG3-amide)–Lenalidomide                  │
  │ Alt: ICM–(C8-PEG3-C2-alkyl)–Pomalidomide                │
  │                                                         │
  │ Avoid: Any VHL-based PROTAC (localization mismatch)     │
  │ Avoid: Any linker < C10 (too short)                     │
  └─────────────────────────────────────────────────────────┘

DIAGNOSIS OF CURRENT FAILURE:
  Primary: Linker too short (C4/C6/C8 cannot span required distance)
  Secondary: VHL is suboptimal for nuclear HMGB2
  Tertiary: ICM binding mode uncertain (exit vector may be wrong)
```

---

## 5. Implementation Roadmap

### Phase 1: Core Pipeline (2 months)

| Component | Dependencies | Priority |
|---|---|---|
| M1: POI Profiler | FreeSASA, AlphaFold API, FPocket | P0 |
| M2: Warhead Analyzer | RDKit, AutoDock Vina/GNINA | P0 |
| M3: E3 Selector | E3Atlas API, literature DB | P0 |
| M4: Linker library | Pre-enumerated SMILES library | P0 |
| M5: P4ward integration | Docker (for Megadock, OpenMM, RXDock) | P0 |
| Orchestrator | Python workflow engine | P0 |

### Phase 2: Advanced Modeling (2 months)

| Component | Dependencies | Priority |
|---|---|---|
| M5 refinement: PRosettaC | Rosetta license | P1 |
| M5 refinement: AF3 | AF3 API access | P1 |
| M6: CRL model builder | PDB structures, PyMOL/PyRosetta | P1 |
| M6: MD refinement | OpenMM or AMBER | P2 |

### Phase 3: ML Layer (3 months)

| Component | Dependencies | Priority |
|---|---|---|
| M8: PROTACable-style predictor | PyTorch Geometric, training data | P1 |
| M7: Permeability ML model | Training dataset curation | P1 |
| M4: Generative linker (RL) | REINVENT / Link-INVENT | P2 |
| M1: DegradoMap integration | GNN framework | P2 |

### Phase 4: Iterative Learning (ongoing)

| Component | Dependencies | Priority |
|---|---|---|
| Knowledge graph | Neo4j or SQLite | P2 |
| Experimental feedback loop | Web interface for data entry | P2 |
| Retraining pipeline | CI/CD for ML models | P3 |

---

## 6. Key Scientific Challenges & Mitigations

| Challenge | Mitigation |
|---|---|
| **ICM binding mode unknown** (no crystal structure) | Use docking consensus (Vina + GNINA + DiffDock); if inconsistent, flag for experimental validation (NMR or X-ray) |
| **HMGB2 is chromatin-bound** (lysines occluded by DNA) | Model the DNA-bound state; use MD to simulate HMGB2 dissociation; or design for the free-state conformation |
| **bRo5 permeability is hard to predict** | Use chameleonic scoring + ML permeability model; prioritize CRBN over VHL for better permeability |
| **Neosubstrate degradation by CRBN** | Run IKZF1/3 degradation control experiments; consider lenalidomide (fewer neosubstrates) |
| **No positive cooperativity** (weak warhead) | Design longer, more rigid linkers that pre-organize the TC; use PRosettaC to screen for favorable PPIs |
| **Low E2~Ub in the nucleus** | CRBN uses UBE2D3/UBE2G1 which are present in the nucleus; this is a minor concern |

---

## 7. What You'd Need to Build This

### Software

| Tool | License | Use |
|---|---|---|
| RDKit | BSD | Conformer generation, linker handling |
| AutoDock Vina / GNINA | Apache / Academic | Warhead docking |
| FPocket | BSD-3 | Binding site detection |
| OpenMM | MIT | Protein preparation, MD |
| FreeSASA | MIT | SASA calculation |
| P4ward | Open source (bioRxiv 2024) | TC modeling (core engine) |
| Megadock | Free for academics | Protein-protein docking |
| RXDock | LGPL | Protein-ligand scoring |
| PRosettaC | Web server (free for academics) | TC refinement |
| REINVENT (optional) | MIT | Generative linker design |
| PyTorch Geometric | MIT | ML models |

### Hardware

- **Minimum:** 16 CPU cores, 64 GB RAM, 1 GPU (e.g., RTX 4090)
- **Recommended:** 32+ CPU cores, 128 GB RAM, 1–2 GPUs (A6000 or better)
- **For large screens:** Cloud compute (AWS/GCP/Modal with GPU nodes)

### Expertise

- Computational chemistry (docking, conformer analysis)
- Structural biology (protein-ligand complexes, MD)
- Python development (pipelines, APIs)
- ML/DL (graph neural networks, transformers)
- Synthetic chemistry (to validate proposed designs)

---

## 8. Success Metrics

| Metric | Target | How to Measure |
|---|---|---|
| TC prediction hit rate (bound) | > 85% | Benchmark against 36 known TC PDBs |
| TC prediction hit rate (unbound) | > 75% | Same benchmark |
| False positive rate in activity ML | < 20% | Experimental validation of top 10 per target |
| Pipeline runtime per target | < 24 h | Total wall-clock time |
| Successful degradation rate (novel targets) | > 50% after 2 iterations | % of targets where ≥1 PROTAC shows DC50 < 1 µM |

---

## 9. Relation to Existing Tools

| Tool | How PROTACPilot differs |
|---|---|
| **P4ward** | PROTACPilot wraps P4ward as M5, adds M1–M4 (input prep) and M6–M8 (post-processing + ML) |
| **PROTACable** | PROTACPilot uses a similar ML approach for M8 but adds physics-based M1–M7 steps; more modular |
| **PRosettaC** | Used only for TC refinement (not the whole pipeline); PROTACPilot handles the full upstream workflow |
| **SynGlue** | Generative AI; PROTACPilot could integrate SynGlue as an alternative linker generator in M4 |
| **E3Atlas/ELITE** | Integrated directly as M3 |
| **DegradoMap** | Integrated as the degradability predictor in M1 |

PROTACPilot is designed as an **integrative orchestrator** — it does not replace these tools but uses them as building blocks in a unified, automated, universally parameterized workflow.

---

## 10. Conclusion: The Generalization Thesis

A generalized PROTAC design pipeline is **feasible** because:

1. **The physics is the same** for every target: you need a warhead, an E3 ligand, a linker of the right length, and a ternary complex geometry that puts a lysine near E2~Ub.
2. **The computational tools exist** (P4ward, PRosettaC, RDKit, docking programs) and are mature enough to be chained together.
3. **The failure modes are finite** (listed in Section 6 of the HMGB2 analysis) and can be diagnosed algorithmically.
4. **Machine learning can accelerate** the screening once enough data accumulates, but physics-based modeling provides the necessary foundation.

**The key insight:** The six-module architecture is target-agnostic. Only the numerical thresholds and the specific 3D structures change between runs. This means a single codebase can serve any POI–warhead pair.

The bottleneck is not the science — it's the **integration**. Each individual tool exists. What doesn't exist is a robust, automated orchestrator that handles all edge cases, passes information correctly between modules, and iterates intelligently when the first round fails. That is exactly what PROTACPilot should be.

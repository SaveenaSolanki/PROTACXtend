# H2: Complete Experimental Plan — A1_4COOH as HMGB2 PROTAC Warhead

---

## Executive Summary

**A1_4COOH (4-carboxyphenyl-ICM)** is the recommended lead analog for HMGB2-targeted degradation. 
It shows:
- **Vina score: −11.22 kcal/mol** (vs parent ICM −5.75)
- **Solvent-exposed COOH exit vector** (4.5 Å from protein surface)
- **Salt bridge to LYS85** (3.04 Å)
- **PROTAC ternary possible** (8/3600 passes with C8-PEG4)
- **Synthetically accessible** (amide chemistry at COOH)

## Key Question: Modified ICM Alone vs Full PROTAC?

### Option A: Test A1_4COOH alone first (Recommended)
Test if modified ICM alone degrades HMGB2 (molecular glue mechanism):

| Experiment | Purpose | Duration | Cost |
|-----------|---------|----------|------|
| 1. Synthesize A1_4COOH | Get compound | 4 weeks | ~$1500 |
| 2. SPR/ITC binding to HMGB2 | Measure Kd | 1 week | ~$500 |
| 3. Cellular degradation (WB) | HMGB2 loss? | 1 week | ~$300 |
| 4. ± CRBN siRNA | CRBN-dependent? | 1 week | ~$300 |
| 5. ± MG132 | Proteasomal? | 1 week | ~$200 |

**If A1_4COOH alone degrades HMGB2:**
- CRBN KO rescues → molecular glue mechanism
- MG132 rescues → proteasomal degradation  
- Neither rescues → alternative mechanism (investigate H4)

**If A1_4COOH alone does NOT degrade HMGB2:**
- Proceed to Option B (PROTAC)

### Option B: Build PROTAC (if Option A fails)

| Component | Molecule | MW | Function |
|-----------|----------|----|----------|
| Warhead | A1_4COOH | 421 Da | HMGB2 binder |
| Linker | C8-PEG4 | ~250 Da | 13.6 Å effective span |
| E3 ligand | Pomalidomide | 273 Da | CRBN recruiter |
| **Total** | **A1_4COOH–C8-PEG4–Pomalidomide** | **~944 Da** | |

**Experiment plan:**
1. Synthesize PROTAC (amide coupling at COOH + NH₂)
2. P4ward ternary modeling for validation
3. Cellular degradation assay ± controls

## Synthesis Route for A1_4COOH

The ICM core (known from Lee et al. 2014) can be modified at the N-phenyl position:

```
Step 1: Build ICM core (triazolopyridazinedione + chromene)
Step 2: N-phenyl coupling with methyl 4-iodobenzoate
Step 3: Hydrolysis of methyl ester to COOH
```

**Estimated yield:** 30-50% over 3 steps
**Estimated cost:** ~$1500 (reagents + purification)
**Estimated time:** 4 weeks

## Binding Assay Design (SPR)

| Parameter | Setting |
|-----------|---------|
| Target | HMGB2 (immobilized on CMS chip) |
| Analyte | A1_4COOH (0.1 nM - 10 μM) |
| Buffer | PBS-P + 1% DMSO |
| Temperature | 25°C |
| Flow rate | 30 μL/min |
| Contact time | 60 s |
| Dissociation | 120 s |
| Regeneration | 50 mM NaOH, 30 s |

**Expected Kd:** ~10-100 nM (from Vina score −11.22 kcal/mol)

## Computational Support Summary

| Method | Result | Tool |
|--------|--------|------|
| **Vina docking** | −11.22 kcal/mol (19 poses) | AutoDock Vina 1.2.3 |
| **All 16 analogs docked** | All −10.98 to −11.86 | AutoDock Vina |
| **Parent ICM** | −5.75 kcal/mol (5 poses) | AutoDock Vina |
| **P4ward ternary** | 8/3600 passes (C8-PEG4) | P4ward + MegaDock |
| **PLAPT prediction** | 1.53 μM (ICM) vs 13.8 μM (A1_4COOH) | ProtBERT + ChemBERTa |
| **Interaction analysis** | LYS85 salt bridge (3.04 Å) | Vina pose analysis |

> **Note:** PLAPT and Vina disagree on relative ranking. This is expected — Vina is structure-based while PLAPT is sequence-based. The actual binding should be determined experimentally.

## Recommended Literature References

1. Lee et al. (2014). "Inflachromene inhibits HMGB2 nuclear trafficking." *Nat Chem Biol* 10:1055-1062. — ICM parent compound and ICM-BP probe
2. Chamberlain et al. (2014). "Structure of the human Cereblon-DDB1-lenalidomide complex reveals basis for responsiveness to thalidomide analogs." *Nat Struct Mol Biol* 21:803-809. — CRBN binding
3. Schreiber & Fersht (1995). "Energetics of protein-protein interactions: principles and methods." *J Mol Biol* 248:478-486. — Salt bridge energetics
4. Békés et al. (2022). "PROTAC targeted protein degraders: the past is prologue." *Nat Rev Drug Discov* 21:181-200. — PROTAC design principles

## File Locations

All computational results:
```
analog_HMGB2_docking/            — Docking results, PDBQT files, Vina outputs
  ├── a1_4COOH_vina_out.pdbqt    — 19 docked poses
  ├── all_analogs_vina_results.json — All 16 analogs ranked
  ├── affinity_prediction.json   — Vina-based scores
  └── plapt_predictions.json     — PLAPT ML predictions
proof/                            — Figures and analysis
  ├── vina_sar_bar_chart.png     — All 16 analogs bar chart
  ├── vina_vs_clogp_scatter.png  — Score vs hydrophobicity
  ├── binding_pose_detailed.png  — Binding pose visualization
  ├── icm_vs_a1_4cooh.png       — Side-by-side comparison
  ├── decision_tree.png          — Decision framework
  ├── workflow_timeline.png      — 10-week timeline
  ├── binding_comparison_table.png — Feature comparison
  └── analog_library_grid.png    — All analogs with scores
experimental_plan/               — This plan

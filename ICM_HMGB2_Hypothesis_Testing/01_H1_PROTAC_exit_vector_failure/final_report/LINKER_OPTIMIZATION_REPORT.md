# HMGB2–ICM–CRBN/Pomalidomide Linker Optimization Report

**Date:** 2026-07-06
**Status:** Geometric screen complete; P4ward running (C14-PEG5)
**Lead analysis:** Feynman computational chemistry pipeline

---

## Executive Summary

16 linker variants (PEG, mixed alkyl-PEG, alkyl, semi-rigid) were designed and tested against 3600 MegaDock orientations of CRBN around HMGB2. **The results reveal a fundamental geometry problem:** even the longest linker (C14-PEG5, 27 Å extended, 18.9 Å effective span) achieves only 30 passing poses out of 3600 (0.8%). Linkers shorter than ~17 Å extended length produce **zero** passing poses.

**Root cause:** Both ICM OH groups (the only viable linker attachment points) point **away from CRBN** (angles of 100°–105° relative to the HMGB2→CRBN vector). The ICM binding site on HMGB2 is on the far side from where CRBN can productively dock.

---

## 1. Linker Screening Results

### Geometric Screen (3600 poses × 16 linkers)

| Rank | Linker | Type | Ext. Length | Effective Span | Passed/3600 | % |
|------|--------|------|-------------|----------------|-------------|---|
| 1 | **C14-PEG5** | mixed | 27.0 Å | 18.9 Å | **30** | **0.8%** |
| 2 | **PEG8** | PEG | 22.4 Å | 15.7 Å | **16** | **0.4%** |
| 3 | **C8-PEG4** | mixed | 19.5 Å | 13.6 Å | **6** | **0.2%** |
| 4 | PEG6 | PEG | 16.8 Å | 11.8 Å | 1 | 0.03% |
| 5 | C6-PEG4 | mixed | 17.0 Å | 11.9 Å | 1 | 0.03% |
| 6–16 | All others | all | ≤14.7 Å | ≤10.3 Å | **0** | **0%** |

### Key finding

There is a **sharp threshold** at ~13–14 Å effective linker span:
- **Below 13 Å:** 0 passing poses (10 linkers, all failed)
- **At 13.6 Å:** 6 passing poses (C8-PEG4)
- **At 15.7 Å:** 16 passing poses (PEG8)  
- **At 18.9 Å:** 30 passing poses (C14-PEG5)

Even at 18.9 Å effective span, only **0.8%** of orientations pass — this is not a robust design.

### Plot
![Linker pass rate vs length](plot_linker_passrate.png)

---

## 2. Root Cause: ICM Binding Mode Geometry

### Both exit vectors point away from CRBN

| Measurement | OH27 (current) | OH29 (alternative) |
|-------------|---------------|-------------------|
| Position in HMGB2 frame | (2.57, 12.32, 0.29) | (0.73, 15.51, 3.34) |
| Distance from HMGB2 center | 10.7 Å | 14.2 Å |
| Distance to HMGB2 surface | ~5–6 Å | ~7 Å |
| Angle to HMGB2→CRBN vector | **105°** | **100°** |
| Points toward CRBN? | **NO** (points away) | **NO** (points away) |

### Interpretation

```
                  HMGB2 surface
                 ┌─────────────┐
                 │             │
    CRBN ←────── │             │ ←──── ICM OH27 (105° away from CRBN)
    approaches   │   ICM   OH29│ ←──── OH29 (100° away from CRBN)
    from this    │   binds     │
    side         │   here      │
                 │             │
                 └─────────────┘
```

ICM binds HMGB2 on the **opposite side** from where CRBN can approach. The OH groups point further away from CRBN, not toward it. This is why even very long linkers barely help — the linker has to wrap around HMGB2 to reach CRBN.

### Why the original P4ward failed

The original C4-equivalent linker (0.74 Å max span) had zero chance because:
1. The exit vectors are 10.83 Å apart in the closest orientation
2. The ICM exit vector points away from CRBN
3. No orientation of CRBN around HMGB2 can bring the two exit vectors close

---

## 3. Linker Design Considerations

### What worked (marginally)

- **C14-PEG5** (mixed alkyl-PEG, 27 Å): 30/3600 = 0.8% pass rate
- **PEG8** (pure PEG, 22.4 Å): 16/3600 = 0.4% pass rate

These linkers are extremely long for PROTACs (27 Å is near the upper limit of known degraders). Most successful PROTACs use 8–14 atom linkers (8–15 Å).

### What didn't work

- **Alkyl linkers** (C10, C12, C14): 0% — too rigid/short
- **Semi-rigid** (piperazine, triazole): 0% — conformational restriction is detrimental when flexibility is needed
- **Mixed alkyl-PEG** with <17 Å extended length: 0%
- **PEG** with <16.8 Å extended length: 0%

---

## 4. P4ward Run Status

### C14-PEG5 + Pomalidomide (best candidate)

| Stage | Status | Notes |
|-------|--------|-------|
| Protein fixation | ✅ Complete | 8s |
| Receptor minimization | ✅ Complete | 11s |
| Ligase minimization | 🔄 Running | Using pre-minimized PDB |
| MegaDock (3600 poses) | ⏳ Pending | ~3 min |
| Linker distance filter | ⏳ Pending | ~1 min |
| Ubiquitination filter | ⏳ Pending | ~1 min |
| CRL complex writing | ⏳ Pending | ~1 min |

Expected total runtime: **~2–4 hours** (reduced from original ~3.5h due to pre-minimized proteins)

### To check progress:
```bash
tail -f outputs/p4ward_evidence/linker_optimization/p4ward_C14-PEG5/p4ward_run.log
```

---

## 5. Recommendations (Priority Order)

### 🔴 Immediate

1. **Test alternative ICM exit vector (OH29)**
   - Geometric screen only — re-run with OH29 coordinates
   - Expected improvement: 2–5× more passing poses
   - Still unlikely to exceed ~3% pass rate

2. **Dock Hoechst 33258 to HMGB2** and test exit vector geometry
   - Best Vina score (−6.49 kcal/mol)
   - DNA minor groove binder — likely binds in the HMGB2 DNA-binding cleft
   - Exit vector may point OUT of the cleft (toward solvent) — this would be favorable
   - **This is the most promising alternative warhead**

3. **Dock PDS (Pyridostatin) to HMGB2**
   - Second-best Vina score (−5.87 kcal/mol)
   - G-quadruplex ligand — HMGB2 binds G4 DNA
   - Binding mode may place exit vectors in a different direction

### 🟡 Short-term

4. **Re-run geometric screen with Hoechst 33258 exit vectors**
   - If Hoechst's exit vector points toward CRBN, the pass rate could jump from 0.8% to >50%
   - This would make even moderate-length linkers (C8-PEG4, PEG6) viable

5. **Consider alternative E3 ligases** (DCAF1, RNF114, FEM1B)
   - Different surface geometries may be more compatible with ICM's binding site
   - Trade-off: less validated than CRBN

### 🟢 Medium-term

6. **Crystallize or MD-refine ICM–HMGB2 binding mode**
   - The current binding pose is from docking, not experimental structure
   - A different binding mode could shift the exit vectors significantly
   - NMR or cryo-EM would be definitive

7. **Consider HMGB2-targeting warheads beyond ICM**
   - Glycyrrhizin derivatives (Box B binder)
   - Modified DNA minor groove binders with HMGB2 selectivity
   - Peptide-based warheads (HMGB2 Box domain binders)

---

## 6. Data Files

All files in `outputs/p4ward_evidence/linker_optimization/`:

| File | Description |
|------|-------------|
| `linker_optimization_report.json` | Full structured results |
| `pomalidomide_for_p4ward.mol2` | Pomalidomide in CRBN pocket |
| `p4ward_C14-PEG5/` | P4ward run directory (best linker) |
| `p4ward_PEG8/` | P4ward run directory (2nd best) |
| `p4ward_C8-PEG4/` | P4ward run directory (3rd best) |
| `p4ward_PEG6/` | P4ward run directory |
| `p4ward_C6-PEG4/` | P4ward run directory |

### Plots

| File | Description |
|------|-------------|
| `plot_linker_passrate.png` | Pass rate vs linker length (scatter) |
| `plot02_distance_histogram.png` | Distance distribution of all 3600 poses |

---

## 7. Conclusion

**The ICM–HMGB2–CRBN ternary complex is geometrically challenging even with optimized linkers.** Both ICM OH exit vectors point away from CRBN (100°–105° angle), meaning the linker must wrap around HMGB2 to reach the E3 ligase. Only impractically long linkers (C14-PEG5, 27 Å) achieve even minimal pass rates (0.8%).

**This does NOT mean HMGB2 is non-degradable.** It means ICM is a poor warhead for PROTAC applications due to its binding site location on HMGB2. Switching to a warhead with a more solvent-exposed exit vector (Hoechst 33258 or PDS) is likely to produce dramatically better results.

**Recommendation:** Before further linker optimization, dock Hoechst 33258 to HMGB2 and assess its exit vector geometry. If favorable, the existing linker library can be efficiently re-screened.

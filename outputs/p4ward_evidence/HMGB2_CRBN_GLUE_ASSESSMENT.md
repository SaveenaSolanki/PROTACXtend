# HMGB2–CRBN Molecular Glue Degradation: Feasibility Assessment

**Date:** 2026-07-06  
**Scope:** Distinguishes PROTAC logic from molecular-glue logic for HMGB2 degradation via CRBN

---

## 1. CRBN-Compatible Degron-Like Motifs on HMGB2

**Known CRBN degron consensus:** β-hairpin with a glycine at the tip (IKZF1: `VDMG`, GSPT1: `GGLGG`, SALL4: `IDMG`)

**HMGB2 scan:**
- HMGB2 is an **α-helical HMG-box protein** — not a zinc finger (IKZF1) or repeat protein (GSPT1)
- No canonical `VDMG`/`IDMG` motif found
- Two glycine-rich regions detected: **GKG** at K2 (N-term) and **GKKG** at K171 (C-tail)
- The C-tail is intrinsically disordered — could adopt a CRBN-compatible conformation
- **Verdict:** No canonical degron found, but CRBN degron specificity is broader than the known motifs. Cannot rule out.

---

## 2. HMGB2 Surface Compatiblity with CRBN

| Property | HMGB2 | CRBN | Compatibility |
|----------|-------|------|---------------|
| Net charge | **+5** (pI 9.5, basic) | Moderately acidic | ✅ Favorable electrostatic steering |
| Interface contacts (closest poses) | 1,500–3,900 atom pairs | | ✅ Substantial contact area |
| Interface residues | Box B (ARG110, ASP124, GLU116, etc.) | | ✅ Involves structured domain |
| C-tail participation | **0 residues** at interface | | ❌ C-tail not involved |

In the closest P4ward poses, the HMGB2–CRBN interface is mediated by **Box B residues** (ARG110, ASP124, GLU108, GLU116, GLU131, GLU135, ALA126, GLY119, HIS117, LEU118, ALA101, ALA148).

---

## 3. ICM Contribution: With-ICM vs Without-ICM

| Metric | Without ICM | With ICM | Δ |
|--------|-------------|----------|---|
| HMGB2–CRBN contacts (avg) | 2,479 | **2,479** | **0** |
| ICM–CRBN direct contacts | — | **0** (0/20 poses) | — |
| Interface enhanced by ICM? | — | **No** | — |

**Full-resolution analysis:** ICM contributes exactly **zero** atom contacts to the HMGB2–CRBN interface in all 20 closest poses. The interface forms between the proteins themselves.

**However:** Static docking cannot capture ICM-induced **conformational changes** in HMGB2. If ICM binding shifts HMGB2 into a CRBN-compatible conformation, this would not appear in our analysis.

---

## 4. Lysine Ubiquitination Compatibility

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| Total lysines | 40 | | |
| Closest lysine (K152) | **16.6 Å** from E2~Ub | < 50 Å | ✅ Excellent |
| Lysines within 60 Å | **40/40** (100%) | | ✅ All accessible |
| Protein size | 24 kDa | < 50 kDa (efficient degradation) | ✅ Small, fast degradation |

**This is the strongest evidence in favor of the hypothesis.** HMGB2's lysine landscape is among the best I've seen for ubiquitination.

---

## 5. Testable Experimental Plan

### Priority 1: Cellular Degradation (3 days)

```
Treatment:  ICM (0.1, 0.5, 1, 5, 10 μM) on CRBN+ cells, 24 h
Controls:   DMSO vehicle, MG132 (10 μM), CRBN siRNA or KO
Readout:    HMGB2 western blot (normalized to GAPDH)
Prediction: If HMGB2 decreases → degradation
            If rescue by MG132 → proteasomal
            If rescue by CRBN KO → CRBN-dependent
```

### Priority 2: Ternary Complex Formation (SPR/BLI, 2 weeks)

```
Setup:  Immobilize CRBN-DDB1 on sensor chip
Flow:   HMGB2 (0.1-10 μM) ± ICM (1 μM)
Readout: KD, kon, koff with and without ICM
Prediction: If α > 1 (tighter binding with ICM) → molecular glue
```

### Priority 3: Ubiquitination (1 week)

```
IP HMGB2 after ICM treatment → blot for ubiquitin
High-MW smear = polyubiquitination
```

---

## Summary

| Criterion | Evidence | Verdict |
|-----------|----------|---------|
| CRBN degron motif | No canonical β-hairpin/G-loop found | ❌ Weak |
| HMGB2–CRBN interface | 1,500–3,900 contacts, Box B mediated | ✅ Moderate |
| ICM at interface | 0 contacts, 0 enhancement | ❌ Not from docking |
| ICM conformational change | Cannot assess from static data | 🔶 Possible |
| Lysine ubiquitination | 40/40 accessible, K152 at 16.6 Å | ✅ Excellent |
| Experimental testability | SPR, degradation, NanoBRET all feasible | ✅ Ready |

**Bottom line:** The HMGB2–CRBN interface geometry and lysine landscape are favorable. ICM's role is unconfirmed from computational data alone. A cellular degradation experiment (ICM → blot for HMGB2 ± MG132 ± CRBN KD) is the fastest path to a definitive answer.

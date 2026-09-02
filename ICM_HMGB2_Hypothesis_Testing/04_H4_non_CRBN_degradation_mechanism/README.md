# H4: ICM-Alone Degradation Is CRBN-Independent

## Hypothesis
If ICM causes HMGB2 loss in cells, the mechanism may not involve CRBN at all. Possibilities include:
1. Disruption of HMGB2–DNA binding → protein destabilization
2. Exposure of a cryptic degron/PEST sequence
3. Recruitment of a different E3 ligase (DCAF1, RNF114, FEM1B, etc.)
4. Autophagy- or lysosome-mediated degradation (LYTAC/AUTOTAC pathway)

## Status: NOT TESTED — Proposed Experiments

This hypothesis is a fallback if H1 (PROTAC) and H3 (CRBN glue) are both ruled out. All experiments below are proposed, not yet executed.

### 1. HMGB2_DNA_ICM_models — DNA-binding disruption
**Proposed experiment:** Model HMGB2 bound to DNA (from crystal structure 2YRQ or similar), then dock ICM. Check whether ICM binding overlaps with the DNA-binding interface.

**What it tells:** Whether ICM could displace HMGB2 from chromatin, leading to protein destabilization.

**Expected output:** Overlap score between ICM binding site and DNA-binding interface. If ICM binds in the DNA-binding cleft → displacement is plausible.

### 2. ubiquitination_site_prediction — Degron/PTM analysis
**Proposed experiment:** Scan HMGB2 sequence for:
- PEST sequences (proteolytic signals)
- Degron motifs (recognized by specific E3s)
- Acetylation sites that could trigger degradation (HMGB2 is known to be acetylated)

**What it tells:** Whether HMGB2 has intrinsic degradation signals that could be unmasked by ICM binding.

**HMGB2 known PTMs:** Acetylation at K7, K8, K30, K43, K82, K87, K90, K114, K146, K147, K152, K154, K170, K172, K173, K177. Methylation at K76 (HMGB2-specific).

### 3. alternative_E3_screen — Other E3 ligases
**Proposed experiment:** Dock HMGB2–ICM against a panel of E3 ligase surfaces (DCAF1, RNF114, FEM1B, β-TrCP, SKP1–CUL1–F-box) using the same P4ward/MegaDock approach.

**What it tells:** Whether a different E3 could explain ICM-mediated HMGB2 degradation if CRBN is ruled out.

**Prioritized E3 list:**
| E3 | Rationale | Subcellular location |
|----|-----------|---------------------|
| DCAF1 | Known glue target (indisulam recruits RBM39 via DCAF1) | Nuclear |
| RNF114 | Known glue target (CDK inhibitors recruit via RNF114) | Cytoplasmic/nuclear |
| FEM1B | Recognizes degrons in disordered proteins | Cytoplasmic |
| β-TrCP | Recognizes phosphorylated degrons | Nuclear/cytoplasmic |

### 4. Pathway-level interpretation
**Proposed experiment:** Based on all experimental results, assign ICM to a degradation pathway.

**Decision tree:**
```
If HMGB2 loss is:
  → Rescued by MG132 → proteasomal degradation
    → Rescued by CRBN KO → CRBN glue
    → NOT rescued by CRBN KO → other E3 (see alternative_E3_screen)
  → NOT rescued by MG132 → non-proteasomal (autophagy? lysosome?)
  → Only seen in specific cell types → cell-type-specific mechanism
```

---

## H4 Verdict: NOT TESTED — Proposed

### What to report (once executed)
| Metric | Expected | Actual (TBD) |
|--------|----------|-------------|
| ICM-DNA-binding overlap | Possibly (unknown) | — |
| PEST/degron motifs in HMGB2 | C-tail has potential | — |
| Alternative E3 interface | Unknown | — |
| MG132 rescue | Yes (if proteasomal) | — |
| CRBN-independent degradation | Possible | — |
| **Final decision** | **PENDING experimental data** | — |

# H3: ICM Itself Works as a CRBN Molecular Glue

## Hypothesis
ICM binding to HMGB2 creates a neo-surface that recruits CRBN, leading to ubiquitination and degradation — without any linker or PROTAC modification. This would be analogous to how thalidomide binds CRBN and creates a surface that recruits neosubstrates.

## Experiments Performed

### 1. ICM_CRBN_docking — Direct ICM-CRBN binding
**Proposed experiment:** Dock ICM directly to CRBN to test whether ICM can bind CRBN independent of HMGB2.

**Status:** Not performed. ICM is known to bind HMGB2 (Lee 2014), not CRBN. No literature evidence for direct ICM-CRBN interaction.

### 2. HMGB2_ICM_CRBN_ternary_docking — Ternary interface analysis
**Experiment:** Using 3600 P4ward MegaDock poses of CRBN around HMGB2, we analyzed whether ICM contributes to the HMGB2–CRBN interface. Full-resolution interface analysis was performed on the 20 closest poses, comparing contacts WITH vs WITHOUT ICM.

**What it tells:** Whether ICM enhances HMGB2–CRBN interface formation.

**Key result:** 
- ICM directly contacts CRBN: **0/20 poses**
- ICM contribution to interface atom count: **0% increase**
- HMGB2–CRBN interface (without ICM): 1,500–3,900 atom contacts
- HMGB2–CRBN interface (with ICM): **identical**

The interface forms between HMGB2 and CRBN proteins themselves. ICM contributes nothing at any sampled orientation.

**However:** Static docking cannot test whether ICM binding *changes HMGB2 conformation* to make it more CRBN-compatible. This would require MD simulation or experiment.

**Files:** `glue_clean_electrostatic.png`, `glue_clean_position.png`

### 3. ternary_MD_refinement — Interface stability
**Proposed experiment:** Run 100+ ns MD of HMGB2–ICM–CRBN ternary complex to test:
- Whether ICM induces conformational changes in HMGB2
- Whether the HMGB2–CRBN interface is stable
- Whether ICM contacts CRBN during the simulation

**Status:** Not performed. MD setup requires force-field parameters for ICM.

### 4. CRBN_competition_analysis — IMiD competition
**Proposed experiment:** Test whether pomalidomide/lenalidomide competes with ICM for CRBN binding. If ICM and IMiDs bind the same CRBN pocket, this would support a CRBN-dependent mechanism.

**Status:** Not performed. Requires CRBN binding assay or competitive docking.

### 5. Lysine geometry analysis
**Experiment:** All 40 HMGB2 lysines are within 60 Å of CRBN E2~Ub active site (K152 at 16.6 Å). HMGB2 surface (pI 9.5, basic) is electrostatically complementary to CRBN (acidic patches). See H1 lysine_accessibility for details.

---

## H3 Verdict: NOT SUPPORTED ❌

**ICM-alone degradation is unlikely to be direct CRBN-glue mediated.**

The evidence against:
1. ICM does not contact CRBN in any of 3600 sampled orientations (verified at full resolution)
2. ICM does not enhance HMGB2–CRBN interface contacts (zero contribution)
3. No canonical CRBN degron motif found on HMGB2
4. ICM binding site is on the far side of HMGB2 from CRBN (100°–105° away)

The remaining open possibility (conformational change) cannot be tested with our current computational tools.

### What to report
| Metric | Value |
|--------|-------|
| ICM-CRBN direct contact | **0/20 poses** — none |
| ICM enhances HMGB2-CRBN interface | **0%** — no enhancement |
| HMGB2-CRBN interface (w/o ICM) | 1,500–3,900 contacts |
| HMGB2-CRBN interface (w/ ICM) | identical |
| Lysine accessibility | ✅ 40/40 within 60 Å |
| Electrostatic complementarity | ✅ HMGB2 basic ↔ CRBN acidic |
| Conformational change mechanism | 🔶 Cannot be ruled out (static docking limitation) |
| **Final decision** | **REJECT — not supported by docking data** |

### What to say to PI
> "Computational docking shows HMGB2 and CRBN have complementary surfaces and can approach each other. However, ICM does NOT participate in this interface — it sits on the far side of HMGB2. ICM is unlikely to act as a CRBN molecular glue. A cellular degradation experiment with CRBN KO control is the fastest way to definitively rule this in or out."

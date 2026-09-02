# STRATEGY: Improve ICM + Degrade HMGB2 — Potential Solutions

**Date:** 2026-07-21
**Motto:** Improve ICM → Degrade HMGB2

---

## The Core Problem (Established by All Our Data)

| Fact | Data | Source |
|------|------|--------|
| ICM binds HMGB2 at residues **78-86** | Vina poses | docking |
| CRBN docks at residues **112-128** | 3600 MegaDock poses | P4ward |
| Angle between sites | **96°** | geometry |
| ICM-PROTAC ternary pass rate | **0.2%** (8/3600) | P4ward |
| A1_4COOH binding (improved ICM) | **−11.22** vs ICM −5.75 | Vina |
| Boltz-1 binding confidence | iPTM **0.70** | Boltz-1 |
| HMGB2 lysine accessibility | **40/40** within 60 Å | H1 |

**Conclusion:** ICM-based PROTAC with CRBN fails because of *binding site location* (96° from CRBN), NOT chemistry. But A1_4COOH is a genuinely improved ICM binder — we just need the right degradation strategy.

---

## SOLUTION S1 (PRIORITY 1): A1_4COOH as Molecular Glue — Test First

**Rationale:** The improved ICM (COOH analog) may recruit an E3 ligase *directly at the 78-86 site* — no linker, no ternary geometry needed.

- ICM site is **basic** (LYS82/85/86, net +2-3) → recruits **acidic E3 surfaces**
- HMGB2 has **40 accessible lysines** → excellent ubiquitination substrate
- Known glues work this way: indisulam→RBM39 (DCAF15), CDKi→RNF114

**Experiment (1-2 weeks, ~$500):**
```
Treat cells with A1_4COOH (0.1, 0.5, 1, 5, 10 μM), 24 h
Readout: HMGB2 Western blot (normalized to GAPDH)
Controls: DMSO | MG132 (10 μM) | CRBN siRNA | DCAF1 siRNA | RNF114 siRNA
If HMGB2 drops → degradation is real
If MG132 rescues → proteasomal
If CRBN siRNA rescues → CRBN-dependent (glue)
If DCAF1/RNF114 siRNA rescues → alternative E3 glue
```

**Success = HMGB2 drops >50% at ≤10 μM.** If this works: **your motto is achieved** — improved ICM alone degrades HMGB2. No PROTAC needed.

---

## SOLUTION S2 (PRIORITY 2): Bivalent Warhead — A1_4COOH + Glycyrrhizin

**Rationale:** If the glue fails, build a molecule that *spans* the two sites:
- **A1_4COOH** binds 78-86 (strong, −11.22)
- **Glycyrrhizin** binds Box B 112-128 (known HMGB2 Box B binder)
- Connect them → the bivalent molecule sits **across the CRBN interface**
- Add a third arm: linker + pomalidomide → CRBN is *forced* to the right place

```
   A1_4COOH──linker──Glycyrrhizin
      |  binds 78-86      |  binds 112-128 (CRBN interface)
      |                   |
      └──linker──Pomalidomide──CRBN
```

**Computational validation first:** Dock the bivalent → run P4ward ternary → target pass rate >5%.

**Cost/time:** ~$3000, 6-8 weeks.

---

## SOLUTION S3 (PRIORITY 3, run in parallel — computational only): Alternative E3 Ligases

**Rationale:** CRBN docks at 112-128. But *another* E3 might dock at 78-86 — making the ICM-PROTAC viable with the *right* E3.

| E3 | Subcellular | Known glue example | ICM site compatibility |
|----|------------|-------------------|------------------------|
| **DCAF1** | Nuclear | Indisulam → RBM39 | ✅ Nuclear + glue-able |
| **DCAF15** | Nuclear | Indisulam class | ✅ Nuclear |
| **RNF114** | Cyto/Nuclear | CDK-inhibitor glues | ✅ Recruits via zinc fingers |
| **β-TrCP** | Nuclear | Phosphodegron | 🔶 Needs phospho-degron |
| **VHL** | Cyto/Nuclear | PROTAC (not glue) | 🔶 Test |
| CRBN | Nuclear | IMiD glues | ❌ Docks 96° away |

**Experiment (computational, 2-3 days):**
1. Get E3 structures (VHL available locally; DCAF1/RNF114 from PDB)
2. MegaDock each E3 around HMGB2 (3600 poses each)
3. Check if any docks within 20 Å of the ICM site (78-86)
4. If yes → ICM-PROTAC with that E3 becomes viable → P4ward screen

**Success = any E3 docks near 78-86.**

---

## SOLUTION S4 (PRIORITY 3): DNA-Binding Disruption (H4 mechanism)

**Rationale:** HMGB2 is a DNA-binding protein. ICM (and stronger A1_4COOH) may:
1. Block HMGB2-DNA binding
2. Free HMGB2 → protein destabilization → degradation

**Experiment (2 weeks, ~$800):**
- EMSA: ICM/A1_4COOH disrupts HMGB2-DNA complex?
- If yes: cellular half-life of free HMGB2 (cycloheximide chase)
- Combined with S1: if A1_4COOH degrades HMGB2 via DNA-disruption, this is CRBN-independent

---

## SOLUTION S5 (FALLBACK): Degron Tag (Guaranteed Degradation)

**Rationale:** If all ICM-based approaches fail, guarantee HMGB2 degradation with an inducible degron:
- **dTAG system** (FKBP12F36V tag) or **Auxin-inducible degron (AID)**
- CRISPR knock-in at HMGB2 locus
- Add degrader → HMGB2 loss >90%

**Cost/time:** ~$5000, 2-3 months. **Abandons ICM** — only use if the goal is HMGB2 degradation above all else.

---

## RECOMMENDED EXECUTION PLAN

```
WEEK 0 (NOW):
  ├── Order A1_4COOH synthesis (4-week lead)      [$1500]
  └── Run S3: alternative E3 MegaDock screen      [computational]

WEEK 4-6:
  ├── S1: A1_4COOH cellular degradation test      [$500]
  │     ├── IF HMGB2 drops → MOLECULAR GLUE = SUCCESS
  │     └── IF not → proceed below
  ├── S4: EMSA (DNA disruption)                   [$800]
  └── S2/S3 decision based on E3 screen results

WEEK 6-8:
  ├── S2: bivalent warhead design + P4ward test   [computational]
  ├── OR S3: ICM-PROTAC with matched E3           [computational]
  └── Cellular validation of the chosen path

FALLBACK: S5 degron-tag (if weeks 6-8 fail)       [$5000]
```

---

## Summary of Likelihood (Honest Assessment)

| Solution | Likelihood of degrading HMGB2 | Why |
|----------|------------------------------|-----|
| S1: A1_4COOH glue | **Moderate-high** | Basic site + 40 lysines + glue precedent |
| S2: Bivalent warhead | **Moderate** | Spans both sites; more complex chemistry |
| S3: Alt E3 + ICM-PROTAC | **Low-moderate** | Need an E3 that docks at 78-86 |
| S4: DNA disruption | **Low-moderate** | Depends on HMGB2 stability when unbound |
| S5: Degron tag | **Very high** (but abandons ICM) | Guaranteed, but not ICM-based |

**Bottom line:** The path that keeps your motto (improve ICM + degrade HMGB2) is:
**S1 (A1_4COOH glue test) first, then S2 (bivalent) or S3 (matched E3).**
All data files and figures are in the project directory.

# Module 3 — Cooperativity (alpha) Predictor

**Entry point:** `predict_cooperativity(protac, poi, e3, ternary_structure=None,
ternary_ensemble=None, smiles=None, poi_chain=None, e3_chain=None, ...)`

## alpha definition (exact)
`alpha = Kd2 / Kd2(ternary)` — the factor by which the SECOND binary interaction
(E3–PROTAC) strengthens when the first arm (POI–PROTAC) is bound (Gadd/Ciulli
two-site formalism, consistent with Module 1). Model target `log_alpha =
ln(alpha)` (natural log, single convention). Classes:
`alpha > 1` positive cooperativity; `0.8 ≤ alpha ≤ 1.25` approximately
non-cooperative; `alpha < 0.8` negative cooperativity (thresholds documented).
alpha is only entered into the dataset from measured binary+ternary Kd in the
SAME assay system — never inferred from qualitative statements, and incompatible
assay conventions are never silently mixed.

## Current state (honest)
The shipped curation template (`data/cooperativity_records.csv`) holds **zero
records**: no reliable machine-readable experimental-alpha dataset is
programmatically available (measured values live in article SI tables). Per
spec step 6, supervised training is therefore **not claimed**; the benchmark
harness (constant → ridge → RF → XGBoost → GP) is implemented and gated on
curated data with grouped (unseen-series) folds. Until data exist, the module
operates in **structural-surrogate mode** and returns `predicted_alpha=None`
rather than a fabricated number.

## Structural surrogate ("cooperativity feasibility score" — clearly NOT alpha)
Interface features from ternary pose(s) (reuses the Module 2 structural toolkit:
PDB parsing + numeric Shrake–Rupley SASA): buried surface area (ΔSASA),
contacts, H-bonds (distance proxy), salt bridges, hydrophobic contacts,
clashes, interface residues, ensemble BSA/interface stability.
Deterministic score in [0,1]:
`0.30·BSA + 0.20·contacts + 0.15·Hbond + 0.10·salt + 0.05·hydrophobic +
0.10·(1−clash) + 0.10·ensemble` (per-component normalisations in
`surrogate.SCALES`). Label: **"Cooperativity feasibility score"** — never
reported as experimental alpha.

## Return
`CooperativityPrediction`: `predicted_alpha` (None in surrogate mode),
`predicted_log_alpha`, `cooperativity_class`, `confidence`/`uncertainty`,
`feature_evidence` (interface + molecular + components + formula),
`structure_available`, `model_applicability` (OOD note), `limitations`,
`model_kind` (`structural_surrogate` | `trained_model`), version metadata.

Evidence policy: no structure AND no trained model ⇒ `CooperativityEvidenceError`
(explicit failure — nothing is fabricated). Structures without
`poi_chain`/`e3_chain` ⇒ explicit error (unambiguous chain assignment required).

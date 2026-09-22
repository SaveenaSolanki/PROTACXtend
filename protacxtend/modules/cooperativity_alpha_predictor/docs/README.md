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
The shipped curation (`data/cooperativity_records.csv`) now holds **46 real
measured records** (12 POIs, 3 E3s) curated from the DOI-cited PROTAC-DB-derived
`protac.csv` (binary POI, binary E3 and ternary affinity columns + assay text).
Twenty records have an unambiguous E3-arm assay description. A small ridge model
on that subset was evaluated with grouped (unseen-POI / unseen-PROTAC) folds and
**does not beat the mean baseline**; the calibration report therefore records
`status = PRIOR_ONLY` and `model_usable = false`. `predicted_alpha` is returned
only through the evidence-ordered lookup
`measured_pair → e3_prior → global_prior`, with sample-size-scaled confidence and
an explicit `uncertainty.evidence_level`. Unsupported E3s still raise
`CooperativityEvidenceError` (nothing is fabricated). The structural surrogate
remains available and is clearly labelled *not* alpha.

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

## Experimental calibration (`calibration.py`)
* `fit_calibration()` reports alpha distribution/coverage (overall, per E3, per
  arm, per affinity basis) and fits/evaluates the ridge model; writes
  `data/calibration_report.json`.
* `empirical_alpha(poi, e3)` returns the highest available evidence tier:
  measured pair, E3 prior, global prior (model only if it beat the gate).
* `predict_cooperativity(..., use_empirical_calibration=True)` consumes this and
  returns `model_kind = empirical_cooperativity_v1` with the evidence tier and
  n in the uncertainty block. Coverage is limited to the curated systems; see
  `RESULTS_INTERPRETATION.md` at the repository `outputs/gap_completion/`.
`CooperativityPrediction`: `predicted_alpha` (None in surrogate mode),
`predicted_log_alpha`, `cooperativity_class`, `confidence`/`uncertainty`,
`feature_evidence` (interface + molecular + components + formula),
`structure_available`, `model_applicability` (OOD note), `limitations`,
`model_kind` (`structural_surrogate` | `trained_model`), version metadata.

Evidence policy: no structure AND no trained model ⇒ `CooperativityEvidenceError`
(explicit failure — nothing is fabricated). Structures without
`poi_chain`/`e3_chain` ⇒ explicit error (unambiguous chain assignment required).

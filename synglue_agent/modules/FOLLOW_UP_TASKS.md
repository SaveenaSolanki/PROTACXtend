# Tracked follow-up tasks (do not block the module build)

1. **Module 2 benchmark (tracked)**: benchmark `score_lysine_ubiquitination`
   against real ternary/E2 structural examples once suitable reference
   structures are identified (e.g., published ternary complexes with validated
   ubiquitination sites). Status: pending dataset identification; non-blocking.
2. **Module 3 data curation (OPEN tracked task)**: populate
   data/cooperativity_records.csv from primary-literature SI tables (binary+ternary
   Kd in the same assay), then run the grouped benchmark (unseen-PROTAC / linker /
   POI / E3 / leave-one-series) before any learned alpha predictor may be claimed.
   Status: OPEN — does not block later modules; the surrogate remains clearly
   labelled as heuristic/untrained until this is done.
3. **Module 5 → M4-v2 retrain (tracked, gated on Module-5 report audit)**: per
   docs/M4_FOLLOWUP.md — train a separately-versioned context-INDEPENDENT pDC50
   model (`degradation_ml` v2) on the Module-5 curated dataset (leg B or
   per-compound aggregated), then publish M4-v1 vs M5-context vs M4-v2 on a
   common held-out set. M4-v1 artifact stays frozen. Status: pending audit.
4. **Module 5 proteomics leg (tracked)**: when a DepMap/CCLE quantitative
   proteomics matrix is available (not in 24Q4), curate per-cell-line protein
   features and re-run leg E; proteotype-awareness may only be claimed then.
5. **Module 5 unseen-cell-line transfer (tracked)**: transcriptomic context did
   not yet robustly beat PROTAC-only on unseen cell lines (RF/XGB negative
   deltas, ET/ridge positive). Candidate fixes: batch-corrected expression,
   per-line assay-matched labels, larger panel; revisit before any
   "generalises to new cell lines" claim.
6. **Module 5 mechanistic leg (tracked)**: structure-paired series curation
   (ternary PDB + measured Kds) is required before Modules 1–3 features can be
   evaluated at scale (currently only 22 rows reference a structure).
7. **Module 6 real-time UniProt/PDB refresh (tracked, optional)**: the
   localization + structural tables are static caches (78 genes; curated
   complex facts for CRBN/VHL only). A refresh utility + broader curation
   would extend POI/E3 coverage; no structural claims are made without it.
8. **Module 6 prospective validation (tracked)**: verdict thresholds were
   calibrated on retrospective retrieval of known usage (absence-of-record
   negatives). A prospective set (newly reported POI-E3 degraders vs
   predictions) is the definitive test of SUPPORTED/PROMISING calibration.

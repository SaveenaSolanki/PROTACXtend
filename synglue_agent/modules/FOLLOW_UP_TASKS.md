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

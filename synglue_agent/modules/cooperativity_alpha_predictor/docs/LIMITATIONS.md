# Limitations — Cooperativity alpha predictor

1. No trained alpha predictor exists yet: curated experimental dataset is empty
   (values live in article SI tables). `predicted_alpha` is None by design.
2. Structural surrogate is an interpretable heuristic of interface quality —
   high interface quality does NOT guarantee positive alpha (measured
   cooperativity may still be neutral/negative); it is a feasibility score only.
3. H-bonds are heavy-atom distance proxies (no explicit H/angles); interface
   BSA is static (single pose or pose ensemble without dynamics); no MM/GBSA
   free-energy integration is performed.
4. alpha definitional consistency: only records from a single assay convention
   are acceptable; mixed ITC/SPR conventions are not merged silently.
5. Ensemble features assume comparable poses (same chains/numbering).
6. GP/uncertainty calibration is implemented for the future trained model and
   is meaningless without curated data.

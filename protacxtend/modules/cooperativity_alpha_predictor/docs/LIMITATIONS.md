# Limitations — Cooperativity alpha predictor

1. Experimental coverage is limited to 46 curated ternary records across 3 E3s
   (VHL/CRBN/cIAP1) and 12 POIs. A trained alpha model does not beat the mean
   baseline under grouped CV, so cooperativity is served as measured-pair /
   E3-prior / global-prior lookups, NOT as a general prediction. For any POI–E3
   pair outside the curated data, no experimental calibration is claimed.
2. Structural surrogate is an interpretable heuristic of interface quality —
   high interface quality does NOT guarantee positive alpha (measured
   cooperativity may still be neutral/negative); it is a feasibility score only.
3. H-bonds are heavy-atom distance proxies (no explicit H/angles); interface
   BSA is static (single pose or pose ensemble without dynamics); no MM/GBSA
   free-energy integration is performed.
4. alpha definitional consistency: only records from a single assay convention
   are acceptable; mixed ITC/SPR conventions are not merged silently.
5. Ensemble features assume comparable poses (same chains/numbering).
6. Uncertainty for the empirical tier is a sample-size-scaled confidence plus the
   observed alpha distribution (not a Gaussian posterior); for the structural
   surrogate, the feasibility score is heuristic. GP/uncertainty calibration for
   a future trained model is meaningless while the model gate is closed.

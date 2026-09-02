# Limitations — PROTAC Degradation ML

1. Small curated set (64 pDC50, 32 Dmax) → grouped test metrics are unstable;
   negative R2 on some folds is honest and expected at this size.
2. E3 vocabulary is CRBN/VHL only; ordinal entity codes carry no chemistry.
3. Features are full-PROTAC 2D/ECFP — component (warhead/linker/E3-ligand)
   decomposition and ternary/cooperativity/lysine features (Modules 1-3) are not
   yet fused; that fusion is the next data step, not skipped silently.
4. degradation probability and (optionally) Dmax are disabled for lack of
   measured labels — never synthesized.
5. Interval is conformal-style on training residuals, not a calibrated posterior.
6. OOD is a descriptor-distance heuristic, not a rigorous applicability domain.
7. No multitask neural model: data do not justify one yet (baselines first).

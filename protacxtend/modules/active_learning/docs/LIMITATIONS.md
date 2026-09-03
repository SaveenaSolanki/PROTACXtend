# LIMITATIONS

1. No experimental feedback loop yet → validated on deterministic synthetic
   objectives + component tests; `public_claim: false`.
2. Surrogate is a RandomForest on two design features (linker index, dose);
   richer molecular descriptors require an M4/M5 scorer adapter (registered by
   the caller) and were deliberately not auto-wired to avoid silent claims.
3. Dose objective (`dose_objective_from_hook`) requires kinetics (Kd_T, Kd_E,
   alpha, concentrations) from experiment/upstream; absent those, the module
   reports the objective as unavailable rather than inventing values.
4. Stereochemistry enters as a budget/cap (orthogonal design), not full
   enumeration, which is intentional (search cost) but means stereo-sensitive
   effects are not searched exhaustively.
5. Linker generative space is guarded; heavy model loads only on explicit use.

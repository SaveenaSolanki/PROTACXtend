# Limitations — Module 6 (E3 opportunity engine)

1. **Expression** is transcriptomic only (DepMap 24Q4 TPM-log1p). Protein
   levels can differ (degradation rates, IMiD-induced CRBN loss, VHL
   regulation) — the engine never treats RNA percentiles as protein
   abundance and always recommends an expression/protein confirmation test
   when context is decisive.
2. **Recruiter evidence** covers only the DOI-cited in-repo library (~19 E3
   ligand classes; 107 rows). Absence from the library = absence of *our*
   record, not proof no recruiter exists (reported as None + limitation).
   Ligand affinity/stereochemistry/exit-vector fields are carried as reported;
   synthetic accessibility is not scored.
3. **Precedent** comes from one degradation database (2,141-source rows
   curated to 1,913; 270 unique benchmark pairs). It is measured-PROTAC usage,
   not a guarantee of efficacy, and its absence for a POI does not imply an
   E3 is unusable. Family-precedent only counts curated families.
4. **Structural/lysine axes are deliberately UNKNOWN at dataset scale.** Only
   curated complex facts for CRBN/VHL exist; no POI structures are bundled.
   `structural_feasibility` is None for every pair without ternary data, and
   lysine census requires a user-supplied POI structure. Interface/ternary
   claims require resolved or docked ternary complexes (Module 2/3 infra
   available for structure-paired series).
5. **Retrospective benchmark** positives are "E3 actually used for POI in the
   dataset" — absence-of-record negatives are NOT known-inactive. AUROC/MRR
   therefore measure *retrieval of known usage*, not prospective activity.
   Unseen-E3/family regimes are the honest generalization tests and show the
   expected drop (RF AUROC .98 → .93; AP .94 → .69).
6. **Cell-line mapping** limits context to DepMap-represented lines (Module 5
   coverage: 137/180 names; unmapped lines get no expression axis). Tissue
   queries aggregate real lineage lines; unknown tissues yield None.
7. **Localization** is UniProt-compartment annotation (reviewed human), not
   measured colocalization; membrane/cytosol reachability is permissive by
   design. Selectivity "restriction" is lineage-expression specificity, and
   off-target degradation risk is not predicted (no curated basis).
8. **Verdict thresholds** are documented heuristics calibrated on this
   benchmark, not externally validated operating points.
9. **XGBoost** is unstable below chance on leave-one-E3/family regimes in this
   small dataset — reported; RandomForest is the chosen model for claims.

## Integrity invariants (tested)
No candidate is ever SUPPORTED/PROMISING from expression alone; low-expression
E3s are capped at EXPLORATORY; missing context produces uncertainty flags not
scores; absent recruiters and unknown structure are explicit; unknown POIs
fail gracefully.

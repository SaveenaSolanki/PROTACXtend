# Limitations — Hook Effect Modeler

1. **Equilibrium only, no kinetics.** The model describes steady-state ternary
   abundance, not time-dependent degradation flux or target resynthesis
   dynamics; DC50/Dmax predictions need Module 4 (degradation ML), not this
   module.
2. **Parameters must come from experiment/upstream estimators.** Kds, α and
   concentrations are inputs; the module never infers or fabricates them.
3. **Simplified ternary topology.** Direct POI–E3 affinity and multi-step
   assembly beyond the TL→TLE pathway are not modelled; α is treated as a
   symmetric enhancement (detailed-balance-consistent single-parameter form).
4. **Occupancy ≠ degradation.** Ternary occupancy is a proxy for activity;
   functional outcomes depend on E2/ubiquitination machinery (Modules 2/5).
5. **Two-component, single-cell assumption.** Subcellular compartmentation and
   non-equilibrium trafficking are ignored; concentrations are total/global.
6. **Monte-Carlo assumes lognormal input uncertainty** with user-supplied σ;
   no calibration against experimental ternary data is bundled (data live in
   Module 3/5 datasets).
7. Hook severity is an *operational* window measure (see `severity_reference_max_dose_nM`): at the tested max dose the curve is usually not fully asymptotic, so severity underestimates the theoretical infinite-dose drop; E3-limiting↔severity ordering holds only for the tested Kd/window regime and must not be treated as a universal invariant.
8. Cmax (nM PROTAC at peak) and ternary_max (nM ternary AT Cmax) are distinct outputs with different units — compare each only with its own MC interval.
9. Numeric solve is bounded least-squares; extreme (>1000-fold) Kd/concentration
   ratios still converge but residual checks are reported for auditability.

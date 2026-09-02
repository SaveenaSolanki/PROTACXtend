# Claims — Module 6 (Novel E3 Ligase Opportunity Engine) v1.0.0

Claim register maintained under the sequential-audit rule. Every claim below
must be backed by the evidence linked in parentheses; anything not listed here
must NOT be stated as supported. This register is reviewed at each module
audit gate.

## SUPPORTED

1. **Ranks catalogued E3s using multiple evidence axes.**
   `rank_e3_ligases()` evaluates every gene in the 30-gene catalog across
   independent axes (cell-context expression, localization, recruiter
   tractability, biological precedent, structural availability, lysine
   opportunity, selectivity) and returns tiered verdicts
   (docs/README.md, rank.py, SPEC.md §3).

2. **Retrieves known/tractable E3 choices.**
   Retrospective grouped benchmark: retrieving the E3 actually used for a POI
   reaches AUROC 0.98 (random / unseen-target), 0.99 (unseen-cell), and
   recruiter-capable E3s surface as PROMISING without over-claiming
   (docs/VALIDATION.md — RF results; artifacts/benchmark_results.json).

3. **Penalizes low-expression context.**
   E3 expression is scored as a DepMap percentile; an E3 below the 20th
   percentile is capped at EXPLORATORY regardless of other evidence
   (rank.py `LOW_EXPRESSION_CAP`; test `test_low_expression_caps_verdict`).

4. **Expresses uncertainty for missing evidence.**
   Missing cell context, absent recruiters, unknown structure and unresolved
   POIs produce explicit None/UNKNOWN values and OOD flags — never fabricated
   scores (uncertainty.py, predict.py; tests 4, 5, 6, 7).

## NOT YET SUPPORTED

1. **Prospective novel-E3 discovery.** The benchmark measures retrieval of
   known usage with absence-of-record negatives; it has not been validated
   prospectively (docs/LIMITATIONS.md §5; follow-up task 8).
2. **Reliable unseen-E3 generalization.** Unseen-E3 / leave-one-family-out
   AUROC drops to 0.93 / 0.93 (AP 0.69) vs 0.98 easy regimes, and the
   −recruiter ablation removes 0.52 AUROC — generalizing to a never-seen E3
   is not yet dependable (docs/VALIDATION.md).
3. **Structural ternary feasibility without actual structures.**
   `structural_feasibility` is None for every pair unless resolved/docked
   ternary data exist; monomer availability never implies an interface
   (structure.py; test `test_structure_unknown_when_unsupported`).
4. **Ubiquitination prediction without supplied structural models.**
   The lysine axis requires a user-supplied POI structure (Module-2 SASA);
   CRL/E2 accessibility needs a ternary/E2 geometry and is not claimed
   (lysines.py).
5. **Causal superiority of one E3 over another.** Ranking reflects evidence
   retrieval, not proof that one E3 will outperform another in a degradation
   assay (docs/LIMITATIONS.md §5; follow-up task 8).

---
Maintained by the sequential module audit. Changes to this register require a
test + evidence update in the same commit.

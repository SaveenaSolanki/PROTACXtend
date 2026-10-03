# Questions this audit is asking

The user asked "what questions are you asking". These are them, grouped by who
must answer. Each is tied to a finding (`F-xx`) and a decision it unblocks.

## A. To the repository maintainer (blocking "closed")

1. **(F-14 — ✅ CLOSED 2026-09-23)** `protacxtend-memory/` was the intended
   replacement for `protacpilot-memory/`. It is committed as a rename
   (`82a0e4d`): all 104 tracked files byte-identical, 234 new files preserved on
   disk, generated outputs re-ignored. Provenance:
   `gateC/F14_memory_provenance.json`.
2. **(F-15)** Which install is canonical for reviewers — the source tree
   (`python -m protacxtend.cli`) or the installed console script? The installed
   one still imports `synglue_agent.cli` and crashes.
3. **(F-16)** What is the project's real test command and expected count?
   `pytest.ini` currently walks vendored third-party repos (1357 tests,
   156 collection errors).
4. **(F-10)** Where do `pre_registration.md`, `splits.json`, and
   `gold_review.tsv` live? `todo/_02` requires them and both `docs/` and
   `benchmark/` lack them.

## B. To the scientific lead (blocking credibility)

5. **(F-01/F-02)** What is "the executed pilot": the deterministic engine, the
   LLM `run_protacpilot` path, or the acceptance runner?
   - deterministic KNOW-01 → **0.0**
   - LLM acceptance KNOW-01 → correct `O60885`
   These must not be blended into one number.
6. **(F-03)** Which path is the scientific control plane? `strategy` ignores
   execution mode (demo output == scientific output); only the agent-tool
   wrapper enforces it. Where should the guard actually live?
7. **(F-04)** Is BRD4→`M0QZD9` acceptable? If not, should target resolution
   prefer `reviewed:true` UniProt entries / the packaged
   `curated_targets.csv` before the live API?
8. **(F-05)** Are the 42 auto-derived scoring overlays allowed to be graded
   against the answer they were derived from? If not, what replaces them?
9. **(F-06)** Who are the two independent annotators for the 29
   expert-review tasks, and where is the adjudication record?
10. **(F-09)** Which baselines define the headline comparison: the n=4
    acceptance run, a 48-task matched-tool pilot, or new Biomni / TPD /
    retrieval-only / tool-only adapters?
11. **(F-12)** Do you want three separate critics (evidence / mechanism /
    reproducibility) or is the single `CriticVerifier` the accepted design?
12. **(F-13)** Should `EvidenceItem` carry external source identifiers
    (DOI/PMID/UniProt + timestamp) rather than internal field labels?

## C. To the benchmark owner

13. **(F-07)** What is the frozen E1 denominator — 296 registry rows, 123
    tools, or 34 agent tools — and who signs off the eligible set?
14. **(F-11)** Is E7 temporal validation in scope for this release? No
    cutoff/as-of/leakage code exists today.
15. **(F-01)** What are the per-task wall-time and cost budgets for a full
    48-task run given that KNOW-01 alone took 239 s deterministically?

## D. Open doubts the audit could not resolve (need network / experts / data)

16. Does the live `rest.uniprot.org` query return `M0QZD9` deterministically,
    or is there a cached/local override? (reproduced once, no cache found).
17. Are the 4 acceptance answers representative of the 48 (they are one task
    per capability), and were they blinded identically? `execution_log.csv`
    points at a different checkout root (`/storage/saveena/protacpilot/...`).
18. Does `run_protacpilot` in SCIENTIFIC mode ever reach the same demo warhead
    panel as the deterministic engine, or only the deterministic engine does?
19. Are the `TACK` model sklearn-version warnings (F, diagnostics) cosmetic or
    do they change DC50/Dmax values quoted in the strategy?

## E. Self-questions about this audit (limits)

20. Were any of the 42 derived overlays hand-edited after derivation? (Not
    verified — would require a git-blame over `benchmark/scoring/`.)
21. Are the 29 "requires_expert_review" tasks the correct 29? (Accepted from
    `SCORABLE_MANIFEST.json`; not independently re-derived.)
22. Did the full pytest suite pass? (Not run to completion — it exceeds the
    session budget; only the focused selections were run. You must run the
    full suite yourself with `testpaths` fixed.)

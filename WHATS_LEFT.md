# WHATS_LEFT — ranked by blocking biological claim

Date 2026-09-24 · HEAD `82a0e4d`. Ranked by the biological claim each item
blocks, **not** by convenience. Every item links to its acceptance test and the
E1–E8 result. A tool/data source that cannot be verified stays grey/unknown; no
connectivity is fabricated.

| rank | blocking claim | why it blocks | acceptance test | current E-result |
|---|---|---|---|---|
| **1** | **Independent gold adjudication (0/48)** — `benchmark/gold_review.tsv` is all `PENDING_ADJUDICATION` | No answer can be called *correct* until two independent reviewers + adjudicator score the 48 cases. Blocks E2 (task correctness), E4 (reasoning), E5 (mechanism), E6 (ablation correctness). | 2 annotators + adjudicator → `reviewed_gold/consensus.json`; `case_level.csv` flips from `pending_independent_gold`. | E2/E4/E5/E6 execution done, **scored N = 0** |
| **2** | **Source-backed, atom-mapped warhead + exit vector; chemist review** | DESIGN currently uses hypothetical `[*:1]`/`[*:2]` attachment markers; 4/4 DESIGN candidates are `attachment_hypothesis = true`. Any "designed degrader" claim is unsupported, and BRD4–VHL is a legitimate no-go. | Curated source-backed warhead/exit vector + independent chemist review; atom-mapped structure artifact. | E5: 214 source-backed records but **0 validated exit vectors**; DESIGN 8/9 valid execution |
| **3** | **Measured degradation labels (0/233 assay-specific DC50)** | Without measured DC50/Dmax no degradation ranking, calibration or MAE can be claimed; ternary proxies are not ubiquitination. | Assay-context labels + scaffold/target split; calibrated selective performance. | E5 ranking/MAE **not measured**; E8 computational panel only |
| **4** | **Frozen pre-cutoff corpus + database release snapshots (E7)** | The system cannot be claimed to prioritise post-cutoff findings without a frozen as-of index and time-pinned weights. Blocks temporal validity (E7) and any leakage-free retrospective claim. | `E7_TEMPORAL_PROTOCOL.md`: t0 definition, archive list, leakage audit, time-correct baselines. | E7 **not evaluated** (0 frozen corpora) |
| **5** | **Wet-lab validation of recommended programs (E8)** | No dose–response, proteasome/E3 dependence, selectivity or controls exist, so no therapeutic outcome can be claimed. | Locked target programs + assays (DC50/Dmax ± controls). | E8 **not experimentally validated** (0 programs) |
| **6** | **Fault-injection harness with paired policy runs (E3 scientific endpoint)** | The repaired agent closes engineering gaps, but the *value of orchestration* conditional on a recoverable fault is unmeasured. Also exposes the single-critic gap (F-12). | Frozen fault schedule (source timeout, malformed response, missing warhead/E3, invalid structure, contradictory sources) + paired adaptive/fixed runs. | E3 engineering achieved (27/45 gaps closed; 18 typed abstain), scientific **not measured** |
| **7** | **Routable DepMap / Open Targets / HPA adapters + calibrated no-go rubric** | Target validation and E3 context are currently catalog/ML outputs, not dependency evidence. Any "tractable target" claim is unsupported. | Operative adapter + reproducible response; blinded no-go rubric. | E4 packet assembled (108 links), **scored N = 0** |
| **8** | **Curated 500-question packages** | The two 500-item workbooks are uncurated templates (no frozen sources, no gold, no cutoff). They must not be presented as a 1,000-case cohort. | Gold + source packages per question; frozen splits. | not a cohort |
| **9** | **Externally benchmarked adapter subset** | Fig B shows **0 adapters externally benchmarked**; only separate scientific capabilities have external benchmarks. Adapter-level claims need an external endpoint. | Benchmark each adapter on a documented external task with CI. | E1 execution readiness **measured**; external validity **not measured** |
| **10** | **Three named critics + provenance-to-source lineage** | One `CriticVerifier` (F-12) and internal-label `evidence_refs` (F-13) mean mechanism/chemistry/evidence critiques are not independently enforced. | Separate evidence/chemistry/mechanism critics with recorded rejections; source-resolved `evidence_refs`. | CORE engineering **partial** |

## The three largest unresolved gaps (one line each)

1. **Gold** — 0/48 independently adjudicated, so no accuracy or biological claim is possible.
2. **Chemistry truth** — 0 source-backed atom-mapped exit vectors, so all designs stay hypothetical and BRD4–VHL is a no-go.
3. **Temporal/wet-lab closure** — 0 frozen as-of corpora and 0 experimental programs, so E7/E8 claims are unproven.

## What is genuinely done (engineering only)

34/34 adapters installed and executed on a real input · 33/34 domain-valid
offline (32/34 online) · 31/34 typed negative refusals · 34/34 fixture-clean ·
27/27 permitted ids mapped · repaired held-out completion 0/32 → 25/32 with
0 timeouts. These are execution facts, **not** scientific results.

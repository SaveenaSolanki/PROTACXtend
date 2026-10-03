# 03 — Experimental Design (pre-execution, Phase 0 output)

**Study id:** `PROTACXTEND-STUDY/1.0.0`
**Status:** DESIGN — awaiting approval. **No full execution has been started.**
**Grounded on:** `00_REPOSITORY_FREEZE.md`, `01_SYSTEM_AUDIT.md`, `02_BENCHMARK_AUDIT.md`.
**Reuses (does not duplicate):** `tpdeval/` (systems, statistics, failure, ablation,
reproducibility, provenance), `benchmark_runner/` (runner, adapters, grader,
scoring, freeze), `runtime/fault_injection.py`.

> Every experiment below is tagged with the hypothesis (H1–H6) it testes. No
> experiment exists that does not map to a hypothesis.

---

## 1. Experimental hypotheses (H1–H6)

Holding the base LLM **constant**, and with the question/case as the experimental
unit:

| ID | Hypothesis | Primary contrast | Falsified if |
|---|---|---|---|
| **H1** Scaffold | ProtacXtend > LLM-only on macro scientific success | S3 vs S0 | Δ ≤ 0 or CI includes 0 |
| **H2** Orchestration | Full ProtacXtend > flat LLM + same tools | S3 vs S2 | S3 ≈ S2 |
| **H3** Evidence | ProtacXtend ↑ correct-AND-supported claims, ↓ unsupported claims and false citations | S3 vs S0/S2 | support precision not ↑ |
| **H4** Reliability | Under injected faults, ProtacXtend detects→recovers/falls back/abstains instead of hallucinating continuation | S3 vs S0/S2 on fault episodes | hallucinated-continuation rate not ↓ |
| **H5** End-to-end | Isolated-QA gains translate to better multi-stage target→degrader workflows | S3 vs S0/S2 on e2e cases | valid completion not ↑ |
| **H6** Reproducibility | Independent replicates converge on evidence, candidates, ordering, conclusions | within-system across replicates | agreement ≈ chance |

**Pre-declared interpretation rules (from Part XV) are frozen in §6.4 and may not
be changed after results are seen.**

---

## 2. Exact benchmark inventory (measured)

### 2.1 Populations used by the study

| Pop | id | n | Source | Gold | Role |
|---|---|---|---|---|---|
| Task-level core | `POP-A` | **300** | 24 governed KNOW/REASON + 276 stratified from `benchmark500/general_500` | curated per §5 | H1–H3, H6 |
| End-to-end | `POP-B` | **48** | 24 governed DESIGN/DISCOVER + 24 constructed target-level cases | curated per §5 | H5 |
| Temporal | `POP-C` | **50** | stratified from `benchmark500/temporal_500` | curated + pre-cutoff corpus | H6, leakage |
| Abstention set | `POP-D` | **60** | authored unanswerable / insufficient-input | expected answer = ABSTAIN | H4, Sec-E4 |
| Fault episodes | `POP-E` | 15 faults × 20 tasks = **300** | `POP-A` tasks + injectors | n/a (behavioural) | H4 |
| Cross-model | `POP-F` | **150** ⊂ POP-A | stratified | curated | H1/H2 transfer |
| Ablation | `POP-G` | **150** ⊂ POP-A | stratified, fixed | curated | causal |

### 2.2 Distribution of POP-A (target; enforced by stratified sampling)

| Stratum | Domains (from `benchmark500` 16-domain taxonomy) | Tasks |
|---|---|---|
| Biology & validation | Target biology, Target validation | 60 |
| TPD tractability | TPD tractability, E3 ligase selection | 50 |
| Chemistry | Warhead discovery, Linker/PROTAC design | 60 |
| Structure | Binary structural modeling, Ternary-complex reasoning | 50 |
| Prediction | Degradation prediction, ADME/PK | 40 |
| Translation | Polypharmacology/safety, Resistance, Biomarker, Combination, Translational, Failure analysis | 40 |
| **Total** | | **300** |

Difficulty mix target (L1–L7 → easy/medium/hard): easy ≈ 25, medium ≈ 140, hard ≈ 135.
Reasoning-depth: number of required stages 1–12. Tool-dependency:
none / one / multi. Retrieval-dependency: none / light / heavy. Structure-dependency:
none / homolog / exact-PDB.

**This taxonomy is the exact Part-III schema** (fields listed in §8.1).

### 2.3 POP-B stage decomposition (G0–G12)

| Stage | Name | Scored by |
|---|---|---|
| G0 | Target resolution | identity/normalised match to UniProt |
| G1 | Biological/degradation rationale | rubric |
| G2 | Binder/warhead identification | DB ID + canonical SMILES |
| G3 | E3 ligase selection | categorical + rationale |
| G4 | E3 ligand selection | canonical SMILES |
| G5 | Exit-vector / linker reasoning | deterministic constraints + rubric |
| G6 | Candidate construction | RDKit-parseable, components preserved |
| G7 | Structural/ternary reasoning | rubric + optional docking |
| G8 | Degradation plausibility | rubric |
| G9 | ADME/property filtering | numeric tolerance |
| G10 | Synthetic feasibility | rubric (backend BLOCKED → reasoning only) |
| G11 | Candidate prioritisation | ranking metrics |
| G12 | Experimental recommendation | rubric |

Outcome codes per stage: `PASS | PARTIAL | FAIL | UNSUPPORTED | NOT_REACHED | APPROPRIATE_ABSTENTION`.

### 2.4 Benchmark provenance caveat (must travel with every result)

Per `02_BENCHMARK_AUDIT.md`, **0/48 governed cases are independently adjudicated**
and **0/1000 benchmark500 tasks are gold-curated**. The design therefore makes gold
curation a hard Phase-0 gate (§11). Until it clears, only H4/H6 behavioural
endpoints and tool metrics are computable; H1–H3/H5 correctness endpoints are not.

---

## 3. Experimental matrix (systems × questions × replicates × models)

### 3.1 Systems

| ID | System | Composition | Code entry point | Gap to close |
|---|---|---|---|---|
| **S0** | LLM-only | base model, question only; no prompt architecture, RAG, tools, agents, graph, memory | `benchmark_runner/live.py::_call_base_llm` / `baselines.LLMBaseline` | none |
| **S1** | LLM + retrieval | S0 + controlled scientific literature/DB retrieval injected as context | `baselines.RetrievalOnlyBaseline` + LLM synthesis | **build thin `LLM-RAG` adapter** (retrieval currently tool-only) |
| **S2** | LLM + flat tools | S1 + exactly the same tool schemas available to S3; **no** workflow graph, specialist decomposition, persistent state, evidence gating | `adapters.tool_only_adapter`/`closed48_worker --arm direct_tool` | **build LLM-with-tools loop** (current tool-only arm is scripted, not LLM-driven) |
| **S3** | Full ProtacXtend | planner + specialist agents + TPD workflow + retrieval + tools + backends + state + evidence + failure handling + ranking + synthesis | `agents.runtime.run_protacpilot`, `closed48_worker --arm protacxtend` | none |

**Fairness manifest is mandatory** (`tpdeval/systems.py::FairnessManifest`): model,
context window, web access, tool access, DB access, retry budget, compute,
time allowance, token budget, temperature, seed recorded per system. Any axis on
which S0–S3 differ is declared; equality is never assumed.

### 3.2 Replication

| Population | Replicates | Rationale |
|---|---|---|
| POP-A task-level | **3** | minimum for variance + agreement |
| POP-B e2e | **5** | high cost of a wrong conclusion |
| POP-C temporal | **3** | |
| POP-D abstention | **3** | |
| POP-E fault episodes | **3** | |
| POP-F cross-model | **3** | |
| POP-G ablation | **3** | |

Fixed across all runs: model version, temperature=0, top_p=1.0, max_tokens=24000,
prompt version, tool-registry version, retrieval-corpus version, explicit seed where
supported. **Memory mode = `reset`** for all primary runs (independence); `frozen`
only in the state-persistence ablation.

### 3.3 Run-count matrix

| Experiment | Systems | Questions | Reps | Runs |
|---|---|---|---|---|
| Phase 1 pilot | 4 | 30 | 3 | **360** |
| Phase 2 primary (POP-A) | 4 | 300 | 3 | **3,600** |
| Phase 3 e2e (POP-B) | 4 | 48 | 5 | **960** |
| Phase 3 temporal (POP-C) | 4 | 50 | 3 | **600** |
| Phase 4 abstention (POP-D) | 4 | 60 | 3 | **720** |
| Phase 4 fault injection (POP-E) | 4 | 300 episodes | 3 | **3,600** |
| Phase 5 ablation (POP-G) | 10 ablations + Full | 150 | 3 | **4,500** |
| Phase 6 cross-model (POP-F) | 3 models | 150 | 3 × 2 conditions | **2,700** |
| **Total planned runs** | | | | **≈ 17,040** |

Plus judge calls (blinded grading) ≈ 0.35 × sum of non-deterministic answers ≈ 5k.
Reproducibility (Phase 7) reuses the replicate structure — no extra runs.

---

## 4. Exact metrics (mathematical definitions)

Notation: question/case index `q = 1..Q`; system `s`; replicate `r = 1..R`;
task family `f`; `1[·]` indicator.

### 4.1 PRIMARY — Scientific Task Success (binary)
```
success(q,s,r) = 1  iff the scientific conclusion is materially correct (gold)
MacroSS(s) = (1/|F|) Σ_f  (1/(|Q_f|·R)) Σ_{q∈Q_f} Σ_r success(q,s,r)
```
Task families weighted equally (macro). Micro average reported as robustness (§22).

### 4.2 SECONDARY 1 — Evidence-grounded success
```
egs(q,s,r) = success(q,s,r) × 1[all material claims supported]
EgsRate(s) = macro-average of egs(·)
```

### 4.3 SECONDARY 2 — Partial scientific score (rubric)
```
partial ∈ {0.00, 0.25, 0.50, 0.75, 1.00}
PartialScore(s) = macro-average of partial(·)
```

### 4.4 SECONDARY 3 — Evidence quality (claim level)
For material claims `C`:
```
support_precision = |{c: supported}| / |{c: carries evidence}|
unsupported_rate  = |{c: unsupported}| / |C|
contradicted_rate = |{c: contradicted}| / |C|
unverifiable_rate = |{c: unverifiable}| / |C|
false_citation_rate = |{c: cited ref does not contain claim}| / |{c: has citation}|
```

### 4.5 SECONDARY 4 — Abstention quality
```
AppropriateAbstentionRate = |{q∈POP-D : abstained}| / |POP-D|
FalseAbstentionRate       = |{q∈POP-D^answerable : abstained}| / |POP-D^answerable|
FalseAnswerRate           = |{q∈POP-D : answered}| / |POP-D|
```

### 4.6 SECONDARY 5 — Tool performance
```
selection_precision = TP_tools / (TP_tools + FP_tools)      # vs task ToolSpec.required/optional/irrelevant
selection_recall    = TP_tools / (TP_tools + FN_tools)
execution_success   = succeeded_calls / executed_calls
useful_result_rate  = used_results / succeeded_calls        # "used" = result referenced downstream
redundant_rate      = duplicate_calls / all_calls
incorrect_tool_rate = irrelevant_calls / all_calls
```
Implemented via `tpdeval/toolenv.py` (required/optional/irrelevant per task).

### 4.7 End-to-end (POP-B)
```
StageSuccess(g,s) = macro share of PASS at stage g
CaseScore(c,s,r)  = Σ_g w_g · score_g   (PASS=1, PARTIAL=.5, FAIL/UNSUPPORTED=0)
Completion(s)     = P(reaches G12)
ValidCompletion(s)= P(reaches G12 ∧ no critical upstream error)
FirstFailure(s)   = argmin_g {score_g < PASS}
ErrorPropagation  = P(downstream incorrect | upstream FAIL)
RecoveryRate      = P(downstream correct after detected upstream FAIL)
CriticalErrorRate = P(final degrader invalidated by ≥1 critical error)
```

### 4.8 Failure injection (POP-E)
```
DetectionRate = detected / episodes
RecoveryRate  = recovered / detected
FallbackRate  = fallback_used / episodes
AbstentionRate= appropriately_abstained / episodes
HallucinationRate = hallucinated_continuation / episodes   ← SAFETY ENDPOINT
```

### 4.9 Reproducibility
```
FinalAnswerAgreement = P(replicates agree on principal conclusion)
EvidenceOverlap      = mean pairwise Jaccard(evidence sets)
CandidateOverlap     = mean pairwise Jaccard(top-k candidates)
RankingRepro         = mean pairwise Spearman ρ, Kendall τ
StagePathConsistency = mean pairwise Jaccard(ordered tool/node sequence)
CV(metric)           = SD / mean across replicates
```

### 4.10 Calibration (only if confidence is emitted)
```
ECE = Σ_bins (n_b/N) · |acc(b) − conf(b)| ;  Brier = mean((p − y)^2)
```

---

## 5. Grading specification

### 5.1 Grading ladder (deterministic first)
1. **Exact match** (normalised case, whitespace/punctuation).
2. **Synonym dictionary** (`acceptable_alternatives` in GT; gene/alias table).
3. **Numeric tolerance** (relative 1 % unless GT specifies otherwise).
4. **Molecular identity** — canonical SMILES via RDKit (`MolFromSmiles` +
   `MolToSmiles`), InChIKey on success.
5. **Database identifiers** — UniProt/PDB/ChEMBL/PubChem normalised.
6. **Ranking metrics** — NDCG@k, Kendall τ, top-k precision/recall vs reference.
7. **Rubric checklist** — deterministic criteria from `benchmark/gateC/rubrics/`
   (`mandatory_answer_elements`, `prohibited_claims`).
8. **LLM judge (blinded)** — ONLY for free-text reasoning not reducible to (1)–(7).
9. **Human expert (blinded)** — adjudication of disagreements; stratified sample.

### 5.2 Blinding & rater agreement
- Judge/experts see **randomised** outputs with system/model/condition stripped.
- Two independent human raters on a stratified sample (≈10 % of rubric cases).
- Inter-rater agreement: **Cohen's κ** (and Krippendorff α if >2 raters).
- LLM-judge provenance recorded (provider/model/prompt version/seed).

### 5.3 Normative rule
A correct conclusion with unsupported justification is `success=1` but
`evidence-grounded success=0`. A fabricated claim forces `partial=0`.

---

## 6. Statistical analysis plan (test by test)

### 6.1 Unit of analysis
**The question/case is the experimental unit.** Replicates are averaged (or
modelled) within unit; they are never treated as independent samples. For binary
endpoints use "majority across replicates" as the unit value; for partial use the
mean; both are pre-registered.

### 6.2 Primary comparison (S3 vs S0)
```
Δ = MacroSS(S3) − MacroSS(S0)
CI = paired bootstrap 95% (resample QUESTIONS with replacement, B = 10,000)
binary: McNemar exact test (paired discordant counts)
partial: two-sided Wilcoxon signed-rank
```
Report **effect size + 95% CI + n** always; never p without effect size.

### 6.3 Multiple comparisons
- Task-family tests: **Benjamini–Hochberg** across families.
- Ablations: **Holm–Bonferroni** across ablations.
- Cross-model: per-model Δ with CI, no between-model ranking claim.

### 6.4 Sensitivity model
```
success ~ system + difficulty + task_family + tool_dependency + reasoning_depth
          + (1 | question)
```
Mixed-effects logistic regression (`tpdeval/stats.py::mixed_effects`); if it fails
to converge, fall back to GEE / cluster-robust logistic and record the fallback.

### 6.5 Pre-declared interpretation rules (frozen)
| Pattern | Interpretation |
|---|---|
| S3 > S0 but S3 ≈ S2 | Tools help; orchestration evidence weak |
| S3 > S2 > S1 > S0 | Additive value of retrieval, tools, orchestration |
| QA ↑ but e2e flat | Isolated-task gain does not transfer |
| e2e ↑ but runtime/cost ↑↑ | Report benefit–cost trade-off, not superiority |
| Correctness ↑ but unsupported ↑ | Reliability unresolved |
| Correctness ↑ AND hallucinated continuation ↓ | Strong utility + safety evidence |

### 6.6 Robustness (Part XXII)
Recompute headline under: binary vs partial, macro vs micro, majority vs mean
replicate. If the conclusion changes materially, report the instability.

---

## 7. Figure plan

### 7.1 Main Figure 1 (panels A–H)
| Panel | Question | Plot | Data |
|---|---|---|---|
| **A** | Does ProtacXtend improve performance? | point + 95 % bootstrap CI for S0–S3; family dots; Δ annotation | `task_level_results` |
| **B** | Is the scaffold useful across LLMs? | paired dumbbell/forest per model (LLM-only → +ProtacXtend) | `cross_model_results` |
| **C** | Where does it help? | heatmap rows=families, cols=S0–S3, + thin Δ annotation; TPD workflow order preserved (no clustering) | `task_level_results` |
| **D** | Can it finish a workflow? | case × G0–G12 stage matrix (7 outcome colours) + right cols score/valid/runtime/tools/first-failure | `case_level_results` |
| **E** | Does it fail safely? | fault types × {Detected, Recovered, Fallback, Abstained, Hallucinated} with CIs | `failure_results` |
| **F** | How does it operate? | architecture diagram drawn from **observed traces** (node/tool frequencies), annotate memory/state/retry/failure return | `raw_runs` + `trace.jsonl` |
| **G** | Which components matter? | ablation forest plot, Δ vs Full, 95 % CI, zero line | `ablation_results` |
| **H** | Benefit/cost trade-off | scatter runtime/cost vs MacroSS, bubble=tool calls, Pareto frontier | `statistics` |

### 7.2 Supplementary figure set
| Panel | Content |
|---|---|
| S1 | performance by easy/medium/hard |
| S2 | success vs required stages (reasoning depth) |
| S3 | no-tool / one-tool / multi-tool |
| S4 | reliability diagram + ECE + Brier (if confidence) |
| S5 | first-failure stage distribution |
| S6 | error-propagation (only if alluvial aids) |
| S7 | replicate Spearman/Kendall distributions |
| S8 | claim support mix (supported/partial/unsupported/contradicted) |
| S9 | tool selection confusion matrix |
| S10 | tool funnel selected→executed→succeeded→used→changed-decision |
| S11 | cost distribution per successful task |
| S12 | performance on common vs rare targets |

### 7.3 Plotting standards (Part XVIII)
matplotlib; white background; DejaVu Sans; no 3-D; remove top/right spines;
consistent typography; uncertainty always shown; no rainbow palettes
(restrained, high-contrast); individual panels ~square; figure readable at
journal column width. Save **PNG 600 dpi + PDF + SVG**. Every axis labelled with
unit, **n**, uncertainty definition, benchmark population. Never a mean bar
without uncertainty. Figures generated only from frozen Parquet tables.

---

## 8. Expected output schemas (column names)

Directory: `study/results/`. All Parquet (Snappy), plus CSV mirrors.

### 8.1 `task_level_results.parquet`
```
question_id, case_id, task_family, subtask, difficulty, reasoning_depth,
tool_dependency, retrieval_dependency, structure_dependency, ground_truth_type,
required_evidence, expected_abstention, leakage_tag, split,
system, model, replicate, seed, memory_mode, route_used,
answer_status, abstained, success, evidence_grounded_success, partial_score,
unsupported_claim_rate, contradicted_claim_rate, false_citation_rate,
tool_selection_precision, tool_selection_recall, tool_execution_success,
useful_tool_result_rate, redundant_tool_call_rate, incorrect_tool_rate,
runtime_s, input_tokens, output_tokens, tool_calls, cost_usd,
confidence, error_class
```

### 8.2 `case_level_results.parquet`
```
case_id, system, model, replicate, seed,
g0_target, g1_rationale, g2_binder, g3_e3, g4_e3_ligand, g5_linker,
g6_construction, g7_ternary, g8_degradation, g9_adme, g10_synthesis,
g11_ranking, g12_recommendation,
case_score, completion, valid_completion, first_failure_stage,
critical_error, error_propagation, recovery,
runtime_s, tool_calls, cost_usd, n_candidates, smiles_valid_rate
```

### 8.3 `tool_level_results.parquet`
```
question_id, system, replicate, step_index, tool_name, tool_kind,
was_expected, was_permitted, call_ordinal, executed, execution_status,
valid_output, redundant, result_used_downstream, changed_decision,
latency_s, error_class, failure_code
```

### 8.4 `claim_level_results.parquet`
```
question_id, system, replicate, claim_id, claim_text, claim_type,
has_citation, citation_ref, evidence_match, support_label,
(supported|partially_supported|unsupported|contradicted|unverifiable),
material, extracted_by, judged_by
```

### 8.5 `failure_results.parquet`
```
episode_id, question_id, system, replicate, fault_type, fault_target,
detected, recovered, fallback_used, abstained, hallucinated_continuation,
detection_method, recovery_action, runtime_s, error_class, notes
```

### 8.6 `ablation_results.parquet`
```
ablation, removed_component, question_id, system, model, replicate,
success, evidence_grounded_success, e2e_success, unsupported_claim_rate,
hallucinated_continuation, runtime_s, tool_calls, cost_usd,
full_success, delta_success
```

### 8.7 `statistics.parquet`
```
comparison, metric, unit_n, effect_estimate, ci_low, ci_high, test,
statistic, p_value, p_adjusted, correction, cohens_d, alpha, significant
```

### 8.8 `raw_runs.parquet`
```
run_id, question_id, case_id, system, model, condition, replicate, seed,
start_utc, end_utc, runtime_s, status, route, nodes_executed,
tools_called, tokens_in, tokens_out, cost_usd, memory_mode, tree_hash,
repo_commit, freeze_id, answer_hash, evidence_ids, candidate_ids,
error_class, raw_path
```

### 8.9 Supporting tables
- `cross_model_results.parquet`: `model_family, condition, question_id, replicate, success, partial, sufficiency, delta_vs_llm_only`
- `reproducibility_results.parquet`: `system, question_id, final_answer_agreement, evidence_jaccard, candidate_jaccard, spearman, kendall, stage_path_jaccard, metric_mean, metric_sd, metric_cv`
- `calibration_results.parquet`: `system, question_id, confidence, correct, bin, ece_contrib, brier_contrib`
- `grading_audit.parquet`: `item_id, grader, blinded, rater_a, rater_b, kappa, adjudicated`
- `leakage_audit.parquet`: `question_id, source, tag(clean|possible|confirmed), evidence`

---

## 9. Estimated compute / time / cost

Assumptions (measured rate basis): deepseek-v4-flash $0.14/1M in, $0.28/1M out.
Per-call token estimates: S0 ~3k/1k; S1 ~5k/2k; S2 ~8k/3k; S3 ~20k/6k across ~6
LLM calls. Scientific backends (docking/MD) are GPU wall-clock, not API cost.

| Experiment | Runs | Dominant cost | Est. API USD | Est. GPU-h | Est. wall (2 GPU) |
|---|---|---|---|---|---|
| Pilot | 360 | API + debug | ≈ 2 | 20 | ~0.5 day |
| Primary POP-A | 3,600 | API (S3 heaviest) | ≈ 25 | 300 | ~2 days |
| E2E POP-B | 960 | GPU (ternary/dock/MD) | ≈ 15 | 500 | ~5 days |
| Temporal POP-C | 600 | API + retrieval | ≈ 6 | 60 | ~1 day |
| Abstention POP-D | 720 | API | ≈ 4 | 20 | ~0.5 day |
| Fault POP-E | 3,600 | API (cheap injectors) | ≈ 15 | 80 | ~1.5 days |
| Ablation POP-G | 4,500 | mixed (many deterministic) | ≈ 20 | 400 | ~4 days |
| Cross-model POP-F | 2,700 | API (≥3 providers) | ≈ 30 | 150 | ~2 days |
| Grading (LLM judge) | ~5,000 | API | ≈ 30 | 0 | ~1 day |
| **Total** | **≈ 17,040** | | **≈ $147** | **≈ 1,530 GPU-h** | **≈ 17–20 days** |

**Sensitivity:** S3 e2e runtime dominates GPU. If median e2e case > 20 min,
reduce e2e replicates to 3 (saves ~200 GPU-h) — must be decided **before** Phase 3.
API cost is negligible relative to GPU/engineering time; therefore **do not
optimise for API cost** — optimise for valid completion and safety.

⚠ **Disk:** 165 GiB free. Raw e2e artifacts must be pruned to scored stages;
Parquet + compressed logs only. Budget ≤ 60 GiB.

---

## 10. Experimental risks

| # | Risk | Evidence from Phase 0 | Mitigation |
|---|---|---|---|
| R1 | **Gold is unadjudicated** (0/48; 0/1000) | `02_BENCHMARK_AUDIT.md` §1.6, §2.3 | Phase-0 gate: adjudicate 48 + curate POP-A/B/C before scoring; report behavioural endpoints meanwhile |
| R2 | **Data leakage** | first-pass clean, not exhaustive | per-case leakage tag; primary on clean subset; hold out `blind` split |
| R3 | **Replicate dependence via memory** | persistent `memory/run_state` active | force `memory_mode=reset`; record per run |
| R4 | **S1/S2 not truly implemented** | `benchmark_runner` lacks LLM+tools and LLM+RAG loops | build thin adapters in Phase 1; validate on pilot; otherwise H2 is uninterpretable |
| R5 | **Judge bias** | LLM judge planned | blind, randomise, 2 human raters on 10 %, report κ; prefer deterministic graders |
| R6 | **Class imbalance** | DESIGN/DISCOVER are rubric-heavy; exact only 5 | macro averaging; report per-family |
| R7 | **Stochasticity** | temperature fixed 0 but provider may be non-deterministic | 3–5 replicates; seed where supported; report CV |
| R8 | **Backend instability** | 11/27 capabilities BLOCKED; docking/MD external | fail-closed; record backend_used; never silent SURROGATE |
| R9 | **Provider drift / version change** | single provider; model may update | pin model string; re-run smoke; record API snapshot date |
| R10 | **Disk exhaustion** | 99 % full, 165 GiB free | prune raw artifacts; Parquet; monitor |
| R11 | **Cross-model infeasibility** | only deepseek provisioned | provision ≥3 families or downgrade H-scaffold arm to 1 model (report limitation) |
| R12 | **Capability-route mismatch** | parser/dispatcher dual paths | log `route_used`; stratify analysis by route |
| R13 | **Constructed e2e validity** | 24 e2e cases must be authored | independent review before Phase 3 |
| R14 | **p-hacking** | — | pre-register endpoints; freeze analysis script hash before Phase 2 |

---

## 11. Go / no-go criteria

**GO for Phase 1 pilot** requires ALL of:
1. `study/freeze_manifest.json` written (repo commit + tree hash + versions). ✅ can do now.
2. `00/01/02` audits accepted.
3. Scoring plumbing passes `--offline-smoke` (GT graded against itself) with 100 % expected pass on the 19 objective cases.
4. Fault injector runs end-to-end on ≥1 task and emits the 5 behavioural flags.
5. Cost/latency/token logging captured for ≥1 real S3 run.
6. Claim-extractor produces ≥1 claim/answer without crashing on 20 answers.

**GO for Phase 2 (primary)** requires:
7. POP-A gold curated & double-adjudicated (κ ≥ 0.7 on a 30-case sample); else primary endpoint = behavioural only (documented downgrade).
8. S1/S2 adapters built and proven to use the *same* model/tools (fairness manifest complete).
9. Replicate stability smoke: 10 questions × 3 reps, answer-agreement reported.
10. Leakage audit complete; clean subset ≥ 90 % of POP-A.
11. Analysis script + Parquet schemas frozen (hash recorded).

**NO-GO triggers (stop and report):**
- any confirmed leakage in > 10 % of POP-A;
- S2 adapter cannot be made tool-matched to S3 (H2 not answerable);
- provider unavailable / model changed without re-smoke;
- disk < 40 GiB free.

---

## 12. Exact first commands (PILOT ONLY)

Run from `/storage/saveena/protacxtend`. **Do not run the full benchmark.**
Steps 1–4 are inspection/plumbing; step 5 is the 30-question pilot.

```bash
# 0. Activate environment
source /home/saveenas/miniconda3/etc/profile.d/conda.sh && conda activate base

# 1. Re-verify the evaluation instrument tests (read-only, ~minutes)
python -m pytest tests/test_tpdeval.py -q

# 2. Regenerate the 500-task DESIGN manifest (no invention of gold)
python -m tpdeval.allocation
python -c "from tpdeval import validate_taxonomy; print(validate_taxonomy())"

# 3. Validate the deterministic grading engine on authored GT (no system run)
python scripts/run_benchmark_pilot.py --offline-smoke

# 4. Re-run the Gate-C 4-case pipeline-integrity pilot (typed outcomes, no score)
PROTACXTEND_EXECUTION_MODE=scientific \
  python scripts/gateC_pilot.py --out-dir benchmark_results/gateC_pilot --run-id study_pilot_00

# 5. FIRST REAL PILOT — 30 stratified questions, S3 arm, 3 replicates
#    (repeat the closed48_worker per (case, arm) is orchestrated by run_closed_48;
#     for the pilot use the agentic benchmark sweep, which is the closest
#     implemented multi-system harness)
python scripts/agentic_benchmark.py --n 30

# 6. Baseline arms on the same pilot tasks (retrieval-only, tool-only, base-LLM)
python scripts/run_baseline_comparison.py --limit 8 --tasks KNOW-01,REASON-03,DESIGN-01,DISCOVER-01

# 7. Fault-injection smoke (writes behavioural CSV; no correctness)
python scripts/run_fault_injection.py

# 8. Cost/latency smoke on one real S3 run (credentials already present)
python scripts/run_benchmark_pilot.py --limit 1 --capability KNOW --engine agentic
```

**Pilot deliverables (before any Phase 2 approval):**
`study/results/pilot/` containing run logs, cost/latency table, scoring smoke
report, fault CSV, claim-extraction sanity output, and a one-page
`PILOT_REVIEW.md` reporting: scoring validity, log completeness, runtime, cost,
failure capture, and the go/no-go checklist of §11.

---

## Appendix A — Experiment → hypothesis traceability

| Experiment | H1 | H2 | H3 | H4 | H5 | H6 |
|---|---|---|---|---|---|---|
| Primary POP-A (S0–S3) | ✅ | ✅ | ✅ | | | ✅ |
| E2E POP-B | | ✅ | ✅ | | ✅ | ✅ |
| Temporal POP-C | ✅ | | ✅ | | | ✅ |
| Abstention POP-D | | | | ✅ | | |
| Fault POP-E | | | | ✅ | | |
| Ablation POP-G | ✅ | ✅ | ✅ | ✅ | ✅ | |
| Cross-model POP-F | ✅ | ✅ | | | | |
| Reproducibility | | | | | | ✅ |

## Appendix B — Falsification checklist (Part XXIV, evaluated explicitly)

1. S3 ≤ S2 → orchestration value not shown.
2. Gains vanish on hard strata → H1/H5 fragile.
3. Gains vanish on unseen targets → no generalisation.
4. Valid e2e completion low → workflow claim fails.
5. Orchestration ↑ hallucinated continuation → safety regression.
6. Ablating the workflow changes nothing → architecture inert.
7. High replicate variance → stochastic luck.
8. Gains track leakage → invalid.

Each will be reported as a first-class result, not hidden.

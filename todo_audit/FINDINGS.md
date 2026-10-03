# PROTACXtend `todo/` audit — consolidated findings

> **Remediation update 2026-09-23 (Gates A, B & C of `todo/_05`):** F-03, F-04,
> F-15 and F-16 are now **fixed and regression-tested**; **F-14 is fixed** — the
> `protacxtend-memory` rename is committed as a rename (`82a0e4d`), all 104
> tracked files byte-identical, no memory data deleted
> (`gateC/F14_memory_provenance.json`). **F-10 is now addressed** and
> **F-05/F-06 are drafted but remain `PENDING` human adjudication**: Gate C has
> inventoried the 48 cases and 2×500 template, drafted evidence packages and
> rubrics, enumerated the 29 reviewer decisions, and frozen splits/provenance
> (`benchmark/gateC/`). The 48-task run / gold / baselines remain blocked and
> were deliberately **not** executed or scored. No benchmark score is reported.

Date: 2026-09-23 · HEAD `0abbe83` (`sprint-2`) · full evidence under `evidence/`

Severity: **S1** blocks a defensible benchmark/publication claim · **S2** material
discrepancy with the todo reports · **S3** hygiene / reproducibility.

---

## S1 — blocks the benchmark/publication claim

### F-01 · Full 48-task executed pilot does not exist
- **Claim** (`TODO.md` P0, `todo/_03` P0): "Select the matching KNOW/REASON/DESIGN/DISCOVER tools, then execute the full 48-task SCIENTIFIC-mode pilot".
- **Observed:** the only non-smoke pilot artifact is
  `benchmark_results/pilots/pilot_deterministic_20260922T104813Z.json` with
  `n_tasks: 1`, `task_id: KNOW-01`, `latency_s: 238.86`, `mean_score: 0.0`.
  All other pilot files are `engine: offline-smoke`.
- **Status:** `partial` — one real task ran; 47 did not. **Scope-lock update
  (closed48_locked):** all 48 cases now executed under three arms with locked
  budgets (144 predictions). Gold-independent outcomes only.
- **Evidence cmd:** `grep -rl '"engine": "deterministic"' benchmark_results`;
  `benchmark_results/closed48/closed48_locked/`.
- **Question:** Is the intended executed pilot PROTACXtend-deterministic, the
  LLM `run_protacpilot` path, or the acceptance runner? They give different
  answers (see F-04/F-10). → adopted: deterministic canonical path is the
  PROTACXtend arm; `direct_tool` and `fixed_workflow` are baselines.

### F-02 · The executed task scored 0.0 on a routing/correctness failure
- **Observed** (`pilot_deterministic_...json`): KNOW-01
  ("Which UniProt ID and bromodomain architecture correspond to BRD4?") was
  answered by the **design engine**, not a KNOW resolver; the grader reports
  `missing: ["O60885", "BD1/BD2 architecture"]`, `score: 0.0`.
- **Status:** `failed` as a *self-graded* number; **scope-lock update:** the
  old 0.0 used the self-derived overlay and is withdrawn. In `closed48_locked`
  the same question was answered by `direct_tool` (`resolve_target` → O60885);
  correctness is `PENDING_INDEPENDENT_GOLD` and no score is reported.
- **Question:** Why does `run_protacpilot` route a KNOW question into the
  deterministic design pipeline instead of the retrieval/LLM KNOW path? — still
  open; the deterministic engine timed out on KNOW-01 within the 120 s budget.

### F-03 · SCIENTIFIC mode is not enforced on the canonical strategy path
- **Claim** (`TODO.md` P0; `todo/_02` step 2): "SCIENTIFIC refuses fixture defaults along every direct, agent and API path".
- **Observed:** `python -m protacxtend.cli --execution-mode scientific strategy "Design a VHL PROTAC against BRD4"` and the same command with
  `--execution-mode demo` produce **identical** output signatures:
  same `uniprot_id`, same `local_demo_*` warhead sources, same 25 candidates,
  same top SMILES.
  - warhead sources: `local_demo_brd4_binder`, `local_demo_bromodomain_warhead`, `local_demo_jq1_like_warhead`
  - E3 ligands: `VHL_demo_vh032_like`, `VHL_demo_hydroxyproline_like`
- **Contrast (works):** `protacxtend/runtime/agent_tools.py` *does* enforce it —
  `run_agent_tool("inspect_smiles", {"smiles":"CCO"})` raises
  `SyntheticInputNotAllowed`; `{}` raises `MissingScientificInput`;
  `use_fixture=True` raises `FixtureUsageError`.
- **Status:** `failed` (canonical path), `verified` (agent-tool path).
- **✅ RESOLVED (Gate B):** demo seeds in the curated tables are now mode-gated;
  canonical modules and the decision engine drop any leaked demo warhead;
  `execution_mode` is recorded on every strategy + manifest; the CLI no longer
  substitutes a hidden default request in SCIENTIFIC mode; the API returns
  typed 422. Regression: `tests/test_gate_b_scientific_integrity.py` (11 tests).
  Before/after traces in `gateB/`.
- **Evidence:** `outputs/strategies/strategy_1ef85a525b.*` (scientific) vs
  `strategy_167cc2f93b.*` (demo); probe transcript in `evidence/mode_probe.txt`.
- **Question:** Which single code path is the "scientific control plane"? The
  guard lives in the agent-tool wrapper, but the product entry point
  (`strategy`) bypasses it.

### F-04 · BRD4 is mis-resolved to a UniProt fragment
- **Observed:** the scientific strategy reports
  `target_validation.uniprot_id = "M0QZD9"` (a BRD4 fragment) and
  `protein_name = "M0QZD9_HUMAN"`, while the curated table
  `protacxtend/data/curated_targets.csv` contains the correct
  `BRD4,BRD4,O60885,...,AF-O60885-F1,120 binders,0.86`.
  `protacxtend/agents/target_agent.py` queries
  `rest.uniprot.org/uniprotkb/search?query=BRD4&size=1` **without
  `reviewed:true`**, so it takes the first (unreviewed/fragment) hit.
- **Consequence:** KNOW-01 scores 0.0 (F-02).
- **Localisation:** the shared agent tool gets it **right** —
  `run_agent_tool("resolve_target", {"target_name":"BRD4"})` returns
  `O60885` (plus zebrafish F1R5H6, mouse Q9ESU6). Only the canonical
  deterministic engine path is wrong. Fix belongs in
  `protacxtend/agents/target_agent.py` (add `reviewed:true`, or prefer
  `curated_targets.csv`).
- **Status:** `failed` (canonical engine), `verified` (agent tool).
- **✅ RESOLVED (Gate B):** `TargetResolverAgent` now prefers the packaged
  curated table, then the reviewed-UniProt client, then a reviewed-filtered
  raw search; BRD4 → `O60885` (human, `2OSS/3MXF/5T35`, 120 binders, 0.86).
  Regression asserts `!= M0QZD9` and `uniprot_tier == curated`.
- **Evidence cmd:** `grep BRD4 protacxtend/data/curated_targets.csv`;
  agent-tool contrast captured in `evidence/registry_summary.txt`.

### F-05 · The 48/48 "mean 0.885" is circular self-grading
- **Observed:** `scripts/run_benchmark_pilot.py --offline-smoke` grades each
  task's **own authored ground-truth answer** against criteria derived from that
  same ground truth. `scripts/derive_scoring_criteria.py` reports
  `48 overlays (42 derived from expected_answer)`. `benchmark/scoring/*.json`
  has `derived: true` for 42/48.
- **Meaning:** 0.885 measures grader/criterion consistency, not system accuracy.
- **Status:** `draft_pending_independent_review` — Gate C drafted independent
  rubrics under `benchmark/gateC/rubrics/` without reading the self-derived
  overlays; the old overlays are retained only as an infrastructure smoke value.
  No score may be quoted until the 29 reviewer decisions are signed.
- **Question:** Should derived overlays be replaced by adjudicated criteria
  before any score is quoted? **Answer adopted: yes** (`gateC/rubrics/`).

### F-06 · No gold adjudication for the 29 expert-review tasks
- **Observed:** `SCORABLE_MANIFEST.json` → `n_requires_expert_review: 29`
  (all DESIGN-01..12, DISCOVER-02/03/05/06/07/09/10/12, REASON-01/02/04/06/08/09/10/11/12).
  No `gold_review.tsv`, adjudication log, or reviewer identity exists anywhere
  under `benchmark/`.
- **Status:** `pending` — the 29 decisions are enumerated with exact questions,
  options and blocked endpoints in `gateC/REVIEWER_DECISIONS.tsv`;
  `gateC/gold_review.tsv` has one row per task, all `PENDING_ADJUDICATION`.
  No reviewer identity exists yet and the agent decided none of them.
- **Question:** Who are the two independent annotators, and where is the
  disagreement/adjudication record? → open reviewer assignment recorded in
  `gateC/REVIEWER_DECISIONS.tsv`; adjudication record is `gateC/gold_review.tsv`.

---

## S2 — material discrepancies with the todo reports

### F-07 · Registry declares 296 entries, declares 0 executable
- **Observed:** `load_toolkit_registry()` →
  `modalities 18 · tools 123 · databases 49 · packages 43 · skills 26 · agent_modules 37`
  = **296 rows**. `get_tool_status()` and `summarize_toolkit_status()` hard-code
  `available: False, executable: False` and totals
  `{"registered": 296, "available": 0, "executable": 0}`.
- **Meaning:** everything is L0 "registered"; the audit's L1/L2 funnel is empty.
- **Status:** `partial` — declarative registry verified, executable status absent.
- **Question:** What is the frozen E1 denominator (296 rows? 123 tools? 34 agent tools?)

### F-08 · 34 agent tools exist and are gated — this part is real
- **Observed:** `list_agent_tools()` → 34 tools, each `readiness: ready`,
  `has_executor: True`, `has_fixture: True`, exposed on
  `tui/api/web/agent` surfaces. Scientific-mode negative cases raise the typed
  `FailureCode`s. `protacxtend/tests/test_agent_tool_exposure.py` +
  `tests/test_execution_modes.py` + `tests/test_p0b_fixture_elimination.py`
  pass.
- **Status:** `verified` (agent-tool surface only).

### F-09 · Baselines exist only at n=4 and were never scored
- **Observed:** `benchmark_results/acceptance/execution_log.csv` has
  PROTACXtend × Base-LLM-control × Biomni on exactly 4 tasks
  (KNOW-01, REASON-03, DESIGN-01, DISCOVER-01). PROTACXtend DISCOVER-01 =
  `failed` ("clarification_required"). `benchmark_results/scored/` is **empty**.
  No `tpd_comparator`, `retrieval_only`, `llm_baseline` adapter exists in code
  (only prose in `benchmark/BASELINES.md`).
- **Status:** `partial`. **Scope-lock update (closed48_locked):** two
  tool-level baselines now run over all 48 cases — `direct_tool` (one matched
  tool) and `fixed_workflow` (fixed chain) — alongside the deterministic
  PROTACXtend arm. Still no external-agent baselines (Biomni/TPD/LLM) because
  none is available/licensed; accuracy remains `PENDING_INDEPENDENT_GOLD`.
- **Question:** Is the publication baseline the 4-task acceptance run, the
  48-task matched-tool pilot, or a yet-to-be-built adapter set? → adopted: the
  48-case `direct_tool` + `fixed_workflow` pair for this closure.

### F-10 · Required minimum artifact tree is absent
- **Observed missing:** `docs/tool_registry_snapshot.json`,
  `docs/universal_reconciliation.md`, `benchmarks/gold_review.tsv`,
  `benchmarks/splits.json`, `benchmarks/pre_registration.md`
  (repo uses `benchmark/`; the manifest/pre-registration/splits files are absent
  from either location).
- **Status:** `addressed (draft, frozen hashes)` — Gate C created
  `benchmark/pre_registration.md`, `benchmark/splits.json`,
  `benchmark/gold_review.tsv`, `docs/tool_registry_snapshot.json` and the full
  `benchmark/gateC/` package with a SHA-256 provenance manifest. Gold is still
  0/48 adjudicated, so the files are structurally present but **pending**.

### F-11 · No temporal / leakage / cutoff infrastructure
- **Observed:** no `cutoff`, `as_of`, `as-of`, `temporal`, or `leakage`
  implementation under `protacxtend/memory/` or `protacxtend/learning/`
  (`grep -rln` empty). E7 in `todo/_01` requires as-of replay.
- **Status:** `absent`.

### F-12 · One critic, not the three named critics
- **Observed:** `protacxtend/canonical/critic.py` has a single
  `CriticVerifier` (166 lines) running 7 checks
  (`module_present`, `measured_vs_predicted`, `structural_claim_gate`,
  `applicability_domain`, `provenance_complete`, contract + legacy critique).
  It **does** warn "predicted degradation is not experimental evidence".
  No separate `EvidenceCritic`, `MechanismCritic`, `ReproducibilityCritic`.
- **Status:** `partial`.

### F-13 · Provenance is structurally present but not source-level
- **Observed:** strategy `evidence_refs` are internal field labels
  (`target_disease:uniprot_id`, `degradation:top_dc50`, …), not external
  sources. No DOI/PMID/accession-with-timestamp on any `EvidenceItem`.
  `RunManifest.runtime_s = 181.738` but `finished_at - started_at = 0.023 s`
  and every `module_runtimes` value is `0.0` — runtime accounting is inconsistent.
- **Status:** `partial`.

---

## S3 — hygiene / reproducibility

### F-14 · Working tree is not clean; a tracked module was renamed uncommitted
- **Observed:** `git status --short` → **104 `D`** (`protacpilot-memory/*`
  deleted from disk) + untracked `protacxtend-memory/` (338 files), `todo/`,
  `outputs/strategies/`. HEAD commit message claims "clean tree".
  `diff` of `protacpilot-memory/README.md` (HEAD) vs `protacxtend-memory/README.md`
  = identical.
- **✅ RESOLVED (Gate C, 2026-09-23):** verified before commit that all 104
  tracked files are byte-identical at the new path and 0 files existed only in
  the old tree; `protacxtend-memory/` is a strict superset (338 files, 234
  new). Committed as a rename in **`82a0e4d`**
  (`chore(memory): commit protacpilot-memory -> protacxtend-memory rename`).
  `.gitignore` now also excludes the new generated `evaluation/`, `paper/` and
  `benchmarks/results/` paths, mirroring the old hygiene, so those 74 generated
  files remain untracked on disk exactly as before. No memory data was deleted.
  Full recursive hash of all 338 on-disk files before the rename commit:
  `gateC/F14_memory_provenance.json`.
- **Status:** `verified` (rename committed, content preserved).
- **Evidence:** `git show --stat 82a0e4d`; `gateC/F14_memory_provenance.json`.

### F-15 · Installed `protacxtend` console script is stale and broken
- **Observed:** `/home/saveenas/miniconda3/bin/protacxtend` (pip 0.1.0) does
  `from synglue_agent.cli import main` → `ModuleNotFoundError`.
  `pyproject.toml` at HEAD correctly declares
  `protacxtend = "protacxtend.cli:main"`, and
  `python -m protacxtend.cli` works.
- **Meaning:** the "synglue_agent residue fixed" claim holds for the source
  tree but **not** for the installed environment. Any user running
  `protacxtend` hits the error.
- **Status:** `failed` (installed artifact); fix = `pip install -e . --force-reinstall`.
- **✅ FIXED (Gate A):** `pip install -e . --no-deps` → version `0.3.0`;
  console script imports `protacxtend.cli`; `protacxtend --help` works.
- **Evidence:** `evidence/console_script.txt`.

### F-16 · Test collection is polluted by vendored third-party repos
- **Observed:** bare `python -m pytest` → `1357 tests collected, 156 errors`,
  almost all from `data/synthesis_prediction/repos/…`. `pytest.ini` has no
  `testpaths`/`norecursedirs`, so the reported test count is not the project's.
  Focused runs pass: `tests/ + protacxtend/tests/` selection = 107 passed
  (execution modes, P0-B, grader, canonical stack, toolkit, CLI, results schema)
  and `test_mode_router + test_entity_extraction + test_toolkit_status +
  test_agent_tool_exposure` = 48 passed.
- **Evidence files:** `evidence/pytest_focused_claims.txt` (107 passed),
  `evidence/pytest_focused_subsystems.txt` (48 passed),
  `evidence/pytest_collection_raw.txt` (1357 collected / 156 errors).
- **Status:** `partial` (tests fine; configuration misleads).
- **✅ FIXED (Gate A):** `pytest.ini` pins `testpaths = tests protacxtend/tests`
  and `norecursedirs`; bare `pytest` now collects **968, 0 errors**
  (was 1357 / 156 errors).

---

## What is genuinely solid

- Parser gate: 125 prompts, target accuracy **1.0000** (threshold 0.98) — `verified`.
- Typed schemas `RunManifest` / `EvidenceItem` / `ToolRun` exist and the
  `strategy` CLI emits them — `verified` (presence, not validity).
- Scientific-mode agent-tool guardrails raise typed failures — `verified`.
- Benchmark grader supports exact/categorical/ranked/numeric/set/constraint/
  rubric types with an explicit `unscorable_missing_fields` path — `verified`.
- `SCORABLE_MANIFEST.json` = 48/48 scorable, 29 flagged — `verified`.
- 34 agent tools wired to real executors with fixtures — `verified`.

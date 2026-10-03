# Audited `todo/PROTACXtend_04_CHECKLIST.md`

Status legend: `[x]` verified · `[~]` partial · `[!]` failed/contradicted · `[-]` absent/not run.

Date 2026-09-23 · HEAD `0abbe83`.

## Foundation and toolkit

- [!] **Locate exact universal markdown tracker and record current HEAD, worktree, environment.**
  No `AGENTS.md` / `universal*.md` exists. HEAD `0abbe83` recorded; worktree is
  **not clean** (104 deletions + untracked rename) → F-14, evidence/git_state.txt.
- [x] **Reconcile three supplied reports against source/tests/artifacts; record contradictions.**
  This audit + `csv/claim_reconciliation.csv`.
- [~] **Verify canonical entry points and one persisted typed strategy for deterministic + adaptive paths.**
  Deterministic `strategy` emits `TherapeuticStrategy.v1`; adaptive path not re-run in this session.
- [!] **Confirm scientific mode rejects every fixture/default along CLI, API, direct and agent paths.**
  Agent path rejects (verified); canonical `strategy` path identical in demo/scientific → F-03.
- [~] **Freeze registry with runnable, licensed, valid and externally-assessed statuses separately.**
  296 rows enumerated; `available/executable` hard-coded 0 → F-07.
- [~] **Validate tool input/units, output domain, provenance, versions, error codes, resource limits.**
  `ToolRun`/`EvidenceItem` fields exist; no per-tool validation report; units not encoded.
- [~] **Implement question-matched routing and measurable failure/retry/fallback/abstention policy.**
  `FailureCode` + retry exist; KNOW-01 was routed to the design engine → F-02.
- [~] **Implement source, chemistry and mechanism critics with rejection traces.**
  One `CriticVerifier`, 7 checks, warnings include measured-vs-predicted → F-12.
- [-] **Verify memory versioning, evidence approval, document cutoff and benchmark isolation.**
  No cutoff/as-of/leakage code found → F-11.
- [!] **Execute all 48 pilot tasks with real tools; distinguish offline grading from execution.**
  1 executed (KNOW-01, score 0.0); 48/48 is offline self-grading → F-01/F-05.
- [-] **Expert-review the 29 flagged gold checklists and archive adjudications.**
  No adjudication artifact → F-06.
- [~] **Pin dependencies, models, data release, code hash, seed and exact rerun commands.**
  `benchmark/FREEZE_MANIFEST.json` + `frozen/` exist; acceptance `execution_log.csv`
  paths point at a different checkout (`/storage/saveena/protacpilot/...`) → F-13/S3.

## Study gates

- [~] **E1:** 296 registered / 34 agent executables; no execution+validity funnel.
- [-] **E2:** 48 authored, 500 not attempted (correct); no gold/splits/baselines-scored.
- [-] **E3:** no 100-task fault schedule.
- [-] **E4:** no 50 contexts / blinded experts.
- [-] **E5:** no 100-record assay-context table.
- [-] **E6:** no frozen-ID ablation with paired CIs.
- [-] **E7:** no frozen as-of data/model/index.
- [-] **E8:** no pre-registered prospective cases.

## Manuscript and figures

- [-] Table of planned/adjudicated/executed N — no such artifact.
- [-] Landscape axes rubric + comparator evidence — absent.
- [~] Tool count vs mechanistic validity vs utility reported distinctly — the critic
  labels predictions separately (good), but no comparative validity/utility measured.
- [-] Primary endpoints, denominators, exclusions, stats, negatives documented — absent.
- [~] Claims link to accessible run artifacts — strategy manifest links run_id; benchmark
  claims have no `scored/` output.

## Blocker log (updated)

| ID | Blocker | Evidence | Owner | Next action | Gate | Status |
| --- | --- | --- | --- | --- | --- | --- |
| B01 | Universal tracker missing | no `AGENTS.md`/`universal*.md` | maintainer | supply path or confirm deprecated | All | **Open** |
| B02 | Full executed pilot unverified | 1 task, score 0.0 | benchmark owner | decide canonical path (Q5), run 48 | E2/E3 | **Open** |
| B03 | Gold review pending | 29 flagged, no file | reviewers | name 2 annotators, adjudicate | E2 | **Open** |
| B04 | Figure coordinates unsupported | no rubric/source matrix | figure owner | treat as hypothesis | Comparison | **Open** |
| B05 | SCIENTIFIC not enforced on canonical path | demo==scientific output | scientific lead | move guard to canonical entry | All | **NEW** |
| B06 | BRD4→M0QZD9 | strategy output vs curated O60885 | scientific lead | prefer reviewed/curated resolution | KNOW | **NEW** |
| B07 | Install broken | console script imports synglue_agent | maintainer | `pip install -e . --force-reinstall` | All | **NEW** |
| B08 | Working tree dirty | 104 deletions, untracked rename | maintainer | commit rename or restore | All | **NEW** |
| B09 | No scored baseline output | `benchmark_results/scored/` empty | benchmark owner | wire acceptance runner → grader | E2 | **NEW** |
| B10 | pytest misconfigured | 156 collection errors from vendored repos | maintainer | set `testpaths`/`norecursedirs` | CI | **NEW** |

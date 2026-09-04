# RELEASE_READINESS_REPORT — cleaned release candidate (review only, NOT committed/pushed)

Date: 2026-09-03 · Repo: `the-ahuja-lab/PROTACXtend` · HEAD `58c690b` (nothing after it committed)
Everything below is staged/unstaged on disk only — **no commit, no push** was made.

---

## 1. Final PASS/FAIL matrix

| # | Check | Status | Evidence |
|---|---|---|---|
| 1 | .gitignore excludes runtime, node_modules, memory logs, caches, temp, derived caches | ✅ PASS | `/runtime/`, `node_modules/`, `**/memory/learnings/`, `**/memory/workflow_logs/`, `tui/outputs/`, `data/synglue/data/grover_*.csv` etc. verified with `git check-ignore` (note: git 2.34 does **not** honour trailing inline comments on ignore lines — block uses comment-only lines) |
| 2 | Stray root image dupes removed (canonical `website/assets/` copies exist) | ✅ PASS | `AA.png`, `hero.png`, `git_hero.png` deleted; canonical `AA.png`/`AA.webp`/`00_PROTACXtend_hero_visual.png`/`og-cover.png` tracked |
| 3 | Derived GROVER caches not committed + documented | ✅ PASS | `git rm --cached` for `grover_warhead.csv`/`grover_e3.csv`; ignore pattern added; regeneration documented in `data/synglue/data/README.md` |
| 4 | Git LFS for large required model artifacts | ✅ PASS (partial) | `.gitattributes`: `protacxtend/modules/*/models/*.joblib` → LFS; both staged artifacts are 133-B pointers. **Note:** already-committed `data/synglue/models/multitask_transformer.pt` (36 MB) and tack joblibs remain plain in history — converting needs `git lfs migrate` (history rewrite, requires clean tree) → defer to after release commit, before final push decision |
| 5 | Would-be-lost legitimate files staged | ✅ PASS | agentic/llm/state/workflows/stream/launcher sources, 5+1 tests, `tui/` sources, `structural/` module+test, `THIRD_PARTY_NOTICES.md`, `data/synglue/data/README.md` — all py_compile-validated before staging |
| 6 | Deletion audit (1 020 deletions) | ✅ PASS — 0 accidental losses | synglue_agent→protacxtend migration 623 (291 .py, **0 without replacement**); ICM_HMGB2 240 (experiment scratch: scripts/images/results — campaign-specific, history-archived); SynGlue_Py 81 (legacy/vendored incl. pip); legacy docs/dirs 65 (superseded by README/documentation hub/CHANGELOG/module docs); no legitimate source/test/config/package-metadata loss found |
| 7 | Re-run secret scan post-staging | ✅ PASS | 0 candidate hits across staged adds + untracked text (first 200 KB of files <1.5 MB, node_modules/runtime excluded); recommend full gitleaks before push |
| 8 | M1–M7 module test suite | ✅ PASS | **111 passed** (M1 24 · M2 8 · M3 21 · M4 9 · M5 16 · M6 17 · M7 16) |
| 9 | Artifact load sweep | ✅ PASS | all 5 joblib artifacts load (incl. `synglue_agent.*` pickle refs via `protacxtend/_compat.py`) |
| 10 | Module-7 quickstart | ✅ PASS | best 0.7958 (40 evals) vs random 0.6022; batch of 10 |
| 11 | Config parse | ✅ PASS | `config/scientific_status.yaml` valid (7 modules, 8 degradation models) |
| 12 | Clean-environment install + import | ✅ PASS | fresh venv `pip install -e .` OK → version 0.3.0; core+module imports OK; optimizer runs; `protacxtend`/`PROTACXtend` CLI `--version` OK. (Found+fixed: `joblib`, `scikit-learn` added to `pyproject.toml` deps) |
| 13 | Nothing committed / pushed | ✅ PASS | `git log` HEAD unchanged `58c690b`; index/working-tree only |

---

## 2. git status --short (summary; full listing in chat/history)

```
A  465 added · M  67 modified · D  1 020 deleted   (index delta vs HEAD 58c690b)
??  4 untracked  (internal review docs only: CODE_REPORT_2026-09-02.md,
                  NP_HARD_AGENT_DESIGN.md, TECHNICAL_COHERENCE_REVIEW.md,
                  STAGED_FILES_AUDIT.md)
```

## 3. Staged totals

- **Added:** 465 files · **Modified:** 67 · **Deleted:** 1 020
- **Total staged size ≈ 30.1 MB** (non-LFS, measured on disk) + 2 Git-LFS pointers (133 B each)

## 4. Staged files > 1 MB

| Size | Path | Class |
|---|---|---|
| 34.1 MB (on disk) | `protacxtend/modules/cell_context_selector/models/cell_context_model.joblib` | **LFS pointer staged** |
| 3.0 MB (on disk) | `protacxtend/modules/degradation_ml/models/pdc50_model.joblib` | **LFS pointer staged** |
| 4.2 MB | `protacxtend/modules/cell_context_selector/data/cell_context_expression.csv` | dataset (M5) |
| 2.5 MB | `protacxtend/modules/e3_opportunity/data/context_expression_matrix.csv` | dataset (M6) |
| 2.2 MB | `website/assets/og-cover.png` | media |
| 2.2 MB | `website/assets/00_PROTACXtend_hero_visual.png` | media |
| 2.2 MB | `code/00_PROTACXtend_hero_visual.png` | ⚠️ duplicate of website asset |
| 1.6 MB | `protacxtend/app/assets/protac_challenge_infographic.png` | media |
| 1.6 MB | `protacxtend/app/assets/protac.png` | media |
| 1.5 MB | `protacxtend/app/assets/protac_degradation_hero_bg.png` | media |
| 1.4 MB | `protacxtend/app/assets/protac_yellow.png` | media |
| 1.0 MB | `website/assets/logo.png` | media |
| 1.0 MB | `code/logo .png` | ⚠️ duplicate of website asset (odd filename) |

## 5. Git LFS tracked

Pattern (`.gitattributes`): `protacxtend/modules/*/models/*.joblib filter=lfs diff=lfs merge=lfs -text`
Staged LFS pointers: `cell_context_model.joblib`, `pdc50_model.joblib`
Deferred (needs `git lfs migrate`, history rewrite): `data/synglue/models/multitask_transformer.pt` (36 MB), tack joblibs.

## 6. Remaining untracked (grouped)

- Internal review docs (intentional, uncommitted): `CODE_REPORT_2026-09-02.md`, `NP_HARD_AGENT_DESIGN.md`, `TECHNICAL_COHERENCE_REVIEW.md`, `STAGED_FILES_AUDIT.md`
- Everything else on disk is now gitignored: `runtime/` (26 246 files), node_modules, memory/workflow logs, tui outputs, derived grover caches.

## 7. Source/test files still scheduled for deletion

- **Zero** product source/test loss. The only .py/scripts in the deletion set are:
  - `synglue_agent/**` → 291 .py, every one migrated to `protacxtend/**` (0 unreplaced)
  - `SynGlue_Py/**` (20 .py) → legacy/vendored package, gitignored dir
  - `ICM_HMGB2_Hypothesis_Testing/**` (240 files incl. ~15 ad-hoc analysis scripts) → obsolete experiment campaign, preserved in git history

## 8. Open items before YOU decide

1. **Duplicates** under `code/` (`00_PROTACXtend_hero_visual.png`, `logo .png`) vs `website/assets/` — decide keep-as-source-art or remove.
2. **LFS migrate** for already-committed 36 MB `.pt` — optional; repo pushes fine today (nothing >50 MB staged now).
3. **Pages deployment** still requires repo-admin enable (Settings → Pages → GitHub Actions), unrelated to this cleanup.
4. Final push should be preceded by `gitleaks` full-history scan and a decision to commit this staged release as the release commit.

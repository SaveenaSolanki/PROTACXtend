# STAGED & UNTRACKED FILE AUDIT — release-readiness classification

Audit date: 2026-09-03 · Repo: `the-ahuja-lab/PROTACXtend` (HEAD `58c690b`)
Method: `git ls-tree HEAD` vs index vs worktree-untracked, per-file sizes, content
scans. Scope: everything the pending release commit would publish + everything
left on disk.

**Numbers:** HEAD 1 776 files → release commit would **ADD 436 / DELETE 1 020 /
MODIFY 756**; **26 289 untracked files** on disk (26 246 inside `runtime/`).

---

## 1. Classification summary (what the release commit would publish)

| Requested category | Count | Size | Representative entries | Verdict / action |
|---|---|---|---|---|
| **Source code** | 304 | 2.5 MB | `protacxtend/` package (agents, tools, modules, backend, research, cli) | ✅ publish (reviewed this session) |
| **Tests** | 61 | 0.4 MB | `protacxtend/modules/*/tests`, `protacxtend/tests`, root `tests/` | ✅ publish |
| **Configs** | 25 | 0.1 MB | `config/scientific_status.yaml`, `pyproject.toml`, module `configs/*.json`, `.github/workflows`, Dockerfile | ✅ publish |
| **Documentation** | 35 | 0.1 MB | `documentation/`, `website/*.md` audits, module `docs/` | ✅ publish |
| **Model artifacts** | 2 staged | 37.1 MB | `cell_context_model.joblib` (33.3 MB!), `pdc50_model.joblib` (2.9 MB) | ⚠️ **LFS** (+ already-committed: `multitask_transformer.pt` 36 MB, chemprop `best.pt`, `linker_generator.pt`) |
| **Benchmark outputs** | 3 | <0.1 MB | module `artifacts/benchmark_results.json`, smoke outputs | ⚠️ `artifacts/` is gitignored → committed via `-f`; decide keep-vs-regenerate |
| **Datasets** | 1 + curated small CSVs | ~0.2 MB | `protacxtend/data/*.csv` (curated targets/warheads/e3/linkers) | ✅ publish (small, curated) |
| **Large datasets** | 2 | **66.7 MB** | `data/synglue/data/grover_warhead.csv` (**58.9 MB**), `grover_e3.csv` (6.3 MB) | ❌ **blocker: >50 MB → push fails without LFS** — LFS or regenerate-on-demand |
| **Media/binary** | 19 | 22.7 MB | `website/assets/` (AA.png 2 MB, hero 2.1 MB, og 2.1 MB, logos), `code/*.png|*.svg` | ⚠️ images >1 MB → LFS; SVGs fine |
| **Website frontend** | 7 | 2 600 lines | `website/index.html`, `styles.css`, `app.js` | ✅ publish |
| **Generated/cache** | 26 223 | **199 MB** | `node_modules` (site/tui/runtime), `__pycache__`, `.pytest_cache`, `.ipynb_checkpoints`, `dist/` | ❌ **gitignore** (mostly untracked already) |
| **Runtime/pi-agent deps** | 26 246 | ~199 MB | `runtime/node_modules/…` (typescript, genai, clipboard native .node binaries, wasm) | ❌ **do not publish** — add `runtime/` to .gitignore |
| **Runtime memory logs** | 5 | 4.1 MB | `protacxtend|synglue_agent/memory/learnings/learning_store.jsonl` (2 MB each) + `workflow_logs/*.json` | ❌ **do not publish** — internal decision logs; gitignore |
| **Vendored upstream clones** | (ignored) | large | `data/protac_repos/repos/*` (7 upstream repos incl. models), `data/synthesis_prediction/repos` | ❌ already gitignored — keep out; fetch on demand |
| **Temporary** | — | — | root `AA.png`, `hero.png`, `git_hero.png` (1.6–2 MB each, duplicates of website assets) | ❌ **delete** (untracked dupes) |
| **Secrets / API keys** | 0 found | — | content scan of staged adds + untracked text (200 KB heads) | ✅ none found (caveat below) |

**Staged deletions (1 020):** `synglue_agent/` 627 (→ moved to `protacxtend/`),
`ICM_HMGB2_Hypothesis_Testing/` 240, `SynGlue_Py/` 81, root `md/` 35, legacy
root docs (AGENT_*, FEYNMAN_USAGE, ASSET_MANIFEST, …) — intentional cleanup. ✅

---

## 2. ⚠️ Critical findings

### 2.1 Push blocker — file > 50 MB
`data/synglue/data/grover_warhead.csv` = **58.9 MB** is staged; GitHub refuses
files > 50 MB (or 100 MB with LFS). Options:
- **Git LFS** for `*.csv` under `data/synglue/` (+ `cell_context_model.joblib`,
  `multitask_transformer.pt`), **or**
- don't commit derived GROVER embedding caches — regenerate from SMILES at
  build time (they are model-derived, not primary data).

### 2.2 Untracked real source — would be LOST if not added before the release commit
These exist on disk but are NOT staged:
- `protacxtend/agentic/{chat_agent,contract,registry}.py`
- `protacxtend/agents/stream.py`
- `protacxtend/llm/{chat_client,setup}.py`
- `protacxtend/{pi_launcher,runtime_worker}.py`
- `protacxtend/state/{artifacts,events,store}.py`
- `protacxtend/workflows/` (pilot_runner, protacpilot_blueprint, __init__)
- `protacxtend/tests/test_{conversational_agent,launcher_e,protacpilot_pipeline,runtime_worker,slices_efgh}.py`
- `tui/{launch.sh,src/app.ts,src/events.ts,src/index.ts,tests/app.test.ts}`
- `THIRD_PARTY_NOTICES.md` (license notices — should be published)
- `synglue_agent/tui_bridge/*` (only if synglue_agent is not fully deleted)

### 2.3 Should never be published (add to .gitignore now)
```
runtime/
node_modules/
**/memory/learnings/*.jsonl
**/memory/workflow_logs/
```
And delete stray root images: `AA.png`, `hero.png`, `git_hero.png`.

### 2.4 Secret scan
No API keys/tokens/private keys detected in staged adds + untracked text files
(sample scan of first 200 KB of files < 1.5 MB, excluding node_modules).
Caveat: not a byte-level scan of binaries/history — gitleaks full-history CI job
(already configured) covers history; re-run before the final push.

### 2.5 .gitignore gaps discovered
Missing generic patterns: `runtime/`, `node_modules/` (root-level),
`**/memory/learnings/*.jsonl`, stray-image names. Present-but-note: `*.pt`,
`*.pkl`, `docs/`, `artifacts/`, `outputs/…` are ignored → the session's module
docs/artifacts had to be force-added (`git add -f`); remember for future adds.

---

## 3. LFS candidates (files > ~5 MB that must remain in-repo)

| File | Size | Why keep | LFS |
|---|---|---|---|
| `data/synglue/data/grover_warhead.csv` | 58.9 MB | SynGlue embedding cache | ✅ **required to push** |
| `data/synglue/data/grover_e3.csv` | 6.3 MB | SynGlue embedding cache | ✅ |
| `protacxtend/modules/cell_context_selector/models/cell_context_model.joblib` | 33.3 MB | M5 committed artifact | ✅ |
| `protacxtend/modules/degradation_ml/models/pdc50_model.joblib` | 2.9 MB | M4 committed artifact | optional |
| `data/synglue/models/multitask_transformer.pt` (HEAD) | 36.1 MB | SynGlue committed model | ✅ |
| `data/linkers/linker_generator.pt` (HEAD) | 0.7 MB | generative linker model | no |
| `website/assets/AA.png` etc. | ~2 MB each | site media | optional (WebP variants already small) |

---

## 4. Bottom line / release checklist

1. Add `runtime/`, `node_modules/`, memory-jsonl patterns to `.gitignore`; delete root `AA.png`/`hero.png`/`git_hero.png`.
2. Stage the "would-be-lost" source (§2.2) — decide whether the agentic/state/workflows/tui code ships in this release or is intentionally excluded.
3. Resolve the 58.9 MB file: enable Git LFS (`git lfs track`) or drop derived caches.
4. Re-run gitleaks before push.
5. Then commit the release (1 188+ staged changes) and push (Pages enablement still an admin action).

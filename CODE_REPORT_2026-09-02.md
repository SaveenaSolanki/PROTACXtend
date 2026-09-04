# CODE REPORT — what was built (2026-09-02)

Everything implemented on **2026-09-02** (git-verified): the **sequential scientific-module program (M1–M7)** reached Modules **5 and 6 implemented end-to-end**, Module 4 was **independently audited and approved**, and the audit-gated **claim register** was added. Below: the full code inventory — every file, its purpose, the logic, the data, the validation, and the exact gates that say what may and may not be claimed.

Repo: `the-ahuja-lab/PROTACXtend` · HEAD `995b437` (2026-09-03, incl. two fix commits on top of yesterday's work) · generated 2026-09-03 from the working tree.

---

## 1. Timeline — what landed yesterday (4 commits)

| Commit | Time | What | Size |
|---|---|---|---|
| `0559238` | 20:27 | **Record sequential module build M1–M4** — tracker, module code, tests, docs, agent tools; **Module-4 independent audit → APPROVED** (entity-context forwarding fix; 9/9 tests; prob-task honesty documented); Module-5 cell-context spec + data audit (PROTAC-Degradation-DB 2141 rows / 180 cell lines; threshold-derived Active gate) | 60 files · **+4 819** |
| `8c1b9a8` | 21:35 | **Module 5 — cell-context/proteotype-aware degradation model** `predict_cell_context()`: curated PROTAC-Degradation-DB (1913 rows) + DepMap 24Q4 transcriptomics; grouped A–G benchmark (leg D beats B on unseen-PROTAC pDC50, **R² 0.605 vs 0.513**); gated claims (cell-context aware = True; transcriptomics unseen-line transfer = False; proteotype = False); artifact + agent tool + **16 tests**; M4-v1 frozen + `M4_FOLLOWUP` memo | 30 files · **+7 812** |
| `1fddf4f` | 22:57 | **Module 6 — Novel E3 Ligase Opportunity Engine** `rank_e3_ligases()`: 30-gene catalog × 8 evidence axes; verdicts SUPPORTED / PROMISING / EXPLORATORY / INSUFFICIENT (expression-only never recommends; SUPPORTED needs direct precedent; low-expression capped); grouped retrospective benchmark (**RF AUROC .93 unseen-E3**; recruiter ablation −0.52); challenges 1–7 as tests (**17**); agent tool `run_e3_opportunity`; docs README/SPEC/VALIDATION/LIMITATIONS/REFERENCES; `artifacts/benchmark_results.json` | 31 files · **+4 954** |
| `d147645` | 23:12 | **Module 6 audit-gated claim register** `docs/CLAIMS.md` — every SUPPORTED vs NOT-YET-SUPPORTED claim tagged to its evidence | 2 files · **+59** |

**Yesterday's committed delta: 123 file-changes, ≈ +17 644 lines added.**

The M1–M7 program continues the sequential rule: each module only starts after the previous one's status report is audited (M1 ✓ QA, M2 ✓, M3 ✓ surrogate/data-gated, M4 ✓ audit-approved, M5 ✓ code+benchmark, M6 ✓ code+benchmark, **M7 pending** — Module 7 not started until the Module-6 status report audit closes).

---

## 2. Module 5 — Cell-context degradation model (deep dive)

**What it does:** predicts pDC50 per **cell line**, not just per PROTAC — conditioning degradation on transcriptomic cell context.

| Concern | Fact |
|---|---|
| Entry point | `predict_cell_context()` (module `predict.py`) |
| Labels | PROTAC-Degradation-DB curated: **1913 rows** (DC50 1181 / Dmax 761) |
| Context features | DepMap **24Q4 transcriptomics** on 1512 rows → `data/context_joined.csv` (1913 rows, header+1913) |
| Provenance | `data/omics_provenance.json`, `data/cell_line_mapping.csv`, `data/cell_context_expression.csv` |
| Benchmark | grouped splits **A–G**; **leg D (with context) beats leg B (PROTAC-only) on unseen-PROTAC pDC50: R² 0.605 vs 0.513** → cell-context-aware = True |
| Artifact | `models/cell_context_model.joblib` (committed) |
| Tests | **16** (`tests/test_cell_context_selector.py`) |
| Docs | `docs/{README,SPEC,VALIDATION,LIMITATIONS,REFERENCES}.md` + `docs/M4_FOLLOWUP.md` memo |
| Agent tool | `protacxtend/tools/cell_context_tool.py` + `tools/context_degradation_predictor.py` |
| Claim gates | ✅ cell-context aware · ❌ transcriptomic unseen-line transfer NOT claimed · ❌ proteotype NOT claimed (no proteomics) |

**Files built (26):** `dataset.py prepare.py features.py models.py train.py predict.py omics.py genemap.py cellline.py schemas.py __init__.py` + data + docs + tests + `examples/train_demo.py`.
**Logic chain:** prepare (join DB labels ↔ DepMap features by cell line) → feature build (expression signature) → grouped train (entity-aware encoding, no leakage) → benchmark legs A–G → artifact + tool → verdict with explicit applicability state.

**Key follow-up memo (M4_FOLLOWUP.md):** train a separately-versioned context-INDEPENDENT pDC50 model (M4-v2) on the same data to publish M4-v1 vs M5-context vs M4-v2 on a common held-out set — pending audit; M4-v1 artifact frozen.

---

## 3. Module 6 — Novel E3 Ligase Opportunity Engine (deep dive)

**What it does:** answers "is this E3 ligase a *usable, evidence-backed* degrader recruiter for this POI?" with honest SUPPORTED / PROMISING / EXPLORATORY / INSUFFICIENT verdicts — never recommends on expression alone.

| Concern | Fact |
|---|---|
| Entry points | `rank_e3_ligases()`, `evaluate_e3_ligandability()` (module `rank.py` / `predict.py`) |
| Catalog | `data/e3_catalog.csv` — **30 genes** (31 lines incl. header) |
| Evidence axes | **8** — expression (DepMap `context_expression_matrix.csv`, 1673 rows), UniProt localization cache (`uniprot_localization.csv`, **78 genes**), structure/lysines, recruiters/precedent, selectivity, context, uncertainty |
| Verdict rules | SUPPORTED requires **direct precedent**; expression-only never recommends; low-expression capped (see `docs/CLAIMS.md` for the exact ruleset) |
| Benchmark | grouped retrospective — **RF AUROC .98 (easy) → .93 unseen-E3**; recruiter ablation **−0.52** → `artifacts/benchmark_results.json` |
| Tests | **17** (`tests/test_e3_opportunity.py`, challenges 1–7) |
| Docs | `docs/{README,SPEC,VALIDATION,LIMITATIONS,REFERENCES}.md` + **`docs/CLAIMS.md`** (audit-gated register, `d147645`) |
| Agent tool | `protacxtend/tools/e3_opportunity_tool.py` → `run_e3_opportunity` |
| Public-claim gate | **code-complete but report-gated** → `config/scientific_status.yaml`: `implemented: true`, `status: UNDER EVALUATION`, `public_claim: false`; website shows NO claim |

**Files built (20+):** `e3_catalog.py recruiters.py localization.py structure.py lysines.py context.py selectivity.py features.py models.py rank.py predict.py uncertainty.py dataset.py schemas.py __init__.py` + data + docs + tests + `examples/quickstart.py`.

---

## 4. Supporting systems built yesterday (commit 0559238)

- **Module tracker** `protacxtend/modules/PROTACXTEND_MODULE_BUILD.md` — sequential build order, per-module status summaries, Module-4 independent audit write-up (incl. the entity-context forwarding fix and honest in-sample R² ≈0.95 correction).
- **M1–M4 module code recorded** (each: `core/config/schemas/__init__`, `configs/<module>.json`, `docs ×6`, tests, agent tool): hook effect (24/24 tests), lysine ubiquitination (structural surrogate, real-PDB pending), cooperativity (data-gated surrogate, harness ready), degradation ML (audit-approved 9/9).
- **Module-5 spec + data audit** (dataset provenance, 2141-row audit, Active-label threshold derivation documented).

---

## 5. The bigger picture — codebase totals (working tree, 2026-09-03)

| Area | Files | Lines |
|---|---|---|
| `protacxtend/` (package, total) | 320 `.py` | 58 656 |
| ├ `protacxtend/tools/` | 93 | 22 842 |
| ├ `protacxtend/modules/` (M1–M6 + tracker) | 61 | 7 871 |
| ├ `protacxtend/agents/` (31-node graph + agents) | 38 | 6 423 |
| └ `protacxtend/research/` (retrieval layer) | 10 | 3 020 |
| `tests/` (root suite) | 24 | 1 939 |
| `website/` (site v2.11 + audits) | 7 | 2 600 |
| `documentation/` (docs hub) | 7 | 734 |

Test inventory: 76 test files / 626 `def test_*` (root suite + module suites); per module: M1 24 · M2 8 · M3 21 · M4 9 · M5 16 · M6 17.

Data (in-repo, measured): PROTAC-Degradation-DB join 1913 rows · DepMap 24Q4 1512 · TACK parquets 4184/6561 · GROVER caches 1104/117/117 · M6 catalog 30 genes · localization 78 genes · linker library 241 · M4 curated labels 64/32 · model binaries: 7 committed (5 joblib + multitask transformer + chemprop checkpoint).

---

## 6. Claims you may (and may not) make from yesterday's work

| Claim | Allowed? | Gate source |
|---|---|---|
| "Cell-context-aware degradation prediction, transcriptomic" | ✅ YES | Module-5 validation (leg D R² 0.605 > leg B 0.513) |
| "Proteotype/proteomics-aware" | ❌ NO | no proteomics data — explicitly not claimed |
| "Generalizes to unseen cell lines" | ❌ NO | unseen-line transfer not claimed |
| "Novel-E3 opportunity engine exists (30-gene catalog)" | ✅ YES as code | tracker DONE v1.0.0 + 17 tests + benchmark |
| "E3 verdicts SUPPORTED/PROMISING are validated predictions" | ❌ NO publicly | Module-6 status report **gated** — `public_claim: false` until audit |
| "Module 7 / active learning exists" | ❌ NO | only CLI `/learn` surface — PARTIAL, not claimed |
| "M1 hook effect validated" | ✅ YES | VALIDATED BASELINE, 24/24 tests |
| "M2/M3 production-grade structural prediction" | ❌ NO | structural surrogate / data-gated — real-PDB & experimental-α datasets pending |

---

## 7. Related work built at the same time (staged, not yet committed)

Yesterday's commits are the code core; the release staging still in the index (1 188 changes) carries the surrounding presentation layer built alongside it:
- **Website v2.x scientific-coherence rewrite** (`website/` — index/styles/app + audits + changelog) — KNOW→REASON→DESIGN→DISCOVER, model panel, validation matrix, evidence badges, docs hub (v2.0–v2.11).
- **Package restructure** `synglue_agent/* → protacxtend/*` with `pyproject.toml` entrypoints (`protacxtend`/`PROTACXtend` → `protacxtend.cli:main`), Dockerfile, `deploy/`, `.github/workflows/{ci,pages}.yml`.
- **`config/scientific_status.yaml`** — machine-readable status source of truth.
- **`documentation/`** hub (GETTING_STARTED / ARCHITECTURE / WORKFLOWS / API_REFERENCE / GITHUB / DEEP_RESEARCH).
- Two fix commits already landed today: `010958b` (audit coherence v2.11) and `995b437` (version 0.3.0 + Module-7 wording).

**Next actions:** commit the staged release (1 188 files) as your release commit · close the Module-6 status-report audit before claiming E3 verdicts · enable GitHub Pages (admin) for the live site.

---

## 8. Reproduce / verify commands

```bash
git log --since="2026-09-02 00:00" --until="2026-09-03 00:00" --oneline   # yesterday's commits
git show --stat 8c1b9a8    # Module 5
git show --stat 1fddf4f    # Module 6
python -m pytest protacxtend/modules/cell_context_selector/tests -q    # 16 tests
python -m pytest protacxtend/modules/e3_opportunity/tests -q           # 17 tests
python -c "import json;print(json.load(open('protacxtend/modules/e3_opportunity/artifacts/benchmark_results.json')))"
```

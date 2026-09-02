# RELEASE CLOSURE REPORT — SynGlue v0.3-agentic-core

_Author: PROTACXtend engineering (Feynman agent)_
_Date: 2026-08-06_
_Branch: `release/v0.3-agentic-core`_
_Tag: `v0.3.0-agentic-core`_
_Commit: `66c42849` (HEAD at closure; rewritten as `1c02183` on 2026-08-07 — see §8 note)_

---

## 1. Final architecture summary

**One runtime entry point** — `synglue_agent/agents/runtime.py::run_protacpilot(request, mode)`
with `mode="deterministic"` (v0.1 reproducible workflow) and `mode="agentic"`
(the unified v0.3 adaptive graph).

```
run_protacpilot(request, mode)
  ├── deterministic → v0.1 workflow (unchanged, agentic_mode=false guarantee)
  └── agentic       → LangGraph StateGraph
        ├── deterministic scientific tools
        │     ├── E3-context engine        (evidence-based CRBN-vs-VHL)
        │     ├── warhead/exit-vector checks + bounded repair loops
        │     ├── linker-design stage      (strain loop router)
        │     ├── ternary ensemble         (geometric proxy + P4ward + SE3-PROTACs)
        │     ├── degradation endpoint     (DC50 + Dmax + class + context)
        │     ├── retrosynthesis           (RAscore/AiZynthFinder + routing)
        │     └── NSGA-II Pareto ranking
        ├── adaptive routers (state → next node; evidence-driven)
        ├── LLM decision layer (Ollama gpt-oss:20b, 6 roles, schema-enforced,
        │     deterministic validators gate every output, safe fallback)
        ├── human gates (before expensive modelling + final recommendation)
        └── persistent checkpointer (PostgresSaver, cross-process resume)
```

Supporting layers:
- **Degradation interface** (`degradation_interface.py`): chemprop (trained) →
  synglue → heuristic, with labelled fallback + provenance.
- **Memory** (`memory/stores.py`): three separate stores — Run State, Evidence,
  Learning — with the learning retrieval sequence (failure signature → validated
  match → suggestion → deterministic validation → outcome recording).
- **Observability** (`observability/tracing.py`): every run writes
  `outputs/runs/<run_id>/trace.jsonl` + `summary.json` (node timings, tool
  calls, decisions, errors).
- **Deployment** (`deploy/`): docker-compose (api, worker, postgres, redis,
  ollama) with model volumes; `deploy/p4ward_worker.py` job queue consumer.

## 2. Test counts (full suite, 2026-08-06)

| Suite | Count |
|---|---|
| Total passed | **293** |
| Skipped (slow: real AiZynthFinder routes, deselect markers) | 11 |
| Deselected (slow marker) | 11 |
| Duration | ~7 min |
| Command | `pytest synglue_agent/tests/ synglue_agent/agents/test_ternary_stage.py -m "not slow"` |

Coverage areas (test files): architecture unification (10), ternary stage (7),
agentic scenarios (6), linker stage (9), learning memory + integration (28),
degradation endpoint (10), E3-context engine (8), LLM layer + gateway (27),
LLM roles harness (8), retrosynthesis (13 incl. 1 slow real), ternary ensemble
(12), Pareto (7), adaptive extras (15), uncertainty layer (5), memory stores
(10), production wiring (10), chemprop degradation (5), + pre-existing suites.

## 3. Formal benchmark table (Task 8b, 16 PROTAC-DB molecules: 8 potent + 8 weak)

| System | ρ (DC50) | Enrichment | Synth-rate | Gates | Repairs | Runtime (s) |
|---|---|---|---|---|---|---|
| fixed_pipeline | 0.479 | 0.750 | 0.929 | 0 | 0 | 0.4 |
| adaptive_deterministic | 0.785 | 0.875 | 0.929 | 0 | 0 | 249 |
| llm_planner_only | 0.785 | 0.875 | 0.929 | 0 | 0 | 254 |
| **full_agentic** | **0.785** | **0.875** | 0.929 | 0 | 0 | 258 |
| full_minus_memory | 0.785 | 0.875 | 0.929 | 0 | 0 | 256 |
| full_minus_repair | 0.785 | 0.875 | 0.929 | 0 | 0 | 248 |
| full_minus_uncertainty | 0.785 | 0.875 | 0.929 | 0 | 0 | 248 |
| full_minus_context | 0.785 | 0.875 | 0.929 | 0 | 0 | 249 |

**Interpretation (documented)**: the trained degradation layer dominates in-domain
ranking (+0.31 ρ over heuristic; enrichment 0.75 → 0.875). The agentic components'
value is demonstrated on failure-injected and safety scenarios (per-layer ablation
B6: repair rescues discarded candidates; AD prevents OOD ranked confident;
E3-context vetoes low-expression biology) — not on clean in-domain ranking.

**Retrospective benchmark (64 held-out PROTAC-DB molecules)**: heuristic ρ=0.42 →
Chemprop ρ=0.758 → conformal ensemble ρ=0.783; hit<100nM 53→77%; MAE 1.21→0.61
log10; **conformal coverage 92.2%** (target 90%).

## 4. Container boot-test results (docker compose, full stack)

| Service | Status | Verification |
|---|---|---|
| postgres | healthy | `/agentic-design` run persisted **20 checkpoints** for the run thread (queried) |
| redis | healthy | queue lifecycle via compose redis: queued → running → done |
| api (:8001) | up | `/health`, `/llm/status`, `/agentic-design`, `/mode validate` all OK |
| worker | up | consumed degradation job → **real trained-model output** (`chemprop_multitarget`, DC50=33.9 nM, Dmax=80%, class=active, AD=out_of_domain correctly flagged) |
| ollama | healthy | LLM provider reachable; host gpt-oss:20b fallback path verified |

Container bugs found + fixed by the boot test: psycopg-binary (PostgresSaver),
openpyxl (xlsx), libexpat1 (cuik_molmaker), aizynthfinder numpy<2 conflict
(omitted by design → RAscore-only degradation), GPU assumption (auto gpu/cpu
accelerator), rdkit 2026.3.4 pin (cuik-molmaker-pin), ABI fix as script.

## 5. LLM validation results (Task 6, live gpt-oss:20b, temperature 0)

Expanded case bank: **17 cases / 5 roles**.

| Role | Cases | Pass |
|---|---|---|
| supervisor | 4 | 4/4 |
| evidence | 4 | 4/4 |
| critic | 3 | 3/3 |
| repair | 4 | 4/4 |
| report | 2 | 2/2 |
| **Total** | **17** | **17/17 (100%)** |

| Safety metric | Value |
|---|---|
| Valid structured output | 1.0 |
| Unsupported tool selection | 0 |
| Invalid SMILES modification | 0 |
| Numerical hallucination | 0 |
| Human-gate recall (unsafe cases) | 1.0 |
| Context-overflow failures | 0 |

Two functional gaps found by the harness (repair OOD-escalation, report
number-fidelity) were **fixed at the model level** (prompt hard rules + a
machine-checkable `numbers` field) and re-verified.

## 6. End-to-end case results (Task 8a)

| Case | Predicted DC50 | Class | Best E3 | Runtime |
|---|---|---|---|---|
| A: known potent PROTAC | 6.9 nM | active ✓ | CRBN | 21s |
| B: known weak degrader | 334.5 nM | inactive ✓ | CRBN | 19s |
| C: HMGB2-ICM (new design) | 6.1 nM (chemistry) vs SE3 ternary ≈ 0 | **AMBIGUOUS → human gate** | CRBN | 18s |

Cross-layer finding: the chemistry-trained degradation model and the
structure-trained SE3 ternary model disagree on the ICM PROTAC; the ensemble
correctly routes to human review instead of fabricating consensus.

## 7. Model and dataset versions

| Artifact | Version / location |
|---|---|
| Chemprop single-target (log DC50) | `outputs/benchmark/chemprop_cal_ensemble_seed{0,1,2}/model_0/best.pt` (3-member, conformal-calibrated) |
| Chemprop multi-target (logDC50 + Dmax) | `outputs/benchmark/chemprop_multitarget/model_0/best.pt` |
| Training data | PROTAC-DB 3.0 (`data/benchmark/PROTAC-DB_3.0_protacs.xlsx`; 15,502 PROTACs, 2,275 with DC50; train sets exclude benchmark + calibration molecules) |
| AiZynthFinder | USPTO ONNX policy + templates + ZINC stock (`data/retrosynthesis/models/aizynth/`, 738 MB) |
| SE3-PROTACs | pretrained `SE(3)-PROTACs.pt` (from cloned repo) + ESM2-t6_8M |
| SynGlue transformer | `SynGlue_Py/models/multitask_transformer.pt` (9M params) + GROVER checkpoint |
| E3 expression evidence | curated literature table (`e3_expression_evidence.csv` / builtin) |
| LLM | gpt-oss:20b via Ollama 0.32.5 (host, port 11435) |

## 8. Exact Git commit

```
Branch:  release/v0.3-agentic-core
Tag:     v0.3.0-agentic-core
Commit:  66c42849 — Full compose stack boot-tested: real degradation in
          container, postgres/redis/queue verified, LLM case bank 17/17

> **2026-08-07 history hygiene note**: the release history was rewritten with
> `git filter-repo` to strip virtualenvs, cloned dependency repos, large data
> dumps and runtime DBs (7.93 GiB → 100.79 MiB) for the controlled GitHub
> publication under `github.com/SaveenaSolanki/protacpilot`. Second hygiene
> pass (2026-08-07): `M1.log` (committed Jupyter token) + all `*.log` purged
> after gitleaks scan; remaining 11 findings verified as false positives
> (conda build hashes, package names). Release commit now `17b85dd` (new SHAs by
> design). Tag `v0.3.0-agentic-core` points at the gitleaks-clean release commit.
```

## 9. Known limitations

1. **Research-grade, not clinically validated.** All predictions are
   computational; no wet-lab confirmation exists for any candidate. DC50/Dmax
   are model estimates with calibrated-but-wide intervals (±1.4 log10).
2. **8-system benchmark task is in-domain-only** for the architecture
   comparison — the agentic components' value shows on failure/safety
   scenarios (B6 ablation), not on clean ranking. The ranking task must
   include OOD/failure-injected candidates to discriminate them directly.
3. **Retrosynthesis in the container** runs RAscore/SAScore-proxy only
   (aizynthfinder omitted for the numpy<2 conflict); the full AiZynthFinder
   stack runs on the host worker.
4. **Cellular context data is curated**, not live DepMap/Open Targets/COSMIC
   (no API keys configured); expression tables are literature-derived.
5. **LLM case bank is 17 cases** — representative of the spec's metrics, not
   exhaustive. The harness is the tool for expansion.
6. **E3-context explanation is rule+table-driven**, not from live retrieval.
7. **Conformal intervals are wide** — ranking is reliable (ρ≈0.78); absolute
   DC50 values need caution.
8. Docker compose ollama container has no gpt-oss pulled (fresh volume); the
   LLM path uses host Ollama or deterministic fallback.

## 10. Reproduction command

```bash
# Environment (protacpilot conda env)
conda activate protacpilot
cd /storage/saveena/protacpilot

# Full test suite (fast; slow = real AiZynthFinder routes)
python -m pytest synglue_agent/tests/ synglue_agent/agents/test_ternary_stage.py -m "not slow"

# Slow real-tool tests
python -m pytest synglue_agent/tests/test_retrosynthesis.py -m slow
python -m pytest synglue_agent/tests/test_ternary_ensemble.py -m slow

# Benchmarks
python scripts/benchmark_degradation.py --sample 64      # retrospective (hours)
python scripts/agentic_benchmark.py --n 16               # 8-system comparison
python scripts/e2e_challenge.py                          # A/B/C cases

# LLM role validation (live)
python scripts/eval_llm_roles.py --live

# Full container stack
docker compose -f deploy/docker-compose.yml up -d api worker

# Unified runtime
python -c "from synglue_agent.agents.runtime import run_protacpilot; \
  print(run_protacpilot('Design PROTACs for BRD4 with CRBN', mode='agentic'))"
```

## 11. Final PASS/FAIL checklist

| Requirement | Status |
|---|---|
| One production entry point | ✅ `agents/runtime.py` |
| Conditional routing (not fixed sequence) | ✅ 6 scenario tests |
| Bounded repair loops (ternary/linker/warhead/exit-vector) | ✅ 24 tests |
| Dynamic tool selection from evidence | ✅ adaptive_extras (15 tests) |
| Parallel candidate evaluation | ✅ ThreadPool, order-preserving |
| Uncertainty calibration + applicability domain | ✅ conformal 92.2% coverage; AD 8/8 OOD flagged |
| Candidate-specific evidence + provenance | ✅ per-result tool/version; DecisionLog |
| Human approval checkpoints | ✅ before expensive modelling + final |
| Multi-objective Pareto ranking | ✅ NSGA-II (7 tests) |
| Retrospective benchmark on known PROTACs | ✅ ρ=0.783, 64 molecules |
| Ablation vs non-agentic pipeline | ✅ 8 systems + per-layer B6 |
| Real retrosynthesis | ✅ AiZynthFinder (host) + routing + 20-PROTAC tests |
| Real ternary ensemble (≥2 independent methods) | ✅ P4ward + SE3-PROTACs weights + geometric proxy |
| DC50 + Dmax prediction | ✅ multi-target Chemprop |
| Cellular context in degradation | ✅ E3-expression gate |
| E3-context engine (data-derived explanation) | ✅ 8 tests, CRBN-vs-VHL verbatim |
| Validated LLM layer (schema, registry, gates) | ✅ 17/17 live; 0 safety violations |
| Persistent checkpointer (cross-process resume) | ✅ PostgresSaver verified |
| Job queue + worker | ✅ redis/sqlite, real model output in container |
| Central logging/tracing | ✅ per-run trace.jsonl |
| Dockerized services (boot-tested) | ✅ full stack healthy + verified |
| Unified memory (3 stores) | ✅ 10 tests |
| Full regression green | ✅ 293 passed |

---

## Statement

**SynGlue v0.3-agentic-core satisfies the predefined functional,
scientific-safety, persistence, deployment and observability requirements for
a research-grade agentic PROTAC design platform.**

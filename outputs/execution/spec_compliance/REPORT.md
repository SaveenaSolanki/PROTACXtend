# PROTACXtend agent-system specification — compliance & status report

Spec source: `PROTACXtend_Agent_System_Specification.md` (dated 2026-10-06, status *Proposed*).
Method: every claim below was re-measured against the working tree at `sprint-2`; the spec
itself states it "does not establish that any new code … has been implemented", so each item
was checked, not assumed. Commands and raw logs are in this folder.

## 0. Headline

| Question | Measured answer |
|---|---|
| Full test suite | **30 failed · 1423 passed · 41 skipped** (`pytest_full_final.log`) |
| Before this pass | 46 failed · 1388 passed (two import-time env leaks inflated failures) |
| 19 spec capability classes | **19/19 present** in `scientific_backends.registry` |
| Agent tools exposed | **44** (all with executors, 4 surfaces) — but only **34 have probe fixtures** |
| Runtime ledger (512 records) | **NOT PRESENT** in the workspace → reconciliation BLOCKED |
| Benchmark gold | **0/48 adjudicated** → correctness/benchmark gates BLOCKED |
| Agent-system operational claim (spec §15) | **NOT established** (no pinned LangGraph decision-loop trace) |

## 1. What this pass changed (concrete fixes, measured)

Two import-time side effects mutated the process-global execution mode and cascaded into
unrelated tests. Both fixed; the full-suite failure count dropped **46 → 30**.

| Fix | File | Evidence |
|---|---|---|
| Moved `PROTACXTEND_EXECUTION_MODE` set from import time into `main()` | `scripts/gateC_four_system.py` | import no longer sets the var; `test_agent_tool_exposure` 9→2 failures |
| Same for the closed48 worker (imported by `tests/test_structured_run.py`) | `scripts/closed48_worker.py` | in-process subset: 8 failures vs 15 before |
| Made the paired development check set its mode via `monkeypatch` | `tests/test_source_backed_design_and_adapters.py` | 30 passed after fix |

Commands run:
```
python -m pytest -q -p no:cacheprovider          # 3× (logs: pytest_full*.log)
python -m pytest tests/test_structured_run.py protacxtend/tests/test_agent_tool_exposure.py -q
git worktree add /tmp/pxt_pre 71624fa             # pre-change differential, then removed
```

## 2. Spec section-by-section status

| Spec § | Requirement | Status | Evidence |
|---|---|---|---|
| §2 | Coordinator with specialist agent loops in typed LangGraph | **PARTIAL** | `protacxtend/agents/{graph,agentic_core,checkpointer,stream}.py`, `protacxtend/llm/graph.py` exist; deterministic 30-node graph is real. A typed-action coordinator with per-role decision loops and observed-result revision is **not demonstrated by a pinned trace** |
| §3 | Named role responsibilities | **PARTIAL** | Agent classes exist (`SupervisorAgent`, `DesignPlannerAgent`, target/warhead/E3/linker/prediction/critic…); not verified as separate context/tool-permission boundaries |
| §4 | Typed action protocol, budgets, terminal outcomes | **PARTIAL** | `agentic/registry.py` (44 typed specs), budget/timeout fields in run config; `test_agent_tool_exposure` execution envelope exists. No pinned multi-step trace showing evidence-driven plan revision |
| §5 | Typed state/results; evidence-kind separation | **PARTIAL** | Scientific-result schema `1.0.0`; `run_records.py`; evidence kinds present. `SyntheticInputNotAllowed`/`MissingScientificInput` typed failures work |
| §6 | Operational tool contract (schemas, prereqs, license, smoke) | **FAIL (partial)** | 44 tools expose 4 surfaces (`/tools`, `/tools/{name}`, `/tools/{name}/run`, TUI/web/agent) — **but 10 repo-backed tools have no probe fixture**, so the smoke-check contract is unmet for them |
| §7 | 19 capability classes | **PASS** | All 19 present with ≥1 backend each (see §3 below) |
| §8 | Family-specific scientific acceptance | **PARTIAL** | Docking/MD/ADMET backends registered; `scientific_backends` runner exists. Contested degradation route fails tests (below) |
| §9 | Fallback protocol with evidence relabeling | **PARTIAL** | `escalation/` + `scientific_backends` registry; `test_escalation`, fallback tests mostly pass; `test_fault_injection::test_abstention_when_no_fallback_exists` fails |
| §10 | Ledger reconciliation (512 records, 85 residual) | **BLOCKED** | The raw runtime ledger is **not in the workspace** (spec §1/§16 say so). Only a 7-event escalation ledger exists (`analysis/audit/ledger/`). 85 residual identities cannot be recovered |
| §11 | Distinct evidence statuses | **PARTIAL** | REGISTERED (registers) and EXECUTABLE (44 tools, 16 Gate-C runs) established; TESTED partial; BENCHMARKED limited; EXTERNAL/PROSPECTIVE **none** |
| §12 | Pinned trace with action selection + revision/abstention | **FAIL (not established)** | Gate-C traces exist but are fixed-path executions; no pinned trace of an evidence-driven action revision |
| §13 | Paired benchmark (500 prompts / 20 subjects) | **BLOCKED** | Gold 0/48; `benchmark500` items are uncurated templates. Gate-C is 4 cases × 4 systems, execution-only |
| §14 | 7 acceptance stages | see §4 | — |
| §15 | Publication language | **Design-stage wording only** | The operational sentence is not yet supportable |

## 3. §7 capability classes — measured

All 19 spec classes resolve in `scientific_backends.registry` (0 gaps):

`chemistry 6 · conformer_generation 3 · protein_preparation 2 · pocket_detection 2 ·
ligand_docking 10 · ppi_docking 9 · ternary_docking 4 · molecular_dynamics 4 ·
md_analysis 1 · interaction_energy 1 · binding_energy 3 · admet 6 ·
interaction_fingerprint 1 · linker_analysis 1 · protac_scoring 1 ·
molecular_glue_scoring 1 · metabolite_ppi_scoring 1 · protein_structure 1 ·
candidate_ranking 2` (number = backends offering the class).

## 4. §14 implementation stages — acceptance gates

| Stage | Required artifact | Status |
|---|---|---|
| 1 Pin release + reconcile inventories | all 85 identities resolved; declared taxonomy | **BLOCKED** — source ledger absent; release manifests `study/freeze_manifest{,_v2}.json` exist |
| 2 Tool/result contracts + routes + fallback tests | schemas, license/hardware, exposure, fallback | **PARTIAL** — 44 tools/4 surfaces; 10 lack probe fixtures; fallback tests partly failing |
| 3 Coordinator + specialist decision loops | typed actions, observed-result routing, budget, revision trace | **PARTIAL** — typed actions + budgets exist; revision trace not demonstrated |
| 4 Verify contested model + learning paths | actual checkpoint/inference route; separate memory vs active-learning | **PARTIAL/FAIL** — `test_degradation_model` fails (model loader refuses `/tmp` artifact); TACK model sklearn-version warnings |
| 5 Durable execution + reporting | recovery trace, job dedup, provenance | **FAIL** — `test_investigate_persistence` 5 failures (`fake_graph()` missing `capability` kwarg) |
| 6 Freeze + paired benchmarks | gold/rubric + all task IDs + paired scores | **BLOCKED** — gold 0/48 |
| 7 Independent/prospective validation | external evidence | **BLOCKED** — none |

## 5. §12 first verification campaign — 5 scenarios

| Scenario | Status | Evidence/blocker |
|---|---|---|
| Reference design/analysis with identity + prediction route | **PARTIAL** | dBET1 reconstruction assembles and passes the identity gate (`outputs/execution/next_phase/source_backed_design_correction.md`), but the full `/design` payload is rejected in SCIENTIFIC mode (demo linkers, below) |
| Preferred-backend failure → fallback/not_assessed | **PARTIAL** | fallback machinery present; `test_fault_injection` failing |
| Component-identity/stereo failure → rejection/repair | **PASS (control)** | placeholder provenance fails the identity gate; dBET1 passes (`tests/test_source_backed_design_and_adapters.py`) |
| Missing/contradictory evidence → retrieval revision | **NOT DEMONSTRATED** | no pinned trace of retrieval revision |
| Interruption/resumption without duplicate jobs | **FAIL** | `test_investigate_persistence` failures |

## 6. Measured failure taxonomy (30) — no assumptions

| # | Cluster | Count | Representative reason |
|---|---|---|---|
| A | Interface exposure / registry drift | 3 | `assert 44 == 34`; 10 repo tools lack probe fixtures |
| B | KNOW/REASON routing & answer contracts | ~10 | `IndexError: list index out of range`; `'' == 'O60885'`; `KeyError:'hypotheses'` |
| C | Persistence/recovery | 5 | `fake_graph() got an unexpected keyword argument 'capability'` |
| D | Design payload / honest labels | ~5 | `honest_report_labels`; design bridge tests |
| E | Contested degradation / model loading | 2 | `refusing to load artifact outside repo root: /tmp/.../tiny_dc50.pkl`; `'MODEL_PREDICTED' != 'heuristic_stub'` |
| F | Launch/architecture markers | 2 | `FileNotFoundError: .../CLI` |
| G | External DB content | 2 | `no ligands for KEAP1`; `'I-BET151' not in ChEMBL …` |
| H | Output format drift | 1 | `assert 'InChIKey=' in '…inchikey=…'` |

All of A–H reproduce at the pre-change commit `71624fa` except the two leak-fix recoveries,
i.e. they are **not introduced by this pass** (differential verified with a git worktree).

## 7. IMPORTANT finding — `/design` is not SCIENTIFIC-clean

In `PROTACXTEND_EXECUTION_MODE=scientific` (the strict mode the spec requires), a real
`/design` run is **rejected by the P0-B payload gate**:

```
SyntheticInputNotAllowed: workflows.designer.run_design: scientific payload contains
14 fixture/synthetic finding(s); first at
candidate_evidence_table[2].provenance.linker_source='curated_demo_linker'
```

Root cause: the deterministic DESIGN route mixes the verified dBET1 candidate with
exploratory candidates built from `curated_demo_*` warheads/E3 ligands/linkers. The verified
candidate is clean; the exploratory ones are demo-provenance and trip the gate.
Default mode is `DEMO`, which is why the test passes by default and fails under SCIENTIFIC.
**This is the top blocker for §8/§12 "source-backed end-to-end design".**

## 8. Where we stand (plain)

- **Real and measured:** 19 capability classes with backends; 44 tools on 4 surfaces; typed
  failure gates; a working dBET1 reconstruction control; Gate-C 4-case execution; freeze
  manifests; 1423 passing tests.
- **Stubbed/partial:** coordinator decision-loop trace; tool smoke fixtures for 10 repo
  tools; persistence/resumption; honest-label checks; degradation model loading under the
  repo-root security policy.
- **Blocked on external input:** the 512-record runtime ledger (not in workspace) and the
  48-case adjudicated gold (human review) — both required by §10 and §13.
- **Not established:** the operational agent-system claim in §15 (needs a pinned trace).

## 9. Next executable actions (ordered)

1. **Fix `/design` SCIENTIFIC cleanliness** — separate exploratory (demo) candidates from
   the scientific payload (evidence-kind `exploratory` / design-brief section) so the
   verified candidate survives the gate. *(stage 2/8; no gold needed)*
2. **Add probe fixtures for the 10 repo-backed tools** (or explicitly scope them out of the
   probe contract) — clears 2–3 interface failures. *(stage 2)*
3. **Fix persistence `fake_graph()` contract** (`capability` kwarg) — clears 5 failures. *(stage 5)*
4. **Fix degradation model loader test path** (repo-root policy vs `/tmp`) and the
   `MODEL_PREDICTED` vs `heuristic_stub` expectation — clears ~2 failures. *(stage 4)*
5. **Reconcile the 512-record ledger** — **requires the source ledger file** (human/external).
6. **Adjudicate gold** — **requires human reviewers** (0/48).

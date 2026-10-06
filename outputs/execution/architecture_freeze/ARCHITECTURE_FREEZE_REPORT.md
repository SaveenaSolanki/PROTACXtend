# PROTACXTEND_AGENTIC_ARCHITECTURE_V1 — Freeze report

Date: 2026-10-06 · Baseline commit `ff21db5` · Branch `sprint-2`

## DECISION: `ARCHITECTURE FREEZE: NOT READY`

MUST gates **G6, G7, G8, G15 are PARTIAL** (details below). Per the acceptance
rules, the architecture may **not** be declared frozen. No benchmark work was started.

---

## 1. Git commit
Baseline `ff21db5`; this pass adds the architecture package, qualification harness,
tests and artifacts (see the commit accompanying this report).

## 2. Files changed / added
```
protacxtend/architecture/__init__.py        new  package
protacxtend/architecture/state.py           new  canonical TherapeuticHypothesisState + TerminalStatus/Plan/Budget
protacxtend/architecture/ontology.py        new  EvidenceRecordV1 (kind≠status), Claim, Contradiction, Disagreement, UncertaintyAxis, ScientificAxisProfile
protacxtend/architecture/critic.py          new  independent ScientificCritic
protacxtend/architecture/coordinator.py     new  AdaptiveCoordinator + CoordinatorDecision
protacxtend/architecture/deliberation.py    new  per-axis disagreement + experiment discrimination
scripts/architecture_qualification.py       new  Q1–Q9 harness
tests/test_architecture_v1.py               new  11 contract tests
docs/architecture/*.md (mirrored to outputs/execution/architecture_freeze/docs/)
outputs/execution/architecture_qualification/q1..q9/
outputs/execution/architecture_freeze/{ARCHITECTURE_FREEZE_REPORT.md,architecture_manifest.json,test_summary.json,baseline_pytest.log,final_pytest.log}
```
Existing production `/design`, the canonical stack, tool registry and security
policies were **not** replaced (no parallel orchestration stack).

## 3. Architectural changes actually implemented
- One canonical scientific state (`TherapeuticHypothesisState`, 16 sections).
- First-class evidence ontology separating `evidence_kind` from `evidence_status`;
  DEMO/EXPLORATORY cannot back scientific claims.
- A **real adaptive coordinator**: state-gap action selection (not a fixed script),
  real tool execution, observation, independent verification, **genuine plan
  revision** (versioned, reason + triggering evidence, old plan preserved),
  no-progress guard, budgeted retries/fallback, typed termination.
- Independent critic (fail-closed) and per-axis disagreement / experiment-selection.
- Checkpoint/resume with provenance continuity.

## 4. Q1–Q9 results (real executions; `outputs/execution/architecture_qualification/`)
| Case | Result | Key evidence |
|---|---|---|
| Q1 normal success | **PASS** | BRD4+CRBN → dBET1 assembled; SUCCESS; 11 steps |
| Q2 true replanning | **PASS** | BTK+VHL unsupported → plan v1→v2, reason + triggering evidence, switch to CRBN (MT-802) |
| Q3 tool failure + recovery | **PASS** | injected `predict_cooperativity` fault → classified → fallback recorded in `state.control.fallbacks` |
| Q4 contradictory evidence | **PASS** | retrieved 5T35 vs derived geometry → `Contradiction` + critic REVISE (not PASS) |
| Q5 justified abstention | **PASS** | MYC+VHL (no source-backed route) → JUSTIFIED_ABSTENTION, no candidate |
| Q6 scientific-mode integrity | **PASS** | DEMO/EXPLORATORY not claim-admissible; critic BLOCKs demo-only claim; scanner flags demo row, verified row clean |
| Q7 model disagreement | **PASS** | degradation_ml=HIGH vs ternary=LOW/permeability=LOW → per-axis Disagreement + resolving action |
| Q8 experiment discrimination | **PASS** | 3 competing hypotheses → max-discrimination experiment selected with per-hypothesis outcomes + decisions |
| Q9 durability | **PASS** | checkpoint → resume → continue; run_id + trace continuity; candidate count preserved |

## 5. Full test results
| | failed | passed | skipped |
|---|---:|---:|---:|
| Baseline `ff21db5` | 28 | 1425 | 41 |
| Final (this pass) | **28** | **1441** | 41 |

**New failures: 0. Fixed: 0.** The 28 failures are byte-identical to baseline.
New file `tests/test_architecture_v1.py`: **11/11 pass**.

## 6. Remaining failures — taxonomy (all pre-existing, per baseline)
| Category | count | examples |
|---|---:|---|
| KNOW/REASON routing & answer contracts | 9 | `test_structured_run` (6), `test_target_response_contracts`, `test_np_hard_agent_features`, `test_protacdb_evidence` |
| Persistence/recovery | 5 | `test_investigate_persistence` (`fake_graph() missing 'capability'`) |
| Design bridge / honest labels | 5 | `test_design_tui_workflow_bridge` (3), `test_honest_report_labels` (2) |
| External-DB content | 2 | `test_e3_library` (KEAP1 / I-BET151) |
| Mechanism / fault / integrity | 3 | `test_mechanistic_milestone`, `test_fault_injection`, `test_integrity_gates` |
| Env/launcher/architecture markers | 3 | `test_launcher_e`, `test_architecture_unification`, `test_local_inference_and_drugbank` |
| Interface exposure (order-dependent) | 1 | `test_agent_tool_exposure::test_tui_bridge_capability_transport` (passes in isolation) |

## 7. Architecture acceptance gates
| Gate | Requirement | Result | Evidence |
|---|---|---|---|
| G1 | canonical state | **PASS** | `state.py` + `test_canonical_state_has_all_required_sections` |
| G2 | adaptive coordinator | **PASS** | `coordinator.py` state-gap selection; Q1/Q3 traces |
| G3 | true replanning | **PASS** | Q2 (plan v2, reason, triggering evidence, different E3) |
| G4 | tool contracts | **PASS** | 44 tools accounted (40 fixtures + 4 `PROBE_EXEMPT`); exposure tests |
| G5 | evidence ontology | **PASS** | `ontology.py`; kind≠status test; claim gate |
| G6 | scientific-mode separation | **PARTIAL** | payload-layer separation + demo isolation PASS, **but the upstream `identity_assembly_gate` still passes demo/generated linkers** (documented) |
| G7 | independent critic | **PARTIAL** | `ScientificCritic` independent of generation, but only a subset of the 18-point falsification checklist is implemented |
| G8 | uncertainty engine | **PARTIAL** | `UncertaintyAxis` by axis exists; expected-information-gain/cost action ranking not yet implemented |
| G9 | disagreement engine | **PASS** | `deliberation.analyze_disagreement`; Q7 |
| G10 | failure recovery | **PARTIAL** | fallback works (Q3); full failure-class taxonomy/retry matrix not exhaustively exercised |
| G11 | abstention | **PASS** | Q5; typed `JUSTIFIED_ABSTENTION` |
| G12 | persistence/resume | **PASS** | Q9 checkpoint/resume roundtrip |
| G13 | termination | **PASS** | typed `TerminalStatus` + `termination_reason`; no-progress guard |
| G14 | tracing/provenance | **PASS** | `agent_trace.v2` records per spec §28; Q1–Q9 traces |
| G15 | structured final report | **PARTIAL** | state has all report sections, but a rendered `ProtacTherapeuticHypothesisReport` serializer is not implemented |
| G16 | architecture qualification traces | **PASS** | Q1–Q9 artifacts present |

## 8. Known limitations (exact)
1. The **seven logical workers** are responsibilities mapped onto coordinator actions
   (`WORKER` map); they are not seven independently deployed agent loops.
2. **`identity_assembly_gate` still passes demo/generated linkers.** SCIENTIFIC
   cleanliness is enforced at the payload layer, not the upstream gate. Tightening the
   gate changes gate semantics and was intentionally not done without a deliberate decision.
3. **Residence time, ubiquitination competence, PK/PD** have typed slots and explicit
   `UNKNOWN`/`INSUFFICIENT_EVIDENCE` defaults; **no validated predictors** exist, so no
   numbers are produced (by design).
4. The **critic** covers evidence provenance + route support; the remaining
   checklist items are declared but not enforced.
5. **Q10 human-in-the-loop** was deferred (documented, SHOULD-level).
6. **Skills/SOP registry (§29)** is not implemented as a first-class registry.
7. 28 pre-existing test failures remain (taxonomy §6); none are architecture-caused.

## 9. Can `PROTACXTEND_AGENTIC_ARCHITECTURE_V1` be declared frozen?
**No.** `ARCHITECTURE FREEZE: NOT READY`.

Required before freeze:
- G6: tighten `identity_assembly_gate` to reject non-source-backed linkers (deliberate
  semantics change + tests).
- G7: implement the full critic falsification checklist.
- G8: implement expected-information-gain / cost action ranking.
- G15: implement the typed `ProtacTherapeuticHypothesisReport` serializer.
- (recommended) G10: full failure-class retry matrix; §29 skills registry; Q10 HITL.

No benchmark, gold-adjudication or competitor work was started.

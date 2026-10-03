# P1 closeout — benchmark readiness

Date: 2026-09-23 · Session 4. This closes every open item in the P1 section of
[`TODO.md`](TODO.md). All work is offline-testable except the live LLM baseline,
which ran against the configured provider.

## Delivered

| item | artifact | evidence |
|---|---|---|
| Failure taxonomy | `protacxtend/canonical/failures.py` — `FailureClass` (26 classes), typed `Failure`, `classify_failure`, `failure_taxonomy()` | `tests/test_p1_governance.py` |
| Retry / fallback / abstention policy | `protacxtend/canonical/policy.py`, wired into `protacxtend/canonical/task_graph.py`; new `TaskStatus.ABSTAINED` | `tests/test_p1_governance.py` |
| EvidenceCritic | `protacxtend/canonical/critics.py::EvidenceCritic` | `tests/test_p1_governance.py` |
| MechanismCritic | `protacxtend/canonical/critics.py::MechanismCritic` | `tests/test_p1_governance.py` |
| ReproducibilityCritic | `protacxtend/canonical/critics.py::ReproducibilityCritic` | `tests/test_p1_governance.py` |
| Explicit tool provenance | `protacxtend/canonical/provenance.py`; every `ModuleResult.provenance` pins tool/version/backend/citation | `tests/test_p1_governance.py` |
| 34-adapter fixture audit | `protacxtend/runtime/adapter_audit.py` → `outputs/adapter_audit.json` (34/34 clean, 0 residual) | `tests/test_p1_governance.py` |
| Non-executable tool decision | `protacxtend/toolkit/disposition.py` → `outputs/tool_disposition.json`/`.md` (123 classified) | `tests/test_p1_governance.py` |
| Matched-tool registry | `benchmark_runner/matched_tools.py` (27/27 distinct permitted ids matched, 0 unmatched) | `tests/test_p1_baselines.py` |
| Biomni adapter | `benchmark_runner/external.py::BiomniAdapter` (fail-closed JSON stdin/stdout contract) | `tests/test_p1_baselines.py` |
| TPD comparator adapter | `benchmark_runner/external.py::TPDComparatorAdapter` | `tests/test_p1_baselines.py` |
| LLM baseline | `benchmark_runner/baselines.py::LLMBaseline` | ran live |
| Retrieval-only baseline | `benchmark_runner/baselines.py::RetrievalOnlyBaseline` | ran 48/48 |
| Tool-only baseline | `benchmark_runner/baselines.py::ToolOnlyBaseline` | ran 48/48 |
| 48-task baseline comparison | `scripts/run_baseline_comparison.py` → `benchmark_results/baselines/` | full run |

## Baseline comparison result (48/48 tasks, offline tools)

| system | scored | abstained | mean score | KNOW | REASON | DESIGN | DISCOVER |
|---|---|---|---|---|---|---|---|
| retrieval-only | 48 | 23 | 0.0625 | 0.0417 | 0.0 | 0.0417 | 0.1667 |
| tool-only | 48 | 4 | 0.0781 | 0.0417 | 0.0 | 0.0833 | 0.1875 |
| Base-LLM-control | 48 | 0 | 0.1684 | 0.2708 | 0.0278 | 0.1667 | 0.2083 |

Match coverage: 27 distinct permitted tool/database ids, 27 matched, 0
unmatched. The LLM baseline ran with live provider credentials; if no key is
present it returns `skipped_no_credentials` and never fabricates an answer.

## Honest gaps (carried forward)

* The deterministic design engine still under-serves KNOW/REASON; this is the
  P0 partial and is now *measurable* through the baseline comparison.
* Biomni and the TPD comparator are fail-closed adapters: they execute only
  when an operator configures `PROTACXTEND_BIOMNI_CMD` /
  `PROTACXTEND_TPD_COMPARATOR_CMD` (or `..._TPD_COMPARATOR_CMD`). They report
  `unavailable` otherwise rather than inventing output.
* The full 48-task **PROTACXtend** executed pilot remains a P0 partial; the
  baseline comparison above is the matched-compute control, not the candidate
  score.

## Reproduce

```bash
python -m pytest tests/test_p1_governance.py tests/test_p1_baselines.py -q
python - <<'PY'
from protacxtend.runtime.adapter_audit import write_adapter_audit
from protacxtend.toolkit.disposition import write_disposition_report
write_adapter_audit("outputs/adapter_audit.json")
write_disposition_report("outputs/tool_disposition.json", "outputs/tool_disposition.md")
PY
python scripts/run_baseline_comparison.py --limit 8          # fast subset
python scripts/run_baseline_comparison.py                    # full 48-task run
```

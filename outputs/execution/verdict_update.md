# Verdict update — supported claims only

Scope: this pass. Rows not listed remain `NOT YET MEASURED` from
`tpdeval/docs/03_VERDICT.md`. No cell is populated by inference.

| Area | PROTACXtend (S3) | LLM+RAG (S1) | LLM+flat-tools (S2) | Biomni (S4) | Basis |
|---|---|---|---|---|---|
| Adapter exists & executes | ✅ yes | ✅ yes | ✅ yes | ✅ yes | 16/16 Gate-C runs, `gateC_4sys_v1` |
| Execution outcome mix (4 cases) | 1 answered / 3 abstained | 4 answered | 4 answered | 3 answered / 1 abstained | `task_level_results.parquet` |
| Typed abstention on REASON-02 (declared missing input) | ✅ abstained | ❌ answered | ❌ answered | ❌ answered | objective pipeline-integrity check |
| KNOW-01 accession (O60885) resolved | ✅ | ✅ | ✅ | ✅ | behavioral check |
| Cost reported | ✅ $0.0024 | ✅ $0.0017 | ✅ $0.0026 | ⚠️ not reported | adapter records |
| Task correctness / accuracy | NOT YET MEASURED | — | — | — | gold 0/48 adjudicated |
| Scientific superiority | NOT YET MEASURED | — | — | — | 4-case smoke, not powered |
| Resource-matched comparison | NOT APPLICABLE | partial | partial | ❌ native-only | declared differences |
| Temporal / reproducibility / fault-injection | NOT YET MEASURED | — | — | — | not run |

## Claim discipline

- **Supported**: the four systems are wired and executed real tasks; S3 alone abstained
  on the one declared-missing-input case; the source-backed design path assembles MZ1
  and passes the identity gate.
- **Not supported**: "PROTACXtend is better/safer than Biomni"; any accuracy figure; any
  scientific correctness claim; any resource-matched comparison. These require
  adjudicated gold, a powered sample, resource matching and (for superiority) paired
  statistics at the task unit.
- **Literature check**: "first published TPD-agent benchmark" remains a **hypothesis**.
  `outputs/manuscript_strategy/tables/competitor_matrix.md` already lists the field
  (Biomni Eval1, SMDD-Bench, BixBench, TACK/PROTAC-Bench). The claim is not asserted here.

# Next-phase completion report — validate the comparison before scaling

Date: 2026-10-03 · Repo `sprint-2`
New freeze: `study/freeze_manifest_v2.json` (supersedes v1) · New run:
`benchmark_results/gateC_four_system/gateC_4sys_v2` (copy:
`outputs/execution/gateC_4sys_v2/`)

## 1. Changes, commands, checks

| change | file |
|---|---|
| S2 observations retain provenance/evidence; param names in catalog; must use ≥1 domain tool; meta tools excluded; `has_data` separates empty-ok from failure | `benchmark_runner/live_systems.py` |
| Corrected verified-candidate id derivation (was hard-coded `SGA-VERIFIED-MZ1`; now `SGA-VERIFIED-<reference>`) | `protacxtend/agents/design_path_agent.py` |
| Telemetry-availability fields (`tokens_available`, `cost_available`, `cost_source`) | `scripts/gateC_four_system.py` |
| Unique-structure audit (stereo-aware) | `scripts/audit_unique_structures.py` |
| Tests: S2 contract, paired dev check, dBET1 id, gold integrity | `tests/test_source_backed_design_and_adapters.py`, `tests/test_gold_integrity.py` |
| Audit, parity, corrections, handoff | `outputs/execution/next_phase/` |

Commands: S2 smoke (`live_systems` real calls) · `pytest` (35 passed) ·
`python scripts/audit_unique_structures.py …` · `python scripts/gateC_four_system.py
--systems S1,S2,S3,S4 --online --run-id gateC_4sys_v2` (16 runs).

## 2. S2 tool parity + executed observations

Parity table: `outputs/execution/next_phase/s2_s3_parity.md` — **40 common domain
tools, all with executors**; S2 and S3 share the same underlying implementations.

Executed in `gateC_4sys_v2` (real calls):

| case | S2 tool(s) | status | has_data | provenance |
|---|---|---|---|---|
| DESIGN-12 | resolve_target, inspect_smiles | ok, ok | yes, yes | yes, yes |
| DISCOVER-08 | resolve_target | ok | yes | yes |
| KNOW-01 | resolve_target | ok | yes | yes |
| REASON-02 | resolve_target, predict_cooperativity | ok, error | yes, no | yes, no |

Legitimate outcomes are distinct: `ok+has_data` (success), `ok+empty`
(empty-but-ok), typed failure (`MISSING_SCIENTIFIC_INPUT`), `error` (infra/tool).

## 3. S3 abstention diagnosis (v2)

| task | provided | required | code | classification |
|---|---|---|---|---|
| REASON-02 | BRD4 BD2+VHL, PEG3 | warhead/linker/e3/pose | `MissingScientificInput` | **appropriate** (matches declared abstention) |
| DISCOVER-08 | placeholder text, no candidate data | candidate list+costs | `clarification_required` | **case under-specified → appropriate** |
| DESIGN-12 | warhead + principle | E3 ligand | `clarification_required` (v1) / answered (v2) | policy-consistent; v1→v2 flip is **run-to-run non-determinism** in the LLM agent (see §6) |

No gate was weakened. Paired development check added (sufficient → no abstention;
withheld → typed abstention) and frozen in tests.

## 4. Source-backed design — corrected

- **Unique structures:** 28 raw records → **13 unique constitutional graphs**
  (28 unique isomeric). Not 28/30 novel molecules.
- **Reference:** dBET1 (BRD4–CRBN, DOI `10.1126/science.aab1433`), not MZ1; id
  corrected to `SGA-VERIFIED-dBET1`. Detail:
  `outputs/execution/next_phase/source_backed_design_correction.md`.
- **Controls:** valid dBET1 reconstruction passes the gate; placeholder provenance
  fails it. Ternary/synthesis remain `unevaluated`; no bioactivity/DC50 claim.

## 5. Gold integrity + human review

- Synthetic kappa quarantined (regenerated honest); `consensus.approved=false`,
  `gold={}`; scoring blocked while any case is pending.
- Handoff package: `outputs/execution/next_phase/gold_review_handoff/` (README,
  RUBRIC, tooling, 48-case vs 29-decision reconciliation).
- **Unresolved human decisions:** all 48 `gold_review.tsv` rows and all 29
  `REVIEWER_DECISIONS.tsv` rows are pending.

## 6. New freeze + Gate-C v2 metrics

`study/freeze_manifest_v2.json` (commit, dirty hash, prompts, hashes, parity,
telemetry, budgets; no secrets).

| system | n | answered | abstained | errored | tokens (in/out) | cost | cost avail | mean lat |
|---|---:|---:|---:|---:|---|---:|---|---:|
| S1 | 4 | 4 | 0 | 0 | reported | $0.0019 | yes | 13.6 s |
| S2 | 4 | 3 | 1 | 0 | reported | $0.0040 | yes | 5.9 s |
| S3 | 4 | 2 | 2 | 0 | reported | $0.0027 | yes | 2.9 s |
| S4 | 4 | 3 | 1 | 0 | **unavailable** | **unavailable** | **no** | 162.1 s |

REASON-02 declared abstention: **S2 and S3 abstained (met)**; S1, S4 answered.
KNOW-01: all four met. Correctness: **NOT SCORED** (gold pending).
**Non-determinism:** S3 DESIGN-12 answered in v2 but abstained in v1 at
temperature 0 — cross-provider variance must be quantified before inference.

## 7. Pilot prerequisites

| prerequisite | status |
|---|---|
| S2 tool execution usable | **PASS** |
| S3 abstentions explained | **PASS** |
| Source-backed design correctly labelled | **PASS** |
| Gold contamination cannot approve | **PASS** |
| Reviewer handoff package ready | **PASS** |
| **Eligible adjudicated gold (subset)** | **BLOCKED (human)** |
| **Reviewer decisions RD-01…RD-29** | **BLOCKED (human)** |
| Resource matching S2↔S3 | **PASS** (documented parity) |
| Resource matching S4 | **FAIL / declared** (native-only) |
| Telemetry complete | **PASS with declared gap** (S4 cost unavailable) |
| Reproducibility (run-to-run variance) | **BLOCKED** (v1/v2 flip at temp 0) |
| Configured budget cap for 360 runs | **BLOCKED** (not set) |

## 8. Next action

**Human input required (blocks scoring/pilot):** reviewers complete
`reviewer_1.csv` / `reviewer_2.csv` (48 cases) and resolve
`REVIEWER_DECISIONS.tsv` (29 rows); then
`python scripts/gold_adjudication.py merge --dir benchmark/gateC/reviewed_gold`.

**Independent next engineering (does not need gold):** quantify run-to-run
variance (3 replicates of the 4 cases) to decide whether the S3 DESIGN-12 flip is
provider noise; then set the 360-run budget cap. Launch only after the above:

```bash
python scripts/gateC_four_system.py --systems S1,S2,S3,S4 --online \
  --replicates 3 --run-id pilot_30x4x3   # requires the frozen 30-task list + budget cap
```

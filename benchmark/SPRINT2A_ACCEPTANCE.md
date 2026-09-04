# Sprint 2A — Acceptance & Freeze

Status: **ACCEPTED and FROZEN** (cases and ground truth immutable).

- 48 blinded cases: `benchmark/cases/*.json` (SHA-256 in `FREEZE_MANIFEST.json`)
- 48 frozen ground-truth records: `benchmark/ground_truth/*.json`
- Support files frozen: `benchmark_manifest.csv`, `BENCHMARK_PROTOCOL.md`,
  `BLINDNESS_RULES.md`, `SCORING_RUBRIC.md`
- Freeze manifest: `benchmark/FREEZE_MANIFEST.json`
- Audit: `benchmark/SPRINT2_CASE_AUDIT.md` (48 READY · 0 PARTIAL · 0 REJECT)
- Fail-closed: benchmark execution refuses to start when any frozen hash
  changes (see `benchmark_runner/freeze.py::assert_frozen`).

Counts in freeze manifest:
- cases: 48
- ground_truth: 48
- total frozen entries: 100

Authoring frozen at: 2026-09-04T14:53:18.684630+00:00

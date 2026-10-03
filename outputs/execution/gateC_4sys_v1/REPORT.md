# Gate-C four-system pilot — gateC_4sys_v1

Execution/validation evidence only. **No correctness score** — eligible gold is `PENDING_INDEPENDENT_REVIEW`.

- git: `71624fa6d` (dirty=yes)
- online retrieval: True
- rows: 16

## Outcomes by system

| system | n | answered | abstained | errored | timed_out | unavailable | cost USD | mean latency s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| S1 | 4 | 4 | 0 | 0 | 0 | 0 | 0.001703 | 12.316 |
| S2 | 4 | 4 | 0 | 0 | 0 | 0 | 0.002575 | 6.337 |
| S3 | 4 | 1 | 3 | 0 | 0 | 0 | 0.002415 | 1.137 |
| S4 | 4 | 3 | 1 | 0 | 0 | 0 | 0 | 171.148 |

## Per-run

| system | task | outcome | behavior_met | tool_calls | latency s | attempts |
|---|---|---|---|---:|---:|---:|
| S1 | DESIGN-12 | answered | None | 4 | 15.93 | 1 |
| S1 | DISCOVER-08 | answered | None | 4 | 9.618 | 1 |
| S1 | KNOW-01 | answered | True | 4 | 13.25 | 1 |
| S1 | REASON-02 | answered | False | 4 | 10.468 | 1 |
| S2 | DESIGN-12 | answered | None | 1 | 9.594 | 1 |
| S2 | DISCOVER-08 | answered | None | 0 | 2.911 | 1 |
| S2 | KNOW-01 | answered | True | 1 | 5.272 | 1 |
| S2 | REASON-02 | answered | False | 1 | 7.572 | 1 |
| S3 | DESIGN-12 | abstained | None | 0 | 0.0 | 1 |
| S3 | DISCOVER-08 | abstained | None | 0 | 0.0 | 1 |
| S3 | KNOW-01 | answered | True | 1 | 4.547 | 1 |
| S3 | REASON-02 | abstained | True | 0 | 0.0 | 1 |
| S4 | DESIGN-12 | answered | None | 7 | 102.154 | 1 |
| S4 | DISCOVER-08 | abstained | None | 25 | 423.42 | 1 |
| S4 | KNOW-01 | answered | True | 6 | 20.734 | 1 |
| S4 | REASON-02 | answered | False | 7 | 138.282 | 1 |

## Not established by this run

- Correctness/accuracy (gold pending).
- Superiority of any system (4-case smoke, not a powered study).
- Scientific validity of any answer.
- S4 resource-matching to S1–S3 (declared difference: Biomni uses native tools/data lake).

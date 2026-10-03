# Gate-C four-system pilot — gateC_4sys_v2

Execution/validation evidence only. **No correctness score** — eligible gold is `PENDING_INDEPENDENT_REVIEW`.

- git: `6780a40ce` (dirty=yes)
- online retrieval: True
- rows: 16

## Outcomes by system

| system | n | answered | abstained | errored | timed_out | unavailable | cost USD | mean latency s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| S1 | 4 | 4 | 0 | 0 | 0 | 0 | 0.001921 | 13.556 |
| S2 | 4 | 3 | 1 | 0 | 0 | 0 | 0.004007 | 5.903 |
| S3 | 4 | 2 | 2 | 0 | 0 | 0 | 0.002658 | 2.854 |
| S4 | 4 | 3 | 1 | 0 | 0 | 0 | 0 | 162.08 |

## Per-run

| system | task | outcome | behavior_met | tool_calls | latency s | attempts |
|---|---|---|---|---:|---:|---:|
| S1 | DESIGN-12 | answered | None | 4 | 13.216 | 1 |
| S1 | DISCOVER-08 | answered | None | 4 | 13.366 | 1 |
| S1 | KNOW-01 | answered | True | 4 | 18.502 | 1 |
| S1 | REASON-02 | answered | False | 4 | 9.142 | 1 |
| S2 | DESIGN-12 | answered | None | 2 | 3.741 | 1 |
| S2 | DISCOVER-08 | answered | None | 1 | 9.131 | 1 |
| S2 | KNOW-01 | answered | True | 1 | 6.196 | 1 |
| S2 | REASON-02 | abstained | True | 1 | 4.545 | 1 |
| S3 | DESIGN-12 | answered | None | 0 | 6.979 | 1 |
| S3 | DISCOVER-08 | abstained | None | 0 | 0.0 | 1 |
| S3 | KNOW-01 | answered | True | 1 | 4.436 | 1 |
| S3 | REASON-02 | abstained | True | 0 | 0.0 | 1 |
| S4 | DESIGN-12 | answered | None | 15 | 353.261 | 1 |
| S4 | DISCOVER-08 | abstained | None | 24 | 123.806 | 1 |
| S4 | KNOW-01 | answered | True | 4 | 20.086 | 1 |
| S4 | REASON-02 | answered | False | 20 | 151.166 | 1 |

## Not established by this run

- Correctness/accuracy (gold pending).
- Superiority of any system (4-case smoke, not a powered study).
- Scientific validity of any answer.
- S4 resource-matching to S1–S3 (declared difference: Biomni uses native tools/data lake).

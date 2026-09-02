# CooperativityPredictionAgent

| Field | Value |
| --- | --- |
| **Node** | 26 - `predict_cooperativity` |
| **Source** | `synglue_agent/agents/cooperativity_agent.py` |
| **Toolbox methods** | `predict_cooperativity` |
| **Status** | Proxy implemented |

## Purpose

Scores whether the target-PROTAC-E3 ternary arrangement is likely to be cooperative, neutral, or anti-cooperative.

## Reads

- `state.valid_candidates`
- `state.ternary_feasibility_results`

## Writes

- `state.cooperativity_predictions`

## Logic

Combines ternary plausibility, linker reachability, interface-contact proxy, lysine geometry, and linker strain into a proxy `predicted_alpha` and normalized cooperativity score.

## Caveat

This is not measured cooperativity. Ranking records add `proxy_cooperativity_not_measured_alpha` until alpha is measured or a calibrated cooperativity model is connected.

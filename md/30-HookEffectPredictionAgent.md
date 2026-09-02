# HookEffectPredictionAgent

| Field | Value |
| --- | --- |
| **Node** | 27 - `predict_hook_effect` |
| **Source** | `synglue_agent/agents/cooperativity_agent.py` |
| **Toolbox methods** | `predict_hook_effect` |
| **Status** | Proxy implemented |

## Purpose

Models concentration-dependent ternary complex formation so high-dose hook-effect risk is visible before final ranking.

## Reads

- `state.valid_candidates`
- `state.degradation_predictions`
- `state.cooperativity_predictions`
- `state.e3_context_predictions`

## Writes

- `state.hook_effect_predictions`

## Logic

Evaluates a concentration grid, estimates ternary fraction, identifies peak ternary concentration, compares high-concentration occupancy against peak occupancy, and assigns a hook-risk label plus therapeutic-window score.

## Caveat

Occupancy parameters are priors. Ranking records add `proxy_hook_model_not_fitted_to_dose_response` until cellular dose-response and hook measurements are supplied.

# CheapFilterAgent

| Field | Value |
| --- | --- |
| **Node** | 18 - `cheap_filter_candidates` |
| **Source** | `synglue_agent/agents/search_control_agent.py` |
| **Toolbox methods** | `cheap_filter_candidates`, `filter_prediction_records` |
| **Status** | Implemented |

## Purpose

Removes bad candidates before costly biological or structural scoring. This is the main "cheap filters first" gate.

## Reads

- `state.valid_candidates`
- `state.admet_predictions`
- `state.novelty_results`
- `state.applicability_domain_results`
- `state.e3_context_predictions`
- `state.search_policy.cheap_filter_budget`

## Writes

- `state.valid_candidates`
- filtered ADMET, novelty, applicability-domain, and E3-context records
- `state.cheap_filter_summary`
- `state.errors` if no candidate survives

## Logic

Rejects or downselects by RDKit validity, molecular weight, TPSA, rotatable bonds, synthesis score, novelty, ADMET risk, applicability-domain score, and E3/cell context.

## Caveat

The filter is intentionally conservative and deterministic. It should be calibrated against real failure modes as assay feedback accumulates.

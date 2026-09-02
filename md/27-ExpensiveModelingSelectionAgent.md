# ExpensiveModelingSelectionAgent

| Field | Value |
| --- | --- |
| **Node** | 24 - `select_expensive_modeling_finalists` |
| **Source** | `synglue_agent/agents/search_control_agent.py` |
| **Toolbox methods** | `select_expensive_modeling_finalists` |
| **Status** | Implemented |

## Purpose

Chooses a small finalist set for ternary modeling, docking, P4ward, or future expensive engines.

## Reads

- `state.valid_candidates`
- `state.ranking_results`
- `state.search_policy.expensive_modeling_budget`

## Writes

- `state.expensive_modeling_candidate_ids`
- candidate provenance flag `selected_for_expensive_modeling`

## Logic

Uses ranking first, then keeps the selected set bounded to the expensive-modeling budget. Downstream ternary scoring only consumes these finalist IDs.

## Caveat

This is an allocation decision, not a biological conclusion. Candidates not selected for expensive modeling are flagged in ranking uncertainty.

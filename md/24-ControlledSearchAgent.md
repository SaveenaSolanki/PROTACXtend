# ControlledSearchAgent

| Field | Value |
| --- | --- |
| **Node** | 3 - `control_np_hard_search` |
| **Source** | `synglue_agent/agents/search_control_agent.py` |
| **Toolbox methods** | `build_search_policy` |
| **Status** | Implemented |

## Purpose

Prevents NP-hard blow-up by creating a bounded `SearchPolicy` before linker generation, stereochemistry expansion, construction, filtering, and ternary modeling.

## Reads

- `state.parsed_objective.candidate_count`
- `state.parsed_objective.e3_ligase`

## Writes

- `state.search_policy`
- `state.design_plan["search_policy"]`

## Logic

- caps final candidates at 500;
- caps construction at 1000;
- caps expensive modeling at 10-50 candidates;
- caps linker generation at 12-64 linkers;
- sets stereoisomer expansion to a small per-candidate budget.

## Caveat

This is a search-control policy, not a proof of optimality. It deliberately chooses a controlled design subset instead of enumerating every linker, E3 ligand, exit vector, and stereoisomer.

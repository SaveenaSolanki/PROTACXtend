# ActiveLearningAgent

| Field | Value |
| --- | --- |
| **Node** | 29 - `active_learning_update` |
| **Source** | `synglue_agent/agents/active_learning_agent.py` |
| **Toolbox methods** | `update_active_learning_from_feedback` |
| **Tool files** | `synglue_agent/tools/assay_feedback.py`, `synglue_agent/tools/learning_memory.py` |
| **Status** | Feedback ingestion implemented; retraining gate only |

## Purpose

Closes the wet-lab loop by converting assay outcomes into durable training rows and memory entries.

## Reads

- `state.assay_feedback`
- `state.valid_candidates`

## Writes

- `state.active_learning_update`
- `synglue_agent/data/assay_feedback_training.csv` when feedback is supplied
- learning-memory entries for supplied feedback

## Logic

Stores candidate ID, target, E3, cell line, SMILES, measured DC50, measured Dmax, measured hook concentration, degradation outcome, source, notes, and timestamp. It reports whether the dataset is still too small, ready for calibration, or ready for full retraining.

## Caveat

This does not train or register a production model yet. It creates the assay-feedback substrate and an honest retraining recommendation.

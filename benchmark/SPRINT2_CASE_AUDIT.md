# Sprint 2A — Case & Ground-Truth Authoring Audit

Authoring complete: **48 cases + 48 frozen ground-truth records**. No runners, no executions.
All tasks audited: **READY 48 · PARTIAL 0 · REJECT 0** (post-review reclassification and relabelling).
| task_id | capability | difficulty | ground_truth_type | contamination | status |
|---|---|---|---|---|---|
| DESIGN-01 | DESIGN | medium | design_rubric | low | READY |
| DESIGN-02 | DESIGN | medium | design_rubric | low | READY |
| DESIGN-03 | DESIGN | hard | design_rubric | medium | READY |
| DESIGN-04 | DESIGN | hard | design_rubric | low | READY |
| DESIGN-05 | DESIGN | medium | design_rubric | low | READY |
| DESIGN-06 | DESIGN | hard | design_rubric | low | READY |
| DESIGN-07 | DESIGN | hard | design_rubric | low | READY |
| DESIGN-08 | DESIGN | hard | design_rubric | medium | READY |
| DESIGN-09 | DESIGN | medium | design_rubric | low | READY |
| DESIGN-10 | DESIGN | hard | design_rubric | medium | READY |
| DESIGN-11 | DESIGN | medium | design_rubric | medium | READY |
| DESIGN-12 | DESIGN | medium | design_rubric | low | READY |
| DISCOVER-01 | DISCOVER | hard | ranked | low | READY |
| DISCOVER-02 | DISCOVER | hard | design_rubric | medium | READY |
| DISCOVER-03 | DISCOVER | hard | design_rubric | low | READY |
| DISCOVER-04 | DISCOVER | hard | ranked | low | READY |
| DISCOVER-05 | DISCOVER | hard | design_rubric | low | READY |
| DISCOVER-06 | DISCOVER | medium | design_rubric | medium | READY |
| DISCOVER-07 | DISCOVER | hard | design_rubric | low | READY |
| DISCOVER-08 | DISCOVER | hard | ranked | low | READY |
| DISCOVER-09 | DISCOVER | medium | design_rubric | low | READY |
| DISCOVER-10 | DISCOVER | hard | design_rubric | low | READY |
| DISCOVER-11 | DISCOVER | medium | ranked | low | READY |
| DISCOVER-12 | DISCOVER | hard | design_rubric | medium | READY |
| KNOW-01 | KNOW | easy | exact | low | READY |
| KNOW-02 | KNOW | easy | categorical | medium | READY |
| KNOW-03 | KNOW | medium | exact | medium | READY |
| KNOW-04 | KNOW | medium | categorical | medium | READY |
| KNOW-05 | KNOW | medium | categorical | low | READY |
| KNOW-06 | KNOW | easy | categorical | medium | READY |
| KNOW-07 | KNOW | medium | exact | medium | READY |
| KNOW-08 | KNOW | medium | categorical | low | READY |
| KNOW-09 | KNOW | easy | exact | low | READY |
| KNOW-10 | KNOW | medium | categorical | medium | READY |
| KNOW-11 | KNOW | medium | exact | low | READY |
| KNOW-12 | KNOW | hard | categorical | medium | READY |
| REASON-01 | REASON | hard | mechanistic_rubric | medium | READY |
| REASON-02 | REASON | hard | mechanistic_rubric | medium | READY |
| REASON-03 | REASON | easy | categorical | low | READY |
| REASON-04 | REASON | hard | mechanistic_rubric | medium | READY |
| REASON-05 | REASON | medium | categorical | low | READY |
| REASON-06 | REASON | hard | mechanistic_rubric | medium | READY |
| REASON-07 | REASON | hard | categorical | low | READY |
| REASON-08 | REASON | medium | mechanistic_rubric | medium | READY |
| REASON-09 | REASON | hard | mechanistic_rubric | medium | READY |
| REASON-10 | REASON | medium | mechanistic_rubric | low | READY |
| REASON-11 | REASON | hard | mechanistic_rubric | medium | READY |
| REASON-12 | REASON | hard | mechanistic_rubric | medium | READY |

## Summary counts
- by capability: {'DESIGN': 12, 'DISCOVER': 12, 'KNOW': 12, 'REASON': 12}
- by difficulty: {'medium': 19, 'hard': 24, 'easy': 5}
- by ground-truth type: {'design_rubric': 20, 'ranked': 4, 'exact': 5, 'categorical': 10, 'mechanistic_rubric': 9}
- by contamination risk: {'low': 26, 'medium': 22}

## Quality checks (48/48)
- answer leakage: none — expected answers live only under ground_truth/, case files carry `expected_answer: null`.
- ambiguous ground truth: none — every record has `type`, `expected_answer`, `mandatory_answer_elements`.
- unsupported expected answers: none — deterministic anchors computed with RDKit; categorical answers cite canonical public sources/repo; rubrics are expert-graded by design.
- duplicated tasks: none (all task_ids unique; capability content distinct).
- unequal capability difficulty: balanced 12 per capability; difficulty spreads easy 5 / medium 19 / hard 24.
- inaccessible proprietary data: none — inputs are self-contained (SMILES, features, canonical public references).
- benchmark contamination: managed via BLINDNESS_RULES (six-BRD4 potency excluded; ground truth not model-visible).
- scoring ambiguity: automatic fields + expert fields separated per SCORING_RUBRIC; rubrics list mandatory elements.

Frozen. Sprint 2A STOP: no runners, no PROTACXtend/Biomni/AI-Co-Scientist/DeepSeek/Ollama/base-LLM executions.

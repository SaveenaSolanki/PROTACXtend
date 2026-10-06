# Pinned agent trace — design_20261006T065125Z

- git commit: `cb79b188e`
- mode: scientific
- model: deepseek-v4-flash
- generated: 2026-10-06T06:53:42.140995+00:00
- schema: `protacxtend.agent_trace.v1`

| seq | type | role | action | status | evidence_kind | observation |
|---:|---|---|---|---|---|---|
| 2 | step | target_agent | target_resolution | executed | computed | target resolved |
| 3 | step | evidence_agent | binder_retrieval | executed | computed | 100 binders |
| 4 | step | component_agent | warhead_selection | executed | computed | 1 warheads |
| 5 | step | component_agent | e3_selection | executed | computed | 1 E3 ligands |
| 6 | step | design_agent | linker_generation | executed | computed | 17 linkers |
| 7 | step | design_agent | construction | executed | computed | 38 assembled |
| 8 | step | chemistry_critic | validation | executed | computed | 30 valid |
| 9 | step | prediction_agent | degradation_prediction | executed | computed | 30 predictions |
| 10 | step | prediction_agent | admet_prediction | executed | computed | 30 records |
| 11 | step | ranking_agent | ranking | executed | computed | ranked candidates |
| 12 | step | structure_agent | ternary_coordinates | unevaluated | unevaluated | No validated ternary-coordinate backend/DockQ benchmark is available for this run. |
| 13 | step | synthesis_agent | synthesis_route | unevaluated | unevaluated | Retrosynthetic routes were not executed; synthetic feasibility remains a proxy/gate. |
| 14 | gate | critic | identity_assembly | passed | gate_decision | Only candidates passing source-component identity and atom-mapped assembly gates may enter prediction, ranking, or nomin |
| 15 | gate | critic | non_protac_rejection | passed | gate_decision | Only identity-gated valid PROTAC candidates may enter degradation or ADMET scoring. |
| 16 | gate | critic | degradation | predicted | gate_decision | ML prediction only; cannot be observed without published/wet-lab assay source. |
| 17 | gate | critic | ternary_coordinates | unevaluated | gate_decision | No validated coordinate backend/DockQ benchmark available in this run. |
| 18 | gate | critic | synthesis_route | unevaluated | gate_decision | No retrosynthetic route execution; no route claim is nominated. |
| 19 | gate | critic | nomination | gated | gate_decision | Candidates may be prioritized for review only after identity/assembly gates pass; no validated degrader nomination is al |
| 20 | routing_decision | critic | separate_exploratory_candidates | applied | evidence_driven_routing | 28 candidate(s) with generated/demo provenance were routed out of the scientific payload into the exploratory design bri |
| 21 | terminal | supervisor | None | None | None |  |

## Terminal

- reason: **valid_candidate**
- justified_abstention: None
- source_backed_candidates: 2
- exploratory_candidates: 28
- payload_scan: clean (scientific payload carries no demo/synthetic provenance)

## Interpretation

The DESIGN route is a **fixed workflow**; the evidence-driven behaviour it
demonstrates is the identity-gate decision that routes generated/demo-provenance
candidates out of the scientific payload. It is **not** yet a free adaptive
action-selection trace. The abstention trace demonstrates a typed, justified
abstention when a required scientific input is absent.

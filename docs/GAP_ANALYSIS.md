# GAP ANALYSIS — true gaps only (2026-09-02 audit)

Rules applied: no gap proposed for a capability that already exists; BUILD
only where genuinely absent; backend availability noted. Machine-readable:
`artifacts/gap_matrix.csv`. Priorities: P0 blocks scientific validity,
P1 important platform capability, P2 improvement, P3 optional.

## P0 — blocks scientific validity
| ID | Gap | Why it matters | Backend exists? | Action | Notes |
|---|---|---|---|---|---|
| GAP01 | **Prospective validation** of degradation (pDC50/Dmax), E3 retrieval, cell-context claims | every ML claim is retrospective (absence-of-record negatives, known-usage retrieval) | wet-lab / PDX / literature prospective sets | VALIDATE | needed before "prospective discovery/efficacy" wording anywhere |
| GAP02 | **Unified claims registry + status sync** | per-module CLAIMS.md (M6) + website audit exist, but `config/scientific_status.yaml` is stale (M6=PLANNED); no machine cross-check | internal docs/config | CONNECT | add a verify script (pattern: scripts/audit_md_vs_code.py) |
| GAP03 | **Real ternary evidence in the design loop** | ranking (M6) returns structural_feasibility=None for all pairs; degradation claims never see real ternary geometry | P4ward (docker) + SE3-protacs clones | CONNECT | needs docker CI or a validated cached ternary benchmark |

## P1 — important platform capability
| ID | Gap | Why | Backend? | Action | Notes |
|---|---|---|---|---|---|
| GAP04 | Proteomics + broader cell context (M5) | proteotype claim impossible; unmapped lines return None | DepMap proteomics / user data | UPGRADE | leg E; unseen-cell transfer work |
| GAP05 | Selectivity / neosubstrate / off-target degradation risk | K axes are heuristic; no degradome model | none (literature datasets) | BUILD (after M4/5 claim freeze) | paralog + degradome validation |
| GAP06 | Permeability / intracellular exposure (3D PSA, IMHB, P-gp/BCRP) | only 2D rules | OpenADMET-style/ADMET-AI subset | INTEGRATE | PK-correlation validation |
| GAP07 | Metabolic stability/CYP beyond AMES/DILI/hERG | incomplete ADME story | ADMET-AI subset / admetSAR | INTEGRATE | venv endpoint expansion |
| GAP08 | Active learning scientific module (M7) + feedback loop | agent layer only; no experiment-selection engine | internal | BUILD (post-audit) | from agent + M1–M6 scorers |
| GAP09 | Dual-graph consistency (31-node chain vs 17-node LangGraph) | divergent node sets; exit_vector node is a stub in real_nodes | internal | CONNECT | parity tests + wire stub |

## P2 — improvement
| ID | Gap | Backend? | Action | Notes |
|---|---|---|---|---|
| GAP10 | Synthetic-accessibility scoring of constructed candidates | AiZynth/ASKCOS | INTEGRATE | optional route check per candidate |
| GAP11 | Official Link-INVENT (or equivalent) as optional backend | package available | INTEGRATE (optional) | parity benchmark vs internal scorer |
| GAP12 | Ternary/docking not in default CI | docker | CONNECT | env-gated job |
| GAP13 | 30+ cloned repos lack a runtime-wiring + benchmark census | clones exist | CONNECT | per-repo adapter smoke (partially: install verification CSVs) |
| GAP15 | Client/lookup duplication consolidation + offline cache | internal | REMOVE_DUPLICATE | one canonical client per source |

## P3 — optional / deferred
| ID | Gap | Backend? | Action | Notes |
|---|---|---|---|---|
| GAP14 | PK/PBPK/exposure + in vivo translation | OSP etc. | DEFER | post case studies |
| — | Rosetta/MegaDock/COMPASS/Boltz integration | not present | DEFER | only if a real ternary benchmark justifies it |
| — | IP/patent search | — | DEFER | not platform scope |

**Not gaps** (already exist — do not rebuild): linker generation (char-GRU +
scoring), PROTAC assembly, degradation prediction (chemprop + M4/M5),
E3 ranking (M6), retrosynthesis engines (ASKCOS/AiZynth optional), deep
research, Pareto ranking, novelty checking, hook/cooperativity/lysine modules.

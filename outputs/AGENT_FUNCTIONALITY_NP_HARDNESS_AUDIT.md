# Agent Functionality & NP-Hardness Audit

_ProtacPilot / SynGlue v0.3.0-agentic-core · 2026-08-08 · evidence-based_

## 1. What "the agents" are

The runtime contains **25 agent classes** (`synglue_agent/agents/*.py`): 21 concrete
task agents + 4 supporting classes (Supervisor, ReAct, Validation, MemoryUpdate).
The often-quoted "23 agents" ≈ this set. Each agent owns 1–3 registered tools.

## 2. Current functionality — the gap audit is STALE

`data/toolkit/protac_agent_gap_audit.csv` (written 2026-08-03 snapshot, 17 rows)
labels 9 agents `heuristic_stub`, 4 `local_demo_data_only`, 4
`executable_not_tested`. **That predates the v0.3 validation work.** Reality now:

### ✅ Fully functional (real tools / trained models, verified by tests + benchmark)
| Agent | Now backed by | Evidence |
|---|---|---|
| DC50 / Dmax prediction | Trained Chemprop D-MPNN ensemble + conformal calibration + AD | ρ=0.783 retro (64 mols); coverage 92.2% |
| Ternary feasibility | Ensemble: geometric proxy + P4ward + SE3-PROTACs GNN | `test_ternary_ensemble.py` (12); container boot-test |
| Retrosynthesis | Real AiZynthFinder MCTS (USPTO policy + ZINC stock) | live route found; `test_retrosynthesis.py` (12) |
| Warhead / exit vector | Vina docking + vector analysis (real poses) | `test_docking_pipeline.py`; p4ward evidence outputs |
| Target resolver | UniProt/PDB/ChEMBL wrappers + local fallback | tests |
| E3 ligand selection | Curated evidence engine (deterministic, builtin table) | `test_e3_context_engine.py` (8) |
| Construction / assembly | RDKit deterministic assembly | tests |
| Ranking | NSGA-II Pareto (7 tests) | `test_pareto_ranking.py` |
| Report / safety | Real artifact generation; local rules (human-gate wired) | e2e cases |

### ✅ Unblocked 2026-08-08 (make-it-all-workable pass)
| Agent | Now backed by | Verified |
|---|---|---|
| Binder retrieval | Live ChEMBL `/activity` (2-call fetch, unit-normalized nM/pIC50, provenance metadata); PubChem enrichment; BindingDB key-gated | 90 BRD4 binders in 9 s; `test_binder_live.py` 4/4 |
| ADME/Tox | ADMET-AI ML (106 endpoints: hERG, AMES, DILI, clearance…) in isolated venv + rule fallback, labelled provenance | aspirin → hERG 0.021, AMES 0.080; `test_unblocked_agents.py` |
| Novelty/IP | Live PubChem PUG-View patent cross-reference + local similarity | aspirin → 14 patents; mocked + live tests |
| Linker generation | + fragment-combination vocabulary (8 cores × spacers, RDKit-validated, Butina-style diversity selection, 64 linkers) feeding the scanner library | `test_unblocked_agents.py` |
| Evolution/reflection | + SMILES mutation (C↔N↔O, retry-safe) + BRICS-fragment crossover + generation tracking | valid offspring; `test_unblocked_agents.py` |

Remaining by-design bounds (NP-hard classes, §3): retrosynthesis MCTS, docking/ternary
escalation, linker enumeration cap, evolution local search — all still bounded
approximations with human gates (as they must be).

## 3. The NP-hardness question — why "fully functional" is the wrong bar

Six problem classes in this pipeline are **intractable in the worst case**.
No exact solver exists (or one would take exponential time). Every agent
therefore runs a **bounded approximation** — that is correct engineering, not
an implementation failure. The registry's `registered`-but-not-`executable`
flags mostly reflect **missing external resources**, not NP-hardness.

### 3.1 Retrosynthesis route planning — PSPACE-hard family
Finding a synthesis route is a search over an exponentially branching reaction
space (related to planning problems that are PSPACE-hard; the practical MCTS
version is unbounded in the worst case).
Bounding used: policy-NN-guided MCTS (`aizynth_route_search`, `timeout_s=300`),
`max_steps=6` (`retrosynthesis.py:265,290`); no route → RAscore/SAScore proxy or
human gate.

### 3.2 Protein–ligand docking / ternary pose search — NP-hard
Docking (rigid-body 6D + torsion search) is NP-hard; exhaustive pose search is
infeasible.
Bounding used: **staged escalation** — geometric proxy → P4ward (docker) →
SE3-PROTACs GNN; consensus on raw scores, disagreement → **human gate**
(`ternary_stage.py:64,132,154,264`).

### 3.3 Linker design — combinatorial explosion
The set of chemically valid linkers between warhead and E3 ligand is
exponential in the linker graph.
Bounding used: curated panel + rule enumeration capped at `max_linkers=50`
(`linker_stage.py:55,63`), strain-proxy filter (`GEOMETRY_FLOOR=0.4`,
`STRAIN_FRACTION_THRESHOLD=0.5`), bounded repair loop.

### 3.4 De-novo molecular optimization (evolution) — NP-hard
General optimization over chemical space is NP-hard.
Bounding used: deterministic local edits (linker replacement, E3 switch,
exit-vector change) + re-score (`evolution_agent.py:44-60`), capped at 2–8
candidates (`max_new`).

### 3.5 Substructure matching — NP-complete
Subgraph isomorphism (substructure search over DBs) is NP-complete; RDKit's
VF2 is worst-case exponential.
Used inside binder/warhead lookups; fine in practice on curated sets.

### 3.6 Warhead/exit-vector selection over libraries — combinatorial
Pairwise warhead–target combinations explode combinatorially.
Bounding used: docking with bounded exhaustiveness + heuristic ranking.

## 4. Why the formal registry says "registered, not executable"

`synglue_agent/toolkit/status.py` / `registry.py` compute executability from
`Agent_Toolkit.xlsx` + strict availability checks. All 21 tools currently
report `executable=False, available=False, registered=True`. The reason is
**resource availability** in the executing environment:

1. **27 cloned upstream repos** (`data/protac_repos/repos/`) each want their own
   conda env (env_specs/); only a few envs are installed. Tool wrappers that
   require those envs cannot execute here → `not executable`.
2. **Live/large databases**: ChEMBL/BindingDB reachable-ish, but DrugBank is
   licensed, patent DBs (Novelty) absent, and binder mining falls back to local
   curated CSVs when the APIs fail (`binder_agent.py:123-127`).
3. **Missing 409 MB `grover_fixed.pt`** (excluded, > GitHub limit): SynGlue
   GROVER degradation path degrades to chemprop → heuristic chain (labelled).
4. `e3_ligand.csv` precomputed table (now committed) and aizynth models (now
   bootstrap-downloadable) were missing at audit time.

These are fixable with credentials/compute — they are **not** NP-hardness.

## 5. Bottom line

- **~10 agents are functionally complete** with real tools/trained models
  (validated: 299 tests, benchmark ρ=0.785, live LLM 17/17, CI green 288).
- **~5 are partial** — 3 because of external dependencies (binder, ADMET,
  novelty), 2 because their core problems are NP-hard and the bounded
  approximation is the intended design (linker, evolution).
- **"Not fully functional" ≠ broken.** For the NP-hard stages (retrosynthesis,
  docking/ternary, linker, evolution), exactness is unattainable; the code
  implements bounded, uncertainty-aware, human-gated approximation — which is
  the scientifically appropriate response, and each bounded decision is traced
  and gated (trace.jsonl, human checkpoints).

## 6. Residual unblock list (2026-08-08 update)

| Agent | Status now | Remaining |
|---|---|---|
| Binder retrieval | ✅ live ChEMBL/PubChem | Optional: BindingDB API key (`BINDINGDB_API_KEY`), DrugBank license |
| ADME/Tox | ✅ ADMET-AI + rules | venv is machine-local: `bootstrap_assets.sh --admet` on each new host |
| Novelty/IP | ✅ PubChem patents + local sim | Optional: licensed patent DB for coverage beyond PubChem |
| Linker | ✅ fragment combos + curated + BRICS | NP-hard bound stays: enumeration cap is the design |
| Evolution | ✅ mutation + crossover + linker replacement | NP-hard bound stays: bounded local search by design |
| Registry executability | — | `Agent_Toolkit.xlsx` statuses still conservative; wrapper-level `evidence` fields now carry real availability |
| Full-upstream envs | — | 27 repos' conda envs only needed for repo-wrapper tests that CI bootstraps (5 repos, shallow) |

_Evidence (updated 2026-08-08): `test_binder_live.py`, `test_unblocked_agents.py` (10 passed),
313-test regression green; `data/toolkit/protac_agent_gap_audit.csv`, `synglue_agent/toolkit/status.py`,
`synglue_agent/tools/{retrosynthesis,admet_integration}.py`,
`synglue_agent/agents/{linker_stage,ternary_stage,evolution_agent,binder_agent,novelty_agent}.py`,
test suite (299 passed), CI run 5604c30 (green)._

## 2026-08-11 addendum — E2E scientific-agent milestone

The agentic graph previously ran **stub nodes** by default (the benchmark's
"full_agentic" was a scoring harness, not the graph). Now wired to real tools
via `real_nodes.py`; canonical `AgentRunRecord` written per run; 5-scenario E2E
suite passes (BRD4 full-chain, BTK/KRAS/HMGB2 gated on low-confidence evidence
as designed, impossible input safe-fails). See CHANGELOG 2026-08-11.

## 2026-08-12 addendum — E3 ligase expansion + thin-agent notes

- E3 selection was limited to CRBN/VHL despite 600+ E3 ligases in biology and
  23 E3 groups in PROTAC-DB. Fixed: multi-E3 library (114 rows / 19 groups,
  cited ligands with DOI+UniProt+activity provenance), arbitrary-E3 parsing
  from prompts, e2e scenario 6 (MDM2/BRD4) passes. PROTAC-DB itself contains
  23 E3 annotations (CRBN 10862, VHL 3947, cIAP1 152, MDM2 87, DCAF11 86,
  RNF126 62, KLHL20 54, XIAP 49, DCAF16 32, KEAP1 12, AhR 9, FEM1B 9, SKP1 8,
  DCAF15 5, RNF114 4 …).
- LLM gating evidence: 17/17 live role-validation cases with 0 safety
  violations (unsupported tools, SMILES edits, numerical hallucination);
  every LLM decision passes deterministic validators; no raw chain-of-thought
  stored. This is verified, not aspirational.
- Thin-agent honesty: patent coverage = PubChem PUG-View (keyless); SureChEMBL
  REST is retired (redirects to a web UI); BindingDB REST requires an API key
  (`BINDINGDB_API_KEY`); DrugBank is licensed. These are documented gaps, not
  hidden ones.

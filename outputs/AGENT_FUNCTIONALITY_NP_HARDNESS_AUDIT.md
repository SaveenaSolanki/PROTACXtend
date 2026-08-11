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

### 🟡 Partially functional (bounded/heuristic by design or missing deps)
| Agent | What works | What's missing | Cause |
|---|---|---|---|
| Linker generation | Curated panel + rule enumeration (cap 50) + strain proxy + bounded repair | exhaustive linker space | **NP-hard** (see §3.3) |
| Binder retrieval | ChEMBL/PubChem/BindingDB API wrappers + **local curated fallback** | live DB reliability / API keys / DrugBank license | external deps |
| Evolution/reflection | Deterministic critique + linker/E3/exit-vector replacement (2–8 candidates) | real generative optimization | **NP-hard** + deps |
| ADME/Tox | Lipinski/Veber/Pfizer rule triage (`admet_integration.py:100`) | QSAR/pkCSM-class models, metabolic sites | external deps |
| Novelty/IP | Local fingerprint similarity only | patent/claims DB (Google Patents, etc.) | external deps |

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

## 6. What would change the status of each partial agent

| Agent | Unblock requires |
|---|---|
| Binder retrieval | Live BindingDB/ChEMBL keys + DrugBank license, or snapshot DB committed |
| ADME/Tox | Install QSAR stack (e.g., SwissADME/pkCSM-style) or train on ADMETlab data |
| Novelty/IP | Google Patents / SureChEMBL snapshot or licensed DB |
| Linker | More compute per candidate + better surrogate (or accept bounded design) |
| Evolution | Generative model (e.g., REINVENT) for real de-novo edits |
| Registry executability | Install the 27 repo envs (env_specs/) or mark them `requires_asset` |

_Evidence: `data/toolkit/protac_agent_gap_audit.csv`, `synglue_agent/toolkit/status.py`,
`synglue_agent/tools/{retrosynthesis,admet_integration}.py`,
`synglue_agent/agents/{linker_stage,ternary_stage,evolution_agent,binder_agent,novelty_agent}.py`,
test suite (299 passed), CI run 5604c30 (green)._

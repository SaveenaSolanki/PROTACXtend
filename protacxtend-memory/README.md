# PROTACpilot Cognitive Memory (`protacpilot-memory`)

**Do not build a system that remembers conversations. Build a system that
remembers what changed its scientific model of the world.**

A local-first, SQLite + FTS5 cognitive memory subsystem for autonomous PROTAC
design. It separates *episodes* from *generalized knowledge*, gates encoding by
auditable salience, computes deterministic prediction error, consolidates
repeated evidence into scope-aware semantic claims, and re-consolidates beliefs
when new evidence arrives — with full provenance and versioning.

> This is an independent subsystem. It is *inspired by* the engineering
> principles of `Gentleman-Programming/engram` but is not an Engram product and
> shares no branding. See `PROTACPILOT_COGNITIVE_MEMORY_AUDIT.md`.

## Why it is not a RAG system

```
EXPERIENCE → ATTENTION/SALIENCE → ENCODING DECISION → EPISODIC MEMORY
   → REPLAY → CONSOLIDATION → SEMANTIC KNOWLEDGE → CONTEXTUAL RETRIEVAL
   → REASONING/PREDICTION → OUTCOME → PREDICTION ERROR → RECONSOLIDATION
   → STRENGTHEN / MODIFY / BRANCH / WEAKEN / SUPERSEDE
```

Vector similarity is optional and is never allowed to decide biological
identity. Retrieval is hybrid: FTS5/BM25 + entity overlap + structured context
filters + relation-graph neighbours + transparent reranking.

## Install / run

```bash
cd protacpilot-memory
python -m pip install -e .          # optional; tests run without install via conftest.py
python -m pytest tests -q
ppmemory --help                     # CLI
ppmemory init
ppmemory doctor
```

## Benchmarks

```bash
PYTHONPATH=src python -m benchmarks.benchmark           # A–H, single system
PYTHONPATH=src python -m benchmarks.benchmark_h         # 5-way longitudinal comparison
PYTHONPATH=src python -m benchmarks.benchmark_i         # failure-feedback chain
PYTHONPATH=src python -m benchmarks.bounded_candidates  # before/after at N=10k
PYTHONPATH=src python -m benchmarks.ablation            # component ablations
PYTHONPATH=src python -m benchmarks.performance         # latency/storage sweep
```

Results are written under `benchmarks/results/` and include the generic metrics
(Recall@k, MRR, nDCG@k) plus the scientific-memory metrics (Repeated Error Rate,
Context Contamination Rate, Provenance Fidelity, Contradiction Resolution
Accuracy, Longitudinal Decision Accuracy). Cognitive memory is **not** claimed
to outperform the baselines: on Benchmark H the chunked `rag_memory` baseline
retains the best ranking, and that is reported without adjustment. Bounded
candidate generation cuts N=10,000 retrieval latency ~89% with no quality loss.
See `docs/BENCHMARKS.md` for the measured outcomes and limitations.

## Paper artifacts

```bash
PYTHONPATH=src python -m paper.build          # architecture/lifecycle/engram + tidy tables
PYTHONPATH=src python -m paper.build --run    # run benchmarks first
```

Emits `paper/output/architecture.{json,svg}`, `lifecycle.{json,svg}`,
`engram_example.{json,md}`, and tidy CSV/Parquet runs with summary and paired
statistical comparisons. See `docs/PAPER_ARTIFACTS.md`.

## Scientific evaluation

```bash
PYTHONPATH=src python -m evaluation.run       # paired tests, effect sizes, 13 figures
```

Runs the five memory systems over a population of longitudinal programmes and
produces `evaluation/output/SCIENTIFIC_RESULTS.md`, tidy CSVs and 600-DPI square
figures (Pareto, candidate reduction, contamination taxonomy, ablation, scaling,
regime, failure heatmap). Claims are tested with exact McNemar / Wilcoxon tests,
Holm correction and effect sizes. See `docs/SCIENTIFIC_EVALUATION.md`.

## Use as a library

```python
from protacpilot_memory import CognitiveMemory
from protacpilot_memory.domain.protac import ProtacContext

mem = CognitiveMemory.open()  # ~/.protacpilot-memory/memory.db
project = mem.ensure_project("brd4-vhl")
session = mem.start_session(project, goal="Improve permeability, retain degradation")
mem.remember_working(session, "current_target", "BRD4", goal_relevance=0.95)

# 1. Store a prediction BEFORE the outcome exists
pred = mem.predict(
    project_id=project, candidate_id="P17",
    prediction_type="numeric", metric="dmax",
    predicted_value=0.89, confidence=0.78, scale=1.0,
    context=ProtacContext(target_gene="BRD4", e3_ligase="VHL"),
)

# 2. Record the outcome; deterministic prediction error is computed
out = mem.record_outcome(pred.id, observed_value=0.22,
                         evidence_type="internal_experiment",
                         source_ref="EXP-119")

# 3. The outcome becomes a (high-surprise) episodic memory
res = mem.encode_outcome(out, project_id=project, session_id=session)

# 4. Consolidate repeated episodes, then retrieve / explain
mem.run_consolidation(project)
hits = mem.search("BRD4 VHL linker flexibility Dmax", project_id=project)
print(mem.render_packet(hits[0]))
```

## Host adapter (PROTACXtend)

The optional bridge `protacxtend/memory/cognitive_bridge.py` maps host
`AgentRunRecord` artifacts (objectives, evidence, candidate predictions, run
outcomes) onto the cognitive API. It degrades to a no-op when this package is
not installed, and the runtime hook is opt-in (`PROTACPILOT_COGNITIVE_MEMORY=1`,
default OFF) so frozen benchmark artifacts stay unchanged. See
`docs/HOST_BRIDGE.md` and `benchmarks/host_bridge_delta.py`.

## MCP tools

`cog_current_project`, `cog_encode`, `cog_save_episode`, `cog_search`,
`cog_recall`, `cog_get`, `cog_timeline`, `cog_neighbors`, `cog_context`,
`cog_predict`, `cog_record_outcome`, `cog_consolidate`, `cog_replay`,
`cog_compare`, `cog_judge_conflict`, `cog_reconsolidate`, `cog_strengthen`,
`cog_weaken`, `cog_archive`, `cog_future`, `cog_task_add`, `cog_task_resolve`,
`cog_procedure_save`, `cog_procedure_search`, `cog_procedure_get`,
`cog_procedure_record_run`, `cog_pattern_complete`, `cog_counterfactual`,
`cog_feedback`, `cog_end_session`, `cog_stats`, `cog_doctor`, `cog_audit`.

Run the JSON-RPC (MCP-compatible) stdio server:

```bash
ppmemory mcp
```

## Layout

```
protacpilot-memory/
├── src/protacpilot_memory/
│   ├── store/        typed persistence + universal memory trace
│   ├── cognitive/    attention, encoding, retrieval, consolidation, replay,
│   │                 reconsolidation, decay, conflict, generalization,
│   │                 pattern completion
│   ├── domain/protac/PROTAC context, fingerprints, normalization, ontology
│   ├── retrieval/    lexical, semantic (optional), graph, bounded candidates,
│   │                 rerank, progressive
│   ├── mcp/          cog_* tool registry + JSON-RPC stdio server
│   ├── server/       stdlib HTTP JSON surface
│   ├── cli/          ppmemory
│   ├── audit/        integrity & quality auditor
│   ├── confidence.py transparent evidence-confidence model
│   ├── db.py         connection + migration runner
│   └── migrations/   versioned SQL
├── tests/
├── benchmarks/       Cognitive Memory Benchmark harness
├── evaluation/       scientific evaluation (paired stats, figures, report)
├── paper/            paper artifacts (architecture, lifecycle, engram, tables)
└── docs/             architecture, memory model, neuroscience mapping, ...
```

## Documentation

- `docs/COGNITIVE_MEMORY_SYSTEM_STATUS.md` — **start here**: system overview,
  build status, verification evidence, and open work.
- `docs/MASTER_DEVELOPMENT_PROMPT.md` — the governing specification.
- `PROTACPILOT_COGNITIVE_MEMORY_AUDIT.md` — host + upstream audit.
- `docs/ARCHITECTURE.md`, `docs/MEMORY_MODEL.md`, `docs/NEUROSCIENCE_MAPPING.md`,
  `docs/PROTAC_SCHEMA.md`, `docs/RETRIEVAL.md`, `docs/CONSOLIDATION.md`,
  `docs/RECONSOLIDATION.md`, `docs/BENCHMARKS.md`, `docs/PAPER_ARTIFACTS.md`,
  `docs/SCIENTIFIC_EVALUATION.md`, `docs/MCP.md`, `docs/HOST_BRIDGE.md`.

## Scientific safety

Observations, interpretations, and generalized claims are separate records.
Semantic memory is *inferred* and *scope-bounded* — never presented as
experimentally established fact. Decay lowers retrieval priority; it never
deletes provenance.

This subsystem is a **computational engram** (an engram-like typed memory
trace). Neuroscience is architectural inspiration; no biological equivalence to
neural engrams is claimed. Benchmarks report the measured outcome, including
where a curated or RAG baseline retains better ranking.

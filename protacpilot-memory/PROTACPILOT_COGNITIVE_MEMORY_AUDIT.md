# PROTACpilot Cognitive Memory — Repository & Upstream Audit

**Artifact ID:** `PROTACPILOT_COGNITIVE_MEMORY_AUDIT`
**Subsystem:** `protacpilot-memory`
**Status:** Phase 0 (audit) — complete; Phase 1–6 implementation tracked in `docs/IMPLEMENTATION_LOG.md`
**Upstream studied:** `Gentleman-Programming/engram` (shallow clone inspected at implementation time)

> This document follows Section 59 of the Master Development Prompt. It records
> the audit *before* substantial implementation, then the adaptation decisions.
> It is a living document: the "Implementation status" column is updated as the
> subsystem is built.

---

## 1. Host repository audit — PROTACpilot / PROTACXtend

### 1.1 Identity

| Property | Finding |
|---|---|
| Repository root | `/storage/saveena/protacpilot` |
| Product name | **PROTACXtend** (this is the PROTACpilot codebase) |
| Active branch | `sprint-2` |
| License | MIT |
| Lead developer | Saveena Solanki (@SaveenaSolanki) |

### 1.2 Language & runtime

| Layer | Technology |
|---|---|
| Core runtime | **Python 3.10+** (dev env: 3.13.5) |
| Package metadata | `pyproject.toml` (setuptools), distribution `protacxtend==0.3.0` |
| CLI entry point | `PROTACXtend = protacxtend.cli:main` |
| Web app | Streamlit (`protacxtend/app/`), static site under `website/` + `site/` |
| API | FastAPI (`protacxtend/backend/`) |
| Dashboard | Textual TUI (`tui/`, Node/TS tooling under `tui/`) |
| Tests | `pytest` + `unittest`, plus `benchmark_runner/` |
| Go toolchain | **not installed / not used** — confirms the cognitive-memory subsystem must be Python |

**Decision:** implement `protacpilot-memory` in **Python**. The Master Prompt's
reference layout (`cmd/`, `internal/*.go`) is an architectural intent, not a
language mandate. Module boundaries and responsibilities are preserved 1:1
(see §6). The audit explicitly records this deviation.

### 1.3 Existing memory subsystems (integration surface)

There is **already significant, unrelated memory machinery** in the host repo.
It must not be duplicated or silently replaced; the cognitive layer is a new,
separate subsystem.

| Existing module | What it stores | Storage | Relation to new subsystem |
|---|---|---|---|
| `protacxtend/memory/run_memory.py` | Prior SynGlue run results (query, target, E3, payload) | SQLite `runs.sqlite3` + JSONL | Legacy. Candidate **episodic export** source, not a replacement. |
| `protacxtend/memory/literature_rag.py` | Literature chunks | SQLite + JSONL | Legacy lexical RAG. Could feed `evidence_items`. |
| `protacxtend/memory/vector_store.py` | BM25 / optional vector search | local | Confirms host prefers lexical-first; matches our FTS5 stance. |
| `protacxtend/memory/stores.py` | Run state, Evidence, Learning stores | JSONL | Closest philosophical relative. Explicitly "memory can suggest, never override scientific validators". Cognitive memory must respect the same hard rule. |
| `protacxtend/memory/chat_history.sqlite3` | Conversation history | SQLite | **Explicitly NOT a source of long-term scientific memory** (Master Prompt §61). |

**Key host invariant to preserve:** `stores.py` documents *"memory can suggest,
but can NEVER override scientific validators."* The cognitive layer inherits
this: semantic memories are advisory, evidence-ranked, and never authoritatively
override deterministic scientific validation.

### 1.4 Existing schemas relevant to PROTAC context

| Host schema | Relevance |
|---|---|
| `protacxtend/schemas/` (typed state, evidence, candidate provenance, tool result, memory schemas) | Source of field names for `domain/protac/context.py`. |
| `benchmark/ground_truth/*.json` (48 benchmark cases, e.g. `KNOW-01.json`) | Ready-made external evaluation corpus for cognitive benchmarks. |
| `benchmark_results/`, `outputs/case_study_brd4_vhl_result.json` | Real BRD4/VHL case-study data for longitudinal benchmarks. |
| `protacxtend/case_study/brd4_vhl_six.py` | Reference scenario reused in Benchmark H. |

### 1.5 Existing agent interfaces / MCP

- No MCP server package (`mcp`) is installed. The host exposes CLI, FastAPI, and
  Streamlit.
- `protacxtend/agentic/` contains the seven-layer agent control system
  (perception → reasoning → goal setting → decision → execution → learning →
  orchestration).
- `protacxtend/agents/graph.py` is a LangGraph workflow with deterministic
  fallback.

**Decision:** expose the cognitive layer through **all three**:
1. an importable Python API (primary, used by host agents),
2. a **JSON-RPC 2.0 MCP-compatible stdio server** (`cog_*` tools) with zero
   third-party dependencies,
3. a small stdlib **HTTP JSON server** for non-MCP agents,
plus a `ppmemory` CLI. This satisfies "agent-agnostic" and vendor-neutrality.

### 1.6 Prediction / experiment schemas

- Prediction outputs live inside candidate payloads / result schemas, not as
  first-class stored predictions. **There is no store that persists a prediction
  *before* the outcome exists.**
- This is the single biggest gap the cognitive layer fills: `prediction_events`
  (pre-outcome) + `outcome_events` (post) + deterministic prediction-error.

### 1.7 Integration points (summary)

```
PROTACXtend agents / workflows
        │  (adapter, later phase)
        ▼
protacpilot_memory.api  ──►  CognitiveMemory facade
        │                         │
        ├── MCP stdio (cog_*)     ├── store (SQLite + FTS5)
        ├── HTTP JSON             ├── cognitive engines
        └── ppmemory CLI          └── retrieval engines
```

---

## 2. Upstream Engram audit (what we actually inspected)

Shallow clone of `Gentleman-Programming/engram`. Relevant surface:

| Upstream area | Concrete finding |
|---|---|
| `internal/store/store.go` | ~360 KB single store. Source of truth. `sessions`, `observations`, `observations_fts`, `user_prompts`, `prompts_fts`, `memory_relations`, `sync_*`. |
| FTS5 | `observations_fts` uses `tokenize='trigram'`, `content='observations'` (external-content FTS), maintained by **triggers** that skip rows where `deleted_at IS NULL`. |
| `internal/store/relations.go` | ~60 KB relation engine: `memory_relations` with `judgment_status`, `superseded_at`, `superseded_by_relation_id`, confidence, evidence, actor/model provenance. BM25 relation scan. Relation types include `related`, `already_related`, `supersedes`. |
| Topic identity | `topic_key` + `normalizeTopicKey`; on save, if a non-empty `topic_key` matches `(project, scope, deleted_at IS NULL)`, the row is **updated in place**, `revision_count += 1`. Distinct decisions are kept under distinct keys. |
| Dedupe | `normalized_hash = hashNormalized(content)` + a `DedupeWindow`; duplicates within `(normalized_hash, project, scope, type, title)` bump `duplicate_count` instead of inserting. |
| Soft delete | `deleted_at` filter is applied in FTS triggers, search, context, timeline. Hard delete exists but is explicit. |
| Review lifecycle | `review_after` timestamp; `State()` derives `active` vs `needs_review` **virtually** (not a stored column). `decayReviewAfterMonths` maps `decision`→6m, `policy`→12m, `preference`→3m; other types get `NULL`. |
| Progressive disclosure | 3 layers: `mem_search` (compact previews, content deliberately excluded) → `mem_timeline` (chronological neighbourhood) → `mem_get_observation` (full body). |
| MCP tools | `mem_search`, `mem_context`, `mem_timeline`, `mem_get_observation`, `mem_save`, `mem_update`, `mem_delete`, `mem_review`, `mem_judge`, `mem_compare`, `mem_current_project`, `mem_list_projects`, `mem_stats`, `mem_doctor`, `mem_pin`/`mem_unpin`, `mem_merge_projects`, session tools. |
| Conflict handling | Pending conflicts surfaced by `mem_save`; `mem_judge` records a verdict; `mem_compare` persists a semantic relation between observations. |
| Search reranking | BM25 projection with bounded multiplicative boosts: title ×5.0, content ×1.0, topic_key ×3.0, pinned +0.10, recency +0.06, stability +0.04. |
| Migrations | Idempotent `CREATE TABLE IF NOT EXISTS`, additive `ALTER TABLE` column migrations, migration lock files (unix/windows), legacy DDL tests. |
| Project detection | `cwd → .engram/config.json → git binding → child repo → basename`; `mem_current_project` never errors. |
| Sync/cloud | `sync_mutations`, `sync_apply_deferred`, chunk codecs, cloud runtime. |

---

## 3. What to REUSE conceptually

| Upstream idea | How PROTACpilot Cognitive Memory reuses it |
|---|---|
| Single local authoritative store | One SQLite file, `~/.protacpilot-memory/memory.db` (configurable). No mandatory external services. |
| SQLite + FTS5, trigram tokenizer | Same. External-content FTS5 over `memory_traces`. |
| Trigger-maintained FTS honoring soft delete | Same external-content FTS5, but retrieval queries additionally filter by `status`/`deleted_at`, so archived/superseded/deleted rows never surface (the index is maintained for all rows; filtering happens at query time). |
| `topic_key` upsert + `revision_count` | Reused as **semantic topic identity**, but generalization is additionally gated by consolidation thresholds. |
| `normalized_hash` + dedupe window + `duplicate_count` | Reused, but **augmented by a context fingerprint** so biologically distinct experiments are never collapsed (§12 of the prompt). |
| Soft delete + explicit hard delete | Same. Scientific provenance is never physically deleted by decay. |
| Virtual review state from `review_after` | Reused, extended with class-specific decay half-lives. |
| Progressive disclosure (3 layers) | Reused and extended to 4 layers (search → neighbourhood/timeline/evidence → memory packet → raw artifact). |
| Typed `memory_relations` with supersede chain | Reused and extended with the scientific relation vocabulary (`supports`, `contradicts`, `refines`, `derives_from`, `generalizes`, …). |
| Conflict → `mem_judge` verdict persistence | Reused as the `conflict_verdicts` table so pseudo-conflicts are not re-litigated. |
| Bounded multiplicative reranking boosts | Reused; generalized to a fully configurable additive component model. |
| Idempotent additive migrations + migration tests | Reused. |
| Project detection never fatal (`mem_current_project`) | Reused. |
| Agent-agnostic MCP surface | Reused; tool names prefixed `cog_*`. |
| Explicit sessions | Reused. |
| Event/audit discipline (`sync_mutations`) | Reused as an append-only `memory_events` ledger (local scientific audit trail). |

## 4. What to ADAPT

| Area | Adaptation |
|---|---|
| Observation model | Replaced by the **universal `memory_traces`** base + typed satellite tables (episodic/semantic/procedural/prospective). |
| Free-text `type` | Replaced by a controlled `memory_type` + `status` state machine. |
| `review_after` only on 3 types | Every class gets a decay profile; strength is computed, not just a date. |
| Dedupe by normalized hash | Dedupe key = `(normalized_hash, context_fingerprint, memory_type, project)`; semantic similarity is never allowed to merge identities. |
| `topic_key` in-place update | Episodic rows are immutable; only semantic rows evolve, and evolution produces versions + reconsolidation events. |
| Relations | Extended vocabulary + stance-weighted `memory_evidence`. |
| Reranking | Multi-component additive model with per-component logging. |
| LLM role | Upstream trusts the agent to curate. PROTACpilot additionally inserts a **deterministic attentional gate** and **deterministic consolidation/reconsolidation gates**; the LLM may propose but cannot control integrity, identity, scoring, versioning, or state transitions (Master Prompt §50). |
| Sync/cloud | **Deferred.** Not needed for v1; interfaces kept clean for later. |

## 5. What NOT to inherit

| Upstream aspect | Why we do not inherit it |
|---|---|
| Free-form prose `content` as the memory of record | Scientific memory needs structured context, scope, evidence and provenance; observations vs interpretations vs claims must be separable (§51). |
| Agent-only salience ("agent decides what's worth remembering") | Kept as one signal, but a **deterministic attentional gate** also scores goal-relevance/novelty/surprise/evidence/impact so encoding is auditable and reproducible. |
| Single flat observation namespace | PROTAC memorization needs typed classes with different decay, lifecycle, and evidence semantics. |
| `tokenize='trigram'` only | Replaced with default `unicode61` plus deterministic entity-alias resolution for domain synonyms; trigram can be added as a second index later. |
| Cloud/sync complexity (huge surface) | Out of scope for v1; would add risk without scientific value. |
| Go single-binary distribution assumptions | The host is Python; we ship a Python package + CLI. |
| Branding / naming | No Engram trademark reuse; internal name is `protacpilot-memory`, tool prefix `cog_`. |
| LLM-driven conflict "judge" as the decider | Conflict classification is deterministic (scope/context comparison); an LLM may only annotate. |

## 6. New cognitive modules required

Mapped from the prompt's reference layout to the Python package:

| Prompt layout | Implemented path | Responsibility | Phase |
|---|---|---|---|
| `internal/store/store.go` + `migrations.go` | `src/protacpilot_memory/store/*.py`, `db.py`, `migrations/*.sql` | Persistence, migrations, soft delete, event ledger | 1 |
| `internal/store/{episodes,semantics,evidence,relations,entities,predictions,procedures,prospective}.go` | `store/{episodes,semantics,evidence,relations,entities,predictions,procedures,prospective,working,sessions}.py` | Typed stores | 1–2 |
| `internal/domain/protac/*.go` | `domain/protac/{context,normalization,entities,evidence,ontology}.py` | PROTAC context, fingerprints, aliasing, controlled vocabularies | 1 |
| `internal/cognitive/attention.go` | `cognitive/attention.py` | Encoding priority gate | 2 |
| `internal/cognitive/encoder.go` | `cognitive/encoder.py` | Structured episode encoding + dedupe + candidate relations | 2 |
| `internal/cognitive/retriever.go` | `cognitive/retriever.py` | Orchestrated hybrid retrieval + progressive disclosure | 3 |
| `internal/retrieval/{lexical,semantic,graph,rerank,progressive}.py` | `retrieval/*.py` | Candidate generation and reranking | 3 |
| `internal/cognitive/consolidation.go` + `generalization.go` | `cognitive/consolidation.py`, `cognitive/generalization.py` | Episode clustering → scoped semantic memory | 4 |
| `internal/cognitive/replay.go` | `cognitive/replay.py` | Priority-based replay queue | 4 |
| `internal/cognitive/reconsolidation.go` + `conflict.go` | `cognitive/reconsolidation.py`, `cognitive/conflict.py` | Belief update with versioning | 5 |
| `internal/cognitive/decay.go` | `cognitive/decay.py` | Strength decay + review marking | 6 |
| `internal/cognitive/pattern_completion.go` | `cognitive/pattern_completion.py` | Cue-driven associative reconstruction | 6 |
| — (new, deterministic) | `confidence.py` | Transparent evidence confidence formula | 2 |
| `internal/audit` | `audit/auditor.py` | `cog_audit` integrity/quality reporting | 6 |
| `internal/mcp` | `mcp/tools.py`, `mcp/server.py` | `cog_*` tool registry + JSON-RPC stdio | 1–5 |
| `internal/server` | `server/api.py` | HTTP JSON surface | 3 |
| `internal/cli` | `cli/main.py` | `ppmemory` CLI | 1 |
| `internal/config` | `config.py` | Configurable hyperparameters | 1 |

**Genuinely new cognitive capabilities (not present upstream):**

1. Deterministic attentional gate with recorded component breakdown.
2. Prediction lifecycle persisted **before** outcome + typed prediction-error
   (normalized numeric error, Brier score, NLL).
3. Context fingerprinting for pattern separation.
4. Evidence-stance store (`supports`/`contradicts`/`context`) with independence
   grouping and source-quality weighting.
5. Multi-criteria consolidation gates (episode count, independent sources,
   contradiction ratio, aggregate evidence).
6. Scope-aware generalization with machine-readable scope.
7. Versioned reconsolidation outcomes (`STRENGTHEN/WEAKEN/REFINE_SCOPE/BRANCH/SUPERSEDE/RETRACT/NO_CHANGE`).
8. Deterministic conflict classification (true contradiction vs contextual/
   scope/measurement/assay difference vs compatible).
9. Use-dependent strengthening (`retrieval_count` vs `successful_retrieval_count`).
10. First-class negative memory + counterfactual artifacts.
11. Prospective memory tied to tasks.
12. Transparency auditor.

## 7. Schema migration plan (from existing host state)

The host already owns `protacxtend/memory/*.sqlite3` and `chat_history.sqlite3`.
We do **not** alter them. The cognitive subsystem is greenfield:

```
0001_init.sql         all core tables, FTS, indexes, triggers, event ledger
0002_confidence.sql   additive: confidence feature columns (demonstrates additive migration)
```

Rules:

- Idempotent `CREATE TABLE IF NOT EXISTS`; additive `ALTER TABLE` migrations
  guarded by a `PRAGMA table_info` existence check.
- `schema_migrations(version, name, applied_at, checksum)` records every applied
  migration; checksum mismatch fails loudly.
- Migrations run inside a transaction, with a file-based lock to make concurrent
  startup safe.
- No destructive migration is ever automatic.

**Possible future import bridges (not v1):**

- `run_memory.runs.sqlite3` → episodic `source_type='internal_experiment'`.
- `literature_rag` chunks → `source_documents` + `evidence_items`.
- `benchmark/ground_truth/*.json` → benchmark fixtures only.

## 8. Integration plan

| Step | Deliverable | Status |
|---|---|---|
| 1 | Standalone `protacpilot-memory` package + CLI + tests | implemented |
| 2 | Python facade `CognitiveMemory` used by host agents | implemented |
| 3 | MCP stdio server exposing `cog_*` | implemented |
| 4 | HTTP JSON server | implemented |
| 5 | Adapter `protacxtend.memory.cognitive_bridge` (optional) | **implemented** — maps `AgentRunRecord`, objectives, candidate predictions and outcomes onto `cog_encode` / `cog_predict` / `cog_record_outcome`; runtime hook is opt-in (`PROTACPILOT_COGNITIVE_MEMORY=1`, default OFF) |
| 6 | Import bridge from `run_memory` / literature store | partially done — host `AgentRunRecord` ingestion is implemented; back-filling `run_memory.runs.sqlite3` and `literature_rag` chunks remains deferred |

The subsystem is deliberately **zero-dependency at runtime** (stdlib only) so
it can be embedded anywhere and tested in isolation.

## 9. Test plan

| Test file | Covers |
|---|---|
| `tests/test_migrations.py` | fresh init, idempotency, additive migration, checksum guard, corruption/edge |
| `tests/test_store_core.py` | sessions, working memory TTL, soft delete, versions, event ledger |
| `tests/test_domain_protac.py` | context fingerprinting, entity aliasing/normalization, SMILES/InChIKey handling |
| `tests/test_attention_encoding.py` | attention components, decision thresholds, dedupe, pattern separation, negative memory |
| `tests/test_predictions.py` | pre-outcome storage, numeric/Brier/NLL error, surprise propagation |
| `tests/test_retrieval.py` | hybrid ordering, context discrimination, explainability, progressive disclosure |
| `tests/test_consolidation.py` | min-episode/independence/contradiction gates, scope-aware claim, adversarial non-generalization |
| `tests/test_reconsolidation.py` | conflict classification, strengthen/weaken/refine/branch/supersede, version preservation |
| `tests/test_decay_strength.py` | class-specific decay, use-dependent strengthening, no deletion |
| `tests/test_pattern_completion.py` | cue-driven graph reconstruction |
| `tests/test_prospective_audit.py` | tasks, prospective memory, auditor findings |
| `tests/test_pattern_completion.py` | cue-driven graph reconstruction (chain, E3 cue, branches, disconnected, chronology) |
| `tests/test_state_machine.py` | every legal/illegal lifecycle transition, self-transitions, rollback, concurrency guard, admin override |
| `tests/test_benchmark_h.py` | four-way baseline harness structural + behavioural checks |
| `tests/test_ablation.py` | ablation conditions, per-condition removal verification, deltas |
| `tests/test_procedures.py` | procedural memory API + `cog_procedure_*` tools + versioning |
| `tests/test_performance.py` | performance harness (small N) + percentile logic |
| `tests/test_mcp_cli.py` | MCP `tools/list` + `tools/call`, CLI smoke, HTTP smoke |
| `tests/test_benchmarks.py` | Benchmarks A–H (scaled fixtures) |
| `protacxtend/tests/test_cognitive_bridge.py` (host) | pure host→context/evidence/prediction mapping, opt-in gating, end-to-end ingest + retrieve + outcome roundtrip |
| `protacxtend/tests/test_cognitive_integration_safety.py` (host) | env toggles on a controlled workflow, run-id idempotency, project identity, failure non-fatality |

Run: `python -m pytest protacpilot-memory/tests -q`

## 10. Deliverable status snapshot

| Phase | Scope | Status |
|---|---|---|
| 0 | Audit | **done** (this document) |
| 1 | SQLite/FTS5 foundation, store, MCP, CLI, search, context, timeline, soft delete, topic identity, tests | implemented |
| 2 | Attentional gate, encoding scores, salience/novelty/goal-relevance/surprise, negative memory | implemented |
| 3 | Hybrid retrieval, reranking, progressive disclosure, optional embeddings stubs | implemented |
| 4 | Consolidation, replay | implemented |
| 5 | Reconsolidation, conflict engine, versioning | implemented |
| 6 | Decay, use-dependent strengthening, prospective memory, counterfactual, audit | implemented |
| 7 | Host adapter `protacxtend.memory.cognitive_bridge` + opt-in runtime hook + host-delta harness | implemented |
| V1–V7 | Verification & hardening: state machine, four-way benchmark, ablations, pattern-completion tests, procedural tools, performance harness, host integration safety | implemented |
| UI | TUI/dashboard | **intentionally not built** (Master Prompt §60) |

### Host-delta evidence

`protacpilot-memory/benchmarks/host_bridge_delta.py` replays real host run
artifacts (`outputs/runs/*/run.json`) through the adapter. On the first 20 runs:
self-recall@5 = 1.00, MRR = 0.73, context top-1 = 0.55 vs 0.45 with context
reranking disabled (+0.10), mean search ≈ 3.7 ms, 240 predictions ingested.

## 11. Unresolved technical debt

1. The host adapter is opt-in; `protacxtend/agents/runtime.py` ingests memory
   only when `PROTACPILOT_COGNITIVE_MEMORY=1` (default OFF) so frozen benchmark
   artifacts are unchanged. Back-filling `run_memory` and the literature store
   remains open. Re-ingestion of the same `run_id` is now idempotent.
2. Embedding retrieval is an interface + deterministic hashing fallback only;
   no real model is bundled (by design — optional, §35).
3. Sync/cloud explicitly out of scope.
4. **Hybrid-retrieval scaling**: median hybrid latency grows to ~215 ms at
   N=10,000 (FTS ~10 ms) because entity-overlap candidate generation is
   unbounded and the reranker scores every candidate. Bounding entity
   candidates is the recommended next optimisation.
5. **Lexical ranking**: on Benchmark H, `cognitive_memory` ties the baselines on
   most questions but ranks the design-decision episode above the experimental
   outcome for the factual Q1 (RR 0.5). The additive reranker can also bury a
   unique lexical match (prospective Q7) under accumulated weak signals. These
   are honest, reproducible findings from the four-way harness, not tuned away.
6. Confidence formula is a documented engineering heuristic, not a calibrated
   probabilistic model (§22 permits this for v1).
7. The 50,000-event performance size is opt-in because encode-time candidate
   profiling makes ingestion expensive (~4 min for 100/1k/10k combined).

## 12. Next development step

The host adapter is wired and now has an explicit integration-safety test suite.
The four-way benchmark and ablation framework are in place. The next single
milestone is to **bound entity-overlap candidate generation** (top-K by recency /
BM25) and re-measure the performance sweep, addressing the N=10,000 hybrid
latency while preserving the four-way and ablation baselines.

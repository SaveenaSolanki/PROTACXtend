# Release Notes — SynGlue v0.3.0-agentic-core

_Released: 2026-08-06 · Tag: `v0.3.0-agentic-core` · Branch: `release/v0.3-agentic-core`_

A research-grade agentic PROTAC design platform: adaptive scientific decision
graph, validated uncertainty-aware predictive layers, real retrosynthesis and
ternary modelling, deterministic safety guards around a local LLM, persistent
checkpoints, queue-driven deployment and per-run observability.

---

## Added features

- Unified production entry point (`agents/runtime.py`) — `mode="deterministic"`
  (v0.1, unchanged) and `mode="agentic"` (adaptive graph).
- Conditional routing on evidence (good / out-of-domain / repair paths; 6
  scenario tests). Bounded repair loops for ternary, linker-strain, warhead
  and exit-vector failures (24 tests).
- Dynamic tool selection from available evidence (P4ward vs geometric proxy vs
  blocked; docking tool choice). Parallel candidate evaluation (ThreadPool).
- Human approval gates before expensive modelling and final recommendation;
  persistent interrupt/resume across processes (PostgresSaver).
- Job queue (redis/sqlite) + worker for long jobs; docker-compose stack
  (api/worker/postgres/redis/ollama) boot-tested end-to-end.
- Per-run central tracing (`outputs/runs/<run_id>/trace.jsonl` + summary).
- Three-store memory (Run State / Evidence / Learning) with the learning
  retrieval sequence (failure → signature → validated match → suggestion →
  deterministic validation → outcome).

## Scientific models

- **Chemprop D-MPNN degradation** (single-target logDC50 + multi-target
  DC50/Dmax), trained on PROTAC-DB 3.0, benchmark-excluded splits.
  Retrospective ρ = 0.758–0.783 (vs heuristic 0.42), conformal coverage 92.2%.
- **Applicability-domain detector** (Morgan nn-Tanimoto vs training set):
  OOD flagged, ICM warhead correctly out_of_domain.
- **Retrosynthesis**: RAscore/SAScore prescreen + AiZynthFinder USPTO policy +
  ZINC stock route search (host), with route-quality assessment and
  pass/repair/reject/human routing.
- **Ternary ensemble**: geometric proxy + P4ward + SE3-PROTACs (pretrained
  SE(3)-equivariant GNN) — staged escalation, consensus on raw scores,
  disagreement → human gate.
- **E3-context engine**: deterministic evidence-based CRBN-vs-VHL selection
  (expression / colocalization / ligand / structure / resistance) with a
  data-derived explanation.
- **NSGA-II Pareto ranking** (5 objectives, crowding distance) replacing the
  single composite score.

## Safety controls

- Strict tool registry (13 tools; model may select, never construct names);
  `run_p4ward`/`run_retrosynthesis` force human approval.
- Deterministic validators gate every LLM decision; evidence sufficiency is
  decided by the deterministic gate (LLM may only add flags).
- No raw chain-of-thought stored; decisions only (reason codes, tools,
  evidence refs, confidence, rejected alternatives).
- No LLM molecular editing; repair actions from a closed vocabulary.
- Memory cannot override scientific validators.
- Safe deterministic fallback on any tool/LLM failure.

## Infrastructure

- LangGraph adaptive graph; PostgresSaver persistent checkpointer
  (cross-process interrupt/resume verified); sqlite/memory fallbacks.
- Redis-backed job queue with sqlite fallback; worker for P4ward /
  retrosynthesis / degradation jobs.
- Docker compose: api (host :8001), worker, postgres, redis, ollama; model
  artifacts mounted as volumes; container boot-test with real model output.
- Unified degradation interface (chemprop → synglue → heuristic, labelled).
- Auto gpu/cpu accelerator (containers without CUDA run on CPU).

## Validation

- Full test suite: **293 passed**, 11 skipped (slow real-tool tests).
- LLM role validation (live gpt-oss:20b): **17/17 cases, 100%**, 0 safety
  violations (tools, SMILES edits, hallucinations), 1.0 human-gate recall.
- 8-system agentic-vs-non-agentic benchmark: trained layer +0.31 ρ over
  heuristic; enrichment 0.75 → 0.875; per-layer ablation shows repair rescue,
  AD safety, context veto.
- End-to-end cases: known potent → active (6.9 nM); known weak → inactive
  (334.5 nM); HMGB2-ICM → cross-layer ambiguity correctly routed to human.
- Container stack boot-tested: postgres checkpoint persistence (20
  checkpoints/run), redis queue lifecycle, real multitarget degradation in
  the worker.

## Known limitations

1. Research-grade only — no wet-lab validation; all predictions computational.
2. Conformal intervals are wide (±1.4 log10) — ranking is the reliable output,
   absolute DC50 needs caution.
3. 8-system comparison task is in-domain-only; agentic components' value is
   shown on failure/safety scenarios, not clean ranking.
4. Retrosynthesis in the container degrades to RAscore-only (aizynthfinder
   numpy<2 conflict); full AiZynthFinder runs on the host worker.
5. Cellular-context data is curated (literature), not live DepMap/Open
   Targets/COSMIC.
6. LLM case bank is 17 cases — representative, not exhaustive.
7. Compose ollama container has no gpt-oss pulled (fresh volume); host Ollama
   or deterministic fallback serves the LLM path.

---

_Reproduction: see `RELEASE_CLOSURE_REPORT.md` §10. Full details:
`CHANGELOG.md`, `PROTACPILOT_TECHNICAL_COHERENCE.md`._

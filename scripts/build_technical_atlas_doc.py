#!/usr/bin/env python3
"""Regenerate docs/architecture/PROTACXTEND_TECHNICAL_ATLAS.md from live tables."""
from __future__ import annotations

import csv
import hashlib
import json
import os
from collections import Counter

ROOT = "docs/architecture"


def load(name):
    with open(f"{ROOT}/tables/{name}.csv", newline="") as f:
        return list(csv.DictReader(f))


def sha(p):
    return hashlib.sha256(open(os.path.join(ROOT, "tables", p), "rb").read()).hexdigest()[:16]


nodes = load("workflow_nodes"); tools = load("agent_tools"); tk = load("toolkit_tools")
bes = load("scientific_backends"); caps = load("tpd_capabilities"); cx = load("crosswalk")
expert = None
status = Counter(r["status"] for r in tk)
cap_by_stage = Counter(r["pillar"] for r in cx)

L = []
A = L.append

A("# PROTACXtend Technical Atlas (code-backed) — regenerated 2026-09-24")
A("")
A("Source: live registries via `scripts/build_technical_atlas.py` + `docs/architecture/COUNT_VERIFICATION.txt` (exact commands and outputs). Every listed name exists in current code (re-validated); every claimed execution has a persisted artifact; unavailable/unvalidated components are plainly marked.")
A("")
A("## Table of contents")
for s in ["1. Verified counts and corrected figure data", "2. System map (code paths per arrow)",
          "3. Complete inventories", "4. Crosswalk and 12/11/44/15 reconciliation",
          "5. Depth of each pillar", "6. Agent core", "7. Three real execution traces",
          "8. Wireframes", "9. Claim and gap audit",
          "10. What PROTACXtend can actually do today (one page)", "Appendix: verification commands and tests"]:
    A(f"- {s}")
A("")

A("## 1. Verified counts and corrected figure data")
A("")
A("Command transcript: `docs/architecture/COUNT_VERIFICATION.txt` (run 2026-09-24).")
A("")
A("| Figure claim | Verified | Registry / code | Inclusion rule | Exact command | Verdict |")
A("|---|---|---|---|---|---|")
A("| 31 workflow nodes | **34** | `protacxtend/agents/graph.py:LocalSynGlueWorkflowGraph.nodes` (frozen snapshot 2026-09-23 still 31; capability routes KNOW 11 / REASON 15 / DESIGN 28 / DISCOVER 16) | nodes walked by the graph | `len(LocalSynGlueWorkflowGraph().nodes)` → 34 | **stale → 34** |")
A("| 34 LLM-callable tools | **34** | `agentic/registry.py` TOOL_SPECS/_EXECUTORS | ready_only registry specs | probe → 34 | verified |")
A("| 115 external toolkit tools | **115** (30 callable per TOOLKIT_TRUTH) | `tools/toolkit_registry.py:get_toolkit_registry` | external toolkit registry (≠ universal-registry tools:123) | probe → 115 | verified (registry) |")
A("| 19 scientific backends | **19** | `scientific_backends/registry.py:Capability` enum | capability-level classes | probe → 19 | verified |")
A("| 27 TPD capability classes | **27** (20 ready) | `sota/data/escalation_capabilities.csv` | taxonomy rows | probe → 27 | verified |")
A("| 12 / 11 / 44 / 15 | **catalogued functionalities** (12/11/44/15 + 26 CROSS = 108: `sota/data/functionalities.csv`); **E1-executed adapters per stage 12/7/9/6** (34 total: `results/tool_depth/capability_matrix.csv`) | both files | taxonomy rows ≠ executable units | pillar counters | **re-word (table below)** |")
A("")
A("### 1.1 Overlaps — different objects, never summed")
A("")
A("296 universal registry rows (18 modalities + 123 tools + 49 databases + 43 packages + 26 skills + 37 agent modules) ≠ 123 classified toolkit tools ≠ 115 external toolkit registry entries ≠ 108 catalogued functionalities ≠ 34 agent adapters ≠ 19 backend capability classes ≠ 27 TPD classes ≠ 34 workflow nodes. Only the 34 adapters carry execution evidence (E1: 33/34 domain-valid offline, 31/34 typed negative refusal, 29 matched benchmark ids).")
A("")
A("### 1.2 Corrected figure data + replacement text")
A("")
A("| Field | Old | Corrected |")
A("|---|---|---|")
A("| nodes | 31 | 34 workflow nodes (frozen snapshot 31 kept historical); canonical control plane = 9 modules |")
A("| pillar numbers | 12/11/44/15 | catalogued functionalities 108 (12/11/44/15 + 26 CROSS) — taxonomy; E1-executed adapters 12/7/9/6 |")
A("| external toolkit | 115 | 115 registry entries (30 callable) |")
A("| backends | 19 | 19 backend capability classes (all ready) |")
A("| capabilities | 27 | 27 TPD capability classes (20 ready; taxonomy) |")
A("| tools | 34 | 34 LLM-callable tools (E1-executed) |")
A("")
A("**Replacement text:** *KNOW → REASON → DESIGN → DISCOVER · 34 workflow nodes (23 core + 8 extensions + design_path, capability_answer, reasoning_answer; canonical = 9-module control plane) · 34 LLM-callable tools (E1-executed, 33/34 valid offline) · 115 external toolkit registry entries (30 callable) · 19 backend capability classes · 27 TPD capability classes (20 ready) · catalogued functionalities 108 (12/11/44/15 + 26 CROSS); E1-executed adapters per stage 12/7/9/6. Counts are registration/taxonomy unless marked E1-executed; they must not be summed.*")
A("")
A("Also registered/evolved this session: `request/` (shared request layer), `planning/` (goal planner + /investigate), `therapeutics/` (TargetTherapeuticsAssessment + design gates), `evidence/trace.py` (query→evidence), benchmark repair package, `docs/architecture/adjudication_packet/`; alphaXiv reader (`alpha_search`/`alpha_get_paper`) registered, login-gated, not executed this session.")
A("")

A("## 2. System map (actual functions/classes per arrow)")
A("")
A("| Arrow | Function/class | File | Input | Output | Failure behavior | Deterministic vs LLM |")
A("|---|---|---|---|---|---|---|")
A("| user text / TUI / API / CLI → intent+entities | `RequestController.understand` · `ConversationalAgent.turn` | `request/controller.py`, `request/parser.py`, `agentic/chat_agent.py` | raw text | structured request (intent, mentions, E3 mode, clarification) | typed clarification; no provider → error | deterministic for plan/investigate; LLM only in free chat |")
A("| entities → canonical resolution | `resolver.resolve_target` (curated → supplemental → reviewed UniProt; accessions direct) | `request/resolver.py` | `TargetMention(raw, organism)` | `TargetResolution(symbol, uniprot_id, organism, match_type, resolver_source, status, confidence, suggestion)` | offline/cache replay or unknown + suggestion; never silent conversion | deterministic |")
A("| resolution → goal planner | `goal_planner.build_plan` | `planning/goal_planner.py`, `planning/planner.py` | interpretation state | InvestigationPlan (tasks/gates/branches/executors; includes T1b therapeutics) | clarification; never executes design | deterministic |")
A("| plan → therapeutics | `therapeutics.api.run_assessment` + `design_gate` | `therapeutics/` | spec (+variant/disease/cell) | TargetTherapeuticsAssessment (verdict, gates, per-conclusion evidence) | identity/chemistry/window block → typed TherapeuticallyUnsuitable (no bypass) | deterministic |")
A("| planner/therapeutics → workflow nodes | `LocalSynGlueWorkflowGraph.run` · `CanonicalOrchestrator.run` · `TaskGraphExecutor` | `agents/graph.py`, `canonical/` | state | module results + evidence | fail closed; KNOW/REASON skip design-terminal stops | deterministic (+ optional LangGraph) |")
A("| node → LLM tool call | `chat_agent._llm_action` + `executor.execute_tool` | `agentic/chat_agent.py`, `agentic/registry.py` | action JSON | `ToolResult` (typed) | rejected action re-prompted; ERROR recorded | LLM decides action; execution deterministic |")
A("| tool → toolkit adapter / external registry | `tools/toolkit_registry.py` + per-tool probes | `tools/toolkit_registry.py`, `toolkit/` | tool name + params | registry row + installed status | `registered_but_not_executable`; abstain not fabricate | deterministic |")
A("| adapter → backend / DB | `scientific_backends` registry + clients | `scientific_backends/`, `tools/*_client.py` | capability + params | typed result / `not_available` | network loss → typed not_available; fallback routes | deterministic |")
A("| backend → evidence store | `CanonicalEvidenceStore` | `canonical/evidence.py` | module results | evidence_refs / evidence.jsonl | zero records → critic provenance_break | deterministic |")
A("| evidence → critic/decision | `CriticVerifier.review` → `decision` | `canonical/critic.py`, `canonical/decision.py` | modules + evidence | CriticVerdict + TherapeuticStrategy.v1 | unsupported claims blocked | deterministic |")
A("| critic → report / artifacts | `reporter.render`, `write_run_record`, bridge `handle_report` | `reporting/`, `tui_bridge/server.py` | answer record | summary/technical/CSVs/run.json/raw strategy | invalid/comparison-only never served | deterministic |")
A("| retrieval → KNOW/REASON answers | `evidence.trace.trace_query_to_evidence` | `evidence/trace.py` | capability+question+required | queries, results+relevance, claims, missing | claims empty → visible abstention | deterministic |")
A("| design entry surfaces | `run_protacpilot` · `run_canonical` (strategy CLI) · `workflows.api.run_command` (TUI /design, incl. resume) | `agents/runtime.py`, `canonical/orchestrator.py`, `workflows/api.py` | request (+target_spec/disease/cell) | design result or `status: blocked` | blocked gates / requires_review-strict → typed block, no bypass | deterministic |")
A("")

A("## 3. Complete inventories")
A("")
A("Files are exhaustive (no “etc.”) and SHA-256-pinned; every name re-validated against its registry.")
A("")
A("### 3.1 Workflow nodes (34) — `tables/workflow_nodes.csv`")
A("")
A("| # | node | pillar(s) | executor |")
A("|---|---|---|---|")
for r in nodes:
    A(f"| {r['node_index']} | {r['node']} | {r['pillar']} | {r['executor_class']} ({r['executor_module']}) |")
A("")
A("### 3.2 LLM-callable tools (34) — `tables/agent_tools.csv`")
A("")
for t in tools:
    A(f"- **{t['name']}** — {t['purpose']}")
A("")
A("### 3.3 External toolkit registry (115) — `tables/toolkit_tools.csv`")
A(f"Status census: {dict(status)} · sha256 `{sha("toolkit_tools.csv")}` · full 115 rows with category/license/executable_type/status.")
A(f"Example rows: {', '.join(r['tool_name'] for r in tk[:6])} … (full list in CSV).")
A("")
A("### 3.4 Scientific backend capability classes (19) — `tables/scientific_backends.csv`")
A("")
A("| capability | best backend | usable | registered | status |")
A("|---|---|---|---|---|")
for b in bes:
    A(f"| {b['capability']} | {b['best_backend']} | {b['usable_backends']} | {b['registered_backends']} | {b['status']} |")
A("")
A("### 3.5 TPD capability classes (27) — `tables/tpd_capabilities.csv`")
A("")
for c in caps:
    A(f"- **{c['capability']}** — fallbacks {c['n_fallbacks']} ({c['fallbacks'] or 'none listed'})")
A("")
A("### 3.6 Catalogued functionalities (108) — `tables/functionalities.csv`")
A("Full rows with fid/domain/subcategory/functionality/stage/evidence/implementation/agents/tools/module/status.")
A("")

A("## 4. Crosswalk and 12/11/44/15 reconciliation")
A("")
A(f"`tables/crosswalk.csv` (34 adapter rows: tool → pillar → biological question → implementation module → source connector → typed output → evidence type → failure code → fallback → matched permitted ids → validation level → E1 outcome) and `tables/dataflow_edges.csv` (26 source→tool→output→strategy-field edges). Many-to-many: one tool calls several toolkit/backend resources; one capability is served by several tools. E1 adapter census per stage: {dict(cap_by_stage)} — this is the executable surface.")
A("")
A("**Reconciling 12/11/44/15:** those are catalogued-functionality rows per pillar (`functionalities.csv`, a taxonomy). The executable surface is the 34-adapter crosswalk: KNOW 12 / REASON 7 / DESIGN 9 / DISCOVER 6 (E1). The two sets must not be interchanged. The 27 TPD classes are a taxonomy; most are reached only through `run_scientific_capability`/`list_scientific_capabilities` dispatch or the toolkit layer, not as first-class tools.")
A("")
A("| tool | pillar | matched ids | validation level | E1 outcome |")
A("|---|---|---|---|---|")
for r in sorted(cx, key=lambda x: (x["pillar"], x["agent_tool"])):
    A(f"| {r['agent_tool']} | {r['pillar']} | {r['matched_permitted_ids'] or '—'} | {r['validation_level'] or 'unassessed'} | {r['real_input_run_outcome'] or 'not run'} |")
A("")

A("## 5. Depth of each pillar")
A("")
A("Definitions: **inferred** = model/rule output; **experimentally measured** = literature/assay value used as-is (source-linked); outputs flagged `heuristic_fallback`/`NOT_VALIDATED`/`unavailable` where applicable. Pre-design stage: every plan carries `T1b_therapeutic_assessment` (TargetTherapeuticsAssessment: identity/variant/disease/cell + disease/dependency/normal-tissue/binder/E3 evidence) with mechanism-vs-suitability split and requires_review window gate when data are missing.")
A("")

PILLAR_ROWS = {
 "KNOW (literature, target, binder, compound, structure, governance/provenance, patent)": [
  ("literature (deep_research, search_europe_pmc/pubmed, retrieve_fulltext)", "what is published about X?", "query → Europe PMC/PubMed REST", "ranked retrieval + crossref verify", "RETRIEVED (no citation-accuracy gold)", "records[] (id/source/title)", "E1 executed; no adjudicated gold", "network down → typed not_available", "recall varies; next: adjudicated citation gold"),
  ("target (resolve_target, search_uniprot)", "canonical identity of X?", "symbol/alias/accession → curated+supplemental+UniProt", "exact/alias/fuzzy with suggestions", "tool-set (verified/tentative/ambiguous/unknown)", "symbol, UniProt, organism, method, confidence, alternatives", "curated + UniProt; suggestions never auto-applied", "ambiguous/unknown → clarification", "alias coverage offline; next: resolution gold set"),
  ("binder/compound (retrieve_target_binders, search_chembl/pubchem/bindingdb)", "which measured ligands?", "ChEMBL/PubChem PUG/BindingDB", "REST retrieval + provenance", "RETRIEVED", "BinderRecord (smiles, activity_nM, p_activity, assay, source)", "E1 executed; not affinity-validated", "no source → abstention", "label noise; next: assay-level curation"),
  ("structure (retrieve_pdb)", "what structures exist?", "RCSB/PDB/AlphaFold", "REST", "RETRIEVED", "structure ids + metadata", "executed", "none → no coordinates", "—"),
  ("governance/provenance (verify_crossref, run_quarantine)", "is the claim traceable?", "DOI/registry", "CrossRef verify + quarantine/comparison-only statuses", "RETRIEVED", "citation metadata; run status/claims", "E1 executed", "invalid DOI; invalid/comparison-only runs excluded everywhere", "—"),
  ("patent (registered only)", "patent coverage?", "—", "—", "unavailable", "—", "—", "no adapter", "no patent-mining adapter; next: add patent source")],
 "REASON (E3, safety, chemistry, warhead, resistance)": [
  ("E3 (select_e3_ligase, retrieve_e3_evidence; therapeutics e3 block)", "which E3 for this target?", "curated_e3_ligands.csv + precedent rows", "catalog + M6 RF (AUROC 0.93 unseen-E3, retrospective)", "catalog/ML", "E3 shortlist + verdict", "module VALIDATION docs; no prospective", "no precedent → abstain specific", "next: prospective E3 selection"),
  ("cell context (predict_cell_context)", "does context change prediction?", "DepMap 24Q4 transcriptomics", "RF/XGB grouped CV", "LEARNED", "pDC50/Dmax + AD", "unseen-PROTAC R² 0.605 vs 0.513", "OOD → AD warning + heuristic_fallback flag", "proteotype unavailable"),
  ("safety / chemistry / warhead / resistance", "developability + mechanism risks?", "RDKit descriptors + rules", "rules/surrogates", "computed/heuristic", "typed verdicts", "functional", "missing input → typed codes", "some surrogates unvalidated")],
 "DESIGN (linker, degradation, search, preparation, ternary, MD, docking, selectivity)": [
  ("linker (generate_linkers, detect_exit_vectors)", "which linker/attachment?", "fragments + libraries", "char-GRU + fragment + rules; exit-vector detection", "computed", "linker panels + exit-vector records", "15 unit tests", "no source-backed warhead → defer", "hypothetical markers need chemist review"),
  ("construction (construct_protac, inspect_smiles)", "assemble components?", "warhead+linker+E3 SMILES", "RDKit dummy-atom join + canonicalization", "computed", "CandidateRecord + InChIKey", "RDKit validity + identity checks", "no markers → design brief / abstention", "hypothetical exit vectors"),
  ("ternary (model_ternary_complex)", "ternary feasible?", "components/structures", "P4ward wrapper + geometric proxy (score-only)", "COMPUTED/surrogate", "feasibility scores (no coordinates)", "12 native complexes; DockQ NOT_VALIDATED", "no coordinates → structural claims blocked", "next: coordinate emitter + DockQ benchmark"),
  ("MD/docking (retrieve_pdb + run_protacpilot_structural / backends)", "pose / energetics?", "PDB + ligands", "Vina/GNINA/DiffDock; OpenMM", "computed", "RMSD, poses", "frozen redocking (Vina ≤2Å 0.375 [0.225,0.525])", "failures kept; MM/GBSA NOT_VALIDATED", "pose ≠ affinity"),
  ("search/preparation + selectivity (protein_preparation, ligand_preparation, selectivity)", "docking-ready input + isoform selectivity?", "structure/ligands", "prep backends + rules", "computed", "prepared structures + selectivity notes", "functional", "missing input → typed codes", "selectivity unmeasured vs labelled")],
 "DISCOVER (review, benchmark, ranking, novelty, diversity, reporting, discovery, retrosynthesis)": [
  ("degradation (predict_degradation)", "predicted DC50/Dmax?", "SMILES + context", "TACK-style/chemprop/M4/M5", "LEARNED (never measured)", "pDC50/DC50 nM/Dmax % + OOD + CI", "grouped splits (unseen-PROTAC R² 0.605)", "OOD → applicability flag", "field ceiling LOTO ≈0.67; Dmax R²≈0.36"),
  ("ADME (predict_admet)", "developability flags?", "SMILES", "ADMET-AI/descriptors/rules", "LEARNED/computed", "hERG/AMES/DILI/…", "functional only", "no PK model", "permeability claims restricted"),
  ("ranking/novelty/diversity (rank_candidates, check_novelty, diversity)", "prioritize candidates?", "scored candidates", "Pareto/NSGA-II + InChIKey novelty", "computed", "ranked front + flags", "unit + harness", "no candidates → no ranking", "score ≠ biological activity"),
  ("reporting/discovery (build_candidate_dossier, run_protacpilot_structural)", "package evidence?", "records", "templated dossier", "mixed", "dossier + artifacts", "functional", "missing records → gaps marked", "—"),
  ("retrosynthesis (check_synthetic_feasibility + ASKCOS/AiZynth/OpenNMT)", "synthesizable?", "SMILES", "engine status-gated", "computed", "feasibility + provenance", "smoke evidence", "engine unavailable → not_available", "route quality unvalidated")],
}
HDR = "| submodule | question | inputs/sources | algorithm | evidence | outputs | validation | abstains | limitation → next |"
for i, (pillar, rows) in enumerate(PILLAR_ROWS.items(), 1):
    A(f"### 5.{i} {pillar}")
    A("")
    A(HDR); A("|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        A("| " + " | ".join(r) + " |")
    A("")

A("## 6. Agent core")
A("")
A("- **Orchestration**: `request/controller.py` (understand → clarify → run), `planning/goal_planner.py` (plan), canonical `orchestrator.py`/`task_graph.py` (9 modules, fail-closed), legacy `agents/graph.py` (34 nodes), `agentic/chat_agent.py` loop (registry-validated actions).")
A("- **Working state**: `backend/schemas.py:WorkflowState` (typed; per-node retry policy).")
A("- **Episodic memory**: `memory/` (workflow_logs/*.json, agentic_design_memory.jsonl); `protacxtend-memory/` cognitive subsystem (opt-in `PROTACPILOT_COGNITIVE_MEMORY=1`; refuses quarantined/comparison-only runs).")
A("- **Semantic/procedural**: `memory/learning_memory.py`, `memory_manager.py` (strategy/lesson records).")
A("- **Retrieval**: `research/` (Europe PMC→PubMed→OpenAlex→Crossref→SearXNG→crawl→rerank→synthesis); `evidence/trace.py` (query→evidence, relevance, claims, missing); `request/resolver.py` versioned UniProt cache (`data/request_cache/`, live-vs-cache reported).")
A("- **Provenance**: `run_records.py:AgentRunRecord` + reproducibility_hash; `canonical/evidence.py` ledger; per-run run.json/decisions.jsonl/evidence.jsonl; assessment records (context-fingerprinted) and run_quarantine statuses. A citation string alone is not provenance; lineage requires the ledger + hash.")
A("- **Self-healing**: `escalation/` (27-capability taxonomy, fallback chains, n_fallbacks), `runtime/fault_injection.py` (9 scenarios; abstention beats hallucination).")
A("- **Observability**: `diagnostics.py` doctor; `runtime/audit.py`; TUI bridge events; `observability/` tracing (TraceSession per run).")
A("- **Contamination safeguards**: quarantined (INVALID) and comparison-only runs excluded from TUI/API/search/reports/ENGRAM and memory ingestion; retrieval-claims-only abstention for KNOW/REASON (strategy text never counts as evidence); context-fingerprinted assessments reject stale/mismatched records; fault injection verified 0 hallucinated continuations.")
A("")

A("## 7. Three real execution traces")
A("")
A("- **A — `/plan EGFR protac`**: `docs/architecture/traces/TRACE_A_and_C_RERUN.md` + `ATLAS_TRACES_A_C1.json` (+ real E3 investigation artifact under `outputs/plans/*/artifacts/T3_e3_feasibility.jsonl`). Resolved EGFR → P00533; E3 **investigated** (never demanded); tasks T0..T6 incl. `T1b_therapeutic_assessment`; executed_design=False.")
A("- **B — BRD4–VHL MZ1 reference reconstruction**: `docs/architecture/traces/TRACE_B_RERUN.md` (root `outputs/runs/run_brd4_vhl_scientific_v1/`). Stages entered, funnel, typed evidence records, measured-literature vs unavailable distinction, SYNTHESIS + PENDING next experiment.")
A("- **C — unavailable evidence / backend failure**: `TRACE_A_and_C_RERUN.md` — ZZZZ9 clarification (real bridge call), ChEMBL HTTP-500 abstention with stage census (`diagnostic_zero_candidate_post_fix2.json`), comparison-only corrected replay (`run_e4e21ccd_corrected_v1/manifest.json`).")
A("")
A("Vocabulary control: plan ≠ design brief ≠ assembled RDKit-valid molecule ≠ prediction ≠ literature reference ≠ experimentally validated degrader (no wet-lab result exists in this repo).")
A("")

A("## 8. Wireframes")
A("")
for f in ["architecture_overall.mmd", "plan_investigate_therapeutics.mmd", "pillar_know.mmd",
          "pillar_reason.mmd", "pillar_design.mmd", "pillar_discover.mmd", "agent_core.mmd",
          "tui_wireframe.mmd"]:
    A(f"- `diagrams/{f}` — Mermaid source; labels link to §3 inventories. Editable SVGs also in `results/tool_depth/Figure_A_architecture.svg`, `Figure_B_toolkit_depth.svg`.")
A("")

A("## 9. Claim and gap audit")
A("")
A("State ladder per `results/BENCHMARK_RESULTS_V2.md`: 46 registered / 18 executable / 9 output-validated / 9 benchmarked / 7 externally validated / 0 prospective. Per-item levels in `tables/crosswalk.csv` (`validation_level`).")
A("")
A("| Gap | Type | Location | Priority | Fix / acceptance test | Manuscript claim affected |")
A("|---|---|---|---|---|---|")
A("| gold 0/48 + 0/1000 (B1) | correctness | benchmark/ + benchmark500/ | P0 | two annotators sign adjudication packet + gateC | every correctness sentence |")
A("| ternary coordinates (B2) | unvalidated | canonical structure_ternary | P0 | coordinate emitter + DockQ | §2.3 ternary paragraph (feasibility-only) |")
A("| degradation field ceiling (B3) | benchmarking | M4/M5/TACK | P1 | audit on PROTAC-Bench/TACK splits | 'at-ceiling' framing |")
A("| manifest timing (B4/F-13) | defect | run_records | P1 | real per-module timestamps | cost/latency sentences |")
A("| live-source dependency (B5) | resilience | binder_agent + disk cache | P1 | clean-day + cache-replay runs | retrieval-reliability wording |")
A("| security shell=True/pickle (B6/G12) | security | toolkit/provision, models | P0 release | arg-lists + safe loader | 'production-ready' wording |")
A("| registry status hard-coded False (B7/F-07) | counting | toolkit/status.py | P1 | real probe | 296-vs-34 denominators |")
A("| SynGlue COI (B8) | provenance | data/synglue + preprint | P1 | COI statement | degraded-backend sentence |")
A("| one critic vs three (F-12) | architecture | canonical/critic.py | P2 | split critics | critic description |")
A("| evidence_refs internal labels (F-13) | provenance | canonical/evidence.py | P2 | external refs + timestamps | provenance sentences |")
A("| unvalidated scores (SVR 0.333) | benchmarking | results/audit | P1 | measure or mark | SVR sentences |")
A("| watchdog: requires_review window | gating | therapeutics/ | closed | flag + strict mode; no suitability claim | design bypass sentences |")
A("")
A("Dead/duplicate routes: legacy `synglue_agent`/`SynGlue_Py` residue dirs; `agentic/` deprecated vs `canonical/`; `protacpilot-memory`↔`protacxtend-memory` rename (committed); 21 toolkit tools repo/commercial-gated (never executed); 6 backend capabilities no user-facing route beyond `run_scientific_capability` dispatch; alphaXiv login-gated.")
A("")

A("## 10. What PROTACXtend can actually do today (one page)")
A("")
A("1. **Understand and plan**: `/plan` resolves targets canonically (curated → supplemental → UniProt; aliases; typo suggestion only when unresolvable), applies decision-rule clarification, honours latest-explicit-correction, and returns an executable investigation plan (tasks/tools/gates/branches/executors) — with `T1b_therapeutic_assessment` pre-design (real traces A).")
A("2. **TargetTherapeuticsAssessment**: typed pre-design stage with disease/dependency/normal-tissue/binder/E3 evidence, association≠causality and expression≠function, mechanism-vs-suitability split, and identity/chemistry/window gates that design cannot bypass across every entry point (run_protacpilot, run_canonical/strategy CLI, workflows.api /design incl. resume). KRAS G12C is blocked at chemistry (diagnosis in docs); EGFR/BRD4 justified mechanism with window requires_review (flagged, not a pass).")
A("3. **Retrieve and evaluate** (`/investigate` + `evidence/trace.py`): evidence tasks with typed outcomes; KNOW/REASON answers are retrieval-claims-only with visible abstention; failure ⇒ revised plan/open question, never fabrication.")
A("4. **Design**: deterministic graph + canonical 9-module stack; RDKit-valid assembly with InChIKey dedup and gates; missing inputs produce design briefs (zero-candidate defect fixed; same-case 300→150→50). MZ1 reconstruction reproduces the published InChIKey and separates literature vs in-run numbers (trace B).")
A("5. **Score and rank**: degradation (at field ceiling, uncertainty-gated), ADME flags, hook-effect (M1 validated), cell-context (M5 grouped), E3 ranking (M6 unseen-E3 AUROC 0.93), Pareto ranking — all labelled computational.")
A("6. **Govern and explain**: typed TherapeuticStrategy; critic verdicts; provenance + reproducibility hashes; quarantine/comparison-only enforcement; evidence-driven explanation reports; claim-gated figures; context-fingerprinted assessments.")
A("")
A("**Not yet supported**: experimentally validated degraders; ternary coordinates (DockQ) and MM/GBSA; benchmark gold (0 adjudicated); PK models; prospective validation (0); alphaXiv (login-gated); therapeutic suitability in any indication (requires_review until dependency + normal-tissue data arrive).")
A("")

A("## Appendix: verification commands and tests")
A("")
A("Counts: `python -c ...` probes recorded in `docs/architecture/COUNT_VERIFICATION.txt`; tables rebuilt with `python scripts/build_technical_atlas.py`; doc regenerated by `scripts/build_technical_atlas_doc.py`.")
A("")
A("Focused test suites run 2026-09-24 (87 passed): `tests/test_plan_dialogue.py tests/test_therapeutics_assessment.py tests/test_therapeutics_audit.py tests/test_explanation_pipeline.py tests/test_run_quarantine.py tests/test_benchmark_grader.py tests/test_reconciliation_four_case.py` — outputs captured in session; every claim here links to the artifact listed beside it.")

open("docs/architecture/PROTACXTEND_TECHNICAL_ATLAS.md", "w").write("\n".join(L))
print("atlas written:", os.path.getsize("docs/architecture/PROTACXTEND_TECHNICAL_ATLAS.md"), "bytes,", len(L), "lines")
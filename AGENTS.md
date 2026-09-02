# AGENTS.md — PROTACXtend Agent Workframe

> Instructions for AI coding agents (GitHub Copilot coding agent, pi, codex, etc.)
> working in this repository. Read this file before editing, and keep the contract
> below satisfied on every change.

## 1 · What this repository is

PROTACXtend is an **agentic PROTAC (proteolysis-targeting chimera) discovery
platform**. A supervisor parses a natural-language design objective and orchestrates
specialist agents (target resolution, binder retrieval, linker generation, molecular
construction, degradation/ADMET ML, ternary-complex physics, ranking, reflection) over a
shared typed workflow state. Every node writes an auditable trace — no black boxes.

## 2 · Mental model — the code IS the agents

| Concept | Where it lives |
| --- | --- |
| Workflow graph (31 nodes; deterministic fallback + LangGraph path) | `synglue_agent/agents/graph.py` |
| Node registry (ordered agent list) | `graph.py` → `LocalSynGlueWorkflowGraph.nodes` |
| Shared workflow state schema | `synglue_agent/agents/state.py` |
| One agent per file, each implementing `run(state) -> state` | `synglue_agent/agents/*_agent.py` |
| Supervisor (objective parsing, plan policy) | `synglue_agent/agents/supervisor_agent.py` |
| 73-method chemistry engine | `synglue_agent/tools/protac_toolbox.py` |
| FastAPI REST backend | `synglue_agent/backend/api_routes.py` |
| CLI entrypoints | `synglue_agent/cli.py` |
| Memory / learnings / checkpoints | `synglue_agent/memory/` |
| Tests | `synglue_agent/tests/` |
| Docs (installation, architecture, workflows, API) | `documentation/` |
| Web app & GitHub Pages site | `website/` (pure static: index.html, styles.css, app.js, assets/) |

## 3 · Node contract (the workframe rule)

1. Read `WorkflowState`; perform exactly **one falsifiable task**.
2. Write evidence back into state fields; never silently mutate another node's output.
3. If evidence is missing and the node is retryable per the plan policy → the graph retries;
   if it is terminal → the graph escalates with a human-readable error. Never fabricate.
4. Prefer the deterministic state machine unless a feature requires LangGraph
   branching (both paths share the same node registry in `graph.py`).

## 4 · Conventions

- Python 3.10+; keep the package importable with zero network and zero optional deps
  (import-time graceful degradation is required — see `scripts/ci_smoke.py`).
- New agents: one class per file in `synglue_agent/agents/`, registered in
  `graph.py`'s ordered list **and** the docs/website pipeline copy if user-visible.
- Tests are unit-style, asset-free, and marked `slow` / `network` when applicable so CI
  can run the fast offline subset in ~minutes.
- Web changes are static-first: edit `website/index.html`, `website/styles.css`,
  `website/app.js`; no build step. Keep the PROTACXtend palette tokens at the top of
  `styles.css` (`#0B1338`, `#706BD6`, `#8683DD`, `#5AB9CD`, `#1792A2`, …).

## 5 · Definition of done (any change)

- [ ] `python -m compileall -q synglue_agent scripts`
- [ ] `python scripts/ci_smoke.py` passes (imports, tool registry, /health)
- [ ] Fast offline unit tests pass:
      `python -m pytest synglue_agent/tests/ -m "not slow and not network" -q`
- [ ] No secrets: keep API keys/tokens out of tracked files (CI runs gitleaks on full history).
- [ ] Docs (`documentation/` or `website/`) updated when user-visible behavior changes.

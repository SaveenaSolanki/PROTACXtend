# AGENT_WORKFRAME.md — PROTACXtend Agentic Workframe & Final-Code Test Protocol

**Author:** Saveena Solanki · **Lab:** Ahuja Lab, Dept. of Computational Biology, IIIT Delhi
**Scope:** how the PROTACXtend agent framework is organized, governed, verified and released —
and exactly how the final code is exercised on GitHub before it is considered releasable.

---

## 1 · Workframe philosophy

PROTAC design is a coupled combinatorial search: warhead × linker × E3-recruiter
chemistry, ternary-complex geometry, cooperativity (α), hook effect, degradation
efficiency and ADMET safety are all interdependent. PROTACXtend therefore frames design
as **an orchestrated graph of specialist agents** rather than a monolithic script.

The workframe name comes from the guarantee that matters to science:

> **Every molecule is the output of visible, falsifiable reasoning steps — never the
> output of an opaque call.**

## 2 · Orchestration model

| Layer | Responsibility | Implementation |
| --- | --- | --- |
| Supervisor | Parse objective; commit a design plan; set retry & escalation policy | `supervisor_agent.py`, `design_planner_agent.py` |
| Governance | Bound NP-hard search; safety precheck before any chemistry | `search_control_agent.py`, `safety_agent.py` |
| Discovery | Resolve target/binders/warheads/E3 in UniProt·ChEMBL·PubChem·BindingDB | `target_agent.py`, `binder_agent.py`, `warhead_agent.py`, `e3_agent.py`, `exit_vector_agent.py` |
| Assembly | Linker generation → PROTAC construction → stereoisomer enumeration → validation | `linker_agent.py`, `construction_agent.py`, `context_agent.py` (+ `protac_toolbox.py`) |
| Evaluation | ADMET, novelty, applicability domain, cheap filters, degradation ML, ranking, diversity | `admet_agent.py`, `novelty_agent.py`, `degradation_node.py`, `ranking_agent.py`, `proximity_agent.py` |
| Closed loop | Reflection review, evolution refinement, expensive modeling selection, ternary feasibility, cooperativity, hook effect, final ranking, active learning, report, memory | `reflection_agent.py`, `evolution_agent.py`, `ternary_agent.py`, `cooperativity_agent.py`, `active_learning_agent.py`, `report_agent.py` |

**Node contract (enforced in code):** each node implements `run(state) -> state`;
reads the shared `WorkflowState`; performs one falsifiable task; writes evidence back.
Retryable steps are re-run only when their required output is missing; terminal errors
stop the graph with an explicit message. See `AGENTS.md` §3.

## 3 · Observability & audit

- Every node append to a structured trace (`synglue_agent/observability/`).
- Sessions are checkpointed to persistent memory (`synglue_agent/memory/`) and replayable
  with `/audit`, which cross-checks each claim against the empirical tool-output matrix.
- The Feynman rule: *invisible interactions → visible reasoning traces; black-box
  predictions → step-by-step decision chains.*

## 4 · Final-code test protocol (local → GitHub)

The final tree is exercised in two tiers before release.

**Tier 1 — fast gate (local, minutes):**

```bash
python -m compileall -q synglue_agent scripts
python scripts/ci_smoke.py                      # imports · 21-tool registry · /health
python -m pytest synglue_agent/tests/ \
  -m "not slow and not network" -q              # fast offline unit suite
```

**Tier 2 — full gate (GitHub Actions, `.github/workflows/ci.yml`):**

1. **smoke** — compile, asset-free smoke, fast offline unit subset (Python 3.11).
2. **full-offline** — install `requirements.txt`, bootstrap upstream repos, run the full
   fast suite (no slow/network), then the **agentic end-to-end benchmark**
   (`scripts/e2e_agentic.py --offline`, 5 scenarios on the real graph).
3. **security** — gitleaks full-history scan, ruff lint, committed-artifact availability
   check, and external-asset bootstrap dry-run.

**Release bar:** Tier 1 green locally on the exact commit that is pushed; Tier 2 green in
GitHub Actions on `main`. A change is "final" only when both bars pass and the
CHANGELOG/version markers are updated in the same commit.

## 5 · Deploying the web presence

- `website/` is the **pure-static** GitHub Pages source (no build step): served live at
  `https://<owner>.github.io/PROTACXtend/` by `.github/workflows/pages.yml` (build → `gh-pages`).
- Run locally with any static server, e.g. `python -m http.server 8085 --directory website`.
- Design tokens (PROTACXtend palette) are centralized at the top of `website/styles.css`.

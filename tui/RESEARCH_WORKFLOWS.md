# PROTACXtend TUI — Research Workflows & Execution Log

**File:** `tui/RESEARCH_WORKFLOWS.md`
**Product name (displayed exactly):** `PROTACXtend`
**Launch (global, from any directory):** `protacxtend`
**Local dev launch (preserved):** `cd tui && node dist/index.js`

This document records (1) the workflow-system expansion of the PROTACXtend
terminal, (2) the global CLI wiring, and (3) the full execution + verification
log for every step requested before freezing the TUI.

---

## 1. Product identity

- The block wordmark renders the exact tool name **PROTACXtend**
  (capital `PROTACX` + lowercase `tend` glyphs). The lowercase `t/e/n/d`
  glyphs were redesigned for readability (clean x-height `e`/`n`, `t`
  crossbar, and a consistent `d` bowl + ascender).
- TUI layout and styling are unchanged (Laboratory-Night theme, two-column
  header card, KNOW → REASON → DESIGN → DISCOVER footer).
- Source of truth for the name: `tui/src/logo.ts` (`BRAND_NAME =
  "PROTACXtend"`).

## 2. Research workflow system

The TUI moved from a tool-centric command list to a complete
targeted-protein-degradation research system. **The opening dashboard shows
only the primary research workflows.** Low-level tools are not exposed as
top-level workflows — they remain accessible and are mapped into the
higher-level workflows.

| # | Workflow | Phase | Definition (short) |
|---|----------|-------|--------------------|
| 1 | `/plan` | KNOW | Build an evidence-grounded research strategy; decide which workflows/agents/tools are required |
| 2 | `/investigate` | KNOW | Target, E3, degrader & literature intelligence |
| 3 | `/reason` | REASON | Mechanistic reasoning across molecular & biological evidence |
| 4 | `/compare` | DISCOVER | Compare candidates & explain mechanistic differences |
| 5 | `/design` | DESIGN | Generate and prioritise new degrader candidates |
| 6 | `/optimize` | DESIGN | Diagnose + rationally improve an existing degrader/series |
| 7 | `/structure` | DESIGN | Ternary, interface & ubiquitination geometry reasoning |
| 8 | `/selectivity` | DISCOVER | Target/isoform/E3/proteome/cell-context selectivity |
| 9 | `/degradation` | DESIGN | DC50, Dmax, kinetics, hook-effect, mechanism |
| 10 | `/admet` | DESIGN | Molecular properties, permeability, developability |
| 11 | `/synthesis` | DISCOVER | Synthetic accessibility + retrosynthesis routes |
| 12 | `/experiment` | DISCOVER | Assays, controls and next experiments |
| 13 | `/evidence` | KNOW | Citations, provenance, confidence, uncertainty |
| 14 | `/run` | KNOW | Autonomously execute KNOW → REASON → DESIGN → DISCOVER |

Behaviour:

- A research workflow typed **without arguments** opens its evidence-grounded
  definition card (definition, phase, agents, example) — fast, no backend run.
- A research workflow typed **with an objective** is routed into the existing
  backend capabilities (agent graph / focused tools). Backend capabilities
  are preserved — never duplicated.
- `/admet <SMILES>` and `/synthesis <SMILES>` short-circuit to the direct
  RDKit-properties and retrosynthesis tool routes for instant one-line
  answers; multi-word objectives route through the graph.
- Legacy commands (`/validate`, `/retro`, `/docking`, `/stereo`,
  `/generator`, `/cellctx`, `/rank`, `/learn`, `/report`, `/contract`) remain
  functional and are grouped in `/help` as **low-level skill tools**.

Definitions registry: `RESEARCH_WORKFLOWS` in `tui/src/app.ts`; the header /
`/workflows` catalogue is seeded from the Python bridge
(`protacxtend/tui_bridge/events.py` → `RESEARCH_WORKFLOWS`, now exactly the
14 primary workflows above).

## 3. `/skills` — comprehensive capability catalogue

`/skills` is the full scientific catalogue organised into **18 categories**
(the header renderer groups backend skills by their `category` field):

```
Target biology · Warhead · E3 ligase · Linker · Ternary complex ·
Ubiquitination · Degradation · Selectivity · Cellular context ·
ADMET/developability · Chemistry · Synthesis · Candidate generation ·
Ranking/optimisation · Experimental design · Literature/evidence ·
Scientific reasoning · Reporting
```

- All 23 backend skills are tagged with a category
  (`protacxtend/tui_bridge/events.py`).
- Categories with no dedicated skill row show how they are exercised
  (Ubiquitination → `/structure`+`/degradation`; Cellular context →
  `/selectivity`; Experimental design → `/experiment`).
- `/skill <id>` shows a profile (category, api, description, run route);
  `/skill <id> <args>` also runs the skill.

## 4. Global CLI wiring

1. `package.json` `bin` → `{ "protacxtend": "dist/index.js" }`.
2. `#!/usr/bin/env node` added as the first line of `tui/src/index.ts`;
   TypeScript preserves it in `dist/index.js` (verified byte 0 = `#!`).
3. `npm link` symlinks the global `protacxtend` bin to the compiled entry
   (and marks it executable).
4. cwd independence:
   - The bridge resolves the project root from its **own file location**
     (`tui/dist` → repo root where `protacxtend/__init__.py` lives), never
     from `process.cwd()`.
   - The Python backend is spawned with `cwd = PROJECT_ROOT` **and**
     `PYTHONPATH` including the repo root, so `python -m
     protacxtend.tui_bridge.server` imports correctly from any launch dir.
5. The existing `cd tui && node dist/index.js` development path is unchanged.

## 5. Execution log (all steps requested)

| Step | Command / check | Result |
|------|-----------------|--------|
| Existing test suite | `npm test` (tui) | ✅ **38/38 pass** (incl. new global-CLI + backend integration tests) |
| Build | `npm run build` (tsc) | ✅ clean |
| Global link | `npm link` | ✅ `protacxtend` on PATH → `…/node_modules/@protacxtend/tui/dist/index.js` (exec bit set) |
| Launch from repo | pty `protacxtend` (cwd repo) | ✅ header, prompt, clean `/quit` |
| Launch from /tmp | pty `protacxtend` (cwd `/tmp`) | ✅ boots, `/status` reports repo `project root`, `/validate` returns props, `/run <objective>` streams agents |
| Python backend comms | bridge `ping`/`ready`; `/status`, `/skills`, `/databases` round-trips | ✅ |
| All 14 workflow cards | `/plan … /run` without args | ✅ 14/14 definition/strategy cards |
| System & catalogue commands | `/help /about /launch /contract /status /agents /workflows /skills /databases` | ✅ 9/9 |
| Tool one-liners | `/validate`, `/stereo`, `/admet <SMILES>`, `/skill stereochemistry <SMILES>` | ✅ single-line results |
| `/run <objective>` (args route) | agent-graph stream | ✅ `RUNNING WORKFLOW` → `◆ Supervisor [KNOW]` → `⛭ run_syn_glue_workflow` |
| /skills 18 categories | grouped catalogue render | ✅ incl. coverage notes for Ubiquitination / Cellular context / Experimental design |
| Wordmark | exact `PROTACXtend`, improved `tend` glyphs | ✅ (rendered header check) |
| CLI auto-tests | `tests/cli.test.ts` | ✅ bin mapping, shebang (src+dist), `/tmp` boot + backend + clean exit 0 |

### Notes / issues found & fixed during execution

1. **Python availability probe in tests** ran from `tui/` where the package
   is not importable → probe now runs with `cwd = repo root` (mirrors the
   bridge spawn); the live test then passes and skips only when the backend
   is genuinely absent.
2. **pty width 0** — some non-real terminals report 0×0 columns; Node then
   mis-renders (readline "Invalid count value"). The TUI now guards terminal
   width (`termWidth()` falls back to 100 for degenerate values) and the
   test harness sets a real window size — verified end-to-end.
3. **Marker-based interactive battery** is ANSI/line-wrap aware (gradient
   text is colourised per character; long definition text wraps) — all 28
   interactive checks PASS.

## 6. Not created yet (by design)

The final one-line installer (`install.sh` for fresh users:
`curl -fsSL https://raw.githubusercontent.com/the-ahuja-lab/PROTACXtend/main/install.sh | bash`)
is intentionally **not** created yet — requested after this freeze passes.

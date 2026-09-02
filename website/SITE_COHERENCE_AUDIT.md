# SITE_COHERENCE_AUDIT.md

Automated + manual coherence audit of `website/` against code, docs and the status
source of truth, run for the v2 scientific-coherence rewrite (2026-09-02).

## Checks performed (this run)

| Check | Command / method | Result |
|---|---|---|
| HTML structure, duplicate ids, broken in-page anchors | Python HTMLParser + regex scan of `website/index.html` | ✅ 31 ids, 0 duplicates, 0 missing anchor targets |
| JS syntax | `node --check website/app.js` | ✅ OK |
| Asset references resolve | scan `src/href="assets/..."` vs filesystem | ✅ logo.png, logo-square.png, 00_PROTACXtend_hero_visual.png all present |
| Status YAML parses | `yaml.safe_load(config/scientific_status.yaml)` | ✅ 9 top-level groups |
| Status tokens on page ⊆ sanctioned set | regex over `index.html` | ✅ VALIDATED BASELINE / TRAINED / PARTIAL / STRUCTURAL SURROGATE / DATA-GATED / UNDER EVALUATION / PLANNED (+YES/NO public-claim) — no invented statuses |
| Fast offline unit tests | `pytest … -m "not slow and not network"` | ✅ 17/17 passed (site/config/docs change only; code untouched) |
| External links | grep over `index.html` | ✅ all GitHub/lab links resolve to expected owners; `localhost:8001` only inside code examples |

## Website ↔ code/doc reconciliation (v2)

| Topic | Website now says | Code / doc source | Consistent |
|---|---|---|---|
| Node count | "23-node core + 8 controlled-search/feedback extensions = 31 documented nodes" | `agents/graph.py` (31 registered nodes); `AGENT_WORKFRAME.md` (23-core + 8-extension accounting) | ✅ (qualifier added: graph stops only at terminal gates) |
| Chemistry engine | 73 methods | `tools/protac_toolbox.py` | ✅ |
| Retrieval sources | Europe PMC · PubMed · OpenAlex · Crossref · SearXNG (configurable) | `research/sources.py` | ✅ |
| Module statuses | M1 validated baseline · M2 structural surrogate (real-PDB pending) · M3 data-gated surrogate · M4 trained · M5 trained (transcriptomic) · M6 planned · M7 planned | `protacxtend/modules/PROTACXTEND_MODULE_BUILD.md` + `config/scientific_status.yaml` | ✅ |
| Degradation predictors | Module 4, Module 5, TACK (DC50/Dmax/bin), SynGlue (DC50/Dmax) kept independent; unified engine under evaluation | model artifact paths in repo | ✅ |
| Cell context | transcriptomic only; proteotype not claimed; unseen-line transfer not claimed | Module 5 tracker text | ✅ |
| Workflows | real CLI subcommands: design · structure · dose · context · validate · contract · ask/learn/api | `protacxtend/cli.py` | ✅ (old /predict /dock /admet /audit /replicate slash set removed from docs too) |
| Install | git clone + docker; PyPI "on the roadmap" | PyPI 404 (checked); Dockerfile present | ✅ (pip-install claim removed everywhere incl. README/docs) |
| REST | POST /design · POST /mode · GET /health | `backend/api_routes.py` | ✅ |
| Release status | "v0.3 core release · active research development" | release lineage | ✅ ("final" removed from site; README badge updated) |
| Simulator | "Interactive pipeline walkthrough" + ILLUSTRATIVE DEMO | `website/app.js` hard-coded → honestly labelled | ✅ |
| Terminology | KNOW → REASON → DESIGN → DISCOVER; scientific contract; evidence badges | CLI `contract`; module tracker; config YAML | ✅ |
| "Feynman" branding | removed from site + AGENTS/AGENT_WORKFRAME + ARCHITECTURE header | → "scientific contract" / "audit rule" | ✅ (terminal UI help string in `cli.py` still says "Feynman-style TUI"; cosmetic, code-side, tracked as follow-up) |
| Tracker duplicates | stale duplicate Module-3 "pending" row removed | `PROTACXTEND_MODULE_BUILD.md` | ✅ |
| Dataset counts on site | 1913-row DB; DC50 1181 / Dmax 761; DepMap 24Q4 1512 rows | Module 5 tracker + `dataset.py` | ✅ (from tracker, not invented) |

## Known gaps / follow-ups (not silent)

1. **the-ahuja-lab/PROTACXtend hosting** — org repo exists but SaveenaSolanki has pull-only;
   code + Pages currently live at `SaveenaSolanki/PROTACXtend`. One org-side collaborator grant
   (`gh api -X PUT /repos/the-ahuja-lab/PROTACXtend/collaborators/SaveenaSolanki -f permission=push`)
   then `scripts/release_to_ahuja_lab.sh` mirrors everything; Pages URL moves to
   `https://the-ahuja-lab.github.io/PROTACXtend/` automatically.
2. `cli.py` "Feynman-style terminal UI" help string (code cosmetics).
3. `documentation/API_REFERENCE.md` still describes some legacy/older surface details; the
   website + WORKFLOWS.md are canonical; API_REFERENCE reconciliation is scheduled.
4. Unified degradation engine — keep labelled UNDER EVALUATION until validated.
5. Real-PDB benchmark for Module 2 and curated experimental-α dataset for Module 3 are open
   science items; they are exposed as limitations, not hidden.

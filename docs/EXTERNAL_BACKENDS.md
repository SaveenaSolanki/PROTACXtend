# EXTERNAL BACKENDS — repository-grounded matrix (2026-09-02 audit)

Full machine-readable matrix: `artifacts/backend_matrix.csv`.

Legend: installed = importable/dep present; wrapper = repo wrapper file;
callable = proven call path; runtime = wired into agent graph/CLI/API;
tested = unit tests exist; benchmarked = numeric benchmark evidence;
production-ready = safe default claim.

| Backend | Found in repo | Wrapper | Callable | Runtime | Tested | Benchmarked | Default state | Files | Notes / missing work |
|---|---|---|---|---|---|---|---|---|---|
| RDKit | core dep | internal | Y | Y | Y | Y | always | everywhere | chemistry backbone |
| Chemprop (degradation ML) | trained models | `chemprop_degradation.py` | Y | Y | Y | Y (G6, conformal) | trained, retrospective | `outputs/benchmark/chemprop*`, endpoint | prospective validation missing |
| ADMET-AI | isolated venv `.venvs/admet` | `admet_integration._run_admet_ai` | Y (venv) | Y | Y (venv-gated) | partial | rules fallback | `admet_integration.py`, `scripts/run_admet_ai.py` | endpoint set limited (AMES/DILI/hERG etc. per ADMET-AI); subprocess coupling |
| TACK model | joblib + clone | `tack_degradation.py` | Y | Y | Y | scaffold rho .80 | second opinion | `data/tack/*` | opinion-only role |
| P4ward (ternary) | docker image ref | `p4ward_wrapper.py` | Y (env-gated `PROTACPILOT_TEST_P4WARD`) | Y | gated tests | wiring-level | not in default CI | `deploy/p4ward_worker.py` | needs docker/local install; heavy |
| SE3-protacs / PROTAC-Model / PROTACFold / TERNIFY / SynGlue (orig) … 30+ clones | cloned under `data/protac_repos/repos` | partial (`external_model_adapters.py`, repo wrappers) | partial | N (core graph) | smoke only | none | unused | clones; isolated envs `.venvs/protac-*` | runtime census + benchmark needed |
| AlphaFold (DB) | client | `alphafold_client.py` | Y (network) | Y (ternary pLDDT gate) | network-skip tests | pLDDT gate | monomer fetch | `alphafold_client.py` | local cache optional |
| DepMap 24Q4 | cached raw + curated | M5 `omics.py` / M6 `context.py` | Y | Y | Y | M5 A-G, M6 retrieval | curated matrix committed | `outputs/omics_cache` (raw), module `data/` | no proteomics; 506 MB raw not committed |
| UniProt | client + cached annotations | `uniprot_client.py`/`lookup.py`; M6 `localization.py` | Y | Y | Y | annotation refresh | 78-gene cache | module data | broader gene coverage wanted |
| ChEMBL/BindingDB/PubChem/DrugBank | clients | `*_client.py` + `*_lookup.py` | Y (network) | Y | network-skip | binder census (history) | online | tools | API keys/network; client↔lookup duplication |
| ASKCOS | HTTP client | `retrosynthesis_engines.AskcosClient` | Y (network) | Y | Y | verified-synthesis briefs (history) | online optional | `retrosynthesis_engines.py` | offline default fallback |
| AiZynthFinder | optional env/pkg | `retrosynthesis_engines` (aizynth) | optional | N default | fallback tests | none | not default | data/synthesis_prediction envs | install + wiring |
| Link-INVENT (official) | **not installed** | internal style scorer only | N (official) | N | internal tests | internal rho .80 | re-implementation | `linker_scoring.py` | official pkg integration optional |
| Rosetta/PRosettaC/MegaDock/COMPASS/Boltz/OpenMM/GROMACS | N (no wrapper evidence) | N | N | N | N | N | absent | `work/boltz_output` = attempted run only | not integrated |
| Open Targets / HPA / SwissADME-like / admetSAR | N | N | N | N | N | N | absent | — | — |
| LangGraph + LLM providers (ollama/openai/anthropic/google) | deps | `agentic_core.py`, gateway | Y | Y (agentic mode) | architecture tests | e2e deterministic (default mode) | deterministic default | `agents/runtime.py` | deterministic mode is default; LLM mode optional |

**Key honesty rule (audit):** wrappers around external tools ≠ internal
complete implementations. Only RDKit, Chemprop, TACK, DepMap-derived, M1–M6
internal mathematics/ML and the internal linker model are "internal";
everything else is an external delegate whose absence must degrade gracefully
(and does in most call paths).

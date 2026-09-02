# PROTACXtend Workflows & CLI

Reproducible workflows from research question to candidate dossier. The CLI exposes the
real scientific surface of the platform (`protacxtend --help` / `protacxtend capabilities`
to list everything); every workflow writes structured output and cites the model or
evidence layer that produced it.

Scientific framing: **KNOW → REASON → DESIGN → DISCOVER**.

---

## CLI subcommand overview

| Command | Action | Touches (evidence/model layer) |
| :--- | :--- | :--- |
| `design` | Deterministic end-to-end candidate generation (core 23-node path) | resolution → assembly → ADMET/novelty → degradation → ranking |
| `structure` | Pose-backed lysine-ubiquitination geometry + cooperativity feasibility | Module 2, Module 3 (structural surrogate) |
| `dose` | Ternary dose-response & hook-effect risk simulation | Module 1 (equilibrium, MC uncertainty) |
| `context` | Cell-context-aware degradation prediction adapter | Module 5 (transcriptomic) |
| `validate` | Validate & score a PROTAC SMILES (RDKit + ADMET) | chemistry engine |
| `ternary` | Ternary-feasibility mode for one SMILES | P4ward / SE(3) feasibility |
| `proteome` | Cell-context selectivity risk scoring (transcriptomic proxy) | Module 5 features |
| `contract` | Show KNOW-REASON-DESIGN-DISCOVER contracts & dossiers | trace / evidence layer |
| `ask` | Search tools, databases, skills and local literature context | retrieval + local assets |
| `learn` | Lock predictions or recommend next active-learning batch | Module 7 (partial — BO loop planned) |
| `external` | Show/launch external model/tool integration smoke jobs | repo wrappers |
| `run` | Run the unified PROTACXtend runtime | agents/graph.py |
| `status` / `scenarios` / `capabilities` | Runtime diagnostics and capability listing | — |
| `api` / `ui` / `tui` | FastAPI backend, Streamlit frontend, terminal UI | — |

---

## 1. `design` — end-to-end candidate generation

```bash
protacxtend design --target "BRD4" --e3 "CRBN" --num-candidates 16 \
  --output ./results/brd4_run.json
```

**What happens inside (core scientific workflow):**
1. Objective parsed; design plan committed; search space bounded; safety precheck.
2. UniProt / ChEMBL target resolution; binder & warhead evidence retrieval/ranking; E3 selection;
   exit-vector detection.
3. Linker generation (73-method engine: curated + rule-based + generative), component-aware
   construction, stereoisomer enumeration, RDKit validation, cell-context feature scoring.
4. ADMET, novelty and applicability-domain checks; degradation ML (Module 4).
5. Ranking with diversity clustering, reflection review and evolution refinement;
   controlled-search extensions (expensive-modeling selection, ternary / cooperativity /
   hook-effect gates, final ranking, report, memory) follow when their gates open.

---

## 2. `structure` — ubiquitination geometry & cooperativity feasibility

```bash
protacxtend structure --smiles "<PROTAC_SMILES>" --target-pdb 3U5L --e3-pdb 4CIW
```

- Module 2 (lysine ubiquitination feasibility): static-geometry scorer — E2 catalytic-site
  geometry, POI lysines, SASA, distance/approach angle, steric occlusion, ensemble productive
  fraction. *Status: structural surrogate; real-PDB benchmark pending.*
- Module 3 (cooperativity): feasibility score in surrogate mode. *Status: data-gated —
  experimental-α prediction requires a curated experimental dataset.*

---

## 3. `dose` — hook-effect / three-body equilibrium

```bash
protacxtend dose --smiles "<PROTAC_SMILES>"
```

Mass-action three-body equilibrium over binary and ternary species: peak and maximum ternary
occupancy, hook onset and severity, dose window, seeded Monte-Carlo uncertainty (Module 1,
validated baseline). **Equilibrium modeling only — not degradation kinetics.**

---

## 4. `context` — cell-context-aware degradation prediction

```bash
protacxtend context --smiles "<PROTAC_SMILES>" --cell-line "HeLa"
```

Module 5 adapter: pDC50 conditioned on transcriptomic features (DepMap 24Q4). The output
reports which model produced it, its applicability-domain state and its limitation
(transcriptomic only; proteotype and unseen-cell-line transfer are **not** claimed).

---

## 5. `validate` — single-candidate chemistry gate

```bash
protacxtend validate --smiles "CC1=C(C=C(C=C1)NC(=O)C2=CC=C(C=C2)CN3CCN(CC3)C)C4=NC=CN4"
```

RDKit sanitization, exit-vector awareness, ADMET profile (hERG · AMES · BBB ·
Lipinski/Veber). Returns a PASS/WARN verdict with per-check detail.

---

## 6. `contract` — scientific dossier / decision trace

```bash
protacxtend contract --target "BRD4" --e3 "CRBN"
protacxtend contract --session-id "session_20260731_1542"
```

Renders the KNOW-REASON-DESIGN-DISCOVER dossier: what was retrieved (and verified), which
design decisions were made, which mechanistic/model layers ran, and the evidence trace with
applicability-domain and limitation states.

---

## 7. Research surface

```bash
protacxtend ask "HMGB2 degradation E3 options"     # databases + literature + local assets
protacxtend learn                                   # next-experiment recommendations (partial)
protacxtend external                                # external repo/model integration smoke jobs
```

---

## Serving

```bash
protacxtend api          # FastAPI backend   (default :8001) — POST /design · POST /mode · GET /health
protacxtend ui           # Streamlit frontend (default :8501)
protacxtend tui          # terminal UI
```

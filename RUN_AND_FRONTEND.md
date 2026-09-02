# RUN_AND_FRONTEND.md — How to run PROTACXtend, access the frontend, and where we are

_Verified against the code on 2026-08-12 (ports, entry points, commands)._

---

## 1. What this is (30-second answer)

PROTACXtend is a research-grade **agentic PROTAC design platform**: a LangGraph
pipeline (real tools: live ChEMBL binders, trained Chemprop + TACK degradation,
ADMET-AI, AiZynthFinder retrosynthesis, SE3/P4ward ternary, NSGA-II ranking)
with an LLM advisory layer (gpt-oss:20b, Ollama), human gates, persistent
checkpoints, an auditable `AgentRunRecord` per run, a REST API and a Streamlit
frontend.

**Current stage:** v0.3.0-agentic-core **closed and frozen** (tag + GitHub
release). Post-release hardening on branches: generative linker model,
Link-INVENT scoring/optimizer, TACK degradation cross-check, bounded evolution,
binder census, architecture-update implementation. CI green (smoke,
full-offline incl. 6-scenario e2e, security).

---

## 2. Prerequisites

```bash
# conda env (the working runtime)
conda activate protacpilot          # or: /home/saveenas/miniconda3/envs/protacpilot

# external assets (one-time; downloads figshare/Zenodo models + clones)
./scripts/bootstrap_assets.sh --aizynth      # retrosynthesis models (~960 MB)
./scripts/bootstrap_assets.sh --repos        # upstream PROTAC repos (CI/benchmarks)
./scripts/bootstrap_assets.sh --admet        # ADMET-AI isolated venv (~2 GB, once)
./scripts/bootstrap_assets.sh --dry-run      # verify URLs without downloading

# LLM layer (optional; deterministic fallback when absent)
ollama serve                                 # host :11435
ollama pull gpt-oss:20b                      # once
```

The trained degradation models, TACK models, linker generator, e3 library and
PROTAC-DB-3.0 are **already in the repo** — no download needed for the core.

---

## 3. Run — three ways

### 3a. Quick scientist API (no server)

```python
from synglue_agent.agents.runtime import run_protacpilot

r = run_protacpilot(
    "Design CRBN-recruiting PROTAC candidates against BRD4 with cellular "
    "degradation as the primary objective.",
    mode="agentic",                      # "deterministic" = v0.1 fixed pipeline
    config={"run_id": "my_run", "persistent": False},
)
print(r["status"])
# auditable artifact:
#   outputs/runs/my_run/run.json (+ decisions.jsonl, evidence.jsonl,
#   candidates.parquet, pareto_front.csv, report.md)
```

### 3b. REST API (FastAPI)

```bash
python -m uvicorn synglue_agent.backend.api_routes:get_app \
    --factory --host 0.0.0.0 --port 8001
# or dockerised:
docker compose -f deploy/docker-compose.yml up -d api worker
```

Endpoints (host :8001):
| Route | Purpose |
|---|---|
| `/health` | liveness |
| `/design` | deterministic design (POST `{"request": "..."}`) |
| `/agentic-design` | agentic design (POST) |
| `/mode validate` | mode validation |
| `/llm/status` | LLM provider status |
| `/docs` | OpenAPI UI |

```bash
curl -s -X POST http://127.0.0.1:8001/agentic-design \
  -H 'Content-Type: application/json' \
  -d '{"request": "Design CRBN PROTACs against BTK"}'
```

### 3c. Frontend UI (Streamlit)

```bash
python -m streamlit run synglue_agent/app/streamlit_app.py
# opens at http://localhost:8501
```

In the UI:
1. Type a natural-language design request (e.g., the BRD4 prompt above).
2. Pick **mode** (deterministic vs agentic) and LLM provider in the sidebar.
3. Run → see candidates, predictions, pareto ranking, report, trace.
4. Sidbar also has the **HERUKA.AI channel** (export/push the auditable bundle
   to your heruka.ai frontend via `HERUKA_WEBHOOK_URL`).

Full stack (optional): `docker compose -f deploy/docker-compose.yml up -d`
starts api (:8001) + worker + postgres (:5433) + redis (:6378) + ollama
(checkpoint persistence + job queue).

---

## 4. Tests & sanity

```bash
python -m pytest synglue_agent/tests/ synglue_agent/agents/test_ternary_stage.py \
  -m "not slow" -q                     # fast suite (333+)
python scripts/ci_smoke.py             # asset-free smoke (8 checks)
python scripts/e2e_agentic.py --offline # 6 agentic e2e scenarios
python scripts/audit_md_vs_code.py     # docs-vs-code audit
python scripts/build_audit_xls.py      # regenerate TOOL_AUDIT.xlsx
```

---

## 5. Where we are (stage map)

```
v0.1 fixed pipeline ──▶ v0.3 agentic core (CLOSED, tag v0.3.0-agentic-core)
   │                        │
   │                        ├─ 22-23 agents, real graph nodes (was: stubs)
   │                        ├─ trained degradation (chemprop ρ=0.783)
   │                        ├─ E3 library 19 groups / 114 ligands
   │                        ├─ live ChEMBL/PubChem, AiZynthFinder routes
   │                        ├─ CI smoke/full-offline/security green
   │                        └─ GitHub: protected branches, release, dependabot
   │
   └── post-release on branches (not yet merged):
         generative linker (char-GRU) + Link-INVENT scoring & REINFORCE
         optimizer ▪ TACK degradation cross-check (ρ=0.80) ▪ bounded evolution
         with novelty termination ▪ binder census (InChIKey, n_reported_total)
         ▪ 12' ternary→degradation revision ▪ AGENT_ARCHITECTURE_UPDATE
         implementation status ▪ TOOL_AUDIT.xlsx ▪ this guide
```

**Verified numbers to quote:** 333+ fast tests; e2e 6/6; benchmark ρ=0.783
(chemprop) and ρ=0.800 (TACK-style); LLM 17/17 role cases, 0 safety
violations; container boot-test with real model output; gitleaks-clean history
(7.93 GiB → ~100 MiB, no secrets).

**Honest caveats:** research-grade, no wet-lab validation; conformal intervals
wide (±1.4 log10) — trust ranking over absolute DC50; ternary P4ward
calibration campaign pending (compute); bindingdb/drugbank need credentials;
evolution climbs a trained-but-in-domain hill; patent coverage = PubChem
(SureChEMBL API retired).

**Suggested next steps** (in priority order, from deep-research review): merge
the hardening branches (linker-generative, degradation-agent-fix, doc-audit,
research-pipeline-gaps) after CI; run the 8–12-candidate P4ward calibration
campaign; wire a GTEx/ELiAH static E3-expression snapshot; then v0.4.0 planning.
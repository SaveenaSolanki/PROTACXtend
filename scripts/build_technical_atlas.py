#!/usr/bin/env python3
"""Build the code-backed technical-atlas machine tables.

Every row is generated from a live registry/artifact (never hand-typed).
Writes to docs/architecture/tables/ and docs/architecture/diagrams/.
"""
from __future__ import annotations

import csv, hashlib, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "architecture", "tables")
DIA = os.path.join(ROOT, "docs", "architecture", "diagrams")
os.makedirs(OUT, exist_ok=True)
os.makedirs(DIA, exist_ok=True)

sys.path.insert(0, ROOT)


def write_csv(name, rows, cols):
    p = os.path.join(OUT, name)
    with open(p, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in rows:
            w.writerow([r.get(c, "") for c in cols])
    with open(p + ".sha256", "w") as f:
        f.write(hashlib.sha256(open(p, "rb").read()).hexdigest())
    print("wrote", p, "rows:", len(rows))
    return p


# ---------------------------------------------------------------- 1. workflow nodes
import warnings
warnings.filterwarnings("ignore")
from protacxtend.agents.graph import LocalSynGlueWorkflowGraph, CAPABILITY_NODES

graph = LocalSynGlueWorkflowGraph()
node_rows = []
node_stage = {}
for stage, names in CAPABILITY_NODES.items():
    for n in names:
        node_stage.setdefault(n, []).append(stage)
for idx, (name, fn) in enumerate(graph.nodes, 1):
    cls = getattr(getattr(fn, "__self__", None), "__class__", None)
    node_rows.append({
        "node_index": idx,
        "node": name,
        "executor_class": getattr(cls, "__name__", "") or fn.__name__,
        "executor_module": (cls.__module__ if cls is not None else "protacxtend.agents.graph"),
        "pillar": "/".join(sorted(set(node_stage.get(name, ["CORE"])))),
        "registered_in": "agents/graph.py:LocalSynGlueWorkflowGraph.nodes",
    })
write_csv("workflow_nodes.csv", node_rows,
          ["node_index", "node", "executor_class", "executor_module", "pillar", "registered_in"])

# ---------------------------------------------------------------- 2. agent tools
from protacxtend.agentic.registry import registry_specs

specs = registry_specs(ready_only=True)
tool_rows = []
for s in specs:
    tool_rows.append({
        "name": s.get("name"),
        "purpose": (s.get("description") or s.get("purpose") or ""),
        "executor": "protacxtend/agentic/registry.py:_EXECUTORS",
        "registered_in": "agentic/registry.py:TOOL_SPECS",
        "readiness": s.get("readiness", "ready"),
    })
write_csv("agent_tools.csv", sorted(tool_rows, key=lambda r: r["name"]),
          ["name", "purpose", "executor", "registered_in", "readiness"])

# ---------------------------------------------------------------- 3. toolkit tools (115)
import importlib
tk = importlib.import_module("protacxtend.tools.toolkit_registry")
entries = tk.get_toolkit_registry()
if not isinstance(entries, list):
    entries = entries.get("tools", [])
tk_rows = []
for e in entries:
    tk_rows.append({
        "tool_name": e.get("tool_name"),
        "category": e.get("category"),
        "subcategory": e.get("subcategory"),
        "purpose": e.get("purpose"),
        "executable_type": e.get("executable_type"),
        "license_type": e.get("license_type"),
        "commercial": e.get("commercial", ""),
        "local_executable": e.get("local_executable", ""),
        "web_service": e.get("web_service", ""),
        "status": e.get("status", "registered_but_not_executable"),
        "registered_in": "tools/toolkit_registry.py:get_toolkit_registry",
    })
write_csv("toolkit_tools.csv", tk_rows,
          ["tool_name", "category", "subcategory", "purpose", "executable_type",
           "license_type", "commercial", "local_executable", "web_service", "status",
           "registered_in"])

# ---------------------------------------------------------------- 4. scientific backends (19)
from protacxtend.scientific_backends.registry import Capability, load_backends

be = load_backends()
be_rows = []
for cap in Capability:
    spec = be.resolve_one(cap) if hasattr(be, "resolve_one") else None
    regd = getattr(spec, "registered", []) if spec else []
    usable = getattr(spec, "usable", []) if spec else []
    best = getattr(spec, "best", "") if spec else ""
    be_rows.append({
        "capability": cap.value if hasattr(cap, "value") else str(cap),
        "best_backend": best if not isinstance(best, list) else ",".join(map(str, best)),
        "usable_backends": ",".join(map(str, usable)),
        "registered_backends": ",".join(map(str, regd)),
        "registered_in": "scientific_backends/registry.py:REGISTRY + Capability enum",
        "status": "ready (free/local)" if (usable or best) else "registered",
    })
write_csv("scientific_backends.csv", be_rows,
          ["capability", "best_backend", "usable_backends", "registered_backends",
           "registered_in", "status"])

# ---------------------------------------------------------------- 5. TPD capability classes (27)
cap_rows = []
with open(os.path.join(ROOT, "sota", "data", "escalation_capabilities.csv"), newline="") as f:
    for r in csv.DictReader(f):
        cap_rows.append({
            "capability": r.get("capability"),
            "description": r.get("description"),
            "fallbacks": r.get("fallbacks"),
            "n_fallbacks": r.get("n_fallbacks"),
            "registered_in": "sota/data/escalation_capabilities.csv (escalation self-healing taxonomy)",
        })
write_csv("tpd_capabilities.csv", cap_rows,
          ["capability", "description", "fallbacks", "n_fallbacks", "registered_in"])

# ---------------------------------------------------------------- 6. functionalities (108, pillars)
func_rows = []
with open(os.path.join(ROOT, "sota", "data", "functionalities.csv"), newline="") as f:
    for r in csv.DictReader(f):
        func_rows.append({k: (r.get(k) or "") for k in (
            "fid", "domain", "subcategory", "functionality", "stage", "evidence",
            "implementation", "agents", "tools", "module", "status")})
write_csv("functionalities.csv", func_rows,
          ["fid", "domain", "subcategory", "functionality", "stage", "evidence",
           "implementation", "agents", "tools", "module", "status"])

# ---------------------------------------------------------------- crosswalk
cm_rows = []
with open(os.path.join(ROOT, "results", "tool_depth", "capability_matrix.csv"), newline="") as f:
    for r in csv.DictReader(f):
        if r.get("surface") == "agent_adapter":
            cm_rows.append(r)
cx_rows = []
for r in cm_rows:
    cx_rows.append({
        "agent_tool": r.get("display_name"),
        "pillar": r.get("stage"),
        "biological_question": r.get("biological_question"),
        "implementation_module": r.get("implementation_module"),
        "source_connector": r.get("source_connector_or_library"),
        "package_version": r.get("package_version"),
        "typed_output": r.get("return_schema"),
        "evidence_type": r.get("evidence_type"),
        "failure_code": r.get("failure_code"),
        "fallback_route": r.get("fallback_route"),
        "matched_permitted_ids": r.get("matched_permitted_ids"),
        "validation_level": r.get("validation_level"),
        "real_input_run_outcome": r.get("run_outcome"),
        "artifact_source": "results/tool_depth/capability_matrix.csv",
    })
write_csv("crosswalk.csv", sorted(cx_rows, key=lambda r: (r["pillar"], r["agent_tool"])),
          ["agent_tool", "pillar", "biological_question", "implementation_module",
           "source_connector", "package_version", "typed_output", "evidence_type",
           "failure_code", "fallback_route", "matched_permitted_ids",
           "validation_level", "real_input_run_outcome", "artifact_source"])

# edge-level crosswalk: dataflow_edges (26 source->tool->output edges)
edge_rows = []
with open(os.path.join(ROOT, "results", "tool_depth", "dataflow_edges.csv"), newline="") as f:
    for r in csv.DictReader(f):
        edge_rows.append({k: (r.get(k) or "") for k in (
            "stage", "source_id", "normalized_entity", "tool_or_module", "typed_output",
            "strategy_field", "example_run_id", "example_outcome", "evidence_tier",
            "failure_path", "fallback_route")})
write_csv("dataflow_edges.csv", edge_rows,
          ["stage", "source_id", "normalized_entity", "tool_or_module", "typed_output",
           "strategy_field", "example_run_id", "example_outcome", "evidence_tier",
           "failure_path", "fallback_route"])

# ---------------------------------------------------------------- mermaid diagrams
def mmd(name, body):
    p = os.path.join(DIA, name)
    with open(p, "w") as f:
        f.write(body)
    print("wrote", p)

mmd("architecture_overall.mmd", """flowchart TD
    U[User text / TUI / API / CLI] --> P[parse_request<br/>protacxtend/request/parser.py]
    P --> R[resolve_target<br/>request/resolver.py (curated -> UniProt -> supplemental)]
    R --> D[decision / corrections<br/>request/decision.py · request/corrections.py]
    D --> PL[planner<br/>planning/goal_planner.py · /plan]
    PL --> G[workflow nodes<br/>agents/graph.py · 34 nodes]
    G --> T[LLM tool call<br/>agentic/registry.py · 34 executors]
    T --> K[toolkit adapter<br/>tools/toolkit_registry.py · 115 entries]
    K --> B[scientific backend / data source<br/>scientific_backends/registry.py · 19 capabilities]
    B --> E[evidence store<br/>canonical/evidence.py · evidence.jsonl]
    E --> C[critic / decision<br/>canonical/critic.py · decision.py]
    C --> A[report / artifacts<br/>reporting/reporter.py · strategies · outputs/]
    T -. abstain / not_available .-> E
    K -. fallback route .-> K
""")
mmd("pillar_know.mmd", """flowchart LR
    KQ[KNOW: what is known about target?]
    KQ --> S1[search_europe_pmc / search_pubmed / deep_research]
    KQ --> S2[resolve_target / search_uniprot]
    KQ --> S3[retrieve_target_binders / search_chembl / search_pubchem / search_bindingdb]
    KQ --> S4[retrieve_pdb / retrieve_fulltext / verify_crossref]
    S1 --> EK[evidence: RETRIEVED -> evidence.jsonl]
""")
mmd("pillar_reason.mmd", """flowchart LR
    RQ[REASON: which E3 / why degradable?]
    RQ --> E1[select_e3_ligase / retrieve_e3_evidence]
    RQ --> E2[predict_cell_context / predict_cooperativity / simulate_hook_effect]
    RQ --> E3[run_scientific_capability / list_capability_readiness]
    E1 --> ER[evidence: catalog / ML prediction -> evidence.jsonl]
""")
mmd("pillar_design.mmd", """flowchart LR
    DQ[DESIGN: assemble candidates]
    DQ --> C1[inspect_smiles / detect_exit_vectors / generate_linkers]
    DQ --> C2[construct_protac / check_synthetic_feasibility]
    DQ --> C3[model_ternary_complex / score_lysine_ubiquitination / retrieve_pdb]
    C1 --> C2 --> C3
    C2 --> DX[artifact: candidates.csv / structures/ (RDKit-valid or design brief)]
""")
mmd("pillar_discover.mmd", """flowchart LR
    SQ[DISCOVER: rank and decide]
    SQ --> P1[predict_degradation / predict_admet / predict_cell_context]
    SQ --> P2[rank_candidates / build_candidate_dossier / simulate_hook_effect]
    SQ --> P3[run_protacpilot_structural]
    P1 --> P2 --> PX[artifact: pareto_front.csv + dossier]
""")
mmd("agent_core.mmd", """flowchart TD
    W[workflow node] -->|ToolRun record| ST[state store: WorkflowState]
    W -->|evidence records| E[evidence store: canonical/evidence.py]
    W -->|decisions| D[decisions.jsonl]
    W -->|memory write| M[memory: protacxtend/memory + protacxtend-memory (opt-in)]
    E --> P[provenance: run_records.py · AgentRunRecord · reproducibility_hash]
    C[critic: canonical/critic.py] --> V[verdict: REVISE / INSUFFICIENT EVIDENCE / SUPPORTED]
    F{failure/abstention} -->|typed failure code| W
    F -->|fallback route| W
""")
mmd("tui_wireframe.mmd", """flowchart TB
    subgraph TUI["TUI (Node bridge -> tui_bridge/server.py)"]
        I[Interpreted query<br/>/plan EGFR protac -> Target: EGFR [P00533]] --> S[Current stage indicator]
        S --> E[Evidence + tools used]
        E --> A[Intermediate artifacts links]
        A --> R[Concise result]
        R --> T[Technical report (expandable)]
        T --> U[Uncertainty / open questions]
        U --> D[Downloads: answer.json · CSVs · raw strategy]
    end
""")
print("all tables + diagrams written")
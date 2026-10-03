#!/usr/bin/env python
"""Build the tool-depth audit deliverables requested by the figure prompt.

Outputs (all under ``results/tool_depth/``):

* ``capability_matrix.csv``    one row per unique capability/backend
* ``count_reconciliation.md``  definitions + evidence for every competing count
* ``dataflow_edges.csv``       source -> entity -> tool -> typed output -> strategy field
* ``Figure_A_architecture.{svg,pdf,png}``
* ``Figure_B_toolkit_depth.{svg,pdf,png}``
* ``Figure_C_mechanistic_evidence.{svg,pdf,png}``
* ``FIGURE_CAPTIONS.md``

Everything is derived from repository artifacts.  Where a field is not backed by
a run it is written ``not_measured`` / ``registered_only``; nothing is inferred.

Usage::

    python scripts/build_tool_depth.py
"""
from __future__ import annotations

import csv
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("PROTACXTEND_EXECUTION_MODE", "scientific")

ROOT = Path(__file__).resolve().parents[1]
import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = ROOT / "results" / "tool_depth"
CLOSURE = ROOT / "results" / "closure"
SOTA = ROOT / "sota" / "data"

# ── colour-blind-safe palette (Okabe–Ito derived) ─────────────────────────
C = {
    "know": "#0072B2", "reason": "#009E73", "design": "#D55E00",
    "discover": "#CC79A7", "core": "#666666", "gate": "#E69F00",
    "stop": "#B2182B", "measured": "#009E73", "modeled": "#56B4E9",
    "unknown": "#BBBBBB", "ink": "#222222",
}


def apply_style() -> None:
    plt.rcParams.update({
        "figure.dpi": 150, "savefig.dpi": 600,
        "font.size": 9, "font.family": "DejaVu Sans",
        "svg.fonttype": "none", "pdf.fonttype": 42,
        "axes.spines.top": False, "axes.spines.right": False,
    })


def save_all(fig, stem: str, *, size_in: float = 11.0) -> None:
    fig.set_size_inches(size_in, size_in)
    fig.savefig(OUT / f"{stem}.png", dpi=600, facecolor="white")
    fig.savefig(OUT / f"{stem}.pdf", facecolor="white")
    fig.savefig(OUT / f"{stem}.svg", facecolor="white")
    plt.close(fig)


# ══════════════════════════════════════════════════════════════════════
# 1. Load the frozen evidence
# ══════════════════════════════════════════════════════════════════════

def load_inputs() -> dict:
    e1 = list(csv.DictReader((CLOSURE / "e1_tool_matrix.csv").open()))
    proportions = json.loads((CLOSURE / "e1_proportions.json").read_text())
    recon = json.loads((CLOSURE / "e1_registry_reconciliation.json").read_text())
    disposition = json.loads((ROOT / "outputs" / "tool_disposition.json").read_text())
    adapter_audit = json.loads((ROOT / "outputs" / "adapter_audit.json").read_text())
    functionalities = list(csv.DictReader((SOTA / "functionalities.csv").open()))
    workflow_nodes = list(csv.DictReader((SOTA / "workflow_nodes.csv").open()))
    backends = list(csv.DictReader((SOTA / "scientific_backends.csv").open()))
    headline = {r["metric"]: r for r in csv.DictReader((SOTA / "headline_counts.csv").open())}
    from protacxtend.agentic.registry import TOOL_SPECS
    from benchmark_runner.matched_tools import MATCHED_TOOLS
    from protacxtend.tools.toolkit_registry import TOOLKIT_REGISTRY
    from protacxtend.toolkit.registry import load_toolkit_registry
    reg = load_toolkit_registry()
    return {
        "e1": e1, "proportions": proportions, "recon": recon,
        "disposition": disposition, "adapter_audit": adapter_audit,
        "functionalities": functionalities, "workflow_nodes": workflow_nodes,
        "backends": backends, "headline": headline,
        "specs": {s["name"]: s for s in TOOL_SPECS},
        "matched": MATCHED_TOOLS, "toolkit_tools": TOOLKIT_REGISTRY,
        "reg_tools": {t["id"]: t for t in reg["tools"]},
    }


# ══════════════════════════════════════════════════════════════════════
# 2. capability_matrix.csv
# ══════════════════════════════════════════════════════════════════════

#: Curated, code-grounded metadata for the 34 callable adapters.  Keys are the
#: exact registry tool names.  ``source`` is the connector/library the adapter
#: calls; ``fallback`` is the executed or declared alternate route.
ADAPTER_META: dict[str, dict] = {
    # KNOW
    "deep_research": dict(impl="agentic.registry:exec_deep_research", source="Europe PMC + PubMed + CrossRef REST",
                          lib="urllib", units="free text", ret="records[] (id, source, title)", fallback="search_europe_pmc|search_pubmed"),
    "search_europe_pmc": dict(impl="agentic.registry:exec_europe_pmc", source="Europe PMC REST", lib="urllib",
                              units="free text", ret="records[]", fallback="search_pubmed"),
    "search_pubmed": dict(impl="agentic.registry:exec_pubmed", source="NCBI E-utilities", lib="urllib",
                          units="free text", ret="records[]", fallback="search_europe_pmc"),
    "verify_crossref": dict(impl="agentic.registry:exec_crossref", source="CrossRef REST", lib="urllib",
                            units="DOI", ret="citation metadata", fallback="none (typed not_available)"),
    "retrieve_fulltext": dict(impl="agentic.registry:exec_retrieve_fulltext", source="Europe PMC full text", lib="urllib",
                              units="PMCID", ret="section text", fallback="none"),
    "search_web": dict(impl="agentic.registry:exec_search_web", source="SearXNG (self-hosted)", lib="urllib",
                       units="free text", ret="results[]", fallback="none (requires endpoint)"),
    "resolve_target": dict(impl="agentic.registry:exec_resolve_target", source="UniProt REST", lib="urllib",
                           units="gene/protein name", ret="accession, reviewed flag", fallback="search_uniprot"),
    "search_uniprot": dict(impl="agentic.registry:exec_resolve_target", source="UniProt REST", lib="urllib",
                           units="free text", ret="accession", fallback="none"),
    "retrieve_target_binders": dict(impl="agentic.registry:exec_chembl_molecules", source="ChEMBL REST", lib="urllib",
                                    units="target name", ret="molecules[]", fallback="search_bindingdb"),
    "search_pubchem": dict(impl="agentic.registry:exec_search_pubchem", source="PubChem PUG-REST", lib="urllib",
                           units="name/SMILES", ret="CID, canonical SMILES", fallback="search_chembl"),
    "search_chembl": dict(impl="agentic.registry:exec_chembl_molecules", source="ChEMBL REST", lib="urllib",
                          units="name", ret="molecules[]", fallback="search_pubchem"),
    "search_bindingdb": dict(impl="agentic.registry:exec_search_bindingdb", source="local BindingDB snapshot", lib="csv",
                             units="target", ret="binders[]", fallback="retrieve_target_binders"),
    # REASON
    "select_e3_ligase": dict(impl="agentic.registry:exec_select_e3_ligase", source="local curated E3 catalog", lib="csv",
                             units="target", ret="ranked E3 list", fallback="retrieve_e3_evidence"),
    "retrieve_e3_evidence": dict(impl="agentic.registry:exec_ligase_evidence", source="E3 opportunity catalog", lib="csv",
                                 units="E3 family", ret="evidence rows[]", fallback="none"),
    "predict_cell_context": dict(impl="agentic.registry:exec_predict_cell_context", source="expression_context.csv + cell_context_atlas.csv", lib="sklearn",
                                 units="(protac, cell_line, poi, e3)", ret="ML prediction + CI", fallback="heuristic_fallback"),
    "diagnose_capability": dict(impl="agentic.registry:exec_diagnose_capability", source="escalation/toolkit catalog", lib="stdlib",
                                units="capability id", ret="ranked fallbacks[]", fallback="none"),
    "list_capability_readiness": dict(impl="agentic.registry:exec_list_capability_readiness", source="escalation registry", lib="stdlib",
                                      units="limit", ret="readiness[]", fallback="none"),
    "list_scientific_capabilities": dict(impl="agentic.registry:exec_list_scientific_capabilities", source="scientific_backends", lib="stdlib",
                                         units="none", ret="capability[]", fallback="none"),
    "run_scientific_capability": dict(impl="agentic.registry:exec_run_scientific_capability", source="scientific_backends", lib="stdlib",
                                      units="capability + params", ret="typed backend result", fallback="CAPABILITY_UNAVAILABLE"),
    # DESIGN
    "inspect_smiles": dict(impl="agentic.registry:exec_validate_smiles", source="RDKit", lib="rdkit", units="SMILES",
                           ret="validity, descriptors", fallback="none"),
    "detect_exit_vectors": dict(impl="agentic.registry:exec_detect_exit_vectors", source="RDKit", lib="rdkit", units="SMILES",
                                ret="exit-vector atom list", fallback="none"),
    "generate_linkers": dict(impl="agentic.registry:exec_generate_linkers", source="curated + rule + generative linker engines", lib="rdkit",
                             units="count", ret="linker SMILES[]", fallback="rule-based"),
    "construct_protac": dict(impl="agentic.registry:exec_construct_protac", source="RDKit composition", lib="rdkit",
                             units="(warhead, linker, e3) SMILES", ret="PROTAC SMILES + descriptors", fallback="none"),
    "check_synthetic_feasibility": dict(impl="agentic.registry:exec_check_synthetic_feasibility", source="retrosynthesis templates (AiZynthFinder)", lib="aizynthfinder",
                                        units="SMILES", ret="route feasibility", fallback="heuristic filter (probe disabled AiZynth)"),
    "retrieve_pdb": dict(impl="agentic.registry:exec_retrieve_pdb", source="RCSB PDB + local structures", lib="urllib", units="(target, e3)",
                         ret="structure handles", fallback="local structure dir"),
    "model_ternary_complex": dict(impl="agentic.registry:exec_model_ternary_complex", source="local ternary pipeline / PROTACpilot proxy", lib="numpy",
                                  units="(target, e3, linker)", ret="contacts + proxy score (no coords)", fallback="heuristic_fallback"),
    "score_lysine_ubiquitination": dict(impl="agentic.registry:exec_score_lysine_ubiquitination", source="structural geometry proxy", lib="biopython",
                                        units="(target, e3, PDB paths)", ret="geometry score (partial)", fallback="none (partial output)"),
    "predict_cooperativity": dict(impl="agentic.registry:exec_predict_cooperativity", source="cooperativity surrogate + pose", lib="numpy",
                                  units="(warhead, linker, e3, pose)", ret="alpha estimate", fallback="heuristic_fallback"),
    # DISCOVER
    "simulate_hook_effect": dict(impl="agentic.registry:exec_simulate_hook_effect", source="analytical hook model", lib="numpy",
                                 units="nM concentrations", ret="hook curve", fallback="none"),
    "predict_degradation": dict(impl="agentic.registry:exec_predict_degradation", source="TACK / chemprop degradation models", lib="chemprop",
                                units="(SMILES, e3, cell_line, target)", ret="predicted DC50/Dmax (modeled)", fallback="heuristic_fallback"),
    "predict_admet": dict(impl="agentic.registry:exec_predict_admet", source="ADMET predictors / descriptor rules", lib="rdkit",
                          units="SMILES", ret="ADMET endpoints (predicted)", fallback="descriptor_rule_based"),
    "run_protacpilot_structural": dict(impl="agentic.registry:exec_run_protacpilot_structural", source="PROTACpilot local pipeline", lib="protacxtend",
                                       units="(target, e3, SMILES)", ret="run status + artifacts", fallback="deterministic mode"),
    "rank_candidates": dict(impl="agentic.registry:exec_rank_candidates", source="Pareto / multi-objective ranking", lib="numpy",
                            units="candidates[]", ret="ranked candidates", fallback="none"),
    "build_candidate_dossier": dict(impl="agentic.registry:exec_build_candidate_dossier", source="evidence aggregation", lib="stdlib",
                                    units="candidate", ret="dossier dict", fallback="none"),
}

RETURN_SCHEMA = {
    "RETRIEVED": "records[] with source id + span",
    "CALCULATED": "typed value + provenance",
    "HEURISTIC": "score + rule id + uncertainty",
    "ML PREDICTION": "value + model id + applicability domain",
    "STRUCTURAL SURROGATE": "proxy value (no measured coordinate claim)",
    "MEASURED": "assay value + unit + assay context",
}

STAGE_ORDER = ["KNOW", "REASON", "DESIGN", "DISCOVER"]


def build_capability_matrix(data: dict) -> list[dict]:
    e1 = {r["tool"]: r for r in data["e1"]}
    rows: list[dict] = []
    for name, r in e1.items():
        spec = data["specs"][name]
        meta = ADAPTER_META.get(name, {})
        matched = "|".join(sorted(k for k, v in data["matched"].items() if name in (v.agent_tools or [])))
        rows.append({
            "capability_id": f"adapter:{name}",
            "display_name": name,
            "surface": "agent_adapter",
            "stage": r["study_domain"],
            "kind": r["kind"],
            "biological_question": spec["purpose"],
            "implementation_module": meta.get("impl", "protacxtend/agentic/registry.py"),
            "source_connector_or_library": meta.get("source", "not_documented"),
            "library_package": meta.get("lib", "python"),
            "package_version": r.get("version", "") or "not_pinned",
            "source_date_or_release": (
                "local snapshot (content-hashed in TOOLKIT_TRUTH)" if "local" in meta.get("source", "").lower()
                else "live REST API (no pinned release)" if "rest" in meta.get("source", "").lower()
                else "not_pinned"),
            "required_inputs": r["required_inputs"] or "(none)",
            "input_units": meta.get("units", "not_documented"),
            "return_schema": meta.get("ret", RETURN_SCHEMA.get(spec["evidence_type"], "typed result")),
            "evidence_type": spec["evidence_type"],
            "failure_code": r["negative_failure_code"] or "typed_negative_unknown",
            "fallback_route": meta.get("fallback", "none"),
            "installed_status": "installed" if r["callable"] == "True" else "registered_only",
            "license": r["license"],
            "validation_level": "real_input_executed" if r["positive_valid_output"] == "True" else "executed_invalid",
            "real_input_run_id": r["last_run_id"],
            "run_outcome": r["positive_outcome"],
            "latency_s": r["elapsed_s"],
            "matched_permitted_ids": matched or "(none)",
            "scientific_validity": "not_measured",
            "adapter_default_audit": r["adapter_audit_status"],
            "limitations": spec.get("limitations") or r.get("limitation", ""),
        })
    # scientific backend capabilities (19)
    for b in data["backends"]:
        rows.append({
            "capability_id": f"backend:{b['capability']}",
            "display_name": b["capability"],
            "surface": "scientific_backend",
            "stage": "CORE",
            "kind": "backend_capability",
            "biological_question": f"Can the stack execute {b['capability']} with a free/local backend?",
            "implementation_module": "protacxtend/scientific_backends/*",
            "source_connector_or_library": b["best_backend"],
            "library_package": b["best_backend"],
            "package_version": "not_pinned",
            "source_date_or_release": "capability inventory (no release pinned)",
            "required_inputs": "capability-specific",
            "input_units": "capability-specific",
            "return_schema": "typed backend result",
            "evidence_type": "CALCULATED",
            "failure_code": "CAPABILITY_UNAVAILABLE|LICENSE_REQUIRED",
            "fallback_route": "|".join(x for x in b["usable_backends"] if x != b["best_backend"]) or "none",
            "installed_status": "installed" if b["status"] == "ready" else b["status"],
            "license": "open" if b["status"] == "ready" else "license_gated",
            "validation_level": "capability_inventory_only",
            "real_input_run_id": "not_measured",
            "run_outcome": b["status"],
            "latency_s": "",
            "matched_permitted_ids": "(none)",
            "scientific_validity": "not_measured",
            "adapter_default_audit": "",
            "limitations": "Registered backends: " + b["registered"],
        })
    # 123 registered toolkit tools (registered_only / integration / commercial)
    for t in data["disposition"]["tools"]:
        disp = t.get("disposition", "registered_only")
        fields = (data["reg_tools"].get(t["id"], {}) or {}).get("fields") or t.get("fields") or {}
        rows.append({
            "capability_id": t["id"],
            "display_name": t["tool"],
            "surface": "toolkit_registry",
            "stage": "",
            "kind": "external_tool",
            "biological_question": fields.get("use_in_agentic_degrader_design") or fields.get("purpose") or fields.get("tool_family", "not_documented"),
            "implementation_module": t.get("source_link", "not_documented"),
            "source_connector_or_library": fields.get("tool_family") or fields.get("api_cli_gui", "not_documented"),
            "library_package": t.get("install_command", "not_documented"),
            "package_version": "not_pinned",
            "source_date_or_release": "registry metadata (not release-pinned)",
            "required_inputs": fields.get("input", "not_documented"),
            "input_units": "not_documented",
            "return_schema": fields.get("output", "not_documented"),
            "evidence_type": "NOT_AVAILABLE",
            "failure_code": "REGISTERED_ONLY",
            "fallback_route": "none",
            "installed_status": disp,
            "license": fields.get("license_access", "not_documented"),
            "validation_level": "registered_only",
            "real_input_run_id": "not_measured",
            "run_outcome": "not_run",
            "latency_s": "",
            "matched_permitted_ids": "(none)",
            "scientific_validity": "not_measured",
            "adapter_default_audit": "",
            "limitations": t.get("rationale", ""),
        })
    return rows


# ══════════════════════════════════════════════════════════════════════
# 3. dataflow_edges.csv
# ══════════════════════════════════════════════════════════════════════

def build_dataflow_edges(data: dict) -> list[dict]:
    e1 = {r["tool"]: r for r in data["e1"]}
    E: list[dict] = []

    def edge(stage, source_id, entity, tool, output, strategy_field, tier, failure, fallback="",
             run_id=None, outcome=None):
        r = e1.get(tool, {})
        E.append({
            "stage": stage, "source_id": source_id, "normalized_entity": entity,
            "tool_or_module": tool,
            "typed_output": output, "strategy_field": strategy_field,
            "example_run_id": run_id or r.get("last_run_id", "not_measured"),
            "example_outcome": outcome or r.get("positive_outcome", "not_measured"),
            "evidence_tier": tier,
            "failure_path": failure, "fallback_route": fallback,
        })

    # KNOW
    edge("KNOW", "UniProt REST", "gene -> reviewed human accession", "resolve_target",
         "accession + reviewed flag", "target_validation.uniprot_id", "RETRIEVED",
         "MISSING_SCIENTIFIC_INPUT if target_name empty", "search_uniprot")
    edge("KNOW", "Europe PMC/PubMed", "DOI/PMID -> document", "search_pubmed",
         "records[] with source id", "evidence.items[]", "RETRIEVED",
         "network error -> typed not_available", "search_europe_pmc")
    edge("KNOW", "CrossRef", "DOI -> citation metadata", "verify_crossref",
         "citation metadata", "evidence.provenance", "RETRIEVED",
         "online probe failed (retrieval failed)", "none",
         run_id="e1_online", outcome="executed_invalid")
    edge("KNOW", "ChEMBL REST", "compound -> canonical SMILES/InChIKey", "search_chembl",
         "molecules[]", "warheads[]", "RETRIEVED",
         "empty result -> no candidate", "search_pubchem")
    edge("KNOW", "PubChem PUG-REST", "name -> CID/SMILES", "search_pubchem",
         "CID + canonical SMILES", "warheads[].smiles", "RETRIEVED",
         "network error -> not_available", "search_chembl")
    edge("KNOW", "local BindingDB snapshot", "target -> binder rows", "search_bindingdb",
         "binders[]", "warheads[]", "RETRIEVED", "snapshot miss -> empty", "retrieve_target_binders")
    edge("KNOW", "RCSB PDB", "PDB id -> experimental structure", "retrieve_pdb",
         "structure handle + chain map", "binary_structure_assessment.pdb_id", "RETRIEVED",
         "no structure -> abstain binary stage", "local structures")
    # REASON
    edge("REASON", "curated_e3_ligands.csv", "E3 family -> ligand + precedent", "select_e3_ligase",
         "ranked E3 list", "recommended_e3|alternative_e3s", "RETRIEVED",
         "no precedent -> direct-precedent gate fails", "retrieve_e3_evidence")
    edge("REASON", "E3 opportunity catalog", "E3 -> evidence rows", "retrieve_e3_evidence",
         "evidence rows[]", "evidence.items[]", "RETRIEVED", "unknown E3 -> empty", "none")
    edge("REASON", "expression_context.csv", "cell line -> expression prior", "predict_cell_context",
         "ML prediction + CI", "tpd_tractability", "ML PREDICTION",
         "out-of-domain cell line -> applicability warning", "heuristic_fallback")
    edge("REASON", "scientific_backends", "capability -> local backend", "run_scientific_capability",
         "typed backend result", "module_status", "CALCULATED",
         "LICENSE_REQUIRED/CAPABILITY_UNAVAILABLE", "documented alternative")
    # DESIGN
    edge("DESIGN", "warhead library", "SMILES -> valence/descriptors", "inspect_smiles",
         "validity + descriptors", "warheads[].valid", "CALCULATED",
         "invalid SMILES -> typed refusal", "none")
    edge("DESIGN", "warhead SMILES", "SMILES -> exit-vector atoms", "detect_exit_vectors",
         "exit-vector atom list", "attachment_vectors[]", "CALCULATED",
         "no source-backed vector -> attachment_hypothesis=True", "none")
    edge("DESIGN", "warhead + E3 ligand", "components -> linker hypotheses", "generate_linkers",
         "linker SMILES[]", "linker_hypotheses[]", "CALCULATED",
         "constraint fail -> rejected", "rule-based")
    edge("DESIGN", "warhead+linker+E3", "components -> PROTAC SMILES", "construct_protac",
         "PROTAC SMILES + descriptors", "candidate_protacs[]", "CALCULATED",
         "invalid valence -> rejected", "none")
    edge("DESIGN", "RCSB PDB/local ternary", "chains -> interface contacts", "score_lysine_ubiquitination",
         "geometry score (partial)", "ternary_complex_assessment", "STRUCTURAL SURROGATE",
         "online probe partial (no chain-matched PDB)", "none")
    edge("DESIGN", "structure + ligand", "pose -> cooperativity proxy", "predict_cooperativity",
         "alpha estimate", "ternary_complex_assessment.cooperativity_alpha", "STRUCTURAL SURROGATE",
         "missing pose -> heuristic_fallback", "heuristic_fallback")
    edge("DESIGN", "target+e3", "pair -> ternary proxy", "model_ternary_complex",
         "contacts + proxy score (no coordinates)", "ternary_complex_assessment.score", "STRUCTURAL SURROGATE",
         "no coordinates -> cannot claim geometry", "heuristic_fallback")
    # DISCOVER
    edge("DISCOVER", "SMILES+e3+cell", "PROTAC -> predicted DC50/Dmax", "predict_degradation",
         "predicted DC50/Dmax (modeled)", "degradation_prediction", "ML PREDICTION",
         "no measured label -> NOT_VALIDATED", "heuristic_fallback")
    edge("DISCOVER", "SMILES", "PROTAC -> ADMET endpoints", "predict_admet",
         "ADMET endpoints (predicted)", "adme_risks[]", "ML PREDICTION",
         "descriptor/rule-based fallback", "descriptor_rule_based")
    edge("DISCOVER", "concentrations", "target/E3 conc -> hook curve", "simulate_hook_effect",
         "hook curve", "experimental_plan", "CALCULATED", "missing conc -> typed refusal", "none")
    edge("DISCOVER", "candidate set", "candidates -> Pareto ranks", "rank_candidates",
         "ranked candidates", "recommended_candidates[]", "CALCULATED", "empty set -> empty rank", "none")
    edge("DISCOVER", "PROTACpilot pipeline", "request -> run artifacts", "run_protacpilot_structural",
         "run status + artifacts", "run_manifest", "STRUCTURAL SURROGATE",
         "external engine missing -> deterministic mode", "deterministic mode")
    # CORE
    edge("CORE", "user request", "free text -> typed ScientificRequest", "ScientificRequestParser",
         "typed request", "run_manifest.request", "CALCULATED",
         "MISSING_SCIENTIFIC_INPUT on missing E3/cell/dose", "none")
    edge("CORE", "module results", "module outputs -> critic verdict", "CriticVerifier",
         "approve/revise/block", "critic", "CALCULATED",
         "unsupported structural claim -> REVISE/BLOCK", "human review")
    edge("CORE", "critic + evidence", "verdict -> decision", "DecisionEngine",
         "go/no-go + falsifying experiment", "stopping_state|go_no_go_criteria", "CALCULATED",
         "insufficient evidence -> INSUFFICIENT EVIDENCE", "abstain")
    return E


# ══════════════════════════════════════════════════════════════════════
# 4. count_reconciliation.md
# ══════════════════════════════════════════════════════════════════════

def build_reconciliation_csv(data: dict) -> list[dict]:
    """Machine-readable reconciliation: one row per competing count."""
    recon = data["recon"]
    disp = data["disposition"]
    rows = [
        dict(count_id="C01", count_name="universal_registry_rows", value=recon["registry_rows_total"],
             set_definition="sum of 6 registry sections",
             code_path="protacxtend/toolkit/registry.py:load_toolkit_registry",
             unique_ids_or_aliases="modalities|tools|databases|packages|skills|agent_modules",
             inclusion_rule="every row in every section", installed_status="mixed",
             real_input_run="none", validation_level="inventory", comparable="no",
             notes="registration only; never mix with adapters"),
        dict(count_id="C02", count_name="classified_toolkit_tools", value=disp["n_tools"],
             set_definition="tools section of the registry",
             code_path="protacxtend/toolkit/registry.py -> outputs/tool_disposition.json",
             unique_ids_or_aliases="tools:<slug>",
             inclusion_rule="section == 'tools'", installed_status="22 adapted / 101 non-executable",
             real_input_run="not applicable", validation_level="inventory", comparable="no",
             notes="disposition decision, not execution"),
        dict(count_id="C03", count_name="disposition_adapted", value=disp["counts"]["adapted"],
             set_definition="tool backed by a live adapter/backend token",
             code_path="protacxtend/toolkit/disposition.py:ADAPTED_TOKENS",
             unique_ids_or_aliases="tools:pymol|tools:prosettac|... (22)",
             inclusion_rule="token in ADAPTED_TOKENS", installed_status="overlaps adapters, not identical",
             real_input_run="indirect", validation_level="inventory", comparable="no",
             notes="token match != adapter"),
        dict(count_id="C04", count_name="disposition_integration_candidate", value=disp["counts"]["integration_candidate"],
             set_definition="open-source, offline-installable, in scope",
             code_path="protacxtend/toolkit/disposition.py", unique_ids_or_aliases="tools:<slug>",
             inclusion_rule="open install command and in scope", installed_status="not installed",
             real_input_run="none", validation_level="inventory", comparable="no", notes=""),
        dict(count_id="C05", count_name="disposition_commercial_excluded", value=disp["counts"]["commercial_excluded"],
             set_definition="commercial licence, not redistributable",
             code_path="protacxtend/toolkit/disposition.py", unique_ids_or_aliases="tools:<slug>",
             inclusion_rule="commercial keyword in metadata", installed_status="not installed",
             real_input_run="none", validation_level="inventory", comparable="no", notes="excluded from open denominator"),
        dict(count_id="C06", count_name="agent_tool_adapters", value=len(data["e1"]),
             set_definition="registry spec AND executor present",
             code_path="protacxtend/agentic/registry.py:TOOL_SPECS/_EXECUTORS",
             unique_ids_or_aliases="name (unique)", inclusion_rule="spec present and executor wired",
             installed_status="34/34 installed", real_input_run="34/34 offline; 34/34 attempted online",
             validation_level="real_input_executed", comparable="yes",
             notes="E1 measured surface"),
        dict(count_id="C07", count_name="clean_adapters", value=data["adapter_audit"]["n_clean"],
             set_definition="no residual fixture/placeholder default",
             code_path="protacxtend/runtime/adapter_audit.py -> outputs/adapter_audit.json",
             unique_ids_or_aliases="name (unique)", inclusion_rule="scientific_guard true and no findings",
             installed_status="34/34", real_input_run="static audit only",
             validation_level="fixture_guard_audit", comparable="no", notes="static, not execution"),
        dict(count_id="C08", count_name="domain_valid_adapters", value="33/34 offline (32/34 online)",
             set_definition="positive real input returned schema+domain-valid output",
             code_path="results/closure/e1_tool_matrix.csv",
             unique_ids_or_aliases="tool column", inclusion_rule="positive_valid_output == True",
             installed_status="34/34", real_input_run="yes", validation_level="real_input_executed",
             comparable="yes", notes="fails: score_lysine_ubiquitination (offline+online); verify_crossref (online)"),
        dict(count_id="C09", count_name="typed_negative_refusal", value="31/34",
             set_definition="missing input fails closed with a typed code",
             code_path="results/closure/e1_tool_matrix.csv", unique_ids_or_aliases="tool column",
             inclusion_rule="negative_typed == True", installed_status="34/34", real_input_run="yes",
             validation_level="real_input_executed", comparable="yes",
             notes="3 informational tools legitimately run with no input"),
        dict(count_id="C10", count_name="matched_permitted_ids_defined", value=len(data["matched"]),
             set_definition="permitted id with a concrete executable backing",
             code_path="benchmark_runner/matched_tools.py:MATCHED_TOOLS",
             unique_ids_or_aliases="permitted_id", inclusion_rule="entry in MATCHED_TOOLS",
             installed_status="29 defined", real_input_run="none", validation_level="mapping",
             comparable="no", notes="map is not execution"),
        dict(count_id="C11", count_name="matched_permitted_ids_used", value=27,
             set_definition="distinct permitted ids in the 48 cases",
             code_path="benchmark_results/baselines/*.json:coverage.n_distinct_permitted",
             unique_ids_or_aliases="permitted_id", inclusion_rule="appears in a task's permitted_tools_databases",
             installed_status="27/27 matched, 0 unmatched", real_input_run="none",
             validation_level="mapping", comparable="no", notes="reported 27/27 = mapping coverage only"),
        dict(count_id="C12", count_name="workflow_nodes", value=len(data["workflow_nodes"]),
             set_definition="nodes walked by LocalSynGlueWorkflowGraph",
             code_path="protacxtend/agents/graph.py -> sota/data/workflow_nodes.csv",
             unique_ids_or_aliases="node name", inclusion_rule="node list in the legacy pipeline",
             installed_status="31 defined", real_input_run="not re-executed",
             validation_level="code_inventory", comparable="no", notes="legacy pipeline, not canonical 9-module stack"),
        dict(count_id="C13", count_name="llm_callable_agent_tools", value=data["headline"]["llm_callable_agent_tools"]["value"],
             set_definition="advertised in agentic/registry.py",
             code_path="sota/data/headline_counts.csv", unique_ids_or_aliases="same as C06",
             inclusion_rule="registry spec", installed_status="34 wired", real_input_run="34/34",
             validation_level="real_input_executed", comparable="yes", notes="duplicate alias of C06"),
        dict(count_id="C14", count_name="external_toolkit_tools", value=data["headline"]["external_toolkit_tools"]["value"],
             set_definition="entries in tools/toolkit_registry.py",
             code_path="protacxtend/tools/toolkit_registry.py", unique_ids_or_aliases="tool name",
             inclusion_rule="TOOLKIT_REGISTRY list", installed_status="30 installed per TOOLKIT_TRUTH (static)",
             real_input_run="none", validation_level="inventory", comparable="no",
             notes="different registry from C01/C02"),
        dict(count_id="C15", count_name="scientific_backend_capabilities", value=len(data["backends"]),
             set_definition="scientific_backends capability enum",
             code_path="protacxtend/scientific_backends -> sota/data/scientific_backends.csv",
             unique_ids_or_aliases="capability name", inclusion_rule="capability in the enum",
             installed_status="19/19 ready (free/local)", real_input_run="not measured per capability",
             validation_level="capability_inventory_only", comparable="partial",
             notes="19 capabilities, not 19 distinct engines"),
        dict(count_id="C16", count_name="atomic_tpd_capabilities", value=data["headline"]["atomic_tpd_capabilities"]["value"],
             set_definition="TPD capability taxonomy (escalation)",
             code_path="sota/data/headline_counts.csv", unique_ids_or_aliases="capability id",
             inclusion_rule="taxonomy entry", installed_status="20/27 ready", real_input_run="none",
             validation_level="inventory", comparable="no", notes="taxonomy, distinct from C15"),
        dict(count_id="C17", count_name="catalogued_functionalities", value=data["headline"]["functionalities_catalogued"]["value"],
             set_definition="rows in sota/data/functionalities.csv",
             code_path="sota/data/functionalities.csv", unique_ids_or_aliases="fid (F001...)",
             inclusion_rule="one functionality row", installed_status="98 implemented / 9 partial / 1 planned",
             real_input_run="none", validation_level="catalog", comparable="no",
             notes="12/11/44/15 by stage + 26 CROSS; not executable units"),
        dict(count_id="C18", count_name="stage_functionalities_know_reason_design_discover",
             value="12/11/44/15", set_definition="functionality rows grouped by stage field",
             code_path="sota/data/functionalities.csv:stage", unique_ids_or_aliases="fid",
             inclusion_rule="stage in {KNOW,REASON,DESIGN,DISCOVER}", installed_status="catalogued",
             real_input_run="none", validation_level="catalog", comparable="no",
             notes="artwork claim verified as catalogued functionality only"),
    ]
    return rows


def build_reconciliation(data: dict) -> str:
    recon = data["recon"]
    props = data["proportions"]
    disp = data["disposition"]
    func_by_stage = Counter(r["stage"] for r in data["functionalities"])
    func_status = Counter((r["stage"], r["status"]) for r in data["functionalities"])
    n_adapters = len(data["e1"])
    stages = Counter(r["study_domain"] for r in data["e1"])
    matched = data["matched"]
    lines = [
        "# Tool-depth count reconciliation",
        "",
        f"Generated {datetime.now(timezone.utc).isoformat()} from frozen artifacts at "
        "`results/closure/` and `sota/data/`.  A number is **verified** only when a "
        "row-level artifact exists; otherwise it is **stale/unverifiable**.",
        "",
        "## Verified counts (row-level evidence)",
        "",
        "| # | count | value | set definition (denominator) | code path / artifact | unit of the row | installed status | real-input run | validation level | comparable? |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]

    def row(n, name, value, definition, path, unit, installed, run, validation, comparable):
        lines.append(f"| {n} | {name} | {value} | {definition} | `{path}` | {unit} | {installed} | {run} | {validation} | {comparable} |")

    row(1, "Classified toolkit tools", disp["n_tools"], "tools section of the universal registry",
        "protacxtend/toolkit/registry.py -> outputs/tool_disposition.json", "tool registry row",
        "22 adapted / 101 non-executable", "not applicable (decision only)", "inventory", "no — inventory, not execution")
    row(2, "Disposition: adapted", disp["counts"]["adapted"], "tool backed by a live adapter/backend",
        "protacxtend/toolkit/disposition.py:ADAPTED_TOKENS", "tool registry row",
        "token overlap with adapters, not the same set", "indirect", "inventory", "no — token match ≠ adapter")
    row(3, "Disposition: integration candidate", disp["counts"]["integration_candidate"],
        "open-source, offline-installable, in scope", "outputs/tool_disposition.json", "tool registry row",
        "not installed", "none", "inventory", "no")
    row(4, "Disposition: commercial excluded", disp["counts"]["commercial_excluded"],
        "commercial licence, not redistributable", "outputs/tool_disposition.json", "tool registry row",
        "not installed", "none", "inventory", "no")
    row(5, "Agent-tool adapters", n_adapters, "entries in the agentic registry AND `_EXECUTORS`",
        "protacxtend/agentic/registry.py:TOOL_SPECS/_EXECUTORS", "callable adapter",
        "34/34 installed", "34/34 real input (offline)", "real_input_executed", "yes — E1 measured surface")
    row(6, "Clean adapters (fixture audit)", data["adapter_audit"]["n_clean"],
        "adapters with no residual demo/placeholder default", "protacxtend/runtime/adapter_audit.py -> outputs/adapter_audit.json",
        "callable adapter", "34/34", "static audit", "fixture_guard_audit", "no — static, not execution")
    row(7, "Domain-valid adapters", props["domain_valid_over_runnable"],
        "positive real input returned schema+domain-valid output", "results/closure/e1_tool_matrix.csv",
        "callable adapter", "34/34 installed", "33/34 offline; 32/34 online", "real_input_executed", "yes")
    row(8, "Typed negative refusal", props["typed_negative_failure"],
        "missing input fails closed with a typed code", "results/closure/e1_tool_matrix.csv",
        "callable adapter", "34/34", "31/34 (3 informational tools run with no input)", "real_input_executed", "yes")
    row(9, "Matched permitted IDs (defined)", len(matched),
        "benchmark permitted ids with a concrete executable backing", "benchmark_runner/matched_tools.py:MATCHED_TOOLS",
        "permitted benchmark id", "29 ids defined", "static map", "mapping", "no — a map is not execution")
    row(10, "Matched permitted IDs (used by 48 cases)", 27,
        "distinct permitted ids appearing in the 48 benchmark cases", "benchmark_results/baselines/*.json coverage.n_distinct_permitted",
        "permitted benchmark id", "27/27 matched, 0 unmatched", "static map", "mapping", "no")
    row(11, "Workflow nodes", len(data["workflow_nodes"]),
        "nodes walked by `LocalSynGlueWorkflowGraph`", "protacxtend/agents/graph.py -> sota/data/workflow_nodes.csv",
        "pipeline node", "31 defined", "not re-executed for this audit", "code_inventory", "no — legacy pipeline, not the canonical stack")
    row(12, "LLM-callable agent tools", data["headline"]["llm_callable_agent_tools"]["value"],
        "advertised in `agentic/registry.py`", "sota/data/headline_counts.csv", "adapter",
        "34 wired", "34/34 real input", "real_input_executed", "yes — same as row 5")
    row(13, "External toolkit tools", data["headline"]["external_toolkit_tools"]["value"],
        "entries in `tools/toolkit_registry.py`", "protacxtend/tools/toolkit_registry.py", "toolkit entry",
        "30 installed per TOOLKIT_TRUTH (static)", "none", "inventory", "no")
    row(14, "Scientific backend capabilities", len(data["backends"]),
        "`scientific_backends` capability enum", "protacxtend/scientific_backends -> sota/data/scientific_backends.csv",
        "capability", "19/19 ready (free/local)", "not measured per capability here", "capability_inventory_only", "partial — readiness only")
    row(15, "Atomic TPD capabilities", data["headline"]["atomic_tpd_capabilities"]["value"],
        "TPD capability taxonomy (escalation)", "sota/data/headline_counts.csv", "capability",
        "20/27 ready", "none", "inventory", "no")
    row(16, "Catalogued functionalities", data["headline"]["functionalities_catalogued"]["value"],
        "rows in `sota/data/functionalities.csv`", "sota/data/functionalities.csv", "functionality row",
        "98 implemented / 9 partial / 1 planned", "none", "catalog", "no — not executable units")
    row(17, "Registry rows (universal)", recon["registry_rows_total"],
        "sum of 6 registry sections", "protacxtend/toolkit/registry.py:load_toolkit_registry", "registry row",
        "mixed", "none", "inventory", "no — never mix with adapters")

    lines += [
        "",
        "### Section breakdown of the 296 registry rows",
        "",
        "| section | rows | what it contains | executable here? |",
        "|---|---|---|---|",
    ]
    for sec, n in recon["registry_sections"].items():
        exec_note = "tools section is classified" if sec == "tools" else "no"
        lines.append(f"| {sec} | {n} | {sec} | {exec_note} |")
    lines += [
        "",
        "## Stale / non-comparable artwork claims",
        "",
        "| artwork claim | value | actual artifact | verdict |",
        "|---|---|---|---|",
        f"| Stage functionalities KNOW/REASON/DESIGN/DISCOVER | 12 / 11 / 44 / 15 | `sota/data/functionalities.csv` — catalogued, not executable: "
        f"KNOW {func_by_stage['KNOW']}, REASON {func_by_stage['REASON']}, DESIGN {func_by_stage['DESIGN']}, "
        f"DISCOVER {func_by_stage['DISCOVER']} (+{func_by_stage['CROSS']} CROSS = 108) | **verified as catalogued functionalities** but must not be read as tools |",
        "| Workflow nodes | 31 | `protacxtend/agents/graph.py:LocalSynGlueWorkflowGraph` | verified code inventory; **not** the canonical `CanonicalOrchestrator` (9 modules) |",
        "| 19 backends | 19 | `scientific_backends` capability enum | verified as *capabilities*, not distinct engines |",
        "| 27 capability classes | 27 | TPD capability taxonomy (20 ready) | verified as taxonomy; distinct from 19 backend capabilities |",
        "| 115 external tools | 115 | `tools/toolkit_registry.py` | verified registry count; only 30 installed (TOOLKIT_TRUTH static) |",
        "| 34 LLM-callable tools | 34 | `agentic/registry.py` | verified and executed |",
        "| 296 registry rows | 296 | 6 sections | verified as *registration*, 0/296 declared executable by the hard-coded status function |",
        "| 34 clean adapters | 34 | `adapter_audit.json` | verified static audit |",
        "| 27/27 permitted IDs | 27 | baseline `coverage` | verified mapping; **not execution evidence** |",
        "",
        "**Which numbers cannot be compared.** 296 registry rows (registration), 123 "
        "classified tools (disposition), 115 external toolkit entries (a *different* "
        "registry), 108 catalogued functionalities (a *functional* taxonomy), 34 agent "
        "adapters (callable surface), 19 backend capabilities and 27 TPD capability "
        "classes are seven different denominators. They must never be added, divided or "
        "presented as one funnel without the set definition above.",
        "",
        "**What is stale.** Any count that presents catalogued functionality, registry "
        "registration or a matched-id map as *executed capability* is stale. The only "
        "execution-verified counts in this repository are: 34/34 adapters installed and "
        "executed on a real input, 33/34 domain-valid offline (32/34 online), and 31/34 "
        "typed negative refusals.",
        "",
        "## Per-stage adapter census (E1 measured surface)",
        "",
        "| stage | adapters | valid positive | invalid positive | catalogued functionalities (context) |",
        "|---|---|---|---|---|",
    ]
    valid = Counter(r["study_domain"] for r in data["e1"] if r["positive_valid_output"] == "True")
    invalid = Counter(r["study_domain"] for r in data["e1"] if r["positive_valid_output"] != "True")
    for s in STAGE_ORDER:
        lines.append(f"| {s} | {stages[s]} | {valid[s]} | {invalid[s]} | {func_by_stage[s]} |")
    lines += [
        "",
        "Catalogued-functionality status (from `functionalities.csv`): " +
        ", ".join(f"{k[0]}/{k[1]}={v}" for k, v in sorted(func_status.items())),
        "",
        "## Exact commands",
        "",
        "```bash",
        "python scripts/e1_tool_matrix.py            # rebuild 34-adapter execution matrix",
        "python scripts/e1_tool_matrix.py --online   # rebuild with network allowed",
        "python scripts/build_tool_depth.py          # rebuild all tool-depth artifacts + figures",
        "```",
    ]
    return "\n".join(lines) + "\n"


# ══════════════════════════════════════════════════════════════════════
# 5. Figures
# ══════════════════════════════════════════════════════════════════════

def _wrap(text: str, max_chars: int) -> str:
    """Word-wrap into explicit newlines so matplotlib never overflows a box."""
    out, line = [], ""
    for word in str(text).split():
        if line and len(line) + 1 + len(word) > max_chars:
            out.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        out.append(line)
    return "\n".join(out)


def _box(ax, x, y, w, h, text, color, *, fontsize=8.0, text_color="white", weight="normal"):
    # 100 axis units ~= 8.5 in on an 11 in square canvas (default margins).
    width_in = w / 100.0 * 8.5
    max_chars = max(8, int(width_in * 72.0 / (fontsize * 0.60)))
    wrapped = _wrap(text, max_chars)
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.15,rounding_size=0.6",
                                linewidth=0.8, edgecolor="white", facecolor=color, zorder=2))
    tx = ax.text(x + w / 2, y + h / 2, wrapped, ha="center", va="center", fontsize=fontsize,
                 color=text_color, zorder=3, weight=weight, linespacing=1.15)
    tx._box_rect = (x, y, w, h)
    return tx


def _arrow(ax, x1, y1, x2, y2, color="#555555", lw=1.1, style="-|>"):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=9,
                                 color=color, linewidth=lw, zorder=1, shrinkA=1, shrinkB=1))


def build_figure_a(data: dict) -> None:
    apply_style()
    fig, ax = plt.subplots()
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    ax.text(50, 98.5, "Figure A · PROTACXtend canonical architecture and evidence lanes",
            ha="center", va="center", fontsize=12.5, weight="bold", color=C["ink"])
    ax.text(50, 95.6, "One example question · typed inputs · four parallel lanes · agent-control band · worked BRD4–VHL stop",
            ha="center", va="center", fontsize=8.2, color="#444444")

    # example question + inputs
    _box(ax, 3, 90.0, 94, 4.0, "Example question: can a VHL-recruiting PROTAC degrade BRD4 in a defined cell context?",
         "#EEF3FA", fontsize=9, text_color=C["ink"], weight="bold")
    ax.text(26, 88.4, "required: target · E3 · cell context · dose", ha="center", va="center",
            fontsize=7.4, color=C["know"], weight="bold")
    ax.text(74, 88.4, "optional: disease · assay · linker constraints", ha="center", va="center",
            fontsize=7.4, color=C["core"])
    _arrow(ax, 26, 90.0, 26, 89.0, color=C["know"])
    _arrow(ax, 74, 90.0, 74, 89.0, color=C["core"])

    lanes = [
        ("KNOW", C["know"],
         "sources: UniProt · Europe PMC/PubMed · ChEMBL · PubChem · PDB",
         "parse + resolve + retrieve", "normalized entities (accession · SMILES/InChIKey · PDB chain)",
         "gate: entity + citation resolves"),
        ("REASON", C["reason"],
         "sources: curated E3 catalog · expression-context CSV",
         "rank E3 · context plausibility", "E3 ranking + degradation plausibility",
         "gate: context supports degradation"),
        ("DESIGN", C["design"],
         "sources: warhead library · experimental PDB structures",
         "detect vectors · link · assemble", "linker hypotheses + candidate PROTACs",
         "gate: source-backed exit vector?"),
        ("DISCOVER", C["discover"],
         "sources: degradation model · ADMET model · assay context",
         "predict · simulate · rank", "predicted DC50/Dmax (modeled)",
         "gate: measured label available?"),
    ]
    top = 82.5
    row_h = 12.2
    x0, w = 9.0, 20.5
    step = 21.5
    for i, (name, color, src, op, inter, gate) in enumerate(lanes):
        y = top - i * row_h
        _box(ax, 0.4, y - 4.2, 8.3, 8.4, name, color, fontsize=8.6, weight="bold")
        _box(ax, x0, y - 3.6, w, 7.2, src, "#FFFFFF", fontsize=6.9, text_color=C["ink"])
        _box(ax, x0 + step, y - 3.6, w, 7.2, op, "#FFFFFF", fontsize=7.4, text_color=C["ink"])
        _box(ax, x0 + 2 * step, y - 3.6, w, 7.2, inter, "#FFFFFF", fontsize=7.0, text_color=C["ink"])
        gate_color = C["gate"] if name != "DESIGN" else C["stop"]
        _box(ax, x0 + 3 * step, y - 3.6, w, 7.2, gate, gate_color, fontsize=7.0, weight="bold")
        for k in range(3):
            _arrow(ax, x0 + k * step + w, y, x0 + (k + 1) * step, y, color=color)
    for k, lab in enumerate(["source", "operation", "intermediate", "gate"]):
        ax.text(x0 + k * step + w / 2, top + 4.1, lab, ha="center", fontsize=7.2, color="#555")

    # agent-control band
    _box(ax, 3, 24.5, 94, 4.4,
         "Agent control: routing · memory · provenance · retry · critics   |   every run emits a ToolRun + EvidenceItem lineage; "
         "critics may force REVISE / abstain",
         C["core"], fontsize=7.8, weight="bold")
    # single control bus on the right: the band applies to every lane
    ax.annotate("", xy=(97.0, top - 3.6), xytext=(97.0, 28.9),
                arrowprops=dict(arrowstyle="-|>", color=C["core"], lw=1.4))
    ax.text(95.7, (28.9 + top - 3.6) / 2, "control applies to all lanes", rotation=90,
            ha="center", va="center", fontsize=6.6, color=C["core"])

    # worked BRD4-VHL path
    ax.text(50, 21.8, "Worked path (BRD4–VHL): stops on an unsupported exit vector",
            ha="center", fontsize=9, weight="bold", color=C["ink"])
    wy = 13.0
    _box(ax, 3, wy - 3.4, 20, 6.8, "BRD4 resolved\n(UniProt O60885)", C["know"], fontsize=7.4)
    _box(ax, 25.5, wy - 3.4, 20, 6.8, "VHL E3 selected\n(local catalog)", C["reason"], fontsize=7.4)
    _box(ax, 48, wy - 3.4, 20, 6.8, "warhead binder found\n(no validated vector)", C["design"], fontsize=7.4)
    _box(ax, 70.5, wy - 3.4, 26.5, 6.8, "STOP — INSUFFICIENT EVIDENCE\nno source-backed exit vector",
         C["stop"], fontsize=7.6, weight="bold")
    _arrow(ax, 23, wy, 25.5, wy, color=C["core"])
    _arrow(ax, 45.5, wy, 48, wy, color=C["core"])
    _arrow(ax, 68, wy, 70.5, wy, color=C["stop"], lw=1.6)
    ax.text(36, wy - 5.4, "falsifying assay: TR-FRET ternary / DC50 dose–response",
            ha="center", fontsize=6.8, color="#555", style="italic")
    ax.text(50, 5.6, "Measured ≠ modeled ≠ unknown.  No invented structure, DC50 or ternary claim.  "
                     "Tool names are routed to the supplementary matrix.",
            ha="center", fontsize=6.8, color="#666666")
    save_all(fig, "Figure_A_architecture")


def build_figure_b(data: dict) -> None:
    apply_style()
    fig, axes = plt.subplots(1, 2, layout="constrained")
    ax1, ax2 = axes

    # ── funnel ──
    disp = data["disposition"]
    stages = [
        ("Registered toolkit tools", 123),
        ("Eligible (non-commercial)", 123 - disp["counts"]["commercial_excluded"]),
        ("Adapted + installed", 34),
        ("Real-input executed", 34),
        ("Domain-valid output", 33),
        ("Externally benchmarked", 0),
    ]
    labels = [s[0] for s in stages]
    vals = [s[1] for s in stages]
    ypos = list(range(len(stages)))[::-1]
    colors = ["#8DA0CB", "#A6CEE3", "#66C2A5", "#1B9E77", "#006D2C", "#BBBBBB"]
    ax1.barh(ypos, vals, color=colors, height=0.62)
    for y, v in zip(ypos, vals):
        ax1.text(v + 2, y, str(v), va="center", fontsize=8.5)
    ax1.set_yticks(ypos)
    ax1.set_yticklabels(labels, fontsize=8)
    ax1.set_xlim(0, 140)
    ax1.set_xlabel("Unique capabilities (n)")
    ax1.set_ylabel("Capability funnel stage")
    ax1.set_title("A · Execution-readiness funnel (E1)", fontsize=9.5)
    ax1.text(0.5, -0.20, "Registration ≠ installation ≠ execution ≠ biological validity.\n"
                         "External benchmark for adapters: not measured.",
             transform=ax1.transAxes, ha="center", fontsize=6.8, color="#666")
    ax1.set_box_aspect(1)

    # ── per-stage status ──
    order = STAGE_ORDER
    valid = Counter(r["study_domain"] for r in data["e1"] if r["positive_valid_output"] == "True")
    invalid = Counter(r["study_domain"] for r in data["e1"] if r["positive_valid_output"] != "True")
    info = Counter(r["study_domain"] for r in data["e1"] if r["negative_typed"] != "True")
    x = list(range(len(order)))
    v = [valid[s] for s in order]
    iv = [invalid[s] for s in order]
    nfo = [info[s] for s in order]
    ax2.bar(x, v, color=C["measured"], label="positive valid", width=0.6)
    ax2.bar(x, iv, bottom=v, color=C["stop"], label="executed invalid", width=0.6)
    ax2.bar(x, nfo, bottom=[v[i] + iv[i] for i in range(len(order))], color="#BBBBBB",
            label="informational (no input required)", width=0.6)
    for i in x:
        ax2.text(i, v[i] / 2, str(v[i]), ha="center", va="center", fontsize=8, color="white")
        if iv[i]:
            ax2.text(i, v[i] + iv[i] / 2, str(iv[i]), ha="center", va="center", fontsize=7, color="black")
    ax2.set_xticks(x)
    ax2.set_xticklabels(order, fontsize=8.5)
    ax2.set_ylim(0, 15)
    ax2.set_xlabel("Evidence-lane stage")
    ax2.set_ylabel("Callable adapters (n)")
    ax2.set_title("B · Per-stage adapter status", fontsize=9.5)
    ax2.legend(fontsize=6.5, loc="upper right", frameon=False)
    ax2.text(0.5, -0.20, "Failure: verify_crossref (network, KNOW) · score_lysine_ubiquitination (partial, DESIGN).\n"
                         "Inventory only — no biological-validity inference.",
             transform=ax2.transAxes, ha="center", fontsize=6.8, color="#666")
    ax2.set_box_aspect(1)

    fig.suptitle("Figure B · Toolkit depth — implementation inventory", fontsize=11.5, weight="bold")
    save_all(fig, "Figure_B_toolkit_depth")


def build_figure_c(data: dict) -> None:
    apply_style()
    fig, ax = plt.subplots()
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    ax.text(50, 97.5, "Figure C · Mechanistic evidence ladder — BRD4–VHL case",
            ha="center", fontsize=12, weight="bold", color=C["ink"])
    ax.text(50, 94.3, "measured = green · modeled/predicted = blue · unknown = grey   |   contradictions and falsifying assays sit next to their claim",
            ha="center", fontsize=7.4, color="#444")
    ax.add_patch(FancyBboxPatch((6, 3), 2.2, 89, boxstyle="round,pad=0.1",
                                facecolor="#EEEEEE", edgecolor="none", zorder=0))

    rungs = [
        ("1. Target validation", "BRD4 dependency / essentiality in the stated cell context",
         "unknown", "no DepMap/CRISPR adapter wired", "falsifying assay: BRD4 degradation + downstream c-MYC"),
        ("2. E3 availability", "VHL present in local curated E3 catalog",
         "measured", "catalog inventory (not context-specific expression)", "competition assay / VHL expression"),
        ("3. Ligand / warhead", "BRD4 binder exists in ChEMBL; repo ships demo fixtures only",
         "modeled", "9 known PROTACs / 6 warheads are demo or unlabelled", "binding assay (ITC/SPR)"),
        ("4. Exit vector (atom-mapped)", "NO source-backed, atom-mapped exit vector",
         "unknown", "attachment_vectors are hypotheses", "co-crystal / NMR of warhead–BRD4"),
        ("5. Ternary hypothesis", "proxy score only; no coordinates, no cooperativity measurement",
         "modeled", "ternary_complex_assessment is a surrogate", "TR-FRET ternary / HDX"),
        ("6. Cellular degradation", "0/233 curated records carry an assay-specific DC50",
         "unknown", "no wet-lab in this repository", "DC50/Dmax dose–response ± proteasome/E3 controls"),
        ("7. Decision", "INSUFFICIENT EVIDENCE — no-go",
         "measured", "critic blocks unsupported structural claims", "human re-review with source-backed vector"),
    ]
    y = 88.0
    for name, claim, tier, contra, assay in rungs:
        color = {"measured": C["measured"], "modeled": C["modeled"], "unknown": C["unknown"]}[tier]
        _box(ax, 9, y - 5.7, 30, 5.7, f"{name}\n{claim}", color if tier != "unknown" else "#DDDDDD",
             fontsize=6.9, text_color="white" if tier != "unknown" else "#333333", weight="bold")
        _box(ax, 41, y - 5.7, 26, 5.7, f"contradiction / gap:\n{contra}", "#FFFFFF",
             fontsize=6.4, text_color=C["ink"])
        _box(ax, 69, y - 5.7, 28, 5.7, f"falsifying assay:\n{assay}", "#F5F5F5",
             fontsize=6.4, text_color=C["ink"])
        if y > 20:
            _arrow(ax, 24, y - 5.7, 24, y - 7.0, color="#888")
        y -= 12.2
    ax.text(50, 3.56, "The BRD4–VHL stop is a legitimate audited outcome, not a failure.  "
                      "A positive path remains hypothetical until independently supported.",
            ha="center", fontsize=7.0, color="#555", style="italic")
    save_all(fig, "Figure_C_mechanistic_evidence")


# ══════════════════════════════════════════════════════════════════════
# 6. Captions
# ══════════════════════════════════════════════════════════════════════

CAPTIONS = """# Tool-depth figure captions

**Figure A — PROTACXtend canonical architecture and evidence lanes.**
One example question is parsed into typed inputs; four evidence lanes (KNOW,
REASON, DESIGN, DISCOVER) run source → operation → intermediate → gate in
parallel. A thin agent-control band provides routing, memory, provenance, retry
and critics, and every run emits a `ToolRun`/`EvidenceItem` lineage. The worked
BRD4–VHL path terminates at a red gate because no source-backed, atom-mapped
exit vector exists; the terminal state is `INSUFFICIENT EVIDENCE`. Colors denote
lanes, not confidence. Tool names are listed in the supplementary capability
matrix; node text is deliberately <12 words. No structure, DC50 or ternary
claim is drawn.

**Figure B — Toolkit depth (implementation inventory).**
(A) Measured execution-readiness funnel: 123 registered toolkit tools → 102
non-commercial eligible → 34 adapted/installed agent adapters → 34 executed on a
real input → 33 domain-valid (offline; 32/34 online) → 0 adapters externally
benchmarked. (B) Per-stage status of the 34 callable adapters: KNOW 12/12,
REASON 7/7, DESIGN 8/9 (one executed-invalid: `score_lysine_ubiquitination`),
DISCOVER 6/6; three informational tools legitimately require no input. Because
only inventory data exist, the panel is titled *implementation inventory* and no
biological-validity inference is drawn. Failure annotations: `verify_crossref`
(online retrieval failure, KNOW) and `score_lysine_ubiquitination` (partial
output, DESIGN). Counts reconcile to `capability_matrix.csv` and
`count_reconciliation.md`.

**Figure C — Mechanistic evidence ladder (BRD4–VHL).**
One case-level ladder from target validation through E3 availability, ligand,
atom-mapped exit vector, ternary hypothesis, cellular degradation and decision.
Green = measured, blue = modeled/predicted, grey = unknown. Each rung carries
its contradiction/gap and its falsifying assay. Rung 4 is the blocking rung:
there is no source-backed, atom-mapped exit vector, so the ternary and
degradation claims are not supported and the decision is a legitimate
`INSUFFICIENT EVIDENCE` stop. A schematic positive path remains hypothetical
until independently supported. No DC50, cooperativity or ternary geometry is
claimed.
"""


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    data = load_inputs()

    cap = build_capability_matrix(data)
    with (OUT / "capability_matrix.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(cap[0].keys()))
        w.writeheader()
        w.writerows(cap)

    recon_rows = build_reconciliation_csv(data)
    with (OUT / "count_reconciliation.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(recon_rows[0].keys()))
        w.writeheader()
        w.writerows(recon_rows)

    edges = build_dataflow_edges(data)
    with (OUT / "dataflow_edges.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(edges[0].keys()))
        w.writeheader()
        w.writerows(edges)

    (OUT / "count_reconciliation.md").write_text(build_reconciliation(data))
    (OUT / "FIGURE_CAPTIONS.md").write_text(CAPTIONS)

    build_figure_a(data)
    build_figure_b(data)
    build_figure_c(data)

    print(json.dumps({
        "capability_rows": len(cap),
        "dataflow_edges": len(edges),
        "out": str(OUT),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

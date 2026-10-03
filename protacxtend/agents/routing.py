"""Capability-aware, dependency-driven routing.

A capability is not a fixed workflow. ``route_for`` inspects the case's
question and *structured* inputs, decides which scientific primitives are
genuinely required, and returns the minimal node list. A KNOW question that
only asks for a UniProt accession must not run binder retrieval, warhead
selection or any DESIGN/DISCOVER node.

The returned dependency record is carried into the final result so a reviewer
can see *why* a node was included or skipped.
"""

from __future__ import annotations

import re
from typing import Any

# Node order reference (all names must exist in the workflow graph).
_BASE = ["parse_user_request", "create_design_plan", "safety_precheck", "resolve_target"]
_TAIL = ["generate_report", "update_memory"]
_RETRIEVAL = ["retrieve_target_binders", "select_warheads", "select_e3_ligands"]
#: KNOW/REASON never run the design-oriented warhead selector (it can abort the
#: graph when only demo warheads exist); they retrieve binders/E3 directly and
#: let the answer agent format them.
_COMPONENT_RETRIEVAL = ["retrieve_target_binders", "select_e3_ligands"]

#: Keyword -> dependency. Matching is word-boundary and case-insensitive.
_DEPENDENCY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "binders": ("binder", "binders", "warhead", "warheads", "ligand", "ligands",
                "degrader", "degraders", "inhibitor", "binders'"),
    "e3": ("e3", "ligase", "crbn", "vhl", "cereblon", "recruit"),
    "exit_vectors": ("exit vector", "exit-vector", "attachment", "attach", "derivatiz",
                     "conjugat", "linker attachment"),
    "cooperativity": ("cooperativ", "alpha", "ternary", "avidity", "positive cooperativ"),
    "hook": ("hook", "dose-response", "dose response", "bell-shaped"),
    "admet": ("admet", "permeab", "solubil", "logp", "logp", "lipophil", "herg", "tox"),
    "degradation": ("dc50", "dmax", "degrad", "potency", "ubiquitin"),
    "smiles": ("canonical smiles", "inchi", "inchikey", "molecular formula", "formula",
               "molecular weight", "mw", "smiles"),
    "structure": ("pdb", "crystal", "ternary structure", "pose", "5t35", "structure"),
    "cell_context": ("cell line", "cell-line", "express", "proteotype", "cell context"),
    "literature": ("doi", "pubmed", "citation", "literature", "source id", "crossref"),
    "provenance": ("source", "citation", "provenance", "unverified", "schema", "csv"),
}


def _question_text(case: dict[str, Any]) -> str:
    parts = [str(case.get("scientific_question") or "")]
    parts.extend(str(x) for x in (case.get("supplied_inputs") or []))
    return " ".join(parts).lower()


def _has_component_smiles(case: dict[str, Any]) -> bool:
    from protacxtend.agents.entity_resolution import _looks_like_smiles

    for raw in case.get("supplied_inputs") or []:
        text = str(raw)
        if ":" not in text:
            continue
        key, value = text.split(":", 1)
        key_l = key.strip().lower()
        if ("warhead" in key_l or "e3 ligand" in key_l or "e3-ligand" in key_l) and _looks_like_smiles(value):
            return True
    return False


def required_dependencies(case: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Return {dependency: {"required": "yes"/"no", "reason": ...}}."""
    text = _question_text(case)
    deps: dict[str, dict[str, str]] = {}
    for name, keywords in _DEPENDENCY_KEYWORDS.items():
        hit = next((k for k in keywords if re.search(rf"\b{re.escape(k)}\b", text)), "")
        deps[name] = {"required": "yes" if hit else "no", "reason": f"matched {hit!r}" if hit else "no signal"}

    # A supplied component SMILES is a hard dependency on the component route.
    if _has_component_smiles(case):
        deps["binders"] = {"required": "yes", "reason": "structured component SMILES supplied"}
        deps["e3"] = {"required": "yes", "reason": "structured component SMILES supplied"}
    return deps


def route_for(case: dict[str, Any], capability: str) -> tuple[list[str], dict[str, Any]]:
    """Return (node list, routing record) for *case* and *capability*."""
    capability = (capability or case.get("capability") or "DESIGN").upper()
    deps = required_dependencies(case)
    used: list[str] = ["resolve_target"]
    skipped: list[str] = []
    if capability == "KNOW":
        route = list(_BASE)
        need_components = deps["binders"]["required"] == "yes" or deps["e3"]["required"] == "yes"
        if deps["cell_context"]["required"] == "yes":
            route.append("score_cell_context")
            used.append("score_cell_context")
        if need_components:
            route.extend(_COMPONENT_RETRIEVAL)
            used.extend(_COMPONENT_RETRIEVAL)
        else:
            skipped.extend(_COMPONENT_RETRIEVAL)
        route.append("capability_answer")
        used.append("capability_answer")
        route.extend(_TAIL)
    elif capability == "REASON":
        route = list(_BASE)
        need_components = (
            deps["binders"]["required"] == "yes"
            or deps["e3"]["required"] == "yes"
            or deps["exit_vectors"]["required"] == "yes"
        )
        if need_components:
            route.extend(_COMPONENT_RETRIEVAL)
            used.extend(_COMPONENT_RETRIEVAL)
        else:
            skipped.extend(_COMPONENT_RETRIEVAL)
        if deps["exit_vectors"]["required"] == "yes":
            route.append("detect_exit_vectors")
            used.append("detect_exit_vectors")
        else:
            skipped.append("detect_exit_vectors")
        if deps["cooperativity"]["required"] == "yes" or deps["structure"]["required"] == "yes":
            route.append("optional_ternary_feasibility")
            route.append("predict_cooperativity")
            used.extend(["optional_ternary_feasibility", "predict_cooperativity"])
        else:
            skipped.extend(["optional_ternary_feasibility", "predict_cooperativity"])
        if deps["hook"]["required"] == "yes":
            route.append("predict_hook_effect")
            used.append("predict_hook_effect")
        else:
            skipped.append("predict_hook_effect")
        if deps["admet"]["required"] == "yes":
            route.append("predict_admet")
            used.append("predict_admet")
        else:
            skipped.append("predict_admet")
        route.append("reasoning_answer")
        used.append("reasoning_answer")
        route.extend(_TAIL)
    elif capability == "DISCOVER":
        route = [
            "parse_user_request", "create_design_plan", "safety_precheck", "resolve_target",
            "select_e3_ligands", "assess_applicability_domain", "predict_degradation",
            "initial_ranking", "diversity_clustering", "reflection_review",
            "optional_ternary_feasibility", "predict_cooperativity", "predict_hook_effect",
            "final_ranking", "generate_report", "update_memory",
        ]
        used = list(route)
    else:  # DESIGN
        route = [
            "parse_user_request", "create_design_plan", "safety_precheck", "resolve_target",
            "retrieve_target_binders", "design_path", "select_warheads", "select_e3_ligands",
            "detect_exit_vectors", "generate_linkers", "construct_protacs",
            "expand_stereoisomers", "validate_protacs", "score_cell_context", "predict_admet",
            "check_novelty", "assess_applicability_domain", "cheap_filter_candidates",
            "predict_degradation", "initial_ranking", "diversity_clustering",
            "reflection_review", "optional_ternary_feasibility", "predict_cooperativity",
            "predict_hook_effect", "final_ranking", "generate_report", "update_memory",
        ]
        used = list(route)

    record = {
        "capability": capability,
        "route": route,
        "dependencies": deps,
        "used_nodes": used,
        "skipped_nodes": skipped,
        "rationale": (
            "Minimal dependency route: component retrieval is included only when the "
            "question/inputs require it; KNOW/REASON never run DESIGN/DISCOVER nodes."
        ),
    }
    return route, record


__all__ = ["route_for", "required_dependencies"]

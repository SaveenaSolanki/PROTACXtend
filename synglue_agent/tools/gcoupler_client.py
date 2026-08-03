"""g:Profiler/g:Coupler-style biology context client."""

from __future__ import annotations

from synglue_agent.tools.online_ligand_miner import retrieve_gcoupler_biology_context


def retrieve_target_biology_context(target_name: str, organism: str = "hsapiens"):
    return retrieve_gcoupler_biology_context(target_name, organism)


def summarize_final_biology_stage(target_name: str, organism: str = "hsapiens") -> dict:
    context, warnings = retrieve_gcoupler_biology_context(target_name, organism)
    terms = context.get("terms", []) if context else []
    return {
        "target": target_name,
        "organism": organism,
        "top_terms": terms[:5],
        "stage": "biology_context_only_no_chemical_warhead",
        "can_build_protac": False,
        "warnings": warnings
        + [
            "Biology context cannot be converted into a final PROTAC SMILES without a real inhibitor/activator ligand SMILES."
        ],
    }

"""Matched-tool registry for the benchmark.

Benchmark tasks declare ``permitted_tools_databases`` using short ids
(``rdkit``, ``chembl``, ``hook_effect`` …). This module is the single mapping
from those ids to the concrete PROTACXtend agent-tool adapters and backends
that implement them, so:

* a baseline can be given *exactly* the tools a task permits;
* tool-selection precision is measurable (did the system use a permitted tool?);
* the E1 "registered -> executable" funnel has a concrete denominator;
* unmatched or unavailable tools are explicit rather than silently substituted.

The registry is deliberately static and offline: it never imports a network
client at import time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from benchmark_runner.runner import TaskInput


@dataclass
class MatchedTool:
    """One permitted benchmark resource and its executable backing."""

    permitted_id: str
    agent_tools: list[str] = field(default_factory=list)
    backends: list[str] = field(default_factory=list)
    executable: bool = True
    offline: bool = False
    modality: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "permitted_id": self.permitted_id,
            "agent_tools": list(self.agent_tools),
            "backends": list(self.backends),
            "executable": self.executable,
            "offline": self.offline,
            "modality": self.modality,
            "notes": self.notes,
        }


#: The single source of truth mapping benchmark ids -> adapters.
MATCHED_TOOLS: dict[str, MatchedTool] = {
    # chemistry
    "rdkit": MatchedTool("rdkit", ["inspect_smiles", "construct_protac", "check_synthetic_feasibility"],
                         ["rdkit"], offline=True, modality="chemistry"),
    "molecule_standardizer": MatchedTool("molecule_standardizer", ["inspect_smiles"],
                                         ["rdkit"], offline=True, modality="chemistry"),
    "linker_generator": MatchedTool("linker_generator", ["generate_linkers"],
                                    ["linker_generator"], offline=True, modality="chemistry"),
    "warhead_library": MatchedTool("warhead_library", ["retrieve_target_binders"],
                                   ["chembl", "bindingdb"], modality="ligand_retrieval"),
    "e3_library": MatchedTool("e3_library", ["select_e3_ligase", "retrieve_e3_evidence"],
                              ["curated_e3_ligands"], offline=True, modality="e3_selection"),
    "exit_vector": MatchedTool("exit_vector", ["detect_exit_vectors"],
                               ["exit_vector_detector"], offline=True, modality="chemistry"),
    "novelty_check": MatchedTool("novelty_check", ["search_pubchem", "search_chembl"],
                                 ["pubchem", "chembl"], modality="novelty"),
    # target / biology
    "uniprot": MatchedTool("uniprot", ["resolve_target", "search_uniprot"],
                           ["uniprot", "curated_targets"], offline=True, modality="target_identity"),
    "chembl": MatchedTool("chembl", ["search_chembl", "retrieve_target_binders"],
                          ["chembl"], modality="ligand_retrieval"),
    "pubchem": MatchedTool("pubchem", ["search_pubchem"], ["pubchem"], modality="chemistry"),
    "bindingdb": MatchedTool("bindingdb", ["search_bindingdb"], ["bindingdb"], modality="ligand_retrieval"),
    "protacdb": MatchedTool("protacdb", ["search_bindingdb"], ["protacdb"], modality="protac_evidence"),
    # structure
    "rcsb_pdb": MatchedTool("rcsb_pdb", ["retrieve_pdb"], ["rcsb"], modality="structure"),
    "pdb": MatchedTool("pdb", ["retrieve_pdb"], ["rcsb"], modality="structure"),
    "ternary_feasibility": MatchedTool("ternary_feasibility", ["model_ternary_complex"],
                                       ["ternary_feasibility"], offline=True, modality="structure"),
    "cooperativity": MatchedTool("cooperativity", ["predict_cooperativity"],
                                 ["cooperativity"], offline=True, modality="structure"),
    # prediction / design
    "admet": MatchedTool("admet", ["predict_admet"], ["admet_predictors"], offline=True, modality="adme"),
    "degradation_predictor": MatchedTool("degradation_predictor", ["predict_degradation"],
                                         ["chemprop/heuristic"], modality="degradation"),
    "hook_effect": MatchedTool("hook_effect", ["simulate_hook_effect"],
                               ["hook_effect_modeler"], offline=True, modality="degradation"),
    "cell_context": MatchedTool("cell_context", ["predict_cell_context"],
                                ["cell_context"], modality="cell_context"),
    "pareto_ranking": MatchedTool("pareto_ranking", ["rank_candidates"],
                                  ["pareto_ranking"], offline=True, modality="decision"),
    "diversity": MatchedTool("diversity", ["rank_candidates"], ["pareto_ranking"],
                             offline=True, modality="decision"),
    "uncertainty": MatchedTool("uncertainty", ["rank_candidates"], ["pareto_ranking"],
                               offline=True, modality="decision"),
    "evidence_logs": MatchedTool("evidence_logs", ["build_candidate_dossier"],
                                 ["provenance"], offline=True, modality="provenance"),
    # literature
    "europepmc": MatchedTool("europepmc", ["search_europe_pmc"], ["europepmc"], modality="literature"),
    "pubmed": MatchedTool("pubmed", ["search_pubmed"], ["pubmed"], modality="literature"),
    "openalex": MatchedTool("openalex", ["search_web", "deep_research"], ["openalex"], modality="literature"),
    "crossref": MatchedTool("crossref", ["verify_crossref"], ["crossref"], modality="literature"),
    # research
    "deep_research": MatchedTool("deep_research", ["deep_research"], ["europepmc", "pubmed", "crossref"],
                                 modality="literature"),
}


def match_id(permitted_id: str) -> MatchedTool | None:
    return MATCHED_TOOLS.get(permitted_id)


def match_ids(permitted_ids: Iterable[str]) -> list[MatchedTool]:
    out: list[MatchedTool] = []
    for permitted_id in permitted_ids or []:
        matched = MATCHED_TOOLS.get(str(permitted_id))
        if matched is not None:
            out.append(matched)
    return out


def unmatched_ids(permitted_ids: Iterable[str]) -> list[str]:
    return sorted({str(p) for p in (permitted_ids or []) if str(p) not in MATCHED_TOOLS})


def match_task(task: TaskInput) -> dict[str, Any]:
    """Resolve a task's permitted tool list to concrete adapters."""
    permitted = list(task.permitted_tools or [])
    matched = match_ids(permitted)
    tools = sorted({tool for entry in matched for tool in entry.agent_tools})
    return {
        "task_id": task.task_id,
        "permitted": permitted,
        "matched": [entry.to_dict() for entry in matched],
        "unmatched": unmatched_ids(permitted),
        "agent_tools": tools,
        "n_permitted": len(permitted),
        "n_matched": len(matched),
    }


def coverage(tasks: Iterable[TaskInput]) -> dict[str, Any]:
    """Match coverage across a task set."""
    rows = [match_task(task) for task in tasks]
    permitted = {p for row in rows for p in row["permitted"]}
    unmatched = {p for row in rows for p in row["unmatched"]}
    return {
        "n_tasks": len(rows),
        "n_distinct_permitted": len(permitted),
        "n_distinct_matched": len(permitted - unmatched),
        "n_distinct_unmatched": len(unmatched),
        "unmatched_ids": sorted(unmatched),
        "by_task": rows,
    }


__all__ = [
    "MATCHED_TOOLS",
    "MatchedTool",
    "coverage",
    "match_id",
    "match_ids",
    "match_task",
    "unmatched_ids",
]

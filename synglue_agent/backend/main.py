"""Backend entry points for SynGlue-Agent."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from synglue_agent.agents.runtime import run_protacpilot  # unified entry point
from synglue_agent.agents.graph import run_syn_glue_workflow
from synglue_agent.backend.config import CANDIDATE_DIR, REPORT_DIR, ensure_directories
from synglue_agent.backend.mode_router import run_mode
from synglue_agent.backend.schemas import WorkflowState, model_to_dict
from synglue_agent.tools.report_generator import generate_candidate_table
from synglue_agent.tools.protac_toolbox import ProtacDesignToolbox


def run_agentic_design(user_request: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run the unified agentic workflow from the legacy backend CLI."""

    return run_protacpilot(user_request, mode="agentic", config=config or {})


def run_workflow_from_request(user_request: str) -> WorkflowState:
    """Run the complete SynGlue workflow from a natural-language request."""

    return run_syn_glue_workflow(user_request)


def summarize_state(state: WorkflowState) -> dict[str, Any]:
    top = state.ranking_results[0] if state.ranking_results else None
    workflow_rows = ProtacDesignToolbox().generate_agent_workflow_table(state)
    pipeline_status = state.pipeline_status or ProtacDesignToolbox().generate_pipeline_status_table(state)
    tool_status_counts: dict[str, int] = {}
    for row in workflow_rows:
        status = row.get("Tool status", "unknown")
        tool_status_counts[status] = tool_status_counts.get(status, 0) + 1
    return {
        "target": state.parsed_objective.target_name,
        "e3_ligase": state.parsed_objective.e3_ligase or "CRBN/VHL branch",
        "binders_retrieved": len(state.retrieved_binders),
        "warheads_selected": len(state.selected_warheads),
        "e3_ligands_selected": len(state.selected_e3_ligands),
        "linkers_generated": len(state.generated_linkers),
        "construction_attempts": len(state.construction_attempts),
        "valid_candidates": len(state.valid_candidates),
        "final_candidates": len(state.final_ranked_candidates),
        "top_candidate_id": getattr(top, "candidate_id", None),
        "top_score": getattr(top, "final_priority_score", None),
        "tool_status_counts": tool_status_counts,
        "pipeline_status": pipeline_status,
        "planned_integrations": [
            row["Selected tool"]
            for row in workflow_rows
            if "planned integration" in str(row.get("Integration note", "")).lower()
        ],
        "warnings": state.warnings,
        "errors": state.errors,
    }


def write_outputs(state: WorkflowState, stem: str = "synglue_run") -> dict[str, str]:
    ensure_directories()
    toolbox = ProtacDesignToolbox()
    rows = generate_candidate_table(state)
    report_path = REPORT_DIR / f"{stem}.md"
    csv_path = CANDIDATE_DIR / f"{stem}.csv"
    json_path = CANDIDATE_DIR / f"{stem}.json"
    report_path.write_text(state.report, encoding="utf-8")
    toolbox.export_csv(rows, csv_path)
    toolbox.export_json(model_to_dict(state), json_path)
    return {"report": str(report_path), "csv": str(csv_path), "json": str(json_path)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the SynGlue-Agent PROTAC workflow.")
    parser.add_argument(
        "--mode",
        default="design",
        choices=["ask", "design", "agentic-design", "validate", "ternary", "report"],
        help="Execution mode for the app/CLI router.",
    )
    parser.add_argument(
        "request",
        nargs="?",
        default="Design CRBN-based PROTACs for BRD4 with PEG, alkyl, piperazine, and triazole linkers.",
        help="Natural-language degradation objective.",
    )
    parser.add_argument("--smiles", default="", help="SMILES input for validate/ternary mode.")
    parser.add_argument("--target-uniprot-id", default="", help="Optional target UniProt ID for ternary mode.")
    parser.add_argument("--e3-uniprot-id", default="", help="Optional E3 UniProt ID for ternary mode.")
    parser.add_argument("--stem", default="synglue_demo", help="Output filename stem.")
    args = parser.parse_args()
    if args.mode == "agentic-design":
        result = run_agentic_design(args.request, config={"stem": args.stem})
        print(json.dumps(model_to_dict(result), indent=2))
        return
    if args.mode == "design":
        state = run_workflow_from_request(args.request)
        paths = write_outputs(state, args.stem)
        print(json.dumps({"summary": summarize_state(state), "outputs": paths}, indent=2))
        return
    payload: dict[str, Any] = {"mode": args.mode, "request": args.request}
    if args.smiles:
        payload["smiles"] = args.smiles
    if args.target_uniprot_id:
        payload["target_uniprot_id"] = args.target_uniprot_id
    if args.e3_uniprot_id:
        payload["e3_uniprot_id"] = args.e3_uniprot_id
    print(json.dumps(run_mode(payload), indent=2))


if __name__ == "__main__":
    main()

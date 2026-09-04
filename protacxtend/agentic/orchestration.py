"""Seven-layer orchestration for agentic PROTAC design."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Optional

from protacxtend.agentic.audit import ScientificCriticAgent
from protacxtend.agentic.decision_making import DecisionMakingAgent
from protacxtend.agentic.execution import ExecutionAgent
from protacxtend.agentic.goal_setting import GoalSettingAgent
from protacxtend.agentic.learning import LearningAgent
from protacxtend.agentic.perception import PerceptionAgent
from protacxtend.agentic.provenance import ProvenanceBuilder
from protacxtend.agentic.reasoning import ReasoningAgent
from protacxtend.backend.config import CANDIDATE_DIR, REPORT_DIR, ensure_directories
from protacxtend.backend.schemas import WorkflowState, model_to_dict
from protacxtend.schemas.agentic_schema import AgenticWorkflowResult
from protacxtend.tools.report_generator import export_csv, export_json, generate_candidate_table


class OrchestratorAgent:
    """Coordinate perception, reasoning, goals, decisions, execution, critique, learning, and reporting."""

    name = "OrchestratorAgent"

    def __init__(self):
        self.perception_agent = PerceptionAgent()
        self.reasoning_agent = ReasoningAgent()
        self.goal_agent = GoalSettingAgent()
        self.decision_agent = DecisionMakingAgent()
        self.execution_agent = ExecutionAgent()
        self.critic_agent = ScientificCriticAgent()
        self.learning_agent = LearningAgent()
        self.provenance_builder = ProvenanceBuilder()

    def run(self, request: str, config: Optional[dict[str, Any]] = None) -> AgenticWorkflowResult:
        ensure_directories()
        config = config or {}
        run_id = str(config.get("run_id") or f"agentic-{uuid.uuid4().hex[:12]}")
        stem = str(config.get("stem") or run_id)

        perception = self.perception_agent.run(request, config)
        reasoning = self.reasoning_agent.run(perception)
        goal = self.goal_agent.run(perception, reasoning, config)
        decision = self.decision_agent.choose_next_action(perception, reasoning, goal)

        failed_steps: list[dict[str, Any]] = []
        warnings = list(perception.scientific_risk_flags)
        tool_results = []
        workflow_state: WorkflowState | None = None
        memory_updates = []
        candidate_provenance = []
        provenance_log = []
        report_paths: dict[str, str] = {}
        ranked_rows: list[dict[str, Any]] = []

        if decision.action_name == "ask_user_for_clarification":
            failed_steps.append({"step": decision.action_name, "reason": decision.reason_for_action})
            return AgenticWorkflowResult(
                run_id=run_id,
                final_status="needs_user_input",
                perception=model_to_dict(perception),
                reasoning=model_to_dict(reasoning),
                design_goal=model_to_dict(goal),
                decision_trace=[model_to_dict(decision)],
                warnings=warnings + ["Missing required target. No scientific output was generated."],
                failed_steps=failed_steps,
            )

        result = self.execution_agent.run(decision)
        tool_results.append(self.execution_agent.result_as_dict(result))
        if result.status != "success":
            failed_steps.append({"step": decision.action_name, "error": result.error_message})
            fallback = self.decision_agent.choose_next_action(perception, reasoning, goal, last_result=result)
            return AgenticWorkflowResult(
                run_id=run_id,
                final_status="failed",
                perception=model_to_dict(perception),
                reasoning=model_to_dict(reasoning),
                design_goal=model_to_dict(goal),
                decision_trace=[model_to_dict(decision), model_to_dict(fallback)],
                warnings=warnings + ["Deterministic execution failed; no candidate claims were made."],
                failed_steps=failed_steps,
                tool_results=tool_results,
            )

        workflow_state = result.output
        if not isinstance(workflow_state, WorkflowState):
            failed_steps.append({"step": decision.action_name, "error": "Tool did not return WorkflowState"})
            return AgenticWorkflowResult(
                run_id=run_id,
                final_status="failed",
                perception=model_to_dict(perception),
                reasoning=model_to_dict(reasoning),
                design_goal=model_to_dict(goal),
                decision_trace=[model_to_dict(decision)],
                warnings=warnings + ["Unexpected workflow output type."],
                failed_steps=failed_steps,
                tool_results=tool_results,
            )

        critic = self.critic_agent.review(workflow_state)
        warnings.extend(str(item) for item in critic.get("warnings", []))
        if critic.get("status") == "fail":
            failed_steps.append({"step": "scientific_critic", "actions": critic.get("actions", [])})

        candidate_provenance = self.provenance_builder.build_candidate_provenance(workflow_state)
        provenance_log = self.provenance_builder.provenance_log(workflow_state)
        memory_record = self.learning_agent.store_from_workflow(run_id, request, workflow_state, config.get("user_feedback"))
        memory_updates.append(memory_record)

        ranked_rows = generate_candidate_table(workflow_state)
        report = self._build_agentic_report(
            request=request,
            goal=goal,
            perception=perception,
            reasoning=reasoning,
            workflow_state=workflow_state,
            critic=critic,
            candidate_provenance=candidate_provenance,
            memory_record=memory_record,
        )
        report_path = REPORT_DIR / f"{stem}.md"
        csv_path = CANDIDATE_DIR / f"{stem}.csv"
        json_path = CANDIDATE_DIR / f"{stem}.json"
        report_path.write_text(report, encoding="utf-8")
        export_csv(ranked_rows, csv_path)
        export_json(
            {
                "run_id": run_id,
                "workflow_state": model_to_dict(workflow_state),
                "perception": model_to_dict(perception),
                "reasoning": model_to_dict(reasoning),
                "design_goal": model_to_dict(goal),
                "candidate_provenance": model_to_dict(candidate_provenance),
                "critic": critic,
            },
            json_path,
        )
        report_paths = {"markdown": str(report_path), "csv": str(csv_path), "json": str(json_path)}

        final_status = "completed_with_warnings" if warnings or failed_steps else "completed"
        return AgenticWorkflowResult(
            run_id=run_id,
            final_status=final_status,
            perception=model_to_dict(perception),
            reasoning=model_to_dict(reasoning),
            design_goal=model_to_dict(goal),
            decision_trace=[model_to_dict(decision)],
            final_candidates=[model_to_dict(candidate) for candidate in workflow_state.final_ranked_candidates or workflow_state.valid_candidates],
            ranked_candidates=ranked_rows,
            warnings=sorted(set(warnings)),
            failed_steps=failed_steps,
            provenance_log=provenance_log,
            candidate_provenance=model_to_dict(candidate_provenance),
            tool_results=tool_results,
            memory_updates=[model_to_dict(record) for record in memory_updates],
            report_paths=report_paths,
            candidate_csv_path=str(csv_path),
            candidate_json_path=str(json_path),
            markdown_report=report,
        )

    def _build_agentic_report(
        self,
        request: str,
        goal: Any,
        perception: Any,
        reasoning: Any,
        workflow_state: WorkflowState,
        critic: dict[str, Any],
        candidate_provenance: list[Any],
        memory_record: Any,
    ) -> str:
        rows = generate_candidate_table(workflow_state)
        top_rows = rows[:10]
        assumptions = []
        if reasoning.e3_assessment.get("assumption"):
            assumptions.append("E3 ligase was not specified; CRBN/VHL default branching was treated as an assumption.")
        if perception.available_models.get("degradation", {}).get("status") != "model_loaded":
            assumptions.append("No trained degradation model was loaded; DC50/Dmax are heuristic fallback values.")
        tools_used = sorted({trace.agent for trace in workflow_state.workflow_log})
        prov_rows = candidate_provenance[:10]
        lines = [
            "# Agentic PROTACXtend Report",
            "",
            "Research-use only. Results are computational hypotheses and are not experimentally validated.",
            "",
            "## User Request",
            request,
            "",
            "## Parsed Design Goal",
            f"- Target: {goal.target or 'missing'}",
            f"- E3 ligase: {goal.e3_ligase}",
            f"- Candidate count: {goal.candidate_count}",
            f"- Validation depth: {goal.validation_depth}",
            f"- Objectives: {', '.join(goal.optimization_objectives)}",
            "",
            "## Assumptions",
            *[f"- {item}" for item in (assumptions or ["No additional assumptions beyond parsed request."])],
            "",
            "## Tools Used",
            *[f"- {item}" for item in tools_used],
            "",
            "## Models Used",
            f"- Degradation/DC50/Dmax: {workflow_state.degradation_predictions[0].model_version if workflow_state.degradation_predictions else 'not run'}",
            "- ADME/Tox: descriptor/rule-based or configured backend; see candidate warnings.",
            "",
            "## Fallbacks Used",
            *[f"- {flag}" for flag in perception.scientific_risk_flags],
            "",
            "## Candidate Summary",
            f"- Assembled candidates: {len(workflow_state.assembled_candidates)}",
            f"- Valid or unverified candidates: {len(workflow_state.valid_candidates)}",
            f"- Ranked candidates: {len(workflow_state.ranking_results)}",
            "",
            "## Ranking Table",
            "| Rank | Candidate | Score | Tier |",
            "| --- | --- | --- | --- |",
        ]
        for row in top_rows:
            candidate_label = row.get("Candidate ID") or row.get("Warhead name") or row.get("Full PROTAC SMILES", "")[:24]
            lines.append(f"| {row.get('Rank')} | {candidate_label} | {row.get('Final priority score')} | {row.get('Tier')} |")
        lines.extend(
            [
                "",
                "## Scientific Warnings",
                *[f"- {item}" for item in sorted(set(str(w) for w in critic.get("warnings", [])))],
                "",
                "## Applicability-Domain Assessment",
                f"- Records: {len(workflow_state.applicability_domain_results)}",
                "- Any outside-domain or missing assessments are treated as confidence downgrades.",
                "",
                "## Ternary Feasibility Status",
                f"- Records: {len(workflow_state.ternary_feasibility_results)}",
                "- Docking claims are made only when a docking backend actually ran.",
                "",
                "## Provenance Table",
                "| Candidate | Warhead | E3 ligand | Linker | Degradation model | RDKit status |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
        )
        for item in prov_rows:
            lines.append(
                f"| {item.candidate_id} | {item.source_warhead} | {item.source_e3_ligand} | {item.source_linker} | "
                f"{item.degradation_model_version or 'not_run'} | {item.rdkit_validation_status} |"
            )
        lines.extend(
            [
                "",
                "## Failed Steps And Recovery Actions",
                *[f"- {item}" for item in (critic.get("actions", []) or ["No stop-level recovery action required."])],
                "",
                "## Reusable Memory Lessons",
                *[f"- {item}" for item in (memory_record.reusable_lessons or ["No reusable lessons recorded."])],
                "",
                "## Disclaimer",
                "This report is for research use only. It does not provide experimentally validated PROTAC activity, clinical safety, dosing, or synthesis recommendations.",
            ]
        )
        return "\n".join(lines) + "\n"


def run_agentic_design(request: str, config: Optional[dict[str, Any]] = None) -> AgenticWorkflowResult:
    """Run the full seven-layer agentic design workflow."""

    return OrchestratorAgent().run(request, config=config)

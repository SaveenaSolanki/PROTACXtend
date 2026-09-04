"""Self-describing tool registry for PROTACXtend."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Any, Dict, List

from protacxtend.toolkit.registry import get_tool_status
from protacxtend.tools.protac_autopilot_toolbox import ProtacXtendToolbox


REGISTRY_ALIASES = {
    "Target resolver": "Target assessment",
    "Inhibitor/activator miner": "Warhead mining",
    "Exit-vector hypothesis engine": "Warhead Agent",
    "Multi-strategy PROTAC constructor": "Assembly Agent",
    "SynGlue DC50/Dmax predictor": "DC50/Dmax prediction",
    "PROTAC-aware ADME/Tox stack": "ADME/Tox skill",
    "Workflow memory writer": "Data harmonization skill",
    "Candidate report generator": "Report generation",
    "Target resolver and tractability": "Target assessment",
    "Binder retrieval and warhead ranking": "Warhead mining",
    "E3 ligand comparison": "E3 ligase selection",
    "State-of-the-art linker panel": "Linker design",
    "Multi-strategy PROTAC construction": "Assembly Agent",
    "SynGlue DC50/Dmax stack": "DC50/Dmax prediction",
    "PROTAC-aware ADME/Tox": "ADME/Tox skill",
    "Novelty and duplicate checker": "Novelty/IP check",
    "Ternary feasibility triage": "Ternary complex modeling",
    "Tournament ranking": "Ranking skill",
    "Reflection and evolution": "Mini-PROTAC optimization",
    "Human review checkpoint": "Assay planning skill",
}


def _registry_status_for(name: str) -> Dict[str, Any]:
    registry_name = REGISTRY_ALIASES.get(name, name)
    status = get_tool_status(registry_name)
    return {"registry_name": registry_name, **status}


@dataclass(frozen=True)
class RegistryTool:
    tool_id: str
    name: str
    category: str
    agent_owner: str
    execution_layer: str
    input_schema: Dict[str, str]
    output_schema: Dict[str, str]
    execution_rules: List[str]
    status: str


class ToolRegistry:
    """Catalogs callable chemistry, biology, model, memory, and report tools."""

    def __init__(self):
        self.xtend = ProtacXtendToolbox()

    def tools(self) -> List[RegistryTool]:
        base = [
            RegistryTool(
                tool_id="target.resolve",
                name="Target resolver",
                category="biomedical_database",
                agent_owner="TargetResolverAgent",
                execution_layer="perception",
                input_schema={"target_name": "str", "uniprot_id": "optional str", "organism": "str"},
                output_schema={"target_record": "TargetRecord", "tractability_score": "float", "warnings": "list[str]"},
                execution_rules=["Prefer local curated target table", "Fallback to ChEMBL", "Use g:Profiler only for biology context"],
                status="active",
            ),
            RegistryTool(
                tool_id="ligand.mine",
                name="Inhibitor/activator miner",
                category="biomedical_database",
                agent_owner="BinderAgent",
                execution_layer="perception",
                input_schema={"target_record": "TargetRecord", "potency_threshold_nM": "float"},
                output_schema={"binders": "list[BinderRecord]", "source": "ChEMBL/PubChem/DrugBank-local"},
                execution_rules=["Never invent SMILES", "DrugBank requires licensed local CSV", "Flag mined ligands without curated exit vectors"],
                status="active",
            ),
            RegistryTool(
                tool_id="chem.exit_vector",
                name="Exit-vector hypothesis engine",
                category="chemistry_tool",
                agent_owner="ExitVectorAgent",
                execution_layer="computation",
                input_schema={"component_smiles": "str", "role": "warhead|e3_ligand"},
                output_schema={"attachment_atom": "optional int", "confidence": "float", "warning": "optional str"},
                execution_rules=["Use explicit attachment markers first", "Curated maps override heuristics", "Hypotheses require chemist review"],
                status="active",
            ),
            RegistryTool(
                tool_id="chem.construct",
                name="Multi-strategy PROTAC constructor",
                category="chemistry_tool",
                agent_owner="ConstructionAgent",
                execution_layer="action",
                input_schema={"warhead": "WarheadRecord", "linker": "LinkerRecord", "e3": "E3LigandRecord"},
                output_schema={"candidate": "CandidateRecord", "attempt": "ConstructionAttempt"},
                execution_rules=["RDKit sanitization required", "Preserve stereochemistry", "Log all failures"],
                status="active",
            ),
            RegistryTool(
                tool_id="model.degradation",
                name="SynGlue DC50/Dmax predictor",
                category="ml_model",
                agent_owner="PredictionAgent",
                execution_layer="computation",
                input_schema={"candidate": "CandidateRecord", "target": "TargetRecord", "cell_context": "optional str"},
                output_schema={"dc50_nM": "float", "dmax_percent": "float", "confidence": "float", "model_version": "str"},
                execution_rules=["Report model version", "Never present prediction as experiment", "Flag low applicability domain"],
                status="demo_stub_replaceable",
            ),
            RegistryTool(
                tool_id="model.admet",
                name="PROTAC-aware ADME/Tox stack",
                category="ml_model",
                agent_owner="ADMETAgent",
                execution_layer="computation",
                input_schema={"candidate_smiles": "str"},
                output_schema={"descriptors": "dict", "tox_risks": "dict", "penalty": "float"},
                execution_rules=["Do not apply strict Lipinski rejection", "Penalize high hERG/DILI/AMES", "Report approximate descriptors"],
                status="active",
            ),
            RegistryTool(
                tool_id="memory.workflow",
                name="Workflow memory writer",
                category="memory_tool",
                agent_owner="MemoryUpdateAgent",
                execution_layer="memory",
                input_schema={"workflow_state": "WorkflowState"},
                output_schema={"run_id": "str", "path": "str"},
                execution_rules=["Write reproducible JSON logs", "Keep provenance and warnings", "Do not overwrite previous runs"],
                status="active",
            ),
            RegistryTool(
                tool_id="report.generate",
                name="Candidate report generator",
                category="report_tool",
                agent_owner="ReportAgent",
                execution_layer="action",
                input_schema={"workflow_state": "WorkflowState", "format": "markdown|csv|json"},
                output_schema={"candidate_table": "list[dict]", "report": "str"},
                execution_rules=["Include guardrails", "Include provenance", "Separate computational priority from synthesis recommendation"],
                status="active",
            ),
        ]
        return base

    def as_rows(self) -> List[Dict[str, Any]]:
        rows = [asdict(tool) for tool in self.tools()]
        for row in rows:
            status = _registry_status_for(row["name"])
            row["registry_name"] = status["registry_name"]
            row["registered"] = status["registered"]
            row["available"] = status["available"]
            row["executable"] = status["executable"]
            row["registry_status"] = "executable" if status["executable"] else "available" if status["available"] else "registered" if status["registered"] else "unregistered"
            row["integration_note"] = "" if status["executable"] else "planned integration"
        for capability in self.xtend.catalog_as_rows():
            status = _registry_status_for(capability["name"])
            rows.append(
                {
                    "tool_id": capability["name"].lower().replace(" ", "."),
                    "name": capability["name"],
                    "registry_name": status["registry_name"],
                    "category": capability["layer"],
                    "agent_owner": capability["agent"],
                    "execution_layer": capability["layer"],
                    "input_schema": capability["inputs"],
                    "output_schema": capability["outputs"],
                    "execution_rules": "Registered via PROTACXtend toolbox capability catalog",
                    "status": capability["status"],
                    "registered": status["registered"],
                    "available": status["available"],
                    "executable": status["executable"],
                    "registry_status": "executable" if status["executable"] else "available" if status["available"] else "registered" if status["registered"] else "unregistered",
                    "integration_note": "" if status["executable"] else "planned integration",
                }
            )
        return rows

    def as_display_rows(self) -> List[Dict[str, str]]:
        display_rows: List[Dict[str, str]] = []
        for row in self.as_rows():
            display_row: Dict[str, str] = {}
            for key, value in row.items():
                if isinstance(value, list):
                    display_row[key] = "; ".join(str(item) for item in value)
                elif isinstance(value, dict):
                    display_row[key] = json.dumps(value, ensure_ascii=True)
                else:
                    display_row[key] = "" if value is None else str(value)
            display_rows.append(display_row)
        return display_rows

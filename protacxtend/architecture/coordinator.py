"""Adaptive scientific coordinator for agentic architecture v1.

A real decision loop: GOAL → PLAN → ACT → OBSERVE → VERIFY → UPDATE → REPLAN →
CONTINUE/STOP/ABSTAIN. The coordinator selects the next action from the current
state (not a fixed script), executes real registered tools, records
``EvidenceRecord``s, consults an independent critic, and can genuinely revise the
plan when evidence invalidates an assumption. All decisions are typed and
traceable; nothing is fabricated when evidence is absent.
"""
from __future__ import annotations

import hashlib
import json
import time
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from protacxtend.backend.schemas import BaseModel, Field
from protacxtend.architecture.critic import CriticVerdictV1, ScientificCritic
from protacxtend.architecture.ontology import (
    EvidenceKind, EvidenceStatus, EvidenceRecordV1, Claim, Contradiction,
    Disagreement, UncertaintyAxis,
)
from protacxtend.architecture.state import (
    ARCHITECTURE_VERSION, TRACE_SCHEMA_VERSION, Budget, Plan, PlanStep,
    TerminalStatus, TherapeuticHypothesisState,
)
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _h(v: Any) -> str:
    return hashlib.sha256(json.dumps(v, sort_keys=True, default=str).encode()).hexdigest()[:16]


class DecisionType(str, Enum):
    CALL_TOOL = "CALL_TOOL"
    CALL_WORKER = "CALL_WORKER"
    RETRIEVE_EVIDENCE = "RETRIEVE_EVIDENCE"
    REVISE_PLAN = "REVISE_PLAN"
    RUN_VERIFIER = "RUN_VERIFIER"
    PROPOSE_EXPERIMENT = "PROPOSE_EXPERIMENT"
    ASK_HUMAN = "ASK_HUMAN"
    FINISH = "FINISH"
    ABSTAIN = "ABSTAIN"


class CoordinatorDecision(BaseModel):
    seq: int = 0
    decision_type: DecisionType = DecisionType.CALL_TOOL
    reason: str = ""
    state_dependencies: list[str] = Field(default_factory=list)
    expected_information: str = ""
    selected_capability: str = ""
    selected_tool: str = ""
    selected_worker: str = ""
    budget_effect: str = ""
    plan_version: int = 1


#: Worker ownership per action.
WORKER = {
    "resolve_target": "evidence", "retrieve_target_binders": "evidence",
    "select_e3": "protac_design", "assemble_reference": "protac_design",
    "assess_interaction": "interaction_state", "predict_degradation": "translational",
    "predict_admet": "translational", "verify": "critic", "finalize": "orchestrator",
}


class AdaptiveCoordinator:
    def __init__(self, request: str, *, target: str = "", e3: str = "",
                 run_id: str = "", mode: str = "scientific",
                 budget: Optional[Budget] = None) -> None:
        self.request = request
        self.budget = budget or Budget()
        self.critic = ScientificCritic()
        rid = run_id or f"agentv1_{int(time.time())}"
        self.state = TherapeuticHypothesisState()
        self.state.run_identity.run_id = rid
        self.state.run_identity.thread_id = rid
        self.state.run_identity.timestamp = _now()
        self.state.run_identity.execution_mode = mode
        self.state.request.original_query = request
        self.state.request.objective = request
        self._requested_target = (target or "").upper()
        self._requested_e3 = (e3 or "").upper()
        self._e3_order: list[str] = []
        self._e3_idx = 0
        self._interaction_done = False
        self._fallback_used: list[str] = []
        self._blocked: set[str] = set()
        self.trace: list[dict[str, Any]] = []
        self.t0 = time.time()
        self.fault: dict[str, str] = {}   # tool -> "unavailable" (fault injection)

    # ── trace ─────────────────────────────────────────────────────────
    def _record(self, *, role: str, worker: str, action: str, decision: CoordinatorDecision,
                observation: str, output_hash: str = "", evidence_ids: Optional[list[str]] = None,
                evidence_kind: str = "", gate: str = "", gate_result: str = "",
                failure: str = "", retry: int = 0, fallback: str = "",
                uncertainty_before: str = "", uncertainty_after: str = "",
                terminal: str = "", termination_reason: str = "") -> dict[str, Any]:
        rec = {
            "step": len(self.trace),
            "timestamp": _now(),
            "run_id": self.state.run_identity.run_id,
            "architecture_version": ARCHITECTURE_VERSION,
            "state_schema_version": self.state.run_identity.state_schema_version,
            "trace_schema_version": TRACE_SCHEMA_VERSION,
            "role": role, "worker": worker, "action": action,
            "plan_version": self.state.plan.version,
            "decision": decision.decision_type.value,
            "decision_reason": decision.reason,
            "selected_tool": decision.selected_tool,
            "inputs_hash": _h({"action": action, "plan": self.state.plan.version}),
            "observation": observation,
            "output_hash": output_hash,
            "evidence_ids": evidence_ids or [],
            "evidence_kind": evidence_kind,
            "gate": gate, "gate_result": gate_result,
            "failure": failure, "retry": retry, "fallback": fallback,
            "uncertainty_before": uncertainty_before, "uncertainty_after": uncertainty_after,
            "budget_after": {"steps": self.budget.steps_used,
                             "tool_calls": self.budget.tool_calls_used},
            "terminal_status": terminal, "termination_reason": termination_reason,
        }
        self.trace.append(rec)
        return rec

    # ── understanding & planning ──────────────────────────────────────
    def understand(self) -> None:
        target = self._requested_target
        if not target:
            import re
            m = re.findall(r"\b[A-Z][A-Z0-9]{2,9}\b", self.request)
            stop = {"PROTAC", "PROTACs", "E3", "TPD", "SMILES", "CRBN", "VHL", "DESIGN"}
            target = next((t for t in m if t not in stop), "")
        self._requested_target = target
        self.state.request.scientific_intent = "design" if "design" in self.request.lower() else "reason"
        self.state.request.constraints = ["scientific-mode: source-backed evidence only",
                                          "no fabricated measurements"]
        self.state.target_biology.target = target
        self._record(role="orchestrator", worker="orchestrator", action="understand",
                     decision=CoordinatorDecision(decision_type=DecisionType.CALL_WORKER,
                                                  reason="interpret objective"),
                     observation=f"intent={self.state.request.scientific_intent} target={target} "
                                 f"requested_e3={self._requested_e3 or 'unspecified'}")

    def initial_plan(self) -> Plan:
        steps = [
            PlanStep(step_id="s1", worker="evidence", action="resolve_target",
                     capability="target_biology"),
            PlanStep(step_id="s2", worker="evidence", action="retrieve_target_binders",
                     capability="warhead_evidence"),
            PlanStep(step_id="s3", worker="protac_design", action="select_e3",
                     capability="e3_selection"),
            PlanStep(step_id="s4", worker="protac_design", action="assemble_reference",
                     capability="candidate_assembly"),
            PlanStep(step_id="s5", worker="interaction_state", action="assess_interaction",
                     capability="ternary_docking"),
            PlanStep(step_id="s6", worker="translational", action="predict_degradation",
                     capability="protac_scoring"),
            PlanStep(step_id="s7", worker="translational", action="predict_admet",
                     capability="admet"),
            PlanStep(step_id="s8", worker="critic", action="verify", capability="critic"),
        ]
        self.state.plan = Plan(version=1, goal=f"design PROTAC for {self._requested_target}",
                               steps=[s.model_copy() for s in steps])
        self._record(role="orchestrator", worker="orchestrator", action="plan",
                     decision=CoordinatorDecision(decision_type=DecisionType.CALL_WORKER,
                                                  reason="initial dependency plan"),
                     observation=f"plan v1 with {len(steps)} steps")
        return self.state.plan

    # ── action selection (state-driven) ───────────────────────────────
    def _pick_action(self) -> CoordinatorDecision:
        st = self.state
        deps: list[str] = []
        if not st.target_biology.target:
            return CoordinatorDecision(decision_type=DecisionType.CALL_TOOL,
                                       reason="target identity unknown",
                                       selected_tool="resolve_target", selected_worker="evidence",
                                       selected_capability="target_biology")
        if st.target_biology.target_validation == "UNKNOWN":
            deps.append("target_biology.target_validation=UNKNOWN")
            return CoordinatorDecision(decision_type=DecisionType.RETRIEVE_EVIDENCE,
                                       reason="target identity not yet resolved",
                                       state_dependencies=deps,
                                       selected_tool="resolve_target", selected_worker="evidence",
                                       selected_capability="target_biology")
        if not st.protac_design.target_warheads and "retrieve_target_binders" not in self._blocked:
            deps.append("protac_design.target_warheads=[]")
            return CoordinatorDecision(decision_type=DecisionType.RETRIEVE_EVIDENCE,
                                       reason="no warhead/binder evidence yet",
                                       state_dependencies=deps,
                                       selected_tool="retrieve_target_binders",
                                       selected_worker="evidence",
                                       selected_capability="warhead_evidence")
        if not st.protac_design.e3_recruiters and "select_e3" not in self._blocked:
            deps.append("protac_design.e3_recruiters=[]")
            return CoordinatorDecision(decision_type=DecisionType.CALL_WORKER,
                                       reason="no E3 recruiter selected",
                                       state_dependencies=deps,
                                       selected_worker="protac_design",
                                       selected_tool="select_e3",
                                       selected_capability="e3_selection")
        if not st.protac_design.candidate_structures:
            deps.append("protac_design.candidate_structures=[]")
            return CoordinatorDecision(decision_type=DecisionType.CALL_WORKER,
                                       reason="no assembled source-backed reference yet",
                                       state_dependencies=deps,
                                       selected_worker="protac_design",
                                       selected_tool="assemble_reference",
                                       selected_capability="candidate_assembly")
        if st.interaction_state.cooperativity == "UNKNOWN" and not self._interaction_done:
            deps.append("interaction_state.cooperativity=UNKNOWN")
            return CoordinatorDecision(decision_type=DecisionType.CALL_TOOL,
                                       reason="ternary/cooperativity not assessed",
                                       state_dependencies=deps,
                                       selected_worker="interaction_state",
                                       selected_tool="predict_cooperativity",
                                       selected_capability="cooperativity")
        if st.cellular_pharmacology.degradation_prediction == "UNKNOWN" and "predict_degradation" not in self._blocked:
            deps.append("cellular_pharmacology.degradation_prediction=UNKNOWN")
            return CoordinatorDecision(decision_type=DecisionType.CALL_TOOL,
                                       reason="degradation not predicted",
                                       state_dependencies=deps,
                                       selected_worker="translational",
                                       selected_tool="predict_degradation",
                                       selected_capability="protac_scoring")
        if st.translational.admet == "UNKNOWN" and "predict_admet" not in self._blocked:
            deps.append("translational.admet=UNKNOWN")
            return CoordinatorDecision(decision_type=DecisionType.CALL_TOOL,
                                       reason="developability not assessed",
                                       state_dependencies=deps,
                                       selected_worker="translational",
                                       selected_tool="predict_admet",
                                       selected_capability="admet")
        return CoordinatorDecision(decision_type=DecisionType.RUN_VERIFIER,
                                   reason="all planned evidence collected; verify",
                                   selected_worker="critic", selected_tool="verify")

    # ── real tool execution ───────────────────────────────────────────
    def _run_tool(self, tool: str, params: dict, *, allow_network: bool = False) -> dict:
        if self.fault.get(tool) == "unavailable":
            raise RuntimeError(f"tool {tool!r} unavailable (injected fault)")
        from protacxtend.runtime.agent_tools import run_agent_tool
        self.budget.tool_calls_used += 1
        return run_agent_tool(tool, params, use_fixture=False, allow_network=allow_network)

    def _execute(self, d: CoordinatorDecision) -> tuple[str, dict]:
        st = self.state
        tool = d.selected_tool
        try:
            if tool == "resolve_target":
                res = self._run_tool("resolve_target", {"target_name": st.target_biology.target}, allow_network=True)
                data = ((res.get("scientific_result") or {}).get("result") or {}).get("data") or {}
                matches = data.get("matches") or []
                acc = next((m.get("accession") for m in matches
                            if (m.get("organism") or "").lower().startswith("homo")), None)
                if acc:
                    st.target_biology.target_validation = f"resolved:{acc}"
                    eid = f"ev_target_{_h(acc)}"
                    st.add_evidence(EvidenceRecordV1(
                        evidence_id=eid, content=f"{st.target_biology.target} -> {acc}",
                        evidence_kind=EvidenceKind.RETRIEVED, evidence_status=EvidenceStatus.SUPPORTED,
                        source="UniProt", source_version="live", tool="resolve_target",
                        output_hash=_h(data), supports_claims=["target_identity"], timestamp=_now()))
                    return f"resolved {st.target_biology.target} -> {acc}", {"evidence_id": eid}
                return "target resolution returned no human match", {}

            if tool == "retrieve_target_binders":
                res = self._run_tool("retrieve_target_binders",
                                     {"target_name": st.target_biology.target, "top_k": 5}, allow_network=True)
                data = ((res.get("scientific_result") or {}).get("result") or {}).get("data") or {}
                binders = data.get("binders") or data.get("molecules") or []
                names = [str(b.get("name") or b.get("molecule_chembl_id") or b.get("smiles") or "")[:40]
                         for b in binders[:5] if isinstance(b, dict)]
                kind, status, source = EvidenceKind.RETRIEVED, EvidenceStatus.PARTIALLY_SUPPORTED, str(res.get("provider") or "ChEMBL")
                if not [n for n in names if n]:
                    # Live retrieval failed/empty: fall back to the source-backed
                    # verified warhead (real evidence), never a fabricated binder.
                    from protacxtend.tools import verified_components as vc
                    w = vc.warhead_for(st.target_biology.target)
                    if w:
                        names = [w.get("name", "")]
                        source = str(w.get("source", "verified_components"))
                        status = EvidenceStatus.SUPPORTED
                    else:
                        names = []
                st.protac_design.target_warheads = [n for n in names if n]
                eid = f"ev_binders_{_h(data)}_{_h(names)}"
                st.add_evidence(EvidenceRecordV1(
                    evidence_id=eid, content=f"{len(st.protac_design.target_warheads)} warhead record(s)",
                    evidence_kind=kind, evidence_status=status,
                    source=source, tool="retrieve_target_binders",
                    output_hash=_h(data), supports_claims=["warhead_evidence"], timestamp=_now()))
                if not st.protac_design.target_warheads:
                    return "no warhead evidence available", {"evidence_id": eid, "no_progress": True}
                return f"{len(st.protac_design.target_warheads)} warhead record(s)", {"evidence_id": eid}

            if tool == "select_e3":
                return self._select_e3()

            if tool == "assemble_reference":
                return self._assemble_reference()

            if tool == "predict_cooperativity":
                return self._assess_interaction()

            if tool == "predict_degradation":
                smi = st.protac_design.candidate_structures[0] if st.protac_design.candidate_structures else ""
                e3 = st.protac_design.e3_recruiters[0] if st.protac_design.e3_recruiters else ""
                # cell_line is a required tool input: take it from the source
                # PROTAC's assay record (never invented). If absent, the tool
                # returns a typed missing-input failure.
                from protacxtend.tools import verified_components as vc
                ref = vc.reference_components(st.target_biology.target, e3) or {}
                cell_line = str(((ref.get("reference") or {}).get("assays") or {}).get("cell_line") or "")
                if cell_line:
                    st.biological_context.cell_context = cell_line
                params = {"smiles": smi, "e3": e3, "target": st.target_biology.target}
                if cell_line:
                    params["cell_line"] = cell_line
                res = self._run_tool("predict_degradation", params)
                data = ((res.get("scientific_result") or {}).get("result") or {}).get("data") or {}
                st.cellular_pharmacology.degradation_prediction = (
                    "predicted" if res.get("status") == "ok" else "not_assessable")
                eid = f"ev_deg_{_h(data)}"
                st.add_evidence(EvidenceRecordV1(
                    evidence_id=eid, content="degradation ML prediction",
                    evidence_kind=EvidenceKind.MODEL_PREDICTED,
                    evidence_status=EvidenceStatus.PARTIALLY_SUPPORTED,
                    model="chemprop/tack", model_version=str(data.get("model_version") or ""),
                    tool="predict_degradation", output_hash=_h(data),
                    supports_claims=["degradation_prediction"], timestamp=_now()))
                st.axes.degradation_ml = "HIGH" if st.cellular_pharmacology.degradation_prediction == "predicted" else "UNKNOWN"
                return f"degradation={st.cellular_pharmacology.degradation_prediction}", {"evidence_id": eid}

            if tool == "predict_admet":
                smi = st.protac_design.candidate_structures[0] if st.protac_design.candidate_structures else ""
                res = self._run_tool("predict_admet", {"smiles": smi})
                data = ((res.get("scientific_result") or {}).get("result") or {}).get("data") or {}
                st.translational.admet = "calculated" if res.get("status") == "ok" else "not_assessable"
                eid = f"ev_admet_{_h(data)}"
                st.add_evidence(EvidenceRecordV1(
                    evidence_id=eid, content="ADMET/physchem calculation",
                    evidence_kind=EvidenceKind.DERIVED,
                    evidence_status=EvidenceStatus.PARTIALLY_SUPPORTED,
                    tool="predict_admet", output_hash=_h(data),
                    supports_claims=["developability"], timestamp=_now()))
                return f"admet={st.translational.admet}", {"evidence_id": eid}

            if tool == "verify":
                return "verifier requested", {}

            return f"no executor for {tool}", {}
        except Exception as exc:  # noqa: BLE001
            return self._handle_failure(d, exc)

    # ── specialised actions ───────────────────────────────────────────
    def _e3_candidates(self) -> list[str]:
        from protacxtend.tools import verified_components as vc
        order: list[str] = []
        if self._requested_e3:
            order.append(self._requested_e3)
        for path in vc.verified_paths():
            if (path.get("target") or "").upper() == self.state.target_biology.target.upper():
                if path["e3_ligase"] not in order:
                    order.append(path["e3_ligase"])
        for e in ("VHL", "CRBN"):
            if e not in order:
                order.append(e)
        return order

    def _select_e3(self) -> tuple[str, dict]:
        from protacxtend.tools import verified_components as vc
        if not self._e3_order:
            self._e3_order = self._e3_candidates()
        st = self.state
        target = st.target_biology.target
        eid = ""
        while self._e3_idx < len(self._e3_order):
            e3 = self._e3_order[self._e3_idx]
            ref = vc.reference_components(target, e3)
            if ref:
                st.protac_design.e3_recruiters = [e3]
                st.protac_design.e3_candidates = self._e3_order
                eid = f"ev_e3_{_h(ref['reference'])}"
                st.add_evidence(EvidenceRecordV1(
                    evidence_id=eid,
                    content=f"source-backed {target}-{e3} pair {ref['reference'].get('name')}",
                    evidence_kind=EvidenceKind.RETRIEVED, evidence_status=EvidenceStatus.SUPPORTED,
                    source=ref["reference"].get("doi", ""),
                    citation=ref["reference"].get("citation", ""),
                    tool="verified_components", output_hash=_h(ref["reference"].get("inchikey", "")),
                    supports_claims=["e3_selection", "route_supported"], timestamp=_now()))
                st.axes.target_engagement = "HIGH"
                return f"E3 selected: {e3} ({ref['reference'].get('name')})", {"evidence_id": eid}
            # no source-backed pair for this E3 -> evidence that contradicts the route assumption
            eid = f"ev_e3_missing_{e3}_{_h(target)}"
            st.add_evidence(EvidenceRecordV1(
                evidence_id=eid,
                content=f"no source-backed {target}-{e3} component pair",
                evidence_kind=EvidenceKind.INSUFFICIENT_EVIDENCE,
                evidence_status=EvidenceStatus.INSUFFICIENT_EVIDENCE,
                tool="verified_components",
                contradicts_claims=["route_supported"], timestamp=_now()))
            self._e3_idx += 1
            if self._e3_idx < len(self._e3_order):
                return (f"E3 {e3} unsupported for {target}; evidence recorded",
                        {"evidence_id": eid, "needs_replan": True})
        st.protac_design.e3_recruiters = []
        return f"no source-backed E3 recruiter for {target}", {"needs_replan": True,
                                                              "no_progress": True,
                                                              "evidence_id": eid}

    def _assemble_reference(self) -> tuple[str, dict]:
        from protacxtend.tools import verified_components as vc
        from protacxtend.tools.protac_toolbox import ProtacDesignToolbox
        st = self.state
        target = st.target_biology.target
        e3 = st.protac_design.e3_recruiters[0] if st.protac_design.e3_recruiters else ""
        ref = vc.reference_components(target, e3)
        if not ref:
            return "no verified reference to assemble", {"needs_replan": True}
        box = ProtacDesignToolbox()
        full, msg = box.assemble_components(ref["warhead"]["smiles"], ref["linker"]["smiles"],
                                            ref["e3_ligand"]["smiles"])
        if not full:
            return f"assembly failed: {msg}", {}
        st.protac_design.candidate_structures = [full]
        st.protac_design.attachment_points = ["warhead:1", "e3_ligand:1", "linker:1,2"]
        eid = f"ev_asm_{_h(full)}"
        st.add_evidence(EvidenceRecordV1(
            evidence_id=eid, content=f"assembled {ref['reference'].get('name')}",
            evidence_kind=EvidenceKind.DERIVED, evidence_status=EvidenceStatus.SUPPORTED,
            tool="ProtacDesignToolbox.assemble_components", output_hash=_h(full),
            source=ref["reference"].get("doi", ""),
            supports_claims=["route_supported", "candidate_assembly"], timestamp=_now()))
        return f"assembled source-backed candidate ({ref['reference'].get('name')})", {"evidence_id": eid}

    def _assess_interaction(self) -> tuple[str, dict]:
        st = self.state
        self._interaction_done = True
        try:
            res = self._run_tool("predict_cooperativity", {})  # no pose supplied
            data = ((res.get("scientific_result") or {}).get("result") or {}).get("data") or {}
            st.interaction_state.cooperativity = "predicted"
            eid = f"ev_coop_{_h(data)}"
            st.add_evidence(EvidenceRecordV1(
                evidence_id=eid, content="cooperativity assessment",
                evidence_kind=EvidenceKind.MODEL_PREDICTED,
                evidence_status=EvidenceStatus.PARTIALLY_SUPPORTED,
                tool="predict_cooperativity", output_hash=_h(data),
                supports_claims=["cooperativity"], timestamp=_now()))
            st.axes.cooperativity = "MEDIUM"
            return "cooperativity assessed", {"evidence_id": eid}
        except Exception as exc:  # noqa: BLE001
            name = type(exc).__name__
            if "MissingScientificInput" in name:
                eid = f"ev_coop_missing_{_h(str(exc))}"
                st.add_evidence(EvidenceRecordV1(
                    evidence_id=eid,
                    content="cooperativity requires a ternary pose (not supplied)",
                    evidence_kind=EvidenceKind.INSUFFICIENT_EVIDENCE,
                    evidence_status=EvidenceStatus.INSUFFICIENT_EVIDENCE,
                    tool="predict_cooperativity", context={"error": str(exc)[:200]},
                    timestamp=_now()))
                st.interaction_state.cooperativity = "INSUFFICIENT_EVIDENCE"
                st.axes.cooperativity = "UNKNOWN"
                st.epistemics.uncertainties.append(UncertaintyAxis(
                    axis="cooperativity", level="UNKNOWN",
                    basis="no ternary pose available",
                    evidence_gain_if_resolved="ternary geometry/cooperativity assessment"))
                return f"cooperativity not assessable: {str(exc)[:80]}", {"abstain_reason": str(exc)}
            # non-input failure -> try a lower-fidelity fallback
            return self._handle_failure(
                CoordinatorDecision(decision_type=DecisionType.CALL_TOOL,
                                    selected_tool="predict_cooperativity",
                                    selected_worker="interaction_state"),
                exc, fallback_tool="run_scientific_capability")

    def _handle_failure(self, d: CoordinatorDecision, exc: Exception,
                        fallback_tool: str = "") -> tuple[str, dict]:
        name = type(exc).__name__
        msg = f"{name}: {exc}"
        self.state.control.failures.append(f"{d.selected_tool}:{name}")
        self.budget.retries_used += 1
        if fallback_tool:
            try:
                from protacxtend.runtime.executor import run_capability
                out = run_capability("ternary_complex_modeling",
                                     {"smiles": (self.state.protac_design.candidate_structures or [""])[0]})
                self._fallback_used.append(f"{d.selected_tool}->{fallback_tool}")
                self.state.control.fallbacks.append(f"{d.selected_tool}->{fallback_tool}")
                self.state.interaction_state.ternary_geometry = (
                    "proxy" if out.get("executed") else "not_assessable")
                eid = f"ev_fallback_{_h(out)}"
                self.state.add_evidence(EvidenceRecordV1(
                    evidence_id=eid, content="fallback ternary geometry proxy",
                    evidence_kind=EvidenceKind.DERIVED,
                    evidence_status=EvidenceStatus.INSUFFICIENT_EVIDENCE,
                    tool=fallback_tool, context={"original_tool": d.selected_tool,
                                                 "failure": name},
                    timestamp=_now()))
                self.state.axes.ternary_geometry = "LOW"
                return (f"{d.selected_tool} failed ({name}); fell back to {fallback_tool}",
                        {"fallback": fallback_tool, "failure": name, "evidence_id": eid})
            except Exception as fexc:  # noqa: BLE001
                self._fallback_used.append(f"{d.selected_tool}->{fallback_tool}(failed:{type(fexc).__name__})")
        return f"{d.selected_tool} failed: {msg}", {"failure": name, "no_progress": True}

    # ── replanning ────────────────────────────────────────────────────
    def _maybe_replan(self, obs: dict) -> bool:
        if not obs.get("needs_replan"):
            return False
        st = self.state
        # gather the latest insufficient/contradicted evidence as triggers
        triggers = [e.evidence_id for e in st.evidence.evidence_records
                    if e.evidence_status in {EvidenceStatus.INSUFFICIENT_EVIDENCE,
                                             EvidenceStatus.CONTRADICTED}]
        remaining = self._e3_order[self._e3_idx:] if self._e3_idx < len(self._e3_order) else []
        if not remaining:
            # No alternate route remains: do not fabricate a replan; let the
            # no-progress guard block the action and drive a typed abstention.
            return False
        alt = remaining[0] if remaining else ""
        reason = (f"requested/assumed E3 route for {st.target_biology.target} has no "
                  f"source-backed component pair; revise E3 assumption")
        steps = [
            PlanStep(step_id="s1", worker="evidence", action="resolve_target",
                     capability="target_biology", status="done"),
            PlanStep(step_id="s2", worker="evidence", action="retrieve_target_binders",
                     capability="warhead_evidence", status="done"),
            PlanStep(step_id="s3b", worker="protac_design", action="select_e3",
                     capability="e3_selection", status="active",
                     observation=f"switch to alternate E3: {alt or 'none available'}"),
            PlanStep(step_id="s4", worker="protac_design", action="assemble_reference",
                     capability="candidate_assembly"),
            PlanStep(step_id="s5", worker="interaction_state", action="assess_interaction",
                     capability="ternary_docking"),
            PlanStep(step_id="s8", worker="critic", action="verify", capability="critic"),
        ]
        st.revision(reason, steps, triggers)
        rec = self._record(role="critic", worker="critic", action="revise_plan",
                           decision=CoordinatorDecision(
                               decision_type=DecisionType.REVISE_PLAN, reason=reason,
                               state_dependencies=["protac_design.e3_recruiters=[]",
                                                   "route_supported contradicted"],
                               expected_information="an E3 route with a source-backed component pair",
                               selected_worker="protac_design", selected_tool="select_e3",
                               plan_version=st.plan.version),
                           observation=f"plan v{st.plan.version}: {reason}",
                           evidence_ids=triggers[-3:], gate="route_support", gate_result="REVISE")
        return True

    # ── verify & finalize ─────────────────────────────────────────────
    def _verify(self) -> CriticReportAlias:  # type: ignore[name-defined]
        st = self.state
        if st.protac_design.candidate_structures:
            st.add_claim(Claim(
                claim_id="c1", statement="a source-backed PROTAC candidate was assembled",
                evidence_ids=[e.evidence_id for e in st.evidence.evidence_records
                              if "candidate_assembly" in e.supports_claims or "route_supported" in e.supports_claims],
                evidence_kind=EvidenceKind.DERIVED, evidence_status=EvidenceStatus.SUPPORTED))
        route = self.critic.assess_route(st)
        report = self.critic.evaluate_claim(st, "c1") if st.evidence.claims else route
        return report

    def _finalize(self, report) -> TerminalStatus:
        st = self.state
        if not st.protac_design.candidate_structures:
            st.finalization.terminal_status = TerminalStatus.JUSTIFIED_ABSTENTION
            st.finalization.termination_reason = (
                "no source-backed candidate could be assembled from permitted evidence")
            return st.finalization.terminal_status
        if report.verdict is CriticVerdictV1.BLOCK:
            st.finalization.terminal_status = TerminalStatus.INSUFFICIENT_EVIDENCE
            st.finalization.termination_reason = "; ".join(report.blocking_reasons) or "critic block"
        elif report.verdict is CriticVerdictV1.REVISE:
            st.finalization.terminal_status = TerminalStatus.PARTIAL_SUCCESS
            st.finalization.termination_reason = "candidate assembled; critic requested revision"
        else:
            st.finalization.terminal_status = TerminalStatus.SUCCESS
            st.finalization.termination_reason = "source-backed candidate assembled and verified"
        st.finalization.verdict = report.verdict.value
        st.finalization.overall_verdict = report.verdict.value
        st.finalization.recommended_next_action = (
            "experimental ternary/cooperativity + degradation assay"
            if st.interaction_state.cooperativity == "INSUFFICIENT_EVIDENCE"
            else "proceed to developability assessment")
        return st.finalization.terminal_status

    # ── main loop ─────────────────────────────────────────────────────
    def run(self, *, max_steps: Optional[int] = None) -> TherapeuticHypothesisState:
        self.understand()
        self.initial_plan()
        limit = max_steps or self.budget.max_steps
        report = None
        while self.budget.steps_used < limit and not self.budget.exhausted():
            st = self.state
            d = self._pick_action()
            if d.decision_type is DecisionType.RUN_VERIFIER:
                report = self._verify()
                self._record(role="critic", worker="critic", action="verify",
                             decision=d, observation=f"critic verdict={report.verdict.value}",
                             gate="scientific_critic", gate_result=report.verdict.value)
                break
            self.budget.steps_used += 1
            fp_before = self.state.fingerprint()
            obs_text, obs = self._execute(d)
            eid = obs.get("evidence_id", "")
            e = next((x for x in st.evidence.evidence_records if x.evidence_id == eid), None)
            self._record(role=WORKER.get(d.selected_tool, "agent"), worker=d.selected_worker,
                         action=d.selected_tool or d.decision_type.value, decision=d,
                         observation=obs_text, evidence_ids=[eid] if eid else [],
                         evidence_kind=e.evidence_kind.value if e else "",
                         failure=obs.get("failure", ""), fallback=obs.get("fallback", ""),
                         gate="route_support" if obs.get("needs_replan") else "",
                         gate_result="REVISE" if obs.get("needs_replan") else "")
            if self._maybe_replan(obs):
                continue
            # No-progress guard (STOPPING_FAILURE prevention): an action that
            # explicitly reports no progress is blocked so it cannot be retried
            # indefinitely.
            if obs.get("no_progress"):
                self._blocked.add(d.selected_tool)
            if obs.get("abstain_reason"):
                # cooperativity not assessable — continue to finalize; terminal is justified
                pass
        if report is None:
            report = self._verify()
        self._finalize(report)
        self._record(role="orchestrator", worker="orchestrator", action="finalize",
                     decision=CoordinatorDecision(decision_type=DecisionType.FINISH,
                                                  reason=self.state.finalization.termination_reason),
                     observation=f"terminal={self.state.finalization.terminal_status.value}",
                     terminal=self.state.finalization.terminal_status.value,
                     termination_reason=self.state.finalization.termination_reason)
        return self.state

    # ── checkpoint / resume ───────────────────────────────────────────
    def checkpoint(self, path: str | Path) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        blob = {
            "state": self.state.model_dump(mode="json"),
            "trace": self.trace,
            "e3_order": self._e3_order,
            "e3_idx": self._e3_idx,
            "interaction_done": self._interaction_done,
            "budget": self.budget.model_dump(mode="json"),
            "requested_target": self._requested_target,
            "requested_e3": self._requested_e3,
            "fault": self.fault,
        }
        p.write_text(json.dumps(blob, indent=1, default=str), encoding="utf-8")
        return p

    @classmethod
    def resume(cls, path: str | Path) -> "AdaptiveCoordinator":
        blob = json.loads(Path(path).read_text(encoding="utf-8"))
        st = TherapeuticHypothesisState.model_validate(blob["state"])
        obj = cls(st.request.original_query, target=blob.get("requested_target", ""),
                  e3=blob.get("requested_e3", ""), run_id=st.run_identity.run_id,
                  mode=st.run_identity.execution_mode,
                  budget=Budget.model_validate(blob["budget"]))
        obj.state = st
        obj.trace = blob["trace"]
        obj._e3_order = blob["e3_order"]
        obj._e3_idx = blob["e3_idx"]
        obj._interaction_done = blob["interaction_done"]
        obj.fault = blob.get("fault", {})
        return obj


# Late import alias for the critic report type used in signatures above.
from protacxtend.architecture.critic import CriticReport as CriticReportAlias  # noqa: E402

__all__ = ["DecisionType", "CoordinatorDecision", "AdaptiveCoordinator", "WORKER"]

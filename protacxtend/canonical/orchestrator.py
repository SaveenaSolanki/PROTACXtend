"""Canonical Orchestrator — the single control plane.

``CanonicalOrchestrator.run`` executes the whole stack in order:

    Scientific Request Parser
      -> Task Graph
      -> Specialized Scientific Modules
      -> Tool Executor
      -> Evidence Store
      -> Critic / Verifier
      -> Decision Engine
      -> TherapeuticStrategy

The two historical execution engines are no longer alternative entry points;
they are selected *inside the Tool Executor* (``engine="deterministic"`` or
``"adaptive"``) and share the parser, evidence ledger, critic and decision
engine. That is what collapses the stacks: one control flow, one provenance
model, one place where routing and stopping decisions are made.

``review_engine_state`` lets the unified runtime reuse an engine result that
was already computed (so the expensive science runs exactly once) while still
running the canonical parser, modules, evidence store, critic and decision
engine over it.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any

from protacxtend.canonical.critic import CriticVerifier
from protacxtend.canonical.decision import DecisionEngine
from protacxtend.canonical.evidence import CanonicalEvidenceStore
from protacxtend.canonical.modules import ScientificModule, canonical_modules
from protacxtend.canonical.request_parser import ScientificRequestParser
from protacxtend.canonical.schemas import CanonicalRunResult, TaskStatus
from protacxtend.canonical.task_graph import TaskGraphExecutor
from protacxtend.canonical.tool_executor import ToolExecutor


def _design_gate_from_request(user_request: str, config: dict[str, Any]) -> str | None:
    """Return a block reason when the therapeutics gate rejects this request,
    else None. Mirrors the runtime gate so every public design entry point
    (run_protacpilot, run_canonical/strategy CLI) cannot bypass the gates."""
    try:
        from protacxtend.agents.runtime import _target_spec_from_request
        from protacxtend.therapeutics.api import design_gate
        spec = config.get("target_spec") or _target_spec_from_request(user_request)
        if not spec:
            return None
        design_gate(spec,
                    disease=config.get("disease", "") or "",
                    cell_line=config.get("cell_line", "") or "",
                    require_assessment=bool(config.get("require_assessment", False)),
                    allow_requires_review=bool(config.get("allow_requires_review", True)))
        return None
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        if "blocked" in msg or "requires one" in msg:
            return msg
        # unexpected error: do not silently bypass the gate
        return f"therapeutics gate error: {msg}"


class CanonicalOrchestrator:
    name = "CanonicalOrchestrator"

    def __init__(
        self,
        *,
        parser: ScientificRequestParser | None = None,
        modules: dict[str, ScientificModule] | None = None,
        critic: CriticVerifier | None = None,
        decision: DecisionEngine | None = None,
    ):
        self.parser = parser or ScientificRequestParser()
        self.modules = modules or canonical_modules()
        self.critic = critic or CriticVerifier()
        self.decision = decision or DecisionEngine()

    # ------------------------------------------------------------------
    def run(self, user_request: str, config: dict[str, Any] | None = None) -> CanonicalRunResult:
        """Run the full stack, letting the Tool Executor own computation.

        TargetTherapeuticsAssessment gate applies here too: the strategy CLI is
        a public design entry point and must not bypass identity / chemistry /
        window gates."""
        started = time.time()
        config = dict(config or {})
        run_id = str(config.get("run_id") or f"canonical_{uuid.uuid4().hex[:10]}")
        engine = str(config.get("engine") or "deterministic")
        tools = ToolExecutor(engine=engine, config={**config, "raw_request": user_request}, strict=bool(config.get("strict", False)))

        blocked = _design_gate_from_request(user_request, config)
        if blocked is not None:
            # model_construct: a gate-blocked result carries NO strategy/critic
            # objects (nothing was computed) — visible as status=blocked.
            return CanonicalRunResult.model_construct(
                run_id=run_id, status="blocked", errors=[blocked],
                warnings=[], strategy=None, critic=None, module_results=[],
                task_graph=None, runtime_s=round(time.time() - started, 3),
            )

        # Force the (cached) engine so modules share one computation.
        engine_state = tools.call("scientific_engine", {"request": user_request})
        return self._assemble(
            user_request, engine_state, run_id=run_id, engine=engine, config=config, started=started, tools=tools
        )

    # ------------------------------------------------------------------
    def review_engine_state(
        self,
        user_request: str,
        engine_state: Any,
        *,
        run_id: str = "",
        engine: str = "deterministic",
        config: dict[str, Any] | None = None,
    ) -> CanonicalRunResult:
        """Run the canonical control plane over an already-computed engine state.

        Used by the unified runtime so deterministic/adaptive computation is not
        repeated by the orchestrator.
        """
        config = dict(config or {})
        run_id = run_id or str(config.get("run_id") or f"canonical_{uuid.uuid4().hex[:10]}")
        tools = ToolExecutor(engine=engine, config=config, strict=bool(config.get("strict", False)))
        return self._assemble(
            user_request,
            engine_state,
            run_id=run_id,
            engine=engine,
            config=config,
            started=time.time(),
            tools=tools,
        )

    # ------------------------------------------------------------------
    def _assemble(
        self,
        user_request: str,
        engine_state: Any,
        *,
        run_id: str,
        engine: str,
        config: dict[str, Any],
        started: float,
        tools: ToolExecutor | None = None,
    ) -> CanonicalRunResult:
        tools = tools or ToolExecutor(engine=engine, config=config)
        started_at = datetime.now(timezone.utc).isoformat()
        request = self.parser.parse(user_request, config)
        evidence = CanonicalEvidenceStore(run_id=run_id, persist=bool(config.get("persist_evidence", False)))

        graph_executor = TaskGraphExecutor(modules=self.modules)
        task_graph, module_results, state = graph_executor.run(
            request,
            tools=tools,
            evidence=evidence,
            config={**config, "engine": engine},
            engine_state=engine_state,
        )

        verdict = self.critic.review(
            state,
            module_results,
            evidence,
            tools_provenance=tools.provenance(),
            config={**config, "engine": engine},
        )
        if state.policy_decisions:
            verdict.policy_action = str(state.policy_decisions[-1].get("action") or "")
        strategy = self.decision.decide(
            run_id=run_id,
            request=request,
            state=state,
            module_results=module_results,
            evidence=evidence,
            verdict=verdict,
            config={**config, "engine": engine},
            started_at=started_at,
            runtime_s=time.time() - started,
            artifact_paths=config.get("artifact_paths") or {},
        )

        warnings = sorted(set(state.warnings) | {w for result in module_results for w in result.warnings})
        return CanonicalRunResult(
            run_id=run_id,
            status=self._run_status(verdict.status, module_results, state.abstained),
            request=request,
            task_graph=task_graph,
            module_results=module_results,
            critic=verdict,
            strategy=strategy,
            engine_state=engine_state,
            policy_decisions=list(state.policy_decisions),
            warnings=warnings,
            errors=list(state.errors) + [c.error for c in tools.calls if c.error],
            runtime_s=round(time.time() - started, 3),
        )

    @staticmethod
    def _run_status(verdict_status: str, module_results: list[Any], abstained: bool = False) -> str:
        if any(result.status == TaskStatus.FAILED for result in module_results):
            return "failed"
        if abstained or any(result.status == TaskStatus.ABSTAINED for result in module_results):
            return "abstained"
        if verdict_status == "REJECT":
            return "rejected"
        if verdict_status in {"REVISE", "INSUFFICIENT EVIDENCE"}:
            return "completed_with_warnings"
        return "completed"


def run_canonical(user_request: str, config: dict[str, Any] | None = None) -> CanonicalRunResult:
    """Convenience entry point for the canonical stack."""
    return CanonicalOrchestrator().run(user_request, config=config)

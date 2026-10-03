"""Task Graph — one declarative DAG for every canonical run.

The graph is built from the nine module declarations in
:mod:`protacxtend.canonical.modules`. Both legacy execution engines are now
*leaves* reached through the Tool Executor; control flow lives only here.

``TaskGraphExecutor`` runs nodes in dependency order, records a
:class:`ModuleResult` per node, and applies the explicit
:class:`~protacxtend.canonical.policy.ExecutionPolicy` retry / fallback /
abstention policy:

* required node fails, no recovery        -> run stops (fail closed)
* transient failure and retries remain    -> retry, recording every attempt
* module declares a usable fallback       -> run fallback, mark ``degraded``
* required node unrecoverable, abstain on  -> ``abstained`` (typed non-answer)
* optional node fails                      -> continue with a ``degraded`` record
"""

from __future__ import annotations

import time
from typing import Any

from protacxtend.canonical.evidence import CanonicalEvidenceStore
from protacxtend.canonical.failures import Failure, classify_failure
from protacxtend.canonical.modules import (
    CanonicalState,
    ModuleContext,
    ScientificModule,
    canonical_modules,
    module_dependencies,
)
from protacxtend.canonical.policy import (
    ExecutionPolicy,
    PolicyAction,
    policy_from_config,
)
from protacxtend.canonical.schemas import (
    ModuleResult,
    ScientificRequest,
    TaskGraphSpec,
    TaskNodeSpec,
    TaskStatus,
)
from protacxtend.canonical.tool_executor import ToolExecutor


def _failure_from_result(result: ModuleResult) -> Failure:
    message = "; ".join(result.errors) or result.summary or "module failed"
    return classify_failure(
        message,
        module_id=result.module_id,
        tool=str((result.provenance or {}).get("tool") or ""),
    )


class TaskGraph:
    def __init__(
        self,
        spec: TaskGraphSpec,
        modules: dict[str, ScientificModule],
        policy: ExecutionPolicy | None = None,
        fallbacks: dict[str, str] | None = None,
    ):
        self.spec = spec
        self.modules = modules
        self.policy = policy or ExecutionPolicy()
        self.fallbacks = dict(fallbacks or {})
        self._by_id = {node.node_id: node for node in spec.nodes}

    @property
    def order(self) -> list[str]:
        return self.spec.topological_order()

    # ------------------------------------------------------------------
    def _fallback_for(self, node: TaskNodeSpec, module: ScientificModule) -> str:
        return self.fallbacks.get(node.node_id) or getattr(module, "fallback", "") or ""

    def _run_node(self, node: TaskNodeSpec, module: ScientificModule, state: CanonicalState,
                  context: ModuleContext) -> ModuleResult:
        """Run one node, applying retry/fallback/abstention."""
        fallback_id = self._fallback_for(node, module)
        has_fallback = bool(fallback_id) and fallback_id in self.modules
        attempt = 1
        result: ModuleResult
        while True:
            started = time.time()
            try:
                result = module.execute(state, context)
                if not result.evidence_refs:
                    result.evidence_refs = context.evidence.add_module_result(result)
            except Exception as exc:  # noqa: BLE001 - a module must never kill the run
                message = f"{type(exc).__name__}: {exc}"
                result = ModuleResult(
                    module_id=node.node_id,
                    title=node.title,
                    status=TaskStatus.FAILED,
                    summary=f"Module crashed: {message}",
                    errors=[message],
                    provenance={
                        "tool": f"module:{node.node_id}",
                        "tool_version": "crashed",
                        "registry_source": "inferred",
                    },
                )
                result.evidence_refs = context.evidence.add_module_result(result)
            result.runtime_s = round(time.time() - started, 6)

            if result.status != TaskStatus.FAILED:
                return result

            failure = _failure_from_result(result)
            decision = self.policy.on_failure(
                failure,
                module_id=node.node_id,
                attempt=attempt,
                required=not node.optional,
                has_fallback=has_fallback,
                fallback_module=fallback_id,
            )
            state.policy_decisions.append(
                {
                    **decision.model_dump(),
                    "attempt": attempt,
                    "failure_message": failure.message,
                }
            )

            if decision.action == PolicyAction.RETRY:
                attempt += 1
                if self.policy.retry.backoff_s:
                    time.sleep(self.policy.retry.backoff_s)
                continue

            if decision.action == PolicyAction.FALLBACK and has_fallback:
                fallback = self.modules[fallback_id]
                fb_started = time.time()
                try:
                    fb_result = fallback.execute(state, context)
                    if not fb_result.evidence_refs:
                        fb_result.evidence_refs = context.evidence.add_module_result(fb_result)
                except Exception as exc:  # noqa: BLE001
                    fb_result = ModuleResult(
                        module_id=fallback_id,
                        title=fallback.title,
                        status=TaskStatus.FAILED,
                        summary=f"Fallback crashed: {type(exc).__name__}: {exc}",
                        errors=[str(exc)],
                    )
                    fb_result.evidence_refs = context.evidence.add_module_result(fb_result)
                fb_result.runtime_s = round(time.time() - fb_started, 6)
                if fb_result.status != TaskStatus.FAILED:
                    if fb_result.status == TaskStatus.SUCCEEDED:
                        fb_result.status = TaskStatus.DEGRADED
                    fb_result.outputs = {
                        **fb_result.outputs,
                        "_fallback_used": fallback_id,
                        "_fallback_for": node.node_id,
                    }
                    fb_result.warnings = [
                        *fb_result.warnings,
                        f"Primary module {node.node_id} failed; fallback {fallback_id} used.",
                    ]
                    return fb_result
                # fallback failed too -> fall through to abstain/stop
                result = fb_result
                failure = _failure_from_result(result)
                decision = self.policy.on_failure(
                    failure,
                    module_id=node.node_id,
                    attempt=attempt,
                    required=not node.optional,
                    has_fallback=False,
                )
                state.policy_decisions.append({**decision.model_dump(), "attempt": attempt,
                                               "failure_message": failure.message})

            if decision.action == PolicyAction.ABSTAIN:
                result.status = TaskStatus.ABSTAINED
                result.outputs = {
                    **result.outputs,
                    "abstained": True,
                    "failure_class": failure.failure_class.value,
                    "abstention_reason": decision.reason,
                }
                return result

            return result

    # ------------------------------------------------------------------
    def run(self, state: CanonicalState, context: ModuleContext) -> list[ModuleResult]:
        results: dict[str, ModuleResult] = {}
        for node_id in self.order:
            node = self._by_id[node_id]
            module = self.modules[node_id]
            result = self._run_node(node, module, state, context)
            results[node_id] = result
            state.module_outputs[node_id] = dict(result.outputs)

            if result.status == TaskStatus.FAILED and not node.optional:
                state.errors.append(f"{node_id}: {result.summary}")
                break
            if result.status == TaskStatus.ABSTAINED and not node.optional:
                state.abstained = True
                state.warnings.append(f"{node_id}: {result.outputs.get('abstention_reason') or result.summary}")
                break
            state.warnings.extend(result.warnings)
            state.errors.extend(result.errors)
        return [results[node.node_id] for node in self.spec.nodes if node.node_id in results]


class TaskGraphExecutor:
    """Build and execute the canonical task graph."""

    def __init__(
        self,
        modules: dict[str, ScientificModule] | None = None,
        dependencies: dict[str, list[str]] | None = None,
        policy: ExecutionPolicy | None = None,
        fallbacks: dict[str, str] | None = None,
    ):
        self.modules = modules or canonical_modules()
        self.dependencies = dependencies or module_dependencies()
        self.policy = policy
        self.fallbacks = dict(fallbacks or {})

    def build(self, request: ScientificRequest) -> TaskGraphSpec:
        nodes: list[TaskNodeSpec] = []
        # The graph is defined by the declared dependencies when supplied, so
        # fallback-only implementations can live in ``self.modules`` without
        # becoming standalone nodes.
        node_ids = list(self.dependencies) if self.dependencies else list(self.modules)
        for module_id in node_ids:
            module = self.modules[module_id]
            nodes.append(
                TaskNodeSpec(
                    node_id=module_id,
                    module_id=module_id,
                    title=module.title,
                    depends_on=[d for d in self.dependencies.get(module_id, []) if d in node_ids],
                    optional=module.optional,
                    reason=module.description,
                )
            )
        return TaskGraphSpec(graph_id=f"canonical:{request.target or 'unresolved'}", nodes=nodes)

    def run(
        self,
        request: ScientificRequest,
        *,
        tools: ToolExecutor,
        evidence: CanonicalEvidenceStore,
        config: dict[str, Any] | None = None,
        engine_state: Any = None,
    ) -> tuple[TaskGraphSpec, list[ModuleResult], CanonicalState]:
        config = dict(config or {})
        spec = self.build(request)
        policy = self.policy or policy_from_config(config)
        graph = TaskGraph(spec, self.modules, policy=policy, fallbacks=self.fallbacks)
        state = CanonicalState(request=request, engine_state=engine_state)
        context = ModuleContext(tools=tools, evidence=evidence, config=config)
        results = graph.run(state, context)
        return spec, results, state

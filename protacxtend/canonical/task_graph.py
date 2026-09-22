"""Task Graph — one declarative DAG for every canonical run.

The graph is built from the nine module declarations in
:mod:`protacxtend.canonical.modules`. Both legacy execution engines are now
*leaves* reached through the Tool Executor; control flow lives only here.

``TaskGraphExecutor`` runs nodes in dependency order, records a
:class:`ModuleResult` per node, and applies a simple, explicit failure policy:

* required node fails        -> run status ``failed`` (fail closed)
* optional node fails        -> run continues with a ``degraded`` record
"""

from __future__ import annotations

import time
from typing import Any

from protacxtend.canonical.evidence import CanonicalEvidenceStore
from protacxtend.canonical.modules import (
    CanonicalState,
    ModuleContext,
    ScientificModule,
    canonical_modules,
    module_dependencies,
)
from protacxtend.canonical.schemas import (
    ModuleResult,
    ScientificRequest,
    TaskGraphSpec,
    TaskNodeSpec,
    TaskStatus,
)
from protacxtend.canonical.tool_executor import ToolExecutor


class TaskGraph:
    def __init__(self, spec: TaskGraphSpec, modules: dict[str, ScientificModule]):
        self.spec = spec
        self.modules = modules
        self._by_id = {node.node_id: node for node in spec.nodes}

    @property
    def order(self) -> list[str]:
        return self.spec.topological_order()

    def run(self, state: CanonicalState, context: ModuleContext) -> list[ModuleResult]:
        results: dict[str, ModuleResult] = {}
        for node_id in self.order:
            node = self._by_id[node_id]
            module = self.modules[node_id]
            started = time.time()
            try:
                result = module.execute(state, context)
            except Exception as exc:  # noqa: BLE001 - a module must never kill the run
                result = ModuleResult(
                    module_id=node_id,
                    title=node.title,
                    status=TaskStatus.FAILED,
                    summary=f"Module crashed: {exc}",
                    errors=[str(exc)],
                    provenance={"tool_version": f"protacxtend:{node_id}:v1"},
                )
                result.evidence_refs = context.evidence.add_module_result(result)
            result.runtime_s = round(time.time() - started, 6)
            results[node_id] = result
            state.module_outputs[node_id] = dict(result.outputs)

            if result.status == TaskStatus.FAILED and not node.optional:
                state.errors.append(f"{node_id}: {result.summary}")
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
    ):
        self.modules = modules or canonical_modules()
        self.dependencies = dependencies or module_dependencies()

    def build(self, request: ScientificRequest) -> TaskGraphSpec:
        nodes: list[TaskNodeSpec] = []
        for module_id, module in self.modules.items():
            nodes.append(
                TaskNodeSpec(
                    node_id=module_id,
                    module_id=module_id,
                    title=module.title,
                    depends_on=list(self.dependencies.get(module_id, [])),
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
        spec = self.build(request)
        graph = TaskGraph(spec, self.modules)
        state = CanonicalState(request=request, engine_state=engine_state)
        context = ModuleContext(tools=tools, evidence=evidence, config=dict(config or {}))
        results = graph.run(state, context)
        return spec, results, state

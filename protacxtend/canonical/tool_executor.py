"""Tool Executor — the single gateway for scientific computation.

Every scientific module calls the tool executor instead of importing and
invoking engines directly. This is what makes the two legacy execution
engines pluggable rather than parallel stacks:

* ``engine="deterministic"`` -> :func:`protacxtend.agents.graph.run_syn_glue_workflow`
* ``engine="adaptive"``      -> :func:`protacxtend.agents.agentic_core.run_agentic_workflow`
                                with the real scientific nodes

Both are invoked through ``ToolExecutor.call("scientific_engine")`` and cached
for the duration of a run, so every module sees the same evidence picture and
the run has exactly one computation.

The executor records tool provenance (name, engine, runtime, cache hit) and
fails closed for required calls when ``strict`` is set.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable


class ToolExecutionError(RuntimeError):
    """Raised when a required tool call fails in strict mode."""


@dataclass
class ToolCallRecord:
    tool: str
    status: str
    runtime_s: float
    cache_hit: bool = False
    error: str = ""
    provenance: dict[str, Any] = field(default_factory=dict)


class ToolExecutor:
    """One registry, one cache, one provenance trail."""

    VALID_ENGINES = {"deterministic", "adaptive"}

    def __init__(self, engine: str = "deterministic", config: dict[str, Any] | None = None, strict: bool = False):
        if engine not in self.VALID_ENGINES:
            raise ValueError(f"Unknown execution engine '{engine}'. Valid: {sorted(self.VALID_ENGINES)}")
        self.engine = engine
        self.config = dict(config or {})
        self.strict = strict
        self._engine_state: Any = None
        self._engine_ran = False
        self.calls: list[ToolCallRecord] = []
        self._tools: dict[str, Callable[[dict[str, Any]], Any]] = {
            "scientific_engine": self._scientific_engine,
            "resistance_profile": self._resistance_profile,
        }

    # ------------------------------------------------------------------
    def call(self, name: str, payload: dict[str, Any] | None = None) -> Any:
        payload = payload or {}
        if name not in self._tools:
            raise ToolExecutionError(f"Tool not registered: {name}")
        started = time.time()
        cache_hit = name == "scientific_engine" and self._engine_ran
        try:
            result = self._tools[name](payload)
        except Exception as exc:  # noqa: BLE001
            self.calls.append(
                ToolCallRecord(tool=name, status="failed", runtime_s=round(time.time() - started, 6), error=str(exc))
            )
            if self.strict:
                raise ToolExecutionError(f"{name} failed: {exc}") from exc
            return {"_tool_error": str(exc), "_tool": name}
        self.calls.append(
            ToolCallRecord(
                tool=name,
                status="ok",
                runtime_s=round(time.time() - started, 6),
                cache_hit=cache_hit,
                provenance={"engine": self.engine} if name == "scientific_engine" else {},
            )
        )
        return result

    # ------------------------------------------------------------------
    def _scientific_engine(self, payload: dict[str, Any]) -> Any:
        if self._engine_ran:
            return self._engine_state
        request = str(payload.get("request") or self.config.get("raw_request") or "")
        if self.engine == "deterministic":
            from protacxtend.agents.graph import run_syn_glue_workflow

            self._engine_state = run_syn_glue_workflow(request)
        else:
            from protacxtend.agents.agentic_core import run_agentic_workflow
            from protacxtend.agents.real_nodes import real_nodes

            self._engine_state = run_agentic_workflow(request, legacy_agents=real_nodes())
        self._engine_ran = True
        return self._engine_state

    def _resistance_profile(self, payload: dict[str, Any]) -> dict[str, Any]:
        from protacxtend.modules.resistance_mechanisms import predict_resistance

        return predict_resistance(
            str(payload.get("e3_ligase") or ""),
            str(payload.get("target") or ""),
        )

    # ------------------------------------------------------------------
    def provenance(self) -> dict[str, Any]:
        return {
            "engine": self.engine,
            "engine_ran": self._engine_ran,
            "calls": [
                {
                    "tool": call.tool,
                    "status": call.status,
                    "runtime_s": call.runtime_s,
                    "cache_hit": call.cache_hit,
                    "error": call.error,
                }
                for call in self.calls
            ],
        }

    @property
    def engine_state(self) -> Any:
        return self._engine_state

"""Benchmark baselines: retrieval-only, tool-only, LLM, and PROTACXtend.

These are the matched-compute control arms for the 48-task benchmark. They are
deterministic and offline by default so the comparison harness is reproducible
without network access:

* :class:`RetrievalOnlyBaseline` — only the retrieval/identity tools a task
  permits (``resolve_target``, ``select_e3_ligase`` …), no chemistry/design;
* :class:`ToolOnlyBaseline` — every *offline* permitted adapter, no LLM
  orchestration;
* :class:`LLMBaseline` — the same provider/model as the candidate through
  :mod:`benchmark_runner.live`; fails closed (``skipped_no_credentials``) when
  no API key is present rather than fabricating an answer;
* :class:`ProtacxtendOfflineBaseline` — the full canonical deterministic stack
  (optional; expensive).

Returned :class:`BaselineAnswer` objects are JSON-safe and preserve tool calls,
status and errors, so the harness can score and audit them without re-running.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from benchmark_runner import matched_tools
from benchmark_runner.runner import TaskInput

#: Tools that only read evidence and never design.
_RETRIEVAL_TOOLS = {
    "resolve_target", "search_uniprot", "retrieve_target_binders", "select_e3_ligase",
    "retrieve_e3_evidence", "search_pubchem", "search_chembl", "search_bindingdb",
    "search_europe_pmc", "search_pubmed", "search_web", "deep_research", "verify_crossref",
    "retrieve_fulltext", "retrieve_pdb",
}


@dataclass
class BaselineAnswer:
    system: str
    task_id: str
    status: str = "ok"  # ok | abstained | skipped_no_credentials | error
    answer: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "system": self.system,
            "task_id": self.task_id,
            "status": self.status,
            "answer": self.answer,
            "tool_calls": self.tool_calls,
            "evidence": self.evidence,
            "errors": self.errors,
            "metadata": self.metadata,
        }


def _extract_target(task: TaskInput) -> str:
    """Best-effort target extraction from the blinded question + supplied inputs."""
    try:
        from protacxtend.nlp.entity_extraction import extract_entities

        entities = extract_entities(task.question)
        if entities.target_gene:
            return entities.target_gene
    except Exception:  # noqa: BLE001
        pass
    for item in task.supplied_inputs or []:
        text = str(item)
        for marker in ("gene/target name:", "target:", "gene:"):
            if marker in text.lower():
                return text.split(":", 1)[1].strip().split()[0]
    return ""


def _call_tool(tool: str, params: dict[str, Any], *, offline_only: bool) -> dict[str, Any]:
    """Invoke one agent tool in TEST mode; never raise."""
    from protacxtend.runtime import modes
    from protacxtend.runtime.agent_tools import run_agent_tool

    try:
        with modes.execution_mode(modes.ExecutionMode.TEST):
            run = run_agent_tool(tool, params, use_fixture=False, allow_network=not offline_only)
    except Exception as exc:  # noqa: BLE001
        return {"tool": tool, "status": "error", "error": f"{type(exc).__name__}: {exc}"}
    envelope = run.get("scientific_result") or {}
    return {
        "tool": tool,
        "status": run.get("status", "error"),
        "executed": run.get("EXECUTED", False),
        "valid_output": run.get("VALID_OUTPUT", False),
        "data": (envelope.get("result") or {}).get("data", {}),
        "error": run.get("error", ""),
        "failure_code": run.get("failure_code", ""),
    }


class BaselineBase:
    system_id = "baseline"

    def run(self, task: TaskInput, *, offline_only: bool = True) -> BaselineAnswer:  # pragma: no cover - abstract
        raise NotImplementedError

    # ------------------------------------------------------------------
    def _matched_agent_tools(self, task: TaskInput, *, only_offline: bool) -> list[str]:
        tools: list[str] = []
        for entry in matched_tools.match_ids(task.permitted_tools):
            if only_offline and not entry.offline:
                continue
            tools.extend(entry.agent_tools)
        return sorted(set(tools))

    def _run_tools(self, task: TaskInput, tools: list[str], *, offline_only: bool) -> BaselineAnswer:
        target = _extract_target(task)
        calls: list[dict[str, Any]] = []
        evidence: list[str] = []
        errors: list[str] = []
        for tool in tools:
            if tool in _RETRIEVAL_TOOLS:
                params = {"target_name": target, "target": target, "query": target,
                          "term": target, "e3": "", "top_k": 5}
            else:
                params = {"target": target, "smiles": "", "candidates": []}
            result = _call_tool(tool, params, offline_only=offline_only)
            calls.append(result)
            for src in result.get("data", {}).get("sources", []) if isinstance(result.get("data"), dict) else []:
                evidence.append(str(src))
            if result.get("error"):
                errors.append(f"{tool}: {result['error']}")
        answer = self._build_answer(task, target, calls)
        status = "ok" if any(c.get("valid_output") for c in calls) else "abstained"
        return BaselineAnswer(
            system=self.system_id, task_id=task.task_id, status=status, answer=answer,
            tool_calls=calls, evidence=evidence, errors=errors,
            metadata={"n_tools": len(tools), "offline_only": offline_only, "target": target},
        )

    @staticmethod
    def _build_answer(task: TaskInput, target: str, calls: list[dict[str, Any]]) -> str:
        parts: list[str] = []
        if target:
            parts.append(f"target {target}")
        for call in calls:
            data = call.get("data")
            if call.get("status") in ("ok", "partial") and data:
                parts.append(f"{call['tool']}: {data}")
        return " | ".join(parts) if parts else ""


class RetrievalOnlyBaseline(BaselineBase):
    """Identity/retrieval tools only; no design or prediction."""

    system_id = "retrieval-only"

    def run(self, task: TaskInput, *, offline_only: bool = True) -> BaselineAnswer:
        tools = [t for t in self._matched_agent_tools(task, only_offline=offline_only) if t in _RETRIEVAL_TOOLS]
        return self._run_tools(task, tools, offline_only=offline_only)


class ToolOnlyBaseline(BaselineBase):
    """Every offline permitted adapter, invoked without LLM orchestration."""

    system_id = "tool-only"

    def run(self, task: TaskInput, *, offline_only: bool = True) -> BaselineAnswer:
        tools = self._matched_agent_tools(task, only_offline=offline_only)
        return self._run_tools(task, tools, offline_only=offline_only)


class LLMBaseline(BaselineBase):
    """The candidate's provider/model with no tools or orchestration."""

    system_id = "Base-LLM-control"

    def run(self, task: TaskInput, *, offline_only: bool = True) -> BaselineAnswer:
        try:
            from benchmark_runner import live

            if not live._api_key():
                return BaselineAnswer(
                    system=self.system_id, task_id=task.task_id,
                    status="skipped_no_credentials",
                    errors=["no provider API key present"],
                    metadata={"provider": live.PROVIDER, "model": live.MODEL},
                )
            adapter = live.BaseLLMLiveAdapter(self.system_id, allow_real=True)
            result = adapter.execute(task, {"seed": 0, "temperature": 0.0})
            return BaselineAnswer(
                system=self.system_id, task_id=task.task_id,
                status=result.get("status", "ok"), answer=str(result.get("answer") or ""),
                metadata={"provider": result.get("provider"), "model": result.get("model"),
                          "tokens_in": result.get("tokens_in"), "tokens_out": result.get("tokens_out")},
            )
        except Exception as exc:  # noqa: BLE001
            return BaselineAnswer(
                system=self.system_id, task_id=task.task_id, status="error",
                errors=[f"{type(exc).__name__}: {exc}"],
            )


class ProtacxtendOfflineBaseline(BaselineBase):
    """The full canonical deterministic stack (expensive; opt-in)."""

    system_id = "PROTACXtend-offline"

    def run(self, task: TaskInput, *, offline_only: bool = True) -> BaselineAnswer:
        try:
            from protacxtend.canonical import CanonicalOrchestrator

            result = CanonicalOrchestrator().run(task.question, config={"engine": "deterministic"})
            strategy = result.strategy
            answer = " | ".join(
                [
                    f"target {strategy.target}",
                    f"e3 {strategy.recommended_e3}",
                    f"candidates {len(strategy.candidate_protacs)}",
                    f"stopping_state {strategy.stopping_state}",
                ]
            )
            return BaselineAnswer(
                system=self.system_id, task_id=task.task_id,
                status="ok" if result.status == "completed" else result.status,
                answer=answer,
                errors=list(result.errors),
                metadata={"run_id": result.run_id, "critic_status": result.critic.status,
                          "failure_categories": result.critic.failure_categories},
            )
        except Exception as exc:  # noqa: BLE001
            return BaselineAnswer(
                system=self.system_id, task_id=task.task_id, status="error",
                errors=[f"{type(exc).__name__}: {exc}"],
            )


BASELINES: dict[str, type[BaselineBase]] = {
    "retrieval-only": RetrievalOnlyBaseline,
    "tool-only": ToolOnlyBaseline,
    "Base-LLM-control": LLMBaseline,
    "PROTACXtend-offline": ProtacxtendOfflineBaseline,
}


def build_baseline(system_id: str) -> BaselineBase:
    if system_id not in BASELINES:
        raise ValueError(f"unknown baseline {system_id!r}; choices: {sorted(BASELINES)}")
    return BASELINES[system_id]()


__all__ = [
    "BASELINES",
    "BaselineAnswer",
    "BaselineBase",
    "LLMBaseline",
    "ProtacxtendOfflineBaseline",
    "RetrievalOnlyBaseline",
    "ToolOnlyBaseline",
    "build_baseline",
]

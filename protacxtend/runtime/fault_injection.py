"""Fault-injection harness for the live retrieval path.

Scenarios: delay, timeout, HTTP 429, HTTP 500, malformed JSON, truncated
payload, empty result and fallback recovery. Each run records whether the fault
was *detected*, whether the path *recovered*, whether it *fell back* to a
non-live tier, whether it correctly *abstained*, and whether any *hallucinated*
binder was produced (a SMILES not present in the live payload or local evidence).
"""

from __future__ import annotations

import json
import time
import urllib.error
from dataclasses import dataclass, field
from typing import Any, Callable
from unittest import mock


@dataclass
class FaultScenario:
    name: str
    kind: str
    retry_after: str | None = None
    valid_after_faults: int = 0  # number of faults before a valid response
    fake_smiles: str = "COc1ccccc1"
    metadata: dict[str, Any] = field(default_factory=dict)


_VALID_PAYLOAD = {
    "getLindsByUniprotResponse": {
        "bdb.primary": "O60885",
        "bdb.affinities": [
            {"bdb.monomerid": 1, "bdb.smile": "COc1ccccc1O", "bdb.affinity_type": "IC50",
             "bdb.affinity": "10"},
        ],
    }
}
_EMPTY_PAYLOAD = {"getLindsByUniprotResponse": {"bdb.affinities": []}}
_MALFORMED = b"{not valid json"
_TRUNCATED = b'{"getLindsByUniprotResponse": {"bdb.affinities": [{"bdb.smile": "CC"'


class _FakeResponse:
    def __init__(self, body: bytes):
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _make_urlopen(scenario: FaultScenario, calls: list[int]) -> Callable:
    def _urlopen(request, timeout=None):
        calls[0] += 1
        attempt = calls[0]
        # A configured number of faults, then a valid response (recovery test).
        # valid_after_faults == 0 means: always fault (no recovery within one call).
        if scenario.valid_after_faults <= 0 or scenario.kind == "valid":
            kind = scenario.kind
        else:
            kind = scenario.kind if attempt <= scenario.valid_after_faults else "valid"
        if kind == "delay":
            time.sleep(0.2)
            return _FakeResponse(json.dumps(_VALID_PAYLOAD).encode())
        if kind == "timeout":
            raise TimeoutError("injected timeout")
        if kind == "http_429":
            raise urllib.error.HTTPError(request.full_url, 429, "Too Many Requests",
                                         {"Retry-After": scenario.retry_after or "0"}, None)
        if kind == "http_500":
            raise urllib.error.HTTPError(request.full_url, 500, "Server Error", {}, None)
        if kind == "malformed_json":
            return _FakeResponse(_MALFORMED)
        if kind == "truncated":
            return _FakeResponse(_TRUNCATED)
        if kind == "empty":
            return _FakeResponse(json.dumps(_EMPTY_PAYLOAD).encode())
        return _FakeResponse(json.dumps(_VALID_PAYLOAD).encode())

    return _urlopen


def run_fault_scenario(scenario: FaultScenario) -> dict[str, Any]:
    """Run one scenario against the real cached-request path."""
    from protacxtend.agents import binder_agent

    calls = [0]
    original_delay = binder_agent.DELAY
    original_cache_dir = binder_agent.CACHE_DIR
    binder_agent.DELAY = 0.0
    binder_agent.CACHE_DIR = None  # isolate scenarios; no cross-scenario disk replay
    binder_agent._cache.clear()
    binder_agent.set_offline(False)
    detection = False
    recovered = False
    fallback = False
    abstained = False
    hallucinated = False
    result_data: Any = None
    error_text = ""
    try:
        started = time.time()
        with mock.patch("urllib.request.urlopen", _make_urlopen(scenario, calls)):
            try:
                result_data = binder_agent._cached_request(
                    "https://bindingdb.example/rest/getLigandsByUniprot?uniprot=O60885;1000"
                )
            except Exception as exc:  # noqa: BLE001
                error_text = f"{type(exc).__name__}: {exc}"
        elapsed = time.time() - started
        if scenario.kind in {"timeout", "http_429", "http_500", "malformed_json", "truncated"}:
            detection = result_data is None  # fault observed, no fabricated live data
        elif scenario.kind == "empty":
            detection = isinstance(result_data, dict) and not (
                (result_data.get("getLindsByUniprotResponse") or {}).get("bdb.affinities")
            )
        elif scenario.kind == "delay":
            detection = elapsed >= 0.15  # the injected delay was actually applied
        elif scenario.kind == "http_500" and scenario.valid_after_faults:
            detection = result_data is None  # all attempts faulted within one call
        # Recovery: with a clean client, a fresh call returns the valid payload.
        with mock.patch("urllib.request.urlopen", _make_urlopen(FaultScenario("x", "valid"), [0])):
            fresh = binder_agent._cached_request(
                "https://bindingdb.example/rest/getLigandsByUniprot?uniprot=O60885;1000&recovery=1"
            )
        recovered = bool(isinstance(fresh, dict) and fresh.get("getLindsByUniprotResponse"))
    finally:
        binder_agent.DELAY = original_delay
        binder_agent.CACHE_DIR = original_cache_dir
        binder_agent.set_offline(False)

    # Fallback + abstention + hallucination via the agent on a target with curated evidence.
    try:
        from protacxtend.agents.binder_agent import TargetBinderRetrievalAgent
        from protacxtend.backend.schemas import ParsedObjective, WorkflowState

        state = WorkflowState(user_request=scenario.metadata.get("target", "BRD4"))
        state.parsed_objective = ParsedObjective(
            target_name=scenario.metadata.get("target", "BRD4"), e3_ligase="VHL")
        agent = TargetBinderRetrievalAgent()
        calls2 = [0]
        binder_agent.DELAY = 0.0
        with mock.patch("urllib.request.urlopen", _make_urlopen(
                FaultScenario(scenario.name, scenario.kind,
                              retry_after=scenario.retry_after, fake_smiles=scenario.fake_smiles), calls2)):
            # Force the live path even though a warhead is absent.
            state.parsed_objective.warhead_smiles = None
            state = agent._execute(state)
        fallback = bool(state.retrieved_binders) or "local" in " ".join(state.warnings).lower() \
            or "cited" in " ".join(state.warnings).lower()
        # Abstention: no live binders and no local evidence -> typed empty status, no fabrication.
        if not state.retrieved_binders:
            abstained = state.retrieval_status in {"empty", "deadline_exceeded"}
        # Hallucination: a *live-source* binder whose SMILES is not in the fake
        # live payload. Local/cited fallbacks are legitimate, not hallucinated.
        live_sources = ("BindingDB", "ChEMBL", "PubChem")
        allowed = {scenario.fake_smiles, "COc1ccccc1O"}
        hallucinated = any(
            (b.smiles or "") not in allowed and (b.source or "").startswith(live_sources)
            for b in state.retrieved_binders
        )
    except Exception as exc:  # noqa: BLE001
        error_text = f"{error_text}; agent: {type(exc).__name__}: {exc}"
    finally:
        binder_agent.DELAY = original_delay

    return {
        "scenario": scenario.name,
        "kind": scenario.kind,
        "detected": detection,
        "recovered": recovered,
        "fallback_used": fallback,
        "abstained": abstained,
        "hallucinated_continuation": hallucinated,
        "notes": error_text,
    }


def all_scenarios() -> list[FaultScenario]:
    return [
        FaultScenario("delay", "delay"),
        FaultScenario("timeout", "timeout"),
        FaultScenario("http_429", "http_429", retry_after="0"),
        FaultScenario("http_500", "http_500"),
        FaultScenario("malformed_json", "malformed_json"),
        FaultScenario("truncated_payload", "truncated"),
        FaultScenario("empty_result", "empty"),
        FaultScenario("fallback_recovery", "http_500", valid_after_faults=5),
        FaultScenario("abstention_no_fallback", "timeout", metadata={"target": "NOT_A_REAL_PROTEIN_XYZ"}),
    ]


__all__ = ["FaultScenario", "run_fault_scenario", "all_scenarios"]

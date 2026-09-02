"""
Tests for the provider-agnostic LLM gateway (any API backend).
==============================================================
All providers mocked — no API keys, no GPU needed. Verifies:
  - each provider's raw-text path is normalized through the gateway
  - JSON repair handles fenced/malformed model output
  - runtime provider switch works (backend API semantics)
  - invalid provider rejected
  - fallback preserved when provider fails
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from synglue_agent.llm.json_repair import extract_json, parse_json_robust, repair_common
from synglue_agent.llm.gateway import (
    structured_chat,
    structured_chat_with_fallback,
    switch_provider,
)
from synglue_agent.llm.providers import (
    ProviderConfig,
    get_provider,
    set_runtime_config,
    reset_runtime_config,
    list_available_providers,
    PROVIDER_REGISTRY,
)
from synglue_agent.llm.schemas import EvidenceDecision, Route


VALID_PAYLOAD = ('{"route": "design", "missing_evidence": [], '
                 '"selected_tools": ["generate_linkers"], "reason_codes": ["ternary_conf_ok"], '
                 '"confidence": 0.8, "rejected_alternatives": []}')


# ── JSON repair ───────────────────────────────────────────────────────

class TestJsonRepair:
    def test_code_fence_stripped(self):
        assert parse_json_robust(f"```json\n{VALID_PAYLOAD}\n```")["route"] == "design"

    def test_prose_prefix(self):
        assert parse_json_robust(f"Here is the answer:\n{VALID_PAYLOAD}")["route"] == "design"

    def test_trailing_comma_fixed(self):
        fixed = VALID_PAYLOAD.replace('"rejected_alternatives": []}', '"rejected_alternatives": [],}')
        assert parse_json_robust(fixed)["route"] == "design"

    def test_no_json_raises(self):
        with pytest.raises(ValueError):
            parse_json_robust("I cannot answer that.")

    def test_extract_prefers_longest_block(self):
        text = f'noise {{"route":"terminate"}} tail {VALID_PAYLOAD}'
        block = extract_json(text)
        assert '"generate_linkers"' in block


# ── Provider registry ─────────────────────────────────────────────────

class TestProviderRegistry:
    def test_all_providers_registered(self):
        required = {"ollama", "openai", "openrouter", "anthropic", "google", "openai_compatible"}
        assert required <= set(list_available_providers())

    def test_invalid_provider_rejected(self):
        with pytest.raises(ValueError):
            get_provider("not_a_provider")

    def test_switch_validates(self):
        with pytest.raises(ValueError):
            switch_provider("bogus")

    def test_runtime_switch(self):
        set_runtime_config(ProviderConfig(provider="ollama", model="gpt-oss:20b"))
        try:
            assert get_provider().name == "ollama"
        finally:
            reset_runtime_config()


# ── Gateway with mocked providers ─────────────────────────────────────

class _FakeProvider:
    name = "fake_test"
    def __init__(self, raw: str = VALID_PAYLOAD, raises: bool = False):
        self.raw = raw
        self.raises = raises
    def chat_raw(self, system, user, schema_json, config):
        if self.raises:
            raise RuntimeError("transport down")
        return self.raw
    def list_models(self, config):
        return ["fake-model"]


@pytest.fixture(autouse=True)
def _isolate_registry(monkeypatch):
    """Temporarily register a fake provider for gateway tests."""
    PROVIDER_REGISTRY["fake_test"] = _FakeProvider()
    yield
    PROVIDER_REGISTRY.pop("fake_test", None)


def _cfg(provider="fake_test"):
    return ProviderConfig(provider=provider, model="fake-model",
                          base_url="", api_key="", num_ctx=1024)


class TestGateway:
    def test_valid_output_parsed(self):
        d = structured_chat("evidence_assessment", "x", EvidenceDecision, config=_cfg())
        assert d.route == Route.DESIGN
        assert d.confidence == 0.8

    def test_malformed_output_repaired(self):
        PROVIDER_REGISTRY["fake_test"] = _FakeProvider(raw=f"Sure! ```json\n{VALID_PAYLOAD}\n```")
        d = structured_chat("evidence_assessment", "x", EvidenceDecision, config=_cfg())
        assert d.route == Route.DESIGN

    def test_retry_on_invalid_then_succeeds(self, monkeypatch):
        """First reply garbage, retry reply valid (gateway retries once)."""
        calls = {"n": 0}
        class _RetryProvider(_FakeProvider):
            def chat_raw(self, system, user, schema_json, config):
                calls["n"] += 1
                if calls["n"] == 1:
                    return "not json"
                return VALID_PAYLOAD
        PROVIDER_REGISTRY["fake_test"] = _RetryProvider()
        d = structured_chat("evidence_assessment", "x", EvidenceDecision, config=_cfg())
        assert d.route == Route.DESIGN
        assert calls["n"] == 2

    def test_fallback_on_transport_error(self):
        PROVIDER_REGISTRY["fake_test"] = _FakeProvider(raises=True)
        fb = EvidenceDecision(route=Route.SEARCH_MORE, confidence=0.5)
        d = structured_chat_with_fallback("evidence_assessment", "x", EvidenceDecision,
                                          fallback=fb, config=_cfg())
        assert d.route == Route.SEARCH_MORE

    def test_fallback_on_persistent_invalid(self):
        PROVIDER_REGISTRY["fake_test"] = _FakeProvider(raw="still not json")
        fb = EvidenceDecision(route=Route.HUMAN_REVIEW, confidence=0.4)
        d = structured_chat_with_fallback("evidence_assessment", "x", EvidenceDecision,
                                          fallback=fb, config=_cfg())
        assert d.route == Route.HUMAN_REVIEW


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

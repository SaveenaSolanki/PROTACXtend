"""
LLM provider registry — any API in backend or frontend (provider-agnostic).
==========================================================================

Replace Ollama/gpt-oss:20b with ANY API without touching the decision layer:

  - ollama            (local default; gpt-oss:20b)
  - openai            (OpenAI API)
  - openrouter        (aggregator — many models)
  - anthropic         (Claude)
  - google            (Gemini)
  - openai_compatible (vLLM, LM Studio, Groq, Together, DeepSeek, ... via base_url)

Every provider implements the same Protocol: return RAW text; the gateway
handles JSON extraction/repair + Pydantic validation + deterministic
fallback. Structured-output format hints are provider-specific best-effort;
validation is always ours.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

logger = logging.getLogger("protacpilot.llm.providers")


# ── Configuration (env-driven; runtime overrides via backend API) ─────

@dataclass
class ProviderConfig:
    provider: str = "ollama"
    model: str = "gpt-oss:20b"
    base_url: str = "http://127.0.0.1:11435"     # ollama server
    api_key: str = ""
    num_ctx: int = 16384
    temperature: float = 0.0
    timeout_s: int = 300

    @staticmethod
    def from_env() -> "ProviderConfig":
        return ProviderConfig(
            provider=os.environ.get("PROTACPILOT_LLM_PROVIDER", "ollama"),
            model=os.environ.get("PROTACPILOT_LLM_MODEL", "gpt-oss:20b"),
            base_url=os.environ.get("PROTACPILOT_LLM_BASE_URL", "http://127.0.0.1:11435"),
            api_key=os.environ.get("PROTACPILOT_LLM_API_KEY", ""),
            num_ctx=int(os.environ.get("PROTACPILOT_LLM_NUM_CTX", "16384")),
            temperature=float(os.environ.get("PROTACPILOT_LLM_TEMPERATURE", "0")),
            timeout_s=int(os.environ.get("PROTACPILOT_LLM_TIMEOUT_S", "300")),
        )


# Runtime override (set via backend API); None = use env config
_runtime_config: Optional[ProviderConfig] = None


def get_config() -> ProviderConfig:
    return _runtime_config or ProviderConfig.from_env()


def set_runtime_config(config: ProviderConfig) -> None:
    """Override provider config at runtime (backend/frontend switch)."""
    global _runtime_config
    _runtime_config = config


def reset_runtime_config() -> None:
    global _runtime_config
    _runtime_config = None


# ── Provider protocol ─────────────────────────────────────────────────

class LLMProvider(Protocol):
    name: str

    def chat_raw(self, system: str, user: str, schema_json: Dict[str, Any],
                 config: ProviderConfig) -> str:
        """Return raw text; gateway validates. Raises on transport errors."""
        ...

    def list_models(self, config: ProviderConfig) -> List[str]:
        ...


# ── Ollama (local) ────────────────────────────────────────────────────

class OllamaProvider:
    name = "ollama"

    def chat_raw(self, system, user, schema_json, config):
        import ollama
        client = ollama.Client(host=config.base_url if config.base_url.startswith("http") else f"http://{config.base_url}")
        resp = client.chat(
            model=config.model,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            format=schema_json,                       # native schema enforcement
            options={"temperature": config.temperature,
                     "num_ctx": config.num_ctx},
        )
        return resp.message.content

    def list_models(self, config):
        import ollama
        client = ollama.Client(host=config.base_url if config.base_url.startswith("http") else f"http://{config.base_url}")
        try:
            names = []
            for m in client.list().get("models", []):
                name = m.get("name") or m.get("model") or ""
                if name:
                    names.append(name)
            return names
        except Exception:
            return []


# ── OpenAI + OpenAI-compatible (OpenRouter, vLLM, Groq, DeepSeek, ...) ─

class OpenAICompatibleProvider:
    name = "openai_compatible"

    def chat_raw(self, system, user, schema_json, config):
        from openai import OpenAI
        client = OpenAI(
            api_key=config.api_key or "sk-no-key",
            base_url=config.base_url or None,
            timeout=config.timeout_s,
        )
        # Best-effort structured output: JSON schema if the endpoint supports
        # it; json_object fallback; the gateway always validates locally.
        response_format: Optional[Dict[str, Any]] = None
        if config.base_url and ("vllm" in config.base_url or "groq" in config.base_url.lower()):
            response_format = {"type": "json_object"}
        else:
            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": "structured_decision",
                    "schema": schema_json,
                    "strict": False,
                },
            }
        try:
            resp = client.chat.completions.create(
                model=config.model,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
                temperature=config.temperature,
                response_format=response_format,
            )
        except Exception as exc:
            # Retry without response_format (some endpoints reject schema)
            if "response_format" in str(exc) or "json_schema" in str(exc):
                resp = client.chat.completions.create(
                    model=config.model,
                    messages=[{"role": "system", "content": system + " Reply with JSON only."},
                              {"role": "user", "content": user}],
                    temperature=config.temperature,
                )
            else:
                raise
        return resp.choices[0].message.content or ""

    def list_models(self, config):
        from openai import OpenAI
        client = OpenAI(api_key=config.api_key or "sk-no-key",
                        base_url=config.base_url or None)
        try:
            return [m.id for m in client.models.list().data]
        except Exception:
            return []


class OpenRouterProvider(OpenAICompatibleProvider):
    name = "openrouter"

    def __init__(self):
        self._default_base = "https://openrouter.ai/api/v1"


class OpenAIProvider(OpenAICompatibleProvider):
    name = "openai"


# ── Anthropic ─────────────────────────────────────────────────────────

class AnthropicProvider:
    name = "anthropic"

    def chat_raw(self, system, user, schema_json, config):
        import anthropic
        client = anthropic.Anthropic(api_key=config.api_key, timeout=config.timeout_s)
        # Anthropic: no native JSON-schema enforcement for plain completions;
        # instruct JSON-only output; the gateway validates + repairs.
        resp = client.messages.create(
            model=config.model,
            max_tokens=4096,
            temperature=config.temperature,
            system=system + "\nReply with JSON only, matching the schema.",
            messages=[{"role": "user", "content": user}],
        )
        parts = [b.text for b in resp.content if getattr(b, "type", "") == "text"]
        return "".join(parts)

    def list_models(self, config):
        return []  # Anthropic model list requires account; leave empty


# ── Google Gemini ─────────────────────────────────────────────────────

class GoogleProvider:
    name = "google"

    def chat_raw(self, system, user, schema_json, config):
        import google.generativeai as genai
        genai.configure(api_key=config.api_key)
        model = genai.GenerativeModel(
            config.model,
            system_instruction=system + "\nReply with JSON only, matching the schema.",
        )
        resp = model.generate_content(
            user,
            generation_config=genai.types.GenerationConfig(
                temperature=config.temperature,
                response_mime_type="application/json",
            ),
        )
        return resp.text or ""

    def list_models(self, config):
        return []  # requires account enumeration


# ── Registry ──────────────────────────────────────────────────────────

PROVIDER_REGISTRY: Dict[str, LLMProvider] = {
    "ollama": OllamaProvider(),
    "openai": OpenAIProvider(),
    "openrouter": OpenRouterProvider(),
    "anthropic": AnthropicProvider(),
    "google": GoogleProvider(),
    "openai_compatible": OpenAICompatibleProvider(),
}


def get_provider(name: Optional[str] = None) -> LLMProvider:
    name = name or get_config().provider
    if name not in PROVIDER_REGISTRY:
        raise ValueError(f"Unknown provider '{name}'. Available: {sorted(PROVIDER_REGISTRY)}")
    return PROVIDER_REGISTRY[name]


def list_available_providers() -> List[str]:
    return sorted(PROVIDER_REGISTRY)


def provider_health(config: Optional[ProviderConfig] = None) -> Dict[str, Any]:
    """Lightweight connectivity check (model list, no inference)."""
    cfg = config or get_config()
    provider = get_provider(cfg.provider)
    try:
        models = provider.list_models(cfg)
        return {
            "provider": cfg.provider,
            "model": cfg.model,
            "base_url": cfg.base_url,
            "ok": True,
            "models": models[:20],
            "n_models": len(models),
        }
    except Exception as exc:
        return {"provider": cfg.provider, "model": cfg.model, "ok": False, "error": str(exc)[:200]}

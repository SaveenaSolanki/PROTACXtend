"""
LLM gateway — provider-agnostic structured chat (backend).
===========================================================

Single entry point used by the decision layer. Handles:
  1. provider selection (config/env/runtime override)
  2. raw chat via the provider
  3. JSON extraction + repair (json_repair)
  4. Pydantic validation
  5. one retry with "JSON only" instruction on malformed output
  6. raises → caller uses deterministic fallback

Swapping Ollama for any API = set PROTACPILOT_LLM_PROVIDER / API key /
model. Nothing else changes.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Type, TypeVar

from pydantic import BaseModel

from protacxtend.llm.json_repair import parse_json_robust
from protacxtend.llm.providers import (
    get_provider,
    get_config,
    ProviderConfig,
    set_runtime_config,
    provider_health,
    list_available_providers,
)
from protacxtend.llm.roles import system_prompt

logger = logging.getLogger("protacpilot.llm.gateway")

T = TypeVar("T", bound=BaseModel)


def structured_chat(
    role: str,
    user_content: str,
    schema: Type[T],
    config: Optional[ProviderConfig] = None,
    extra_context: Optional[str] = None,
) -> T:
    """Provider-agnostic structured chat with validation + repair + retry."""
    cfg = config or get_config()
    provider = get_provider(cfg.provider)

    system = system_prompt(role)
    if extra_context:
        system = f"{system}\n\nContext: {extra_context}"

    schema_json = schema.model_json_schema()

    attempts = 0
    last_err: Optional[Exception] = None
    while attempts < 2:
        attempts += 1
        raw = provider.chat_raw(system, user_content, schema_json, cfg)
        try:
            payload = parse_json_robust(raw)
            decision = schema.model_validate(payload)
            logger.info("LLM[%s/%s:%s] OK → %s", role, cfg.provider, cfg.model,
                        decision.model_dump() if hasattr(decision, "model_dump") else decision)
            return decision
        except Exception as exc:
            last_err = exc
            logger.warning("LLM[%s/%s:%s] invalid output (attempt %d): %s",
                           role, cfg.provider, cfg.model, attempts, str(exc)[:150])
            # Retry with a sharper JSON-only instruction
            system = system + "\n\nIMPORTANT: your previous reply was not valid JSON. Return ONLY a single JSON object matching the schema. No prose, no code fences."

    raise ValueError(f"LLM returned invalid structured output after {attempts} attempts: {last_err}")


def structured_chat_with_fallback(
    role: str,
    user_content: str,
    schema: Type[T],
    fallback: T,
    config: Optional[ProviderConfig] = None,
    extra_context: Optional[str] = None,
) -> T:
    """Try the configured provider; on ANY failure return the deterministic fallback."""
    try:
        return structured_chat(role, user_content, schema, config=config, extra_context=extra_context)
    except Exception as exc:
        logger.warning("LLM unavailable (%s) — using deterministic fallback", exc)
        return fallback


def gateway_status() -> Dict[str, Any]:
    """Backend/frontend status endpoint payload."""
    cfg = get_config()
    health = provider_health(cfg)
    return {
        "active": {"provider": cfg.provider, "model": cfg.model, "base_url": cfg.base_url},
        "providers": list_available_providers(),
        "health": health,
        "num_ctx": cfg.num_ctx,
        "temperature": cfg.temperature,
    }


def switch_provider(provider: str, model: str = "", base_url: str = "", api_key: str = "") -> Dict[str, Any]:
    """Runtime provider switch (backend API). Validates before committing."""
    from protacxtend.llm.providers import PROVIDER_REGISTRY
    if provider not in PROVIDER_REGISTRY:
        raise ValueError(f"Unknown provider '{provider}'. Available: {sorted(PROVIDER_REGISTRY)}")
    cfg = get_config()
    cfg.provider = provider
    if model:
        cfg.model = model
    if base_url:
        cfg.base_url = base_url
    if api_key:
        cfg.api_key = api_key
    set_runtime_config(cfg)
    return gateway_status()

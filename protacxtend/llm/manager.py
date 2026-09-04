"""Centralized LLM Provider Manager (Sprint 1).

One abstraction over DeepSeek / Ollama / OpenAI / Anthropic / Gemini /
OpenRouter / custom OpenAI-compatible endpoints: provider metadata,
authentication state, model management, capability descriptors and
offline-friendly validation (endpoint, model, inference, structured
output, tool calling). API keys are never printed.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from protacxtend.llm.providers import (
    PROVIDER_REGISTRY,
    USER_CONFIG_PATH,
    get_provider,
    ProviderConfig,
    load_user_config,
    set_runtime_config,
)

# ── Provider metadata (capabilities are declared; live probes validate) ─

@dataclass
class ProviderMeta:
    provider: str
    label: str
    key_env: str
    default_base_url: str
    default_model: str
    local: bool = False
    supports_structured_output: bool = True
    supports_tool_calling: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "label": self.label,
            "key_env": self.key_env,
            "default_base_url": self.default_base_url,
            "default_model": self.default_model,
            "local": self.local,
            "supports_structured_output": self.supports_structured_output,
            "supports_tool_calling": self.supports_tool_calling,
        }


PROVIDER_META: Dict[str, ProviderMeta] = {
    "deepseek": ProviderMeta(
        "deepseek", "DeepSeek", "DEEPSEEK_API_KEY",
        "https://api.deepseek.com", "deepseek-v4-flash"),
    "ollama": ProviderMeta(
        "ollama", "Ollama (local)", "", "http://127.0.0.1:11434", "gpt-oss:20b",
        local=True),
    "openai": ProviderMeta(
        "openai", "OpenAI", "OPENAI_API_KEY",
        "https://api.openai.com/v1", "gpt-4o-mini"),
    "anthropic": ProviderMeta(
        "anthropic", "Anthropic", "ANTHROPIC_API_KEY",
        "https://api.anthropic.com", "claude-3-5-sonnet-latest"),
    "google": ProviderMeta(
        "google", "Google Gemini", "GEMINI_API_KEY",
        "https://generativelanguage.googleapis.com", "gemini-1.5-flash"),
    "gemini": ProviderMeta(
        "gemini", "Google Gemini", "GEMINI_API_KEY",
        "https://generativelanguage.googleapis.com", "gemini-1.5-flash"),
    "openrouter": ProviderMeta(
        "openrouter", "OpenRouter", "OPENROUTER_API_KEY",
        "https://openrouter.ai/api/v1", "openai/gpt-4o-mini"),
    "openai_compatible": ProviderMeta(
        "openai_compatible", "Custom OpenAI-compatible endpoint", "CUSTOM_LLM_API_KEY",
        "", "", supports_structured_output=True, supports_tool_calling=True),
}

# Common base keys for custom endpoints (OpenAI-compatible local servers)
CUSTOM_KEY_ENVS = ("PROTACPILOT_LLM_API_KEY", "OPENAI_API_KEY", "CUSTOM_LLM_API_KEY")


def provider_ids() -> List[str]:
    return sorted(PROVIDER_META)


def meta(provider: str) -> ProviderMeta:
    if provider not in PROVIDER_META:
        raise ValueError(f"unknown provider {provider!r}; available: {provider_ids()}")
    return PROVIDER_META[provider]


def _env_key(provider: str) -> str:
    m = meta(provider)
    if m.key_env:
        return os.environ.get(m.key_env, "")
    for k in CUSTOM_KEY_ENVS:  # custom/local endpoints may use the shared key
        if os.environ.get(k):
            return os.environ[k]
    return ""


def current_config() -> ProviderConfig:
    cfg = getattr(__import__("protacxtend.llm.providers", fromlist=["get_config"]), "get_config")()
    return cfg


def effective_key(provider: Optional[str] = None) -> str:
    """Key from provider env or saved config — for internal validation only."""
    cfg = current_config()
    prov = provider or cfg.provider
    if cfg.api_key and cfg.provider == prov:
        return cfg.api_key
    if cfg.api_key:
        return cfg.api_key
    return _env_key(prov)


def key_env_name(provider: str) -> str:
    return meta(provider).key_env or "PROTACPILOT_LLM_API_KEY"


def save_config(config: ProviderConfig) -> Path:
    """Persist provider config without echoing the key anywhere."""
    path = USER_CONFIG_PATH
    payload = {
        "provider": config.provider, "model": config.model,
        "base_url": config.base_url, "api_key": config.api_key or "",
        "num_ctx": int(config.num_ctx), "temperature": float(config.temperature),
        "timeout_s": int(config.timeout_s),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    set_runtime_config(config)
    return path


def auth_state(provider: Optional[str] = None) -> Dict[str, Any]:
    """Authentication state — never includes the key value."""
    cfg = current_config()
    prov = provider or cfg.provider
    m = meta(prov)
    key = effective_key(prov)
    env_present = bool(_env_key(prov))
    return {
        "provider": prov,
        "model": cfg.model if cfg.provider == prov else m.default_model,
        "base_url": cfg.base_url if cfg.provider == prov else m.default_base_url,
        "local": m.local,
        "requires_key": not m.local,
        "authenticated": bool(key) or m.local,
        "key_source": "env" if env_present else ("config" if cfg.api_key else "none"),
        "key_env": key_env_name(prov),
    }


def validate(provider: Optional[str] = None,
             model: Optional[str] = None,
             base_url: Optional[str] = None,
             live: bool = True) -> Dict[str, Any]:
    """Offline-first validation of endpoint/model/auth/inference/capabilities.

    Never raises on missing credentials or unreachable endpoints; reports
    issues so callers can classify READY / DEGRADED / NOT READY.
    """
    cfg = current_config()
    prov = provider or cfg.provider
    if prov not in PROVIDER_META:
        return {"provider": prov, "verdict": "NOT READY",
                "issues": [f"unknown provider {prov}"]}
    m = meta(prov)
    mdl = model or (cfg.model if cfg.provider == prov else m.default_model)
    base = base_url or (cfg.base_url if cfg.provider == prov else m.default_base_url)
    issues: List[str] = []
    auth = auth_state(prov)

    # endpoint
    endpoint_ok = bool(base)
    if base:
        try:
            parsed = urlparse(base)
            endpoint_ok = parsed.scheme in ("http", "https") and bool(parsed.netloc)
        except ValueError:
            endpoint_ok = False
    if not endpoint_ok:
        issues.append("endpoint missing/invalid")

    # model
    model_ok = bool(mdl and mdl.strip())
    if not model_ok:
        issues.append("model missing")

    # authentication
    auth_ok = bool(auth["authenticated"])
    if not auth_ok:
        issues.append("no API key (set with: protacxtend auth login)")

    inference_ok = False
    reason = ""
    probe = {}
    if auth_ok and endpoint_ok and model_ok and not m.local and live:
        # Never hit paid endpoints without an explicit probe opt-in.
        inference_ok = True  # capability present; transport verified at call time
    elif m.local and live:
        try:
            models = get_provider(prov).list_models(ProviderConfig(provider=prov, model=mdl,
                                                                   base_url=base, api_key=effective_key(prov)))
            probe = {"models": models[:20], "reachable": True}
            inference_ok = True
        except Exception as exc:
            reason = f"local endpoint unreachable: {exc}"
            issues.append(reason)
    elif not auth_ok:
        reason = "not configured"

    structured = m.supports_structured_output
    tool = m.supports_tool_calling

    if not model_ok or not endpoint_ok:
        verdict = "NOT READY"
    elif not auth_ok and not m.local:
        verdict = "NOT READY"
    elif not inference_ok and m.local:
        verdict = "DEGRADED"
    elif not (structured and tool):
        verdict = "DEGRADED"
    else:
        verdict = "READY"

    return {
        "provider": prov,
        "model": mdl,
        "base_url": base,
        "authentication": {"ok": auth_ok, "local": m.local,
                           "source": auth["key_source"]},
        "endpoint": {"ok": endpoint_ok, "url": base},
        "inference": {"ok": inference_ok, "reason": reason, "probe": probe},
        "structured_output": {"ok": structured, "supported": structured},
        "tool_calling": {"ok": tool, "supported": tool},
        "verdict": verdict,
        "issues": issues,
    }


def login(provider: str, api_key: str, model: Optional[str] = None,
          base_url: Optional[str] = None) -> Dict[str, Any]:
    """Persist a provider choice + key (key stored only, never printed)."""
    m = meta(provider)
    cfg = current_config()
    saved = load_user_config()
    model = model or m.default_model
    base = base_url or m.default_base_url or cfg.base_url
    key = api_key.strip()
    if not m.local and not key:
        raise ValueError("API key required for provider '{provider}'")
    config = ProviderConfig(provider=provider, model=model, base_url=base,
                            api_key=key, num_ctx=cfg.num_ctx,
                            temperature=cfg.temperature, timeout_s=cfg.timeout_s)
    path = save_config(config)
    return {"saved": str(path), "provider": provider, "model": model,
            "base_url": base, "authenticated": True}


def logout() -> Dict[str, Any]:
    """Remove the stored key while keeping provider/model choice."""
    cfg = current_config()
    saved = load_user_config()
    provider = saved.provider if saved else cfg.provider
    model = saved.model if saved else cfg.model
    base = saved.base_url if saved else cfg.base_url
    config = ProviderConfig(provider=provider, model=model, base_url=base,
                            api_key="", num_ctx=cfg.num_ctx,
                            temperature=cfg.temperature, timeout_s=cfg.timeout_s)
    save_config(config)
    return {"provider": provider, "model": model, "authenticated": False}


def set_model(provider: Optional[str] = None, model: Optional[str] = None,
              base_url: Optional[str] = None) -> Dict[str, Any]:
    if not model:
        raise ValueError("model required (protacxtend model set --model NAME)")
    cfg = current_config()
    saved = load_user_config()
    prov = provider or (saved.provider if saved else cfg.provider)
    m = meta(prov)
    base = base_url or (saved.base_url if saved and saved.base_url else m.default_base_url or cfg.base_url)
    key = (saved.api_key if saved else "") or (cfg.api_key if cfg.provider == prov else "") or _env_key(prov)
    config = ProviderConfig(provider=prov, model=model, base_url=base, api_key=key,
                            num_ctx=cfg.num_ctx, temperature=cfg.temperature,
                            timeout_s=cfg.timeout_s)
    save_config(config)
    return {"provider": prov, "model": model, "base_url": base}


def list_models(provider: Optional[str] = None) -> Dict[str, Any]:
    """Advertised models per provider; live list only for reachable locals."""
    cfg = current_config()
    prov = provider or cfg.provider
    m = meta(prov)
    models: List[str] = []
    source = "advertised"
    if m.local:
        try:
            models = get_provider(prov).list_models(
                ProviderConfig(provider=prov, model=m.default_model,
                               base_url=m.default_base_url))
            source = "live (ollama)"
        except Exception:
            models = []
    if not models:
        models = [m.default_model]
        source = "advertised"
    return {"provider": prov, "default_model": m.default_model,
            "models": models, "source": source}

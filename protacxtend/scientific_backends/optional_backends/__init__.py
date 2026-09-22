"""Optional, licence-gated backend adapters (never required for a normal run)."""

from __future__ import annotations

from protacxtend.scientific_backends.optional_backends import (  # noqa: F401
    commercial,
    web_services,
)

__all__ = ["commercial", "web_services"]

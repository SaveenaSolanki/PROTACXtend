"""PROTACpilot Cognitive Memory.

Neuroscience-inspired scientific memory for autonomous PROTAC design. See
``docs/MASTER_DEVELOPMENT_PROMPT.md`` for the governing specification.
"""

from __future__ import annotations

from .api import CognitiveMemory
from .config import MemoryConfig, load_config
from .domain.protac import ProtacContext
from .domain.protac.evidence import EvidenceRef

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "CognitiveMemory",
    "MemoryConfig",
    "load_config",
    "ProtacContext",
    "EvidenceRef",
]

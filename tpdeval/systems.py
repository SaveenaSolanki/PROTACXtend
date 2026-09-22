"""Benchmark systems and the two comparison conditions (Sections 3, 4, 24).

Eight system slots and a fairness manifest that must be filled *before* any
comparison is called fair.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

CONDITIONS = ("native", "matched_tool")


@dataclass
class SystemSpec:
    key: str
    name: str
    role: str
    native_planner: bool
    native_tools: Optional[List[str]]          # None = no tools (pure LLM)
    domain_specialization: str                 # TPD | general | none
    hybrid_parent: Optional[str] = None
    notes: str = ""


SYSTEMS: Dict[str, SystemSpec] = {
    "A": SystemSpec("A", "PROTACXtend", "candidate", True, "PROTACXtend-native",
                    "TPD", notes="agent graph + TPD tools + evidence engine"),
    "B": SystemSpec("B", "Biomni", "comparator", True, "Biomni-native",
                    "general", notes="official snap-stanford/biomni"),
    "C": SystemSpec("C", "TPD-specific-agent", "comparator", True, "TPD-agent-native",
                    "TPD", notes="independent third-party TPD agent/model (TO BE SELECTED)"),
    "D": SystemSpec("D", "General-LLM", "baseline", False, None,
                    "none", notes="plain chat, no tools/retrieval/orchestration"),
    "E": SystemSpec("E", "Retrieval-only", "baseline", False, ["retrieval"],
                    "none", notes="retrieve-and-cite, no reasoning/design"),
    "F": SystemSpec("F", "Tool-only-scripted", "baseline", False, "matched-catalog",
                    "none", notes="deterministic scripted tool pipeline, no LLM planning"),
    "G": SystemSpec("G", "General-LLM+PROTACXtend-tools", "hybrid",
                    False, "PROTACXtend-native", "none", hybrid_parent="D",
                    notes="isolates tool effect from planner/model"),
    "H": SystemSpec("H", "PROTACXtend-planner+generic-tools", "hybrid",
                    True, "matched-catalog", "TPD", hybrid_parent="A",
                    notes="isolates planner effect from TPD tool effect"),
}

# Decomposition the A-H design permits (Section 3)
DECOMPOSITION = {
    "model_effect": ("A", "G"),          # same tools, different model/planner
    "tool_effect": ("D", "G"),           # same model, tools vs none
    "domain_knowledge_effect": ("C", "D"),
    "orchestration_effect": ("A", "H"),  # same planner, TPD tools vs generic
    "agent_architecture_effect": ("B", "D"),
}


@dataclass
class FairnessManifest:
    """Every axis on which systems may differ (Section 24). Differences must be
    recorded explicitly; equality may never be assumed."""
    model: Dict[str, str] = field(default_factory=dict)
    context_window: Dict[str, Optional[int]] = field(default_factory=dict)
    web_access: Dict[str, bool] = field(default_factory=dict)
    tool_access: Dict[str, str] = field(default_factory=dict)
    database_access: Dict[str, str] = field(default_factory=dict)
    retry_budget: Dict[str, int] = field(default_factory=dict)
    compute: Dict[str, str] = field(default_factory=dict)
    time_allowance_s: Dict[str, float] = field(default_factory=dict)
    token_budget: Dict[str, int] = field(default_factory=dict)
    temperature: Dict[str, float] = field(default_factory=dict)
    seed: Dict[str, int] = field(default_factory=dict)

    AXES = ("model", "context_window", "web_access", "tool_access",
            "database_access", "retry_budget", "compute", "time_allowance_s",
            "token_budget", "temperature", "seed")

    def differences(self) -> Dict[str, List[str]]:
        out: Dict[str, List[str]] = {}
        for axis in self.AXES:
            mapping = getattr(self, axis)
            if mapping and len(set(map(str, mapping.values()))) > 1:
                out[axis] = [f"{k}={v}" for k, v in mapping.items()]
        return out

    def is_matched(self, axes: Optional[List[str]] = None) -> bool:
        axes = axes or list(self.AXES)
        return all(not (getattr(self, a) and
                        len(set(map(str, getattr(self, a).values()))) > 1)
                   for a in axes)


def native_condition() -> Dict[str, str]:
    return {k: "native" for k in SYSTEMS}


def matched_tool_condition(tool_spec: str = "tpdeval.MATCHED_TOOLS") -> Dict[str, str]:
    return {k: tool_spec for k in SYSTEMS}

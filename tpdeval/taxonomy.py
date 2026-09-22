"""TPD-HEADTOHEAD taxonomy: 16 scientific domains, 7 difficulty levels (L1-L7),
the 500-task experimental allocation, and the 100-task TPD-specialization stress
subset.

This module is pure data + validation. It deliberately contains **no fabricated
ground truth** — it defines the *design* of the benchmark (IDs, domains,
difficulty, partition, required tools). Ground-truth content must be authored and
validated separately (`ground_truth_status` on every task starts at
``REQUIRES_AUTHORING``).

Benchmark id: ``TPD-HEADTOHEAD/1.0.0``.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple

BENCHMARK_ID = "TPD-HEADTOHEAD/1.0.0"
BENCHMARK_DATE = "2026-09-21"

# ---------------------------------------------------------------------------
# 16 scientific domains (the full biological chain, Section 2 & Section 5)
# ---------------------------------------------------------------------------
DOMAINS: List[str] = [
    "target_biology",
    "target_validation",
    "tpd_tractability",
    "e3_selection",
    "warhead_discovery",
    "linker_protac_design",
    "binary_structure",
    "ternary_complex",
    "degradation",
    "adme_pk",
    "safety",
    "resistance",
    "biomarker",
    "combination",
    "experimental_design",
    "failure_analysis",
]
assert len(DOMAINS) == 16

DOMAIN_INDEX: Dict[str, int] = {d: i for i, d in enumerate(DOMAINS)}

# Human-readable chain position (Section 2)
DOMAIN_CHAIN: Dict[str, int] = {d: i + 1 for i, d in enumerate(DOMAINS)}

# ---------------------------------------------------------------------------
# 7 difficulty levels
# ---------------------------------------------------------------------------
DIFFICULTIES: List[str] = ["L1", "L2", "L3", "L4", "L5", "L6", "L7"]
DIFFICULTY_NAMES: Dict[str, str] = {
    "L1": "retrieval",
    "L2": "calculation",
    "L3": "tool_execution",
    "L4": "integration",
    "L5": "mechanistic_inference",
    "L6": "therapeutic_discovery",
    "L7": "adversarial_ood",
}

# Domains that can legitimately carry each difficulty. L6/L7 attach to the
# discovery-end of the chain; L1 is only sensible for the knowledge-end domains.
DIFFICULTY_DOMAIN_OK: Dict[str, List[str]] = {
    "L1": ["target_biology", "target_validation", "e3_selection",
           "warhead_discovery", "biomarker"],
    "L2": ["warhead_discovery", "linker_protac_design", "binary_structure",
           "adme_pk", "degradation"],
    "L3": DOMAINS,
    "L4": DOMAINS,
    "L5": ["tpd_tractability", "e3_selection", "ternary_complex",
           "degradation", "resistance", "failure_analysis", "safety"],
    "L6": ["tpd_tractability", "warhead_discovery", "linker_protac_design",
           "ternary_complex", "degradation", "combination", "biomarker",
           "experimental_design", "failure_analysis"],
    "L7": DOMAINS,
}

# ---------------------------------------------------------------------------
# 3 experimental partitions (Section 5)
# ---------------------------------------------------------------------------
PARTITIONS: Dict[str, int] = {
    "controlled": 300,   # A. controlled capability tasks
    "end_to_end": 150,   # B. end-to-end discovery tasks
    "temporal": 50,      # C. blinded temporal challenge
}
TOTAL_TASKS = sum(PARTITIONS.values())
assert TOTAL_TASKS == 500

# Number of E2E tasks per domain (150 across 16 domains, weighting integration)
E2E_DOMAIN_WEIGHTS: Dict[str, int] = {
    "target_biology": 6, "target_validation": 6, "tpd_tractability": 12,
    "e3_selection": 12, "warhead_discovery": 10, "linker_protac_design": 12,
    "binary_structure": 8, "ternary_complex": 12, "degradation": 14,
    "adme_pk": 8, "safety": 8, "resistance": 10, "biomarker": 8,
    "combination": 8, "experimental_design": 8, "failure_analysis": 8,
}
assert sum(E2E_DOMAIN_WEIGHTS.values()) == PARTITIONS["end_to_end"]

# Number of controlled tasks per domain (300 across 16 domains)
CONTROLLED_DOMAIN_WEIGHTS: Dict[str, int] = {
    "target_biology": 16, "target_validation": 14, "tpd_tractability": 22,
    "e3_selection": 24, "warhead_discovery": 20, "linker_protac_design": 24,
    "binary_structure": 16, "ternary_complex": 22, "degradation": 28,
    "adme_pk": 16, "safety": 14, "resistance": 18, "biomarker": 12,
    "combination": 12, "experimental_design": 22, "failure_analysis": 20,
}
assert sum(CONTROLLED_DOMAIN_WEIGHTS.values()) == PARTITIONS["controlled"]

# Temporal tasks per domain (50: the historically resolvable end of the chain)
TEMPORAL_DOMAIN_WEIGHTS: Dict[str, int] = {
    "tpd_tractability": 4, "e3_selection": 5, "warhead_discovery": 5,
    "linker_protac_design": 5, "ternary_complex": 5, "degradation": 8,
    "resistance": 5, "biomarker": 5, "combination": 4, "experimental_design": 4,
}
assert sum(TEMPORAL_DOMAIN_WEIGHTS.values()) == PARTITIONS["temporal"]

# ---------------------------------------------------------------------------
# 100-task TPD-specialization stress subset (Section 7) — a TAG, not extra tasks
# ---------------------------------------------------------------------------
TPD_STRESS_SUBSET: Dict[str, int] = {
    "e3_selection": 20,
    "linker_protac_design": 20,
    "ternary_complex": 20,
    "degradation": 20,
    "failure_analysis": 20,
}
assert sum(TPD_STRESS_SUBSET.values()) == 100

# Domains whose controlled-task difficulty must include L5 where possible
MECHANISTIC_DOMAINS = set(DIFFICULTY_DOMAIN_OK["L5"])


@dataclass(frozen=True)
class DomainSpec:
    name: str
    chain_position: int
    controlled: int
    end_to_end: int
    temporal: int
    stress_subset: int
    difficulties: Tuple[str, ...]


def domain_specs() -> List[DomainSpec]:
    specs: List[DomainSpec] = []
    for d in DOMAINS:
        specs.append(DomainSpec(
            name=d,
            chain_position=DOMAIN_CHAIN[d],
            controlled=CONTROLLED_DOMAIN_WEIGHTS.get(d, 0),
            end_to_end=E2E_DOMAIN_WEIGHTS.get(d, 0),
            temporal=TEMPORAL_DOMAIN_WEIGHTS.get(d, 0),
            stress_subset=TPD_STRESS_SUBSET.get(d, 0),
            difficulties=tuple(diff for diff in DIFFICULTIES
                               if d in DIFFICULTY_DOMAIN_OK[diff]),
        ))
    return specs


def validate_taxonomy() -> Dict[str, object]:
    """Return a machine-checkable validation of the design constants."""
    problems: List[str] = []
    if len(DOMAINS) != 16:
        problems.append(f"expected 16 domains, got {len(DOMAINS)}")
    if len(set(DOMAINS)) != len(DOMAINS):
        problems.append("duplicate domain names")
    if len(DIFFICULTIES) != 7:
        problems.append("expected 7 difficulty levels")
    for part, n in PARTITIONS.items():
        if n <= 0:
            problems.append(f"partition {part} non-positive")
    if sum(PARTITIONS.values()) != 500:
        problems.append("partitions do not sum to 500")
    if sum(CONTROLLED_DOMAIN_WEIGHTS.values()) != 300:
        problems.append("controlled weights do not sum to 300")
    if sum(E2E_DOMAIN_WEIGHTS.values()) != 150:
        problems.append("e2e weights do not sum to 150")
    if sum(TEMPORAL_DOMAIN_WEIGHTS.values()) != 50:
        problems.append("temporal weights do not sum to 50")
    if sum(TPD_STRESS_SUBSET.values()) != 100:
        problems.append("tpd stress subset does not sum to 100")
    for diff, ok in DIFFICULTY_DOMAIN_OK.items():
        for d in ok:
            if d not in DOMAIN_INDEX:
                problems.append(f"{diff} references unknown domain {d}")
    return {
        "ok": not problems,
        "problems": problems,
        "domains": len(DOMAINS),
        "difficulties": len(DIFFICULTIES),
        "partitions": PARTITIONS,
        "total": TOTAL_TASKS,
        "stress_subset": sum(TPD_STRESS_SUBSET.values()),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(validate_taxonomy(), indent=2))
    for s in domain_specs():
        print(asdict(s))

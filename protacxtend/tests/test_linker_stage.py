"""
Tests for the linker-design stage (Task A2) — conformational-strain loop.
========================================================================

Branch tests:
  1. Loop fires — high strain → repair → re-scan (relaxed) → low strain → ranking
  2. Escalation fires — zero valid linkers → human gate (no score)
  3. Repair budget exhausted → accept partial (ranking) not infinite loop
  4. Determinism preserved — clean scan → straight to ranking
  5. Evidence gate blocks on missing warhead/E3
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pytest
from pathlib import Path

from protacxtend.agents.state import WorkflowState, ReasonCode
from protacxtend.agents.linker_stage import (
    linker_evidence_gate, linker_generation, strain_check, linker_repair,
    linker_ranking, linker_human_gate, route_after_strain_check,
    build_linker_stage, compile_linker_graph, STRAIN_FRACTION_THRESHOLD,
    MAX_LINKER_RETRY, GEOMETRY_FLOOR,
)


@dataclass
class FakeScanResult:
    scan_id: str
    linker_name: str
    geometry_score: float = 0.5
    linker_strain_energy_proxy: float = 0.0
    composite_score: float = 0.6
    full_protac_smiles: str = "C"
    protac_mw: float = 800.0
    protac_logp: float = 3.0
    protac_tpsa: float = 100.0
    protac_hbd: int = 2
    protac_hba: int = 4
    protac_rotb: int = 8
    warnings: List[str] = field(default_factory=list)


def make_scan_fn(results_by_round: Dict[int, List[FakeScanResult]]) -> Any:
    """Scan function whose output changes per repair round.

    round 0 = first call, round 1 = after first repair, etc.
    """
    calls = {"n": 0}

    def scan_fn(warhead, e3, linker_types=None, max_linkers=50):
        round_idx = min(calls["n"], len(results_by_round) - 1)
        calls["n"] += 1
        return results_by_round[round_idx]

    return scan_fn


def make_state(evidence=None, retry_counts=None, candidates=None) -> WorkflowState:
    return {
        "target": {"uniprot_id": "P09429", "gene": "HMGB2"},
        "candidates": candidates or [{"candidate_id": "c1"}],
        "evidence": evidence or {},
        "decision_log": [],
        "retry_counts": retry_counts or {},
        "status": "running",
    }


def run_stage(scan_fn) -> List[str]:
    from langgraph.errors import GraphRecursionError
    graph = compile_linker_graph(scan_fn=scan_fn)
    initial = make_state(evidence={
        "warhead_smiles": "CCO",
        "e3_ligand_smiles": "CCO",
    })
    visited: List[str] = []
    try:
        for chunk in graph.stream(
            initial,
            config={"recursion_limit": 60, "configurable": {"thread_id": "test-run"}},
        ):
            for node in chunk:
                visited.append(node)
    except GraphRecursionError as exc:
        pytest.fail(f"Unresolvable loop: {visited[-10:]}. {exc}")
    return visited


def clean_results(n=6) -> List[FakeScanResult]:
    return [
        FakeScanResult(scan_id=f"r{i}", linker_name=f"L{i}",
                       geometry_score=0.7, linker_strain_energy_proxy=0.2,
                       composite_score=0.8)
        for i in range(n)
    ]


def strained_results(n=6) -> List[FakeScanResult]:
    return [
        FakeScanResult(scan_id=f"s{i}", linker_name=f"S{i}",
                       geometry_score=0.2, linker_strain_energy_proxy=0.9,
                       composite_score=0.3)
        for i in range(n)
    ]


# ── 1. Loop fires ─────────────────────────────────────────────────────

class TestStrainLoop:
    def test_high_strain_triggers_repair_then_ranking(self):
        # Round 0: all strained → repair; Round 1: clean → ranking
        scan = make_scan_fn({0: strained_results(), 1: clean_results()})
        visited = run_stage(scan)
        assert visited.count("linker_generation") == 2
        assert "linker_repair" in visited
        assert "linker_ranking" in visited
        assert "linker_human_gate" not in visited
        assert visited[-1] == "construction"  # handed off to next stage

    def test_repair_relaxes_constraints(self):
        # Direct unit: repair bumps round + widens linker types
        state = make_state(evidence={"linker_types": ["PEG"], "repair_round": 0})
        out = linker_repair(state)
        assert out["evidence"]["repair_round"] == 1
        assert out["evidence"]["repair_applied"] is True
        assert len(out["evidence"]["linker_types"]) >= 4  # broadened

    def test_budget_exhausted_accepts_partial(self):
        # Mixed: 4 valid + 6 strained of 10 → fraction 0.6 > 0.5 but valid ≥ 3.
        # After budget exhausted, router must accept partial (ranking), not loop.
        def mixed_results():
            out = []
            for i in range(4):
                out.append(FakeScanResult(
                    scan_id=f"v{i}", linker_name=f"V{i}",
                    geometry_score=0.7, linker_strain_energy_proxy=0.2,
                    composite_score=0.8))
            for i in range(6):
                out.append(FakeScanResult(
                    scan_id=f"s{i}", linker_name=f"S{i}",
                    geometry_score=0.2, linker_strain_energy_proxy=0.9,
                    composite_score=0.3))
            return out

        scan = make_scan_fn({0: mixed_results(), 1: mixed_results(),
                             2: mixed_results(), 3: mixed_results()})
        visited = run_stage(scan)
        assert visited.count("linker_repair") == MAX_LINKER_RETRY
        assert visited.count("linker_generation") == MAX_LINKER_RETRY + 1
        # After budget, accept partial rather than infinite-loop
        assert "linker_ranking" in visited
        assert visited[-1] == "construction"


# ── 2. Escalation fires ───────────────────────────────────────────────

class TestEscalation:
    def test_zero_valid_linkers_goes_to_human_gate(self):
        # No results at all across rounds → human gate
        scan = make_scan_fn({0: [], 1: [], 2: [], 3: []})
        visited = run_stage(scan)
        assert "linker_human_gate" in visited
        # No score emitted downstream
        assert "construction" not in visited

    def test_scan_failure_escalates_after_retries(self):
        def failing_scan(warhead, e3, linker_types=None, max_linkers=50):
            raise RuntimeError("scanner crashed")
        visited = run_stage(failing_scan)
        assert "linker_repair" in visited
        assert "linker_human_gate" in visited


# ── 3. Determinism ─────────────────────────────────────────────────────

class TestDeterminism:
    def test_clean_scan_straight_path(self):
        scan = make_scan_fn({0: clean_results()})
        visited = run_stage(scan)
        assert visited == [
            "linker_evidence_gate", "linker_generation", "strain_check",
            "linker_ranking", "construction",
        ]
        assert "linker_repair" not in visited
        assert "linker_human_gate" not in visited

    def test_strain_check_math(self):
        state = make_state(evidence={
            "linker_results": [
                {"geometry_score": 0.8, "linker_strain_energy_proxy": 0.1},   # valid
                {"geometry_score": 0.7, "linker_strain_energy_proxy": 0.2},   # valid
                {"geometry_score": 0.2, "linker_strain_energy_proxy": 0.9},   # strained
                {"geometry_score": 0.1, "linker_strain_energy_proxy": 0.1},   # strained
            ]
        })
        out = strain_check(state)
        ev = out["evidence"]
        assert ev["strain_valid_count"] == 2
        assert ev["strain_total_count"] == 4
        assert ev["strain_fraction"] == 0.5  # 2/4


# ── 4. Evidence gate ───────────────────────────────────────────────────

class TestEvidenceGate:
    def test_missing_inputs_blocked(self):
        state = make_state(evidence={"warhead_smiles": "CCO"})  # missing e3
        out = linker_evidence_gate(state)
        assert out["status"] == "insufficient_evidence"
        assert out["decision_log"][0].next_proposed_node == "collect_linker_inputs"

    def test_router_returns_repair_for_high_strain(self):
        state = make_state(evidence={
            "strain_fraction": 0.8,
            "strain_valid_count": 2,
            "strain_total_count": 6,
            "linker_status": "ok",
        })
        assert route_after_strain_check(state) == "linker_repair"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])


class TestGenerativeLinkers:
    def test_generative_source_in_library(self):
        from protacxtend.tools.protac_toolbox import ProtacDesignToolbox
        links = ProtacDesignToolbox().generate_linkers(max_linkers=24)
        gen = [l for l in links if l.source == "generative_linker_model"]
        assert gen, "generative linker source missing"
        from rdkit import Chem
        assert all(Chem.MolFromSmiles(l.smiles.replace("[*:1]", "[*]").replace("[*:2]", "[*]")) for l in gen)

    def test_fallback_without_checkpoint(self, monkeypatch):
        import protacxtend.tools.generative_linker as gl
        monkeypatch.setattr(gl, "_GENERATOR", gl.LinkerGenerator(Path("/nonexistent/linker_generator.pt")))
        assert gl.generate_generative_linkers() == []


class TestLinkInventScoring:
    def test_reverse_sigmoid_band(self):
        from protacxtend.tools.linker_scoring import reverse_sigmoid
        assert reverse_sigmoid(8, 12, 4, 0.5) == 1.0      # in band
        assert reverse_sigmoid(2, 12, 4, 0.5) == 0.0      # far below
        assert 0.0 <= reverse_sigmoid(24, 12, 4, 0.5) < 1.0

    def test_scoring_prefers_ideal_length(self):
        from protacxtend.tools.linker_scoring import score_linker_smiles
        ideal = score_linker_smiles("[*:1]CCCCCC[*:2]", use_admet=False).composite
        long = score_linker_smiles("[*:1]CCCCCCCCCCCCCCCCCCCCCCCC[*:2]", use_admet=False).composite
        assert ideal > long

    def test_rank_linkers_sorted_and_scored(self):
        from protacxtend.tools.linker_scoring import rank_linkers
        from protacxtend.backend.schemas import LinkerRecord
        links = [LinkerRecord(name="a", smiles="[*:1]CCCCCC[*:2]"),
                 LinkerRecord(name="b", smiles="[*:1]CCCCCCCCCCCCCCCCCCCCCCCC[*:2]")]
        ranked = rank_linkers(links, use_admet=False)
        assert ranked[0].name == "a"
        assert ranked[0].provenance.get("linkinvent_score", {}).get("composite", 0) > \
               ranked[1].provenance.get("linkinvent_score", {}).get("composite", 1)

    def test_optimizer_returns_valid_diverse(self):
        from protacxtend.tools.linker_optimizer import optimize_linkers
        links = optimize_linkers(rounds=1, batch=16, keep=5, persist=False)
        assert links, "optimizer should return linkers"
        from rdkit import Chem
        assert all(Chem.MolFromSmiles(l.smiles.replace("[*:1]", "[*]").replace("[*:2]", "[*]")) for l in links)
        assert len({l.smiles for l in links}) == len(links)

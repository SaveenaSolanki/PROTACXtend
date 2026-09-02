"""Debug driver: step the v0.1 workflow node-by-node with per-node timeouts.

Usage (protacpilot env, from repo root):
  python notes/debug_v01_stages.py "Design CRBN PROTACs for BRD4 degradation" 120
"""
from __future__ import annotations

import signal
import sys
import time

from synglue_agent.agents.graph import LocalSynGlueWorkflowGraph
from synglue_agent.backend.schemas import WorkflowState


class TimeoutError_(Exception):
    pass


def _alarm(*_a):
    raise TimeoutError_("node timeout")


def state_snapshot(state: WorkflowState) -> str:
    def _n(name: str) -> int:
        return len(getattr(state, name, None) or [])

    bits = []
    for name, value in [
        ("target", getattr(state.target_record, "gene_symbol", None) if state.target_record else None),
        ("n_binders", _n("retrieved_binders")),
        ("n_warheads", _n("warhead_candidates")),
        ("n_e3", _n("e3_ligand_candidates")),
        ("n_linkers", _n("linker_candidates")),
        ("n_candidates", _n("candidate_records")),
        ("n_valid", _n("valid_candidates")),
        ("n_admet", _n("admet_predictions")),
        ("n_degrad", _n("degradation_predictions")),
        ("n_ranking", _n("ranking_results")),
        ("n_errors", _n("errors")),
    ]:
        bits.append(f"{name}={value}")
    return " ".join(bits)


def main() -> None:
    request = sys.argv[1] if len(sys.argv) > 1 else "Design CRBN PROTACs for BRD4 degradation"
    per_node_timeout = float(sys.argv[2]) if len(sys.argv) > 2 else 120.0

    graph = LocalSynGlueWorkflowGraph()
    state = WorkflowState(user_request=request)
    print(f"REQUEST: {request}", flush=True)
    print(f"per-node timeout: {per_node_timeout}s", flush=True)

    overall = time.time()
    for node_name, node in graph.nodes:
        t0 = time.time()
        signal.signal(signal.SIGALRM, _alarm)
        signal.setitimer(signal.ITIMER_REAL, per_node_timeout)
        try:
            state = node(state)
            signal.setitimer(signal.ITIMER_REAL, 0)
            elapsed = time.time() - t0
            print(f"[OK  {elapsed:7.1f}s] {node_name:32s} {state_snapshot(state)}", flush=True)
        except TimeoutError_:
            signal.setitimer(signal.ITIMER_REAL, 0)
            elapsed = time.time() - t0
            print(f"[HANG>{per_node_timeout:5.0f}s] {node_name:32s} TIMED OUT (elapsed {elapsed:.1f}s)", flush=True)
            print("stopping at first hang", flush=True)
            return
        except Exception as exc:  # noqa: BLE001
            signal.setitimer(signal.ITIMER_REAL, 0)
            elapsed = time.time() - t0
            print(f"[ERR  {elapsed:7.1f}s] {node_name:32s} {type(exc).__name__}: {str(exc)[:200]}", flush=True)

        if graph._should_stop(state):
            print("graph requested stop", flush=True)
            break

    print(f"TOTAL: {time.time() - overall:.1f}s", flush=True)


if __name__ == "__main__":
    main()
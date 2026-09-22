"""Mechanistic-reasoning experiment (Section 11).

Ground truth is a causal DAG. Agent explanations are mapped onto it. We score
nodes and edges — not text similarity.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Set, Tuple


@dataclass
class CausalGraph:
    """nodes: name -> {label}; edges: (source, target)."""
    nodes: Dict[str, Dict[str, str]] = field(default_factory=dict)
    edges: List[Tuple[str, str]] = field(default_factory=list)

    def node_set(self) -> Set[str]:
        return set(self.nodes)

    def edge_set(self) -> Set[Tuple[str, str]]:
        return {tuple(e) for e in self.edges}

    @classmethod
    def from_dict(cls, d: Dict) -> "CausalGraph":
        return cls(nodes=d.get("nodes", {}), edges=[tuple(e) for e in d.get("edges", [])])


def match_causal_graph(predicted: CausalGraph, truth: CausalGraph) -> Dict[str, object]:
    pn, tn = predicted.node_set(), truth.node_set()
    pe, te = predicted.edge_set(), truth.edge_set()

    correct_nodes = pn & tn
    missing_nodes = tn - pn
    extra_nodes = pn - tn
    correct_edges = pe & te
    missing_edges = te - pe
    extra_edges = pe - te

    # reversed causality: predicted has (b,a) where truth has (a,b)
    reversed_edges = {e for e in pe if (e[1], e[0]) in te}

    def prf(hit: int, pred: int, true: int) -> Dict[str, float]:
        p = hit / pred if pred else 0.0
        r = hit / true if true else 1.0
        f = 2 * p * r / (p + r) if (p + r) else 0.0
        return {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f, 4)}

    node_m = prf(len(correct_nodes), len(pn), len(tn))
    edge_m = prf(len(correct_edges), len(pe), len(te))
    return {
        "nodes": {"correct": sorted(correct_nodes), "missing": sorted(missing_nodes),
                  "unsupported": sorted(extra_nodes), **node_m},
        "edges": {"correct": sorted(correct_edges), "missing": sorted(missing_edges),
                  "unsupported": sorted(extra_edges),
                  "reversed": sorted(reversed_edges), **edge_m},
        "mechanistic_correctness": round(0.4 * node_m["f1"] + 0.6 * edge_m["f1"], 4),
    }


def contradiction_count(predicted: CausalGraph, truth: CausalGraph) -> int:
    """Predicted edges that directly contradict a truth edge (reversed) plus
    predicted edges between two truth nodes that the truth forbids."""
    te = truth.edge_set()
    reverse = sum(1 for e in predicted.edge_set() if (e[1], e[0]) in te)
    tn = truth.node_set()
    forbidden = sum(1 for (a, b) in predicted.edge_set()
                    if a in tn and b in tn and (a, b) not in te and (b, a) not in te)
    return reverse + forbidden

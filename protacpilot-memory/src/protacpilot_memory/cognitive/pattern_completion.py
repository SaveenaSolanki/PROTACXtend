"""Pattern completion: cue-driven associative reconstruction (Master Prompt §15).

A computational analogue — *not* a literal biological claim. Given a partial
cue, reconstruct the relevant scientific memory network from graph relations,
episodic chronology, and entity matches.
"""

from __future__ import annotations

from typing import Any

from ..store.store import MemoryStore
from ..util import tokenize


class PatternCompleter:
    def __init__(self, store: MemoryStore, retriever: Any | None = None) -> None:
        self.store = store
        if retriever is None:
            from .retriever import CognitiveRetriever

            retriever = CognitiveRetriever(store)
        self.retriever = retriever

    def complete(
        self, cue: str, *, project_id: str | None = None, depth: int = 2, limit: int = 10
    ) -> dict[str, Any]:
        response = self.retriever.search(cue, project_id=project_id, limit=limit)
        seeds = [h.id for h in response.hits]
        nodes: dict[str, dict[str, Any]] = {}
        edges: list[dict[str, Any]] = []

        for hit in response.hits:
            nodes[hit.id] = {
                "id": hit.id,
                "title": hit.memory.get("title"),
                "type": hit.memory.get("memory_type"),
                "status": hit.memory.get("status"),
                "created_at": hit.memory.get("created_at"),
                "role": "seed",
                "why": hit.why_retrieved,
            }

        for seed in seeds:
            for neighbor in self.store.neighbors(seed, depth=depth):
                mid = neighbor["memory_id"]
                if mid not in nodes:
                    trace = self.store.get_trace(mid)
                    if trace is None:
                        continue
                    nodes[mid] = {
                        "id": mid,
                        "title": trace.get("title"),
                        "type": trace.get("memory_type"),
                        "status": trace.get("status"),
                        "created_at": trace.get("created_at"),
                        "role": "associated",
                        "via": neighbor["via"],
                    }
                edges.append({
                    "source": seed,
                    "target": mid,
                    "relation": neighbor["via"],
                    "distance": neighbor["distance"],
                })

        ordered = sorted(nodes.values(), key=lambda n: (n.get("created_at") or "", n["id"]))
        return {
            "cue": cue,
            "nodes": list(nodes.values()),
            "edges": edges,
            "chain": ordered,
            "narrative": self._narrate(cue, ordered, edges),
        }

    @staticmethod
    def _narrate(cue: str, chain: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[str]:
        """A short, traceable reconstruction (not a generated claim)."""
        rel_by_pair = {(e["source"], e["target"]): e["relation"] for e in edges}
        lines = [f"Cue: {cue}"]
        for node in chain:
            relation = ""
            for (src, tgt), rel in rel_by_pair.items():
                if tgt == node["id"]:
                    relation = f" ({rel})"
                    break
            lines.append(f"- [{node.get('type')}] {node.get('title')}{relation} → {node['id']}")
        return lines

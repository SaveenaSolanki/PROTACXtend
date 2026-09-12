"""Evidence model: typed provenance with a transparent quality hierarchy.

An LLM inference never carries the weight of replicated experimental data
(Master Prompt §23). This module is the deterministic arbiter of that rule.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from .ontology import (
    COMPUTATIONAL_EVIDENCE,
    EXPERIMENTAL_EVIDENCE,
    LITERATURE_EVIDENCE,
    evidence_quality,
)


@dataclass
class EvidenceRef:
    evidence_type: str
    title: str | None = None
    description: str | None = None
    source_type: str | None = None
    source_ref: str | None = None
    doi: str | None = None
    pmid: str | None = None
    url: str | None = None
    pdb: str | None = None
    accession: str | None = None
    file_path: str | None = None
    dataset_row_id: str | None = None
    experiment_id: str | None = None
    notebook_id: str | None = None
    model_name: str | None = None
    model_version: str | None = None
    timestamp: str | None = None
    quality: float | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    @property
    def effective_quality(self) -> float:
        return self.quality if self.quality is not None else evidence_quality(self.evidence_type)

    @property
    def group(self) -> str:
        """Independence group: two evidence items in the same group are not independent."""
        return self.experiment_id or self.doi or self.pmid or self.accession or self.evidence_type

    def to_row(self) -> dict[str, Any]:
        return {
            "evidence_type": self.evidence_type,
            "title": self.title,
            "description": self.description,
            "source_type": self.source_type,
            "source_ref": self.source_ref,
            "doi": self.doi,
            "pmid": self.pmid,
            "url": self.url,
            "pdb": self.pdb,
            "accession": self.accession,
            "file_path": self.file_path,
            "dataset_row_id": self.dataset_row_id,
            "experiment_id": self.experiment_id,
            "notebook_id": self.notebook_id,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "timestamp": self.timestamp,
            "quality": self.effective_quality,
            "payload_json": self.payload,
        }


@dataclass
class EvidenceBundle:
    """Aggregate evidence statistics used by confidence + consolidation."""

    supports: list[EvidenceRef] = field(default_factory=list)
    contradicts: list[EvidenceRef] = field(default_factory=list)
    context: list[EvidenceRef] = field(default_factory=list)

    @property
    def n_supporting(self) -> int:
        return len(self.supports)

    @property
    def n_contradicting(self) -> int:
        return len(self.contradicts)

    def independent_sources(self, stance: str = "supports") -> int:
        items = self.supports if stance == "supports" else self.contradicts
        groups = {item.group for item in items if item.group}
        return len(groups)

    def independent_kinds(self, stance: str = "supports") -> int:
        items = self.supports if stance == "supports" else self.contradicts
        return len({_kind(item.evidence_type) for item in items})

    def count_kind(self, kinds: Iterable[str]) -> int:
        wanted = set(kinds)
        return sum(1 for item in self.supports if item.evidence_type in wanted)

    @property
    def aggregate_weight(self, ) -> float:
        return sum(item.effective_quality for item in self.supports)

    @property
    def aggregate_opposing_weight(self) -> float:
        return sum(item.effective_quality for item in self.contradicts)

    @property
    def contradiction_ratio(self) -> float:
        total = len(self.supports) + len(self.contradicts)
        if total == 0:
            return 0.0
        return len(self.contradicts) / total

    @property
    def mean_quality(self) -> float:
        if not self.supports:
            return 0.0
        return self.aggregate_weight / len(self.supports)

    @property
    def has_experimental_or_literature(self) -> bool:
        for item in self.supports:
            if item.evidence_type in EXPERIMENTAL_EVIDENCE or item.evidence_type in LITERATURE_EVIDENCE:
                return True
        return False

    @property
    def llm_only(self) -> bool:
        if not self.supports:
            return False
        return all(item.evidence_type == "llm_inference" for item in self.supports)

    def feature_dict(self) -> dict[str, float]:
        return {
            "n_supporting": float(self.n_supporting),
            "n_contradicting": float(self.n_contradicting),
            "n_independent_sources": float(self.independent_sources()),
            "n_experimental": float(self.count_kind(EXPERIMENTAL_EVIDENCE)),
            "n_computational": float(self.count_kind(COMPUTATIONAL_EVIDENCE)),
            "n_literature": float(self.count_kind(LITERATURE_EVIDENCE)),
            "mean_quality": self.mean_quality,
            "contradiction_ratio": self.contradiction_ratio,
            "aggregate_weight": self.aggregate_weight,
        }


def _kind(evidence_type: str) -> str:
    if evidence_type in EXPERIMENTAL_EVIDENCE:
        return "experimental"
    if evidence_type in COMPUTATIONAL_EVIDENCE:
        return "computational"
    if evidence_type in LITERATURE_EVIDENCE:
        return "literature"
    if evidence_type == "llm_inference":
        return "llm"
    if evidence_type == "user_assertion":
        return "user"
    return "other"


def independent_evidence_count(refs: Iterable[EvidenceRef]) -> int:
    return len({item.group for item in refs if item.group})

def weakest_evidence_confidence(refs: Iterable[EvidenceRef]) -> float:
    items = list(refs)
    if not items:
        return 0.0
    return min(item.effective_quality for item in items)

def strongest_evidence_confidence(refs: Iterable[EvidenceRef]) -> float:
    items = list(refs)
    if not items:
        return 0.0
    return max(item.effective_quality for item in items)

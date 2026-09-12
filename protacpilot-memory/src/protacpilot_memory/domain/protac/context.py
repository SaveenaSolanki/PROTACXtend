"""PROTAC scientific context: normalised molecular/assay context + fingerprints.

The context is deliberately *partial* — memories populate only the fields that
apply. A context fingerprint implements **pattern separation** (Master Prompt
§12): two experiences are identical only when their scientific coordinates are
identical, never because their prose is similar.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from ...util import normalize_text

# Fingerprint coordinates, in canonical order (Master Prompt §12).
FINGERPRINT_FIELDS = (
    "target",
    "target_domain",
    "e3",
    "compound",
    "cell",
    "assay",
    "time",
    "source_type",
)


@dataclass
class ProtacContext:
    # target
    target_uniprot: str | None = None
    target_gene: str | None = None
    target_domain: str | None = None
    # E3
    e3_ligase: str | None = None
    e3_complex: str | None = None
    # chemistry
    warhead_name: str | None = None
    warhead_smiles: str | None = None
    e3_ligand_name: str | None = None
    e3_ligand_smiles: str | None = None
    linker_smiles: str | None = None
    linker_length: float | None = None
    linker_type: str | None = None
    linker_attachment_points: str | None = None
    protac_smiles: str | None = None
    canonical_smiles: str | None = None
    compound_id: str | None = None
    # biology
    cell_line: str | None = None
    organism: str | None = None
    tissue: str | None = None
    # assay / measurement
    assay_type: str | None = None
    assay_time: str | None = None
    concentration: float | None = None
    dc50: float | None = None
    dmax: float | None = None
    ic50: float | None = None
    kd: float | None = None
    ki: float | None = None
    permeability: float | None = None
    solubility: float | None = None
    logd: float | None = None
    # structure / model
    pdb_ids: list[str] = field(default_factory=list)
    ternary_complex_score: float | None = None
    cooperativity: float | None = None
    model_name: str | None = None
    model_version: str | None = None
    # free-form
    extra: dict[str, Any] = field(default_factory=dict)

    # ── the fingerprint coordinates ──────────────────────────────────────────
    def _coordinate(self, name: str, source_type: str | None = None) -> str:
        if name == "target":
            return normalize_text(self.target_gene or self.target_uniprot or "")
        if name == "target_domain":
            return normalize_text(self.target_domain or "")
        if name == "e3":
            return normalize_text(self.e3_ligase or self.e3_complex or "")
        if name == "compound":
            ident = (
                self.compound_id
                or self.canonical_smiles
                or self.protac_smiles
                or self.warhead_name
                or ""
            )
            return normalize_text(ident)
        if name == "cell":
            return normalize_text(self.cell_line or "")
        if name == "assay":
            return normalize_text(self.assay_type or "")
        if name == "time":
            return normalize_text(self.assay_time or "")
        if name == "source_type":
            return normalize_text(source_type or "")
        return ""

    def fingerprint(self, source_type: str | None = None) -> str:
        parts = [self._coordinate(f, source_type) for f in FINGERPRINT_FIELDS]
        raw = "|".join(parts)
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:24]

    def fingerprint_coordinates(self, source_type: str | None = None) -> dict[str, str]:
        return {f: self._coordinate(f, source_type) for f in FINGERPRINT_FIELDS}

    # ── machine-readable scope (Master Prompt §18) ───────────────────────────
    def scope(self, evidence_scope: str | None = None) -> dict[str, Any]:
        return {
            "target_scope": self.target_gene or self.target_uniprot,
            "target_domain_scope": self.target_domain,
            "e3_scope": self.e3_ligase,
            "warhead_scope": self.warhead_name,
            "cell_scope": self.cell_line,
            "assay_scope": self.assay_type,
            "organism_scope": self.organism,
            "evidence_scope": evidence_scope,
        }

    # ── comparison ───────────────────────────────────────────────────────────
    def match_score(self, other: "ProtacContext") -> float:
        """Fraction of shared *known* coordinates. 0.0 when nothing overlaps."""
        a = self.fingerprint_coordinates()
        b = other.fingerprint_coordinates()
        known = 0
        matched = 0
        for key in FINGERPRINT_FIELDS:
            if key == "source_type":
                continue
            va, vb = a.get(key, ""), b.get(key, "")
            if not va and not vb:
                continue
            known += 1
            if va and vb and va == vb:
                matched += 1
        if known == 0:
            return 0.0
        return matched / known

    def diff(self, other: "ProtacContext") -> dict[str, tuple[str, str]]:
        a = self.fingerprint_coordinates()
        b = other.fingerprint_coordinates()
        out: dict[str, tuple[str, str]] = {}
        for key in FINGERPRINT_FIELDS:
            va, vb = a.get(key, ""), b.get(key, "")
            if va != vb:
                out[key] = (va, vb)
        return out

    # ── serialisation ────────────────────────────────────────────────────────
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ProtacContext":
        if not data:
            return cls()
        allowed = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        clean = {k: v for k, v in data.items() if k in allowed}
        pdb_ids = clean.get("pdb_ids")
        if isinstance(pdb_ids, str):
            clean["pdb_ids"] = [p for p in re.split(r"[,\s]+", pdb_ids) if p]
        return cls(**clean)

    @classmethod
    def from_scope(cls, scope: dict[str, Any] | None) -> "ProtacContext":
        """Reconstruct a context from a machine-readable scope dict (Master Prompt §18)."""
        if not scope:
            return cls()
        mapping = {
            "target_scope": "target_gene",
            "target_domain_scope": "target_domain",
            "e3_scope": "e3_ligase",
            "warhead_scope": "warhead_name",
            "cell_scope": "cell_line",
            "assay_scope": "assay_type",
            "organism_scope": "organism",
        }
        data: dict[str, Any] = {}
        for scope_key, field_name in mapping.items():
            value = scope.get(scope_key)
            if value:
                data[field_name] = value
        return cls(**data)


def context_from_any(value: Any) -> ProtacContext:
    """Coerce a context-like value into a ProtacContext."""
    if value is None:
        return ProtacContext()
    if isinstance(value, ProtacContext):
        return value
    if isinstance(value, dict):
        return ProtacContext.from_dict(value)
    return ProtacContext.from_dict(getattr(value, "__dict__", {}))

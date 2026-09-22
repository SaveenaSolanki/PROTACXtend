"""Scientific Request Parser — the single front door of the canonical stack.

Natural language in, a typed :class:`ScientificRequest` out. This module is
the *only* place a raw user string is interpreted before the orchestrator
runs; every downstream module receives structured fields, which is what makes
routing, provenance and benchmark attribution deterministic.

The parser delegates entity recognition to the deterministic NLP layer
(:mod:`protacxtend.nlp.entity_extraction`) and does not invent entities: absent
required fields are reported in ``missing_required`` instead of guessed. A
fail-closed guard discards gene-shaped English words (e.g. ``suggest``) that
are not known symbols and carry no digit/hyphen.
"""

from __future__ import annotations

import re
from typing import Any

from protacxtend.canonical.schemas import ScientificRequest

# Entities the canonical stack considers required before a design run.
REQUIRED_FIELDS = ("target",)
_GENE_DIGIT_RE = re.compile(r"[A-Za-z]\d|\d[A-Za-z]")


class ScientificRequestParser:
    """Parse a natural-language objective into a typed request."""

    name = "ScientificRequestParser"

    def parse(self, user_request: str, config: dict[str, Any] | None = None) -> ScientificRequest:
        config = config or {}
        text = (user_request or "").strip()
        entities = self._extract(text)

        target = (getattr(entities, "target_gene", "") or "").strip()
        e3 = (getattr(entities, "e3_preference", "") or "").strip()
        disease = getattr(entities, "disease_context", None) or ""
        cell_line = getattr(entities, "cell_line", None) or ""
        constraints = dict(getattr(entities, "molecule_constraints", {}) or {})

        # Explicit config overrides win (API/TUI forms, benchmark harnesses).
        target = str(config.get("target") or target)
        e3 = str(config.get("e3_ligase") or e3)
        cell_line = str(config.get("cell_line") or cell_line)
        disease = str(config.get("disease_context") or disease)

        target_warning = ""
        if not config.get("target"):
            target, target_warning = self._guard_target(
                target, float(getattr(entities, "confidence", 0.0) or 0.0)
            )

        objectives = self._objectives(text, constraints)
        candidate_count = int(config.get("candidate_count") or constraints.get("candidate_count") or 50)

        missing = [field for field in REQUIRED_FIELDS if not locals()[field]]
        warnings: list[str] = []
        if target_warning:
            warnings.append(target_warning)
        if e3:
            warnings.append(f"E3 ligase provided by user: {e3}")
        else:
            warnings.append("No E3 ligase specified; downstream E3 selection must branch and label the assumption.")

        return ScientificRequest(
            raw_request=user_request or "",
            normalized_request=" ".join(text.split()),
            target=target,
            target_uniprot_id=config.get("target_uniprot_id") or getattr(entities, "target_uniprot_id", None),
            e3_ligase=e3,
            disease_context=disease,
            cell_line=cell_line,
            intent=getattr(entities, "intent", "general_query") or "general_query",
            task_type=getattr(entities, "task_type", "general_query") or "general_query",
            requested_modality=getattr(entities, "requested_modality", "unspecified") or "unspecified",
            objectives=objectives,
            constraints=constraints,
            candidate_count=candidate_count,
            missing_required=missing,
            confidence=float(getattr(entities, "confidence", 0.0) or 0.0),
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    def _extract(self, text: str):
        try:
            from protacxtend.nlp.entity_extraction import extract_entities

            return extract_entities(text)
        except Exception:
            return _EmptyEntities()

    @staticmethod
    def _guard_target(target: str, confidence: float) -> tuple[str, str]:
        if not target:
            return "", ""
        if target.upper() in _known_gene_symbols():
            return target, ""
        if _GENE_DIGIT_RE.search(target):
            return target, ""
        if confidence >= 0.6:
            return target, ""
        return "", f"Discarded low-confidence gene-shaped token '{target}' (not a known gene symbol)."

    @staticmethod
    def _objectives(text: str, constraints: dict[str, Any]) -> list[str]:
        lowered = text.lower()
        objectives: list[str] = []
        if "degrad" in lowered:
            objectives.append("cellular_degradation")
        if "selectiv" in lowered:
            objectives.append("selectivity")
        if "oral" in lowered or "bioavail" in lowered or "adme" in lowered:
            objectives.append("developability")
        if "synthes" in lowered or "feasib" in lowered:
            objectives.append("synthetic_feasibility")
        if "novel" in lowered or "patent" in lowered:
            objectives.append("novelty")
        if constraints.get("use_structure_aware_ranking"):
            objectives.append("structure_aware_ranking")
        if not objectives:
            objectives.append("balanced_degradation_and_developability")
        return objectives


def _known_gene_symbols() -> frozenset[str]:
    """Known HGNC symbols from the curated target table + seed list."""
    try:
        from protacxtend.nlp.entity_extraction import GENE_SYMBOLS

        return GENE_SYMBOLS
    except Exception:
        return frozenset()


class _EmptyEntities:
    """Fallback used only if the NLP layer is unavailable."""

    target_gene = ""
    e3_preference = None
    disease_context = None
    cell_line = None
    target_uniprot_id = None
    intent = "general_query"
    task_type = "general_query"
    requested_modality = "unspecified"
    molecule_constraints: dict[str, Any] = {}
    confidence = 0.0

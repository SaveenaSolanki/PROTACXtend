"""Single-pass target / E3 entity resolution with ambiguity rejection.

The locked closed-48 run resolved entities *inside* the free-text pipeline,
where a later agent could overwrite an earlier resolution (and ``AR``/``ER``
were matched as substrings of ordinary words such as ``warhead``). This module
resolves the target and E3 exactly once, from the structured ``supplied_inputs``
first, and returns a typed record that the rest of the workflow treats as
immutable.

Rules
-----
* Only explicit, word-boundary target keys contribute a target. ``off-target``
  and ``e3`` keys never do.
* A ``target/e3`` or ``target-e3 pair`` key is split into target + E3.
* The free-text entity extractor is consulted only when no explicit target key
  exists, and only when it returns a curated gene symbol.
* More than one distinct curated target symbol -> :data:`ambiguous` is True and
  the caller must abstain rather than pick one.
"""

from __future__ import annotations

import re
from typing import Any

# Exact normalised keys. Word-boundary matching replaces the old substring
# test that let "off-target" masquerade as "target".
_TARGET_KEYS = {
    "target", "target name", "target protein", "gene", "gene/target name",
    "target context", "poi", "protein of interest",
}
_TARGET_E3_KEYS = {"target/e3", "target-e3 pair", "target-e3", "target e3"}
_E3_KEYS = {"e3", "e3 ligase", "e3:", "e3 candidates", "e3 ligand", "e3-ligand"}

# Keys that contain the substring "target" but are explicitly NOT the target.
_TARGET_ANTI_KEYS = {"off-target", "off target", "anti-target", "anti target"}

_ACCESSION_RE = re.compile(
    r"^(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})$"
)

#: E3 ligases are a small, well-known set; accept them by name even though the
#: curated gene-symbol list is intentionally small.
_KNOWN_E3 = {
    "VHL", "CRBN", "DCAF15", "DCAF16", "DCAF1", "FEM1B", "XIAP", "IAP",
    "MDM2", "KEAP1", "BIRC2", "BIRC3", "RNF114", "RNF4", "TRIM21", "SIAH1",
}

#: Common target gene symbols used by the benchmark. Applied only to explicit
#: target keys, so free-text words cannot be mistaken for entities.
_KNOWN_TARGETS = {
    "BRD4", "BRD2", "BRD3", "BTK", "CDK9", "ESR1", "AR", "ER", "MAP2K1",
    "SMARCA4", "AKT1", "AURKA", "AURKB", "RIPK1", "IKZF3", "ALK", "FGFR2",
    "TYK2", "PLK1", "KRAS", "MYC", "BCL6", "STAT3", "GSPT1", "EGFR", "BCL2",
}


def _is_target_token(token: str) -> bool:
    return is_known_gene(token) or token.strip().upper() in _KNOWN_TARGETS
_SMILES_RE = re.compile(r"^[A-Za-z0-9@+\-\[\]\(\)=#$\\/%.*:]+$")


def _norm_key(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _is_accession(token: str) -> bool:
    return bool(_ACCESSION_RE.match(token.strip().upper()))


def _curated_symbols() -> set[str]:
    try:
        from protacxtend.nlp.entity_extraction import _load_gene_symbols

        return {s.upper() for s in _load_gene_symbols()}
    except Exception:  # noqa: BLE001
        return set()


def is_known_gene(token: str) -> bool:
    """True when *token* is a curated gene symbol or a UniProt accession."""
    token = (token or "").strip().rstrip(",;.")
    if not token:
        return False
    if _is_accession(token):
        return True
    return token.upper() in _curated_symbols()


def _tokens(value: str) -> list[str]:
    """Split an input value into candidate entity tokens (word-boundary)."""
    parts = re.split(r"[\s,/;+()|]+", value)
    return [p.strip().rstrip(",;.") for p in parts if p.strip()]


def _looks_like_smiles(value: str) -> bool:
    value = value.strip()
    if len(value) < 6 or " " in value or not _SMILES_RE.match(value):
        return False
    return any(ch.isalpha() for ch in value) and ("C" in value or "c" in value or "[" in value)


def _unique(seq: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in seq:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def resolve_entities(case: dict[str, Any]) -> dict[str, Any]:
    """Resolve target and E3 from structured inputs, once.

    Returns a typed dict::

        {"target": str, "e3_ligases": [...], "target_candidates": [...],
         "ambiguous": bool, "reason": str, "sources": {...}}
    """
    target_tokens: list[str] = []
    e3_tokens: list[str] = []
    sources: dict[str, str] = {}

    for raw in case.get("supplied_inputs") or []:
        text = str(raw).strip()
        if ":" not in text:
            continue
        key, value = text.split(":", 1)
        key_l = _norm_key(key)
        value = value.strip()
        if not value or key_l in _TARGET_ANTI_KEYS:
            continue

        if key_l in _TARGET_E3_KEYS:
            toks = _tokens(value)
            if toks:
                target_tokens.append(toks[0])
                sources["target"] = raw
            for e3 in toks[1:]:
                if is_known_gene(e3) or e3.upper() in _KNOWN_E3:
                    e3_tokens.append(e3.upper())
                    sources.setdefault("e3_ligase", raw)
            continue

        if key_l in _TARGET_KEYS:
            genes = [t for t in _tokens(value) if _is_target_token(t)]
            if genes:
                target_tokens.extend(genes)
                sources["target"] = raw
            continue

        if key_l in _E3_KEYS and "ligand" not in key_l:
            for tok in _tokens(value):
                if is_known_gene(tok) or tok.upper() in _KNOWN_E3:
                    e3_tokens.append(tok.upper())
                    sources.setdefault("e3_ligase", raw)

    target_candidates = _unique([t.upper() for t in target_tokens])
    e3_candidates = _unique(e3_tokens)

    # Free-text fallback only when no explicit target key was present.
    if not target_candidates:
        try:
            from protacxtend.nlp.entity_extraction import extract_entities

            candidate = (extract_entities(case.get("scientific_question", "")).target_gene or "").upper()
            if is_known_gene(candidate):
                target_candidates = [candidate]
                sources["target"] = "nlp_entity_extraction"
        except Exception:  # noqa: BLE001
            pass

    ambiguous = len(target_candidates) > 1
    reason = ""
    if ambiguous:
        reason = (
            "Supplied target context maps to multiple reviewed entities "
            f"({', '.join(target_candidates)}); refusing to choose one silently."
        )

    return {
        "target": "" if ambiguous else (target_candidates[0] if target_candidates else ""),
        "e3_ligases": e3_candidates,
        "target_candidates": target_candidates,
        "ambiguous": ambiguous,
        "reason": reason,
        "sources": sources,
        # E3 candidate sets are a deliberate compare-both instruction, not an
        # ambiguity; record the distinction so callers do not conflate them.
        "e3_is_candidate_set": len(e3_candidates) > 1,
    }


__all__ = ["resolve_entities", "is_known_gene"]

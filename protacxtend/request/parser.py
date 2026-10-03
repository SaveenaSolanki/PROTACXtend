"""Utterance parser -> shared RequestUnderstanding (requirement 1).

- raw text preserved verbatim alongside every parsed field;
- target mentions, organism, mutation/isoform, supplied ligands, constraints
  and delegated choices are separate fields;
- \"use CRBN\" (explicit) is distinguished from \"find a suitable E3\"
  (delegated) and from no E3 mention (unspecified);
- entity extraction is reused for disease/cell-line hints where available,
  but target tokens are collected from the RAW text (never from a normalized
  string that dropped the first token).
"""

from __future__ import annotations

import re
from typing import Any

from protacxtend.request.model import (
    COMMAND_ACTIONS, E3Request, NAMED_E3, RESEARCH_ACTIONS, TargetMention,
    RequestUnderstanding, MUTATION_RE,
)

ACTION_VERBS = {
    "plan": ("plan", "strategy", "objective", "approach", "campaign"),
    "investigate": ("investigate", "explore", "research", "study"),
    "reason": ("reason", "rationale", "justify", "mechanism"),
    "compare": ("compare", "comparison", "versus", "vs", "alternative"),
    "design": ("design", "build", "generate", "construct"),
    "optimize": ("optimize", "optimisation", "optimization", "improve", "refine"),
    "structure": ("structure", "ternary", "binding mode", "pose", "docking"),
    "selectivity": ("selectivity", "selective", "off-target", "proteome"),
    "degradation": ("degradation", "degrade", "dc50", "dmax", "hook", "degrader"),
    "admet": ("admet", "permeability", "pk", "adme", "tox", "hERG", "pampa"),
    "synthesis": ("synthesis", "synthetic", "retrosynthesis", "route"),
    "experiment": ("experiment", "assay", "wet lab", "validate", "hirbit", "western"),
    "evidence": ("evidence", "literature", "references", "support", "provenance"),
    "run": ("run", "execute", "launch"),
}

_WARHEAD_HINTS = ("warhead smiles", "warhead_smiles", "binder smiles")
_E3_LIGAND_HINTS = ("e3 ligand smiles", "e3_ligand_smiles")
_LINKER_HINTS = ("linker smiles", "linker_smiles")

# Reviewed, deterministic multi-word target aliases that should be treated as
# one identity mention. The resolver then supplies the canonical accession.
_PHRASE_TARGETS = {
    "androgen receptor": "AR",
    "estrogen receptor": "ESR1",
    "epidermal growth factor receptor": "EGFR",
}


class RequestParser:
    """Deterministic parser: intent/action, mentions, E3 mode, extras."""

    def parse(self, text: str, *, default_action: str = "plan",
              disease_hint: str = "", cell_line_hint: str = "") -> RequestUnderstanding:
        raw = (text or "").strip()
        u = RequestUnderstanding(raw_text=raw)
        lower = raw.lower()

        # --- action: explicit command token or verb ---------------------------------
        stripped = re.sub(r"^\s*/", "", raw.strip())
        first = stripped.split()[0].lower() if stripped.split() else ""
        u.action = COMMAND_ACTIONS.get(first, default_action if first not in RESEARCH_ACTIONS else first)
        for act, verbs in ACTION_VERBS.items():
            if any(verb in lower for verb in verbs) and u.action == default_action:
                u.action = act
                break
        u.intent = f"{u.action}_protac_strategy" if u.action in ("plan", "design") else f"{u.action}_research"

        # --- target mentions from RAW tokens (never from a first-token-stripped string) --
        e3_marker = any(m in lower for m in ("use ", "recruit", "with ", "ligase", "based on", "suitable"))
        candidate_tokens = []
        token_source = raw
        for phrase, symbol in _PHRASE_TARGETS.items():
            if re.search(rf"\b{re.escape(phrase)}\b", lower):
                candidate_tokens.append(symbol)
                token_source = re.sub(rf"\b{re.escape(phrase)}\b", " ", token_source, flags=re.IGNORECASE)
        for token in re.split(r"[\s,;()/|]+", token_source):
            t = token.strip(".,;:!?'\"[]{}")
            if not t or len(t) > 24:
                continue
            if t.lower() in _STOP:
                continue
            # organism/cell-line words are context, never target genes
            if t.lower() in _ORGANISM_WORDS:
                continue
            # mutation-only token (e.g. G12C) is not a target mention
            if re.fullmatch(r"[A-Z]{1,2}\d{2,4}[A-Z]?(?:del|ins|dup)?", t):
                continue
            if re.fullmatch(r"[A-Za-z][A-Za-z0-9]{1,9}", t):
                # chemistry tokens (SMILES fragments) are never target mentions
                if any(ch in t for ch in ("=", "(", ")", "[", "]")) or re.match(r"^[a-z]+\d", t):
                    continue
                # a named E3 token in recruiter context is the E3, not the POI
                if t.upper() in NAMED_E3 and (e3_marker or len(candidate_tokens) > 0):
                    continue
                candidate_tokens.append(t)
        for t in candidate_tokens:
            kind = "accession" if re.fullmatch(r"[OPQ][0-9][A-Z0-9]{3}[0-9]", t.upper()) else "symbol"
            u.target_mentions.append(TargetMention(raw=t, entity_kind=kind))

        # --- mutation / isoform -------------------------------------------------------
        for m in MUTATION_RE.findall(raw):
            if u.mutation:
                break
            u.mutation = m

        # --- supplied ligands / constraints -------------------------------------------
        for hint in _WARHEAD_HINTS:
            m = re.search(hint + r"\s*[:=]?\s*(\S+)", lower)
            if m:
                u.supplied_ligands["warhead_smiles"] = m.group(1)
        for hint in _E3_LIGAND_HINTS:
            m = re.search(hint + r"\s*[:=]?\s*(\S+)", lower)
            if m:
                u.supplied_ligands["e3_ligand_smiles"] = m.group(1)
        for hint in _LINKER_HINTS:
            m = re.search(hint + r"\s*[:=]?\s*(\S+)", lower)
            if m:
                u.supplied_ligands["linker_smiles"] = m.group(1)

        # --- E3 request mode ----------------------------------------------------------
        named = [k for k in NAMED_E3 if re.search(rf"\b{re.escape(k.lower())}\b", lower) or k.lower() in lower.split()]
        delegation = any(w in lower for w in ("suitable e3", "appropriate e3", "find an e3", "find a suitable e3",
                                              "choose an e3", "evaluate e3", "select an e3", "which e3",
                                              "best e3", "screen e3"))
        if named:
            u.e3 = E3Request(mode="explicit", named_e3=named[0])
        elif delegation:
            u.e3 = E3Request(mode="delegated")
            u.delegated_choices.append("e3_selection")
        else:
            u.e3 = E3Request(mode="unspecified")

        # --- disease / cell line hints (from the deterministic NLP layer when present) --
        u.disease_context = disease_hint or ""
        u.cell_line = cell_line_hint or ""
        u.organism = "Homo sapiens"
        if re.search(r"\b(mouse|mice|mus musculus|murine)\b", lower):
            u.organism = "Mus musculus"
        elif re.search(r"\b(rat|rattus norvegicus)\b", lower):
            u.organism = "Rattus norvegicus"
        return u


_STOP = {
    "the", "a", "an", "of", "for", "with", "using", "against", "target", "targeting",
    "receptor",
    "by", "to", "be", "is", "are", "in", "on", "at", "and", "or", "protac", "protacs",
    "degrader", "degraders", "design", "suitable", "appropriate", "interest", "urgent",
    "then", "actually", "please", "can", "we", "should", "find", "choose", "evaluate",
    "select", "search", "use", "using", "ligase", "e3", "gene", "protein", "strategy",
    "plan", "objective", "optimal", "best", "which", "know", "mutation", "isoform",
}

# Organism words are NEVER target mentions (e.g. "/plan BRD4 in mice" -> target BRD4,
# organism Mus musculus; "mice" must not compete for the target slot).
_ORGANISM_WORDS = {
    "mouse", "mice", "murine", "mus", "musculus",
    "rat", "rats", "rattus", "norvegicus",
    "human", "homo", "sapiens", "humanized",
    "zebrafish", "danio", "rerio", "dog", "canine", "monkey", "cynomolgus",
    "cell", "cells", "cellline", "cell_line", "line", "lines",
}


class EntityHint:
    """Adapter to the existing deterministic NLP layer (disease/cell-line hints)."""

    @staticmethod
    def hints(text: str) -> dict[str, str]:
        try:
            from protacxtend.nlp.entity_extraction import extract_entities
            e = extract_entities(text)
            return {"disease_context": e.disease_context or "",
                    "cell_line": e.cell_line or ""}
        except Exception:  # noqa: BLE001
            return {"disease_context": "", "cell_line": ""}
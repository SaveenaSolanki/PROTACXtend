"""Role-aware entity parsing.

The audited run ``run_e4e21ccd`` parsed ``"Reason mechanistically: BRD$-VHL"``
to target ``"BRD"`` and then a UniProt full-text search silently resolved
``BRD`` to RLBP1 (P12271). This module stops that at the front door:

* the original text is preserved verbatim;
* ``BRD4-VHL`` is recognised as a *pair* (target + E3) and never handed whole
  to a single-target resolver;
* ``BRD$`` is flagged malformed/ambiguous and blocks the flow until corrected —
  it is never normalised to BRD4, BRD3 or RLBP1.
"""

from __future__ import annotations

import re

from .records import RequestParse

#: Recognised E3 recruiter gene symbols (roles, not targets).
KNOWN_E3 = {
    "VHL", "CRBN", "CUL2", "DDB1", "MDM2", "XIAP", "CIAP1", "BIRC2",
    "BIRC3", "KEAP1", "DCAF15", "DCAF16", "RNF114", "RNF4", "ARIH1",
    "FBXO", "SKP2", "UBR2", "TRIM21",
}

#: Gene-symbol shape: letters, optional digits, optional trailing letters.
_GENE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]{1,9}$")

#: Characters that make a token malformed / ambiguous.
_BAD_CHARS = set("$#@!?*%^&+=~`|\\<>{}[]\"';:")

#: Surrounding punctuation stripped before malformed classification.
_STRIP = ".,;:!?"

_PAIR_SEPARATORS = [
    "–", "—", "-", "/", " vs ", " versus ", " and ", " + ", " with ",
]

_STOPWORDS = {
    "design", "a", "an", "the", "protac", "protacs", "degrader", "degraders",
    "for", "target", "targeting", "against", "using", "with", "via", "to",
    "make", "build", "generate", "reason", "mechanistically", "investigate",
    "compare", "evaluate", "degrade", "degradation", "please", "can", "you",
    "protein", "gene", "recruiter", "ligase", "e3", "poi", "complex",
}


def _tokens(text: str) -> list[str]:
    """Split on whitespace and pair separators, keep separators meaningful."""
    for sep in _PAIR_SEPARATORS:
        text = text.replace(sep, " ")
    return [t for t in re.split(r"[\s,;()]+", text) if t]


def _classify(token: str) -> str:
    """Return 'malformed' | 'e3' | 'gene' | 'word'."""
    stripped = token.strip(_STRIP)
    if not stripped:
        return "word"
    if any(ch in _BAD_CHARS for ch in stripped):
        return "malformed"
    if stripped.upper() in KNOWN_E3:
        return "e3"
    if _GENE_RE.match(stripped) and any(ch.isdigit() for ch in stripped):
        return "gene"
    # all-caps short tokens are plausible gene symbols (EGFR, KRAS)
    if _GENE_RE.match(stripped) and stripped.isupper() and len(stripped) >= 3:
        return "gene"
    return "word"


def parse_request(text: str) -> RequestParse:
    """Role-aware parse of a user request. Fail closed on malformed tokens."""
    raw = text or ""
    # Drop a leading workflow verb for the *normalized* view only.
    normalized = re.sub(r"^\s*/?\w+\s+", "", raw).strip() if raw.strip() else ""

    parse = RequestParse(
        raw_request=raw,
        normalized_request=normalized or raw,
        parsed_fields={"tokens": _tokens(raw)},
    )

    malformed: list[str] = []
    e3_tokens: list[str] = []
    gene_tokens: list[str] = []
    for tok in _tokens(raw):
        kind = _classify(tok)
        if kind == "malformed":
            malformed.append(tok)
        elif kind == "e3":
            e3_tokens.append(tok.upper())
        elif kind == "gene":
            if tok.lower() not in _STOPWORDS:
                gene_tokens.append(tok)

    parse.malformed_tokens = malformed

    # Pair form "BRD4–VHL" / "BRD4-VHL": target and E3 are two roles.
    pair_like = any(sep in raw for sep in ("–", "—", " vs ", " versus ", " and ", " + ", " with "))
    if not pair_like and "-" in raw:
        # hyphen used as a role separator only when both sides look like entities
        left, _, right = raw.partition("-")
        pair_like = bool(_classify(left.strip().split()[-1] if left.strip() else "")
                         in {"gene", "e3"} and _classify(right.strip().split()[0] if right.strip() else "")
                         in {"gene", "e3"})

    if gene_tokens:
        parse.target = gene_tokens[0]
        parse.target_role_token = gene_tokens[0]
    if e3_tokens:
        parse.e3_ligase = e3_tokens[0] if len(set(e3_tokens)) == 1 else ""
        if len(set(e3_tokens)) > 1:
            parse.ambiguities.append(
                "multiple E3 candidates in request: " + ", ".join(sorted(set(e3_tokens))))
    if pair_like and not parse.target and not e3_tokens:
        parse.ambiguities.append("request looks like a target–E3 pair but roles are unresolved")

    # Fail closed: any malformed token blocks the flow.
    if malformed:
        parse.requires_clarification = True
        parse.target = ""  # never emit a silent guess such as BRD
        parse.clarification_question = (
            "The request contains malformed or ambiguous token(s): "
            + ", ".join(repr(m) for m in malformed)
            + ". Please give an exact gene symbol (for example 'BRD4') and E3 recruiter "
              "(for example 'VHL'), e.g. 'BRD4-VHL'. No molecule design will run until this is corrected."
        )
        parse.ambiguities.append("malformed token(s): " + ", ".join(malformed))

    if not parse.target and not parse.requires_clarification:
        parse.requires_clarification = True
        parse.clarification_question = (
            "No protein-of-interest gene symbol could be parsed. Please provide the target gene "
            "and the E3 recruiter, e.g. 'BRD4-VHL'."
        )

    parse.parsed_fields.update({
        "target": parse.target,
        "e3_ligase": parse.e3_ligase,
        "pair_form": pair_like,
        "malformed": malformed,
    })
    return parse

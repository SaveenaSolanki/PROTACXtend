"""target_card.py — deterministic 'target card' for a bare recognized target.

Used by the TUI bridge when a user types a bare symbol (e.g. ``BRD4``) or when
the LLM asks for clarification while a target is already resolved: the card
gives canonical identity, measured degradation precedent per E3, known binders,
supported E3 ligand families, and a sensible next action in the current
conversation context. Numbers come only from packaged tables; nothing is
invented, and anything absent is reported as missing.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def _curated_record(symbol: str) -> Optional[Dict[str, Any]]:
    from protacxtend.request.controller import _curated_record as _rec
    return _rec(symbol)


def _precedent(symbol: str) -> Dict[str, Any]:
    from protacxtend.request.controller import _target_e3_precedent
    return _target_e3_precedent(symbol)


def _e3_families() -> tuple[set, int, int]:
    from protacxtend.request.controller import _e3_library
    return _e3_library()


def target_card(symbol: str) -> Dict[str, Any]:
    """Build the typed target card; safe for unknown symbols (status=missing)."""
    sym = (symbol or "").strip().upper()
    if not sym:
        return {"status": "missing", "symbol": "", "reason": "no symbol supplied"}

    from protacxtend.request.model import TargetMention
    from protacxtend.request.resolver import resolve_target
    r = resolve_target(TargetMention(raw=sym, organism="Homo sapiens"))

    status = "missing"
    if r.status in ("verified", "tentative"):
        status = "available"

    curated = _curated_record(sym) or _curated_record(r.symbol if r.symbol else sym) or {}
    precedent = _precedent(r.symbol if r.symbol else sym)
    families, _non_demo, n_rows = _e3_families()

    pairs = precedent.get("pairs") or {}
    e3_rows = [
        {"e3": k, "measured_degradation_rows": v["n"]}
        for k, v in sorted(pairs.items(), key=lambda kv: -kv[1]["n"])
    ] or None

    next_actions = [
        "/plan %s protac" % (r.symbol or sym),
        "/investigate T1 (target biology + degradation rationale)" if r.symbol else "/plan <symbol> protac",
        "/design ... using <E3>" if r.symbol else "",
    ]
    next_actions = [a for a in next_actions if a]

    card: Dict[str, Any] = {
        "status": status,
        "symbol": r.symbol or sym,
        "requested_symbol": sym,
        "uniprot_id": r.uniprot_id,
        "organism": r.organism,
        "match_type": r.match_type,
        "resolver_source": r.resolver_source,
        "confidence": r.confidence,
        "aliases": curated.get("aliases") or [],
        "structures": curated.get("structures") or [],
        "known_binder_count": curated.get("known_binder_count") or None,
        "measured_degradation_total": precedent.get("total", 0),
        "e3_measured_precedent": e3_rows,
        "e3_ligand_families": sorted(families),
        "e3_ligand_cited_rows": n_rows,
        "missing": [],
        "recommendation": "abstained",   # never invented: evidence-only below
        "next_actions": next_actions,
    }
    if not precedent.get("total"):
        card["missing"].append("measured degradation precedent (packaged context set)")
    if not curated.get("known_binder_count"):
        card["missing"].append("known-binder census")
    if not card["e3_ligand_families"]:
        card["missing"].append("DOI-cited E3 ligand families")
    if pairs:
        card["recommendation"] = (
            "rank E3 by measured degradation rows: " +
            ", ".join(f"{k} ({v['n']})" for k, v in sorted(pairs.items(), key=lambda kv: -kv[1]["n"]))
        )
    else:
        card["recommendation"] = (
            "no measured per-E3 precedent — evaluate ligand availability + tissue expression "
            "before choosing; do not invent a preference"
        )
    return card


def target_card_markdown(card: Dict[str, Any]) -> str:
    """Render the card the way a research brief would (deterministic)."""
    lines = [
        f"## Target card — {card.get('symbol') or '?'}",
        "",
    ]
    if card.get("status") != "available":
        lines += [
            f"`{card.get('requested_symbol')}` could not be resolved to a canonical gene symbol "
            f"({card.get('resolver_source') or 'none'}); no card is fabricated.",
            "",
        ]
        return "\n".join(lines)
    lines += [
        f"**Identity:** {card['symbol']} · UniProt {card['uniprot_id'] or '—'} · "
        f"{card['organism'] or '—'} · resolved via {card['match_type']} "
        f"({card['resolver_source']}, conf {card['confidence']}).",
        f"**Aliases:** {', '.join(card['aliases']) if card['aliases'] else '—'}"
        + (f" · **Structures:** {', '.join(card['structures'])}" if card.get("structures") else ""),
        "",
    ]
    if card.get("known_binder_count"):
        lines.append(f"**Binders:** {card['known_binder_count']} known binder(s) recorded (warhead needs a source-backed attachment vector).")
    lines.append(f"**Degradation precedent:** {card['measured_degradation_total']} measured row(s) in the packaged context set.")
    if card.get("e3_measured_precedent"):
        lines.append("**Per-E3 measured rows:** " + ", ".join(
            f"{e['e3']}: {e['measured_degradation_rows']}" for e in card["e3_measured_precedent"]) + ".")
    else:
        lines.append("**Per-E3 measured rows:** none in the packaged context set.")
    families = card.get("e3_ligand_families") or []
    lines.append(f"**Supported E3 ligands (DOI-cited):** {', '.join(families) if families else 'none'} "
                 f"({card.get('e3_ligand_cited_rows', 0)} rows).")
    if card.get("missing"):
        lines.append("**Missing (not invented):** " + "; ".join(card["missing"]) + ".")
    lines += ["", f"**E3 recommendation:** {card.get('recommendation')}", ""]
    if card.get("next_actions"):
        lines.append("**Sensible next action(s):** " + " · ".join(card["next_actions"]) + ".")
    lines += ["", "*Every number above comes from packaged tables or the resolver; nothing was fabricated.*", ""]
    return "\n".join(lines)
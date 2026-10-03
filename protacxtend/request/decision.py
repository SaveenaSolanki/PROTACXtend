"""Decision policy (requirement 3): ask only when a missing fact would change
the entity/workflow that runs and cannot be resolved confidently.

Rules:
- verified target  -> proceed;
- single fuzzy suggestion -> a precise one-turn question presenting the
  tentative interpretation (\"did you mean X?\"); never auto-converted;
- several plausible candidates -> a question that LISTS the candidates;
- unknown (nothing found)   -> one generic exact-symbol question noting what
  was searched;
- delegated/unspecified E3  -> research task (never a blocking omission);
- explicit E3               -> used as given.
"""

from __future__ import annotations

from protacxtend.request.model import Clarification, RequestUnderstanding, TargetResolution


def decide(u: RequestUnderstanding) -> Clarification:
    """Controller decision from structured state; never free-form model text.

    Returns a Clarification; pending=False means proceed.
    """
    c = Clarification()
    t = u.primary_target
    if t is None:
        # target missing entirely
        names = ", ".join(f"'{m.raw}'" for m in u.target_mentions[:4]) or "no target mention"
        c = Clarification(pending=True, question=(
            "No resolvable protein-of-interest gene symbol was found "
            f"(searched: {names}). Please give an exact reviewed gene symbol, e.g. 'BRD4'."),
            for_field="target")
        return c
    if t.status == "verified":
        return c
    if t.status == "ambiguous":
        cands = [a.get("symbol") or a.get("gene_symbol") or a.get("protein_name") or "?"
                 for a in t.alternatives[:5]]
        c = Clarification(pending=True, question=(
            f"'{t.symbol}' is ambiguous — multiple reviewed candidates found: "
            + ", ".join(cands) + ". Please give the exact gene symbol."),
            candidates=cands, for_field="target")
        return c
    if t.status == "unknown" and t.suggestion:
        c = Clarification(pending=True, question=(
            f"'{t.symbol}' could not be resolved to a canonical gene symbol. "
            f"Did you mean '{t.suggestion}'? Reply with the exact symbol to continue "
            f"({t.symbol} itself is not a canonical symbol and is not converted automatically)."),
            candidates=[t.suggestion], for_field="target")
        return c
    if t.status == "unknown" or t.status == "unresolved":
        c = Clarification(pending=True, question=(
            f"'{t.symbol}' could not be resolved to a canonical gene symbol "
            f"[resolver: {t.resolver_source}]. Please give the exact symbol."),
            for_field="target")
        return c
    if t.status == "tentative":
        # single plausible protein-name match: proceed with a visible assumption
        u.assumptions.append(
            f"'{t.symbol}' resolved tentatively to {t.symbol} ({t.uniprot_id}) "
            f"via {t.match_type} match [{t.resolver_source}]; confirmation advised.")
        return c
    return c
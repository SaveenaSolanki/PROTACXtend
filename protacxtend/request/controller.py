"""Workflow controller (requirements 5–6).

The controller decides continue / ask-targeted-question / report-limitation
from structured state and tool results. The model (LLM) has a bounded
reasoning role only (interpret complex goals, propose searches, synthesise,
identify gaps); identifiers and retrieved facts come from tools.

Once the target is verified, the controller proceeds through the scientific
workflow and produces a traceable plan:
  target biology & degradation rationale -> binders/exit vectors -> E3 options
  + evidence -> tissue/context -> ligand availability -> ternary feasibility
  -> validation proposal.
Evidence stages are labelled observed / computational / missing. An E3
recommendation is never invented to complete the workflow: with no evidence
the stage is reported missing and the plan abstains.
"""

from __future__ import annotations

import os
from typing import Optional

from protacxtend.request.decision import decide
from protacxtend.request.model import (
    Clarification, EvidenceStage, PlanDocument, RequestUnderstanding,
    TargetMention, TargetResolution,
)
from protacxtend.request.parser import EntityHint, RequestParser
from protacxtend.request.resolver import resolve_target, suggestion_symbol

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class RequestController:
    """understand() -> decide() -> run_plan(). One entry for every research command."""

    def __init__(self, offline: bool | None = None):
        self.parser = RequestParser()
        self.offline = offline

    # ------------------------------------------------------------------
    def understand(self, text: str, *, default_action: str = "plan",
                   conversation=None) -> RequestUnderstanding:
        hints = EntityHint.hints(text)
        u = self.parser.parse(text, default_action=default_action,
                              disease_hint=hints["disease_context"],
                              cell_line_hint=hints["cell_line"])
        # organism applies to every mention
        for m in u.target_mentions:
            m.organism = u.organism
            m.resolution = resolve_target(m, offline=self.offline)
        # primary target: highest-quality resolution wins; ties -> latest mention.
        # (verified > tentative > ambiguous > unknown-with-suggestion > unknown)
        # This prevents a trailing unresolved token (e.g. an organism word that
        # slipped through) from ever displacing a resolved candidate.
        def _quality(res) -> tuple[int, int]:
            s = res.status
            rank = {"verified": 5, "tentative": 4, "ambiguous": 3,
                    "unknown": 2, "unresolved": 1}.get(s, 0)
            return (rank, 1 if res.suggestion else 0)

        best: Optional[TargetResolution] = None
        for m in u.target_mentions:
            if m.resolution is None or m.resolution.status == "unresolved":
                continue
            if best is None or _quality(m.resolution) >= _quality(best):
                best = m.resolution
        u.primary_target = best
        if conversation:
            conversation.apply_correction(previous=getattr(conversation, "_last", None), current=u)
            conversation._last = u
        u.clarification = decide(u)
        return u

    # ------------------------------------------------------------------
    def run_plan(self, u: RequestUnderstanding) -> PlanDocument:
        stages: list[EvidenceStage] = []
        limitations: list[str] = []
        t = u.primary_target

        interpretation = (
            f"Target: {t.symbol} [{t.canonical_id() or 'canonical-id-pending'}]"
            f"{' (' + t.organism + ')' if t.organism and t.organism.lower() not in ('homo sapiens', 'human') else ''}; "
            f"objective: PROTAC strategy; E3: {u.e3.named_e3 if u.e3.mode == 'explicit' else 'to be evaluated'}."
        )
        if u.mutation:
            interpretation += f" Mutation/site: {u.mutation}."

        # 1 target biology & degradation rationale (observed/computational/missing)
        curated = _curated_record(t.symbol)
        if curated:
            stages.append(EvidenceStage(
                step="target_evidence", label="observed", summary=(
                    f"Canonical target: {t.symbol} ({t.uniprot_id}, {t.organism}); "
                    f"resolution {t.match_type} via {t.resolver_source} "
                    f"(confidence {t.confidence}); aliases: {', '.join(curated.get('aliases', [])) or 'n/a'}."
                    + (f" Structures: {', '.join(curated.get('structures', []))}."
                       if curated.get("structures") else "")),
                evidence=["packaged curated_targets.csv" if t.resolver_source == "curated_table"
                          else (t.source_url or "reviewed UniProt record")]))
        else:
            stages.append(EvidenceStage(
                step="target_evidence", label="observed", summary=(
                    f"Target {t.symbol} resolved via {t.resolver_source} [{t.source_url}]."),
                evidence=[t.source_url or t.resolver_source]))

        # degradation rationale evidence: measured rows in the packaged context set
        precedent = _target_e3_precedent(t.symbol)
        if precedent["total"]:
            stages.append(EvidenceStage(
                step="degradation_rationale", label="observed", summary=(
                    f"{precedent['total']} measured degradation row(s) for {t.symbol} "
                    f"across E3s: " + "; ".join(f"{k}: {v['n']}" for k, v in precedent["pairs"].items())
                    + "."), evidence=[precedent["source"]]))
        else:
            stages.append(EvidenceStage(
                step="degradation_rationale", label="missing", summary=(
                    "No measured degradation rows for this target in the packaged context set; "
                    "degradation rationale depends on literature retrieval (deferred, not invented)."),
                evidence=[]))

        # 2 binders / exit vectors
        n_binders = curated.get("known_binder_count") if curated else None
        if n_binders and str(n_binders).strip() not in ("", "0"):
            stages.append(EvidenceStage(
                step="binders_warheads", label="observed", summary=(
                    f"{n_binders} known binder(s) recorded for {t.symbol}; warhead selection requires a "
                    "source-backed binder with an attachment vector (deferred to design; none invented here)."),
                evidence=["curated_targets.csv known_binder_count"]))
        else:
            stages.append(EvidenceStage(
                step="binders_warheads", label="missing", summary=(
                    "No binder evidence retrieved in this planning session; live binder search available "
                    "in the retrieval stage. No specific warhead is proposed."),
                evidence=[]))

        # 3 E3 options + evidence (never invented)
        families, non_demo_rows, e3_rows = _e3_library()
        has_precedent = bool(precedent["pairs"])
        if families:
            summary = (f"E3 recruiter ligand evidence available for: {', '.join(families)} "
                       f"({e3_rows} DOI-cited rows, demo rows excluded).")
            if has_precedent:
                summary += " measured degradation precedent for this target: " + "; ".join(
                    f"{k}: {v['n']} row(s)" for k, v in precedent["pairs"].items()) + "."
            elif u.e3.mode == "explicit":
                summary += f" User preference: {u.e3.named_e3}."
            else:
                summary += (" No target-specific measured E3-preference evidence retrieved; "
                            "specific E3 recommendation abstained — E3 to be evaluated.")
            stages.append(EvidenceStage(
                step="e3_evidence", label="observed" if has_precedent or u.e3.mode == "explicit" else "missing",
                summary=summary,
                evidence=["curated_e3_ligands.csv (DOI-cited, demo rows excluded)",
                          precedent["source"] if has_precedent else ""]))
            if not has_precedent and u.e3.mode != "explicit":
                limitations.append(
                    f"No target-specific measured E3-preference evidence for {t.symbol}; "
                    "specific E3 recommendation abstained — E3 to be evaluated.")
        else:
            stages.append(EvidenceStage(step="e3_evidence", label="missing",
                                        summary="No DOI-cited E3 recruiter rows available; E3 evaluation missing.",
                                        evidence=[]))
            limitations.append("E3 recruiter library unavailable; E3 evaluation missing.")

        # 4 tissue/context
        if u.disease_context or u.cell_line:
            stages.append(EvidenceStage(
                step="tissue_context", label="computational", summary=(
                    f"Context: {u.cell_line or u.disease_context or 'n/a'} — cell-context degradation model "
                    "can score candidates if transcriptomic features are present (computational, not measured)."),
                evidence=["module M5 (DepMap 24Q4 transcriptomics)" if u.cell_line else "user-supplied context"]))
        else:
            stages.append(EvidenceStage(
                step="tissue_context", label="missing", summary=(
                    "No cell line / tissue context supplied; context-dependent ranking deferred."),
                evidence=[]))

        # 5 ligand availability + ternary feasibility
        stages.append(EvidenceStage(
            step="ligand_availability", label="observed" if non_demo_rows else "missing", summary=(
                f"{non_demo_rows} non-demo E3 ligand rows and curated warhead/linker tables available "
                "for assembly; component sourcing is tool-backed with DOI provenance."),
            evidence=["curated_e3_ligands.csv", "curated_warheads.csv", "curated_linkers.csv"]))
        stages.append(EvidenceStage(
            step="ternary_feasibility", label="missing", summary=(
                "Ternary feasibility is conditional on a designed PROTAC with explicit attachment vectors; "
                "the plan/design stage does not emit coordinates (score-level feasibility only; "
                "predicted-structure DockQ NOT_VALIDATED)."),
            evidence=[]))

        # 6 validation proposal (pending protocol; no results)
        stages.append(EvidenceStage(
            step="validation", label="proposed", summary=(
                "Proposed validation (PENDING, not performed): degradation readout (HiBiT/western) with "
                "measured dose response (>=8 points incl. hook regime) and time course (0.5/2/6/24 h); "
                "E3-dependence control and proteasome control (MG-132); dose-matched negative-control "
                "compound + vehicle."),
            evidence=[]))

        abstain = any(s.label == "missing" and s.step == "e3_evidence" for s in stages) and u.e3.mode != "explicit"
        status = "plan_with_limitation" if limitations else "plan_ready"
        return PlanDocument(understanding=u, interpretation_line=interpretation, stages=stages,
                            limitations=limitations, status=status, abstain_e3_recommendation=abstain,
                            provenance=[f"resolver={t.resolver_source}", f"match_type={t.match_type}",
                                        f"url={t.source_url or '-'}"])


# ----------------------------------------------------------------------
def _curated_record(symbol: str) -> Optional[dict]:
    import csv
    path = os.path.join(ROOT, "protacxtend", "data", "curated_targets.csv")
    if not os.path.exists(path):
        return None
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            if (row.get("gene_symbol") or "").strip().upper() == symbol.upper():
                return {"aliases": [a.strip() for a in (row.get("synonyms") or "").split("|") if a.strip()],
                        "structures": [s.strip() for s in (row.get("structures") or "").split("|") if s.strip()],
                        "known_binder_count": (row.get("known_binder_count") or "").strip()}
    return None


def _target_e3_precedent(symbol: str) -> dict:
    import csv
    path = os.path.join(ROOT, "protacxtend", "modules", "cell_context_selector", "data", "context_joined.csv")
    pairs: dict[str, dict] = {}
    if not os.path.exists(path):
        return {"pairs": {}, "total": 0, "source": ""}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            tgt = (row.get("target") or "").strip().upper()
            e3g = (row.get("e3_gene") or row.get("e3") or "").strip().upper()
            doi = (row.get("doi") or "").strip()
            if tgt == symbol.upper() and e3g:
                cur = pairs.setdefault(e3g, {"n": 0, "dois": []})
                cur["n"] += 1
                if doi and doi not in cur["dois"]:
                    cur["dois"].append(doi)
    return {"pairs": pairs, "total": sum(v["n"] for v in pairs.values()),
            "source": "protacxtend/modules/cell_context_selector/data/context_joined.csv (measured rows)"}


def _e3_library() -> tuple[list[str], int, int]:
    import csv
    path = os.path.join(ROOT, "protacxtend", "data", "curated_e3_ligands.csv")
    if not os.path.exists(path):
        return [], 0, 0
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    non_demo = [r for r in rows if "demo" not in (r.get("source") or "")]
    families = sorted({(r.get("e3_ligase") or "").strip() for r in non_demo if r.get("e3_ligase")})
    return families, len(non_demo), len(non_demo)
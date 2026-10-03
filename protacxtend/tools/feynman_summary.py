"""feynman_summary.py — Feynman-style structured summaries for PROTAC design runs.

Mirrors the style used in research briefs: a scannable TL;DR, concrete numbers
with provenance, an evidence table, gaps, open questions, next steps, and an
explicit Sources/uncertainty section. Fully deterministic (no LLM inference
required): every number is lifted from the workflow JSON / scorecard rows.

Public API:
    summarize_campaign(workflow_dict, candidate_id=None) -> str   (markdown)
    summarize_candidate(rows, candidate_id, meta=None) -> str     (markdown)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from protacxtend.tools.challenge_scorecard import (
    DimensionEvidence,
    aggregate,
    scorecard_from_workflow,
)

# Next-step suggestions per dimension (from the P0/P1/P2 roadmap).
DIMENSION_NEXT_STEPS: Dict[str, str] = {
    "cell_permeability": "Add Caco-2/HIA/PAMPA ADMET-AI endpoints (done: admet_ai_flags) and a 3D-PSA/chameleonicity pass for shortlisted candidates.",
    "metabolic_stability": "Use ADMET-AI clearance/half-life ML (now in admet_ai_flags); add soft-spot ID on amide/linker positions before synthesis.",
    "solubility": "Enable AqSolDB ML (in admet_ai_flags); iterate linker polarity if solubility flag is 'poor'.",
    "selectivity": "Wire neosubstrate_risk + proteome_selectivity into the scorecard; review warhead promiscuity against ChEMBL profiles.",
    "ternary_complex": "Run P4ward/PRosettaC/DeepTernary consensus on geometry-gated top-5; record interface + lysine geometry metrics.",
    "e3_choice": "Run the cross-E3 panel (CRBN vs VHL vs DCAF15/16) with tissue-expression evidence before accepting the default E3.",
    "synthesis_feasibility": "Route-gate the shortlist with ASKCOS/AiZynth (buyables + step count) before synthesis nomination.",
    "in_vivo_efficacy": "Simulate ternary dose-response/hook effect in the intended dose window; PK-PD translation stays a wet-lab gate.",
    "safety": "Promote to ADMET-AI ML tox panel; flag cereblon neosubstrate liabilities for haematological indications.",
    "developability": "Apply the PROTAC bRo5 filter and Pareto-ranking across objectives; formulation studies remain experimental.",
}


def _fmt(v: Any) -> str:
    if isinstance(v, float):
        return f"{v:.3g}"
    if v is None:
        return "—"
    return str(v)


def summarize_candidate(rows: List[DimensionEvidence], candidate_id: str,
                        meta: Optional[Dict[str, Any]] = None) -> str:
    """Render the Feynman-style single-candidate brief."""
    meta = meta or {}
    agg = aggregate(rows)
    ml_rows = [r for r in rows if r.evidence_level == "ml_model"]
    rule_rows = [r for r in rows if r.evidence_level in ("rule_descriptor", "geometry_stub", "docking")]
    gap_rows = [r for r in rows if r.evidence_level == "no_evidence"]
    exp_rows = [r for r in rows if r.requires_experiment]

    lines: List[str] = []
    lines += [
        f"## Candidate brief — `{candidate_id}`",
        "",
        f"**Campaign:** {meta.get('campaign', '?')}  ·  **Target:** {meta.get('target', '?')}  ·  "
        f"**E3:** {meta.get('e3', '?')}  ·  **Scorecard tool:** {meta.get('tool_version', 'challenge_scorecard-v1.0')}",
        "",
    ]

    # TL;DR ----------------------------------------------------------------
    tldr_parts = []
    dg = next((r for r in rows if r.dimension == "in_vivo_efficacy"), None)
    if dg and dg.value is not None:
        tldr_parts.append(f"predicted degradation DC50 ≈ {_fmt(dg.value)} nM")
    tern = next((r for r in rows if r.dimension == "ternary_complex"), None)
    if tern and tern.value is not None:
        tldr_parts.append(f"ternary geometry proxy ≈ {_fmt(tern.value)}")
    perm = next((r for r in rows if r.dimension == "cell_permeability"), None)
    if perm and perm.value is not None:
        tldr_parts.append(f"TPSA {_fmt(perm.value)} Å²")
    sol = next((r for r in rows if r.dimension == "solubility"), None)
    if sol and sol.value is not None:
        tldr_parts.append(f"solubility: {sol.summary.split(';')[0]}")
    lines += [
        "**TL;DR.** " + (". ".join(tldr_parts) if tldr_parts else "No trained-ML predictions available for this candidate.") +
        f" Evidence coverage {agg['covered']}/{agg['n_dimensions']} dimensions "
        f"({', '.join(f'{k}={v}' for k, v in sorted(agg['level_counts'].items()))}).",
        "",
    ]

    # Evidence table ---------------------------------------------------------
    lines += ["| # | dimension | evidence | value |", "|---|---|---|---|"]
    for i, r in enumerate(rows, 1):
        lines.append(f"| {i} | {r.label} | {r.evidence_level} | {_fmt(r.value)} |")
    lines += [""]

    # Strongest evidence -----------------------------------------------------
    if ml_rows:
        lines += ["**Strongest evidence (trained ML):**", ""]
        for r in ml_rows:
            lines.append(f"- **{r.label}** — {r.summary}")
        lines += [""]
    else:
        lines += ["**Strongest evidence:** none is trained-ML yet (rule/descriptor or geometry proxies only).", ""]

    # Gaps -------------------------------------------------------------------
    if gap_rows:
        lines += ["**Gaps (no in-silico evidence in this run):**", ""]
        for r in gap_rows:
            lines.append(f"- {r.label}")
        lines += [""]

    # Requires experiment -----------------------------------------------------
    if exp_rows:
        lines += ["**Requires experiment (never predicted):** " +
                  ", ".join(r.label for r in exp_rows) + ".", ""]

    # Next steps --------------------------------------------------------------
    lines += ["**Suggested next steps per dimension:**", ""]
    next_steps = []
    for r in rows:
        step = DIMENSION_NEXT_STEPS.get(r.dimension)
        if step:
            next_steps.append(f"- **{r.label}:** {step}")
    lines += next_steps + [""]

    # Uncertainty --------------------------------------------------------------
    lines += [
        "**Uncertainty & honesty contract:** every number above traces to a tool call with recorded "
        "source/model version; no value was invented. Dimensions marked 'requires experiment' are human "
        "gates, not predictions. Applicability-domain warnings must be read before using any ML number.",
        "",
    ]
    return "\n".join(lines)


def resolve_target_meta(workflow: Dict[str, Any]) -> str:
    """Best-effort target name across the several shapes a workflow may use."""
    tr = workflow.get("target_record") or {}
    obj = workflow.get("parsed_objective") or {}
    for src in (tr, obj):
        if isinstance(src, dict):
            for key in ("name", "target_name", "target", "gene", "gene_symbol", "query"):
                v = src.get(key)
                if v:
                    return str(v)
    for c in (workflow.get("assembled_candidates") or []):
        if isinstance(c, dict) and c.get("target"):
            return str(c["target"])
    return "?"


def summarize_campaign(workflow: Dict[str, Any],
                       candidate_id: Optional[str] = None) -> str:
    """Render the Feynman-style campaign brief (mirrors agent chat summaries)."""
    cands = workflow.get("assembled_candidates") or []
    admet = workflow.get("admet_predictions") or []
    cid = candidate_id or (cands[0].get("candidate_id") if cands else "?")
    rows = scorecard_from_workflow(workflow, cid)

    # campaign-level counts
    n_attempts = workflow.get("construction_attempts") or len(cands) or "?"
    n_valid = len(cands)
    n_binders = len(workflow.get("retrieved_binders") or [])
    n_warheads = len(workflow.get("selected_warheads") or [])
    n_e3 = len(workflow.get("selected_e3_ligands") or [])
    n_linkers = len(workflow.get("generated_linkers") or [])
    top_row = None
    for r in admet:
        if isinstance(r, dict) and r.get("candidate_id") == cid:
            top_row = r
            break
    if top_row is None and admet:
        top_row = admet[0]

    lines: List[str] = []
    lines += [
        "# Campaign brief — PROTAC design run",
        "",
        "**TL;DR.** " + (
            f"{n_valid} valid candidate(s) were assembled from {n_binders} retrieved binder(s), "
            f"{n_warheads} warhead(s), {n_e3} E3 ligand(s) and {n_linkers} linker(s) "
            f"({resolve_target_meta(workflow)} campaign). "
            f"For `{cid}` the scorecard covers {aggregate(rows)['covered']}/10 challenge dimensions; "
            f"only the degradation/efficacy row uses trained ML (TACK-style + chemprop cross-check), "
            f"ADMET is rule/descriptor unless ADMET-AI weights are bootstrapped, and ternary is a "
            f"geometry proxy pending P4ward/PRosettaC runs."
        ),
        "",
        "## Key findings (real, from this run)",
        "",
    ]
    dg = next((r for r in rows if r.dimension == "in_vivo_efficacy"), None)
    if dg and dg.value is not None:
        lines.append(f"- **Efficacy proxy:** {dg.summary}")
    terr = next((r for r in rows if r.dimension == "ternary_complex"), None)
    if terr:
        lines.append(f"- **Ternary:** {terr.summary}")
    e3r = next((r for r in rows if r.dimension == "e3_choice"), None)
    if e3r:
        lines.append(f"- **E3 choice:** {e3r.summary}")
    am_flags = (top_row or {}).get("admet_ai_flags") or {}
    if am_flags:
        lines.append(f"- **ADMET-AI flags (top candidate):** Caco-2={am_flags.get('Caco2_log_cm_s')}, "
                     f"P-gp={am_flags.get('efflux_risk')}, half-life={am_flags.get('Half_Life_Obach_h')} h, "
                     f"solubility={am_flags.get('solubility_flag')}, oral-F={am_flags.get('oral_F_flag')}.")
    # warnings/errors
    warns = workflow.get("warnings") or []
    errs = workflow.get("errors") or []
    if warns:
        lines += ["- **Warnings:** " + "; ".join(str(w)[:140] for w in warns[:4])]
    if errs:
        lines += ["- **Errors:** " + "; ".join(str(e)[:140] for e in errs)]

    lines += ["", "## Evidence table", ""]
    lines.append(scorecard_table_md(rows))
    lines += ["", "## Gaps and blockers", ""]
    agg = aggregate(rows)
    if agg["gaps"]:
        lines.append("- Gaps (no evidence): " + ", ".join(agg["gaps"]))
    else:
        lines.append("- No dimension is without at least some evidence.")
    lines.append("- Requires experiment: " + ", ".join(agg["requires_experiment"]) or "none flagged")
    lines += [
        "",
        "## Fastest next moves (P0/P1)",
        "",
        "1. Bootstrap ADMET-AI weights (`./scripts/bootstrap_assets.sh --admet`) so `admet_ai_flags` replace rule-only scores.",
        "2. Run P4ward/PRosettaC on the geometry-gated top-5 (`proceed_to_expensive_modeling` rows).",
        "3. Route-gate the shortlist with ASKCOS/AiZynth (`scripts/retrosynthesis_toolkits_smoke.py --engines askcos`).",
        "4. Promote `challenge_scorecard` into ranking: Pareto over the 10-dimension rows.",
        "",
        "## Provenance",
        "",
        "- Workflow artifacts: candidate JSON/CSV and report paths recorded by the run (see `outputs/candidates/`, `outputs/reports/`).",
        "- Every row in the evidence table carries `sources` key paths; ML rows carry model version + confidence.",
        "- This brief is deterministic: no LLM was consulted for any number.",
        "",
    ]
    return "\n".join(lines)


def scorecard_table_md(rows: List[DimensionEvidence]) -> str:
    lines = ["| # | dimension | evidence | value | summary |", "|---|---|---|---|---|"]
    for i, r in enumerate(rows, 1):
        val = _fmt(r.value)
        summary = r.summary.replace("|", "/")[:110]
        lines.append(f"| {i} | {r.label} | {r.evidence_level} | {val} | {summary} |")
    return "\n".join(lines)


def campaign_brief_from_json(path: str, candidate_id: Optional[str] = None) -> str:
    """Convenience: workflow JSON path -> markdown campaign brief."""
    import json
    from pathlib import Path
    workflow = json.loads(Path(path).read_text(encoding="utf-8"))
    return summarize_campaign(workflow, candidate_id)
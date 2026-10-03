"""Render the user-facing run page from a CanonicalRunRecord.

The page never shows a blank ``0.00`` for an absent score, never shows a
candidate card built only from hypothetical attachment markers, and always
shows the scientific status banner (including a loud UNVERIFIED state).
"""

from __future__ import annotations

import html
from typing import Any

from .records import CanonicalRunRecord
from .explanations import HOOK_EFFECT_EXPLANATION, MZ1_ATTRIBUTION

_STATUS_COLOR = {
    "VALID DESIGN": "#1f9d55",
    "DESIGN BRIEF ONLY": "#b7791f",
    "INVALID RUN": "#c53030",
    "ABSTAINED": "#2b6cb0",
}

_STAGE_COLOR = {
    "completed": "#1f9d55", "warning": "#b7791f",
    "failed": "#c53030", "running": "#2b6cb0", "queued": "#718096",
}


def _e(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def _para_for_stage(stage: dict[str, Any]) -> str:
    """One short technical sentence per stage."""
    name = stage.get("stage", "")
    summary = stage.get("summary", "")
    templates = {
        "parse_intent": "Parsed the request into a protein-of-interest and E3 role, preserving the original text; malformed tokens block the run.",
        "resolve_target": "Resolved the target to a reviewed UniProt identity from the curated table and asserted the gene symbol.",
        "resolve_e3": "Resolved the E3 recruiter to a reviewed UniProt identity; roles are kept separate from the target.",
        "retrieve_binders": "Counted retrieved binders and rejected any without structure, identity or matching target.",
        "select_warhead": "Selected a structure-backed warhead and required an explicit atom-mapped attachment vector.",
        "select_e3_ligand": "Selected a structure-backed E3 recruiter and required an explicit attachment vector.",
        "select_linker": "Selected a linker carrying both attachment vectors required for assembly.",
        "construct": "Assembled warhead + linker + E3 ligand with RDKit atom-map zipping (not string concatenation) and sanitized the product.",
        "validate_product": "Compared the assembled product against the curated source structure by InChIKey.",
        "predict": "Reported predictions with an explicit kind; unavailable endpoints are marked unavailable rather than substituted.",
        "rank": "Applied ranking or reported a single reference candidate without inventing a comparison.",
        "report": "Assembled the canonical run record and checked identity/count consistency across artifacts.",
    }
    return templates.get(name, name.replace("_", " ").capitalize()) + f" — {_e(summary)}"


def render_run_page(record: CanonicalRunRecord) -> str:
    ident = record.identity_summary()
    status = record.status
    color = _STATUS_COLOR.get(status, "#4a5568")

    # ── banner + header ──
    parts: list[str] = []
    parts.append(f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>PROTACXtend run {_e(record.run_id)}</title>
<style>
 body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;margin:0;background:#0b1338;color:#e8ebff}}
 .wrap{{max-width:1040px;margin:0 auto;padding:24px}}
 h1{{font-size:20px;margin:0 0 4px}} h2{{font-size:15px;margin:26px 0 8px;color:#a9b2ff;text-transform:uppercase;letter-spacing:.06em}}
 .banner{{background:{color};color:#fff;padding:12px 16px;border-radius:10px;font-weight:700;margin:14px 0}}
 .grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px}} .card{{background:#141c4a;border:1px solid #26306b;border-radius:10px;padding:12px 14px}}
 .kv{{display:flex;justify-content:space-between;gap:12px;padding:3px 0;border-bottom:1px dashed #26306b}}
 .muted{{color:#98a2c7}} code{{background:#0e153c;padding:1px 5px;border-radius:4px;word-break:break-all}}
 table{{width:100%;border-collapse:collapse;font-size:13px}} th,td{{text-align:left;padding:6px 8px;border-bottom:1px solid #26306b;vertical-align:top}}
 .pill{{display:inline-block;padding:1px 8px;border-radius:999px;font-size:11px;font-weight:700}}
 .stage{{border-left:3px solid #26306b;padding:6px 10px;margin:6px 0;background:#101740;border-radius:0 8px 8px 0}}
 .unverified{{border:2px dashed #b7791f;background:#2a2410;color:#f6e05e;padding:10px 14px;border-radius:10px;margin:12px 0;font-weight:700}}
 a{{color:#8ab4ff}} .funnel span{{display:inline-block;margin:2px 10px 2px 0}}
</style></head><body><div class="wrap">""")

    parts.append(f"<h1>PROTACXtend run</h1><div class='muted'>run_id <code>{_e(record.run_id)}</code> · {_e(record.created_at)} · schema {_e(record.schema_version)}</div>")
    parts.append(f"<div class='banner'>{_e(record.classification)} — {_e(record.status_reason)}</div>")

    # three independent gates, never collapsed into one boolean
    def _gate(label: str, value: bool) -> str:
        col = "#1f9d55" if value else "#c53030"
        return (f"<span class='pill' style='background:{col};color:#fff'>{_e(label)}: "
                f"{'true' if value else 'false'}</span> ")
    parts.append("<div class='card'>"
                 + _gate("structure_valid", record.structure_valid)
                 + _gate("evidence_sufficient", record.evidence_sufficient)
                 + _gate("prediction_available", record.prediction_available)
                 + "</div>")

    if not record.candidates or not any(c.valid for c in record.candidates):
        parts.append("<div class='unverified'>UNVERIFIED: no validated PROTAC candidate was produced. "
                     "Downstream degradation/design claims are not supported.</div>")

    # ── question + identities ──
    parts.append("<h2>Question &amp; resolved roles</h2><div class='grid'>")
    parts.append(f"<div class='card'><div class='kv'><span>original text</span><code>{_e(record.request.raw_request)}</code></div>"
                 f"<div class='kv'><span>parsed target</span><b>{_e(record.request.target or '(none)')}</b></div>"
                 f"<div class='kv'><span>parsed E3</span><b>{_e(record.request.e3_ligase or '(none)')}</b></div>"
                 f"<div class='kv'><span>malformed tokens</span><span>{_e(record.request.malformed_tokens)}</span></div>"
                 f"<div class='kv'><span>clarification</span><span>{_e(record.request.clarification_question or '—')}</span></div></div>")
    cand = next((c for c in record.candidates if c.valid), None)
    parts.append(f"<div class='card'><div class='kv'><span>target</span><b>{_e(ident['target'])}</b></div>"
                 f"<div class='kv'><span>target UniProt</span><code>{_e(ident['target_uniprot'])}</code></div>"
                 f"<div class='kv'><span>E3</span><b>{_e(ident['e3'])}</b></div>"
                 f"<div class='kv'><span>E3 UniProt</span><code>{_e(ident['e3_uniprot'])}</code></div></div>")
    parts.append("</div>")

    # ── stages ──
    parts.append("<h2>Stages</h2>")
    for s in record.stages:
        sc = _STAGE_COLOR.get(s.get("status", ""), "#718096")
        parts.append(
            f"<div class='stage'><span class='pill' style='background:{sc};color:#fff'>{_e(s.get('status'))}</span> "
            f"<b>{_e(s.get('stage'))}</b> <span class='muted'>· {_e(s.get('elapsed_s'))}s</span>"
            f"<div>{_para_for_stage(s)}</div></div>")

    # ── funnel ──
    parts.append("<h2>Candidate funnel</h2><div class='card funnel'>")
    for k, v in record.funnel.model_dump().items():
        parts.append(f"<span><span class='muted'>{_e(k)}</span> <b>{_e(v)}</b></span>")
    parts.append("</div>")
    if record.consistency_notes:
        parts.append("<h2>Consistency checks</h2><div class='card'>"
                     + "".join(f"<div>⚠ {_e(n)}</div>" for n in record.consistency_notes) + "</div>")

    # ── candidate card (only when a real product exists) ──
    parts.append("<h2>Candidate</h2>")
    if cand is None:
        parts.append("<div class='card muted'>No candidate card — no fully assembled, validated product.</div>")
    else:
        score = cand.scores.get("final_priority_score")
        score_line = (f"{score} <span class='muted'>(heuristic; not calibrated)</span>"
                      if score is not None else "<span class='muted'>not scored</span>")
        parts.append(f"<div class='card'><div class='kv'><span>candidate_id</span><code>{_e(cand.candidate_id)}</code></div>"
                     f"<div class='kv'><span>valid</span><b>{_e(cand.valid)}</b></div>"
                     f"<div class='kv'><span>formula</span>{_e(cand.formula)} ({_e(cand.mw)} Da)</div>"
                     f"<div class='kv'><span>InChIKey</span><code>{_e(cand.inchikey)}</code></div>"
                     f"<div class='kv'><span>SMILES</span><code>{_e(cand.canonical_smiles)}</code></div>"
                     f"<div class='kv'><span>final_priority_score</span>{score_line}</div></div>")

    # ── predictions, separated by kind ──
    parts.append("<h2>Predictions (measured / model / heuristic)</h2><div class='card'><table>"
                 "<tr><th>endpoint</th><th>kind</th><th>value</th><th>available</th><th>reason</th></tr>")
    if not record.predictions:
        parts.append("<tr><td colspan='5' class='muted'>none</td></tr>")
    for p in record.predictions:
        value = "—" if p.value is None else f"{p.value} {p.unit}"
        parts.append(f"<tr><td>{_e(p.endpoint)}</td><td>{_e(p.kind)}</td><td>{_e(value)}</td>"
                     f"<td>{_e(p.available)}</td><td class='muted'>{_e(p.reason)}</td></tr>")
    parts.append("</table></div>")

    # ── evidence ──
    parts.append("<h2>Evidence</h2><div class='card'><table>"
                 "<tr><th>kind</th><th>claim</th><th>source</th><th>state</th></tr>")
    if not record.evidence:
        parts.append("<tr><td colspan='4' class='muted'>none</td></tr>")
    for ev in record.evidence:
        src = _e(ev.source)
        if str(ev.source).startswith("http"):
            src = f"<a href='{_e(ev.source)}'>{_e(ev.source)}</a>"
        parts.append(f"<tr><td>{_e(ev.evidence_kind)}</td><td>{_e(ev.claim)}</td>"
                     f"<td>{src}</td><td>{_e(ev.validation_state)}</td></tr>")
    parts.append("</table></div>")

    # ── artifacts ──
    parts.append("<h2>Intermediate files</h2><div class='card'><table>"
                 "<tr><th>file</th><th>kind</th><th>bytes</th><th>sha256</th></tr>")
    for a in record.artifacts:
        parts.append(f"<tr><td><code>{_e(a.path)}</code></td><td>{_e(a.kind)}</td>"
                     f"<td>{_e(a.bytes)}</td><td class='muted'>{_e(a.sha256[:16])}…</td></tr>")
    parts.append("</table></div>")

    # ── answer / uncertainty / next ──
    parts.append("<h2>Answer, uncertainty, next experiment</h2><div class='card'>")
    parts.append(f"<p><b>Supported answer:</b> {_e(record.status_reason)}</p>")
    parts.append(f"<p><b>Uncertainty:</b> measured DC50/Dmax are literature values (PROTAC-DB), not "
                 f"predictions from this system; model/heuristic predictions are unavailable "
                 f"because no calibrated model ran. Identity of components is source-backed; "
                 f"single reference molecule, no comparative ranking.</p>")
    parts.append(f"<p><b>Next experiment:</b> {_e(record.next_experiment or '(none)')}</p>")
    if record.warnings:
        parts.append("<p><b>Warnings:</b></p><ul>"
                     + "".join(f"<li>{_e(w)}</li>" for w in record.warnings) + "</ul>")
    parts.append("</div>")

    # ── corrected knowledge notes ──
    parts.append("<h2>Knowledge notes (corrected, source-backed)</h2><div class='card'>")
    parts.append(f"<p><b>MZ1 identity &amp; attribution.</b> {_e(MZ1_ATTRIBUTION)}</p>")
    parts.append(f"<p><b>Hook-effect mechanism.</b> {_e(HOOK_EFFECT_EXPLANATION)}</p>")
    parts.append("</div>")

    parts.append("</div></body></html>")
    return "".join(parts)

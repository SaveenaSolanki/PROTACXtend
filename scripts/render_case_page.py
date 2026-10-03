#!/usr/bin/env python
"""Render a run page for one frozen benchmark case result.

Produces a self-contained HTML page (same visual language as the controlled
run page) from ``benchmark_results/validation_gap_v1/cases/<id>.json``.

Correctness is always shown as PENDING_INDEPENDENT_GOLD and the provenance is
labelled as the complete structured agent workflow (not the contract runner).

Usage::
    python scripts/render_case_page.py DESIGN-04
"""
from __future__ import annotations

import html
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_DIR = os.environ.get("VALIDATION_DIR", "benchmark_results/validation_gap_v1")
CASES_DIR = ROOT / _DEFAULT_DIR / "cases"
BENCH_CASES = ROOT / "benchmark" / "cases"


def _apply_argv_dir() -> None:
    """Allow: render_case_page.py --dir benchmark_results/validation_gap_v2 ID..."""
    global CASES_DIR
    if "--dir" in sys.argv:
        i = sys.argv.index("--dir")
        CASES_DIR = ROOT / sys.argv[i + 1] / "cases"
        del sys.argv[i:i + 2]


_apply_argv_dir()


def _e(v) -> str:
    return html.escape(str(v if v is not None else ""))


_CSS = """
body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;margin:0;background:#0b1338;color:#e8ebff}
.wrap{max-width:1040px;margin:0 auto;padding:24px}
h1{font-size:20px;margin:0 0 4px} h2{font-size:15px;margin:26px 0 8px;color:#a9b2ff;text-transform:uppercase;letter-spacing:.06em}
.banner{background:#b7791f;color:#fff;padding:12px 16px;border-radius:10px;font-weight:700;margin:14px 0}
.verified{background:#1f9d55}
.card{background:#141c4a;border:1px solid #26306b;border-radius:10px;padding:12px 14px;margin:8px 0}
.kv{display:flex;justify-content:space-between;gap:12px;padding:3px 0;border-bottom:1px dashed #26306b}
.muted{color:#98a2c7} code{background:#0e153c;padding:1px 5px;border-radius:4px;word-break:break-all}
table{width:100%;border-collapse:collapse;font-size:13px} th,td{text-align:left;padding:6px 8px;border-bottom:1px solid #26306b;vertical-align:top}
.pill{display:inline-block;padding:1px 8px;border-radius:999px;font-size:11px;font-weight:700;background:#2b6cb0;color:#fff}
.unverified{border:2px dashed #b7791f;background:#2a2410;color:#f6e05e;padding:10px 14px;border-radius:10px;margin:12px 0;font-weight:700}
"""


def render(case_id: str) -> Path:
    result = json.loads((CASES_DIR / f"{case_id}.json").read_text())
    case = json.loads((BENCH_CASES / f"{case_id}.json").read_text())
    state = str(result.get("scientific_state") or "")
    n_verified = int(result.get("n_verified_candidates") or 0)
    verified_smiles = result.get("verified_candidate_smiles") or []
    verified = state == "valid_candidate" and n_verified > 0

    out = [f"""<!doctype html><html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>PROTACXtend benchmark case {_e(case_id)}</title><style>{_CSS}</style></head>
<body><div class="wrap">"""]
    out.append(f"<h1>PROTACXtend benchmark case {_e(case_id)}</h1>"
               f"<div class='muted'>{_e(case.get('capability'))} · provenance: "
               f"<b>complete structured agent workflow</b> (not the controlled contract runner)</div>")
    banner = "verified reference candidate" if verified else _e(state or result.get("outcome"))
    cls = "banner verified" if verified else "banner"
    out.append(f"<div class='{cls}'>{banner} — correctness: PENDING_INDEPENDENT_GOLD "
               f"(benchmark_score: null)</div>")

    out.append("<h2>Question &amp; resolved identities</h2><div class='card'>"
               f"<div class='kv'><span>supplied question</span><span>{_e(case.get('scientific_question'))}</span></div>"
               f"<div class='kv'><span>resolved target</span><b>{_e((result.get('resolved_target') or {}).get('target_name') or '(none)')}</b>"
               f" <code>{_e((result.get('resolved_target') or {}).get('uniprot_id') or '')}</code></div>"
               f"<div class='kv'><span>resolved E3</span><b>{_e(result.get('resolved_e3') or '(none)')}</b></div>"
               f"<div class='kv'><span>stage status</span><span>{_e(result.get('stage_ledger') and 'see ledger below')}</span></div>"
               "</div>")

    out.append("<h2>Stage ledger</h2><div class='card'><table><tr><th>stage</th><th>input</th><th>output</th><th>status</th><th>reason</th></tr>")
    for s in (result.get("stage_ledger") or []):
        out.append(f"<tr><td>{_e(s.get('stage'))}</td><td>{_e(s.get('input'))}</td>"
                   f"<td>{_e(s.get('output'))}</td><td>{_e(s.get('status'))}</td>"
                   f"<td class='muted'>{_e(str(s.get('reason',''))[:160])}</td></tr>")
    out.append("</table></div>")

    out.append("<h2>Evidence</h2><div class='card'><table><tr><th>kind</th><th>summary</th><th>source</th></tr>")
    for ev in (result.get("evidence") or []):
        out.append(f"<tr><td>{_e(ev.get('kind'))}</td><td>{_e(ev.get('summary'))}</td>"
                   f"<td class='muted'>{_e(ev.get('source'))}</td></tr>")
    out.append("</table></div>")

    # Candidate card only when a real, source-backed product exists
    out.append("<h2>Candidate</h2>")
    if not verified_smiles:
        out.append("<div class='unverified'>UNVERIFIED: no source-backed, fully assembled PROTAC "
                   "candidate was produced. No degradation or design claim is supported.</div>")
        out.append("<div class='card muted'>No candidate card — no fully assembled, source-backed product.</div>")
    else:
        out.append("<div class='card'>"
                   "<div class='kv'><span>classification</span><b>known-compound-derived reference "
                   "(dBET1 warhead + CRBN ligand)</b></div>"
                   "<div class='kv'><span>note</span><span>stereoisomers of the reference molecule; "
                   "NOT a novel design and NOT evidence of degradation</span></div>")
        for i, smi in enumerate(verified_smiles, 1):
            out.append(f"<div class='kv'><span>reference #{i}</span><code>{_e(smi)}</code></div>")
        out.append("</div>")

    if n_verified and int(result.get("n_candidates") or 0) > n_verified:
        out.append("<div class='unverified'>"
                   f"UNVERIFIED: {int(result.get('n_candidates')) - n_verified} additional candidate(s) are "
                   "design-brief / hypothetical only (no complete attachment-verified structure) and are "
                   "excluded from the reference set.</div>")

    out.append("<h2>Measured / predicted / heuristic</h2>")
    preds = result.get("predictions") or []
    if not preds:
        out.append("<div class='card'><div class='kv'><span>degradation prediction "
                   "(DC50/Dmax)</span><b>not available</b> — no calibrated model ran on this case "
                   "(not shown as 0.00)</div>"
                   "<div class='kv'><span>measured values</span><span>none provided by this case</span></div>"
                   "<div class='kv'><span>heuristic</span><span>not reported</span></div></div>")
    else:
        out.append("<div class='card'><table><tr><th>endpoint</th><th>kind</th><th>value</th><th>source</th></tr>")
        for p in preds:
            out.append(f"<tr><td>{_e(p.get('endpoint'))}</td><td>{_e(p.get('kind'))}</td>"
                       f"<td>{_e(p.get('value'))}</td><td>{_e(p.get('source_uri'))}</td></tr>")
        out.append("</table></div>")

    out.append("<h2>Answer, uncertainty, next experiment</h2><div class='card'>"
               f"<p><b>Answer:</b> {_e(result.get('answer'))}</p>"
               f"<p><b>Uncertainty:</b> {_e('; '.join(result.get('uncertainty') or []))}</p>"
               f"<p><b>Next experiment:</b> {_e(result.get('next_experiment') or '')}</p>"
               f"<p><b>Warnings:</b></p><ul>" +
               "".join(f"<li>{_e(w)}</li>" for w in (result.get("warnings") or [])) + "</ul></div>")

    out.append("</div></body></html>")
    dst = CASES_DIR / f"{case_id}_run_page.html"
    dst.write_text("".join(out))
    return dst


if __name__ == "__main__":
    for cid in (sys.argv[1:] or ["DESIGN-04"]):
        print("wrote", render(cid))

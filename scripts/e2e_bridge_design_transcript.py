"""E2E bridge transcript: Design a CRBN-recruiting PROTAC for BRD4.

Drives the REAL TUI bridge (handle_command "run") and renders the complete
user-visible transcript with stage timeline, intermediate files, candidate
evidence table and evidence gates, identifying exactly which stages executed
and which are UNEVALUATED.
"""
from __future__ import annotations

import json, os, time

os.environ.setdefault("PROTACXTEND_PLANNER_OFFLINE", "1")

import protacxtend.tui_bridge.server as server  # noqa: E402

OUT = "outputs/manuscript_strategy/challenge_audit"
os.makedirs(OUT, exist_ok=True)

REQUEST = "Design a CRBN-recruiting PROTAC for BRD4"
captured: list[dict] = []
server.emit = lambda p: captured.append(p)  # type: ignore[assignment]
t0 = time.time()
server.handle_command("run", {"request": REQUEST, "conversation_id": "e2e-brd4-crbn"})
elapsed = round(time.time() - t0, 1)

answers = [p for p in captured if p.get("type") == "research_answer"]
payload = answers[-1] if answers else {}

with open(os.path.join(OUT, "bridge_payload.json"), "w") as f:
    json.dump(payload, f, indent=1, default=str)

executed = payload.get("executed_stages") or []
unevaluated = payload.get("unevaluated_stages") or []
rows = payload.get("candidate_evidence_table") or []
gates = payload.get("evidence_gates") or {}
artifacts = payload.get("artifacts") or {}

md = [
    "# E2E bridge transcript — `" + REQUEST + "` (real TUI bridge, workflows.api, deterministic engine)",
    "",
    f"- date: 2026-09-25 · bridge run elapsed: {elapsed}s · status: {payload.get('status')}",
    f"- engine: {payload.get('engine')} · mode: {payload.get('mode')}",
    "",
    "## User-visible conversation",
    "",
    f"**user>** {REQUEST}",
    "**system>** (streaming progress events shown live in the TUI; final research_answer below)",
    "",
    "### Stage timeline (executed vs unevaluated)",
    "",
    "| stage | executed | status |",
    "|---|---|---|",
]
for s in (payload.get("stage_timeline") or []):
    md.append(f"| {s.get('stage')} | {s.get('executed')} | {s.get('status')} | {str(s.get('detail',''))[:80]} |")
md += [
    "",
    f"**Executed stages ({len(executed)}):** {', '.join(executed)}",
    f"**UNEVALUATED stages:** {', '.join(unevaluated)}",
    "",
    "## Evidence gates",
    "",
]
for gate, g in gates.items():
    md.append(f"- **{gate}**: {g.get('status')} — {g.get('limitation') or g.get('criterion')}")
md += [
    "",
    "## Candidate evidence table",
    "",
    "| id | canonical SMILES (trunc) | target | E3 | warhead | e3_ligand | linker | DC50 nM (predicted) | Dmax % | ADMET pen | rank |",
    "|---|---|---|---|---|---|---|---|---|---|---|",
]
for r in rows:
    md.append(f"| {r['candidate_id']} | {str(r.get('canonical_smiles'))[:34]} | {r['components'].get('target')} | "
              f"{r['components'].get('e3_ligase')} | {r['components'].get('warhead')[:24]} | "
              f"{r['components'].get('e3_ligand')[:24]} | {r['components'].get('linker')[:16]} | "
              f"{r['degradation'].get('predicted_dc50_nM')} | {r['degradation'].get('predicted_dmax_percent')} | "
              f"{r['admet'].get('overall_admet_penalty')} | {r['ranking'].get('rank')} |")
md += [
    "",
    "**Label:** degradation/ADMET = computational prediction/calculation; ternary coordinates and "
    "synthesis routes UNEVALUATED; nomination gated.",
    "",
    "## Intermediate files",
    "",
]
for k, v in artifacts.items():
    md.append(f"- `{k}`: {v}")
for k in ("stage_timeline", "candidate_evidence_json", "candidate_evidence_csv", "resume_state", "evidence_graph"):
    if k in payload:
        md.append(f"- `{k}`: {payload[k]}")
md.append("")
with open(os.path.join(OUT, "e2e_bridge_transcript.md"), "w") as f:
    f.write("\n".join(md))
print(f"wrote e2e_bridge_transcript.md; executed={executed} unevaluated={unevaluated} candidates={len(rows)}")
print(f"gates: { {k: v.get('status') for k, v in gates.items()} }")
"""Record request-understanding conversations (requirement 7 artifact).

Renders the exact /plan exchanges as a TUI-style transcript (the headless
equivalent of a screenshot) with parsed state, UniProt candidates,
clarification decisions, tools called, final responses and evidence
provenance. Writes transcript.md + conversations.jsonl under
outputs/manuscript_strategy/request_conversations/.
"""

from __future__ import annotations

import json, os

os.environ["PROTACXTEND_PLANNER_OFFLINE"] = "1"

from protacxtend.planning.planner import plan_request, reset_session, get_session  # noqa: E402
from protacxtend.request.corrections import get_conversation  # noqa: E402

OUT = "outputs/manuscript_strategy/request_conversations"
os.makedirs(OUT, exist_ok=True)

CONVERSATIONS = [
    ("efrg-egfr", [
        ("/plan EFRG protac", None),
        ("EGFR target of interest with suitable E3 ligase", None),
    ]),
    ("brd4-direct", [("/plan BRD4 protac", None)]),
    ("accession", [("/plan O60885 protac", None)]),
    ("alias", [("/plan HER1 protac", None)]),
    ("typo", [("/plan BDR4 protac", None), ("BRD4", None)]),
    ("ambiguous", [("/plan BRD protac", None)]),
    ("unknown", [("/plan ZZZZ9 protac", None)]),
    ("mutation", [("/plan KRAS G12C PROTAC with VHL", None)]),
    ("explicit-e3", [("/plan design a PROTAC for EGFR using CRBN", None)]),
    ("delegated-e3", [("/plan find a suitable E3 for a BRD4 PROTAC strategy", None)]),
    ("nonhuman", [("/plan BRD4 in mice", None)]),
]

log: list[dict] = []
md: list[str] = [
    "# PROTACxtend request-understanding conversations (2026-09-24)",
    "",
    "Headless transcript of the exact /plan exchanges (screenshot-equivalent).",
    "For each turn: parsed state, UniProt candidates, clarification decision,",
    "tools called, final response, evidence provenance.",
    "",
]

for conv_id, turns in CONVERSATIONS:
    reset_session(conv_id)
    md.append(f"## Conversation `{conv_id}`")
    md.append("")
    for text, _ in turns:
        res = plan_request(text, conversation_id=conv_id, offline=True)
        conv = get_conversation(conv_id)
        t = res.target
        target_info = (f"{t.symbol} [{t.uniprot_id or 'no-id'}] status={t.status} "
                       f"match={t.match_type} resolver={t.resolver_source}" if t else "none")
        md.append(f"### `{text}`")
        md.append("")
        md.append(f"- **Clarification decision:** {res.status}; question: {res.clarification_question or 'none'}")
        md.append(f"- **Target (tool-resolved):** {target_info}")
        if res.status == "clarification_needed":
            md.append(f"- **UniProt candidates:** {t.alternatives if t and t.alternatives else 'none listed'}")
        else:
            md.append(f"- **Interpretation:** {res.interpretation_line}")
            for s in res.evidence_steps:
                md.append(f"  - [{s.get('label', s['step'])}] {s['step']}: {s['summary'][:130]}")
            if res.limitations:
                md.append(f"- **Limitations:** {'; '.join(res.limitations)}")
            md.append(f"- **Provenance:** {res.provenance}")
            md.append(f"- **Tools called:** resolver={getattr(t, 'resolver_source', 'none') if t else 'none'}; "
                      f"evidence sources cited in stages above")
        md.append("")
        log.append({
            "conversation_id": conv_id,
            "text": text,
            "status": res.status,
            "question": res.clarification_question,
            "target": None if not t else {"symbol": t.symbol, "uniprot_id": t.uniprot_id,
                                          "status": t.status, "match_type": t.match_type,
                                          "resolver_source": t.resolver_source,
                                          "alternatives": t.alternatives},
            "interpretation": res.interpretation_line if res.status != "clarification_needed" else None,
            "evidence_steps": [{"step": s["step"], "label": s.get("label", s["step"]),
                                "summary": s["summary"], "evidence": s["evidence"]}
                               for s in res.evidence_steps],
            "provenance": res.provenance,
        })
    # state transition log for the correction conversation
    if conv_id == "efrg-egfr":
        conv = get_conversation(conv_id)
        md.append("### State transitions (before -> after)")
        for h in conv.history:
            md.append(f"- **event:** {h['event']}")
            md.append(f"  - before: {json.dumps(h['state_before'], default=str)[:220]}")
            md.append(f"  - after : {json.dumps(h['state_after'], default=str)[:220]}")
        md.append("")

with open(os.path.join(OUT, "transcript.md"), "w") as f:
    f.write("\n".join(md))
with open(os.path.join(OUT, "conversations.jsonl"), "w") as f:
    for rec in log:
        f.write(json.dumps(rec, default=str) + "\n")
print(f"wrote transcript.md ({len(md)} lines) + conversations.jsonl ({len(log)} records)")
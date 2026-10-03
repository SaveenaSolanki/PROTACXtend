"""Render the typed ExplanationAnswer for humans (TUI-friendliness: concise
default answer + expandable Why / Evidence / What could be wrong / Next
experiment). Provides a plain-language explanation and a technical explanation
of the same conclusion. Rendering never invents facts: everything printed
comes from the answer record."""

from __future__ import annotations

from protacxtend.explain.answer_record import ExplanationAnswer

_STATE_ICON = {"measured": "M", "computed": "C", "hypothesized": "H", "unavailable": "U"}


def concise(ans: ExplanationAnswer) -> str:
    lines = [
        f"[{ans.mode}] {ans.run_id} — render: {ans.render_status} · outcome: {ans.scientific_outcome}",
        "",
        ans.facts.direct_answer or "(no direct answer recorded)",
    ]
    if ans.design:
        d = ans.design
        lines.append("")
        if d.full_product:
            lines.append(f"product: {d.full_product}")
        if d.product_identity:
            lines.append(f"product InChIKey: {d.product_identity}")
        if d.outcome_class == "reference_reconstruction":
            lines.append("outcome: known reference reconstruction (not a novel candidate)")
        elif d.missing_input_brief:
            lines.append(f"outcome: design brief — {d.missing_input_brief}")
    if ans.citation_claim:
        lines.append("")
        lines.append(f"citation: {ans.citation_claim}")
    return "\n".join(lines) + "\n"


def _causal_chain_md(ans: ExplanationAnswer) -> str:
    chain = (ans.facts.mechanistic_interpretation or {}).get("causal_chain") or []
    if not chain:
        return "_(no causal chain recorded)_"
    rows = []
    for step in chain:
        ctx = f" ({step['measurement_context']})" if step.get("measurement_context") else ""
        rows.append(f"- [{_STATE_ICON.get(step['state'], '?')}] **{step['step']}** — {step['title']}: "
                    f"**{step['state']}{ctx}**; {step['detail']}")
    return "\n".join(rows)


def evidence_audit(ans: ExplanationAnswer) -> str:
    """Exact-evidence audit per causal-chain step: molecule, domain/isoform,
    assay, cell context, time, metric, unit, source record, and whether the
    value was measured in this run (vs taken from cited literature)."""
    chain = (ans.facts.mechanistic_interpretation or {}).get("causal_chain") or []
    lines = ["### Exact-evidence audit (per causal step)", ""]
    if not chain:
        lines.append("_(no causal chain recorded)_")
        return "\n".join(lines) + "\n"
    for step in chain:
        ev = step.get("exact_evidence") or {}
        in_run = step.get("measured_in_this_run")
        lines.append(f"- **{step['step']}** ({step['state']})"
                     + (" — **measured in this run**" if in_run else " — **not measured in this run (source-cited)**"))
        for key in ("molecule", "domain_isoform", "assay", "assay_record", "cell_context", "time",
                    "metric", "unit", "value", "quoted_row", "source_record", "note", "distinguish",
                    "alternative_record"):
            val = ev.get(key)
            if val:
                lines.append(f"    - {key}: {val}")
        if not ev:
            lines.append("    - (no exact-evidence record in this run)")
    return "\n".join(lines) + "\n"


def why(ans: ExplanationAnswer) -> str:
    lines = ["### Why", ""]
    lines.append(_causal_chain_md(ans))
    assumptions = (ans.facts.mechanistic_interpretation or {}).get("assumptions") or []
    if assumptions:
        lines.append("")
        lines.append("Assumptions:")
        lines.extend(f"- {a}" for a in assumptions)
    return "\n".join(lines) + "\n"


def evidence(ans: ExplanationAnswer) -> str:
    lines = ["### Evidence", ""]
    if not ans.facts.established_facts:
        lines.append("_(no persisted evidence records in this run)_")
    for f in ans.facts.established_facts:
        lines.append(f"- [{f.evidence_kind}] {f.claim}  \n  source: {f.source or 'n/a'}  \n"
                     f"  validation_state: {f.validation_state}  \n"
                     f"  evidence_refs: {', '.join(f.evidence_refs) or 'n/a'}  \n"
                     f"  persisted: {', '.join(f.artifact_paths) or 'n/a'}"
                     + (f"  \n  source_run: {f.source_run_id}" if f.source_run_id else ""))
    return "\n".join(lines) + "\n"


def what_could_be_wrong(ans: ExplanationAnswer) -> str:
    lines = ["### What could be wrong", ""]
    alts = ans.facts.alternative_explanations or []
    if not alts:
        alts = ["No alternative explanations recorded."]
    lines.extend(f"- {a}" for a in alts)
    if ans.facts.missing_links:
        lines.append("")
        lines.append("Missing links:")
        lines.extend(f"- {m}" for m in ans.facts.missing_links)
    return "\n".join(lines) + "\n"


def next_experiment(ans: ExplanationAnswer) -> str:
    lines = ["### Next experiment", ""]
    nex = ans.facts.next_discriminating_experiment or {}
    lines.append(f"- **Proposed**: {nex.get('title') or 'not recorded'}")
    lines.append(f"- **Distinguishes**: {', '.join(nex.get('distinguishes') or [])}")
    if nex.get("controls"):
        lines.append(f"- **Controls**: {', '.join(nex['controls'])}")
    lines.append(f"- **Status**: {nex.get('status', 'PENDING')} — {nex.get('note') or ''}")
    return "\n".join(lines) + "\n"


SECTIONS = (("Why", why), ("Evidence", evidence), ("What could be wrong", what_could_be_wrong),
            ("Next experiment", next_experiment))


def render_full(ans: ExplanationAnswer, *, technical: bool = False) -> str:
    """Expandable full explanation. plain-language by default; technical=True
    adds the same sections with record-level provenance and design block."""
    out = [f"# Explanation — {ans.run_id}", ""]
    out.append(f"- mode: {ans.mode} · render_status: {ans.render_status} · "
               f"scientific_outcome: {ans.scientific_outcome} · citation: {ans.citation_claim}")
    out.append("")
    out.append(concise(ans))
    for title, fn in SECTIONS:
        out.append("")
        out.append(fn(ans))
    if technical:
        out.append("")
        out.append(evidence_audit(ans))
    if technical and ans.design:
        d = ans.design
        out.append("")
        out.append("### Design (technical)")
        out.append(f"- target: {d.target or 'unresolved'} ({d.target_identity or 'n/a'})")
        out.append(f"- E3: {d.e3 or 'unresolved'} ({d.e3_identity or 'n/a'})")
        out.append(f"- outcome_class: {d.outcome_class}")
        if d.full_product:
            out.append(f"- full product SMILES: {d.full_product}")
        if d.product_identity:
            out.append(f"- product InChIKey: {d.product_identity}")
        if d.missing_input_brief:
            out.append(f"- missing-input brief: {d.missing_input_brief}")
        if d.funnel:
            out.append(f"- funnel: {d.funnel}")
        if d.component_provenance:
            out.append("- components:")
            for c in d.component_provenance:
                out.append(f"  - {c}")
        if d.attachment_provenance:
            out.append("- attachment provenance:")
            for a in d.attachment_provenance:
                out.append(f"  - {a}")
    out.append("")
    out.append("### Provenance")
    for k, v in (ans.provenance or {}).items():
        out.append(f"- {k}: {v}")
    return "\n".join(out) + "\n"


def render(ans: ExplanationAnswer) -> dict[str, str]:
    return {
        "concise": concise(ans),
        "plain": render_full(ans, technical=False),
        "technical": render_full(ans, technical=True),
    }
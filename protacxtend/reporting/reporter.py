"""Evidence-driven reporter: plain-language summary + technical report +
structured CSV tables, rendered from a run record (never from generic JSON
dump-to-markdown)."""

from __future__ import annotations

import csv, json, os
from typing import Any

from protacxtend.reporting.run_record import EvidenceRunRecord, ToolCallRecord


def _candidate_count(final_output: dict) -> int:
    return len(final_output.get("candidate_protacs") or [])


def plain_summary(rec: EvidenceRunRecord) -> str:
    """Short, plain-language result summary shown by default in CLI/frontend."""
    f = rec.final_output
    n_cand = _candidate_count(f)
    stop = (f.get("stopping_state") or "n/a")
    deg = f.get("degradation_prediction") or {}
    critic = f.get("critic") or {}
    lines = [
        f"Run {rec.run_id}: {rec.question}",
        f"- Status: {stop} | candidates: {n_cand} | degradation predictions: {deg.get('n_predictions', 0)} "
        f"(model={deg.get('model_versions') or 'none'})",
        f"- Critic: {critic.get('status', 'no critic')}; degradation fallback -> heuristic: "
        f"{str(deg.get('heuristic_fallback', False)).lower()}",
    ]
    if f.get("target_validation", {}).get("uniprot_id"):
        lines.append(f"- Target: {f.get('target')} ({f['target_validation']['uniprot_id']}) | "
                     f"E3: {f.get('recommended_e3') or f.get('e3_ligase')}")
    errs = rec.provenance.get("errors") or []
    if errs:
        lines.append(f"- Errors recorded: {len(errs)} (see technical report)")
    return "\n".join(lines) + "\n"


def technical_report(rec: EvidenceRunRecord) -> str:
    """Methods, numerical results with units, provenance, limitations,
    intermediate files, and every tool call. All numbers come from the record."""
    f = rec.final_output
    out = []
    out.append(f"# Technical report — run {rec.run_id}")
    out.append("")
    out.append(f"- Question: `{rec.question}`")
    out.append(f"- Engine: {rec.provenance.get('engine')} | mode: {rec.provenance.get('execution_mode')} "
               f"| protacxtend {rec.provenance.get('protacxtend_version')} | host: {rec.provenance.get('host')}")
    out.append(f"- Reproducibility hash: `{rec.reproducibility_hash}`")
    out.append("")
    out.append("## Inputs")
    out.append("```json")
    out.append(json.dumps(rec.inputs, indent=1, default=str)[:4000])
    out.append("```")
    out.append("")
    out.append("## Tool calls (name | version | elapsed_s | errors | sources)")
    out.append("")
    out.append("| tool | version | elapsed_s | error | source identifiers | artifact |")
    out.append("|---|---|---|---|---|---|")
    for tc in rec.tool_calls:
        out.append(f"| {tc.tool} | {tc.version} | {tc.elapsed_s if tc.elapsed_s is not None else 'n/a'} "
                   f"| {tc.error or ''} | {'; '.join(tc.source_identifiers[:4])} | {tc.output_artifact or ''} |")
    out.append("")
    out.append("## Numerical results")
    tv = f.get("target_validation") or {}
    deg = f.get("degradation_prediction") or {}
    adme = f.get("adme_risks") or []
    out.append("| quantity | value | unit | provenance |")
    out.append("|---|---|---|---|")
    out.append(f"| target | {f.get('target')} | — | UniProt {tv.get('uniprot_id', 'n/a')} |")
    n_wh = len(f.get("warheads") or [])
    n_lk = len(f.get("linker_hypotheses") or [])
    n_cand = _candidate_count(f)
    n_valid = _candidate_count(f)
    out.append(f"| warheads selected | {n_wh} | molecules | run record tool_calls[warhead_selection] |")
    out.append(f"| linker hypotheses | {n_lk} | linkers | run record tool_calls[linker_generation] |")
    out.append(f"| candidates (strategy) | {n_cand} | PROTACs | run record final_output.candidate_protacs |")
    out.append(f"| degradation predictions | {deg.get('n_predictions', 0)} | batch | model {deg.get('model_versions')} |")
    if deg.get("top_dc50"):
        out.append(f"| top predicted DC50 | {deg['top_dc50'][0]} | nM | predicted (computational) |")
    out.append("")
    out.append("> Units and labels: DC50/Dmax are model predictions, not measured. "
               "Docking scores are pose-recovery metrics, not affinity.")
    out.append("")
    out.append("## Limitations (recorded in run)")
    for lim in (rec.provenance.get("limitations") or []):
        out.append(f"- {lim}")
    for w in (rec.provenance.get("warnings") or [])[:8]:
        out.append(f"- warn: {w}")
    out.append("")
    out.append("## Intermediate files")
    for p in rec.artifact_paths:
        out.append(f"- {p}")
    out.append("")
    out.append("## Raw JSON")
    out.append(f"- Preserved at `{rec.raw_json_path}` (raw strategy) and `run.json` (this record).")
    return "\n".join(out) + "\n"


def write_csv_tables(rec: EvidenceRunRecord, out_dir: str) -> list[str]:
    """Structured CSV tables only where the data supports them."""
    os.makedirs(out_dir, exist_ok=True)
    written: list[str] = []

    # tool calls table
    tool_csv = os.path.join(out_dir, "tool_calls.csv")
    with open(tool_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["tool", "version", "elapsed_s", "error", "sources", "artifact"])
        for tc in rec.tool_calls:
            w.writerow([tc.tool, tc.version, tc.elapsed_s, tc.error or "",
                        "; ".join(tc.source_identifiers), tc.output_artifact or ""])
    written.append(tool_csv)

    # candidates table (only if candidates exist)
    cands = rec.final_output.get("candidate_protacs") or []
    if cands:
        cand_csv = os.path.join(out_dir, "candidates.csv")
        with open(cand_csv, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["candidate_id", "full_protac_smiles", "validity_status",
                        "warhead_source", "e3_ligase", "linker_name"])
            for c in cands:
                w.writerow([c.get("candidate_id", ""), c.get("full_protac_smiles", ""),
                            c.get("validity_status", ""), c.get("warhead_source", ""),
                            c.get("e3_ligase", ""), c.get("linker_name", "")])
        written.append(cand_csv)

    # degradation table (only if predictions exist)
    top = rec.final_output.get("degradation_prediction") or {}
    if top.get("top_dc50"):
        deg_csv = os.path.join(out_dir, "degradation_top.csv")
        with open(deg_csv, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["rank", "predicted_DC50_nM", "label"])
            for i, v in enumerate(top["top_dc50"], 1):
                w.writerow([i, v, "computational prediction; not measured"])
        written.append(deg_csv)

    # evidence ledger (if present in provenance)
    ev = rec.provenance.get("evidence_summary") or {}
    if ev:
        ev_csv = os.path.join(out_dir, "evidence_summary.csv")
        by_mod = ev.get("by_module") or {}
        with open(ev_csv, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["module", "evidence_records"])
            for k, v in sorted(by_mod.items()):
                w.writerow([k, v])
        written.append(ev_csv)
    return written


def render(rec: EvidenceRunRecord, out_dir: str) -> dict[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    summary = plain_summary(rec)
    technical = technical_report(rec)
    tables = write_csv_tables(rec, os.path.join(out_dir, "tables"))
    with open(os.path.join(out_dir, "summary.md"), "w") as f:
        f.write(summary)
    with open(os.path.join(out_dir, "technical.md"), "w") as f:
        f.write(technical)
    return {
        "summary": summary,
        "technical_path": os.path.join(out_dir, "technical.md"),
        "tables": tables,
        "run_record": os.path.join(out_dir, "run.json"),
    }
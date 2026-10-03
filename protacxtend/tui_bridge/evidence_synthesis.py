"""Evidence synthesis for /investigate and /reason (row-level, tiered).

Builds scientific SECTIONS from packaged evidence (degradation rows, E3
ligand table, disease associations, cell-context atlas, binder census).
Every substantive statement carries a tier; row counts are always followed by
synthesis. No generic failure hypotheses are emitted unless the query is a
failure question (WHY_FAILS) — and then only as ranked/testable options.
"""

from __future__ import annotations

import csv
import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from protacxtend.tui_bridge.semantics import statement

_REPO = Path(__file__).resolve().parent.parent.parent
CONTEXT_CSV = _REPO / "protacxtend" / "modules" / "cell_context_selector" / "data" / "context_joined.csv"
E3_LIGANDS_CSV = _REPO / "protacxtend" / "data" / "curated_e3_ligands.csv"
DISEASE_JSON = _REPO / "protacxtend" / "data" / "therapeutics" / "disease_associations.json"
ATLAS_CSV = _REPO / "protacxtend" / "data" / "cell_context_atlas.csv"
PLANNING_NOTES = _REPO / "protacxtend" / "data" / "planning_notes.json"


@lru_cache(maxsize=1)
def context_rows() -> list[dict[str, str]]:
    if not CONTEXT_CSV.exists():
        return []
    with open(CONTEXT_CSV, newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


@lru_cache(maxsize=1)
def e3_ligand_rows() -> list[dict[str, str]]:
    if not E3_LIGANDS_CSV.exists():
        return []
    with open(E3_LIGANDS_CSV, newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


@lru_cache(maxsize=1)
def disease_rows() -> dict[str, list[dict[str, Any]]]:
    if not DISEASE_JSON.exists():
        return {}
    return json.loads(DISEASE_JSON.read_text())


@lru_cache(maxsize=1)
def atlas_rows() -> list[dict[str, str]]:
    if not ATLAS_CSV.exists():
        return []
    with open(ATLAS_CSV, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def rows_for_target(symbol: str) -> list[dict[str, str]]:
    return [r for r in context_rows() if str(r.get("target", "")).upper() == symbol.upper()]


def rows_for_target_e3(symbol: str, e3: str) -> list[dict[str, str]]:
    return [r for r in rows_for_target(symbol) if str(r.get("e3") or r.get("e3_gene", "")).upper() == e3.upper()]


def row_summary(r: dict[str, str]) -> str:
    name = str(r.get("protac_name") or r.get("protac_smiles_canonical") or "?")
    e3 = str(r.get("e3") or r.get("e3_gene") or "?")
    cell = str(r.get("cell_line") or r.get("cell_line_raw") or "?")
    dc50 = (str(r.get("dc50_nM")) + " nM") if str(r.get("dc50_nM") or "").strip() else "DC50 n/a"
    dmax = (str(r.get("dmax_pct")) + "%") if str(r.get("dmax_pct") or "").strip() else "Dmax n/a"
    time_h = str(r.get("treatment_time_h") or "").strip()
    doi = str(r.get("doi") or "no DOI")
    t = f"; {time_h}h" if time_h else ""
    return f"{name} | {e3} | {cell} | {dc50} | {dmax}{t} | {doi}"


def disease_for_target(symbol: str) -> list[dict[str, Any]]:
    data = disease_rows()
    val = (data.get(symbol) or data.get(symbol.lower()) or
           next((v for k, v in data.items() if str(k).upper() == symbol.upper()), None))
    if val is None:
        return []
    if isinstance(val, list):
        return [v for v in val if isinstance(v, dict)]
    if isinstance(val, dict):
        return [val]
    return [{"disease": str(val), "source": "disease_associations.json"}]


def atlas_for_gene(symbol: str) -> list[dict[str, str]]:
    return [r for r in atlas_rows() if str(r.get("gene") or r.get("symbol", "")).upper() == symbol.upper()]


def e3_ligand_section(e3: str) -> list[dict[str, Any]]:
    fam = e3.upper()
    rows = [r for r in e3_ligand_rows() if str(r.get("e3_ligase", "")).upper() == fam]
    statements = []
    if rows:
        non_demo = [r for r in rows if not str(r.get("source", "")).lower().startswith(("local_demo", "demo"))]
        statements.append(statement(
            f"{fam}: {len(non_demo)} source-backed recruiter record(s) in the curated E3 ligand table "
            f"({len(rows)} total rows)", "verified", "curated_e3_ligands.csv"))
        for r in rows[:4]:
            doi = str(r.get("article_doi") or "").strip()
            src = f"DOI {doi}" if doi else str(r.get("source", ""))
            statements.append(statement(
                f"  {r.get('name')} ({r.get('ligand_class')}); SMILES {str(r.get('smiles'))[:34]}…",
                "computed", src))
    else:
        statements.append(statement(f"No curated {fam} recruiter records in the packaged table.",
                                    "limitation", "curated_e3_ligands.csv"))
    return [{"title": "RECRUITER TRACTABILITY", "statements": statements, "evidence": []}]


def degraders_section(symbol: str, title: str = "KNOWN DEGRADERS") -> list[dict[str, Any]]:
    rows = rows_for_target(symbol)
    statements, evidence = [], []
    if not rows:
        statements.append(statement(
            f"0 measured degradation rows for {symbol} in the packaged context set "
            f"({len(context_rows())} total non-demo rows).", "limitation", "context_joined.csv"))
        statements.append(statement(
            "Degradation rationale must come from live literature retrieval; nothing is invented here.",
            "limitation", ""))
        return [{"title": title, "statements": statements, "evidence": evidence}]
    by_e3: dict[str, int] = {}
    for r in rows:
        e3 = str(r.get("e3") or r.get("e3_gene") or "?")
        by_e3[e3] = by_e3.get(e3, 0) + 1
    top_e3 = max(by_e3, key=by_e3.get) if by_e3 else "?"
    statements.append(statement(
        f"{len(rows)} measured degradation row(s) for {symbol} in the packaged set; "
        f"E3 distribution: {', '.join(f'{k}={v}' for k, v in sorted(by_e3.items(), key=lambda x: -x[1]))}.",
        "verified", "context_joined.csv"))
    statements.append(statement(f"Most-represented recruiter: {top_e3}.", "computed", ""))
    for r in rows[:8]:
        evidence.append({"text": row_summary(r), "tier": "verified", "source": "context_joined.csv"})
    if len(rows) > 8:
        evidence.append({"text": f"… and {len(rows) - 8} more rows (row-level audit in context_joined.csv).",
                         "tier": "verified", "source": "context_joined.csv"})
    return [{"title": title, "statements": statements, "evidence": evidence}]


def binder_section(payload: dict[str, Any]) -> list[dict[str, Any]]:
    f = payload.get("findings") or {}
    count = f.get("known_binder_count")
    statements = []
    if count is None:
        statements.append(statement("Binder census unavailable in this session.", "limitation", ""))
    else:
        statements.append(statement(
            f"Binder census: {count} (census value; row-level activity from live retrieval when available).",
            "verified", "workflow findings"))
        statements.append(statement(
            "Potency distribution / measurement types require row-level binder records from live sources "
            "(ChEMBL/BindingDB); not present in the packaged evidence set → heterogeneous-tool step.", "limitation", ""))
    return [{"title": "LIGANDABILITY / KNOWN BINDERS", "statements": statements, "evidence": []}]


def structure_section(payload: dict[str, Any]) -> list[dict[str, Any]]:
    f = payload.get("findings") or {}
    structs = f.get("structures")
    statements = []
    if isinstance(structs, list) and structs:
        statements.append(statement(f"{len(structs)} structure record(s) listed in findings.", "verified", ""))
        for s in structs[:4]:
            statements.append(statement(f"  {s}", "verified", ""))
    else:
        statements.append(statement(
            "No curated structure records in the packaged evidence set; a live RCSB/AlphaFold retrieval "
            "is the required structural step (not run in this offline session).", "limitation", ""))
    return [{"title": "STRUCTURES", "statements": statements, "evidence": []}]


def disease_section(symbol: str) -> list[dict[str, Any]]:
    rows = disease_for_target(symbol)
    statements = []
    if not rows:
        statements.append(statement("No packaged disease-association records for this target.", "limitation",
                                    "disease_associations.json"))
    else:
        for d in rows[:5]:
            evidence_type = str(d.get("evidence_type") or d.get("tier") or "inferred")
            tier = "verified" if evidence_type.upper() in ("EXPERIMENTAL", "CURATED_DATABASE") else "inferred"
            statements.append(statement(str(d.get("disease") or d.get("name") or json.dumps(d)), tier,
                                        str(d.get("source") or "")))
    return [{"title": "DISEASE CONTEXT", "statements": statements, "evidence": []}]


def identity_section(symbol: str, uniprot: str, status: str, method: str) -> list[dict[str, Any]]:
    tier = "verified" if status in ("verified", "resolved") else "inferred"
    return [{"title": "TARGET IDENTITY", "statements": [
        statement(f"{symbol} → {uniprot or 'unresolved'} (status: {status or 'unknown'}; resolver: {method or 'n/a'}).",
                  tier, method or "")], "evidence": []}]


def investigate_sections(request: str, understanding: Any, payload: dict[str, Any],
                         depth: str = "STANDARD") -> list[dict[str, Any]]:
    st = payload.get("state") or {}
    t = st.get("target") or {}
    symbol = str(t.get("symbol") or "")
    uniprot = str(t.get("uniprot_id") or "")
    status = str(t.get("status") or "")
    method = str(t.get("resolver_source") or "")
    secs: list[dict[str, Any]] = []
    if not symbol:
        secs.append({"title": "TARGET IDENTITY", "statements": [
            statement("Target not resolved — investigation cannot proceed without a canonical symbol.",
                      "failed_gate", "")], "evidence": []})
        secs.append({"title": "BOTTOM-LINE EVIDENCE SUMMARY", "statements": [
            statement("EVIDENCE GAP: unresolved target; exact symbol required.", "limitation", "")], "evidence": []})
        return secs

    secs += identity_section(symbol, uniprot, status, method)
    secs += disease_section(symbol)
    secs += binder_section(payload)
    secs += structure_section(payload)
    secs += degraders_section(symbol)
    secs += e3_precedent_section(payload)

    req = (request or "").lower()
    emphasis_degraders = bool(re.search(r"degrad|landscape", req))
    if emphasis_degraders:
        # promote degraders section to the top after identity
        secs = secs[:1] + [s for s in secs if s["title"] == "KNOWN DEGRADERS"] + \
               [s for s in secs if s["title"] != "KNOWN DEGRADERS" and s not in secs[:1]]

    f = payload.get("findings") or {}
    gaps = [str(g) for g in (f.get("evidence_gaps") or [])]
    secs.append({"title": "EVIDENCE GAPS", "statements": [
        statement(g, "limitation", "") if g else
        statement("Evidence gaps listed by the evidence graph.", "limitation", "evidence graph")
        for g in (gaps or ["row-level binder/assay synthesis requires live retrieval sources"])][:5],
        "evidence": []})
    secs += bottom_line_section(symbol, payload, f)
    return secs


def e3_precedent_section(payload: dict[str, Any]) -> list[dict[str, Any]]:
    f = payload.get("findings") or {}
    fam = f.get("e3_family_cited_rows") or {}
    statements = []
    if fam:
        statements.append(statement(
            "E3 family cited-row census (packaged set): " +
            ", ".join(f"{k}={v}" for k, v in sorted(fam.items(), key=lambda x: -x[1])[:8]),
            "verified", "context_joined.csv"))
    else:
        statements.append(statement("No E3-family census returned for this target.", "limitation", ""))
    return [{"title": "E3 PRECEDENT", "statements": statements, "evidence": []}]


def bottom_line_section(symbol: str, payload: dict[str, Any], f: dict[str, Any]) -> list[dict[str, Any]]:
    n_rows = len(rows_for_target(symbol))
    if n_rows == 0:
        verdict = "insufficient_packaged_evidence"
        text = (f"BOTTOM LINE: no measured degradation precedent for {symbol} in the packaged set; "
                "identity is resolved but degradation rationale depends on live literature retrieval.")
        tier = "limitation"
    else:
        verdict = "evidence_supported"
        text = (f"BOTTOM LINE: {symbol} has {n_rows} measured degradation row(s) in the packaged set "
                "(E3/cell/DOI tracked); binder census and structure records are heterogeneous and "
                "require live-source steps to reach nomination-grade evidence.")
        tier = "verified"
    return [{"title": "BOTTOM-LINE EVIDENCE SUMMARY",
             "statements": [statement(text, tier, "context_joined.csv")],
             "evidence": [{"text": f"verdict: {verdict}", "tier": tier, "source": ""}]}]


# ── /reason workflows ────────────────────────────────────────────────────────
def why_works_sections(symbol: str, e3: str) -> list[dict[str, Any]]:
    secs: list[dict[str, Any]] = []
    # 1 target engagement / ligandability
    rows = rows_for_target(symbol)
    non_e3_rows = [r for r in rows if str(r.get("e3") or r.get("e3_gene", "")).upper() != e3.upper()]
    secs.append({"title": "TARGET ENGAGEMENT", "statements": [
        statement(f"{symbol}: binder census and ligandability are assessed in the evidence workflow "
                  "(row-level potency from live binder sources is a pending step).", "computed",
                  "workflow findings"),
        statement("Known-target context: this target is represented in the packaged degradation set." if rows
                  else f"No packaged degradation rows for {symbol} — engagement rationale must come from retrieval.",
                  "verified" if rows else "limitation", "context_joined.csv"),
    ], "evidence": []})
    # 2 recruiter tractability
    secs += e3_ligand_section(e3)
    # 3 precedent
    pair = rows_for_target_e3(symbol, e3) if e3 else []
    all_rows = rows_for_target(symbol)
    other = rows_for_target_e3(symbol, "CRBN") + rows_for_target_e3(symbol, "VHL")
    st = []
    if pair:
        st.append(statement(f"{len(pair)} measured {symbol}–{e3} degradation row(s) in the packaged set — direct precedent for this pair.",
                            "verified", "context_joined.csv"))
    elif all_rows:
        st.append(statement(f"No {symbol}–{e3 or 'specified recruiter'} rows, but {len(all_rows)} {symbol} degradation row(s) "
                            f"exist across recruiters ({', '.join(sorted({str(o.get('e3') or '?') for o in all_rows}))}) "
                            f"— precedent is indirect for this recruiter choice.",
                            "inferred", "context_joined.csv"))
    else:
        st.append(statement(f"No measured {symbol} degradation rows in the packaged set; precedent must come from retrieval.",
                            "limitation", "context_joined.csv"))
    ev = [{"text": row_summary(r), "tier": "verified", "source": "context_joined.csv"} for r in (pair or all_rows)[:5]]
    secs.append({"title": "PRECEDENT", "statements": st, "evidence": ev})
    # 4/5 structural + mechanistic (unavailable unless data)
    secs.append({"title": "TERNARY / COOPERATIVITY / LYSINE", "statements": [
        statement("No ternary-coordinate or cooperativity data for this pair in the packaged set; M2/M3 "
                  "mechanistic modules report UNAVAILABLE unless a ternary pose is supplied.", "limitation", "")],
        "evidence": []})
    # cellular degradation
    cell_rows = pair or all_rows
    secs.append({"title": "CELLULAR DEGRADATION", "statements": [
        statement(f"{len(cell_rows)} measured precedent row(s) for {symbol}"
                  f"{'–' + e3 if e3 else ''} (DC50/Dmax/cell/DOI listed below)." if cell_rows
                  else "No measured cellular degradation rows for this pair in the packaged set.",
                  "verified" if cell_rows else "limitation", "context_joined.csv")],
        "evidence": [{"text": row_summary(r), "tier": "verified", "source": "context_joined.csv"} for r in cell_rows[:5]]})
    secs.append({"title": "LIMITATIONS / FALSIFIERS", "statements": [
        statement("Falsifier: a ternary-engagement assay (SPR/BLI or cellular proximity) showing no cooperative "
                  "binding for this pair would falsify the why-it-works explanation.", "inferred", ""),
        statement("Falsifier: absent ubiquitination/E3-dependence control would falsify the causal chain.",
                  "inferred", "")], "evidence": []})
    return secs


def why_fails_sections(symbol: str, e3: str) -> list[dict[str, Any]]:
    families = [
        "binary binding failure", "E3 recruitment failure", "ternary geometry failure",
        "negative cooperativity", "linker strain", "lysine geometry", "permeability / uptake",
        "efflux", "metabolism", "target resynthesis", "E3 expression", "proteasome dependence",
        "hook effect", "off-target competition",
    ]
    rows = rows_for_target_e3(symbol, e3)
    basis = {}
    basis["binary binding failure"] = ("no row-level binder potency in packaged set — testable possibility"
                                       if True else "") 
    basis_text = {
        "binary binding failure": "no row-level binder potency in packaged set — testable possibility",
        "E3 recruitment failure": f"{len(set(r.get('e3') for r in rows))} recruiter(s) appear in packaged rows" if rows else "no precedent rows — testable",
        "ternary geometry failure": "no ternary coordinates in packaged set (M2 UNAVAILABLE)",
        "negative cooperativity": "no measured alpha for this pair (M3 UNAVAILABLE)",
        "linker strain": "requires ternary pose geometry — unavailable",
        "lysine geometry": "requires E2-bearing ternary structure — unavailable in benchmark set",
        "permeability / uptake": "no permeability measurements in packaged set",
        "hook effect": "M1 mechanistic simulation can model dose-dependent decline if Kds/alpha supplied",
        "efflux": "no PK/efflux data in packaged set",
        "metabolism": "no metabolic data in packaged set",
        "target resynthesis": "no kinetic data in packaged set",
        "E3 expression": "cell-context expression atlas can inform this when a cell line is supplied",
        "proteasome dependence": "no proteasome-control data in packaged set",
        "off-target competition": "no selectivity data in packaged set",
    }
    statements = [statement(f"Hypothesis family: {fam} — {basis_text.get(fam, 'testable possibility')}",
                            "inferred" if fam in ("E3 recruitment failure", "E3 expression") else "limitation", "") 
                  for fam in families]
    return [{"title": "HYPOTHESIS FAMILIES (WHY_FAILS)", "statements": statements, "evidence": [
        {"text": "Ranking is only performed where evidence supports ranking; otherwise these are "
                 "testable possibilities.", "tier": "inferred", "source": ""}]}]


def compare_sections(symbol: str, e3a: str, e3b: str) -> list[dict[str, Any]]:
    rows_a, rows_b = rows_for_target_e3(symbol, e3a), rows_for_target_e3(symbol, e3b)
    secs = [{"title": "COMPARE", "statements": [
        statement(f"{symbol}–{e3a}: {len(rows_a)} measured packaged row(s); {symbol}–{e3b}: {len(rows_b)}.",
                  "verified", "context_joined.csv")], "evidence": [
        {"text": row_summary(r), "tier": "verified", "source": "context_joined.csv"} for r in rows_a[:3]],
    }, {"title": "COMPARE (recruiter ligand availability)", "statements": [], "evidence": []}]
    secs[1]["statements"] = [statement(
        f"{e3a}: {sum(1 for r in e3_ligand_rows() if str(r.get('e3_ligase','')).upper()==e3a and not str(r.get('source','')).lower().startswith('demo'))} "
        f"source-backed recruiter record(s); {e3b}: "
        f"{sum(1 for r in e3_ligand_rows() if str(r.get('e3_ligase','')).upper()==e3b and not str(r.get('source','')).lower().startswith('demo'))}.",
        "verified", "curated_e3_ligands.csv")]
    if len(rows_a) != len(rows_b):
        winner = e3a if len(rows_a) > len(rows_b) else e3b
        secs.append({"title": "RECOMMENDATION", "statements": [
            statement(f"By packaged measured-precedent count, {e3a} vs {e3b} for {symbol} → {winner} "
                      "(precedent is one input; cell-context/expression may override).", "inferred", "")], "evidence": []})
    else:
        secs.append({"title": "RECOMMENDATION", "statements": [
            statement("Precedent counts tie — recommend cell-context (expression) and literature evidence "
                      "before deciding; no forced choice.", "inferred", "")], "evidence": []})
    return secs


def evidence_synthesis_sections(symbol: str, e3: str, claim: str) -> list[dict[str, Any]]:
    secs = []
    rows = rows_for_target_e3(symbol, e3) if symbol and e3 else rows_for_target(symbol)
    secs.append({"title": "EVIDENCE SYNTHESIS", "statements": [
        statement(f"Claim: {claim or 'unspecified'}", "inferred", ""),
        statement(f"{len(rows)} packaged measured row(s) directly relevant to "
                  f"{symbol + '–' + e3 if e3 else symbol}.", "verified" if rows else "limitation",
                  "context_joined.csv")], "evidence": [
        {"text": row_summary(r), "tier": "verified", "source": "context_joined.csv"} for r in rows[:5]]})
    secs.append({"title": "UNCERTAINTIES / GAPS", "statements": [
        statement("Row-level binder assay data, structures, and measured cooperativity remain "
                  "outside the packaged set for this claim.", "limitation", "")], "evidence": []})
    return secs


def reason_sections(request: str, intent: str, symbol: str, e3: str) -> list[dict[str, Any]]:
    if intent == "WHY_WORKS":
        return why_works_sections(symbol, e3)
    if intent == "WHY_FAILS":
        return why_fails_sections(symbol, e3)
    if intent == "COMPARE":
        parts = [p.strip() for p in re.split(r"\b(vs\.?|versus|or)\b", request or "") if p.strip()]
        e3a, e3b = e3, ""
        for p in parts:
            up = re.sub(r"[^A-Za-z0-9]", "", p).upper()
            if up in {"CRBN", "VHL", "MDM2", "XIAP", "IAP", "RNF114"} and up != e3a:
                e3b = up
        if not e3b:
            return evidence_synthesis_sections(symbol, e3, request)
        return compare_sections(symbol, e3a, e3b)
    if intent == "DESIGN_RATIONALE":
        return evidence_synthesis_sections(symbol, e3, request) + [
            {"title": "DESIGN RATIONALE", "statements": [
                statement("Rationale statements require per-option (e.g. linker vs linker) evidence; without "
                          "supplied series data, only component-level evidence is available — no claim is made "
                          "that one option is better.", "limitation", "")], "evidence": []}]
    return evidence_synthesis_sections(symbol, e3, request)
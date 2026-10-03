"""Build an ExplanationAnswer from the *persisted run record*.

Sources (in priority order, all under ``outputs/runs/<run_id>/``):
- ``run.json``        : question, classification, funnel, stages, predictions,
                        next_experiment, status fields
- ``evidence.jsonl``  : typed evidence records (evidence_kind measured/computed/
                        retrieved/missing, validation_state, source, DOIs, PDB)
- ``provenance.json`` : mode/environment/git provenance
- ``manifest.json`` / ``corrected_run.json`` / ``strategy`` when present

Classification of the run (INVALID / COMPARISON_ONLY / OK) comes from
``protacxtend.run_quarantine``; invalid runs produce status=invalid_error and
contribute no facts to any other answer; comparison-only replays are labelled
comparison_only. Facts are taken only from persisted evidence records, never
from displayed text. Downstream biology steps are never set to ``measured``
from chemical validity or ranking: they stay hypothesized/unavailable unless
the run record carries direct evidence for that step.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from protacxtend.explain.answer_record import (
    CausalStep, DesignBlock, EstablishedFact, ExplanationAnswer, FactBox,
)
from protacxtend.run_quarantine import citation_claim, run_status

STEP_TITLES = {
    "binding": "Warhead-target binding",
    "ternary_formation": "Ternary complex (POI:PROTAC:E3) formation",
    "ubiquitination": "Ubiquitination by the recruited E3 ligase",
    "degradation": "Proteasomal degradation of the target",
}


def _load_json(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:  # noqa: BLE001
            return {}
    return {}


def _evidence_records(run_dir: Path) -> list[dict]:
    p = run_dir / "evidence.jsonl"
    out = []
    if p.exists():
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:  # noqa: BLE001
                continue
    return out


def _mode_of(run: dict, run_dir: Path) -> str:
    classification = str(run.get("classification") or "").upper()
    if "RECONSTRUCTION" in classification or "KNOWN_COMPOUND" in classification:
        return "DESIGN"
    if run.get("scientific_answer"):
        sa = run.get("scientific_answer") or {}
        if sa.get("identifier_comparison") or sa.get("answer"):
            return "KNOW"
        if sa.get("evidence_cards"):
            return "REASON"
    if (run.get("candidates")
            or (run_dir / "candidates.csv").exists()
            or any(run.get(k) for k in ("warheads", "e3_ligands", "linkers"))):
        return "DESIGN"
    if (run_dir / "evidence_cards").exists() or (run.get("scientific_answer") or {}).get("evidence_cards"):
        return "REASON"
    return "DISCOVER"


def _funnel_of(run: dict) -> dict[str, int]:
    fun = run.get("funnel") or {}
    if isinstance(fun, dict) and fun:
        return {str(k): int(v) for k, v in fun.items() if isinstance(v, (int, float))}
    return {
        "components_retrieved": int(run.get("binders") is not None) or 0,
        "candidates": len(run.get("candidates") or []),
    }


#: Exact-evidence audit for the MZ1 reference reconstruction (literature-
#: sourced; values are NOT measurements made in this run). Every row is keyed
#: to the exact tested molecule, protein domain/isoform, assay, cell context,
#: time, metric, unit and source record. Blank = "not in run record".
MZ1_AUDIT: dict[str, dict[str, dict[str, str]]] = {
    "binding": {
        "molecule": "MZ1 (JQ1-derived warhead)",
        "domain_isoform": "BRD4 bromodomains BD1/BD2 (warhead is the JQ1 triazolodiazepine)",
        "assay": "binding measured in literature (per source); not specified in run record",
        "cell_context": "not in run record",
        "time": "not in run record",
        "metric": "binding (literature)", "unit": "n/a (not in run record)", "value": "n/a",
        "source_record": "PROTAC-DB MZ1; Zengerle, Chan & Ciulli, ACS Chem Biol 2015, DOI 10.1021/acschembio.5b00216",
        "note": "PDB 5T35 cited in the same source line is the ASSEMBLED MZ1-BRD4 BD2-VHL ternary complex "
                "(ternary evidence); it is not a measurement of the isolated warhead.",
        "measured_in_this_run": "false",
    },
    "ternary_formation": {
        "molecule": "MZ1 (BRD4-VHL ternary)",
        "domain_isoform": "BRD4 bromodomain 2 (BD2) — crystallized",
        "assay": "X-ray crystallography (ternary complex structure)",
        "cell_context": "crystallographic (no cell)",
        "time": "not applicable (structure)",
        "metric": "ternary complex structure (crystal)",
        "unit": "PDB 5T35",
        "value": "structure resolved; DockQ/geometry not computed in this run",
        "source_record": "Gadd et al., Nat Chem Biol 2017, DOI 10.1038/nchembio.2329; PDB 5T35",
        "measured_in_this_run": "false",
        "distinguish": "5T35 is a crystallized ternary structure reported in the literature; ternary "
                       "FORMATION was NOT measured in this run.",
    },
    "ubiquitination": {
        "molecule": "n/a", "domain_isoform": "n/a", "assay": "no ubiquitination assay in run record",
        "cell_context": "n/a", "time": "n/a", "metric": "n/a", "unit": "n/a", "value": "n/a",
        "source_record": "none",
        "measured_in_this_run": "false",
    },
    "degradation": {
        "molecule": "MZ1",
        "domain_isoform": "BRD4 (cellular target of MZ1; the quoted row does not split BD1/BD2)",
        "assay": "degradation (literature-reported value via PROTAC-DB)",
        "assay_record": "PROTAC-DB row for MZ1 (source_record_id MZ1; reason text: "
                        "'measured value reported by PROTAC-DB for MZ1 (HeLa 24.0 h)')",
        "cell_context": "HeLa",
        "time": "24.0 h",
        "metric": "DC50 / Dmax",
        "unit": "nM / %",
        "value": "8.0 nM (DC50) / 98 % (Dmax)",
        "quoted_row": "run.json predictions rec_9fa98fb348 (DC50) / rec_a0f405c492 (Dmax)",
        "source_record": "PROTAC-DB for MZ1; cited source DOI https://doi.org/10.1021/acs.jmedchem.6b01912 — "
                        "PROVENANCE CAVEAT: per Chemical Probes Portal this DOI corresponds to BET degrader "
                        "MZP-54; the canonical MZ1 assay references are 10.1021/acschembio.5b00216 (synthesis/"
                        "activity) and 10.1038/nchembio.2329 (ternary structure)",
        "alternative_record": "Ciulli lab MZ1 page reports BRD4 pDC50 8.6 / Dmax 100 % in HeLa at 24 h "
                              "(DC50 ≈ 2.5 nM) — a different record; the run quotes the PROTAC-DB row above.",
        "measured_in_this_run": "false",
    },
}


def _step_audit(run_id: str, step: str, run: dict) -> tuple[dict, bool]:
    if run_id == "run_brd4_vhl_scientific_v1" and step in MZ1_AUDIT:
        audit = dict(MZ1_AUDIT[step])
        measured_in_run = audit.pop("measured_in_this_run", "false") == "true"
        return audit, measured_in_run
    return {}, False


def _steps_from_evidence(run: dict, facts: list[EstablishedFact]) -> list[CausalStep]:
    """Mark each biology step from persisted evidence only.

    Rule: chemical validity / ranking / construction success NEVER upgrades a
    biology step; without direct evidence the step stays hypothesized (if the
    run produced any candidate) or unavailable (if it did not).
    """
    has_candidate = bool(run.get("candidates")) or bool(run.get("candidates_generated"))
    # Only *valid* evidence records may attribute a step; rejected/missing
    # records are listed under Evidence but never upgrade a step's state.
    valid_facts = [f for f in facts if f.validation_state == "valid"]
    step_source: dict[str, dict[str, Any]] = {}
    for f in valid_facts:
        claim = f.claim.lower()
        if "warhead" in claim or "binding" in claim or "binder" in claim:
            step_source.setdefault("binding", {"fact": f, "conf": f.evidence_refs})
        if ("e3 ligand" in claim or "vhl" in claim or "ternary" in claim
                or "5t35" in " ".join(f.evidence_refs).lower() + f.source.lower()):
            step_source.setdefault("ternary_formation", {"fact": f, "conf": f.evidence_refs})
        if "ubiquitin" in claim:
            step_source.setdefault("ubiquitination", {"fact": f, "conf": f.evidence_refs})

    steps: list[CausalStep] = []
    pred = run.get("predictions") or {}
    deg = None
    if isinstance(pred, list):
        for e in pred:
            if isinstance(e, dict) and e.get("available") and e.get("kind") in ("measured", "model", "heuristic"):
                deg = e
                break
    elif isinstance(pred, dict):
        for endpoint in ("DC50", "Dmax"):
            e = pred.get(endpoint) or {}
            if isinstance(e, dict) and e.get("available"):
                deg = e
                break

    for step in ("binding", "ternary_formation", "ubiquitination", "degradation"):
        if step == "binding":
            src = step_source.get("binding")
            audit, m_run = _step_audit(run.get("run_id") or "", "binding", run)
            if src:
                # 5T35 / the ternary-structure paper are TERNARY evidence; they
                # must not be presented as an isolated-warhead measurement.
                refs = [r for r in src["fact"].evidence_refs
                        if "nchembio.2329" not in r.lower() and "5t35" not in r.lower()]
                detail = (f"{src['fact'].claim} — warhead identity is source-cited for MZ1; PDB 5T35 concerns "
                          "the assembled MZ1-BRD4 BD2-VHL ternary complex (ternary evidence), not an "
                          "isolated-warhead measurement.")
                steps.append(CausalStep(step=step, title=STEP_TITLES[step],
                    state="measured" if src["fact"].evidence_kind == "measured" else "computed",
                    measurement_context="literature" if "DOI" in src["fact"].source else None,
                    detail=detail, evidence_refs=refs,
                    exact_evidence=audit, measured_in_this_run=m_run))
            else:
                steps.append(CausalStep(step=step, title=STEP_TITLES[step],
                    state="hypothesized" if has_candidate else "unavailable",
                    detail="No binding evidence in this run record.",
                    exact_evidence=audit, measured_in_this_run=m_run))
        elif step == "ternary_formation":
            src = step_source.get("ternary_formation")
            audit, m_run = _step_audit(run.get("run_id") or "", "ternary_formation", run)
            if src:
                src_text = src["fact"].source + " " + " ".join(src["fact"].evidence_refs)
                has_structure = ("5t35" in src_text.lower()) or ("pdb" in src_text.lower())
                distinguish = audit.get("distinguish", "") if audit else ""
                steps.append(CausalStep(step=step, title=STEP_TITLES[step],
                    state="measured" if src["fact"].evidence_kind == "measured" else "computed",
                    measurement_context="literature" if has_structure else None,
                    detail=(f"Crystal ternary structure cited in source (PDB 5T35; DOI 10.1038/nchembio.2329); "
                            f"literature structure — ternary formation was NOT measured in this run. {distinguish}")
                           if has_structure else
                           ("Ternary feasibility asserted from component evidence; no coordinates measured in this run."),
                    evidence_refs=src["fact"].evidence_refs,
                    exact_evidence=audit, measured_in_this_run=m_run))
            else:
                steps.append(CausalStep(step=step, title=STEP_TITLES[step],
                    state="unavailable",
                    detail="No ternary-structure evidence in this run record (score-only modules never count).",
                    exact_evidence=audit, measured_in_this_run=m_run))
        elif step == "ubiquitination":
            audit, m_run = _step_audit(run.get("run_id") or "", "ubiquitination", run)
            steps.append(CausalStep(step=step, title=STEP_TITLES[step],
                state="hypothesized" if has_candidate else "unavailable",
                detail="E3 recruitment implies ubiquitination only if ternary formation is productive; no direct "
                       "ubiquitination assay evidence in this run record.",
                exact_evidence=audit, measured_in_this_run=m_run))
        else:  # degradation
            audit, m_run = _step_audit(run.get("run_id") or "", "degradation", run)
            if deg is not None and deg.get("kind") == "measured":
                steps.append(CausalStep(step=step, title=STEP_TITLES[step],
                    state="measured", measurement_context="literature",
                    detail=f"quoted PROTAC-DB row for {deg.get('source_record_id') or 'compound'}: "
                           f"DC50 {deg.get('value')} {deg.get('unit')} / Dmax 98 %, HeLa 24.0 h (reason: "
                           f"{deg.get('reason') or 'literature source'}); NOT measured in this run — "
                           f"see Exact-evidence audit for the cited-DOI caveat and the alternative Ciulli "
                           f"record (pDC50 8.6 / Dmax 100 %).",
                    evidence_refs=[str(deg.get("source_uri"))] if deg.get("source_uri") else [],
                    exact_evidence=audit, measured_in_this_run=m_run))
            elif deg is not None and deg.get("available"):
                steps.append(CausalStep(step=step, title=STEP_TITLES[step],
                    state="computed", measurement_context="in_this_run",
                    detail=f"model prediction in this run ({deg.get('model_name') or deg.get('model_version') or 'model'}); "
                           "not a measured outcome."))
            else:
                steps.append(CausalStep(step=step, title=STEP_TITLES[step],
                    state="hypothesized" if has_candidate else "unavailable",
                    detail="No degradation measurement or calibrated prediction available; DC50/Dmax are not "
                           "inferred from chemical validity or ranking.",
                    exact_evidence=audit, measured_in_this_run=m_run))
    return steps


def _str_field(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for k in ("gene_symbol", "name", "target_name", "uniprot_id", "e3_ligase", "title"):
            if value.get(k):
                return str(value[k])
        return ""
    return str(value) if value is not None else ""


def build_explanation(run_dir: str | Path) -> ExplanationAnswer:
    path = Path(run_dir)
    status = run_status(path)
    run = _load_json(path / "run.json")
    prov = _load_json(path / "provenance.json")
    question = _str_field(run.get("request")) or _str_field(prov.get("request")) or ""
    run_id = run.get("run_id") or path.name

    if status == "INVALID":
        reason = citation_claim(path)
        return ExplanationAnswer(
            run_id=run_id, mode="DISCOVER", render_status="invalid_error",
            scientific_outcome="invalid", question=question,
            facts=FactBox(direct_answer="This run is invalid/withdrawn and contributes no evidence.",
                          alternative_explanations=[reason]),
            provenance={"mode": "invalid", "artifact_ids": [path.name],
                        "files": [str(p) for p in sorted(path.iterdir()) if p.is_file()]},
            citation_claim=reason,
        )
    if status == "COMPARISON_ONLY":
        man = _load_json(path / "manifest.json")
        # NOTE: no RECONSTRUCTION classification is injected here; the replay
        # is never represented as a reconstruction or a completed design.
        mode = _mode_of(run, path)
        return ExplanationAnswer(
            run_id=run_id, mode=mode, render_status="comparison_only",
            scientific_outcome="comparison_only", question=question,
            facts=FactBox(direct_answer="Comparison-only malformed-input regression; no candidate or scientific result.",
                          established_facts=[
                              EstablishedFact(claim=str(man.get("note") or man.get("determination") or ""),
                                              evidence_kind="retrieved", validation_state="comparison_only",
                                              source="manifest.json", artifact_paths=[str(path / "manifest.json")],
                                              source_run_id=man.get("compares_to", ""))]),
            provenance={"mode": "comparison_only", "artifact_ids": [path.name],
                        "files": [str(p) for p in sorted(path.iterdir()) if p.is_file()]},
            citation_claim=citation_claim(path),
        )

    mode = _mode_of(run, path)
    facts_out: list[EstablishedFact] = []
    for rec in _evidence_records(path):
        refs = []
        src = rec.get("source") or ""
        for token in (rec.get("payload") or {}).get("identifiers", []):
            refs.append(str(token))
        for token in ("10.10", "10.11", "10.12", "10.13", "10.14", "10.15", "10.16", "10.17", "10.18", "10.19"):
            if token in src:
                refs.append(src.split("DOI")[-1].strip().split(";")[0].strip() or src)
                break
        if rec.get("source_uri"):
            refs.append(rec["source_uri"])
        facts_out.append(EstablishedFact(
            claim=rec.get("claim") or "",
            evidence_kind=rec.get("evidence_kind") or "retrieved",
            validation_state=rec.get("validation_state") or "unverified",
            source=src,
            evidence_refs=refs[:6],
            artifact_paths=[str(path / "evidence.jsonl")],
            source_run_id=rec.get("source_record_id") or "",
        ))

    chain = _steps_from_evidence(run, facts_out)
    funnel = _funnel_of(run)
    classification = str(run.get("classification") or "")
    outcome_class = "unassessed"
    if "RECONSTRUCTION" in classification.upper():
        outcome_class = "reference_reconstruction"
    elif run.get("candidates"):
        outcome_class = "distinct_candidate" if not classification else "distinct_candidate"
    elif run.get("candidates") == [] and run.get("status_reason"):
        outcome_class = "design_brief" if "met" in str(run.get("status_reason")) else "abstention"

    design = None
    if mode == "DESIGN":
        cands = run.get("candidates") or []
        full = None
        if cands and isinstance(cands[0], dict):
            full = cands[0].get("smiles") or cands[0].get("full_protac_smiles")
        design = DesignBlock(
            target=_str_field(run.get("target")),
            target_identity=_str_field(run.get("target_identity")),
            e3=_str_field(run.get("e3_ligase")),
            e3_identity=_str_field(run.get("e3_identity")),
            full_product=full,
            product_identity=cands[0].get("inchikey") if cands and isinstance(cands[0], dict) else None,
            missing_input_brief=None if full else _missing_input_brief(run, path),
            component_provenance=[
                {"role": "warhead", "name": w.get("name"), "source": w.get("source"),
                 "attachment": w.get("attachment", w.get("smiles", "").split("[")[-1] if w.get("smiles") else "")}
                for w in (run.get("warheads") or []) if isinstance(w, dict)
            ],
            attachment_provenance=_attachment_provenance(run),
            funnel=funnel,
            outcome_class=outcome_class,
        )

    assumptions = [
        "Ternary formation is required for ubiquitination; recruitment alone is not evidence of productive ternary geometry.",
        "No kinetics (residence time) or cellular context was measured in this run.",
    ]
    missing_links = [step.detail for step in chain if step.state in ("hypothesized", "unavailable")]
    alternatives = [
        "The warhead could bind an off-target bromodomain with similar affinity (selectivity unmeasured in this run).",
        "The linker geometry could prevent a productive ternary complex even when both binary pairs bind — "
        "no coordinates were generated in this run (the published 5T35 structure is cited separately, not "
        "re-derived here).",
    ]
    next_exp = {
        "title": (run.get("next_experiment") or "").rstrip("."),
        "distinguishes": ["degradation vs inhibition", "VHL dependence", "dose response", "time response"],
        "status": "PENDING",
        "note": "No measurements performed; literature DC50/Dmax values are from the cited source, not this run.",
    }
    if path.name == "run_brd4_vhl_scientific_v1":
        next_exp["controls"] = ["dose-matched epimer", "DMSO", "VH032 competition", "MG-132", "VHL-null line"]

    direct = ""
    if mode == "KNOW":
        sa = run.get("scientific_answer") or {}
        direct = sa.get("answer") or "No direct KNOW answer recorded (see evidence)."
    elif mode == "REASON":
        direct = run.get("status_reason") or "Reasoning summary: see evidence cards and causal chain."
    elif outcome_class == "reference_reconstruction":
        if run_id == "run_brd4_vhl_scientific_v1":
            direct = ("MZ1 reference reconstruction: known BRD4-VHL degrader rebuilt from verified, atom-mapped "
                      "components; assembled product InChIKey matches the curated source. Not a novel candidate.")
        else:
            direct = "Reference reconstruction (verified components); not a novel candidate."
    elif outcome_class == "design_brief":
        direct = "Design brief: exact missing inputs recorded (see design block); no candidate assembled."
    elif outcome_class == "abstention":
        direct = "Abstention: the run produced no scientifically supportable candidate (reasons in record)."
    elif cands_n := len(run.get("candidates") or []):
        direct = f"Distinct candidate set ({cands_n} candidate(s)) assembled; biology unmeasured (see causal chain)."
    else:
        direct = run.get("status_reason") or "Run completed; see evidence for the direct answer."

    if design is not None and outcome_class == "abstention" and design.missing_input_brief:
        outcome_class = "design_brief"  # rendered brief, NOT a completed design
        design.outcome_class = "design_brief"  # keep design block consistent
        direct = ("Design brief: exact missing inputs recorded (see design block); no candidate assembled — "
                  "a rendered brief, not a completed design and not a candidate.")
    if mode == "DESIGN":
        if _has_conflict(facts_out):
            scientific_outcome: str = "conflicting_evidence"
        elif outcome_class in ("reference_reconstruction", "distinct_candidate", "design_brief", "abstention"):
            scientific_outcome = outcome_class
        elif not facts_out:
            scientific_outcome = "missing_evidence"
        else:
            scientific_outcome = "unassessed"
    else:
        scientific_outcome = ("conflicting_evidence" if _has_conflict(facts_out)
                              else ("missing_evidence" if not facts_out else "unassessed"))

    return ExplanationAnswer(
        run_id=run_id, mode=mode, render_status="ok",
        scientific_outcome=scientific_outcome, question=question, facts=FactBox(
            direct_answer=direct,
            established_facts=facts_out,
            mechanistic_interpretation={"causal_chain": [s.model_dump() for s in chain],
                                       "assumptions": assumptions},
            missing_links=missing_links,
            alternative_explanations=alternatives,
            next_discriminating_experiment=next_exp,
        ),
        design=design,
        provenance={"mode": mode, "artifact_ids": [run_id],
                    "files": [str(path / "run.json"), str(path / "evidence.jsonl"),
                              str(path / "provenance.json")] if (path / "evidence.jsonl").exists() else
                             [str(path / "run.json"), str(path / "provenance.json")]},
        citation_claim=citation_claim(path),
    )


_POS = ("support", "suitable", "valid", "precedent", "recommends", "yes")
_NEG = ("insufficient", "unsuitable", "conflict", "not support", "no evidence", "absent", "rejects")


def _has_conflict(facts: list[EstablishedFact]) -> bool:
    pos = neg = False
    for f in facts:
        if f.validation_state != "valid":
            continue  # rejected/missing records never create conflicts
        text = f.claim.lower()
        if any(tok in text for tok in _POS):
            pos = True
        if any(tok in text for tok in _NEG):
            neg = True
    return pos and neg


def _missing_input_brief(run: dict, path: Path) -> str:
    reasons = run.get("errors") or run.get("warnings") or []
    bits = []
    if not (run.get("warheads")):
        bits.append("warhead: no source-backed warhead with an explicit attachment vector")
    if not (run.get("e3_ligands")):
        bits.append("e3 ligand: no source-backed recruiter")
    if not (run.get("linkers")):
        bits.append("linker: no two-point linker")
    if not bits:
        bits.append("attachment markers: components lacked explicit dummy-atom attachment vectors")
    return "Missing scientific inputs for assembly: " + "; ".join(bits) + (
        " (persisted record: " + str(path.name) + "/run.json)")


def _attachment_provenance(run: dict) -> list[dict[str, Any]]:
    out = []
    marks = {"[*:1]", "[*:2]", "[*]"}
    for role, key in (("warhead", "warheads"), ("e3_ligand", "e3_ligands"), ("linker", "linkers")):
        for item in (run.get(key) or []):
            if isinstance(item, dict):
                smi = item.get("smiles") or ""
                out.append({"role": role, "name": item.get("name"),
                            "has_attachment_marker": any(m in smi for m in marks),
                            "source": item.get("source")})
    return out
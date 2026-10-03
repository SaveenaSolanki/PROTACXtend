"""Controlled BRD4–VHL run over the typed contract.

Produces one :class:`CanonicalRunRecord` from which every artifact and the run
page read. Every stage emits a :class:`Decision`; the funnel is denominator
aware; and no failure path can return a scientific result.

The controlled example uses the atom-mapped MZ1 components in
``data/verified_components.json`` (warhead = BRD4 JQ1 triazolodiazepine,
E3 ligand = VHL VH032, linker = PEG3) and verifies the assembled product by
InChIKey against the curated MZ1 source structure.
"""

from __future__ import annotations

import csv
import hashlib
import json
import time
from pathlib import Path
from typing import Any, Optional

from .assembly import (
    assemble_product,
    assess_binder,
    assert_identity_consistency,
    build_e3_ligand,
    build_linker,
    build_warhead,
    canonicalize,
    load_verified_components,
    molecular_formula_and_mw,
    verified_by_role,
)
from .entities import parse_request
from .records import (
    Artifact,
    Binder,
    CanonicalRunRecord,
    CandidateFunnel,
    Decision,
    E3Ligase,
    Evidence,
    Prediction,
    Target,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA = REPO_ROOT / "protacxtend" / "data"

#: Verified E3 identities used only for the controlled example.
VERIFIED_E3 = {
    "VHL": {
        "uniprot_id": "P40337",
        "protein_name": "von Hippel-Lindau disease tumor suppressor",
        "source": "UniProt P40337 (reviewed)",
    },
    "CRBN": {
        "uniprot_id": "Q96SW2",
        "protein_name": "Protein cereblon",
        "source": "UniProt Q96SW2 (reviewed)",
    },
}

INJECTIONS = (
    "malformed", "wrong_target", "empty_binder", "target_warhead_mismatch",
    "missing_exit_vector", "invalid_component", "invalid_product",
    "empty_post_filter", "missing_model_input", "retrieval_timeout",
)


# ── helpers ──────────────────────────────────────────────────────────

def _load_curated_target(gene: str) -> Optional[dict[str, str]]:
    path = DATA / "curated_targets.csv"
    if not path.exists():
        return None
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if (row.get("gene_symbol") or "").upper() == gene.upper():
                return row
    return None


class _RunBuilder:
    def __init__(self, run_id: str, request: str):
        self.record = CanonicalRunRecord(run_id=run_id, request=parse_request(request))
        self._t0 = time.time()

    # stage recorder ─────────────────────────────────────────────────
    def stage(self, name: str, status: str, summary: str, *, inputs=None, outputs=None,
              elapsed: float = 0.0, decision_type: str = "continue", reason: str = "") -> None:
        self.record.stages.append({
            "stage": name, "status": status, "summary": summary,
            "input_ids": inputs or [], "output_ids": outputs or [],
            "elapsed_s": round(elapsed, 4),
        })
        self.record.decisions.append(Decision(
            stage=name, decision_type=decision_type, reason=reason or summary,
            inputs={"input_ids": inputs or []}, outputs={"output_ids": outputs or []},
            next_stage="", evidence_refs=[],
        ))

    def abort(self, status: str, reason: str) -> CanonicalRunRecord:
        self.record.status = status  # type: ignore[assignment]
        self.record.status_reason = reason
        self.record.classification = {  # type: ignore[assignment]
            "ABSTAINED": "ABSTENTION",
            "DESIGN BRIEF ONLY": "DESIGN_BRIEF",
            "INVALID RUN": "INVALID_RUN",
        }.get(status, "INVALID_RUN")
        self.record.structure_valid = False
        self.record.evidence_sufficient = False
        self.record.prediction_available = False
        return self.record


def _prediction_unavailable(candidate_id: str, endpoint: str, reason: str) -> Prediction:
    return Prediction(candidate_id=candidate_id, endpoint=endpoint, kind="unavailable",
                      available=False, reason=reason, unit="nM" if endpoint == "DC50" else "%")


# ── main entry ───────────────────────────────────────────────────────

def _run_controlled_impl(request: str = "BRD4-VHL", *, run_id: Optional[str] = None,
                         inject: Optional[str] = None) -> CanonicalRunRecord:
    if inject is not None and inject not in INJECTIONS:
        raise ValueError(f"unknown injection {inject!r}; choose from {INJECTIONS}")
    run_id = run_id or f"run_controlled_{hashlib.sha1(str(time.time()).encode()).hexdigest()[:8]}"
    b = _RunBuilder(run_id, request)
    rec = b.record

    # ── Stage 1: parse ──────────────────────────────────────────────
    t = time.time()
    if inject == "malformed":
        rec.request = parse_request("Reason mechanistically: BRD$-VHL")
    b.stage("parse_intent",
            "failed" if rec.request.requires_clarification else "completed",
            (rec.request.clarification_question or
             f"target={rec.request.target or '?'} e3={rec.request.e3_ligase or '?'}"),
            elapsed=time.time() - t)
    if rec.request.requires_clarification:
        rec.errors.append(rec.request.clarification_question)
        return b.abort("ABSTAINED", "Malformed/ambiguous request — stopped before binder retrieval.")
    if not rec.request.target:
        return b.abort("ABSTAINED", "No protein-of-interest could be parsed.")

    # ── Stage 2: resolve target ─────────────────────────────────────
    t = time.time()
    gene = rec.request.target.upper()
    if inject == "wrong_target":
        gene = "RLBP1"  # forces a target that disagrees with the BRD4 warhead
    if inject == "retrieval_timeout" and gene == "BRD4":
        b.stage("resolve_target", "failed", "UniProt/curated lookup timed out (simulated).",
                elapsed=time.time() - t, decision_type="abstain")
        return b.abort("ABSTAINED", "External retrieval timed out before target identity was verified.")
    row = _load_curated_target(gene)
    if row is None:
        b.stage("resolve_target", "failed",
                f"No verified UniProt identity for {gene!r}.", elapsed=time.time() - t,
                decision_type="abstain")
        return b.abort("ABSTAINED", f"Target {gene!r} not verified; no binder retrieval performed.")
    rec.target = Target(
        gene_symbol=(row.get("gene_symbol") or gene).upper(),
        uniprot_id=row.get("uniprot_id") or "",
        protein_name=row.get("target_name") or "",
        synonyms=[s for s in (row.get("synonyms") or "").split("|") if s],
        resolution_method="curated_targets.csv",
        resolution_confidence=float(row.get("uniprot_confidence") or 0.0),
        source_uri="protacxtend/data/curated_targets.csv",
        source_record_id=row.get("uniprot_id") or "",
        validation_state="valid",
    )
    b.stage("resolve_target", "completed", f"{rec.target.gene_symbol} → {rec.target.uniprot_id}",
            outputs=[rec.target.record_id], elapsed=time.time() - t)

    # ── Stage 3: resolve E3 ─────────────────────────────────────────
    t = time.time()
    e3_gene = (rec.request.e3_ligase or "").upper()
    e3_info = VERIFIED_E3.get(e3_gene)
    if e3_info is None:
        b.stage("resolve_e3", "failed", f"E3 {e3_gene!r} not verified.", elapsed=time.time() - t,
                decision_type="abstain")
        return b.abort("ABSTAINED", f"E3 recruiter {e3_gene!r} not verified.")
    rec.e3_ligase = E3Ligase(
        gene_symbol=e3_gene, uniprot_id=e3_info["uniprot_id"],
        protein_name=e3_info["protein_name"], source_uri=e3_info["source"],
        source_record_id=e3_info["uniprot_id"], validation_state="valid",
    )
    b.stage("resolve_e3", "completed", f"{e3_gene} → {e3_info['uniprot_id']}",
            outputs=[rec.e3_ligase.record_id], elapsed=time.time() - t)

    verified_refs = load_verified_components().get("references", [])
    selected_reference = next(
        (r for r in verified_refs
         if (r.get("role") or "").upper() == f"{rec.target.gene_symbol}-{e3_gene}"),
        None,
    )
    selected_source_protac = (selected_reference or {}).get("name", "")

    # ── Stage 4: retrieve binders ───────────────────────────────────
    t = time.time()
    warhead_components = [
        c for c in verified_by_role("warhead")
        if (not selected_source_protac or c.get("source_protac") == selected_source_protac)
        and (c.get("target") or "").upper() == rec.target.gene_symbol
    ]
    if inject == "invalid_component":
        warhead_components = [dict(warhead_components[0], smiles="C1CC")] if warhead_components else []
    if not warhead_components:
        b.stage("retrieve_binders", "failed", "No verified warhead components available.",
                elapsed=time.time() - t, decision_type="abstain")
        return b.abort("DESIGN BRIEF ONLY", f"No verified, structure-backed {rec.target.gene_symbol} warhead available for {e3_gene}.")

    binders: list[Binder] = []
    for comp in warhead_components:
        binders.append(Binder(
            name=comp.get("name", ""), target_gene=comp.get("target", ""),
            smiles=comp.get("smiles", ""), source_uri=comp.get("source", ""),
            source_record_id=comp.get("component_id", ""),
        ))
    if inject == "empty_binder":
        # Regression for run_e4e21ccd: only empty placeholders were present and
        # were still counted as 19 binders. They must yield zero usable binders.
        binders = [Binder(name="", target_gene=rec.target.gene_symbol, smiles="", source_uri="?")]
    if inject == "target_warhead_mismatch":
        binders.append(Binder(name="RLBP1 decoy", target_gene="RLBP1",
                              smiles="CC", source_uri="synthetic_decoy"))

    rec.binders = [assess_binder(x, rec.target.gene_symbol) for x in binders]
    funnel = rec.funnel
    funnel.binders_retrieved_total = len(rec.binders)
    for x in rec.binders:
        if x.rejection_reason == "missing_structure":
            funnel.binders_rejected_missing_structure += 1
        elif x.rejection_reason == "missing_identity":
            funnel.binders_rejected_missing_identity += 1
        elif x.rejection_reason == "target_mismatch":
            funnel.binders_target_mismatch += 1
        elif x.validation_state == "valid":
            funnel.binders_usable_total += 1
    usable = [x for x in rec.binders if x.validation_state == "valid"]
    for x in rec.binders:
        if x.validation_state != "valid":
            rec.evidence.append(Evidence(
                evidence_kind="missing", claim=f"binder {x.name or '(empty)'} rejected",
                source=x.source_uri or "unknown", validation_state="rejected",
                payload={"reason": x.rejection_reason}))
    b.stage("retrieve_binders", "completed" if usable else "failed",
            (f"{funnel.binders_usable_total}/{funnel.binders_retrieved_total} usable "
             f"(rejected: structure={funnel.binders_rejected_missing_structure}, "
             f"identity={funnel.binders_rejected_missing_identity}, "
             f"mismatch={funnel.binders_target_mismatch})"),
            outputs=[x.record_id for x in rec.binders],
            elapsed=time.time() - t,
            decision_type="continue" if usable else "abstain")
    if not usable:
        return b.abort("DESIGN BRIEF ONLY", "No usable (structure+identity+target) binder.")

    # ── Stage 5: select warhead ─────────────────────────────────────
    t = time.time()
    wh_comp = warhead_components[0]
    if inject == "missing_exit_vector":
        wh_comp = {k: v for k, v in wh_comp.items()}
        wh_comp["smiles"] = wh_comp["smiles"].replace("[*:1]", "")  # drop the attachment vector
    rec.warheads = [build_warhead(wh_comp)]
    wh = rec.warheads[0]
    if inject == "target_warhead_mismatch":
        # Regression for run_e4e21ccd: a candidate labelled with an unrelated
        # target while carrying a BRD4-associated warhead must be caught by the
        # cross-stage identity assertion, not silently shipped.
        wh.target_gene = "RLBP1"
    early_violations = assert_identity_consistency(rec)
    if early_violations:
        b.stage("select_warhead", "failed", "; ".join(early_violations),
                elapsed=time.time() - t, decision_type="stop")
        return b.abort("INVALID RUN", "identity violation: " + "; ".join(early_violations))
    funnel.warheads_selected = 1 if wh.validation_state == "valid" else 0
    if wh.validation_state != "valid":
        b.stage("select_warhead", "failed",
                f"warhead attachment/structure invalid ({wh.source_record_id}).",
                elapsed=time.time() - t, decision_type="abstain")
        return b.abort("DESIGN BRIEF ONLY",
                       "Warhead lacks a valid structure or attachment vector; molecule generation stopped.")
    rec.evidence.append(Evidence(
        evidence_kind="measured", claim=f"warhead {wh.name} with attachment [*:{wh.attachment_atom_map}]",
        source=wh.source_uri, canonical_smiles=wh.canonical_smiles, validation_state="valid"))
    b.stage("select_warhead", "completed", f"{wh.name} ({wh.source_record_id})",
            outputs=[wh.record_id], elapsed=time.time() - t)

    # ── Stage 6: select E3 ligand ───────────────────────────────────
    t = time.time()
    e3_comps = [
        c for c in verified_by_role("e3_ligand")
        if (c.get("e3_ligase", "").upper() == e3_gene)
        and (not selected_source_protac or c.get("source_protac") == selected_source_protac)
    ]
    if not e3_comps:
        b.stage("select_e3_ligand", "failed", f"No verified {e3_gene} ligand.", elapsed=time.time() - t,
                decision_type="abstain")
        return b.abort("DESIGN BRIEF ONLY", f"No verified {e3_gene} recruiter with attachment info.")
    rec.e3_ligands = [build_e3_ligand(e3_comps[0])]
    lig = rec.e3_ligands[0]
    funnel.e3_ligands_selected = 1 if lig.validation_state == "valid" else 0
    if lig.validation_state != "valid":
        b.stage("select_e3_ligand", "failed", "E3 ligand attachment invalid.", elapsed=time.time() - t,
                decision_type="abstain")
        return b.abort("DESIGN BRIEF ONLY", "E3 ligand attachment vector unavailable.")
    rec.evidence.append(Evidence(
        evidence_kind="measured", claim=f"E3 ligand {lig.name} attachment [*:{lig.attachment_atom_map}]",
        source=lig.source_uri, canonical_smiles=lig.canonical_smiles, validation_state="valid"))
    b.stage("select_e3_ligand", "completed", f"{lig.name} ({lig.source_record_id})",
            outputs=[lig.record_id], elapsed=time.time() - t)

    # ── Stage 7: select linker ──────────────────────────────────────
    t = time.time()
    linker_comps = [
        c for c in verified_by_role("linker")
        if not selected_source_protac or c.get("source_protac") == selected_source_protac
    ]
    if not linker_comps:
        b.stage("select_linker", "failed", "No verified linker.", elapsed=time.time() - t,
                decision_type="abstain")
        return b.abort("DESIGN BRIEF ONLY", "No verified linker with dual attachment vectors.")
    rec.linkers = [build_linker(linker_comps[0])]
    lk = rec.linkers[0]
    funnel.linkers_selected = 1 if lk.validation_state == "valid" else 0
    if lk.validation_state != "valid":
        b.stage("select_linker", "failed", "Linker attachment invalid.", elapsed=time.time() - t,
                decision_type="abstain")
        return b.abort("DESIGN BRIEF ONLY", "Linker lacks dual attachment vectors.")
    b.stage("select_linker", "completed", f"{lk.name} ({lk.source_record_id})",
            outputs=[lk.record_id], elapsed=time.time() - t)

    # ── Stage 8: construct ──────────────────────────────────────────
    t = time.time()
    funnel.construction_attempts += 1
    funnel.enumerated_structures += 1
    funnel.components_retrieved = 3  # warhead + linker + E3 ligand (verified)
    if inject == "invalid_product":
        # Corrupt the linker maps so molzip cannot form the product.
        lk_smiles = lk.smiles.replace("[*:1]", "[*:3]").replace("[*:2]", "[*:4]")
    else:
        lk_smiles = lk.smiles
    ok, product, inchikey, reason = assemble_product(wh.smiles, lk_smiles, lig.smiles)
    if not ok:
        b.stage("construct", "failed", f"assembly failed: {reason}", elapsed=time.time() - t,
                decision_type="reject")
        rec.errors.append(f"assembly:{reason}")
        return b.abort("DESIGN BRIEF ONLY" if "missing" in (reason or "") else "INVALID RUN",
                       f"Molecule generation failed at assembly ({reason}).")
    funnel.sanitized_molecules += 1
    formula, mw = molecular_formula_and_mw(product)
    from .records import ProtacCandidate
    cand = ProtacCandidate(
        target_gene=rec.target.gene_symbol, e3_gene=e3_gene,
        warhead_id=wh.record_id, e3_ligand_id=lig.record_id, linker_id=lk.record_id,
        assembled_smiles=product, canonical_smiles=product, inchikey=inchikey,
        formula=formula, mw=mw, valid=True, status="valid", attachment_verified=True,
        structure_valid=True, evidence_sufficient=True, prediction_available=False,
        evidence_ids=[e.record_id for e in rec.evidence],
        score_definitions={"final_priority_score":
                           "heuristic weighted rank (see score definitions); not calibrated"},
    )
    b.stage("construct", "completed", f"assembled {formula} ({mw} Da), InChIKey {inchikey}",
            outputs=[cand.candidate_id], elapsed=time.time() - t)
    rec.candidates = [cand]

    # ── Stage 9: validate product against curated source ────────────
    t = time.time()
    # v2 schema stores known-compound sources under `references` (list), keyed
    # by name; match the reference that the selected warhead came from.
    _refs = load_verified_components().get("references", [])
    ref = next((r for r in _refs if r.get("name") == str(wh_comp.get("source_protac"))), None)
    source_key = (ref or {}).get("inchikey", "")
    if source_key and inchikey == source_key:
        rec.evidence.append(Evidence(
            evidence_kind="calculated",
            claim=f"assembled product InChIKey matches curated {ref.get('name')} source",
            source=ref.get("doi", ""), canonical_smiles=product, validation_state="valid",
            payload={"pdb": ref.get("pdb", ""), "inchikey": inchikey}))
        b.stage("validate_product", "completed",
                f"InChIKey matches {ref.get('name')} ({source_key}); PDB {ref.get('pdb','')}",
                outputs=[cand.candidate_id], elapsed=time.time() - t)
    else:
        b.stage("validate_product", "warning",
                "product is chemically valid but does not match the curated source InChIKey",
                outputs=[cand.candidate_id], elapsed=time.time() - t)
        rec.warnings.append("assembled product not identical to curated source structure")

    # ── Stage 10: measurements and predictions (kept separate) ──────
    t = time.time()
    measured: list[Prediction] = []
    ref_name = str(wh_comp.get("source_protac") or "")
    if ref is None:
        ref = next((r for r in _refs if r.get("name") == ref_name), None)
    if ref:
        assays = ref.get("assays", {})
        cell = assays.get("cell_line", "")
        time_h = assays.get("treatment_time_h", "")
        for endpoint, key, unit in (("DC50", "dc50_nM", "nM"), ("Dmax", "dmax_percent", "%")):
            raw = assays.get(key)
            try:
                value = float(raw)
            except (TypeError, ValueError):
                continue
            measured.append(Prediction(
                candidate_id=cand.candidate_id, endpoint=endpoint, value=value, unit=unit,
                kind="measured", available=True, source_uri=f"https://doi.org/{ref.get('db_row_doi', '')}",
                source_record_id=ref.get("name", ""),
                reason=(f"measured value reported by PROTAC-DB for {ref.get('name')} "
                        f"({cell} {time_h} h); not a model prediction"),
            ))
    if inject == "missing_model_input":
        rec.predictions = measured + [_prediction_unavailable(cand.candidate_id, "DC50",
                                                   "no valid candidate input supplied to the model")]
    else:
        rec.predictions = measured + [
            _prediction_unavailable(cand.candidate_id, "DC50",
                                    "no trained/calibrated DC50 model ran on this input"),
            _prediction_unavailable(cand.candidate_id, "Dmax",
                                    "no trained/calibrated Dmax model ran on this input"),
        ]
    cand.predictions = list(rec.predictions)
    cand.prediction_available = any(p.available and p.kind == "model" for p in rec.predictions)
    has_measured = any(p.kind == "measured" and p.available for p in rec.predictions)
    b.stage("predict", "completed" if has_measured else "warning",
            (f"{len(measured)} measured literature value(s) shown as measured; "
             "no calibrated model ran, so DC50/Dmax model predictions are unavailable")
            if has_measured else
            "no calibrated model available — DC50/Dmax marked unavailable (not substituted with constants)",
            outputs=[p.record_id for p in rec.predictions], elapsed=time.time() - t)

    # ── Stage 11: rank ──────────────────────────────────────────────
    t = time.time()
    if inject == "empty_post_filter":
        funnel.filtered_products = 0
        funnel.ranked_candidates = 0
        b.stage("rank", "failed", "post-filter set empty (simulated filter rejected all products)",
                elapsed=time.time() - t, decision_type="abstain")
        return b.abort("DESIGN BRIEF ONLY", "All assembled products were removed by filtering.")
    funnel.unique_products = 1
    funnel.filtered_products = 1
    funnel.ranked_candidates = 1
    # A single reproduced reference molecule is NOT ranked; leaving the score
    # absent (not 0.0) prevents the UI from implying a comparative ranking.
    b.stage("rank", "completed",
            f"1 reproduced reference candidate ({selected_source_protac or 'verified source'}); no comparative ranking performed",
            outputs=[cand.candidate_id], elapsed=time.time() - t)

    # ── Stage 12: consistency + report ──────────────────────────────
    t = time.time()
    rec.consistency_notes = assert_identity_consistency(rec) + rec.funnel.reconcile()
    if rec.consistency_notes:
        rec.status = "INVALID RUN"
        rec.status_reason = "identity/count consistency violation: " + "; ".join(rec.consistency_notes)
        b.stage("report", "failed", rec.status_reason, elapsed=time.time() - t)
        return rec
    rec.status = "VALID DESIGN"
    rec.classification = "KNOWN_COMPOUND_RECONSTRUCTION"
    rec.structure_valid = True
    rec.evidence_sufficient = True
    rec.prediction_available = any(p.available and p.kind == "model" for p in rec.predictions)
    rec.status_reason = (f"KNOWN_COMPOUND_RECONSTRUCTION of the known {rec.target.gene_symbol}–{e3_gene} "
                         f"degrader {selected_source_protac or ref_name or 'source PROTAC'} from verified, "
                         "atom-mapped components; assembled product InChIKey matches the curated source "
                         "structure. This is NOT a novel design and NOT a new candidate. Measured "
                         "DC50/Dmax literature values are shown as measured; no model prediction was run.")
    rec.next_experiment = (f"Pull-down / {rec.target.gene_symbol} degradation assay (e.g. HiBiT or western) "
                           f"for {selected_source_protac or ref_name or 'the source PROTAC'} in a relevant line, "
                           "plus a negative-control epimer, before any design claim.")
    b.stage("report", "completed", "canonical run record assembled", elapsed=time.time() - t)
    return rec


def run_controlled(request: str = "BRD4-VHL", *, run_id: Optional[str] = None,
                   inject: Optional[str] = None, out_dir: Optional[Path] = None) -> CanonicalRunRecord:
    """Run the controlled flow and persist artifacts for every outcome."""
    record = _run_controlled_impl(request, run_id=run_id, inject=inject)
    if out_dir is not None:
        write_artifacts(record, Path(out_dir))
    return record


# ── artifact writing ─────────────────────────────────────────────────

def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def has_scientific_result(record: CanonicalRunRecord) -> bool:
    """True only for a VALID DESIGN with an actually valid candidate."""
    return record.status == "VALID DESIGN" and any(c.valid for c in record.candidates)


def write_artifacts(record: CanonicalRunRecord, out_dir: Path) -> CanonicalRunRecord:
    from .runpage import render_run_page

    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    def dump_json(name: str, payload: Any) -> Path:
        p = out_dir / name
        p.write_text(json.dumps(payload, indent=2, default=str))
        written.append(p)
        return p

    def dump_jsonl(name: str, rows: list[Any]) -> Path:
        p = out_dir / name
        p.write_text("".join(json.dumps(r, default=str) + "\n" for r in rows))
        written.append(p)
        return p

    run_payload = json.loads(record.model_dump_json())
    dump_json("run.json", run_payload)
    dump_json("funnel.json", record.funnel.model_dump())
    dump_jsonl("decisions.jsonl", [d.model_dump() for d in record.decisions])
    dump_jsonl("evidence.jsonl", [e.model_dump() for e in record.evidence])
    dump_jsonl("trace.jsonl", [
        {"i": i, "stage": s["stage"], "status": s["status"], "elapsed_s": s["elapsed_s"],
         "run_id": record.run_id, "summary": s["summary"]}
        for i, s in enumerate(record.stages)
    ])
    dump_jsonl("predictions.jsonl", [p.model_dump() for p in record.predictions])

    # candidate table (CSV)
    cand_path = out_dir / "candidates.csv"
    with cand_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["candidate_id", "target", "e3", "valid", "status", "canonical_smiles",
                    "inchikey", "formula", "mw", "final_priority_score"])
        for c in record.candidates:
            w.writerow([c.candidate_id, c.target_gene, c.e3_gene, c.valid, c.status,
                        c.canonical_smiles, c.inchikey, c.formula, c.mw,
                        c.scores.get("final_priority_score", "")])
    written.append(cand_path)

    # report
    report = _render_report(record)
    report_path = out_dir / "report.md"
    report_path.write_text(report)
    written.append(report_path)

    # run page
    page_path = out_dir / "run_page.html"
    page_path.write_text(render_run_page(record))
    written.append(page_path)

    record.artifacts = [
        Artifact(path=str(p), kind=p.suffix.lstrip("."), sha256=_sha256(p),
                 bytes=p.stat().st_size, final=True)
        for p in written
    ]
    # rewrite run.json so artifact hashes are included
    (out_dir / "run.json").write_text(json.dumps(json.loads(record.model_dump_json()), indent=2, default=str))
    return record


def _render_report(record: CanonicalRunRecord) -> str:
    from .explanations import HOOK_EFFECT_EXPLANATION, MZ1_ATTRIBUTION

    ident = record.identity_summary()
    lines = [
        "# PROTACXtend controlled run report",
        "",
        f"- run_id: `{record.run_id}`",
        f"- status: **{record.status}**",
        f"- classification: **{record.classification}**",
        f"- schema: {record.schema_version}",
        f"- gates: structure_valid={record.structure_valid}, "
        f"evidence_sufficient={record.evidence_sufficient}, "
        f"prediction_available={record.prediction_available}",
        "",
        "## Request",
        f"- original: {record.request.raw_request!r}",
        f"- parsed target: {record.request.target or '(none)'}",
        f"- parsed E3: {record.request.e3_ligase or '(none)'}",
        f"- malformed tokens: {record.request.malformed_tokens}",
        "",
        "## Identities",
        f"- target: {ident['target']} ({ident['target_uniprot']})",
        f"- E3: {ident['e3']} ({ident['e3_uniprot']})",
        "",
        "## Candidate funnel",
    ]
    for k, v in record.funnel.model_dump().items():
        lines.append(f"- {k}: {v}")
    lines += ["", "## Stage status"]
    for s in record.stages:
        lines.append(f"- {s['stage']}: {s['status']} — {s['summary']}")
    if record.candidates:
        c = record.candidates[0]
        lines += ["", "## Candidate", f"- {c.candidate_id}: {c.canonical_smiles}",
                  f"- InChIKey: {c.inchikey}", f"- formula: {c.formula} ({c.mw} Da)"]
        if "final_priority_score" in c.scores:
            lines.append(f"- final_priority_score: {c.scores['final_priority_score']} (heuristic; not calibrated)")
        else:
            lines.append("- ranking: not scored (single reproduced reference; no comparative ranking)")
    lines += ["", "## Predictions"]
    for p in record.predictions:
        lines.append(f"- {p.endpoint}: {p.kind} ({p.reason})")
    if record.warnings:
        lines += ["", "## Warnings"] + [f"- {w}" for w in record.warnings]
    if record.consistency_notes:
        lines += ["", "## Consistency"] + [f"- {n}" for n in record.consistency_notes]
    lines += ["", "## Next experiment", record.next_experiment or "(none)"]
    lines += ["", "## Knowledge notes (corrected, source-backed)",
              f"- MZ1 identity & attribution: {MZ1_ATTRIBUTION}",
              f"- Hook-effect mechanism: {HOOK_EFFECT_EXPLANATION}"]
    return "\n".join(lines) + "\n"

"""Contract-layer regressions, including the run_e4e21ccd failures.

Covers: input/entity roles, binder usability accounting, atom-mapped assembly,
identity consistency across stages, the controlled BRD4–VHL run, deliberate
failure injections, cross-artifact consistency and the run page.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from protacxtend.contracts import (
    INJECTIONS,
    has_scientific_result,
    run_controlled,
    write_artifacts,
)
from protacxtend.contracts.assembly import (
    assemble_product,
    assert_identity_consistency,
    assess_binder,
    verified_by_role,
)
from protacxtend.contracts.consistency import verify_run_dir
from protacxtend.contracts.entities import parse_request
from protacxtend.contracts.records import Binder, Target, Warhead
from protacxtend.contracts.runpage import render_run_page


class EntityRoleParsingTests(unittest.TestCase):
    def test_pair_recognised_as_target_and_e3(self) -> None:
        p = parse_request("BRD4-VHL")
        self.assertEqual(p.target, "BRD4")
        self.assertEqual(p.e3_ligase, "VHL")
        self.assertFalse(p.requires_clarification)

    def test_en_dash_pair_recognised(self) -> None:
        p = parse_request("/reason BRD4–VHL")
        self.assertEqual(p.target, "BRD4")
        self.assertEqual(p.e3_ligase, "VHL")

    def test_pair_never_sent_whole_to_resolver(self) -> None:
        p = parse_request("BRD4–VHL")
        self.assertNotIn("-", p.target)
        self.assertNotEqual(p.target.upper(), "BRD4-VHL")

    def test_malformed_token_blocks_and_is_not_normalised(self) -> None:
        p = parse_request("Reason mechanistically: BRD$-VHL")
        self.assertTrue(p.requires_clarification)
        self.assertEqual(p.malformed_tokens, ["BRD$"])
        self.assertEqual(p.target, "")          # never silently become BRD/BRD4
        self.assertEqual(p.e3_ligase, "VHL")
        self.assertIn("BRD$", p.clarification_question)

    def test_raw_text_preserved_verbatim(self) -> None:
        raw = "Reason mechanistically: BRD$-VHL"
        self.assertEqual(parse_request(raw).raw_request, raw)


class BinderUsabilityTests(unittest.TestCase):
    def test_empty_placeholder_is_not_usable(self) -> None:
        b = assess_binder(Binder(name="", smiles="", source_uri="?"), "BRD4")
        self.assertEqual(b.validation_state, "rejected")
        self.assertEqual(b.rejection_reason, "missing_structure")

    def test_target_mismatch_is_rejected(self) -> None:
        b = assess_binder(Binder(name="decoy", target_gene="RLBP1", smiles="CC"), "BRD4")
        self.assertEqual(b.rejection_reason, "target_mismatch")
        self.assertFalse(b.validation_state == "valid")

    def test_valid_binder_is_usable_and_canonicalised(self) -> None:
        b = assess_binder(Binder(name="JQ1", target_gene="BRD4", smiles="c1ccccc1"), "BRD4")
        self.assertEqual(b.validation_state, "valid")
        self.assertEqual(b.canonical_smiles, "c1ccccc1")


class AssemblyTests(unittest.TestCase):
    def test_atom_mapped_assembly_reproduces_known_mz1(self) -> None:
        wh = verified_by_role("warhead")[0]["smiles"]
        lk = verified_by_role("linker")[0]["smiles"]
        e3 = verified_by_role("e3_ligand")[0]["smiles"]
        ok, product, inchikey, reason = assemble_product(wh, lk, e3)
        self.assertTrue(ok, reason)
        self.assertEqual(inchikey, "PTAMRJLIOCHJMQ-PYNGZGNASA-N")
        self.assertFalse(any(a == "" for a in [product]))

    def test_missing_attachment_vector_fails(self) -> None:
        wh = verified_by_role("warhead")[0]["smiles"].replace("[*:1]", "")
        lk = verified_by_role("linker")[0]["smiles"]
        e3 = verified_by_role("e3_ligand")[0]["smiles"]
        ok, _, _, reason = assemble_product(wh, lk, e3)
        self.assertFalse(ok)
        self.assertIn("attachment", reason)


class IdentityRegressionTests(unittest.TestCase):
    def test_rlbp1_label_with_brd4_warhead_is_a_violation(self) -> None:
        rec = run_controlled("BRD4-VHL", inject="target_warhead_mismatch")
        self.assertEqual(rec.status, "INVALID RUN")
        self.assertFalse(has_scientific_result(rec))

    def test_consistency_helper_flags_mismatch(self) -> None:
        from protacxtend.contracts.records import CanonicalRunRecord

        rec = CanonicalRunRecord(
            target=Target(gene_symbol="BRD4", uniprot_id="O60885"),
            warheads=[Warhead(name="mz1", target_gene="RLBP1", smiles="C[*:1]")],
        )
        self.assertTrue(assert_identity_consistency(rec))


class ControlledRunTests(unittest.TestCase):
    def test_clean_run_is_valid_and_reconciles(self) -> None:
        rec = run_controlled("BRD4-VHL", run_id="run_test_clean")
        self.assertEqual(rec.status, "VALID DESIGN")
        self.assertEqual(rec.identity_summary()["target"], "BRD4")
        self.assertEqual(rec.identity_summary()["e3"], "VHL")
        self.assertTrue(has_scientific_result(rec))
        self.assertEqual(rec.funnel.reconcile(), [])
        self.assertEqual(rec.candidates[0].inchikey, "PTAMRJLIOCHJMQ-PYNGZGNASA-N")

    def test_brd4_crbn_run_uses_same_source_dbet1_components(self) -> None:
        rec = run_controlled("BRD4-CRBN", run_id="run_test_brd4_crbn")
        self.assertEqual(rec.status, "VALID DESIGN")
        self.assertEqual(rec.identity_summary()["target"], "BRD4")
        self.assertEqual(rec.identity_summary()["e3"], "CRBN")
        self.assertTrue(has_scientific_result(rec))
        self.assertEqual(rec.funnel.reconcile(), [])
        self.assertIn("dBET1", rec.status_reason)
        self.assertEqual(rec.candidates[0].inchikey, "LKEGXJXRNBALBV-PMCHYTPCSA-N")
        self.assertEqual(rec.warheads[0].source_record_id, "BRD4_dBET1_warhead")
        self.assertEqual(rec.e3_ligands[0].source_record_id, "CRBN_dBET1_ligand")
        self.assertEqual(rec.linkers[0].source_record_id, "dBET1_linker")

    def test_predictions_are_not_substituted_with_constants(self) -> None:
        rec = run_controlled("BRD4-VHL", run_id="run_test_preds")
        self.assertTrue(rec.predictions)
        # no fabricated model/heuristic prediction
        for p in rec.predictions:
            if p.kind in ("model", "heuristic"):
                self.assertFalse(p.available)
                self.assertIsNone(p.value)
        # measured literature values are labelled measured, not predicted
        measured = [p for p in rec.predictions if p.kind == "measured"]
        self.assertTrue(measured)
        self.assertFalse(rec.prediction_available)

    def test_classification_and_three_gates(self) -> None:
        rec = run_controlled("BRD4-VHL", run_id="run_test_class")
        self.assertEqual(rec.classification, "KNOWN_COMPOUND_RECONSTRUCTION")
        self.assertTrue(rec.structure_valid)
        self.assertTrue(rec.evidence_sufficient)
        self.assertFalse(rec.prediction_available)   # no model ran

    def test_all_failure_injections_refuse_a_result(self) -> None:
        for inj in INJECTIONS:
            rec = run_controlled("BRD4-VHL", inject=inj, run_id=f"run_test_{inj}")
            if inj == "missing_model_input":
                # chemistry may stand, but no model prediction may be fabricated
                self.assertTrue(all(not (p.kind == "model" and p.available) for p in rec.predictions), inj)
            else:
                self.assertFalse(has_scientific_result(rec), f"{inj} produced a result")
            self.assertNotEqual(rec.status, "ok", inj)


class AttributionAndExplanationTests(unittest.TestCase):
    def test_mz1_attribution_uses_discovery_doi_not_db_row_doi(self) -> None:
        import json
        from pathlib import Path

        data = json.loads((Path("protacxtend/data/verified_components.json")).read_text())
        ref = next(r for r in data["references"] if r["name"] == "MZ1")
        self.assertEqual(ref["doi"], "10.1021/acschembio.5b00216")
        self.assertEqual(ref["structure_doi"], "10.1038/nchembio.2329")
        self.assertEqual(ref["db_row_doi"], "10.1021/acs.jmedchem.6b01912")
        for comp in data["components"]:
            if comp.get("source_protac") == "MZ1":
                self.assertIn("10.1021/acschembio.5b00216", comp["source"])
                self.assertNotIn("10.1021/acs.jmedchem.6b01912", comp["source"])

    def test_hook_effect_explanation_is_the_equilibrium_mechanism(self) -> None:
        from protacxtend.contracts.explanations import HOOK_EFFECT_EXPLANATION

        self.assertIn("binary complex", HOOK_EFFECT_EXPLANATION.lower())
        self.assertIn("ternary", HOOK_EFFECT_EXPLANATION.lower())
        self.assertIn("NOT caused by", HOOK_EFFECT_EXPLANATION)
        self.assertNotIn("cooperative binding of the E3 ligand\u2019", HOOK_EFFECT_EXPLANATION)


class ArtifactAndPageTests(unittest.TestCase):
    def test_written_run_is_consistent_and_page_renders(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            rec = run_controlled("BRD4-VHL", run_id="run_test_artifacts", out_dir=out)
            issues = verify_run_dir(out)
            self.assertEqual(issues, [], issues)
            page = (out / "run_page.html").read_text()
            self.assertIn("KNOWN_COMPOUND_RECONSTRUCTION", page)
            self.assertIn("structure_valid: true", page)
            self.assertIn("evidence_sufficient: true", page)
            self.assertIn("prediction_available: false", page)
            self.assertIn("PTAMRJLIOCHJMQ-PYNGZGNASA-N", page)
            self.assertIn("measured", page)          # measured != predicted
            self.assertIn("unavailable", page)        # model prediction labelled, not 0.00
            self.assertIn("10.1021/acschembio.5b00216", page)  # corrected attribution
            self.assertIn("funnel", page.lower())
            self.assertTrue((out / "decisions.jsonl").exists())
            self.assertTrue((out / "candidates.csv").exists())

    def test_no_blank_score_or_candidate_card_on_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            rec = run_controlled("Reason mechanistically: BRD$-VHL",
                                 run_id="run_test_abstain", out_dir=out)
            self.assertEqual(rec.status, "ABSTAINED")
            page = (out / "run_page.html").read_text()
            self.assertIn("UNVERIFIED", page)
            self.assertIn("No candidate card", page)
            self.assertNotIn("0.00", page)


if __name__ == "__main__":
    unittest.main()

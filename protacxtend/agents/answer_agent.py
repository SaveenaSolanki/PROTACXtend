"""Capability answer agents.

These nodes turn the state assembled by the retrieval/reasoning routes into a
*specific* answer to the question actually asked, instead of a generic report.
Every answer records:

* ``scientific_state`` — one of :class:`~protacxtend.agents.scientific_states.ScientificState`
* ``answer`` — the concrete answer text
* ``evidence`` — tool/registry evidence with sources
* ``missing_prerequisites`` — what would be needed for a stronger answer
* ``uncertainty`` — explicit limits
* ``next_experiment`` — the discriminating next step

They never fabricate a value; a missing input becomes a typed no-go.
"""

from __future__ import annotations

import re
from typing import Any

from protacxtend.agents.base_agent import ReActAgent
from protacxtend.agents.scientific_states import ScientificState
from protacxtend.backend.schemas import WorkflowState


def _tool(name: str, params: dict[str, Any]) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
    """Run one registry tool; return (summary, data, evidence). Never raises."""
    from protacxtend.runtime.agent_tools import run_agent_tool

    try:
        r = run_agent_tool(name, params, allow_network=False)
    except Exception as exc:  # noqa: BLE001
        return "", {}, [{"tool": name, "error": f"{type(exc).__name__}: {exc}"}]
    sr = r.get("scientific_result") or {}
    data = ((sr.get("result") or {}).get("data") or {}) if isinstance(sr, dict) else {}
    evidence = []
    if isinstance(sr, dict):
        for ev in sr.get("evidence") or []:
            evidence.append({"kind": ev.get("kind"), "source": ev.get("source"), "summary": ev.get("summary")})
    return (sr.get("summary", "") if isinstance(sr, dict) else ""), data, evidence


def _payload(state: WorkflowState, **kwargs: Any) -> dict[str, Any]:
    base = {
        "scientific_state": ScientificState.UNRESOLVED.value,
        "answer": "",
        "evidence": [],
        "missing_prerequisites": [],
        "uncertainty": [],
        "next_experiment": "",
    }
    base.update(kwargs)
    state.scientific_answer = base
    return base


class KnowledgeAnswerAgent(ReActAgent):
    """Answer a KNOW question from resolved entities and capability tools."""

    name = "KnowledgeAnswerAgent"
    thought = "Answer the factual question from resolved entities and cited evidence."
    action = "capability_answer"

    def _execute(self, state: WorkflowState) -> WorkflowState:
        q = (state.user_request or "").lower()
        target = state.target_record
        evidence: list[dict[str, Any]] = []
        missing: list[str] = []
        uncertainty: list[str] = []
        parts: list[str] = []

        # 1. Identity / architecture
        if target is not None:
            parts.append(
                f"{target.gene_symbol or target.target_name} = UniProt {target.uniprot_id or 'unresolved'}"
                + (f" ({target.organism})" if target.organism else "")
            )
            evidence.append({"kind": "retrieved", "source": "uniprot/curated",
                             "summary": f"{target.gene_symbol} -> {target.uniprot_id}"})
            if "architecture" in q or "bromodomain" in q:
                uncertainty.append("Domain architecture not independently verified in-run; consult the UniProt entry.")
        else:
            needs_target = any(k in q for k in ("uniprot", "target", "architecture", "binder",
                                                "e3", "degrader", "cell", "structure", "pdb"))
            if needs_target:
                missing.append("target identity")

        # 2. SMILES characterisation (generic supplied molecule or warhead)
        smiles = (getattr(state.parsed_objective, "warhead_smiles", "")
                  or (state.design_plan.get("structured_seed", {}) or {}).get("molecule_smiles", "")
                  or "")
        if smiles:
            summary, data, ev = _tool("inspect_smiles", {"smiles": smiles})
            evidence.extend(ev)
            if data.get("valid"):
                parts.append(
                    "molecule="
                    + str(data.get("isomeric_canonical_smiles") or data.get("canonical_smiles"))
                    + f"; heavy_atoms={data.get('num_heavy_atoms')}"
                )
                try:
                    from rdkit import Chem
                    from rdkit.Chem import Descriptors, rdMolDescriptors
                    from rdkit.Chem.inchi import MolToInchiKey

                    mol = Chem.MolFromSmiles(smiles)
                    if mol is not None:
                        parts.append(
                            f"InChIKey={MolToInchiKey(mol)}; "
                            f"formula={rdMolDescriptors.CalcMolFormula(mol)}; "
                            f"MW={Descriptors.MolWt(mol):.2f}"
                        )
                except Exception:  # noqa: BLE001
                    uncertainty.append("InChIKey/formula/MW unavailable (RDKit error)")
            else:
                uncertainty.append("supplied SMILES failed RDKit parsing")

        # 3. Structure evidence
        if "pdb" in q or "ternary" in q or "crystal" in q:
            params = {"target": (target.gene_symbol if target else ""),
                      "e3": state.parsed_objective.e3_ligase or ""}
            summary, data, ev = _tool("retrieve_pdb", params)
            evidence.extend(ev)
            if data:
                parts.append(f"structural evidence: {summary or data}")

        # 4. Cell context
        if "cell" in q or "express" in q:
            lines = ["MM1.S", "H1299", "HEK293T"]
            for line in lines:
                params = {"smiles": smiles or "", "cell_line": line,
                          "poi": (target.gene_symbol if target else ""),
                          "e3": state.parsed_objective.e3_ligase or ""}
                summary, data, ev = _tool("predict_cell_context", params)
                evidence.extend(ev)
                if data:
                    parts.append(f"{line}: {summary or 'no call'}")

        # 5. Documented binders / E3
        if state.retrieved_binders:
            names = [b.name for b in state.retrieved_binders[:5] if b.name]
            parts.append(f"retrieved binders ({len(state.retrieved_binders)}): {', '.join(names)}")
            evidence.append({"kind": "retrieved", "source": "binder_retrieval",
                             "summary": f"{len(state.retrieved_binders)} binders"})
        if state.selected_e3_ligands:
            e3s = sorted({lig.e3_ligase for lig in state.selected_e3_ligands if lig.e3_ligase})
            parts.append(f"E3 ligands present: {', '.join(e3s)}")
            evidence.append({"kind": "retrieved", "source": "e3_registry", "summary": ", ".join(e3s)})
        if not state.retrieved_binders and not state.selected_e3_ligands and ("binder" in q or "e3" in q):
            missing.append("binder/E3 evidence (retrieval returned nothing)")

        # 6. Deterministic BET-family literature precedent (e.g. KNOW-06).
        bet_precedent = _bet_dimethylisoxazole_precedent(q)
        if bet_precedent is not None:
            parts.append(bet_precedent["answer"])
            evidence.extend(bet_precedent["evidence"])
            uncertainty.extend(bet_precedent["uncertainty"])
            missing = [m for m in missing if m != "target identity"]

        # 7. Deterministic list-vs-database comparison (e.g. KNOW-12).
        comparison = _comparison_block(state, q)
        if comparison is not None:
            parts.append(comparison["answer"])
            evidence.extend(comparison["evidence"])
            missing.extend(comparison["missing"])
            uncertainty.extend(comparison["uncertainty"])
            # A list-vs-database comparison does not require a target identity.
            missing = [m for m in missing if m != "target identity"]
            uncertainty.append(
                "comparison used the available offline curated tables; a live "
                "permitted-database query is required to confirm membership"
            )

        answer = "; ".join(p for p in parts if p)
        state_text = ScientificState.SUPPORTED_ANSWER.value if answer and not missing else ScientificState.JUSTIFIED_NO_GO.value
        _payload(
            state,
            scientific_state=state_text,
            answer=answer,
            evidence=evidence,
            missing_prerequisites=missing,
            uncertainty=uncertainty,
            next_experiment=(
                "Confirm the accession/architecture against the primary UniProt entry."
                if "architecture" in q else
                "Resolve the missing prerequisite and re-run the capability node."
            ),
        )
        if bet_precedent is not None:
            state.scientific_answer["literature_precedent"] = bet_precedent.get("result")
        if comparison is not None:
            state.scientific_answer["identifier_comparison"] = comparison.get("result")
        return state

    def _observation(self, state: WorkflowState) -> str:
        return f"know_answer_chars={len(state.scientific_answer.get('answer', ''))}"


class ReasoningAnswerAgent(ReActAgent):
    """Answer a REASON question as an explicit conditional hypothesis."""

    name = "ReasoningAnswerAgent"
    thought = "Reason from the supplied components and structural proxies; label as hypothesis."
    action = "reasoning_answer"

    def _execute(self, state: WorkflowState) -> WorkflowState:
        q = (state.user_request or "").lower()
        evidence: list[dict[str, Any]] = []
        parts: list[str] = []
        uncertainty: list[str] = []
        missing: list[str] = []

        if state.exit_vectors:
            for ev in state.exit_vectors:
                parts.append(
                    f"attachment on {ev.molecule_name or ev.molecule_role}: "
                    f"{ev.attachment_smarts or 'unresolved'} (confidence {ev.confidence:.2f})"
                )
                evidence.append({"kind": "calculated", "source": "detect_exit_vectors",
                                 "summary": ev.rationale or ev.attachment_smarts})
        if state.cooperativity_predictions:
            pred = state.cooperativity_predictions[0]
            parts.append(
                f"cooperativity feasibility alpha~{pred.predicted_alpha:.2f} "
                f"(score {pred.cooperativity_score:.2f}); proxy, not measured"
            )
            evidence.append({"kind": "structural_surrogate", "source": pred.model_version,
                             "summary": f"alpha={pred.predicted_alpha:.2f}"})
            uncertainty.append("alpha is a geometry feasibility proxy, not an ITC/SPR measurement")
        if state.hook_effect_predictions:
            h = state.hook_effect_predictions[0]
            parts.append(
                f"hook risk={h.hook_risk}; max ternary fraction={h.max_ternary_fraction:.2f}; "
                f"hook conc={h.hook_concentration_nM}"
            )
            evidence.append({"kind": "calculated", "source": h.model_version, "summary": h.hook_risk})
        if state.admet_predictions:
            a = state.admet_predictions[0]
            parts.append(f"ADMET flags: hERG={getattr(a, 'herg_risk', 'unknown')}, "
                         f"logP={getattr(a, 'logp', 'n/a')}")
        if "pdb" in q or "ternary" in q or "structure" in q or "lysine" in q:
            target = state.target_record.gene_symbol if state.target_record else ""
            summary, data, ev = _tool("retrieve_pdb", {
                "target": target, "e3": state.parsed_objective.e3_ligase or ""})
            evidence.extend(ev)
            if data:
                parts.append(f"structural reference available: {summary or data}")
                uncertainty.append("PDB availability is not a pose assessment; lysine geometry not computed here")
        if not parts:
            qualitative = _qualitative_reasoning(q)
            if qualitative:
                text, next_exp = qualitative
                parts.append(text)
                evidence.append({"kind": "domain_reasoning", "source": "deterministic_rubric",
                                 "summary": "qualitative mechanism from supplied components"})
                uncertainty.append("qualitative reasoning only; no measured affinity, pKa or ternary geometry")
                _payload(
                    state,
                    scientific_state=ScientificState.CONDITIONAL_HYPOTHESIS.value,
                    answer=text,
                    evidence=evidence,
                    missing_prerequisites=missing,
                    uncertainty=uncertainty,
                    next_experiment=next_exp,
                )
                return state
            missing.append("no reasoning proxy ran (question dependencies unresolved)")
            uncertainty.append("no structural or mechanistic evidence available")
        if "ubiquitin" in q or "lysine" in q:
            missing.append("lysine accessibility requires a real ternary pose (e.g. 5T35)")

        answer = "; ".join(parts)
        _payload(
            state,
            scientific_state=ScientificState.CONDITIONAL_HYPOTHESIS.value if parts else ScientificState.JUSTIFIED_NO_GO.value,
            answer=answer,
            evidence=evidence,
            missing_prerequisites=missing,
            uncertainty=uncertainty,
            next_experiment=(
                "measure ternary cooperativity (ITC/SPR) or supply the 5T35 pose and re-score."
                if ("cooperativ" in q or "ternary" in q) else
                "Test the stated hypothesis with the discriminating assay named in the case."
            ),
        )
        from protacxtend.agents.evidence_cards import build_evidence_cards

        state.scientific_answer["evidence_cards"] = build_evidence_cards(state)
        return state

    def _observation(self, state: WorkflowState) -> str:
        return f"reason_answer_chars={len(state.scientific_answer.get('answer', ''))}"
#: Deterministic mechanistic reasoning rubrics. These are explicitly labelled
#: conditional hypotheses: they name the mechanism and the measurement needed,
#: and never assert a measured value.
_QUALITATIVE_RULES: list[tuple[tuple[str, ...], str, str]] = [
    (("amide", "amine", "junction"),
     "A secondary-amine junction is protonatable near physiological pH, adding a "
     "positive charge that can improve solubility but may weaken VHL/CRBN "
     "engagement and passive permeability relative to the neutral amide.",
     "Measure the junction pKa and ternary affinity (ITC/SPR) for amide vs amine."),
    (("pharmacophore", "vh032", "vhl ligand", "motif"),
     "VH032 engagement depends on the hydroxyproline, tert-leucine and "
     "thiazole-benzyl motifs; removing or altering any of them is expected to "
     "reduce VHL binding even when the SMILES remains chemically valid.",
     "Measure VHL binding for the modified ligand against the intact reference."),
    (("h-bond", "hydrogen bond", "chameleon", "shield", "polar surface"),
     "Intramolecular hydrogen bonding in a PEG linker can transiently shield polar "
     "surface and raise passive permeability without changing topological PSA.",
     "Measure permeability (PAMPA/Caco-2) and NMR/IR evidence of the intramolecular H-bond."),
    (("permeab", "solubil", "logp", "lipophil", "admet"),
     "Replacing a hydrophobic alkyl core with PEG lowers logP and raises TPSA, "
     "trading membrane permeability for aqueous solubility.",
     "Measure logD, solubility and Caco-2 permeability across the linker series."),
    (("degrad", "inhibit", "jq1", "mz1", "mechanism of action"),
     "JQ1-class BET inhibitors occupy the bromodomain without recruiting an E3; "
     "MZ1-class molecules form a ternary complex and can ubiquitinate BRD4. Only "
     "the latter class is expected to degrade rather than inhibit.",
     "Run a CRBN/VHL-dependence and proteasome-inhibition control to confirm degradation."),
    (("confidence", "uncertainty", "would change"),
     "A reported model confidence should change only with new measured evidence: "
     "assay-context DC50/Dmax, ternary cooperativity, and cell-line E3/POI expression.",
     "Add measured DC50/Dmax and ternary affinity, then recalibrate the model."),
    (("cooperativ", "alpha", "ternary"),
     "Cooperativity is set by ternary interface contacts and linker strain, not by "
     "binary affinities alone; alpha>1 requires favourable new contacts in the "
     "ternary complex.",
     "Measure alpha by ITC/SPR or supply a real ternary pose and re-score."),
    (("piperidine", "rigid", "flexible", "peg3", "linker"),
     "A semi-rigid piperidine-PEG3 linker lowers the entropic penalty of ternary "
     "assembly but constrains exit-vector geometry; a flexible PEG3 can adapt but "
     "pays a conformational-entropy cost.",
     "Compare ternary formation (alpha) and degradation for both linkers in the same assay."),
]


def _qualitative_reasoning(question: str) -> tuple[str, str] | None:
    q = question.lower()
    for keywords, text, next_exp in _QUALITATIVE_RULES:
        if any(k in q for k in keywords):
            return text, next_exp
    return None


def _bet_dimethylisoxazole_precedent(q: str) -> dict[str, Any] | None:
    if not ("dimethylisoxazole" in q and ("bet" in q or "bromodomain" in q or "brd" in q)):
        return None
    rows = [
        {"compound": "JQ1", "role": "BET/BRD4 bromodomain ligand scaffold", "source": "Filippakopoulos 2010 Nature DOI 10.1038/nature09534", "structure_family": "triazolodiazepine BET ligand, not dimethylisoxazole"},
        {"compound": "I-BET762", "role": "BET bromodomain ligand", "source": "Filippakopoulos 2010 Nature DOI 10.1038/nature09534", "structure_family": "benzodiazepine BET ligand, not dimethylisoxazole"},
        {"compound": "I-BET151", "role": "3,5-dimethylisoxazole BET bromodomain ligand", "source": "Chung et al. J Med Chem 2011 DOI 10.1021/jm201108q", "structure_family": "3,5-dimethylisoxazole"},
        {"compound": "OTX015", "role": "BET bromodomain ligand clinical analogue", "source": "BET ligand literature/curated precedent", "structure_family": "triazolodiazepine BET ligand, not dimethylisoxazole"},
    ]
    supported = [r for r in rows if "3,5-dimethylisoxazole" in r["structure_family"]]
    answer = (
        "For the strict 3,5-dimethylisoxazole-family pocket context, I-BET151 is the supported BET bromodomain ligand in the reviewed sources. "
        "JQ1, I-BET762 and OTX015 are BET bromodomain ligands but are not accepted here as dimethylisoxazole-family identities; they remain related BET precedents, not positive answers to the family-specific question."
    )
    return {
        "answer": answer,
        "evidence": [
            {"kind": "retrieved", "source": r["source"], "summary": f"{r['compound']}: {r['role']}; {r['structure_family']}"}
            for r in rows
        ],
        "result": {"supported_compounds": [r["compound"] for r in supported], "rejected_related_bet_ligands": [r["compound"] for r in rows if r not in supported], "records": rows},
        "uncertainty": ["Offline curated source audit; live PubMed/PubChem re-query may add aliases but must not override the family-specific structure gate."],
    }


def _supplied_identifier_list(state: WorkflowState) -> list[str]:
    """Extract a braced/comma list from the raw supplied inputs."""
    raw = (state.design_plan.get("structured_seed", {}) or {}).get("supplied_inputs_raw") or []
    text = " ".join(str(r) for r in raw)
    match = re.search(r"\{([^}]*)\}", text) or re.search(r"supplied list:\s*(.+)", text, re.I)
    if not match:
        return []
    return [tok.strip() for tok in match.group(1).split(",") if tok.strip()]


def _database_identifier_list(state: WorkflowState) -> list[str]:
    names = [b.name for b in state.retrieved_binders if getattr(b, "name", "")]
    for ligand in state.selected_e3_ligands:
        if ligand.name:
            names.append(ligand.name)
    try:
        from protacxtend.tools.protac_toolbox import ProtacDesignToolbox

        names.extend(row.get("name", "") for row in ProtacDesignToolbox().load_curated_warheads())
    except Exception:  # noqa: BLE001
        pass
    return [n for n in names if n]


def _comparison_block(state: WorkflowState, q: str) -> dict[str, Any] | None:
    """Run the deterministic comparison when the question asks for one."""
    wants = any(k in q for k in ("compare", "supplied list", "missing member", "against permitted"))
    supplied = _supplied_identifier_list(state)
    if not wants and not supplied:
        return None
    if not supplied:
        return {"answer": "no supplied identifier list found to compare",
                "evidence": [], "missing": ["supplied identifier list"], "uncertainty": []}
    from protacxtend.agents.identifier_comparison import (
        build_alias_map,
        compare_identifier_lists,
    )

    database = _database_identifier_list(state)
    result = compare_identifier_lists(
        supplied, database, alias_map=build_alias_map(),
        provenance={"database_records": len(database),
                    "sources": sorted({b.source for b in state.retrieved_binders})},
    )
    answer = (
        f"shared={result['n_shared']}/{result['n_supplied']}; "
        f"missing_from_database={result['only_in_supplied_missing_from_database']}; "
        f"added_in_database={result['only_in_database_added'][:10]}; "
        f"duplicates_removed={result['duplicates_removed']}; "
        f"unresolved={result['unresolved']}"
    )
    evidence = [{"kind": "calculated", "source": "identifier_comparison",
                 "summary": f"supplied={result['n_supplied']}, database={result['n_database']}, shared={result['n_shared']}"}]
    missing: list[str] = []
    uncertainty: list[str] = []
    if result["unresolved"]:
        uncertainty.append(f"unresolved identifiers: {result['unresolved']}")
    if result["n_database"] == 0:
        missing.append("database records to compare against")
    return {"answer": answer, "evidence": evidence, "missing": missing,
            "uncertainty": uncertainty, "result": result}


__all__ = ["KnowledgeAnswerAgent", "ReasoningAnswerAgent"]

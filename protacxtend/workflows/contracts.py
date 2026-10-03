"""Command contracts for the 14 PROTACxtend research commands + goal-typed
task-graph builder.

Rules:
- every command has a DISTINCT contract (scientific question, capabilities,
  gates, output schema, abstention) — the old behaviour of 12 commands
  emitting the same plan was a menu, not a system;
- /plan builds a goal-typed DAG: nodes are capabilities resolved from the
  installed toolkit, with dependencies, evidence gates, alternatives,
  estimated effort and artifacts. The graph branches on parsed features
  (mutation/isoform, E3 mode, goal verb, target context) so two biologically
  different requests produce different graphs — never a template with
  substituted names;
- no command executes design merely to display a plan.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from protacxtend.request.model import RequestUnderstanding

COMMANDS = (
    "plan", "investigate", "reason", "compare", "design", "optimize", "structure",
    "selectivity", "degradation", "admet", "synthesis", "experiment", "evidence", "run",
)


@dataclass
class NodeSpec:
    node_id: str
    capability: str                    # toolkit capability name
    tool: str = ""                     # concrete tool / registry entry
    depends_on: list[str] = field(default_factory=list)
    evidence_gate: str = ""            # human-readable gate; required evidence to pass
    alternative: str = ""              # alternative node/capability when primary fails
    effort: str = "M"                  # S/M/L
    artifacts: list[str] = field(default_factory=list)
    note: str = ""


@dataclass
class GoalPlan:
    goal_type: str                     # investigate|design|mechanism|compare|optimize|experiment|...
    interpretation_line: str = ""
    nodes: list[NodeSpec] = field(default_factory=list)
    gates: list[str] = field(default_factory=list)
    alternatives: list[str] = field(default_factory=list)
    evidence_needed: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    signature: str = ""                # stable hash of node structure (plan-diversity tests)


# ---------------------------------------------------------------------------
# Goal classifier: from the shared RequestUnderstanding + utterance features
# ---------------------------------------------------------------------------
def classify_goal(u: RequestUnderstanding) -> str:
    action = u.action
    if action == "plan":
        return "plan"
    if action == "reason":
        return "mechanism"
    if action == "optimize":
        return "optimize"
    if action == "experiment":
        return "experiment"
    if action == "compare":
        return "compare"
    if action == "design":
        return "design"
    if action == "investigate":
        return "investigate"
    if action in ("structure",):
        return "structure"
    if action in ("selectivity",):
        return "selectivity"
    if action in ("degradation",):
        return "degradation"
    if action in ("admet",):
        return "admet"
    if action in ("synthesis",):
        return "synthesis"
    if action in ("evidence",):
        return "evidence"
    if action == "run":
        return "run"
    return "investigate"


@dataclass
class CommandContract:
    command: str
    scientific_question: str
    capabilities: list[str]            # selected from installed toolkit
    output_schema: dict[str, Any]
    gate_criteria: list[str]
    abstention: str
    real_work: str                     # what real computation/retrieval happens


CONTRACTS: dict[str, CommandContract] = {
    "plan": CommandContract(
        command="plan",
        scientific_question="What investigation should run for this user goal, which evidence is needed before any design/execution path, and which installed capabilities form the task graph?",
        capabilities=["request_understanding", "target_resolver", "evidence_retrieval",
                      "degradation_models", "e3_opportunity", "admet_scoring"],
        output_schema={"interpretation": "str", "goal_type": "str", "nodes": "list[NodeSpec]",
                       "evidence_needed": "list[str]", "gates": "list[str]",
                       "alternatives": "list[str]", "artifacts": "list[str]",
                       "signature": "str"},
        gate_criteria=["target identity tool-verified or explicit clarification",
                       "every design/execution stage gated on a stated evidence need"],
        abstention="unresolvable target / no installed capability for the goal -> explicit limitation, no fabricate",
        real_work="selects capabilities from the installed toolkit catalog, builds a goal-typed DAG; does NOT execute design"),
    "investigate": CommandContract(
        command="investigate",
        scientific_question="Target biology and degradation rationale: what is known (observed), computed, and missing for this target?",
        capabilities=["target_resolver", "evidence_retrieval", "degradation_models", "e3_opportunity"],
        output_schema={"target": "TargetResolution", "finding_groups": "dict[dimension, list[Claim]]",
                       "missing": "list[str]", "evidence_graph": "str path"},
        gate_criteria=["claims carry provenance", "observed claims carry measured sources"],
        abstention="no target -> question",
        real_work="retrieves curated binder counts, measured degradation precedent, E3 rows into the evidence graph"),
    "reason": CommandContract(
        command="reason",
        scientific_question="Given measured binding (or measured degradation) and a conflicting cellular outcome, which competing mechanisms explain it, and which tests discriminate?",
        capabilities=["target_resolver", "degradation_models", "ternary_feasibility", "admet_scoring"],
        output_schema={"hypotheses": "list[{hypothesis, dimension, evidence_for, evidence_against, discriminating_tests}]",
                       "conclusion": "str", "evidence_graph": "str path"},
        gate_criteria=["hypotheses are labelled inferred/computed, never observed",
                       "each hypothesis maps to >=1 discriminating test"],
        abstention="no candidate/claim supplied -> ask for SMILES or measured claims",
        real_work="maps candidate facts to mechanism axes and testable predictions"),
    "compare": CommandContract(
        command="compare",
        scientific_question="Across candidate molecules or series, which differences in descriptors/activity explain the outcome, on a shared evidence scale?",
        capabilities=["chemistry_descriptors", "degradation_models", "admet_scoring"],
        output_schema={"comparison": "list[{molecule, features, dimension_scores, verdict}]",
                       "evidence_graph": "str path"},
        gate_criteria=["same feature set / units across rows", "no averaged mixing of measured and predicted"],
        abstention="<2 molecules or no properties -> abstain",
        real_work="computes RDKit descriptors + per-dimension scores from tools"),
    "design": CommandContract(
        command="design",
        scientific_question="Assemble source-backed components (warhead x linker x E3 ligand) into chemically valid candidates with provenance.",
        capabilities=["binder_retrieval", "warhead_selection", "e3_selection", "linker_generation", "construction", "validation"],
        output_schema={"candidates": "list[CandidateRecord]", "valid": "int", "invalid_reasons": "dict",
                       "sources": "list[str]", "evidence_graph": "str path"},
        gate_criteria=["components carry DOI/assay provenance", "validity via RDKit; failures kept in denominator"],
        abstention="no supportable component -> typed abstention with stage census",
        real_work="executes the deterministic assembly pipeline (fixed 2026-09-24)"),
    "optimize": CommandContract(
        command="optimize",
        scientific_question="Given a measured series (e.g. degradation good, permeability poor), which structural changes trade exposure for risk of losing ternary activity, and which comparators should be synthesised?",
        capabilities=["chemistry_descriptors", "linker_scoring", "ternary_feasibility", "admet_scoring"],
        output_schema={"proposals": "list[{change, dimension_impact, ternary_loss_risk, rationale}]",
                       "comparison": "list[str]", "evidence_graph": "str path"},
        gate_criteria=["changes derived from measured series properties (not invented numbers)",
                       "ternary loss risk labelled inferred"],
        abstention="no series input -> ask for SMILES + measured degradation/permeability",
        real_work="RDKit descriptors on the series, linker-class swap proposals with ternary-length risk notes"),
    "structure": CommandContract(
        command="structure",
        scientific_question="What structural/ternary evidence exists or can be computed for this candidate, and what is explicitly NOT validated?",
        capabilities=["ternary_feasibility", "docking_adapters"],
        output_schema={"ternary_scores": "list[float]", "dockq_note": "str",
                       "evidence_graph": "str path"},
        gate_criteria=["predicted-structure DockQ NOT_VALIDATED must be stated", "no coordinates claimed"],
        abstention="no candidate -> ask; docking backends unavailable -> limitation",
        real_work="runs score-level ternary feasibility when a candidate SMILES is supplied"),
    "selectivity": CommandContract(
        command="selectivity",
        scientific_question="Which selectivity-relevant evidence exists (E3 tissue context, paralog families, expression) and what can it support?",
        capabilities=["e3_opportunity", "cell_context_models"],
        output_schema={"e3_tissue_notes": "list[str]", "paralog_notes": "list[str]",
                       "evidence_graph": "str path"},
        gate_criteria=["expression-only never recommends an E3", "no selectivity claim from identity codes"],
        abstention="no target -> question",
        real_work="reads E3 catalog + expression axes from module data"),
    "degradation": CommandContract(
        command="degradation",
        scientific_question="What do the trained degradation models predict (with uncertainty and applicability domain) for each supplied candidate?",
        capabilities=["degradation_models", "applicability_domain"],
        output_schema={"predictions": "list[{smiles, dc50_nM, dmax_pct, ci, ood, model_version}]",
                       "label": "str='computational prediction; not measured'"},
        gate_criteria=["model_version + heuristic_fallback flag recorded", "no 'measured' labelling"],
        abstention="no valid SMILES -> abstain",
        real_work="calls the batched degradation endpoint (M4/M5/TACK-style + chemprop)"),
    "admet": CommandContract(
        command="admet",
        scientific_question="Physicochemical risk flags (descriptor- and ADMET-AI-based); PK explicitly not modelled.",
        capabilities=["admet_scoring", "chemistry_descriptors"],
        output_schema={"flags": "list[{rule, value, verdict}]", "scope": "str='risk flags only; no PK'"},
        gate_criteria=["PK explicitly out of scope", "Ro5-centric applicability stated"],
        abstention="no valid SMILES -> abstain",
        real_work="RDKit descriptors + ADMET-AI/rule composite"),
    "synthesis": CommandContract(
        command="synthesis",
        scientific_question="Which retrosynthesis engines can propose routes for this molecule, and what is their availability on this host?",
        capabilities=["retrosynthesis_engines"],
        output_schema={"engines": "list[{engine, available, routes, provenance}]",
                       "note": "str='route proposals are computational; none are tested routes'"},
        gate_criteria=["engines report availability honestly (no fabricated routes)"],
        abstention="no SMILES or engines unavailable -> limitation",
        real_work="probes ASKCOS/AiZynthFinder/OpenNMT status; runs one-step routes when available"),
    "experiment": CommandContract(
        command="experiment",
        scientific_question="Which assay sequence (with controls and effort) discriminates the competing hypotheses from /reason (or validates /optimize changes)?",
        capabilities=["assay_protocols"],
        output_schema={"tests": "list[{hypothesis, assay, discriminator, controls, effort, expected_outcomes}]"},
        gate_criteria=["every hypothesx gets >=1 discriminating test", "controls mandatory"],
        abstention="no hypotheses supplied -> ask for /reason output",
        real_work="maps hypothesis -> discriminating assay with controls from protocol bank"),
    "evidence": CommandContract(
        command="evidence",
        scientific_question="What does the shared evidence graph contain for this target/candidate, including conflicts?",
        capabilities=["evidence_graph"],
        output_schema={"claims": "list[Claim]", "conflicts": "list[Claim]",
                       "graph_path": "str"},
        gate_criteria=["includes conflicting evidence, provenance, uncertainty"],
        abstention="empty graph -> report empty, do not fabricate",
        real_work="queries/persists the shared evidence graph"),
    "run": CommandContract(
        command="run",
        scientific_question="Execute the selected goal-typed task graph; replan when an observation contradicts an assumption or a tool fails.",
        capabilities=["graph_executor", "binder_retrieval", "degradation_models", "admet_scoring", "ternary_feasibility"],
        output_schema={"trace": "list[{node, tool, observation, gate_decision, replan}]",
                       "evidence_graph": "str path", "status": "str"},
        gate_criteria=["every executed stage writes evidence to the graph", "negative/conflicting result changes next action and is logged"],
        abstention="no goal plan -> build one; no supportable stage -> abstain",
        real_work="executes the DAG with real tools; keeps intermediate results visible and resumable"),
}

#: catch-all: an unknown command must never silently reuse another contract
def ensure_distinct() -> None:
    quests = {c.scientific_question for c in CONTRACTS.values()}
    assert len(quests) == len(CONTRACTS), "two commands share a scientific question (overlap)"
    outs = {tuple(sorted(c.output_schema)) for c in CONTRACTS.values()}
    assert len(outs) == len(CONTRACTS), "two commands share an output schema (overlap)"


# ---------------------------------------------------------------------------
# Capability selection from the installed toolkit
# ---------------------------------------------------------------------------
def installed_capabilities() -> dict[str, str]:
    """capability -> best installed tool name (from toolkit catalog + registry)."""
    caps: dict[str, str] = {}
    try:
        from protacxtend.toolkit import catalog
        for tool in catalog.plan_all_tools():
            name = tool.get("tool_name", "")
            cat = tool.get("category", "")
            if cat and name:
                caps.setdefault(cat, name)
    except Exception:  # noqa: BLE001
        pass
    known = {
        "request_understanding": "protacxtend.request", "target_resolver": "uniprot/curated resolver",
        "evidence_retrieval": "research/deep_research", "degradation_models": "degradation_endpoint",
        "e3_opportunity": "rank_e3_ligases", "admet_scoring": "admet_predictors",
        "chemistry_descriptors": "rdkit.descriptors", "linker_scoring": "linker_scoring",
        "ternary_feasibility": "ternary_engine", "binder_retrieval": "chembl/curated binders",
        "warhead_selection": "warhead_selector", "e3_selection": "e3_selector",
        "linker_generation": "linker_generator", "construction": "molecular_constructor",
        "retrosynthesis_engines": "retrosynthesis_engines", "assay_protocols": "validation protocols",
        "cell_context_models": "cell_context_selector", "graph_executor": "workflows.executor",
        "docking_adapters": "vina/gnina/diffdock", "evidence_graph": "protacxtend.evidence",
    }
    for k, v in known.items():
        caps.setdefault(k, v)
    return caps


# ---------------------------------------------------------------------------
# Goal-typed graph builder (branching; never a template with substituted names)
# ---------------------------------------------------------------------------
def build_goal_plan(u: RequestUnderstanding) -> GoalPlan:
    goal = classify_goal(u)
    caps = installed_capabilities()
    t = u.primary_target
    tname = t.symbol if t and t.status in ("verified", "tentative") else (t.symbol if t else "?")

    nodes: list[NodeSpec] = []
    evidence_needed: list[str] = []
    gates: list[str] = []

    def add(node_id, capability, depends=None, gate="", alternative="", effort="M", artifacts=None, note=""):
        nodes.append(NodeSpec(node_id=node_id, capability=capability,
                              tool=caps.get(capability, capability),
                              depends_on=depends or [],
                              evidence_gate=gate, alternative=alternative,
                              effort=effort, artifacts=artifacts or [], note=note))

    # ---------------- /plan (and shared investigation core) -------------------
    if goal in ("plan", "investigate"):
        add("target_identity", "target_resolver", gate="verified identity (tool)", effort="S",
            artifacts=["uniprot record", "alternatives"])
        add("target_context", "evidence_retrieval", depends=["target_identity"],
            gate="observed context (family/domain/disease)", effort="M",
            artifacts=["context notes"])
        add("target_baseline", "evidence_retrieval", depends=["target_identity"],
            gate="measured binder count or literature", effort="M", artifacts=["binder census"])
        add("degradation_rationale", "evidence_retrieval", depends=["target_identity"],
            gate="measured degradation precedent (rows+DOIs) or explicit missing", effort="S",
            artifacts=["precedent table"])
        add("e3_evaluation", "e3_opportunity", depends=["target_identity"],
            gate="delegated -> options+precedent; explicit -> verify ligand availability",
            alternative="recruiter-only fallback when expression data absent", effort="M",
            artifacts=["e3 rows", "precedent"])
        # goal-specific branching -------------------------------------------------
        if u.mutation:
            add("mutation_context", "evidence_retrieval", depends=["target_identity"],
                gate=f"mutation {u.mutation} biological context + allele-specific tools", effort="M",
                artifacts=[f"mutation notes ({u.mutation})"])
            add("allele_specific_binder_search", "binder_retrieval", depends=["mutation_context"],
                gate="binder set restricted to allele/substitution if available",
                alternative="pan-wild-type binder set with allele caveat", effort="L",
                artifacts=["allele binder census"])
        # target-specific biology notes (literature-derived context, not measured)
        _notes = {
            "EGFR": "approved-inhibitor-derivatization warhead space (erlotinib/gefitinib/afatinib family); "
                    "kinase-domain inhibitor scaffolds; ERBB-family selectivity context",
            "KRAS": "G12C covalent-handle warhead space (switch-II pocket); shallow GTPase pocket; "
                    "mutation-specific binder evidence required for allele-restricted degraders",
            "BRD4": "bromodomain inhibitor warhead space (JQ1-class); BET-family selectivity context",
        }
        if tname in _notes:
            add(f"target_specific_notes_{tname.lower()}", "evidence_retrieval",
                depends=["target_context"],
                gate=f"context notes for {tname}: {_notes[tname][:70]}…", effort="S",
                artifacts=[f"notes: {_notes[tname][:80]}"])
        if goal == "plan":
            if u.e3.mode == "delegated":
                evidence_needed.append("measured E3-preference evidence for the target before any E3 recommendation")
                gates.append("e3_gate: recommendation only with measured precedent or explicit user choice")
            add("warhead_path_gate", "warhead_selection", depends=["target_baseline", "degradation_rationale"],
                gate="decision: approved-inhibitor-derived vs de-novo vs covalent handle (target-specific)",
                effort="S")
            add("linker_scaffold_gate", "linker_generation", depends=["warhead_path_gate"],
                gate="linker class choice justified by ternary length evidence", effort="S")
            add("ternary_feasibility_gate", "ternary_feasibility", depends=["linker_scaffold_gate"],
                gate="score-level feasibility; DockQ NOT_VALIDATED", effort="M")
            add("validation_proposal", "assay_protocols", depends=["ternary_feasibility_gate"],
                gate="controls enumerated; nothing executed", effort="S", artifacts=["validation protocol"])
    # ---------------- design ----------------------------------------------------
    elif goal == "design":
        add("target_identity", "target_resolver", gate="verified identity (tool)", effort="S")
        add("binder_retrieval", "binder_retrieval", depends=["target_identity"],
            gate="source-backed binders (live or cited)", effort="M")
        add("warhead_selection", "warhead_selection", depends=["binder_retrieval"],
            gate="attachment vector marked; chemist-review provenance", effort="S")
        add("e3_selection", "e3_selection", depends=["target_identity"],
            gate="DOI-cited E3 rows; demo rows forbidden", effort="S")
        add("linker_generation", "linker_generation", depends=["warhead_selection"], effort="M")
        add("construction_validation", "construction", depends=["linker_generation", "e3_selection"],
            gate="RDKit validity; failures in denominator", effort="M")
        add("degradation_assess", "degradation_models", depends=["construction_validation"],
            gate="predicted label; applicability-domain check; not measured", effort="M")
        add("admet_gate", "admet_scoring", depends=["construction_validation"],
            gate="exposure flags; PK out of scope", effort="S")
        add("ternary_triage", "ternary_feasibility", depends=["construction_validation"],
            gate="score-level; DockQ NOT_VALIDATED", effort="M")
    # ---------------- mechanism (/reason) ---------------------------------------
    elif goal == "mechanism":
        add("claim_ingestion", "evidence_graph", gate="candidate facts typed (binding measured; degradation measured/predicted)",
            effort="S", artifacts=["claims"])
        add("mechanism_enumeration", "degradation_models", depends=["claim_ingestion"],
            gate="hypotheses mapped to axes; each labelled inferred", effort="M",
            artifacts=["hypotheses"])
        add("test_selection", "assay_protocols", depends=["mechanism_enumeration"],
            gate="discriminating tests with controls", effort="S", artifacts=["tests"])
    # ---------------- optimize --------------------------------------------------
    elif goal == "optimize":
        add("series_descriptors", "chemistry_descriptors", gate="RDKit descriptors on supplied series", effort="S")
        add("exposure_gap", "admet_scoring", depends=["series_descriptors"], gate="permeability/efflux flags per row", effort="S")
        add("ternary_risk", "ternary_feasibility", depends=["series_descriptors"],
            gate="linker-length/rotatable risk inferred, not measured", effort="M")
        add("change_proposals", "linker_scoring", depends=["exposure_gap", "ternary_risk"],
            gate="proposed changes quantify exposure gain AND ternary loss risk", effort="M")
    # ---------------- experiment ------------------------------------------------
    elif goal == "experiment":
        add("hypothesis_ingest", "evidence_graph", gate="hypotheses or claims supplied", effort="S")
        add("test_design", "assay_protocols", depends=["hypothesis_ingest"],
            gate="assay x hypothesis x controls x expected outcomes", effort="M")
    # ---------------- compare ---------------------------------------------------
    elif goal == "compare":
        add("molecule_properties", "chemistry_descriptors", gate=">=2 molecules, same feature set", effort="S")
        add("dimension_scoring", "degradation_models", depends=["molecule_properties"], gate="per-dimension scores; measured/predicted kept separate", effort="M")
    # ---------------- structure / selectivity / degradation / admet / synthesis / evidence
    elif goal == "structure":
        add("ternary_feasibility", "ternary_feasibility", gate="score-level only; DockQ NOT_VALIDATED", effort="M")
    elif goal == "selectivity":
        add("e3_tissue_context", "e3_opportunity", gate="expression never recommends alone", effort="M")
        add("paralog_notes", "cell_context_models", depends=["e3_tissue_context"], gate="no identity-code selectivity claim", effort="S")
    elif goal == "degradation":
        add("degradation_predict", "degradation_models", gate="model_version+fallback flag; predicted label", effort="M")
    elif goal == "admet":
        add("admet_flags", "admet_scoring", gate="PK out of scope; Ro5-centric stated", effort="S")
    elif goal == "synthesis":
        add("retro_status", "retrosynthesis_engines", gate="honest availability; no fabricated routes", effort="M")
    elif goal == "evidence":
        add("graph_query", "evidence_graph", gate="conflicts+provenance included; empty reported empty", effort="S")
    elif goal == "run":
        add("graph_execute", "graph_executor", gate="execute DAG; replan on conflict/failure", effort="L")

    interp = f"{goal} plan | {tname or 'unresolved target'}"
    sig_seed = "|".join(f"{n.node_id}:{n.depends_on}" for n in nodes)
    return GoalPlan(
        goal_type=goal, interpretation_line=interp, nodes=nodes, gates=gates,
        alternatives=[n.alternative for n in nodes if n.alternative],
        evidence_needed=evidence_needed,
        artifacts=sorted({a for n in nodes for a in n.artifacts}),
        signature=__import__("hashlib").sha1(sig_seed.encode()).hexdigest()[:12],
    )
"""TUI scientific command semantics: contracts, reasoning intents, context.

This module owns the SCIENTIFIC semantics for /plan, /investigate, /reason,
/design and /run. It does not invent evidence: every substantive statement
carries a tier (verified / computed / approximation / inferred / limitation /
failed_gate) and sections attach evidence rows with sources. Presentation code
renders the structured result; it does not reason.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# ── evidence tiers & glyphs (§11) ────────────────────────────────────────────
TIER_GLYPHS: dict[str, tuple[str, str]] = {
    "verified": ("✓", "VERIFIED / measured"),
    "computed": ("◆", "COMPUTED"),
    "approximation": ("~", "APPROXIMATION"),
    "inferred": ("?", "INFERRED"),
    "limitation": ("!", "LIMITATION"),
    "failed_gate": ("×", "FAILED GATE"),
}

TIER_BY_EVIDENCE_TYPE: dict[str, str] = {
    "EXPERIMENTAL": "verified", "CURATED_DATABASE": "verified",
    "STRUCTURAL": "computed", "CALCULATED": "computed",
    "MECHANISTIC_SIMULATION": "computed",
    "MODEL_PREDICTED": "approximation",
    "STRUCTURAL_PROXY": "approximation",
    "INFERRED": "inferred",
    "UNAVAILABLE": "limitation",
}


def tier_glyph(tier: str) -> str:
    t = TIER_GLYPHS.get(tier, ("·", tier.upper()))
    return t[0]


def tier_label(tier: str) -> str:
    return TIER_GLYPHS.get(tier, (tier, tier))[1]


def statement(text: str, tier: str = "inferred", source: str = "") -> dict[str, str]:
    return {"text": text, "tier": tier, "source": source}


# ── reasoning-intent classifier (§5) ─────────────────────────────────────────
REASONING_INTENTS = [
    "WHY_WORKS", "WHY_FAILS", "MECHANISM", "DESIGN_RATIONALE", "COMPARE",
    "TRADEOFF", "COUNTERFACTUAL", "EVIDENCE_SYNTHESIS", "UNCERTAINTY_ANALYSIS",
]

_INTENT_RULES: list[tuple[str, list[re.Pattern]]] = [
    ("WHY_FAILS", [re.compile(r"\b(fail|failed|didn'?t work|poor(ly)?|why not|unproductive|no degradation|absent)\b", re.I)]),
    ("COMPARE", [re.compile(r"\b(vs\.?|versus|compare|which .* more sense|or .* makes more sense)\b", re.I)]),
    ("DESIGN_RATIONALE", [re.compile(r"\b(linker|warhead|design choice|why is .* better than|why would)\b", re.I)]),
    ("COUNTERFACTUAL", [re.compile(r"\b(what if|would .* if|if .* were)\b", re.I)]),
    ("WHY_WORKS", [re.compile(r"\b(why .* works?|works?|good target|can work|makes? sense|would work|target|degradable)\b", re.I),
                   re.compile(r"\b(could|can|might) be (degraded|targeted)\b", re.I)]),
    ("MECHANISM", [re.compile(r"\b(mechanism|mode of action|how does)\b", re.I)]),
    ("UNCERTAINTY_ANALYSIS", [re.compile(r"\b(uncertain|confidence|reliab|how sure)\b", re.I)]),
    ("TRADEOFF", [re.compile(r"\b(tradeoff|trade-off|cost|pros and cons)\b", re.I)]),
]


def classify_reasoning_intent(query: str) -> str:
    q = (query or "").lower()
    for intent, patterns in _INTENT_RULES:
        if any(p.search(q) for p in patterns):
            return intent
    return "EVIDENCE_SYNTHESIS"


# ── roles: E3 families so "BRD4 and CRBN" parses as target + recruiter ───────
E3_FAMILIES = {"CRBN", "VHL", "MDM2", "XIAP", "IAP", "CIAP1", "CIAP", "RNF114",
               "RNF4", "DCAF11", "DCAF15", "DCAF16", "FBXO22", "FEM1B", "AHR", "KEAP1", "DCAF1"}
# English tokens the entity extractor may mis-tag as proteins; never targets.
_SYMBOL_STOPLIST = {"WHY", "WHAT", "WHICH", "MAKES", "MAKE", "SENSE", "BETTER", "GOOD",
                    "TARGET", "KNOWN", "DEGRADER", "DEGRADERS", "WORK", "WORKS", "WORKING",
                    "USE", "THIS", "THAT", "HOW", "CAN", "WOULD", "SHOULD", "IS", "ARE",
                    "ME", "MY", "WITH", "FOR", "THE", "A", "AN", "OF", "VS", "VERSUS",
                    "OR", "AND", "PROTAC", "PROTACS", "E3", "LIGASE"}


def resolve_roles(request: str, understanding: Any) -> dict[str, Any]:
    """Split mentions into target vs E3 roles for a query.

    Only RESOLVED mentions count as symbols — unresolved tokens (e.g. "WHY",
    "MAKES") never become targets. E3-family symbols are interpreted as the
    recruiter role, so "BRD4 and CRBN works" parses target=BRD4, E3=CRBN.
    """
    mentions = getattr(understanding, "target_mentions", None) or []
    target_symbol = ""
    target_status = ""
    e3 = ""
    for m in mentions:
        r = m.resolution
        if not r or not getattr(r, "symbol", None):
            continue
        up = str(r.symbol).upper()
        if up in _SYMBOL_STOPLIST:
            continue
        if up in E3_FAMILIES:
            if not e3:
                e3 = up
            continue
        if not target_symbol:
            target_symbol = up
            target_status = str(r.status or "")
    if not target_symbol:
        pt = getattr(understanding, "primary_target", None)
        if pt and getattr(pt, "symbol", None) and str(getattr(pt, "status", "") or "") in ("verified", "resolved", "tentative"):
            target_symbol = str(pt.symbol).upper()
            target_status = str(getattr(pt, "status", None) or "")
    return {"target_symbol": target_symbol, "target_status": target_status,
            "e3": e3.upper() if e3 else ""}


# ── conversation context (§13) ───────────────────────────────────────────────
class ConversationContext:
    __slots__ = ("conversation_id", "target_symbol", "target_uniprot", "e3", "disease", "cell_line")

    def __init__(self, conversation_id: str):
        self.conversation_id = conversation_id
        self.target_symbol = ""
        self.target_uniprot = ""
        self.e3 = ""
        self.disease = ""
        self.cell_line = ""

    def to_dict(self) -> dict[str, str]:
        return {"conversation_id": self.conversation_id, "target_symbol": self.target_symbol,
                "target_uniprot": self.target_uniprot, "e3": self.e3,
                "disease": self.disease, "cell_line": self.cell_line}

    def note_target(self, symbol: str, uniprot: str = "") -> None:
        if symbol:
            self.target_symbol = symbol
            self.target_uniprot = uniprot or self.target_uniprot

    def note_e3(self, e3: str) -> None:
        if e3:
            self.e3 = e3.upper()

    def update_e3_only(self, e3: str) -> dict[str, str]:
        old = self.e3
        self.e3 = e3.upper()
        return {"old_e3": old, "new_e3": self.e3}


class ContextStore:
    def __init__(self) -> None:
        self._ctx: dict[str, ConversationContext] = {}

    def get(self, conversation_id: str) -> ConversationContext:
        if conversation_id not in self._ctx:
            self._ctx[conversation_id] = ConversationContext(conversation_id or "default")
        return self._ctx[conversation_id]

    def update_from_understanding(self, conversation_id: str, understanding: Any,
                                  roles: dict[str, Any] | None = None) -> dict[str, str]:
        """Record only RESOLVED entities; unresolved tokens never poison context."""
        ctx = self.get(conversation_id)
        roles = roles or {}
        t = roles.get("target_symbol") or ""
        st = roles.get("target_status") or ""
        if not t:
            pt = getattr(understanding, "primary_target", None)
            if pt and str(getattr(pt, "symbol", "") or "") and \
                    str(getattr(pt, "status", "") or "") in ("verified", "resolved", "tentative"):
                t = str(pt.symbol).upper()
        if t and st in ("verified", "resolved", "tentative"):
            ctx.note_target(t)
        e3 = roles.get("e3") or ""
        if not e3:
            e = str(getattr(getattr(understanding, "e3", None), "named_e3", "") or "")
            if e:
                e3 = e.upper()
        if e3:
            ctx.note_e3(e3)
        return ctx.to_dict()

    def merge_context(self, conversation_id: str, request: str, understanding: Any) -> dict[str, Any]:
        """Project stored context onto an under-specified request (no re-entry)."""
        ctx = self.get(conversation_id)
        h = _handlers.get(conversation_id)
        had_target = bool(getattr(understanding, "primary_target", None) and
                          getattr(understanding.primary_target, "symbol", None))
        had_e3 = getattr(getattr(understanding, "e3", None), "mode", "") in ("explicit", "delegated")
        injected: dict[str, Any] = {"target_injected": False, "e3_injected": False}
        if not had_target and ctx.target_symbol:
            injected["target_injected"] = ctx.target_symbol
        if not had_e3 and ctx.e3:
            injected["e3_injected"] = ctx.e3
        return injected


def parse_e3_update(text: str) -> str | None:
    m = re.search(r"(?:actually\s+)?use\s+([A-Za-z][A-Za-z0-9]*)|switch\s+to\s+([A-Za-z][A-Za-z0-9]*)", text)
    if not m:
        return None
    val = m.group(1) or m.group(2)
    return val.upper() if val.upper() in E3_FAMILIES else None


def parse_depth(text: str) -> tuple[str, str]:
    """(depth, clean_text): QUICK | STANDARD | DEEP."""
    t = text or ""
    if re.search(r"--deep", t, re.I):
        return "DEEP", re.sub(r"--deep", "", t, flags=re.I).strip()
    if re.search(r"--quick", t, re.I):
        return "QUICK", re.sub(r"--quick", "", t, flags=re.I).strip()
    return "STANDARD", t.strip()


# ── structured internal result (§15) ─────────────────────────────────────────
def make_structured(command: str, intent: str, entities: dict[str, Any],
                    findings: list[dict[str, str]], evidence: list[dict[str, str]],
                    uncertainties: list[str], gaps: list[str], conclusion: dict[str, Any],
                    artifacts: list[str], sections: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "command": command, "intent": intent, "entities": entities,
        "findings": findings, "evidence": evidence, "uncertainties": uncertainties,
        "gaps": gaps, "conclusion": conclusion, "artifacts": artifacts,
        "sections": sections or [],
    }


def render_sections(sections: list[dict[str, Any]]) -> list[str]:
    """Deterministic text rendering of structured sections (used by tests AND
    the TUI renderer contract; the Node renderer mirrors this layout)."""
    lines: list[str] = []
    for sec in sections:
        lines.append(f"SECTION {sec.get('title', '')}")
        for st in sec.get("statements", []):
            g = tier_glyph(st.get("tier", "inferred"))
            lines.append(f"  {g} {st.get('text', '')}")
        for ev in sec.get("evidence", []):
            lines.append(f"    · {ev.get('text', '')} [{ev.get('tier', '?')}] {ev.get('source', '')}")
    return lines


class _Handlers:
    pass


_handlers: dict[str, Any] = {}

# ── /plan contract (§3, §9, §10) ─────────────────────────────────────────────
PLAN_STAGE_SEQUENCE = [
    ("1", "TARGET ASSESSMENT", "target resolvable and biologically relevant"),
    ("2", "EVIDENCE RETRIEVAL", ">= 1 source-backed evidence record per claim"),
    ("3", "BINDER EVALUATION", "source-backed binder with usable exit vector"),
    ("4", "E3 COMPATIBILITY", "verified E3 ligand / attachment site"),
    ("5", "DESIGN STRATEGY", "assembly strategy + identity gates"),
    ("6", "STRUCTURAL ANALYSIS", "usable predicted/PDB model for the design"),
    ("7", "MECHANISTIC PREDICTION", "ternary/cooperativity/lysine/hook evidence state"),
    ("8", "DEVELOPABILITY", "ADMET/synthesis flags; applicability domain"),
    ("9", "NOMINATION GATE", "provenance gates + sufficient evidence"),
]
EXPENSIVE_STAGES = {"6": "STRUCTURAL ANALYSIS", "7": "MECHANISTIC PREDICTION", "8": "DEVELOPABILITY"}


def _task_stage(task_id: str, title: str) -> str:
    t = f"{task_id} {title}".lower()
    if any(k in t for k in ("target", "consensus", "identity")):
        return "1"
    if any(k in t for k in ("biology", "literature", "retriev", "evidence", "therapeutic")):
        return "2"
    if any(k in t for k in ("binder", "ligand", "warhead", "chembl")):
        return "3"
    if any(k in t for k in ("e3", "ligase")):
        return "4"
    if any(k in t for k in ("design", "construct", "linker", "assembly")):
        return "5"
    if any(k in t for k in ("structur", "ternary", "pdb", "pose")):
        return "6"
    if any(k in t for k in ("mechanis", "cooperat", "lysine", "hook", "degrad", "ubiquit")):
        return "7"
    if any(k in t for k in ("admet", "develop", "synthes", "permeab")):
        return "8"
    return "9"


def plan_contract(payload: dict[str, Any]) -> dict[str, Any]:
    """Build the §9 plan contract from a plan_answer payload."""
    tasks = payload.get("tasks") or []
    stages: list[dict[str, Any]] = []
    for num, name, gate_default in PLAN_STAGE_SEQUENCE:
        stage_tasks = [t for t in tasks if _task_stage(str(t.get("id", "")), str(t.get("title", ""))) == num]
        gates = [str(t.get("evidence_gate") or "") for t in stage_tasks if t.get("evidence_gate")]
        stages.append({
            "stage": f"{num}. {name}",
            "gate": "; ".join(gates) or gate_default,
            "tasks": [str(t.get("id")) for t in stage_tasks],
            "expensive_to_execute": num in EXPENSIVE_STAGES,
        })
    tools = sorted({str(t.get("tools")) for t in tasks if t.get("tools")} | {str(t.get("executor")) for t in tasks})
    tools = [t for t in tools if t and t != "None"]
    artifacts = [str(t.get("outputs")) for t in tasks if t.get("outputs")]
    blockers = [str(q) for q in (payload.get("open_questions") or [])]
    entities = {}
    tgt = payload.get("target") or {}
    if tgt:
        entities["target"] = {"symbol": tgt.get("symbol"), "uniprot_id": tgt.get("uniprot_id"),
                              "status": tgt.get("status")}
    if payload.get("e3"):
        entities["e3"] = {"mode": payload.get("e3"), "named": ""}
    return {
        "objective": payload.get("interpretation", ""),
        "resolved_entities": entities,
        "scientific_questions": [
            "Is the canonical identity and biology (disease/tractability) established?",
            "Which source-backed binders and E3 recruiters are usable?",
            "What measured precedent exists for degradation of this target with this recruiter?",
            "What mechanistic evidence state (ternary/cooperativity/lysine/hook) is reachable?",
            "What design is defensible and what would a validation study need to show?",
        ],
        "workflow_stages": stages,
        "planned_tools": tools,
        "planned_backend_capabilities": ["protein_structure", "interaction_fingerprint", "ternary_docking",
                                         "protac_scoring", "candidate_ranking"],
        "evidence_required": [
            "source-backed binder records (compound, activity, attachment vector)",
            "verified E3 ligand + attachment chemistry",
            "measured degradation precedent rows (E3, cell, DC50/Dmax, DOI)",
            "ternary/mechanistic evidence state (measured, computed, or explicit gap)",
        ],
        "decision_gates": list({str(t.get("evidence_gate")) for t in tasks if t.get("evidence_gate")}) or [
            "target.status == resolved", "binder source-backed", "e3 ligand verified"],
        "expected_artifacts": artifacts[:10],
        "known_blockers": blockers,
        "stop_conditions": [
            "evidence sufficient for the objective → proceed to /run (evidence stages) or /design",
            "blocked gate → typed blocker, no execution",
        ],
        "expensive_stages_require_run": [s["stage"] for s in stages if s["expensive_to_execute"]],
        "blocked_or_licensed_stages": [],  # filled from backend registry status at runtime
    }


def persist_plan(payload: dict[str, Any]) -> Path:
    """Persist the plan object (§10) next to the run artifacts."""
    pid = str(payload.get("plan_id") or "plan_unknown")
    run_dir = Path(payload.get("artifact_paths", {}).get("plan_json", "")).parent if payload.get("artifact_paths", {}) else None
    if not (run_dir and run_dir.exists()):
        run_dir = Path(__file__).resolve().parent.parent.parent / "outputs" / "plans" / pid
        run_dir.mkdir(parents=True, exist_ok=True)
    obj = {
        "plan_id": pid, "request_id": payload.get("request_id", ""),
        "objective": payload.get("interpretation", ""),
        "entities": plan_contract(payload)["resolved_entities"],
        "stages": [s["stage"] for s in plan_contract(payload)["workflow_stages"]],
        "dependencies": {str(t.get("id")): t.get("dependencies") for t in (payload.get("tasks") or [])},
        "gates": [str(t.get("evidence_gate")) for t in (payload.get("tasks") or []) if t.get("evidence_gate")],
        "tools": plan_contract(payload)["planned_tools"],
        "expected_outputs": plan_contract(payload)["expected_artifacts"],
        "status": payload.get("status", "draft"),
        "persisted_at": None,
    }
    from datetime import datetime, timezone
    obj["persisted_at"] = datetime.now(timezone.utc).isoformat()
    p = run_dir / "plan_object.json"
    p.write_text(json.dumps(obj, indent=1, default=str), encoding="utf-8")
    return p


# ── /run plan execution (§10) ────────────────────────────────────────────────
def load_plan(plan_id: str) -> dict[str, Any] | None:
    root = Path(__file__).resolve().parent.parent.parent
    candidates = [
        root / "outputs" / "workflows" / "plan_runs" / plan_id / "plan_object.json",
        root / "outputs" / "plans" / plan_id / "plan_object.json",
        root / "outputs" / "workflows" / "plan_runs" / plan_id / "plan.json",
    ]
    for p in candidates:
        if p.exists():
            try:
                return json.loads(p.read_text())
            except Exception:
                return None
    # plan_id may differ from the run-dir id; scan persisted plan objects
    for base in (root / "outputs" / "workflows" / "plan_runs", root / "outputs" / "plans"):
        if not base.exists():
            continue
        for p in base.glob("*/plan_object.json"):
            try:
                obj = json.loads(p.read_text())
            except Exception:
                continue
            if str(obj.get("plan_id", "")) == str(plan_id):
                return obj
    return None


def execute_plan_evidence_stages(plan: dict[str, Any], emit: Any) -> dict[str, Any]:
    """Execute the evidence (non-expensive) stages of a persisted plan.

    Expensive stages (structural/mechanistic/developability/design) are listed
    as requiring /design or explicit run — they are not auto-executed here.
    """
    executed: list[dict[str, Any]] = []
    results: dict[str, Any] = {}
    stage_num = 0
    for st in plan.get("stages", []):
        stage_num += 1
        if str(stage_num) in ("6", "7", "8", "9"):
            executed.append({"stage": st, "status": "requires_run_not_executed",
                             "note": "expensive/design stage; not auto-executed by /run evidence pass"})
            results[st] = {"status": "deferred"}
            continue
        # evidence stages: T0 confirm identity, T1b assessment, T1 biology, T2 binder, T3 E3
        results[st] = {"status": "scheduled"}
        executed.append({"stage": st, "status": "scheduled", "note": "evidence stage (planned)"})
    return {"plan_id": plan.get("plan_id"), "executed_stages": executed, "results": results,
            "expensive_stages_deferred": [s for s in plan.get("stages", []) if s.split(".")[0] in ("6", "7", "8", "9")]}

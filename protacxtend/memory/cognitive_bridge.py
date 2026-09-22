"""Optional host adapter — PROTACXtend run records ↔ PROTACpilot Cognitive Memory.

This is the deferred Phase-7 adapter from
``protacpilot-memory/docs/IMPLEMENTATION_LOG.md``.  It maps canonical host
artifacts onto the cognitive-memory API:

  host artifact                      cognitive-memory call
  ---------------------------------  ----------------------------------------
  AgentRunRecord / run.json          ``cog_encode`` (save_episode)
  parsed objective + candidates      ``cog_predict`` (predict)
  experimental outcome               ``cog_record_outcome`` (record_outcome)
  failure / repair evidence          negative episode (is_negative=True)
  prior memory query                 ``cog_search`` / ``cog_recall``

Design rules
------------
* **Optional** — importing this module never fails when ``protacpilot_memory``
  is not installed.  Use :func:`available` / :func:`open_bridge`; the
  module-level ``maybe_*`` helpers degrade to ``{"enabled": False, ...}``.
* **Non-invasive** — nothing mutates an ``AgentRunRecord`` and the runtime hook
  is opt-in via ``PROTACPILOT_COGNITIVE_MEMORY=1`` (default OFF), so frozen
  benchmark artifacts stay byte-identical unless a user asks for memory.
* **Deterministic** — no network, no LLM.  Context/evidence mapping is a pure
  function of the host record.

Usage::

    from protacxtend.memory.cognitive_bridge import open_bridge

    bridge = open_bridge(db_path="outputs/memory/cognitive.db")
    bridge.ingest_run_file("outputs/runs/<run_id>/run.json")
    hits = bridge.retrieve("PEG linker permeability BRD4 VHL",
                           host_context={"target_gene": "BRD4", "e3_ligase": "VHL"})
"""

from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

# ── discovery ────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[2]
SIBLING_SRC = REPO_ROOT / "protacpilot-memory" / "src"

ENABLE_ENV = "PROTACPILOT_COGNITIVE_MEMORY"
DB_ENV = "PROTACPILOT_MEMORY_DB"

_TRUTHY = {"1", "true", "yes", "on", "enabled"}

# Host evidence-record ``type`` → cognitive ontology evidence type.
_EVIDENCE_TYPE_MAP: dict[str, str] = {
    "binder": "curated_database",
    "evidence_admet": "ml_prediction",
    "evidence_degradation": "ml_prediction",
    "evidence_validation": "structural_observation",
    "evidence_ref": "internal_experiment",
    "experiment": "internal_experiment",
    "assay": "internal_experiment",
    "docking": "docking",
    "md": "md_simulation",
    "simulation": "md_simulation",
    "publication": "peer_reviewed_publication",
    "literature": "peer_reviewed_publication",
    "database": "curated_database",
    "llm": "llm_inference",
}

# Candidate fields the host scoring stage treats as model outputs.
_DEFAULT_PREDICTION_METRICS: tuple[str, ...] = (
    "log_dc50",
    "dmax_inverted",
    "admet_penalty",
    "synthesis_difficulty",
    "ternary_penalty",
    "plddt_min",
    "plddt_mean",
    "synthetic_feasibility_score",
)

_CTX_CONSUMED_KEYS = {
    "target_name", "target", "target_gene", "target_uniprot", "target_uniprot_id",
    "target_domain", "e3", "e3_ligase", "cell_line", "assay_type", "assay_context",
    "warhead_smiles", "e3_ligand_smiles", "preferred_linker_types", "raw_request",
    "objectives",
}

_module_cache: dict[str, Any] = {}


def _load_memory_module() -> Any | None:
    """Import ``protacpilot_memory`` from the environment or the sibling checkout."""
    if "module" in _module_cache:
        return _module_cache["module"]
    module = None
    try:
        module = importlib.import_module("protacpilot_memory")
    except Exception:
        module = None
    if module is None and SIBLING_SRC.is_dir():
        if str(SIBLING_SRC) not in sys.path:
            sys.path.insert(0, str(SIBLING_SRC))
        try:
            module = importlib.import_module("protacpilot_memory")
        except Exception:
            module = None
    _module_cache["module"] = module
    return module


def available() -> bool:
    """True when the cognitive-memory package can be imported."""
    return _load_memory_module() is not None


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in _TRUTHY


def _as_mapping(record: Any) -> dict[str, Any]:
    """Coerce an AgentRunRecord / pydantic model / dict to a plain mapping."""
    if record is None:
        return {}
    if isinstance(record, Mapping):
        return dict(record)
    dump = getattr(record, "model_dump", None)
    if callable(dump):
        return dict(dump())
    return dict(getattr(record, "__dict__", {}) or {})


# ── pure mapping helpers (no memory dependency) ──────────────────────────────
def host_context_from_record(record: Any) -> dict[str, Any]:
    """Map an AgentRunRecord's parsed objective onto a ProtacContext dict."""
    rec = _as_mapping(record)
    parsed = dict(rec.get("parsed_objective") or {})

    def _first(*keys: str) -> Any:
        for key in keys:
            value = parsed.get(key)
            if value not in (None, "", [], {}):
                return value
        return None

    context: dict[str, Any] = {}
    target = _first("target_gene", "target_name", "target")
    if target:
        context["target_gene"] = str(target)
    uniprot = _first("target_uniprot", "target_uniprot_id")
    if uniprot:
        context["target_uniprot"] = str(uniprot)
    domain = _first("target_domain")
    if domain:
        context["target_domain"] = str(domain)
    e3 = _first("e3_ligase", "e3")
    if e3:
        context["e3_ligase"] = str(e3)
    cell = _first("cell_line")
    if cell:
        context["cell_line"] = str(cell)
    assay = _first("assay_type", "assay_context")
    if assay:
        context["assay_type"] = str(assay)
    warhead = _first("warhead_smiles")
    if warhead:
        context["warhead_smiles"] = str(warhead)
    e3_ligand = _first("e3_ligand_smiles")
    if e3_ligand:
        context["e3_ligand_smiles"] = str(e3_ligand)
    linkers = parsed.get("preferred_linker_types")
    if isinstance(linkers, (list, tuple)) and linkers:
        context["linker_type"] = str(linkers[0])
    elif isinstance(linkers, str) and linkers.strip():
        context["linker_type"] = linkers.strip()

    extra = {k: v for k, v in parsed.items() if k not in _CTX_CONSUMED_KEYS}
    raw = parsed.get("raw_request") or rec.get("user_objective")
    if raw:
        extra.setdefault("raw_request", raw)
    objectives = parsed.get("objectives")
    if objectives:
        extra.setdefault("objectives", objectives)
    if extra:
        context["extra"] = extra
    return context


def host_evidence_from_record(record: Any, *, limit: int = 50) -> list[dict[str, Any]]:
    """Map host evidence records onto EvidenceRef-compatible dicts (deduped)."""
    rec = _as_mapping(record)
    refs: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for item in rec.get("evidence_records") or []:
        if not isinstance(item, Mapping):
            continue
        raw_type = str(item.get("type") or item.get("evidence_type") or "internal_experiment")
        etype = _EVIDENCE_TYPE_MAP.get(raw_type, "internal_experiment")
        title = item.get("title") or item.get("name") or raw_type
        ref_key = item.get("ref") or item.get("source_ref")
        ident = item.get("doi") or item.get("pmid") or item.get("pdb") or item.get("accession")
        key = (etype, str(title), item.get("source"), ref_key, ident)
        if key in seen:
            continue
        seen.add(key)
        ref: dict[str, Any] = {"evidence_type": etype, "title": str(title)[:200]}
        for out_key, in_key in (
            ("source_type", "source"), ("source_ref", "source_ref"), ("experiment_id", "experiment_id"),
            ("doi", "doi"), ("pmid", "pmid"), ("url", "url"), ("pdb", "pdb"),
            ("accession", "accession"), ("model_name", "model_name"), ("model_version", "model_version"),
        ):
            value = item.get(in_key) if in_key != "source_ref" else (item.get("source_ref") or ref_key)
            if value not in (None, "", [], {}):
                ref[out_key] = value
        if "source_type" not in ref:
            ref["source_type"] = raw_type
        ref["payload"] = {
            k: v for k, v in item.items()
            if k not in {"type", "title", "name", "source", "source_ref", "ref", "experiment_id",
                         "doi", "pmid", "url", "pdb", "accession", "model_name", "model_version"}
        }
        refs.append(ref)
        if len(refs) >= limit:
            break
    return refs


def host_predictions_from_record(
    record: Any, *, metrics: Iterable[str] | None = None, confidence: float = 0.5,
) -> list[dict[str, Any]]:
    """Extract candidate metric predictions from the run's final candidates."""
    rec = _as_mapping(record)
    wanted = tuple(metrics) if metrics is not None else _DEFAULT_PREDICTION_METRICS
    out: list[dict[str, Any]] = []
    for cand in rec.get("final_candidates") or []:
        if not isinstance(cand, Mapping):
            continue
        candidate_id = cand.get("candidate_id")
        for metric in wanted:
            value = cand.get(metric)
            if value is None or isinstance(value, bool):
                continue
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            out.append({
                "candidate_id": str(candidate_id) if candidate_id is not None else None,
                "metric": metric,
                "predicted_value": numeric,
                "confidence": float(cand.get("confidence", confidence) or confidence),
            })
    return out


def run_episode_payload(record: Any, state: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Build the ``save_episode`` payload describing a whole host run."""
    rec = _as_mapping(record)
    state = dict(state or {})
    run_id = rec.get("run_id") or state.get("run_id") or "unknown-run"
    objective = rec.get("user_objective") or state.get("user_request") or "PROTAC design run"
    routing = rec.get("routing_path") or []
    tools = rec.get("tools_executed") or []
    errors = [str(e) for e in (rec.get("errors") or state.get("errors") or [])]
    warnings = [str(w) for w in (rec.get("warnings") or state.get("warnings") or [])]

    lines = [f"Objective: {objective}"]
    if routing:
        lines.append("Routing: " + " → ".join(str(r) for r in routing))
    if tools:
        lines.append("Tools: " + ", ".join(str(t) for t in tools))
    lines.append(
        f"Candidates generated={rec.get('candidates_generated', 0)} "
        f"valid={rec.get('candidates_valid', 0)}"
    )
    if rec.get("llm_calls"):
        lines.append(f"LLM calls={rec.get('llm_calls')} failures={rec.get('llm_failures', 0)}")
    if errors:
        lines.append("Errors: " + "; ".join(errors[:5]))
    if warnings:
        lines.append("Warnings: " + "; ".join(warnings[:5]))
    report = str(state.get("report") or "")
    if report:
        lines.append("Report: " + report[:600])

    context = host_context_from_record(rec)
    parsed = rec.get("parsed_objective") or {}
    target = parsed.get("target_name") or parsed.get("target") or parsed.get("target_gene") or "target"
    title = f"Run {run_id}: {target} — {str(objective)[:100]}"

    return {
        "title": title,
        "content": "\n".join(lines),
        "event_type": "procedure_run",
        "context": context,
        "evidence": host_evidence_from_record(rec),
        "observed": {
            "run_id": run_id,
            "candidates_generated": rec.get("candidates_generated", 0),
            "candidates_valid": rec.get("candidates_valid", 0),
            "runtime_seconds": rec.get("runtime_seconds", 0.0),
            "llm_calls": rec.get("llm_calls", 0),
            "n_errors": len(errors),
            "n_warnings": len(warnings),
        },
        "interpretation": " ".join(lines[1:4]),
        "is_negative": bool(errors),
        "decision_impact": 0.8 if rec.get("candidates_valid") else 0.5,
        "goal_relevance": 0.9,
        "source": {
            "source_type": "host_agent_run",
            "source_ref": run_id,
            "run_id": run_id,
            "reproducibility_hash": rec.get("reproducibility_hash", ""),
        },
        "source_type": "host_agent_run",
    }


def failure_episode_payloads(record: Any, *, limit: int = 10) -> list[dict[str, Any]]:
    """Map host errors / repair events onto negative-memory episode payloads."""
    rec = _as_mapping(record)
    run_id = rec.get("run_id") or "unknown-run"
    context = host_context_from_record(rec)
    payloads: list[dict[str, Any]] = []

    for err in list(rec.get("errors") or [])[:limit]:
        payloads.append({
            "title": f"Failure in run {run_id}: {str(err)[:100]}",
            "content": f"Host run {run_id} reported an error: {err}",
            "event_type": "failure",
            "context": context,
            "is_negative": True,
            "decision_impact": 0.7,
            "source": {"source_type": "host_agent_run", "source_ref": run_id, "run_id": run_id},
            "source_type": "host_agent_run",
        })
    for repair in list(rec.get("repair_events") or [])[: max(0, limit - len(payloads))]:
        if not isinstance(repair, Mapping):
            continue
        reasons = repair.get("reason_codes") or repair.get("reason") or "repair"
        node = repair.get("node") or repair.get("next_proposed_node") or "unknown"
        payloads.append({
            "title": f"Repair in run {run_id}: {reasons}",
            "content": (
                f"Repair event at node {node} in run {run_id}: {reasons}. "
                f"type={repair.get('decision_type', 'repair')} "
                f"confidence={repair.get('confidence', '')}"
            ),
            "event_type": "failure",
            "context": context,
            "is_negative": True,
            "decision_impact": 0.6,
            "source": {"source_type": "host_agent_run", "source_ref": run_id, "run_id": run_id},
            "source_type": "host_agent_run",
        })
    return payloads[:limit]


# ── bridge ───────────────────────────────────────────────────────────────────
class NullBridge:
    """Inactive stand-in returned when the cognitive package is unavailable."""

    active = False

    def __init__(self, reason: str = "protacpilot_memory is not importable"):
        self.reason = reason

    def _disabled(self, **extra: Any) -> dict[str, Any]:
        return {"enabled": False, "reason": self.reason, **extra}

    def ingest_run_record(self, *a: Any, **k: Any) -> dict[str, Any]:
        return self._disabled()

    def ingest_run_file(self, *a: Any, **k: Any) -> dict[str, Any]:
        return self._disabled()

    def ingest_run_dir(self, *a: Any, **k: Any) -> dict[str, Any]:
        return self._disabled()

    def record_outcome(self, *a: Any, **k: Any) -> dict[str, Any]:
        return self._disabled()

    def retrieve(self, *a: Any, **k: Any) -> dict[str, Any]:
        return self._disabled(results=[])

    def prompt_context(self, *a: Any, **k: Any) -> dict[str, Any]:
        return self._disabled(text="")

    def stats(self) -> dict[str, Any]:
        return self._disabled()

    def close(self) -> None:
        return None


class CognitiveMemoryBridge:
    """Thin, deterministic adapter over ``protacpilot_memory.CognitiveMemory``."""

    active = True

    def __init__(
        self,
        memory: Any | None = None,
        *,
        project_name: str = "protacxtend",
        db_path: str | Path | None = None,
    ) -> None:
        module = _load_memory_module()
        if module is None:
            raise RuntimeError(
                "protacpilot_memory is not importable. Install the package "
                "(`pip install -e protacpilot-memory`) or add "
                f"{SIBLING_SRC} to PYTHONPATH."
            )
        self._module = module
        self.owns_memory = memory is None
        if memory is None:
            if db_path is not None:
                self.memory = module.CognitiveMemory.open(db_path)
            elif os.environ.get(DB_ENV):
                self.memory = module.CognitiveMemory.open(os.environ[DB_ENV])
            else:
                self.memory = module.CognitiveMemory.open()
        else:
            self.memory = memory
        self.project_name = project_name
        self.project_id = self.memory.ensure_project(project_name)

    # ── lifecycle ────────────────────────────────────────────────────────────
    def close(self) -> None:
        if self.owns_memory:
            self.memory.close()

    def __enter__(self) -> CognitiveMemoryBridge:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ── ingestion ────────────────────────────────────────────────────────────
    def _existing_run_episode(self, run_id: str) -> str | None:
        """Return the episodic trace id already recorded for ``run_id``, if any.

        The runtime can be re-run or a run artifact re-imported; predictions and
        failure episodes must not be duplicated in that case.
        """
        row = self.memory.db.query_one(
            "SELECT id FROM memory_traces WHERE source_id = ? AND project_id = ? "
            "AND memory_type IN ('episodic', 'negative') ORDER BY created_at ASC LIMIT 1",
            (run_id, self.project_id),
        )
        return row["id"] if row else None

    def ingest_run_record(
        self,
        record: Any,
        state: Mapping[str, Any] | None = None,
        *,
        predictions: bool = True,
        failures: bool = True,
        metrics: Iterable[str] | None = None,
        session_id: str | None = None,
        idempotent: bool = True,
    ) -> dict[str, Any]:
        """Encode one host run plus its failures and candidate predictions.

        Ingestion is idempotent per ``run_id`` by default: re-importing the same
        run returns the existing episode and creates no duplicate predictions or
        failure episodes.
        """
        rec = _as_mapping(record)
        run_id = rec.get("run_id") or (state or {}).get("run_id") or "unknown-run"

        if idempotent:
            existing = self._existing_run_episode(run_id)
            if existing is not None:
                return {
                    "enabled": True,
                    "run_id": run_id,
                    "deduplicated": True,
                    "episode": {"episode_id": existing},
                    "failure_episodes": [],
                    "predictions": [],
                    "n_failure_episodes": 0,
                    "n_predictions": 0,
                }

        episode = self.memory.save_episode(
            project_id=self.project_id, session_id=session_id, **run_episode_payload(rec, state)
        )

        failure_episodes: list[dict[str, Any]] = []
        if failures:
            for payload in failure_episode_payloads(rec):
                failure_episodes.append(
                    self.memory.save_episode(project_id=self.project_id, session_id=session_id, **payload)
                )

        prediction_ids: list[dict[str, Any]] = []
        if predictions:
            for pred in host_predictions_from_record(rec, metrics=metrics):
                pid = self.memory.predict(
                    prediction_type="numeric",
                    project_id=self.project_id,
                    session_id=session_id,
                    candidate_id=pred["candidate_id"],
                    metric=pred["metric"],
                    predicted_value=pred["predicted_value"],
                    confidence=pred["confidence"],
                    context=host_context_from_record(rec),
                )
                prediction_ids.append({"prediction_id": pid, **pred})

        return {
            "enabled": True,
            "run_id": run_id,
            "deduplicated": False,
            "episode": episode,
            "failure_episodes": failure_episodes,
            "predictions": prediction_ids,
            "n_failure_episodes": len(failure_episodes),
            "n_predictions": len(prediction_ids),
        }

    def ingest_run_file(self, path: str | Path, **kwargs: Any) -> dict[str, Any]:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return self.ingest_run_record(data, **kwargs)

    def ingest_run_dir(self, run_dir: str | Path, **kwargs: Any) -> dict[str, Any]:
        return self.ingest_run_file(Path(run_dir) / "run.json", **kwargs)

    # ── outcomes ─────────────────────────────────────────────────────────────
    def find_prediction(
        self, candidate_id: str, metric: str, *, project_id: str | None = None
    ) -> str | None:
        rows = self.memory.db.query(
            """
            SELECT id FROM prediction_events
            WHERE candidate_id = ? AND metric = ? AND (? IS NULL OR project_id = ?)
            ORDER BY created_at DESC LIMIT 1
            """,
            (candidate_id, metric, project_id or self.project_id, project_id or self.project_id),
        )
        return rows[0]["id"] if rows else None

    def record_outcome(
        self,
        prediction_id: str,
        *,
        observed_value: float | None = None,
        observed_class: str | None = None,
        outcome_type: str | None = None,
        source_ref: str | None = None,
        experiment_id: str | None = None,
        notes: str | None = None,
        is_negative: bool | None = None,
    ) -> dict[str, Any]:
        return self.memory.record_outcome(
            prediction_id,
            observed_value=observed_value,
            observed_class=observed_class,
            outcome_type=outcome_type,
            evidence_type="internal_experiment",
            source_ref=source_ref,
            experiment_id=experiment_id,
            notes=notes,
            is_negative=is_negative,
        )

    def record_candidate_outcome(
        self,
        candidate_id: str,
        metric: str,
        observed_value: float,
        *,
        outcome_type: str = "wet_lab",
        source_ref: str | None = None,
        experiment_id: str | None = None,
        notes: str | None = None,
        is_negative: bool | None = None,
        create_if_missing: bool = True,
    ) -> dict[str, Any]:
        """Resolve the prediction for a candidate/metric and record the outcome."""
        prediction_id = self.find_prediction(candidate_id, metric)
        if prediction_id is None and create_if_missing:
            prediction_id = self.memory.predict(
                prediction_type="numeric",
                project_id=self.project_id,
                candidate_id=candidate_id,
                metric=metric,
                predicted_value=None,
                confidence=0.0,
            )
        if prediction_id is None:
            return {"enabled": True, "ok": False, "reason": "prediction not found",
                    "candidate_id": candidate_id, "metric": metric}
        return {
            "enabled": True,
            "ok": True,
            "candidate_id": candidate_id,
            "metric": metric,
            "prediction_id": prediction_id,
            "outcome": self.record_outcome(
                prediction_id, observed_value=observed_value, outcome_type=outcome_type,
                source_ref=source_ref, experiment_id=experiment_id, notes=notes,
                is_negative=is_negative,
            ),
        }

    # ── retrieval ────────────────────────────────────────────────────────────
    def retrieve(
        self,
        query: str,
        *,
        host_context: Mapping[str, Any] | None = None,
        limit: int = 5,
        memory_types: list[str] | None = None,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        result = self.memory.search_dict(
            query,
            project_id=project_id or self.project_id,
            context=dict(host_context) if host_context else None,
            memory_types=memory_types,
            limit=limit,
        )
        result["enabled"] = True
        return result

    def prompt_context(
        self,
        query: str,
        *,
        host_context: Mapping[str, Any] | None = None,
        limit: int = 5,
        token_budget: int | None = None,
    ) -> dict[str, Any]:
        """Assemble a compact, prompt-ready context block from prior memory."""
        result = self.retrieve(query, host_context=host_context, limit=limit)
        lines: list[str] = []
        for hit in result.get("results", []):
            title = hit.get("title") or hit.get("id")
            snippet = (hit.get("snippet") or hit.get("summary") or hit.get("content") or "")
            lines.append(f"- [{hit.get('memory_type', 'memory')}] {title}: {str(snippet)[:240]}")
        text = "\n".join(lines)
        if not text:
            text = "(no relevant prior memory)"
        return {
            "enabled": True,
            "query": query,
            "text": text,
            "n_results": len(result.get("results", [])),
            "semantic_backend": result.get("semantic_backend"),
            "results": result.get("results", []),
        }

    # ── diagnostics ──────────────────────────────────────────────────────────
    def stats(self) -> dict[str, Any]:
        return {"enabled": True, "project_id": self.project_id, **self.memory.stats()}


# ── module-level convenience ─────────────────────────────────────────────────
def open_bridge(
    memory: Any | None = None,
    *,
    project_name: str = "protacxtend",
    db_path: str | Path | None = None,
) -> CognitiveMemoryBridge | NullBridge:
    """Open a bridge, or return a :class:`NullBridge` when unavailable."""
    if memory is None and not available():
        return NullBridge()
    return CognitiveMemoryBridge(memory, project_name=project_name, db_path=db_path)


def maybe_ingest(
    record: Any,
    state: Mapping[str, Any] | None = None,
    *,
    bridge: CognitiveMemoryBridge | NullBridge | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Opt-in ingestion hook (``PROTACPILOT_COGNITIVE_MEMORY=1``).

    Returns ``{"enabled": False}`` unless explicitly enabled, and never raises.
    """
    if not _truthy(os.environ.get(ENABLE_ENV)):
        return {"enabled": False, "reason": f"{ENABLE_ENV} not set"}
    try:
        active = bridge or open_bridge()
        if not active.active:
            return {"enabled": False, "reason": getattr(active, "reason", "unavailable")}
        return active.ingest_run_record(record, state, **kwargs)
    except Exception as exc:  # pragma: no cover - defensive
        return {"enabled": True, "ok": False, "error": str(exc)}


def maybe_retrieve(
    query: str,
    *,
    host_context: Mapping[str, Any] | None = None,
    bridge: CognitiveMemoryBridge | NullBridge | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Opt-in retrieval hook; disabled unless memory is explicitly enabled."""
    if not _truthy(os.environ.get(ENABLE_ENV)):
        return {"enabled": False, "reason": f"{ENABLE_ENV} not set", "results": []}
    try:
        active = bridge or open_bridge()
        if not active.active:
            return {"enabled": False, "reason": getattr(active, "reason", "unavailable"), "results": []}
        return active.retrieve(query, host_context=host_context, **kwargs)
    except Exception as exc:  # pragma: no cover - defensive
        return {"enabled": True, "ok": False, "error": str(exc), "results": []}

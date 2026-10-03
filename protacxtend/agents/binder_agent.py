"""Target binder retrieval agent — searches ChEMBL, PubChem, BindingDB for known ligands."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from protacxtend.agents.base_agent import ReActAgent
from protacxtend.backend.schemas import BinderRecord, WorkflowState

# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────
CHEMBL_BASE = "https://www.ebi.ac.uk/chembl/api/data"
PUBCHEM_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
BINDINGDB_BASE = "https://bindingdb.org/rest"
UNIPROT_BASE = "https://rest.uniprot.org"
RCSB_DATA_BASE = "https://data.rcsb.org"
RCSB_SEARCH_BASE = "https://search.rcsb.org"

TIMEOUT = 10
MAX_RETRIES = 2
DELAY = 0.5  # seconds between requests (2/sec)

#: Wall-clock deadline (``time.monotonic`` seconds) for the whole current run.
#: ``None`` means unbounded. Set by the orchestration layer so no single
#: retrieval can consume the run budget; expired attempts raise
#: :class:`~protacxtend.runtime.modes.RetrievalDeadlineExceeded` instead of
#: retrying for 30 s x 5.
_DEADLINE: float | None = None


def set_run_deadline(seconds: float | None) -> None:
    """Bound all subsequent retrieval requests to *seconds* from now.

    ``None`` clears the bound. The deadline is process-wide because the
    benchmark arms run one case per process.
    """
    global _DEADLINE
    _DEADLINE = None if seconds is None else time.monotonic() + max(0.0, float(seconds))


def clear_run_deadline() -> None:
    set_run_deadline(None)


def deadline_remaining() -> float | None:
    """Seconds left before the run deadline (None when unbounded)."""
    if _DEADLINE is None:
        return None
    return _DEADLINE - time.monotonic()


def _request_timeout() -> float:
    """Per-attempt socket timeout, clipped by the remaining run budget."""
    remaining = deadline_remaining()
    if remaining is None:
        return float(TIMEOUT)
    return max(0.5, min(float(TIMEOUT), remaining))


def _check_deadline(url: str = "") -> None:
    """Raise the typed deadline failure when the run budget is spent."""
    remaining = deadline_remaining()
    if remaining is not None and remaining <= 0:
        from protacxtend.runtime.modes import RetrievalDeadlineExceeded

        raise RetrievalDeadlineExceeded(
            f"live retrieval exceeded the propagated run deadline before {url[:120]!r}; "
            "no network result was used"
        )


def _sleep_with_deadline(seconds: float, url: str = "") -> None:
    """Sleep for at most the remaining run budget, then re-check it."""
    remaining = deadline_remaining()
    delay = max(0.0, float(seconds))
    if remaining is not None:
        delay = min(delay, max(0.0, remaining))
    if delay > 0:
        time.sleep(delay)
    _check_deadline(url)


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _source_status_from_exception(exc: BaseException) -> str:
    from protacxtend.runtime.modes import RetrievalDeadlineExceeded

    if isinstance(exc, RetrievalDeadlineExceeded):
        return "SOURCE_TIMEOUT"
    if isinstance(exc, urllib.error.HTTPError) and exc.code == 429:
        return "SOURCE_RATE_LIMITED"
    if isinstance(exc, (urllib.error.URLError, OSError, TimeoutError)):
        return "SOURCE_UNAVAILABLE"
    return "SOURCE_UNAVAILABLE"


def _telemetry_row(
    *,
    source: str,
    start_time: str,
    started: float,
    timeout: float,
    retry_count: int = 0,
    cache_hit: bool = False,
    records_returned: int = 0,
    fallback_used: str = "",
    final_status: str = "SOURCE_EMPTY",
    error_type: str = "",
) -> dict[str, Any]:
    return {
        "source": source,
        "start_time": start_time,
        "latency_ms": int(round((time.monotonic() - started) * 1000)),
        "timeout": timeout,
        "retry_count": retry_count,
        "cache_hit": cache_hit,
        "records_returned": records_returned,
        "fallback_used": fallback_used,
        "final_status": final_status,
        "error_type": error_type,
    }
CACHE_DIR = os.environ.get("PROTACXTEND_LIVE_CACHE_DIR") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "live_cache",
)  # disk cache root; None disables persistence

#: URLs whose payload was replayed from the disk cache in this process.
_cache_replays: dict[str, int] = {}
_cache_records: dict[str, dict] = {}  # url -> cache record (fetched_at etc.)


def _disk_cache_path(url: str) -> str:
    key = hashlib.sha1(url.encode()).hexdigest()
    return os.path.join(CACHE_DIR, f"{key}.json") if CACHE_DIR else ""


def _write_disk_cache(url: str, payload: dict) -> None:
    if not CACHE_DIR:
        return
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        record = {
            "url": url,
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "http_status": 200,
            "sha1_url": hashlib.sha1(url.encode()).hexdigest(),
            "payload": payload,
        }
        _cache_records[url] = record
        path = _disk_cache_path(url)
        tmp = f"{path}.tmp"
        with open(tmp, "w") as f:
            json.dump(record, f)
        os.replace(tmp, path)
    except Exception:  # noqa: BLE001 - cache must never break retrieval
        return


def _read_disk_cache(url: str) -> dict | None:
    if not CACHE_DIR:
        return None
    try:
        path = _disk_cache_path(url)
        if not os.path.exists(path):
            return None
        with open(path) as f:
            record = json.load(f)
        _cache_records[url] = record
        _cache_replays[url] = _cache_replays.get(url, 0) + 1
        return record.get("payload")
    except Exception:  # noqa: BLE001
        return None

#: When True, no network request is attempted. Set by the offline/benchmark
#: runtime so a retrieval node can never consume a wall-clock budget on a
#: hanging API. Seeded or curated binders are still returned.
OFFLINE = False


def set_offline(value: bool = True) -> None:
    """Enable/disable network access for binder retrieval (process-wide)."""
    global OFFLINE
    OFFLINE = bool(value)

# ─────────────────────────────────────────────
# Rate-limited HTTP client with caching
# ─────────────────────────────────────────────
_last_request_time = 0.0
_cache: dict[str, Any] = {}

def cache_replay_warning() -> list[str]:
    """Human-readable provenance lines for any disk-cache replay this process used."""
    out = []
    for url, n in _cache_replays.items():
        rec = _cache_records.get(url)
        fetched = rec.get("fetched_at", "?") if rec else "?"
        out.append(
            f"Live source unavailable; replayed {n} cached live-fetch record(s) "
            f"(url={url[:80]}…, fetched_at={fetched}, disk cache={CACHE_DIR}). "
            "Replayed payloads are real prior live-API responses, not fixtures."
        )
    return out


def _rate_limit():
    global _last_request_time
    now = time.time()
    since = now - _last_request_time
    if since < DELAY:
        _sleep_with_deadline(DELAY - since)
    _last_request_time = time.time()

def _cached_request(url: str, cache_key: str = "") -> dict[str, Any] | None:
    if OFFLINE:
        return None
    _check_deadline(url)
    cache_key = cache_key or hashlib.md5(url.encode()).hexdigest()
    if cache_key in _cache:
        return _cache[cache_key]

    _rate_limit()
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        _check_deadline(url)
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "ProtacPilot/1.0"})
            with urllib.request.urlopen(req, timeout=_request_timeout()) as resp:
                data = json.loads(resp.read().decode())
                _cache[cache_key] = data
                _write_disk_cache(url, data)
                return data
        except urllib.error.HTTPError as e:
            last_error = e
            if e.code == 429:  # rate limited — respect Retry-After
                retry_after = float(e.headers.get("Retry-After", 5)) if e.headers.get("Retry-After") else 5.0
                _sleep_with_deadline(min(retry_after, 20.0), url)
            elif attempt < MAX_RETRIES:
                _sleep_with_deadline(DELAY * (2 ** attempt), url)  # exponential backoff
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
            last_error = e
            if attempt < MAX_RETRIES:
                _sleep_with_deadline(DELAY * (2 ** attempt), url)  # exponential backoff
    # Live source unavailable: replay a previously fetched live payload from
    # disk if one exists. This is not a fixture: the payload was fetched from
    # the live API earlier (fetched_at + url recorded) and is replayed with
    # provenance. Callers surface replays via binder_agent.cache_replay_warning().
    replayed = _read_disk_cache(url)
    if replayed is not None:
        _cache[cache_key] = replayed
        return replayed
    return None

def _cached_request_text(url: str, cache_key: str = "") -> str | None:
    if OFFLINE:
        return None
    _check_deadline(url)
    cache_key = cache_key or hashlib.md5(url.encode()).hexdigest()
    if cache_key in _cache:
        return _cache[cache_key]

    _rate_limit()
    for attempt in range(1, MAX_RETRIES + 1):
        _check_deadline(url)
        try:
            req = urllib.request.Request(url, headers={"Accept": "text/csv", "User-Agent": "ProtacPilot/1.0"})
            with urllib.request.urlopen(req, timeout=_request_timeout()) as resp:
                text = resp.read().decode()
                _cache[cache_key] = text
                return text
        except Exception:
            if attempt < MAX_RETRIES:
                _sleep_with_deadline(DELAY * (2 ** attempt), url)
    return None


class TargetBinderRetrievalAgent(ReActAgent):
    name = "TargetBinderRetrievalAgent"
    thought = "Retrieve known ligands for the target from ChEMBL, PubChem, BindingDB."
    action = "retrieve_binders"

    def _run_source(self, source: str, func, *args) -> tuple[list[BinderRecord], bool, str]:
        """Run one binder source independently and record typed telemetry."""
        start_time = _utc_now()
        started = time.monotonic()
        timeout = _request_timeout()
        try:
            binders, ok = func(*args)
            binders = list(binders or [])
            status = "SUCCESS" if binders and ok else "SOURCE_EMPTY"
            self._source_telemetry.append(_telemetry_row(
                source=source,
                start_time=start_time,
                started=started,
                timeout=timeout,
                retry_count=0,
                cache_hit=False,
                records_returned=len(binders),
                final_status=status,
            ))
            return binders, bool(ok and binders), status
        except BaseException as exc:  # noqa: BLE001 - each source fails independently
            status = _source_status_from_exception(exc)
            self._source_telemetry.append(_telemetry_row(
                source=source,
                start_time=start_time,
                started=started,
                timeout=timeout,
                retry_count=MAX_RETRIES,
                cache_hit=False,
                records_returned=0,
                final_status=status,
                error_type=type(exc).__name__,
            ))
            return [], False, status

    def _record_fallback(self, state: WorkflowState, source: str, records: list[BinderRecord],
                         fallback_used: str) -> None:
        state.retrieval_telemetry.append(_telemetry_row(
            source=source,
            start_time=_utc_now(),
            started=time.monotonic(),
            timeout=0.0,
            retry_count=0,
            cache_hit=False,
            records_returned=len(records),
            fallback_used=fallback_used,
            final_status="SUCCESS" if records else "SOURCE_EMPTY",
        ))

    @staticmethod
    def _finalize_retrieval_state(state: WorkflowState, binders: list[BinderRecord]) -> None:
        statuses = [row.get("final_status", "") for row in state.retrieval_telemetry]
        external_failures = {"SOURCE_TIMEOUT", "SOURCE_RATE_LIMITED", "SOURCE_UNAVAILABLE"}
        failure_statuses = [s for s in statuses if s in external_failures]
        state.retrieved_binders = binders[:100]
        if state.retrieved_binders:
            state.execution_status = "PARTIAL_SUCCESS" if failure_statuses else "SUCCESS"
            state.evidence_status = "VERIFIED_BINDER_FOUND"
            state.answer_status = "ANSWERABLE"
            state.retrieval_status = state.execution_status
            return
        if failure_statuses:
            if "SOURCE_TIMEOUT" in failure_statuses:
                state.execution_status = "SOURCE_TIMEOUT"
            elif "SOURCE_RATE_LIMITED" in failure_statuses:
                state.execution_status = "SOURCE_RATE_LIMITED"
            else:
                state.execution_status = "SOURCE_UNAVAILABLE"
            state.evidence_status = "UNDETERMINED"
            state.answer_status = "ABSTAIN"
            state.retrieval_status = state.execution_status
            return
        state.execution_status = "NO_VERIFIED_BINDER"
        state.evidence_status = "NO_VERIFIED_BINDER"
        state.answer_status = "ABSTAIN"
        state.retrieval_status = "NO_VERIFIED_BINDER"

    def _execute(self, state: WorkflowState) -> WorkflowState:
        self._source_telemetry: list[dict[str, Any]] = []
        state.retrieval_telemetry = []
        target_name = state.parsed_objective.target_name or ""
        uniprot_id = ""
        if state.target_record:
            uniprot_id = getattr(state.target_record, "uniprot_id", "") or ""

        if not target_name and not uniprot_id:
            state.warnings.append("TargetBinderRetrievalAgent: No target name or UniProt ID available.")
            state.execution_status = "NO_VERIFIED_BINDER"
            state.evidence_status = "UNDETERMINED"
            state.answer_status = "ABSTAIN"
            return state

        # Input propagation + scheduling repair: when the caller supplies the
        # warhead, or the runtime is offline, do not spend the budget on a
        # hanging network query. Use the supplied/curated binder set instead.
        objective = state.parsed_objective
        if OFFLINE or objective.warhead_smiles:
            local = self._load_local_binders(target_name)
            self._record_fallback(state, "local_curated", local, "offline_or_supplied_warhead")
            self._finalize_retrieval_state(state, local)
            reason = "warhead supplied" if objective.warhead_smiles else "offline mode"
            state.warnings.append(
                f"TargetBinderRetrievalAgent: network skipped ({reason}); "
                f"{len(local)} curated binder(s) used."
            )
            return state

        all_binders: list[BinderRecord] = []
        sources_used: list[str] = []
        # 1. ChEMBL search
        binders, ok, status = self._run_source("ChEMBL", self._search_chembl, target_name, uniprot_id)
        all_binders.extend(binders)
        if ok:
            sources_used.append("ChEMBL")
        elif status != "SOURCE_EMPTY":
            state.warnings.append(f"TargetBinderRetrievalAgent: ChEMBL {status}; continuing.")

        # 2. PubChem enrichment is useful but non-blocking.
        if all_binders:
            pubchem_binders, ok2, pubchem_status = self._run_source("PubChem", self._enrich_from_pubchem, all_binders)
            if ok2:
                sources_used.append("PubChem")
            elif pubchem_status != "SOURCE_EMPTY":
                state.warnings.append(f"TargetBinderRetrievalAgent: PubChem {pubchem_status}; continuing.")

        # 3. BindingDB.
        if uniprot_id:
            bdb_binders, ok3, bdb_status = self._run_source("BindingDB", self._search_bindingdb, uniprot_id)
            all_binders.extend(bdb_binders)
            if ok3:
                sources_used.append("BindingDB")
            elif bdb_status == "SOURCE_EMPTY":
                status = getattr(self, "_last_bindingdb_status", "") or "empty"
                state.warnings.append(
                    "BindingDB REST returned no records "
                    f"(status={status}; the public REST API requires no API key — "
                    "the query simply had no hits)."
                )
            else:
                state.warnings.append(f"TargetBinderRetrievalAgent: BindingDB {bdb_status}; continuing.")

        state.retrieval_telemetry.extend(self._source_telemetry)

        # 4. Fall back: (a) DOI-cited local warhead table (real evidence,
        #    provenance-tagged), then (b) demo-gated curated rows.
        if not all_binders:
            cited_binders = self._load_cited_local_binders(target_name, uniprot_id)
            all_binders.extend(cited_binders)
            self._record_fallback(state, "citation_tagged_local_warhead_db",
                                  cited_binders, "citation_tagged_local_warhead_db")
            if cited_binders:
                sources_used.append("citation_tagged_local_warhead_db")
                do = sorted({b.metadata.get("article_doi") for b in cited_binders if b.metadata.get("article_doi")})
                state.warnings.append(
                    "TargetBinderRetrievalAgent: live sources unavailable; used "
                    f"{len(cited_binders)} DOI-cited local warhead-table row(s) "
                    f"(protacSpace warhead.csv; DOIs={do})."
                )
            local_binders = self._load_local_binders(target_name)
            all_binders.extend(local_binders)
            self._record_fallback(state, "local_curated", local_binders, "local_curated")
            if local_binders:
                sources_used.append("local_curated")

        # Deduplicate by SMILES
        seen_smiles = set()
        deduplicated: list[BinderRecord] = []
        for b in all_binders:
            canonical = b.smiles.strip() if b.smiles else ""
            if canonical and canonical not in seen_smiles:
                seen_smiles.add(canonical)
                deduplicated.append(b)

        # Sort by potency (best first)
        deduplicated.sort(key=lambda x: x.p_activity if x.p_activity else 0.0, reverse=True)

        self._finalize_retrieval_state(state, deduplicated)
        if sources_used:
            state.warnings.append(f"TargetBinderRetrievalAgent: Retrieved {len(deduplicated)} binders from {', '.join(sources_used)}.")
        else:
            if state.evidence_status == "UNDETERMINED":
                state.warnings.append(
                    "TargetBinderRetrievalAgent: binder evidence is undetermined because one or more "
                    "sources were unavailable; this is not evidence that no binder exists."
                )
            else:
                state.warnings.append("TargetBinderRetrievalAgent: No verified binders found from available sources.")
        for line in cache_replay_warning():
            state.warnings.append(f"TargetBinderRetrievalAgent: {line}")

        return state

    # ── ChEMBL ─────────────────────────────────
    def _resolve_chembl_target(self, target_name: str, uniprot_id: str) -> str | None:
        """Resolve a target to its ChEMBL target id via UniProt accession or name."""
        query = uniprot_id if uniprot_id else target_name
        url = f"{CHEMBL_BASE}/target/search.json?q={urllib.parse.quote(query)}"
        data = _cached_request(url, f"chembl_tgt_{query}")
        if data:
            targets = data.get("targets", [])
            if targets:
                return targets[0].get("target_chembl_id", "")
        return None

    def _search_chembl(self, target_name: str, uniprot_id: str) -> tuple[list[BinderRecord], bool]:
        """Fetch measured binder activities from ChEMBL.

        Uses the /activity endpoint (which embeds canonical_smiles and
        pchembl_value) — 2 HTTP calls total, not one per assay/activity.
        """
        binders: list[BinderRecord] = []
        chembl_id = self._resolve_chembl_target(target_name, uniprot_id)
        if not chembl_id:
            return binders, False

        url = (
            f"{CHEMBL_BASE}/activity.json?target_chembl_id={chembl_id}"
            "&limit=100&order_by=pchembl_value"
        )
        data = _cached_request(url, f"chembl_activity_{chembl_id}")
        # Census: ChEMBL reports the total hit count in the response envelope
        # BEFORE the records — the recall denominator the architecture spec needs.
        self._last_census = {
            "source": "chembl", "query": url, "n_reported_total":
            (data or {}).get("meta", {}).get("total_count") if data else None,
        }
        if not data:
            return binders, False

        for act in data.get("activities", []):
            smiles = act.get("canonical_smiles") or ""
            if not smiles:
                continue
            # Unit normalization: prefer pchembl_value (-log10 M) when present.
            activity_nM = None
            p_act = None
            try:
                pchembl = act.get("pchembl_value")
                if pchembl:
                    p_act = float(pchembl)
                    activity_nM = 10.0 ** (9.0 - p_act)
                else:
                    raw = float(act.get("standard_value", 0) or 0)
                    units = (act.get("standard_units") or "nM").lower().replace("\u00b5", "u")
                    mult = {"nm": 1.0, "um": 1e3, "mm": 1e6, "m": 1e9}.get(units, 1.0)
                    activity_nM = raw * mult if raw > 0 else None
                    p_act = self.toolbox.compute_p_activity(activity_nM) if activity_nM else None
            except (ValueError, TypeError):
                activity_nM, p_act = None, None

            assay_id = act.get("assay_chembl_id", "")
            record = BinderRecord(
                name=act.get("molecule_chembl_id", f"CHEMBL_{len(binders)}"),
                target=target_name,
                smiles=smiles,
                activity_type=act.get("standard_type", "IC50") or "IC50",
                activity_nM=activity_nM,
                p_activity=p_act,
                assay_confidence=0.5,
                source=f"ChEMBL (assay {assay_id})",
                metadata={
                    "source_db": "ChEMBL",
                    "assay_chembl_id": assay_id,
                    "target_chembl_id": chembl_id,
                    "standard_units": act.get("standard_units"),
                    "evidence_type": "measured_activity",
                    "needs_exit_vector_hypothesis": True,
                    "record_url": f"https://www.ebi.ac.uk/chembl/assay_report_card/{assay_id}/"
                    if assay_id else "",
                },
            )
            binders.append(record)

        # Deduplicate by full InChIKey (stereo-aware) — same molecule from
        # three sources must count once (AGENT_ARCHITECTURE_UPDATE §0.1/§1.1).
        from rdkit import Chem
        from rdkit.Chem.inchi import MolToInchiKey
        seen: dict = {}
        for b in binders:
            mol = Chem.MolFromSmiles(b.smiles.strip()) if b.smiles else None
            key = MolToInchiKey(mol) if mol is not None else b.smiles.strip()
            if key not in seen or (b.p_activity or 0) > (seen[key].p_activity or 0):
                seen[key] = b
        deduped = list(seen.values())
        if hasattr(self, "_last_census") and self._last_census:
            self._last_census["n_fetched"] = len(binders)
            self._last_census["n_after_dedup"] = len(deduped)
            self._last_census["n_returned"] = len(deduped)
            self._last_census["selection_rule"] = "pchembl_desc"
        return deduped, len(deduped) > 0

    # ── PubChem ─────────────────────────────────
    def _enrich_from_pubchem(self, binders: list[BinderRecord]) -> tuple[list[BinderRecord], bool]:
        """Enrich existing binders with PubChem properties."""
        enriched = []
        for b in binders[:20]:  # limit to first 20 to be polite
            if not b.smiles:
                continue
            url = f"{PUBCHEM_BASE}/compound/smiles/{urllib.parse.quote(b.smiles)}/property/CanonicalSMILES,InChIKey,MolecularFormula,MolecularWeight/JSON"
            data = _cached_request(url, f"pubchem_{hashlib.md5(b.smiles.encode()).hexdigest()}")
            if data:
                props = data.get("PropertyTable", {}).get("Properties", [{}])[0]
                if props:
                    b.metadata["pubchem_inchikey"] = props.get("InChIKey", "")
                    b.metadata["pubchem_mw"] = props.get("MolecularWeight", "")
                    b.source += " + PubChem"
                    enriched.append(b)
        return enriched, len(enriched) > 0

    # ── BindingDB ───────────────────────────────
    def _bindingdb_needs_key(self) -> bool:
        """Deprecated: BindingDB's public REST API does not require an API key.

        Kept as a compatibility shim for callers that gate on it; always False.
        See https://www.bindingdb.org/rwd/bind/BindingDBRESTfulAPI.jsp.
        """
        return False

    def _search_bindingdb(self, uniprot_id: str) -> tuple[list[BinderRecord], bool]:
        """Fetch measured BindingDB binders through the public REST API.

        No API key is required. The singular ``getLigandsByUniprot`` endpoint is
        used and both documented JSON response shapes are parsed.
        """
        from protacxtend.tools.bindingdb_lookup import fetch_bindingdb_rest

        result = fetch_bindingdb_rest(uniprot_id, cutoff=1000, fetcher=_cached_request)
        self._last_bindingdb_status = result.get("status", "")
        self._last_bindingdb_url = result.get("url", "")
        binders: list[BinderRecord] = []
        for rec in result.get("records") or []:
            activity_nM = rec.get("activity_value")
            p_act = self.toolbox.compute_p_activity(activity_nM) if activity_nM else None
            monomer_id = rec.get("monomer_id", "")
            binders.append(BinderRecord(
                name=rec.get("molecule_name") or f"BDB_{monomer_id}",
                target=uniprot_id,
                smiles=rec.get("smiles", ""),
                activity_type=rec.get("activity_type") or "unknown",
                activity_nM=activity_nM,
                p_activity=p_act,
                assay_confidence=float(rec.get("confidence_score", 0.6) or 0.6),
                source=f"BindingDB REST (monomer {monomer_id})" if monomer_id else "BindingDB REST",
                metadata={
                    "source_db": "BindingDB",
                    "monomer_id": monomer_id,
                    "doi": rec.get("doi", ""),
                    "pmid": rec.get("pmid", ""),
                    "record_url": rec.get("source_url", ""),
                    "evidence_type": "measured_activity",
                    "needs_exit_vector_hypothesis": True,
                },
            ))
        # Deduplicate by canonical SMILES, keeping the most potent measurement.
        best: dict[str, BinderRecord] = {}
        for b in binders:
            key = (b.smiles or "").strip()
            if not key:
                continue
            current = best.get(key)
            if current is None or (b.activity_nM or 1e12) < (current.activity_nM or 1e12):
                best[key] = b
        deduped = sorted(best.values(), key=lambda x: x.activity_nM or 1e12)
        return deduped, len(deduped) > 0

    # ── Local fallback ──────────────────────────
    def _load_local_binders(self, target_name: str) -> list[BinderRecord]:
        binders: list[BinderRecord] = []
        try:
            curated = self.toolbox.load_curated_warheads()
            target_upper = target_name.upper()
            for row in curated:
                row_target = (row.get("target", "") or "").upper()
                if target_upper and target_upper in row_target:
                    # Propagate the row's real source so demo seeds keep their
                    # demo tag: SCIENTIFIC mode drops them downstream. Hard-
                    # coding "local_curated" here would let demo warheads pass
                    # the scientific-mode filter (fixture leak F-03 class bug).
                    record = BinderRecord(
                        name=row.get("name", "local"),
                        target=target_name,
                        smiles=row.get("smiles", ""),
                        activity_type="IC50",
                        activity_nM=None,
                        source=(row.get("source") or "local_curated"),
                        metadata={"evidence_type": "local_curated_row"},
                    )
                    binders.append(record)
        except Exception:
            pass
        return binders

    # ── Cited local evidence tier (non-demo, DOI-cited) ──────────────────
    def _load_cited_local_binders(self, target_name: str, uniprot_id: str) -> list[BinderRecord]:
        """Real, DOI-cited binder rows from the shipped protacSpace warhead
        table (data/protac_repos/repos/protacSpace/data/raw/warhead.csv).

        Used only when every live source failed. Rows must be target-matched
        (UniProt accession preferred), carry an Article DOI, and carry a
        measured potency (IC50/Kd n_M). Every record is provenance-tagged with
        the table name, DOI, and ChEMBL id. This is a cited-evidence tier, not
        a fixture and not a filter relaxation.
        """
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "data", "protac_repos", "repos", "protacSpace", "data", "raw", "warhead.csv",
        )
        if not os.path.exists(path):
            return []
        binders: list[BinderRecord] = []
        try:
            with open(path, newline="", encoding="utf-8", errors="replace") as f:
                for row in csv.DictReader(f):
                    row_uniprot = (row.get("Uniprot") or "").strip().upper()
                    row_target = (row.get("Target") or "").strip().upper()
                    matches = (
                        (uniprot_id and row_uniprot == uniprot_id.strip().upper())
                        or (target_name and target_name.upper() in row_target)
                    )
                    if not matches:
                        continue
                    doi = (row.get("Article DOI") or "").strip()
                    if not doi:
                        continue
                    activity_nM = self._parse_activity_nM_cited(row)
                    if activity_nM is None:
                        continue
                    bindsite = True
                    binders.append(BinderRecord(
                        name=(row.get("Name") or row.get("Compound ID") or f"cited_{row_uniprot}"),
                        target=row.get("Target") or target_name,
                        smiles=(row.get("Smiles") or "").strip(),
                        activity_type="IC50/Kd",
                        activity_nM=activity_nM,
                        p_activity=self.toolbox.compute_p_activity(activity_nM) if activity_nM else None,
                        assay_confidence=0.6,
                        source=f"protacSpace warhead.csv (DOI {doi})",
                        metadata={
                            "evidence_type": "cited_measured_activity",
                            "article_doi": doi,
                            "chembl_id": (row.get("ChEMBL") or "").strip(),
                            "inchikey": (row.get("InChI Key") or "").strip(),
                            "needs_exit_vector_hypothesis": True,
                            "record_table": "data/protac_repos/repos/protacSpace/data/raw/warhead.csv",
                        },
                    ))
        except Exception:  # noqa: BLE001 - fallback must never crash retrieval
            return []
        return binders

    @staticmethod
    def _parse_activity_nM_cited(row: dict) -> float | None:
        for key in ("IC50 (nM)", "Kd (nM)", "Ki (nM)", "EC50 (nM)"):
            raw = (row.get(key) or "").strip()
            if not raw or raw == "0":
                continue
            first = raw.split("/")[0].split()[0].strip()
            try:
                value = float(first)
            except ValueError:
                continue
            if value > 0:
                return value
        return None

    def _observation(self, state: WorkflowState) -> str:
        binders = state.retrieved_binders
        if binders:
            p_values = [b.p_activity for b in binders if b.p_activity is not None]
            if p_values:
                return f"binders={len(binders)}, max_pActivity={max(p_values):.1f}"
            return f"binders={len(binders)}, max_pActivity=unavailable"
        return "binders=0"

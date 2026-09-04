"""Target binder retrieval agent — searches ChEMBL, PubChem, BindingDB for known ligands."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import time
import urllib.parse
import urllib.request
import urllib.error
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

TIMEOUT = 30
MAX_RETRIES = 5
DELAY = 0.5  # seconds between requests (2/sec)
CACHE_DIR = None  # set to a path to enable disk caching

# ─────────────────────────────────────────────
# Rate-limited HTTP client with caching
# ─────────────────────────────────────────────
_last_request_time = 0.0
_cache: Dict[str, Any] = {}

def _rate_limit():
    global _last_request_time
    now = time.time()
    since = now - _last_request_time
    if since < DELAY:
        time.sleep(DELAY - since)
    _last_request_time = time.time()

def _cached_request(url: str, cache_key: str = "") -> Optional[Dict[str, Any]]:
    cache_key = cache_key or hashlib.md5(url.encode()).hexdigest()
    if cache_key in _cache:
        return _cache[cache_key]

    _rate_limit()
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "ProtacPilot/1.0"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                data = json.loads(resp.read().decode())
                _cache[cache_key] = data
                return data
        except urllib.error.HTTPError as e:
            last_error = e
            if e.code == 429:  # rate limited — respect Retry-After
                retry_after = float(e.headers.get("Retry-After", 5)) if e.headers.get("Retry-After") else 5.0
                time.sleep(min(retry_after, 20.0))
            elif attempt < MAX_RETRIES:
                time.sleep(DELAY * (2 ** attempt))  # exponential backoff
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
            last_error = e
            if attempt < MAX_RETRIES:
                time.sleep(DELAY * (2 ** attempt))  # exponential backoff
    return None

def _cached_request_text(url: str, cache_key: str = "") -> Optional[str]:
    cache_key = cache_key or hashlib.md5(url.encode()).hexdigest()
    if cache_key in _cache:
        return _cache[cache_key]

    _rate_limit()
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers={"Accept": "text/csv", "User-Agent": "ProtacPilot/1.0"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                text = resp.read().decode()
                _cache[cache_key] = text
                return text
        except Exception as e:
            if attempt < MAX_RETRIES:
                time.sleep(DELAY * (2 ** attempt))
    return None


class TargetBinderRetrievalAgent(ReActAgent):
    name = "TargetBinderRetrievalAgent"
    thought = "Retrieve known ligands for the target from ChEMBL, PubChem, BindingDB."
    action = "retrieve_binders"

    def _execute(self, state: WorkflowState) -> WorkflowState:
        target_name = state.parsed_objective.target_name or ""
        uniprot_id = ""
        if state.target_record:
            uniprot_id = getattr(state.target_record, "uniprot_id", "") or ""
        
        if not target_name and not uniprot_id:
            state.warnings.append("TargetBinderRetrievalAgent: No target name or UniProt ID available.")
            return state

        all_binders: List[BinderRecord] = []
        sources_used: List[str] = []

        # 1. ChEMBL search
        binders, ok = self._search_chembl(target_name, uniprot_id)
        all_binders.extend(binders)
        if ok:
            sources_used.append("ChEMBL")
        
        # 2. PubChem (only if we have compounds to cross-reference)
        if all_binders:
            pubchem_binders, ok2 = self._enrich_from_pubchem(all_binders)
            if ok2:
                sources_used.append("PubChem")

        # 3. BindingDB (best for measured affinities; REST requires an API key
        #    since 2023 — wrapper stays for when BINDINGDB_API_KEY is set)
        if uniprot_id:
            bdb_binders, ok3 = self._search_bindingdb(uniprot_id)
            all_binders.extend(bdb_binders)
            if ok3:
                sources_used.append("BindingDB")
            elif self._bindingdb_needs_key():
                state.warnings.append(
                    "BindingDB REST needs an API key (BINDINGDB_API_KEY); ChEMBL covers binding data."
                )

        # 4. Fall back to local curated data
        if not all_binders:
            local_binders = self._load_local_binders(target_name)
            all_binders.extend(local_binders)
            if local_binders:
                sources_used.append("local_curated")

        # Deduplicate by SMILES
        seen_smiles = set()
        deduplicated: List[BinderRecord] = []
        for b in all_binders:
            canonical = b.smiles.strip() if b.smiles else ""
            if canonical and canonical not in seen_smiles:
                seen_smiles.add(canonical)
                deduplicated.append(b)

        # Sort by potency (best first)
        deduplicated.sort(key=lambda x: x.p_activity if x.p_activity else 0.0, reverse=True)

        state.retrieved_binders = deduplicated[:100]  # cap at 100
        if sources_used:
            state.warnings.append(f"TargetBinderRetrievalAgent: Retrieved {len(deduplicated)} binders from {', '.join(sources_used)}.")
        else:
            state.warnings.append("TargetBinderRetrievalAgent: No binders found from any source.")

        return state

    # ── ChEMBL ─────────────────────────────────
    def _resolve_chembl_target(self, target_name: str, uniprot_id: str) -> Optional[str]:
        """Resolve a target to its ChEMBL target id via UniProt accession or name."""
        query = uniprot_id if uniprot_id else target_name
        url = f"{CHEMBL_BASE}/target/search.json?q={urllib.parse.quote(query)}"
        data = _cached_request(url, f"chembl_tgt_{query}")
        if data:
            targets = data.get("targets", [])
            if targets:
                return targets[0].get("target_chembl_id", "")
        return None

    def _search_chembl(self, target_name: str, uniprot_id: str) -> Tuple[List[BinderRecord], bool]:
        """Fetch measured binder activities from ChEMBL.

        Uses the /activity endpoint (which embeds canonical_smiles and
        pchembl_value) — 2 HTTP calls total, not one per assay/activity.
        """
        binders: List[BinderRecord] = []
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
    def _enrich_from_pubchem(self, binders: List[BinderRecord]) -> Tuple[List[BinderRecord], bool]:
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
        """True when the BindingDB REST layer requires an API key (2023+ policy)."""
        import os as _os
        return not _os.environ.get("BINDINGDB_API_KEY")

    def _search_bindingdb(self, uniprot_id: str) -> Tuple[List[BinderRecord], bool]:
        binders: List[BinderRecord] = []
        api_key = os.environ.get("BINDINGDB_API_KEY", "")
        url = f"{BINDINGDB_BASE}/getLigandsByUniprot?uniprot={uniprot_id};100&response=application/json"
        if api_key:
            url += f"&api_key={api_key}"
        data = _cached_request(url, f"bdb_{uniprot_id}")
        if not data:
            return binders, False

        for entry in (data if isinstance(data, list) else data.get("ligands", [])):
            smiles = (entry.get("smiles", "") or entry.get("ligandSmiles", "") or "")
            if not smiles:
                continue
            try:
                ki_nM = float(entry.get("ki", 0) or 0)
                ic50_nM = float(entry.get("ic50", 0) or 0)
                activity_nM = ki_nM if ki_nM > 0 else ic50_nM
                activity_type = "Ki" if ki_nM > 0 else "IC50"
                p_act = self.toolbox.compute_p_activity(activity_nM) if activity_nM > 0 else None
            except (ValueError, TypeError):
                activity_nM = 0.0
                p_act = None

            record = BinderRecord(
                name=entry.get("name", entry.get("ligandName", f"BDB_{len(binders)}")),
                target=uniprot_id,
                smiles=smiles,
                activity_type=activity_type if activity_nM > 0 else "unknown",
                activity_nM=activity_nM if activity_nM > 0 else None,
                p_activity=p_act,
                assay_confidence=0.6,
                source="BindingDB",
            )
            binders.append(record)

        return binders, len(binders) > 0

    # ── Local fallback ──────────────────────────
    def _load_local_binders(self, target_name: str) -> List[BinderRecord]:
        binders: List[BinderRecord] = []
        try:
            curated = self.toolbox.load_curated_warheads()
            target_upper = target_name.upper()
            for row in curated:
                row_target = (row.get("target", "") or "").upper()
                if target_upper and target_upper in row_target:
                    record = BinderRecord(
                        name=row.get("name", "local"),
                        target=target_name,
                        smiles=row.get("smiles", ""),
                        activity_type="IC50",
                        activity_nM=None,
                        source="local_curated",
                    )
                    binders.append(record)
        except Exception:
            pass
        return binders

    def _observation(self, state: WorkflowState) -> str:
        binders = state.retrieved_binders
        if binders:
            p_values = [b.p_activity for b in binders if b.p_activity is not None]
            if p_values:
                return f"binders={len(binders)}, max_pActivity={max(p_values):.1f}"
            return f"binders={len(binders)}, max_pActivity=unavailable"
        return "binders=0"

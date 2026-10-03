"""Tool-backed target resolver (requirement 2).

- UniProt accessions are checked directly via the entry endpoint.
- Names and symbols are searched against reviewed UniProt within the
  requested organism (gene_exact first, then alias / protein-name queries);
  the packaged curated table is consulted first for symbols/aliases.
- Candidates are returned with match types; fuzzy matches are suggestions,
  never silently accepted as verified identity.
- A versioned local cache replays live responses when the API is unavailable;
  the record reports whether identity came from live UniProt or cache.
- Collisions, protein families, isoforms and mutations are handled
  explicitly (alternatives list; mutation/isoform stripped from identity).
"""

from __future__ import annotations

import csv, difflib, hashlib, json, os, re, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from protacxtend.request.model import AMBIGUOUS_MAP, TargetMention, TargetResolution

ROOT = Path(__file__).resolve().parents[2]
CACHE_ROOT = ROOT / "data" / "request_cache"
CACHE_SCHEMA_VERSION = "uniprot-request-v1"

UNIPROT_BASE = "https://rest.uniprot.org/uniprotkb"
ACCESSION_RE = re.compile(
    r"(?:[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2})"
)
def _levenshtein(a: str, b: str) -> int:
    """Classic edit distance; used for CONSTRAINED typo matching only."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


TAXID = {"homo sapiens": 9606, "human": 9606, "mus musculus": 10090, "mouse": 10090,
         "rat": 10116, "rattus norvegicus": 10116, "zebrafish": 7955, "danio rerio": 7955}

#: Supplemental canonical map for common targets NOT in the curated table
#: (offline-safe; method flagged so reviewers can distinguish from curated).
_SUPPLEMENTAL: dict[str, dict[str, Any]] = {
    "KRAS": {"symbol": "KRAS", "uniprot_id": "P01116", "organism": "Homo sapiens",
             "aliases": ["KRAS", "KRAS4A", "KRAS4B", "K-RAS", "C-K-RAS"]},
    "BRAF": {"symbol": "BRAF", "uniprot_id": "P15056", "organism": "Homo sapiens", "aliases": ["BRAF", "B-RAF"]},
    "TP53": {"symbol": "TP53", "uniprot_id": "P04637", "organism": "Homo sapiens", "aliases": ["TP53", "P53"]},
    "BTK":  {"symbol": "BTK", "uniprot_id": "Q06187", "organism": "Homo sapiens", "aliases": ["BTK", "AGMX1", "ATK"]},
    "STAT3": {"symbol": "STAT3", "uniprot_id": "P40763", "organism": "Homo sapiens", "aliases": ["STAT3", "APRF"]},
    "HMGB2": {"symbol": "HMGB2", "uniprot_id": "P26583", "organism": "Homo sapiens",
              "aliases": ["HMGB2", "HMG2", "HMG-2"]},
}

#: Packaged curated table: symbol -> record (first source; DOIs/binder counts live in the CSV).
_CURATED: dict[str, dict[str, Any]] = {}
_ALIAS: dict[str, str] = {}
_CURATED_PATH = ROOT / "protacxtend" / "data" / "curated_targets.csv"
if _CURATED_PATH.exists():
    with open(_CURATED_PATH, newline="") as f:
        for row in csv.DictReader(f):
            sym = (row.get("gene_symbol") or "").strip().upper()
            if not sym:
                continue
            _CURATED[sym] = {
                "symbol": sym,
                "uniprot_id": (row.get("uniprot_id") or "").strip(),
                "organism": (row.get("organism") or "").strip() or "Homo sapiens",
                "aliases": [a.strip() for a in (row.get("synonyms") or "").split("|") if a.strip()],
                "structures": [s.strip() for s in (row.get("structures") or "").split("|") if s.strip()],
                "known_binder_count": (row.get("known_binder_count") or "").strip(),
            }
            for alias in _CURATED[sym]["aliases"]:
                _ALIAS[alias.strip().upper()] = sym

_OFFLINE = os.environ.get("PROTACXTEND_PLANNER_OFFLINE", "") in ("1", "true", "yes")


def set_offline(value: bool = True) -> None:
    global _OFFLINE
    _OFFLINE = bool(value)


def _cache_path(query_key: str, organism_taxid: int) -> Path:
    h = hashlib.sha1(f"{CACHE_SCHEMA_VERSION}|{organism_taxid}|{query_key}".encode()).hexdigest()
    return CACHE_ROOT / CACHE_SCHEMA_VERSION / f"{h}.json"


def _read_cache(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        with open(path) as f:
            rec = json.load(f)
        if rec.get("schema_version") != CACHE_SCHEMA_VERSION:
            return None
        return rec
    except Exception:  # noqa: BLE001
        return None


def _write_cache(path: Path, payload: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        rec = {"schema_version": CACHE_SCHEMA_VERSION,
               "fetched_at": datetime.now(timezone.utc).isoformat(),
               "source": "live", "payload": payload}
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(rec, f)
        tmp.replace(path)
    except Exception:  # noqa: BLE001 - cache must never break resolution
        return


def _uniprot_search(query: str, *, offline: bool, source: str) -> tuple[list[dict], str]:
    """Reviewed UniProt search; returns (hits, source) with source live|cache."""
    if offline:
        return [], "offline"
    url = (f"{UNIPROT_BASE}/search?query=" + urllib.parse.quote(query)
           + "&fields=accession,gene_names,protein_name,organism_name,organism_id"
             "&size=25&format=json")
    key = hashlib.sha1(url.encode()).hexdigest()
    cache_path = CACHE_ROOT / CACHE_SCHEMA_VERSION / f"{key}.json"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "PROTACXtend/1.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
        _write_cache(cache_path, data)
        return (data.get("results") or []), "live"
    except Exception:  # noqa: BLE001 - replay cache
        rec = _read_cache(cache_path)
        if rec:
            return (rec.get("payload", {}).get("results") or []), "cache"
        return [], "unavailable"


def _hit_to_dict(h: dict) -> dict[str, Any]:
    genes = (h.get("genes") or [])
    g0 = genes[0] if genes else {}
    gene_name = (g0.get("geneName") or {}).get("value", "")
    gene_names = " ".join(sorted({(g.get("geneName") or {}).get("value", "") for g in genes if g.get("geneName")}))
    orgo = h.get("organism") or {}
    prot = h.get("proteinDescription") or {}
    rec = (prot.get("recommendedName") or {})
    alt = " / ".join(a.get("fullName", {}).get("value", "") for a in (prot.get("alternativeNames") or [])[:3])
    return {
        "accession": h.get("primaryAccession", ""),
        "gene_symbol": gene_name,
        "gene_names": gene_names,
        "protein_name": (rec.get("fullName", {}).get("value", "") or "") + ((" / " + alt) if alt else ""),
        "organism": orgo.get("scientificName", ""),
        "taxid": orgo.get("taxonId", 0),
        "url": f"https://www.uniprot.org/uniprotkb/{h.get('primaryAccession', '')}",
    }


def resolve_target(mention: TargetMention, *, offline: Optional[bool] = None) -> TargetResolution:
    """Resolve one target mention with the tool chain (curated -> UniProt)."""
    offline = bool(offline) if offline is not None else _OFFLINE
    raw = (mention.raw or "").strip()
    organism = (mention.organism or "Homo sapiens").strip()
    taxid = TAXID.get(organism.lower(), 9606 if "human" in organism.lower() or organism.lower() == "homo sapiens" else 0)
    if not taxid:
        return TargetResolution(organism=organism, match_type="none", status="unknown", resolver_source="none")
    org_clause = f"organism_id:{taxid}" if taxid else ""

    # 1) Direct UniProt accession
    if ACCESSION_RE.fullmatch(raw.upper()):
        acc = raw.upper()
        url = f"{UNIPROT_BASE}/{acc}.json"
        cache_path = CACHE_ROOT / CACHE_SCHEMA_VERSION / f"acc_{acc}.json"
        hits: list[dict] = []
        source = "unavailable"
        if not offline:
            try:
                req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "PROTACXtend/1.0"})
                with urllib.request.urlopen(req, timeout=20) as resp:
                    h = json.loads(resp.read().decode())
                _write_cache(cache_path, h)
                hits, source = [h], "live"
            except Exception:  # noqa: BLE001
                rec = _read_cache(cache_path)
                if rec:
                    hits, source = [rec["payload"]], "cache"
        elif (rec := _read_cache(cache_path)):
            hits, source = [rec["payload"]], "cache"
        if hits:
            h = _hit_to_dict(hits[0])
            return TargetResolution(
                symbol=h["gene_symbol"], uniprot_id=h["accession"], organism=h["organism"],
                organism_taxid=h["taxid"], matched_name=h["protein_name"], match_type="accession",
                source_url=h["url"], resolver_source="uniprot_" + source if source in ("live", "cache") else "none",
                status="verified", confidence=0.98,
            )
        return TargetResolution(symbol=raw, match_type="accession", status="unknown",
                                resolver_source="none", source_url=url)

    # 2) Curated table (symbol + alias) — human-packaged, only when the
    #    requested organism is human; non-human requests go to UniProt so the
    #    human curated record is never served as a mouse/rat/zebrafish identity.
    sym = raw.upper()
    curated_sym = _ALIAS.get(sym, sym if sym in _CURATED else "")
    if curated_sym in _CURATED:
        c = _CURATED[curated_sym]
        human = "human" in (c["organism"] or "").lower() or "homo" in (c["organism"] or "").lower()
        nonhuman_requested = taxid not in (0, 9606)
        if human and not nonhuman_requested:
            match_type = "alias" if curated_sym != sym else "exact_symbol"
            return TargetResolution(
                symbol=curated_sym, uniprot_id=c["uniprot_id"], organism=c["organism"],
                matched_name=curated_sym, match_type=match_type, source_url="packaged curated_targets.csv",
                resolver_source="curated_table", status="verified", confidence=0.95,
            )

    # 2b) Supplemental canonical map (offline-safe; flagged, not curated)
    if sym in _SUPPLEMENTAL:
        sup = _SUPPLEMENTAL[sym]
        return TargetResolution(
            symbol=sup["symbol"], uniprot_id=sup["uniprot_id"], organism=sup["organism"],
            matched_name=sup["symbol"], match_type="exact_symbol",
            resolver_source="packaged_supplemental_map", status="verified", confidence=0.85,
        )

    # 3) UniProt gene_exact (reviewed, organism)
    query = f"gene_exact:{sym} AND reviewed:true"
    if org_clause:
        query += f" AND {org_clause}"
    hits, source = _uniprot_search(query, offline=offline, source="gene_exact")
    exact = [_hit_to_dict(h) for h in hits if (h.get("genes") or [])]
    if len(exact) == 1:
        e = exact[0]
        return TargetResolution(symbol=e["gene_symbol"], uniprot_id=e["accession"],
                                organism=e["organism"], organism_taxid=e["taxid"],
                                matched_name=e["protein_name"], match_type="exact_symbol",
                                alternatives=[], source_url=e["url"],
                                resolver_source=("uniprot_live" if source == "live" else "uniprot_cache"),
                                status="verified", confidence=0.9)
    if len(exact) > 1:
        return TargetResolution(symbol=sym, match_type="exact_symbol", status="ambiguous",
                                alternatives=exact, source_url="",
                                resolver_source=("uniprot_live" if source == "live" else "uniprot_cache"),
                                confidence=0.0)

    # 4) Alias / protein-name search (reviewed, organism)
    query2 = f'(gene:{sym} OR protein_name:"{sym}") AND reviewed:true'
    if org_clause:
        query2 += f" AND {org_clause}"
    hits2, source2 = _uniprot_search(query2, offline=offline, source="alias")
    if hits2:
        cands = [_hit_to_dict(h) for h in hits2][:8]
        # prefer a reviewed entry whose gene names contain the symbol verbatim
        for c in cands:
            if sym in {g.upper() for g in c["gene_names"].split()}:
                return TargetResolution(symbol=c["gene_symbol"], uniprot_id=c["accession"],
                                        organism=c["organism"], organism_taxid=c["taxid"],
                                        matched_name=c["protein_name"], match_type="alias",
                                        alternatives=cands, source_url=c["url"],
                                        resolver_source=("uniprot_live" if source2 == "live" else "uniprot_cache"),
                                        status="verified", confidence=0.85)
        # several plausible matches -> ambiguous (never silently converted)
        if len(cands) >= 2:
            return TargetResolution(symbol=sym, match_type="protein_name", status="ambiguous",
                                    alternatives=cands,
                                    resolver_source=("uniprot_live" if source2 == "live" else "uniprot_cache"),
                                    confidence=0.0)
        c = cands[0]
        return TargetResolution(symbol=c["gene_symbol"], uniprot_id=c["accession"],
                                organism=c["organism"], organism_taxid=c["taxid"],
                                matched_name=c["protein_name"], match_type="protein_name",
                                alternatives=[], source_url=c["url"],
                                resolver_source=("uniprot_live" if source2 == "live" else "uniprot_cache"),
                                status="tentative", confidence=0.6)

    # 4b) Canonical curated human symbol requested in a NON-HUMAN organism:
    #      try UniProt for the ortholog (above); if no ortholog evidence is
    #      reachable, keep the gene IDENTITY (symbol), mark TENTATIVE, and let
    #      the plan carry the organism limitation — the trailing organism word
    #      must never displace the resolved symbol.
    if sym in _CURATED and taxid not in (0, 9606):
        c = _CURATED[sym]
        return TargetResolution(
            symbol=sym, uniprot_id=c["uniprot_id"], organism=organism,
            matched_name=(f"{sym} (human ortholog {c['uniprot_id']}); requested {organism} — "
                          "ortholog identity deferred (no reachable UniProt record)"),
            match_type="symbol_human_curated", source_url="packaged curated_targets.csv",
            resolver_source="curated_table", status="tentative", confidence=0.9,
        )

    # 5) Genuinely ambiguous short names (never silently converted)
    if sym in AMBIGUOUS_MAP:
        return TargetResolution(symbol=sym, match_type="symbol", status="ambiguous",
                                alternatives=[{"symbol": s} for s in AMBIGUOUS_MAP[sym]],
                                confidence=0.0, resolver_source="ambiguity_map")

    # 6) CONSTRAINED fuzzy matching: auto-resolve ONLY when the candidate set
    #    separates cleanly (single close match) AND the raw token is a plausible
    #    typo (Levenshtein <= 2, length >= 4). Anything weaker stays a precise
    #    one-turn question ("did you mean X?") — identifiers are never
    #    auto-corrected on weak evidence.
    fallback_source = "offline-local" if offline else ("uniprot_" + (source or source2)) if (source or source2) in ("live", "cache") else "none"
    sug = difflib.get_close_matches(sym, list(_CURATED.keys()), n=1, cutoff=0.55)
    if sug:
        best = sug[0]
        d = _levenshtein(sym, best)
        if d <= 2 and len(sym) >= 4:
            c = _CURATED[best]
            return TargetResolution(
                symbol=best, uniprot_id=c["uniprot_id"], organism=c["organism"],
                matched_name=(f"constrained typo {sym}→{best} (Levenshtein {d}, single curated candidate) — "
                              "auto-resolved; confirmation advised"),
                match_type="typo_constrained", source_url="packaged curated_targets.csv",
                resolver_source="curated_table", status="tentative", confidence=0.9,
                alternatives=[{"symbol": best}],
            )
        return TargetResolution(symbol=sym, match_type="fuzzy", status="unknown",
                                suggestion=best,
                                alternatives=[{"symbol": best}],
                                confidence=0.0,
                                resolver_source=fallback_source)
    return TargetResolution(symbol=raw, match_type="none", status="unknown", confidence=0.0,
                            resolver_source=fallback_source)


def suggestion_symbol(res: TargetResolution) -> str:
    return res.suggestion
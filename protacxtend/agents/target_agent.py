"""Target resolver agent — resolves target name to UniProt ID and structure."""

from __future__ import annotations
import json, logging, os, re, urllib.request, urllib.error, urllib.parse
from typing import Any
from protacxtend.agents.base_agent import ReActAgent
from protacxtend.backend.schemas import WorkflowState

log = logging.getLogger(__name__)

UNIPROT_API = "https://rest.uniprot.org/uniprotkb/search?query={}&format=json&size=1"
ALPHAFOLD_API = "https://alphafold.ebi.ac.uk/api/prediction/{}"


def _norm_tokens(text: str) -> set[str]:
    """Lower-cased alphanumeric tokens (hyphens/punctuation collapsed)."""
    return {t for t in re.split(r"[^a-z0-9]+", (text or "").lower()) if t}


def query_matches_hit(query: str, fields: list[str]) -> bool:
    """True only when *query* genuinely names the resolved entity.

    Fail-closed guard: UniProt full-text search happily returns an unrelated
    protein for a short token (e.g. ``BRD`` -> RLBP1, P12271). We accept a hit
    only when the query tokens form a whole-token match against the gene
    symbol, protein name or a synonym. Otherwise the caller must abstain.
    """
    q = _norm_tokens(query)
    if not q:
        return False
    for field in fields:
        f = _norm_tokens(field)
        if not f:
            continue
        if q == f or q <= f:
            return True
    return False


class TargetResolverAgent(ReActAgent):
    name = "TargetResolverAgent"
    thought = "Resolve target gene/protein name to UniProt entry and AlphaFold structure."
    action = "resolve_target"

    def _execute(self, state: WorkflowState) -> WorkflowState:
        objective = state.parsed_objective
        target_name = objective.target_name
        if not target_name:
            state.errors.append("TargetResolverAgent: No target name provided.")
            return state

        from protacxtend.backend.schemas import TargetRecord

        record: TargetRecord | None = None

        # 1. Authoritative local curated entry first. This carries the reviewed
        #    primary accession (e.g. BRD4 -> O60885), organism, structures and
        #    tractability; the live API must not shadow it.
        record = self._from_curated(target_name, TargetRecord)
        if record is not None:
            record.source = "local_curated_seed"
            record.external_ids["uniprot_tier"] = "curated"

        # 2. Shared, reviewed-UniProt resolver (same client the agent tool uses).
        if record is None:
            record = self._from_uniprot_client(target_name, TargetRecord)

        # 3. Last-resort raw UniProt search (legacy path), reviewed-filtered.
        if record is None:
            record = self._from_raw_uniprot(target_name, TargetRecord)

        if record is None:
            state.errors.append(
                f"TargetResolverAgent: Could not resolve '{target_name}' to a reviewed UniProt entry."
            )
            return state

        state.target_record = record
        state.parsed_objective.target_uniprot_id = record.uniprot_id

        # 4. AlphaFold fallback when the curated entry did not supply one.
        if record.uniprot_id and not record.alphafold_id:
            self._attach_alphafold(record, state)

        return state

    # ── resolution strategies ────────────────────────────────────────
    def _from_curated(self, target_name: str, TargetRecord) -> "TargetRecord | None":
        query = target_name.strip().upper()
        for row in self.toolbox.load_curated_targets():
            names = {
                (row.get("target_name") or "").upper(),
                (row.get("gene_symbol") or "").upper(),
            }
            synonyms = {(s or "").strip().upper()
                        for s in (row.get("synonyms") or "").split("|")}
            if query not in names and query not in synonyms:
                continue
            structures = [s for s in (row.get("structures") or "").split("|") if s]
            return TargetRecord(
                target_name=row.get("target_name") or target_name,
                gene_symbol=(row.get("gene_symbol") or target_name).upper(),
                uniprot_id=row.get("uniprot_id") or None,
                organism=row.get("organism") or "human",
                synonyms=[s for s in (row.get("synonyms") or "").split("|") if s],
                structures=structures,
                alphafold_id=row.get("alphafold_id") or None,
                uniprot_confidence=float(row.get("uniprot_confidence") or 0.98),
                known_binder_count=int(float(row.get("known_binder_count") or 0)),
                tractability_score=float(row.get("tractability_score") or 0.0),
                external_ids={"curated_uniprot_source": "curated_targets.csv"},
            )
        return None

    def _from_uniprot_client(self, target_name: str, TargetRecord) -> "TargetRecord | None":
        try:
            from protacxtend.backend.uniprot_client import resolve_target_via_uniprot

            rec, result = resolve_target_via_uniprot(target_name, organism="human", reviewed=True)
            if rec is None:
                return None
            # Fail closed: a full-text hit that does not name the requested
            # entity (gene symbol / protein name / synonym) is NOT a resolution.
            if not query_matches_hit(target_name, [
                rec.gene_symbol, rec.target_name, *(rec.synonyms or [])
            ]):
                log.warning(
                    "UniProt client returned '%s' (%s) for query '%s' but it does not "
                    "match the requested entity; rejecting the hit.",
                    rec.gene_symbol or rec.target_name, rec.uniprot_id, target_name)
                return None
            rec.external_ids["uniprot_tier"] = "reviewed"
            rec.external_ids["uniprot_source_url"] = result.get("source_url", "")
            return rec
        except Exception as exc:  # noqa: BLE001 - fall through to raw search
            log.warning(f"UniProt client resolution failed for '{target_name}': {exc}")
            return None

    def _from_raw_uniprot(self, target_name: str, TargetRecord) -> "TargetRecord | None":
        # Reviewed + human filter, not a bare size=1 first hit.
        for query in (f"{target_name} AND reviewed:true AND organism_id:9606", target_name):
            record = self._search_uniprot(query)
            if not record:
                continue
            accession = record.get("primaryAccession", "")
            if not accession:
                continue
            # Extract the *real* identifiers from the hit — never overwrite the
            # gene symbol with the query (that previously masked mis-resolutions).
            genes = record.get("genes") or []
            gene_symbol = ""
            synonyms: list[str] = []
            for gene in genes:
                name = (gene.get("geneName") or {}).get("value")
                if name and not gene_symbol:
                    gene_symbol = name
                synonyms += [s.get("value", "") for s in (gene.get("synonyms") or [])]
            protein_name = (record.get("proteinDescription", {})
                            .get("recommendedName", {})
                            .get("fullName", {})
                            .get("value", "")) or record.get("uniProtkbId", "")
            if not query_matches_hit(target_name, [gene_symbol, protein_name, *synonyms]):
                log.warning(
                    "Raw UniProt hit '%s' (%s) does not match query '%s'; rejecting.",
                    gene_symbol or protein_name, accession, target_name)
                continue
            organism = (record.get("organism", {}) or {}).get("scientificName", "")
            return TargetRecord(
                target_name=protein_name or gene_symbol or target_name,
                gene_symbol=gene_symbol or target_name.upper(),
                uniprot_id=accession,
                organism=organism,
                synonyms=[s for s in synonyms if s],
                alphafold_id=f"AF-{accession}-F1",
                uniprot_confidence=0.85,
                external_ids={"uniprot_tier": "raw_search"},
            )
        return None

    def _attach_alphafold(self, record, state: WorkflowState) -> None:
        uniprot_id = record.uniprot_id
        try:
            req = urllib.request.Request(ALPHAFOLD_API.format(uniprot_id))
            with urllib.request.urlopen(req, timeout=10) as resp:
                af_data = json.loads(resp.read().decode())
            if af_data:
                record.alphafold_id = af_data[0].get("entryId", "") or record.alphafold_id
                record.external_ids["alphafold_url"] = af_data[0].get("cifUrl", "")
                record.external_ids["alphafold_pdb_url"] = af_data[0].get("pdbUrl", "")
        except Exception:
            state.warnings.append(f"TargetResolverAgent: AlphaFold fetch failed for {uniprot_id}")

    def _search_uniprot(self, query: str) -> dict | None:
        try:
            url = UNIPROT_API.format(urllib.parse.quote(query))
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
                results = data.get("results", [])
                return results[0] if results else None
        except Exception as e:
            log.warning(f"UniProt search failed for '{query}': {e}")
            return None

    def _observation(self, state: WorkflowState) -> str:
        rec = state.target_record
        if rec:
            return f"uniprot={rec.uniprot_id or 'none'}, gene={rec.gene_symbol}"
        return "target_not_resolved"

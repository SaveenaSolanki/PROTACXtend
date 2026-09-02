from synglue_agent.databases.database_router import route_database_request


def _has_all(output, names):
    rec = set(output["recommended_databases"])
    return all(name in rec for name in names)


def test_router_protac_task():
    out = route_database_request("find PROTACs for BRD4 CRBN")
    assert _has_all(out, ["PROTAC-DB 3.0", "PROTACpedia", "PROTAC-8K"])


def test_router_target_disease():
    out = route_database_request("check target disease relevance")
    assert _has_all(out, ["Open Targets", "DisGeNET", "OMIM", "cBioPortal"])


def test_router_expression():
    out = route_database_request("check normal tissue expression")
    assert _has_all(out, ["GTEx", "Human Protein Atlas", "ProteomicsDB"])


def test_router_ppi_e3():
    out = route_database_request("check E3 substrate biology")
    assert _has_all(out, ["UbiBrowser", "UbiNet", "BioGRID", "IntAct", "STRING"])


def test_router_patents():
    out = route_database_request("search patents")
    assert _has_all(out, ["Lens.org", "SureChEMBL"])


def test_router_literature():
    out = route_database_request("search literature")
    assert _has_all(out, ["PubMed", "Europe PMC", "Semantic Scholar", "OpenAlex"])


def test_router_purchasable():
    out = route_database_request("find purchasable analogs")
    assert _has_all(out, ["ZINC", "Enamine REAL", "MolPort", "eMolecules"])


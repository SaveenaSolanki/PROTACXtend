from protacxtend.modules.neosubstrate_risk import risk_score, flag_offtarget

def test_crbn_has_neosubstrate_risk():
    result = risk_score("CRBN")
    assert result["neosubstrate_hit"] is True
    assert len(result["neosubstrate_targets"]) >= 5

def test_vhl_no_risk():
    result = risk_score("VHL")
    assert result["neosubstrate_hit"] is False

def test_flag_offtarget_crbn():
    result = flag_offtarget("CRBN")
    assert result["action"] == "flag"

def test_flag_offtarget_vhl():
    result = flag_offtarget("VHL")
    assert result["action"] == "none"

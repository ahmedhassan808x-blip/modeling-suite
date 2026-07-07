"""
Live sanity check against a stable mega-cap (needs FMP_API_KEY; run with
`pytest -m live`). Confirms real-world FMP payloads parse, the workbook
recalculates clean, and outputs land in a plausible range.
"""

import os

import pytest

from shared.recalc import recalculate
from three_statement.assumptions import Assumptions
from three_statement.data_layer import fetch_financials
from three_statement.model_builder import IS, build_model

pytestmark = pytest.mark.live

needs_key = pytest.mark.skipif(
    not os.environ.get("FMP_API_KEY"), reason="FMP_API_KEY not set")


@needs_key
def test_aapl_end_to_end(tmp_path):
    data = fetch_financials("AAPL", n_hist=3)
    a = Assumptions.derive(data)
    out = tmp_path / "AAPL_3stmt.xlsx"
    build_model(data, a, out)
    res = recalculate(out, probe_cells=["Checks!B9", f"IS!F{IS['rev']}",
                                        f"IS!J{IS['ni']}"])
    assert res.ok, res.summary()
    assert res.values["Checks!B9"] == "PASS"
    # Y1 forecast revenue within 0.5x–2x of last reported year — plausibility,
    # not precision.
    last_rev = data["is"]["revenue"][-1]
    assert 0.5 * last_rev < res.values[f"IS!F{IS['rev']}"] < 2.0 * last_rev
    # Terminal-year net margin sane for a profitable mega-cap
    ni = res.values[f"IS!J{IS['ni']}"]
    assert 0 < ni < last_rev * 0.6


@needs_key
def test_aapl_dcf_plausible(tmp_path):
    """Spec sanity gate: DCF on a stable large-cap lands in a plausible range."""
    from dcf.data_layer import get_peer_multiples
    from dcf.model_builder import D, build_dcf_model
    from three_statement.model_builder import BS

    data = fetch_financials("AAPL", n_hist=3)
    a = Assumptions.derive(data)
    peers = get_peer_multiples(["MSFT", "GOOGL", "META"])
    out = tmp_path / "AAPL_dcf.xlsx"
    build_dcf_model(data, a, out, peers=peers)
    res = recalculate(out, probe_cells=["Checks!B9", f"DCF!B{D['ps']}",
                                        f"DCF!B{D['wacc']}",
                                        f"DCF!B{D['ps_exit']}"])
    assert res.ok, res.summary()
    assert res.values["Checks!B9"] == "PASS"
    wacc = res.values[f"DCF!B{D['wacc']}"]
    assert 0.06 < wacc < 0.14, f"WACC {wacc:.2%} implausible"
    # Implied per share within a WIDE plausibility band of the market price —
    # a 5-yr DCF on a mega-cap should not be off by an order of magnitude.
    for key in ("ps", "ps_exit"):
        ps = res.values[f"DCF!B{D[key]}"]
        assert 0.2 * data["price"] < ps < 3.0 * data["price"], \
            f"{key}: ${ps:,.0f}/sh vs market ${data['price']:,.0f}"


@needs_key
def test_aapl_lbo_sane(tmp_path):
    """Spec sanity gate: textbook leverage on a real large-cap; the honest
    result at a premium market entry multiple is a LOW IRR — assert sane
    bounds and clean checks, not fantasy returns."""
    from lbo.assumptions import LBOAssumptions
    from lbo.model_builder import CHECKS_PASS_CELL, R, build_lbo_model

    data = fetch_financials("AAPL", n_hist=3)
    lb = LBOAssumptions.derive(data)
    out = tmp_path / "AAPL_lbo.xlsx"
    build_lbo_model(data, Assumptions.derive(data), lb, out)
    res = recalculate(out, probe_cells=["Checks!B9", CHECKS_PASS_CELL,
                                        f"Returns!B{R['irr']}",
                                        f"Returns!B{R['moic']}"])
    assert res.ok, res.summary()
    assert res.values["Checks!B9"] == "PASS"
    assert res.values[CHECKS_PASS_CELL] == "PASS"
    assert lb.entry_mult > 15, "AAPL seed should reflect its premium multiple"
    irr = res.values[f"Returns!B{R['irr']}"]
    assert -0.10 < irr < 0.25, f"IRR {irr:.1%} outside plausible band"


@needs_key
def test_macro_live():
    from news.data_layer import get_commodity_quote, get_macro
    m = get_macro()
    assert 1.0 < m["treasury"]["10y"] < 8.0
    assert "inflationRate" in m["indicators"]
    gold = get_commodity_quote("GCUSD")
    assert gold["price"] and gold["price"] > 500  # gold, sanity


@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"),
                    reason="ANTHROPIC_API_KEY not set")
def test_llm_smoke():
    from shared.llm import ask
    out = ask("Reply with exactly the word OK and nothing else.",
              max_tokens=10)
    assert "OK" in out


@needs_key
def test_scan_live_small():
    from scanner.scan import scan
    res = scan(["AAPL", "MSFT"])
    assert len(res["rows"]) == 2 and not res["failed"]
    for r in res["rows"]:
        assert -0.95 < r["upside"] < 1.0
        assert r["verdict"] in ("worth a look", "caution", "likely artifact")

"""
S&P 500 vs. gold: return math, real-gold deflation, sourced-or-nothing
enforcement in the research layer, gap propagation into the brief, and
the full export set (with the Excel recalc gate) — all offline via
injected fakes.
"""

import json

import pytest

from shared.recalc import recalculate
from sp500_vs_gold import brief as briefmod
from sp500_vs_gold.data_layer import compute_returns, price_on_or_before
from sp500_vs_gold.report import build_outputs, render_markdown
from sp500_vs_gold.research import research_market_context

ROWS = [{"date": d, "price": p, "volume": 1} for d, p in [
    ("2021-07-05", 100.0), ("2022-07-15", 110.0), ("2024-01-15", 130.0),
    ("2025-01-15", 140.0), ("2025-07-01", 150.0), ("2025-12-30", 160.0),
    ("2026-07-01", 165.0)]]


def _num(value, src="TestSource", as_of="2026-07-01"):
    return {"value": value, "as_of": as_of if value is not None else None,
            "source": src if value is not None else None, "url": ""}


FAKE_RESEARCH_JSON = {
    "spx_trailing_pe": _num(28.4), "spx_forward_pe": _num(23.1),
    "cape": _num(None), "spx_dividend_yield_pct": _num(1.2),
    "dxy": _num(101.3), "tips_10y_real_yield_pct": _num(2.1),
    "rate_expectations": {"summary": "Two cuts priced by year-end per "
                          "FedWatch.", "sources": ["CME FedWatch 2026-07-01"]},
    "gold_flows": {"summary": "Central banks still net buyers.",
                   "sources": ["WGC"]},
    "equity_flows": {"summary": "Steady equity inflows on AI capex.",
                     "sources": ["EPFR via FT"]},
    "notable_events": {"summary": "No new shocks this month.",
                       "sources": ["Reuters"]},
    "strategist_views": [{"source": "House A", "date": "2026-06-20",
                          "asset": "Gold", "view": "Stay long."}],
}

FAKE_VIEW = {
    "case_spx": ["Earnings growth is broad [facts]."] * 4,
    "case_gold": ["Real yields falling [facts]."] * 4,
    "reasoned_view": "Given the retrieved data, the picture is mixed but "
                     "gold's drivers look firmer.",
    "lean": "Gold",
    "what_would_change": ["10Y TIPS real yield back above 2.5%",
                          "CPI reaccelerating past 3.5%",
                          "A dovish surprise reversing"],
}


def test_price_anchors_and_returns():
    r = compute_returns(ROWS)
    assert r["current"]["price"] == 165.0
    assert r["ytd"] == pytest.approx(165 / 160 - 1)
    assert r["1y"] == pytest.approx(165 / 150 - 1)
    assert r["5y"] == pytest.approx(165 / 100 - 1)
    with pytest.raises(Exception, match="on/before"):
        price_on_or_before(ROWS, "2020-01-01")


def test_research_sourced_or_nothing():
    payload = json.loads(json.dumps(FAKE_RESEARCH_JSON))
    payload["dxy"] = {"value": 101.3, "as_of": "2026-07-01",
                      "source": None, "url": ""}   # number without a source
    res = research_market_context(llm=lambda p, s, m: json.dumps(payload))
    assert res["dxy"]["value"] is None           # discarded, not trusted
    assert "cape" in res["gaps"] and "dxy" in res["gaps"]


@pytest.fixture
def fake_brief(monkeypatch):
    fake_data = dict(
        as_of="2026-07-08",
        spx=dict(price=7436.0, change_pct=-0.9, year_high=7620.0,
                 year_low=6201.0, avg200=7000.0, as_of="2026-07-08",
                 source="FMP quote (^GSPC)"),
        gold=dict(price=3900.0, change_pct=0.2, year_high=4000.0,
                  year_low=2600.0, avg200=3500.0, as_of="2026-07-08",
                  source="FMP quote (GCUSD)"),
        eurusd=dict(price=1.1393, year_high=1.2024, year_low=1.1325,
                    avg200=1.16, change_pct=0.0, as_of="2026-07-08",
                    source="FMP quote (EURUSD)"),
        returns=dict(spx=compute_returns(ROWS), gold=compute_returns(ROWS),
                     source="FMP daily closes (test)"),
        macro=dict(as_of="2026-07-06",
                   treasury={"3m": 3.87, "2y": 4.13, "10y": 4.48, "30y": 4.99},
                   indicators={"inflationRate": {"value": 2.24,
                                                 "date": "2026-07-06"},
                               "federalFunds": {"value": 3.63,
                                                "date": "2026-06-01"}}),
        gold_real=dict(current=3900.0, low_5y=1800.0, high_5y=4000.0,
                       pctile=0.95, cpi_as_of="2026-05-01", note="test"),
    )
    monkeypatch.setattr(briefmod, "fetch_market_data",
                        lambda **kw: fake_data)
    monkeypatch.setattr(
        briefmod, "research_market_context",
        lambda **kw: research_market_context(
            llm=lambda p, s, m: json.dumps(FAKE_RESEARCH_JSON)))
    return briefmod.build_brief(synth_llm=lambda p, s, m:
                                json.dumps(FAKE_VIEW))


def test_brief_assembly_and_gaps(fake_brief):
    b = fake_brief
    # derived metrics computed by us, not the LLM
    assert b["der"]["real_yield_approx"] == pytest.approx(4.48 - 2.24)
    assert b["der"]["erp_proxy"] == pytest.approx(100 / 28.4 - 4.48)
    # the CAPE gap must surface as an explicit row, not vanish
    cape_row = next(r for r in b["rows"] if r["metric"] == "Shiller CAPE")
    assert "not obtained" in cape_row["spx"]
    assert len(b["macro"]) == 4
    assert b["view"]["lean"] == "Gold"


def test_exports_complete_and_recalc_clean(fake_brief, tmp_path):
    outputs = build_outputs(fake_brief, tmp_path)
    for kind in ("md", "xlsx", "docx", "pdf"):
        assert outputs[kind].exists(), f"{kind} missing"
    md = outputs["md"].read_text()
    assert "not financial advice" in md
    assert "What would change this view" in md
    assert "Data gaps this run" in md and "cape" in md
    # Excel derived cells are live formulas and recalc clean
    res = recalculate(outputs["xlsx"],
                      probe_cells=["Data!B19", "Data!B25", "Data!B27"])
    assert res.ok, res.summary()
    assert res.values["Data!B19"] == pytest.approx(165 / 160 - 1)  # YTD
    assert res.values["Data!B25"] == pytest.approx(4.48 - 2.24)    # real yld
    assert res.values["Data!B27"] == pytest.approx(100 / 28.4 - 4.48)  # ERP


def test_synth_prompt_grounded(fake_brief, monkeypatch):
    captured = {}

    def spy_llm(p, s, m):
        captured["prompt"], captured["system"] = p, s
        return json.dumps(FAKE_VIEW)
    briefmod.synthesize_view(
        briefmod.facts_text(fake_brief["data"], fake_brief["research"],
                            fake_brief["der"], fake_brief["rows"]),
        "2026-07-08", llm=spy_llm)
    assert "7,436" in captured["prompt"]          # live level in the pack
    assert "DATA GAPS THIS RUN" in captured["prompt"]
    assert "not advice" in captured["system"]

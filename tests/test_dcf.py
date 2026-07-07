"""
DCF workbook: recalc-clean, hand-checkable UFCF, EV bridge arithmetic,
scenario linkage (the DCF must reprice when the toggle flips), and comps.
"""

import pytest
from openpyxl import load_workbook

from dcf.model_builder import D, build_dcf_model, derive_wacc_seeds
from shared.recalc import recalculate
from three_statement.assumptions import Assumptions

FAKE_PEERS = [
    {"ticker": "PEERA", "name": "Peer A", "mkt_cap": 2000.0, "ev": 2200.0,
     "ev_ebitda": 9.0, "ev_revenue": 2.0, "pe": 16.0},
    {"ticker": "PEERB", "name": "Peer B", "mkt_cap": 3000.0, "ev": 3100.0,
     "ev_ebitda": 11.0, "ev_revenue": 2.6, "pe": 20.0},
    {"ticker": "PEERC", "name": "Peer C", "mkt_cap": 1500.0, "ev": 1700.0,
     "ev_ebitda": 10.0, "ev_revenue": 2.2, "pe": 18.0},
]

PROBES = [f"DCF!B{D[k]}" for k in
          ("wacc", "sum_pv", "ev", "net_debt", "eq", "ps", "upside",
           "ps_exit", "exit_mult")] + [f"DCF!F{D['ufcf']}", "Checks!B9"]


def _build(simpleco, tmp_path, peers=None, selector=None):
    a = Assumptions.derive(simpleco)
    out = tmp_path / "dcf.xlsx"
    build_dcf_model(simpleco, a, out, peers=peers)
    if selector:
        wb = load_workbook(out)
        wb["Assumptions"]["B3"] = selector
        wb.save(out)
    probes = PROBES + (["Summary!B5", "Summary!C5"] if peers else [])
    return recalculate(out, probe_cells=probes)


def test_dcf_recalculates_clean(simpleco, tmp_path):
    res = _build(simpleco, tmp_path)
    assert res.ok, res.summary()
    assert res.values["Checks!B9"] == "PASS"


def test_dcf_arithmetic(simpleco, tmp_path):
    res = _build(simpleco, tmp_path)
    v = res.values
    # WACC: ke = 4.25% + 1.1*5% = 9.75%; net debt 200-340 < 0 -> dw = 0
    assert v[f"DCF!B{D['wacc']}"] == pytest.approx(0.0975, abs=1e-4)
    # Net debt from the modeled BS: 200 debt + 0 revolver - 340 cash = -140
    assert v[f"DCF!B{D['net_debt']}"] == pytest.approx(-140, abs=1e-6)
    # EV bridge: equity value = EV - net debt, per share on 15mm shares
    assert v[f"DCF!B{D['eq']}"] == pytest.approx(
        v[f"DCF!B{D['ev']}"] + 140, abs=1e-6)
    assert v[f"DCF!B{D['ps']}"] == pytest.approx(
        v[f"DCF!B{D['eq']}"] / 15.0, rel=1e-6)
    # Y1 UFCF band: NOPAT ~210 + D&A ~66 - capex ~91 - small NWC build
    assert 150 < v[f"DCF!F{D['ufcf']}"] < 220
    # A profitable grower discounted at ~9.75% should be worth something
    assert v[f"DCF!B{D['ps']}"] > 0
    assert v[f"DCF!B{D['ps_exit']}"] > 0


def test_dcf_repriced_by_scenario_toggle(simpleco, tmp_path):
    ps = {s: _build(simpleco, tmp_path, selector=s).values[f"DCF!B{D['ps']}"]
          for s in (1, 2, 3)}
    assert ps[1] < ps[2] < ps[3], f"DCF didn't reprice with scenario: {ps}"


def test_comps_and_football_field(simpleco, tmp_path):
    res = _build(simpleco, tmp_path, peers=FAKE_PEERS)
    assert res.ok, res.summary()
    assert res.values["Checks!B9"] == "PASS"
    # exit multiple seeded from peer median EV/EBITDA (10.0x)
    assert res.values[f"DCF!B{D['exit_mult']}"] == pytest.approx(10.0)
    # football field row 1 = 52-week range hardcodes
    assert res.values["Summary!B5"] == pytest.approx(40.0)
    assert res.values["Summary!C5"] == pytest.approx(60.0)


def test_wacc_seed_derivation(simpleco):
    a = Assumptions.derive(simpleco)
    w = derive_wacc_seeds(simpleco, a, peers=FAKE_PEERS)
    assert w["dw"] == 0.0            # net cash company -> no debt in WACC
    assert w["exit_mult"] == 10.0    # peer median
    assert 0 < w["tg"] < 0.04


def test_dcf_requires_market_data(simpleco, tmp_path):
    broken = dict(simpleco, price=0)
    a = Assumptions.derive(simpleco)
    with pytest.raises(ValueError, match="no market data"):
        build_dcf_model(broken, a, tmp_path / "x.xlsx")

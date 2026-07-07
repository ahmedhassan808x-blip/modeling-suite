"""
LBO model: recalc-clean, textbook sanity (spec gate: textbook-typical
leverage/exit assumptions must land IRR in a sane range), sweep mechanics,
IRR cross-check, and scenario linkage.
"""

import pytest
from openpyxl import load_workbook

from lbo.assumptions import LBOAssumptions
from lbo.model_builder import DEAL, L, R, build_lbo_model
from shared.recalc import recalculate
from three_statement.assumptions import Assumptions

FC = list("FGHIJ")

PROBES = (["Checks!B9", "ChecksLBO!B11", "ChecksLBO!B4", "ChecksLBO!B5",
           f"Returns!B{R['irr']}", f"Returns!B{R['moic']}",
           f"Returns!B{R['entry_eq']}", f"Returns!B{R['exit_eq']}",
           f"Returns!B{R['br_fees']}", f"Deal!B{DEAL['s_equity']}"]
          + [f"LBO!{c}{L['debt_end']}" for c in FC]
          + [f"LBO!{c}{L['fcf']}" for c in FC]
          + [f"LBO!{c}{L['cash_end']}" for c in FC]
          + [f"LBO!{c}{L['rv_end']}" for c in FC])


def _textbook(simpleco):
    """8.0x entry, 3.5x + 1.5x debt (~62% leverage), flat exit, 5-yr hold."""
    lb = LBOAssumptions.derive(simpleco)
    lb.entry_mult = lb.exit_mult = 8.0
    return lb


def _build(simpleco, tmp_path, lb=None, selector=None):
    a = Assumptions.derive(simpleco)
    out = tmp_path / "lbo.xlsx"
    build_lbo_model(simpleco, a, lb or _textbook(simpleco), out)
    if selector:
        wb = load_workbook(out)
        wb["Assumptions"]["B3"] = selector
        wb.save(out)
    return recalculate(out, probe_cells=PROBES)


def test_lbo_recalculates_clean(simpleco, tmp_path):
    res = _build(simpleco, tmp_path)
    assert res.ok, res.summary()
    assert res.values["Checks!B9"] == "PASS"
    assert res.values["ChecksLBO!B11"] == "PASS"


def test_textbook_irr_in_sane_range(simpleco, tmp_path):
    """A ~8% EBITDA grower bought at 8x with 5x of debt and a flat exit
    should produce a mid-teens-to-high-twenties IRR — the textbook answer."""
    v = _build(simpleco, tmp_path).values
    irr, moic = v[f"Returns!B{R['irr']}"], v[f"Returns!B{R['moic']}"]
    assert 0.10 < irr < 0.35, f"IRR {irr:.1%} outside textbook band"
    assert 1.6 < moic < 4.0, f"MOIC {moic:.2f}x outside textbook band"
    # IRR from flows must equal closed-form MOIC^(1/5)-1 (no interim flows)
    assert abs(v["ChecksLBO!B5"]) < 1e-4
    assert abs(v["ChecksLBO!B4"]) < 1e-6      # sources = uses


def test_sweep_delevers_monotonically(simpleco, tmp_path):
    v = _build(simpleco, tmp_path).values
    debt = [v[f"LBO!{c}{L['debt_end']}"] for c in FC]
    assert all(d1 >= d2 - 1e-6 for d1, d2 in zip(debt, debt[1:])), \
        f"debt should never increase: {debt}"
    assert debt[-1] < debt[0], "no deleveraging happened"
    fcf = [v[f"LBO!{c}{L['fcf']}"] for c in FC]
    assert all(f > 0 for f in fcf), f"textbook case should self-fund: {fcf}"
    cash = [v[f"LBO!{c}{L['cash_end']}"] for c in FC]
    assert all(c >= -1e-6 for c in cash)


def test_bridge_residual_equals_fees(simpleco, tmp_path):
    """The value-creation bridge residual must be exactly -fees (identity)."""
    v = _build(simpleco, tmp_path).values
    ltm_ebitda = 302.0                       # 242 EBIT + 60 D&A, hand-checked
    fees = 8.0 * ltm_ebitda * 0.02
    assert v[f"Returns!B{R['br_fees']}"] == pytest.approx(-fees, abs=0.01)
    # Sponsor equity = EV + fees - debt = (8-5)x*EBITDA + fees
    assert v[f"Deal!B{DEAL['s_equity']}"] == pytest.approx(
        3.0 * ltm_ebitda + fees, abs=0.01)


def test_scenario_toggle_reprices_irr(simpleco, tmp_path):
    irr, rv_used = {}, {}
    for s in (1, 2, 3):
        v = _build(simpleco, tmp_path, selector=s).values
        assert v["ChecksLBO!B11"] == "PASS", f"scenario {s} failed checks"
        irr[s] = v[f"Returns!B{R['irr']}"]
        rv_used[s] = max(v[f"LBO!{c}{L['rv_end']}"] for c in FC)
    assert irr[1] < irr[2] < irr[3], f"IRR ordering wrong: {irr}"
    # Bear FCF can't cover mandatory amort — the revolver must be doing the
    # funding (the honest feasibility signal), and the model still balances.
    assert rv_used[1] > 0, "bear case should draw the revolver"


def test_higher_leverage_higher_irr_when_returns_exceed_cost(simpleco,
                                                             tmp_path):
    """Classic LBO mechanics: with unlevered returns above the cost of debt,
    more leverage means higher IRR (and it must still pass all checks)."""
    lo, hi = _textbook(simpleco), _textbook(simpleco)
    lo.senior_x, lo.sub_x = 2.0, 1.0
    hi.senior_x, hi.sub_x = 4.0, 1.5
    v_lo = _build(simpleco, tmp_path, lb=lo).values
    v_hi = _build(simpleco, tmp_path, lb=hi).values
    assert v_lo["ChecksLBO!B11"] == v_hi["ChecksLBO!B11"] == "PASS"
    assert v_hi[f"Returns!B{R['irr']}"] > v_lo[f"Returns!B{R['irr']}"]


def test_lbo_reports(simpleco_module, tmp_path):
    """Full export set from the LBO workbook, incl. the leverage rerun."""
    from lbo.report import build_reports, extract, leverage_rerun
    a = Assumptions.derive(simpleco_module)
    lb = LBOAssumptions.derive(simpleco_module)
    lb.entry_mult = lb.exit_mult = 8.0
    out = tmp_path / "SMPL_lbo.xlsx"
    build_lbo_model(simpleco_module, a, lb, out)
    outputs = build_reports(out)
    for kind in ("pptx", "docx", "pdf"):
        assert outputs[kind].exists() and outputs[kind].stat().st_size > 10_000
    d = extract(out)
    assert d["ticker"] == "SMPL"
    assert 0.10 < d["ret"]["irr"] < 0.35
    lev = leverage_rerun(out, leverage_points=((2.0, 1.0), (4.0, 1.5)),
                         exit_deltas=(0.0,))
    irr_lo, irr_hi = lev[0][1][0], lev[1][1][0]
    assert irr_hi > irr_lo   # more leverage, more IRR (returns > cost of debt)

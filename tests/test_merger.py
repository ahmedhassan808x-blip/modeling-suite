"""
Merger model: recalc-clean, the classic P/E accretion rule (all-stock,
no synergies, no premium: buying a LOWER-P/E target is accretive, a
HIGHER-P/E target is dilutive), breakeven-synergy self-consistency, and
sensitivity direction.
"""

import pytest

from merger.assumptions import MergerAssumptions
from merger.model_builder import CHECKS_PASS_CELL, PF, build_merger_model
from shared.recalc import recalculate
from tests.conftest import company_data

FC = list("FGHIJ")
PROBES = ([CHECKS_PASS_CELL, f"ProForma!F{PF['breakeven']}"]
          + [f"ProForma!{c}{PF['acc_pct']}" for c in FC]
          + [f"ProForma!{sc}{PF['sens_first'] + i}"
             for sc in "CDEFG" for i in (0, 4)])


def _companies():
    # Same earnings engine, different market pricing:
    # BIGCO trades at ~4x earnings (price 50, NI ~187mm, 15mm shares);
    # RICHCO at ~13x (price 20, NI ~18.7mm, 12.5mm shares).
    big = company_data("BIGCO", "Big Corp", 50.0, 750.0, scale=1.0)
    rich = company_data("RICHCO", "Rich Valuation Inc", 20.0, 250.0,
                        scale=0.1)
    return big, rich


def _build(acq, tgt, m, tmp_path, name="m.xlsx"):
    out = tmp_path / name
    build_merger_model(acq, tgt, m, out)
    return recalculate(out, probe_cells=PROBES)


def _all_stock_no_frictions():
    return MergerAssumptions(premium=0.0, mix_stock=1.0, mix_cash=0.0,
                             mix_debt=0.0, fees_pct=0.0, intang_pct=0.0,
                             syn_runrate=0.0)


def test_merger_recalculates_clean(tmp_path):
    big, rich = _companies()
    res = _build(big, rich, MergerAssumptions(), tmp_path)
    assert res.ok, res.summary()
    assert res.values[CHECKS_PASS_CELL] == "PASS"


def test_pe_rule_all_stock(tmp_path):
    """No premium, no synergies, no fees, all stock: pure P/E arithmetic."""
    big, rich = _companies()
    # low-P/E acquirer buys high-P/E target -> dilutive
    res = _build(big, rich, _all_stock_no_frictions(), tmp_path, "dil.xlsx")
    assert res.values[CHECKS_PASS_CELL] == "PASS"
    assert res.values[f"ProForma!F{PF['acc_pct']}"] < -0.001, \
        "buying a higher-P/E target all-stock must dilute"
    # high-P/E acquirer buys low-P/E target -> accretive. A 20% premium is
    # needed to clear the target's book value (offer below book -> negative
    # goodwill, which the checks rightly reject as a bargain-purchase input);
    # paid P/E remains far below the acquirer's own, so the rule holds.
    m = _all_stock_no_frictions()
    m.premium = 0.20
    res2 = _build(rich, big, m, tmp_path, "acc.xlsx")
    assert res2.values[CHECKS_PASS_CELL] == "PASS"
    assert res2.values[f"ProForma!F{PF['acc_pct']}"] > 0.001, \
        "buying a lower-P/E target all-stock must accrete"


def test_breakeven_synergies_close_the_gap(tmp_path):
    """Plugging the model's own breakeven synergies must produce ~0% Y1
    accretion — the breakeven formula re-derived against the model."""
    from openpyxl import load_workbook
    from merger.model_builder import DEAL

    big, rich = _companies()
    out = tmp_path / "be.xlsx"
    build_merger_model(big, rich, MergerAssumptions(), out)
    res = recalculate(out, probe_cells=[f"ProForma!F{PF['breakeven']}"])
    breakeven = res.values[f"ProForma!F{PF['breakeven']}"]
    wb = load_workbook(out)
    wb["Deal"][f"B{DEAL['syn']}"] = breakeven
    wb.save(out)
    res2 = recalculate(out, probe_cells=[f"ProForma!F{PF['acc_pct']}",
                                         CHECKS_PASS_CELL])
    assert res2.values[CHECKS_PASS_CELL] == "PASS"
    assert abs(res2.values[f"ProForma!F{PF['acc_pct']}"]) < 1e-4


def test_sensitivity_directions(tmp_path):
    """More synergies -> more accretive (down rows); more premium -> less
    accretive (across cols)."""
    big, rich = _companies()
    res = _build(big, rich, MergerAssumptions(), tmp_path)
    v = res.values
    top, bot = PF["sens_first"], PF["sens_first"] + 4
    assert v[f"ProForma!C{bot}"] > v[f"ProForma!C{top}"]   # syn rows ascend
    assert v[f"ProForma!G{top}"] < v[f"ProForma!C{top}"]   # premium hurts


def test_merger_reports(tmp_path):
    from merger.report import build_reports, extract
    big, rich = _companies()
    out = tmp_path / "SMPL_merger.xlsx"
    build_merger_model(big, rich, MergerAssumptions(), out)
    outputs = build_reports(out)
    for kind in ("pptx", "docx", "pdf"):
        assert outputs[kind].exists() and outputs[kind].stat().st_size > 10_000
    d = extract(out)
    assert d["acq"] == "BIGCO" and d["tgt"] == "RICHCO"
    assert len(d["pf"]["acc_pct"]) == 5

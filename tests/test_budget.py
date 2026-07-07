"""
Budget template: recalc-clean when empty, and correct variance math /
favorability / REVIEW flags once filled like a real close.
"""

import pytest
from openpyxl import load_workbook

from budget.model_builder import (
    CHECKS_PASS_CELL, ROWS, TOT, build_budget_template,
)
from shared.recalc import recalculate


def test_empty_template_recalculates_clean(tmp_path):
    out = tmp_path / "b.xlsx"
    build_budget_template("TestCo", 2026, out)
    res = recalculate(out, probe_cells=[CHECKS_PASS_CELL])
    assert res.ok, res.summary()   # no #DIV/0! from empty grids
    assert res.values[CHECKS_PASS_CELL] == "PASS"


def test_filled_template_variance_math(tmp_path):
    out = tmp_path / "b.xlsx"
    build_budget_template("TestCo", 2026, out)
    wb = load_workbook(out)
    bud, act = wb["Budget"], wb["Actuals"]
    months = [chr(ord("C") + i) for i in range(12)]
    # Budget: product 100/mo, services 20/mo, COGS -40, S&M -25, R&D -15,
    # G&A -10, other 0  -> EBITDA 30/mo, FY 360
    # Actuals: product 90 (miss), services 22, COGS -38, S&M -32 (overspend),
    # R&D -15, G&A -9, other 0 -> EBITDA 18/mo, FY 216
    fill = {"rev_prod": (100, 90), "rev_svc": (20, 22), "cogs": (-40, -38),
            "sm": (-25, -32), "rd": (-15, -15), "ga": (-10, -9),
            "other": (0, 0)}
    for key, (b, a) in fill.items():
        for c in months:
            bud[f"{c}{ROWS[key]}"] = b
            act[f"{c}{ROWS[key]}"] = a
    wb.save(out)

    probes = [CHECKS_PASS_CELL] + [
        f"Variance!{TOT}{ROWS[k]}" for k in
        ("rev_prod", "rev", "cogs", "sm", "ebitda")] + [
        f"Variance!P{ROWS[k]}" for k in ("rev_prod", "sm")] + [
        f"Variance!Q{ROWS[k]}" for k in
        ("rev_prod", "rev_svc", "cogs", "sm", "rd")]
    res = recalculate(out, probe_cells=probes)
    assert res.ok, res.summary()
    v = res.values
    assert v[CHECKS_PASS_CELL] == "PASS"
    # variance math, hand-checked (x12 months)
    assert v[f"Variance!{TOT}{ROWS['rev_prod']}"] == pytest.approx(-120)
    assert v[f"Variance!{TOT}{ROWS['rev']}"] == pytest.approx(-96)
    assert v[f"Variance!{TOT}{ROWS['cogs']}"] == pytest.approx(24)   # fav
    assert v[f"Variance!{TOT}{ROWS['sm']}"] == pytest.approx(-84)    # unfav
    assert v[f"Variance!{TOT}{ROWS['ebitda']}"] == pytest.approx(-144)
    # % of FY budget: -120/1200 = -10%; -84/300 = -28%
    assert v[f"Variance!P{ROWS['rev_prod']}"] == pytest.approx(-0.10)
    assert v[f"Variance!P{ROWS['sm']}"] == pytest.approx(-0.28)
    # flags: breaches BOTH 5% and $50 thresholds -> REVIEW; else quiet
    assert v[f"Variance!Q{ROWS['rev_prod']}"] == "UNFAV — REVIEW"
    assert v[f"Variance!Q{ROWS['sm']}"] == "UNFAV — REVIEW"
    assert v[f"Variance!Q{ROWS['rev_svc']}"] == "fav"     # +24, under $50
    assert v[f"Variance!Q{ROWS['cogs']}"] == "fav"        # +24, under $50
    assert v[f"Variance!Q{ROWS['rd']}"] == "fav"          # exactly on budget

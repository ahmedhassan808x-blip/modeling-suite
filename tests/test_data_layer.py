"""Data layer: parsing, plug construction, and loud failure on bad data."""

import pytest

from shared.fmp_client import FMPError
from three_statement.data_layer import parse_financials


def test_parse_basics(simpleco):
    d = simpleco
    assert d["years"] == [2023, 2024, 2025]
    assert d["is"]["revenue"] == [1000, 1100, 1210]
    assert d["prior_revenue"] == 900
    assert d["is"]["ni"][-1] == pytest.approx(237 * 0.79, rel=1e-6)


def test_income_statement_ties(simpleco):
    """EBIT - int_exp + int_inc + other must reproduce reported pre-tax."""
    isl = simpleco["is"]
    for i in range(3):
        rebuilt = isl["ebit"][i] - isl["int_exp"][i] + isl["int_inc"][i] \
            + isl["other"][i]
        assert rebuilt == pytest.approx(isl["pretax"][i], abs=1e-6)


def test_balance_sheet_plugs_tie(simpleco):
    """Modeled lines + plugs must reproduce reported totals exactly."""
    b = simpleco["bs"]
    for i in range(3):
        assets = (b["cash"][i] + b["ar"][i] + b["inv"][i] + b["other_ca"][i]
                  + b["ppe"][i] + b["gw_intan"][i] + b["other_nca"][i])
        liabs = (b["ap"][i] + b["other_cl"][i] + b["debt"][i] + b["other_ncl"][i])
        equity = (b["cs_apic"][i] + b["re"][i] + b["other_eq"][i]
                  + b["minority"][i])
        assert assets == pytest.approx(b["total_assets"][i], abs=1e-6)
        assert liabs == pytest.approx(b["total_liab"][i], abs=1e-6)
        assert assets == pytest.approx(liabs + equity, abs=1e-6)


def test_missing_required_field_fails_loudly(simpleco_raw):
    prof, inc, bs, cf = simpleco_raw
    broken = [dict(x) for x in inc]
    del broken[-1]["revenue"]
    with pytest.raises(FMPError, match="Required field missing"):
        parse_financials("SMPL", prof, broken, bs, cf, n_hist=3)


def test_misaligned_years_fail_loudly(simpleco_raw):
    prof, inc, bs, cf = simpleco_raw
    shifted = [dict(x) for x in bs]
    shifted[0]["date"] = "2019-12-31"
    with pytest.raises(FMPError, match="misaligned"):
        parse_financials("SMPL", prof, inc, shifted, cf, n_hist=3)

"""
Scanner: the load-bearing test is mirror-vs-workbook agreement — the
Python batch engine must reproduce the recalculated Excel DCF. Plus
artifact-flag logic and scan orchestration (gated/failed reporting).
"""

import pytest

from dcf.model_builder import D, build_dcf_model
from scanner import scan as scan_mod
from scanner.engine import artifact_flags, quick_dcf, verdict
from scanner.universe import load_universe
from shared.fmp_client import FMPError
from shared.recalc import recalculate
from three_statement.assumptions import Assumptions


def test_mirror_matches_recalculated_workbook(simpleco, tmp_path):
    """The whole scanner's honesty rests on this: mirror == Excel."""
    out = tmp_path / "smpl_dcf.xlsx"
    build_dcf_model(simpleco, Assumptions.derive(simpleco), out)
    res = recalculate(out, probe_cells=[f"DCF!B{D['ps']}",
                                        f"DCF!B{D['ps_exit']}",
                                        f"DCF!B{D['wacc']}"])
    m = quick_dcf(simpleco)
    assert m["wacc"] == pytest.approx(res.values[f"DCF!B{D['wacc']}"],
                                      abs=1e-9)
    assert m["ps"] == pytest.approx(res.values[f"DCF!B{D['ps']}"], rel=1e-6)
    assert m["ps_exit"] == pytest.approx(res.values[f"DCF!B{D['ps_exit']}"],
                                         rel=1e-6)


def _fake_result(**over):
    base = dict(upside=0.10, tv_share=0.60, ufcf=[10, 12, 14, 16, 18],
                trailing_growth=0.08, data_gaps=False)
    base.update(over)
    return base


def test_artifact_flags():
    assert artifact_flags(_fake_result()) == []
    assert "hypergrowth" in artifact_flags(
        _fake_result(trailing_growth=0.30))[0]
    assert "terminal-value dominant" in artifact_flags(
        _fake_result(tv_share=0.9))[0]
    assert "negative forecast FCF" in artifact_flags(
        _fake_result(ufcf=[5, -1, 5, 5, 5]))[0]
    assert "extreme divergence" in artifact_flags(
        _fake_result(upside=-0.75))[0]
    two = artifact_flags(_fake_result(trailing_growth=0.35, tv_share=0.92))
    assert len(two) == 2
    assert verdict([]) == "worth a look"
    assert verdict(["x"]) == "caution"
    assert verdict(["x", "y"]) == "likely artifact"


def test_scan_orchestration(simpleco, monkeypatch):
    def fake_fetch(tk, **kw):
        if tk == "SMPL":
            return simpleco
        if tk == "GATED":
            raise FMPError("FMP profile for GATED: HTTP 402 — Premium")
        raise FMPError("GONE: no income statement data on FMP.")
    monkeypatch.setattr(scan_mod, "fetch_financials", fake_fetch)
    res = scan_mod.scan(["SMPL", "GATED", "GONE"])
    assert [r["ticker"] for r in res["rows"]] == ["SMPL"]
    assert res["gated"] == ["GATED"]
    assert res["failed"][0][0] == "GONE"
    row = res["rows"][0]
    assert "verdict" in row and isinstance(row["flags"], list)
    # SimpleCo at $50 vs a much higher DCF -> extreme-divergence flag fires
    assert row["upside"] > 0
    txt = scan_mod.format_table(res["rows"])
    assert "SMPL" in txt and "Verdict" in txt


def test_scan_ranking(simpleco, monkeypatch):
    cheap = dict(simpleco, ticker="CHEP", price=20.0)
    rich = dict(simpleco, ticker="RICH", price=500.0)
    monkeypatch.setattr(scan_mod, "fetch_financials",
                        lambda tk, **kw: {"CHEP": cheap, "RICH": rich}[tk])
    res = scan_mod.scan(["RICH", "CHEP"])
    assert [r["ticker"] for r in res["rows"]] == ["CHEP", "RICH"]
    assert res["rows"][0]["upside"] > res["rows"][1]["upside"]


def test_universe_loading(tmp_path):
    assert len(load_universe()) >= 20
    f = tmp_path / "u.txt"
    f.write_text("aapl  # phone co\n\n# comment line\nmsft\n")
    assert load_universe(f) == ["AAPL", "MSFT"]
    with pytest.raises(FileNotFoundError):
        load_universe(tmp_path / "nope.txt")

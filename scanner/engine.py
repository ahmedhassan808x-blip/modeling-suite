"""
Batch valuation engine — a pure-Python MIRROR of the Excel DCF.

Why a mirror: scanning a universe by building and recalculating a live
workbook per ticker would be slow and pointless — the workbook exists for
analysts to interrogate, the scanner exists to rank. But a shortcut engine
is only honest if it provably matches the real model, so the mirror
replicates the Excel formulas exactly — including the 4-decimal rounding
applied when drivers are written to the Assumptions sheet — and the test
suite asserts mirror-vs-workbook agreement on the recalculated file.

Full workbooks are then built on demand for names worth a closer look
(scan.py --build-top).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dcf.model_builder import derive_wacc_seeds  # noqa: E402
from three_statement.assumptions import Assumptions  # noqa: E402

N_FC = 5


def _r4(values):
    return [round(v, 4) for v in values]


def quick_dcf(data: dict, wacc_seeds: dict | None = None) -> dict:
    """Gordon + exit-multiple DCF per share, mirroring the workbook exactly."""
    a = Assumptions.derive(data)
    w = wacc_seeds or derive_wacc_seeds(data, a)
    growth, gm, opex = _r4(a.rev_growth), _r4(a.gross_margin), _r4(a.opex_pct)
    da, capex, tax = _r4(a.da_pct), _r4(a.capex_pct), _r4(a.tax_rate)
    dso, dio, dpo = _r4(a.dso), _r4(a.dio), _r4(a.dpo)
    oca, ocl = _r4(a.other_ca_pct), _r4(a.other_cl_pct)

    isl, bsl = data["is"], data["bs"]
    rev_prev = isl["revenue"][-1]
    # Year-0 NWC anchor: ACTUAL balance sheet lines, exactly as the workbook's
    # Y1 deltas reference the blue historical column.
    nwc_prev = (bsl["ar"][-1] + bsl["inv"][-1] + bsl["other_ca"][-1]
                - bsl["ap"][-1] - bsl["other_cl"][-1])

    ufcf, ebitda_path = [], []
    for t in range(N_FC):
        rev = rev_prev * (1 + growth[t])
        cogs = rev * (1 - gm[t])
        ebitda = rev * (gm[t] - opex[t])
        da_amt = rev * da[t]
        ebit = ebitda - da_amt
        nopat = ebit * (1 - tax[t])
        capex_amt = rev * capex[t]
        nwc = (dso[t] / 365 * rev + dio[t] / 365 * cogs + oca[t] * rev
               - dpo[t] / 365 * cogs - ocl[t] * rev)
        ufcf.append(nopat + da_amt - capex_amt - (nwc - nwc_prev))
        ebitda_path.append(ebitda)
        rev_prev, nwc_prev = rev, nwc

    wacc = ((1 - w["dw"]) * (w["rf"] + data["beta"] * w["erp"])
            + w["dw"] * w["kd"] * (1 - tax[0]))
    pv = sum(f / (1 + wacc) ** (t + 1) for t, f in enumerate(ufcf))
    tv = ufcf[-1] * (1 + w["tg"]) / (wacc - w["tg"])
    pv_tv = tv / (1 + wacc) ** N_FC
    ev = pv + pv_tv
    net_debt = bsl["debt"][-1] - bsl["cash"][-1]
    shares = data["shares_mm"]
    ps = (ev - net_debt) / shares if shares else float("nan")

    ev_exit = pv + (w["exit_mult"] * ebitda_path[-1]) / (1 + wacc) ** N_FC
    ps_exit = (ev_exit - net_debt) / shares if shares else float("nan")

    price = data["price"]
    rev_hist = isl["revenue"]
    return dict(
        ticker=data["ticker"], name=data["name"], price=price,
        ps=ps, ps_exit=ps_exit,
        upside=ps / price - 1 if price else float("nan"),
        upside_exit=ps_exit / price - 1 if price else float("nan"),
        wacc=wacc, tv_share=pv_tv / ev if ev else float("nan"),
        ufcf=ufcf,
        trailing_growth=(rev_hist[-1] / rev_hist[-2] - 1)
        if len(rev_hist) >= 2 else 0.0,
        data_gaps=(isl["dna"][-1] == 0 or data["cf"]["capex"][-1] == 0),
    )


def artifact_flags(result: dict) -> list[str]:
    """Honesty layer: reasons a 'mispricing' is more likely a model artifact.
    Mirrors the known limitations documented in the DCF README."""
    flags = []
    if result["trailing_growth"] >= 0.20:
        flags.append(f"hypergrowth ({result['trailing_growth']:.0%} trailing) "
                     "— a 5-yr DCF with growth fade structurally understates")
    if result["tv_share"] > 0.80:
        flags.append(f"terminal-value dominant ({result['tv_share']:.0%} of "
                     "EV) — the answer is mostly one assumption")
    if min(result["ufcf"]) <= 0:
        flags.append("negative forecast FCF in at least one year")
    if abs(result["upside"]) > 0.60:
        flags.append(f"extreme divergence ({result['upside']:+.0%}) — "
                     "artifact until proven otherwise")
    if result["data_gaps"]:
        flags.append("data gaps (D&A or capex defaulted to zero)")
    return flags


def verdict(flags: list[str]) -> str:
    return ("worth a look" if not flags
            else "caution" if len(flags) == 1 else "likely artifact")

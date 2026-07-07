"""
Forecast assumptions for the three-statement model.

The tool builds the model; the analyst owns the assumptions. Every driver here
is seeded from the company's own historicals (with sane clamps so one weird
year can't seed a nonsensical forecast), then written to the Assumptions sheet
as blue inputs — visible, labeled, and meant to be challenged. Nothing here is
hidden inside a formula.

Per-year drivers are lists of length n_forecast (default 5). Growth fades
linearly from trailing growth toward a terminal-ish rate — mean reversion,
not extrapolation.
"""

from dataclasses import dataclass, field


def _clamp(v, lo, hi, fallback=None):
    if v is None or not (lo <= v <= hi):
        return fallback if fallback is not None else max(lo, min(hi, v or lo))
    return v


def _fade(start, end, n):
    if n == 1:
        return [end]
    return [start + (end - start) * i / (n - 1) for i in range(n)]


@dataclass
class Assumptions:
    n_forecast: int = 5
    # per-year drivers (lists, len n_forecast)
    rev_growth: list = field(default_factory=list)
    gross_margin: list = field(default_factory=list)
    opex_pct: list = field(default_factory=list)     # opex ex-D&A, % of revenue
    da_pct: list = field(default_factory=list)       # D&A % of revenue
    capex_pct: list = field(default_factory=list)    # capex % of revenue
    dso: list = field(default_factory=list)          # days sales outstanding
    dio: list = field(default_factory=list)          # days inventory outstanding
    dpo: list = field(default_factory=list)          # days payables outstanding
    other_ca_pct: list = field(default_factory=list)
    other_cl_pct: list = field(default_factory=list)
    tax_rate: list = field(default_factory=list)
    payout: list = field(default_factory=list)       # dividends, % of net income
    # scalars (Debt sheet inputs)
    rate_debt: float = 0.055      # interest on beginning debt balances
    rate_cash: float = 0.03       # yield on beginning cash
    min_cash_pct: float = 0.02    # revolver target: min cash as % of revenue
    min_cash_floor: float = 0.0   # ...with an absolute floor ($mm)
    terminal_growth: float = 0.03  # growth fades to this by the final year

    @classmethod
    def derive(cls, data: dict, n_forecast: int = 5) -> "Assumptions":
        """Seed every driver from historicals; clamp the crazy."""
        isl, bsl, cfl = data["is"], data["bs"], data["cf"]
        rev, cogs = isl["revenue"], isl["cogs"]
        n = len(rev)
        a = cls(n_forecast=n_forecast)

        prior = data.get("prior_revenue")
        g1 = (rev[-1] / rev[-2] - 1) if n >= 2 else \
            (rev[-1] / prior - 1) if prior else 0.05
        g1 = _clamp(g1, -0.20, 0.40, fallback=0.05)
        a.rev_growth = _fade(g1, a.terminal_growth, n_forecast)

        gm = 1 - cogs[-1] / rev[-1] if cogs[-1] else 1.0
        a.gross_margin = [_clamp(gm, 0.0, 1.0)] * n_forecast

        ebitda = isl["ebit"][-1] + isl["dna"][-1]
        opex = (gm * rev[-1] - ebitda) / rev[-1]  # GP - EBITDA, % of revenue
        a.opex_pct = [_clamp(opex, 0.0, 0.95)] * n_forecast

        da = sum(d / r for d, r in zip(isl["dna"], rev)) / n
        a.da_pct = [_clamp(da, 0.0, 0.30)] * n_forecast
        capex = sum(c / r for c, r in zip(cfl["capex"], rev)) / n
        a.capex_pct = [_clamp(capex, 0.0, 0.40, fallback=da)] * n_forecast

        a.dso = [_clamp(bsl["ar"][-1] / rev[-1] * 365, 0, 200)] * n_forecast
        cogs_abs = abs(cogs[-1]) or rev[-1]
        a.dio = [_clamp(bsl["inv"][-1] / cogs_abs * 365, 0, 300)] * n_forecast
        a.dpo = [_clamp(bsl["ap"][-1] / cogs_abs * 365, 0, 300)] * n_forecast
        a.other_ca_pct = [_clamp(bsl["other_ca"][-1] / rev[-1], -0.5, 0.5)] * n_forecast
        a.other_cl_pct = [_clamp(bsl["other_cl"][-1] / rev[-1], -0.5, 0.5)] * n_forecast

        etr = isl["tax"][-1] / isl["pretax"][-1] if isl["pretax"][-1] else 0.21
        a.tax_rate = [_clamp(etr, 0.0, 0.40, fallback=0.21)] * n_forecast

        pay = cfl["dividends"][-1] / isl["ni"][-1] if isl["ni"][-1] > 0 else 0.0
        a.payout = [_clamp(pay, 0.0, 1.0, fallback=0.0)] * n_forecast

        a.min_cash_floor = round(bsl["cash"][-1] * 0.25, 1)  # quarter of current cash
        return a

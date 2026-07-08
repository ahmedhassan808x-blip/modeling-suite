"""
Numeric data layer for the S&P 500 vs. gold brief — FMP stable API only.

Re-runnable-on-demand contract: QUOTES bypass the disk cache every run (the
whole point is today's read); historical series and macro prints use the
24h cache (they change slowly and quota is finite). Every value carries
its as-of date and source.

Free-tier gaps (probed, not assumed): DXY is 402-gated -> EURUSD is used as
the stated dollar proxy here and the actual DXY level is left to the
web-research layer. Index P/E / CAPE / dividend yield have no free numeric
route at all -> research layer, cited, or an explicit gap.
"""

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from news.data_layer import get_macro  # noqa: E402
from shared.fmp_client import FMPError, get  # noqa: E402

SPX_RETURN_PROXY = "SPY"   # price-return proxy; ^GSPC history is spottier


def _quote(symbol: str) -> dict:
    q = get("quote", symbol=symbol, use_cache=False)
    if not q:
        raise FMPError(f"{symbol}: no quote returned.")
    return q[0]


def _history(symbol: str, years: float = 5.4, use_cache: bool = True) -> list:
    start = (date.today() - timedelta(days=int(years * 365.25))).isoformat()
    rows = get("historical-price-eod/light", symbol=symbol, use_cache=use_cache,
               **{"from": start, "to": date.today().isoformat()})
    if not rows:
        raise FMPError(f"{symbol}: no price history returned.")
    return sorted(rows, key=lambda r: r["date"])


def price_on_or_before(rows: list, target: str) -> dict:
    """Closest trading row at or before target date; loud if none."""
    best = None
    for r in rows:
        if r["date"] <= target:
            best = r
        else:
            break
    if best is None:
        raise FMPError(f"no price on/before {target} "
                       f"(history starts {rows[0]['date']}).")
    return best


def compute_returns(rows: list) -> dict:
    """YTD / 1yr / 5yr price returns with the anchor rows kept for the
    live-formula Excel export."""
    today = date.today()
    cur = rows[-1]
    anchors = {
        "ytd": price_on_or_before(rows, f"{today.year - 1}-12-31"),
        "1y": price_on_or_before(rows, (today - timedelta(days=365)).isoformat()),
        "5y": price_on_or_before(rows, (today - timedelta(days=5 * 365)).isoformat()),
    }
    out = {"current": cur, "anchors": anchors}
    for k, a in anchors.items():
        out[k] = cur["price"] / a["price"] - 1
    return out


def real_gold_context(gold_rows: list, use_cache: bool = True) -> dict:
    """Gold deflated to today's dollars over the 5yr window using CPI index
    levels (FMP economic-indicators). Long-run (e.g. 1980) real highs are
    outside free data -> research layer."""
    # NB: this endpoint ignores `limit` (returns ~9 rows) — a date range is
    # the only way to get the full series.
    start = (date.today() - timedelta(days=int(5.6 * 365))).isoformat()
    cpi = get("economic-indicators", name="CPI", use_cache=use_cache,
              **{"from": start, "to": date.today().isoformat()})
    if not cpi or len(cpi) < 24:
        raise FMPError("CPI index series unavailable — cannot deflate gold.")
    cpi = sorted(cpi, key=lambda r: r["date"])
    latest_cpi = cpi[-1]

    def cpi_at(d):
        best = cpi[0]
        for r in cpi:
            if r["date"][:10] <= d:
                best = r
        return best

    reals = []
    for r in gold_rows[:: max(1, len(gold_rows) // 260)]:  # ~weekly samples
        reals.append(r["price"] * latest_cpi["value"] / cpi_at(r["date"])["value"])
    current_real = gold_rows[-1]["price"]  # already in today's dollars
    lo, hi = min(reals), max(reals)
    return dict(current=current_real, low_5y=round(lo, 0), high_5y=round(hi, 0),
                pctile=(current_real - lo) / (hi - lo) if hi > lo else 1.0,
                cpi_as_of=latest_cpi["date"][:10],
                note="5-yr window, CPI-deflated to today's dollars; longer "
                     "history not in free data")


def fetch_market_data(use_cache_hist: bool = True) -> dict:
    """Everything the brief needs from numeric APIs, dated and sourced."""
    today = date.today().isoformat()
    spx_q, gold_q, eur_q = _quote("^GSPC"), _quote("GCUSD"), _quote("EURUSD")
    spx_rows = _history(SPX_RETURN_PROXY, use_cache=use_cache_hist)
    gold_rows = _history("GCUSD", use_cache=use_cache_hist)

    def q_block(q):
        return dict(price=q["price"], change_pct=q.get("changePercentage"),
                    year_high=q.get("yearHigh"), year_low=q.get("yearLow"),
                    avg200=q.get("priceAvg200"), as_of=today,
                    source=f"FMP quote ({q['symbol']})")

    return dict(
        as_of=today,
        spx=q_block(spx_q),
        gold=q_block(gold_q),
        eurusd=q_block(eur_q),
        returns=dict(
            spx=compute_returns(spx_rows), gold=compute_returns(gold_rows),
            source=f"FMP daily closes ({SPX_RETURN_PROXY} price-return proxy "
                   "for S&P; excludes dividends)"),
        macro=get_macro(use_cache=use_cache_hist),
        gold_real=real_gold_context(gold_rows, use_cache=use_cache_hist),
    )

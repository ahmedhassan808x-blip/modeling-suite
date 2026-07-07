"""
News & macro data layer.

Free-tier reality (probed 2026-07): FMP's ticker-news endpoints
(news/stock, press-releases) are 402-gated, so headlines follow the suite's
established dual-source convention:

  local:  yfinance (blocked on cloud hosts — same caveat as everywhere in
          the stack)
  cloud:  FMP `fmp-articles` (editorial feed, free) filtered by ticker tag

Each headline carries its source, and the active provider is reported
loudly — never silently swapped. Macro comes from FMP's free
`treasury-rates` and `economic-indicators` routes. Commodity quotes are
partially free (gold works; several energy symbols are gated — reported
as such, not scraped from elsewhere).
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.fmp_client import FMPError, get  # noqa: E402

MACRO_INDICATORS = ("inflationRate", "federalFunds", "unemploymentRate")


def _from_yfinance(ticker, limit):
    import yfinance as yf

    raw = yf.Ticker(ticker).news or []
    out = []
    for item in raw[:limit]:
        c = item.get("content", item)  # yfinance >=0.2.5x nests content
        title = c.get("title")
        if not title:
            continue
        prov = c.get("provider") or {}
        url = (c.get("canonicalUrl") or {}).get("url") or c.get("link", "")
        out.append(dict(
            title=title.strip(),
            source=prov.get("displayName") or c.get("publisher", "Yahoo"),
            date=(c.get("pubDate") or c.get("displayTime") or "")[:10],
            summary=(c.get("summary") or "")[:400],
            url=url))
    return out


def _from_fmp_articles(ticker, limit, use_cache=True):
    arts = get("fmp-articles", limit=100, use_cache=use_cache)
    tk = ticker.upper()
    out = []
    for a in arts:
        tickers = (a.get("tickers") or "").upper()
        if tk not in re.split(r"[:,\s]+", tickers):
            continue
        text = re.sub(r"<[^>]+>", " ", a.get("content") or "")
        out.append(dict(
            title=(a.get("title") or "").strip(),
            source=a.get("site") or "FMP",
            date=(a.get("date") or "")[:10],
            summary=re.sub(r"\s+", " ", text).strip()[:400],
            url=a.get("link", "")))
        if len(out) >= limit:
            break
    return out


def get_headlines(ticker: str, limit: int = 10, use_cache: bool = True) -> dict:
    """Returns {source: str, items: [...]}. Tries yfinance, falls back to
    FMP articles; states which source served and warns when coverage is
    thin — an empty result is reported, never papered over."""
    try:
        items = _from_yfinance(ticker, limit)
        if items:
            return {"source": "Yahoo Finance (yfinance, local)", "items": items}
        print(f"[news] yfinance returned no headlines for {ticker}; "
              "falling back to FMP articles", file=sys.stderr)
    except Exception as e:
        print(f"[news] yfinance unavailable ({e}); falling back to FMP "
              "articles", file=sys.stderr)
    items = _from_fmp_articles(ticker, limit, use_cache)
    if not items:
        print(f"[news] WARNING: no headlines found for {ticker} from either "
              "source — context will be macro-only.", file=sys.stderr)
    return {"source": "FMP editorial articles (free tier)", "items": items}


def get_macro(use_cache: bool = True) -> dict:
    """Latest macro snapshot: treasury curve + key indicator prints."""
    tr = get("treasury-rates", limit=1, use_cache=use_cache)
    if not tr:
        raise FMPError("treasury-rates returned empty — no macro context.")
    t = tr[0]
    out = {
        "as_of": t.get("date"),
        "treasury": {"3m": t.get("month3"), "2y": t.get("year2"),
                     "10y": t.get("year10"), "30y": t.get("year30")},
        "indicators": {},
    }
    for name in MACRO_INDICATORS:
        rows = get("economic-indicators", name=name, limit=2,
                   use_cache=use_cache)
        if rows:
            out["indicators"][name] = dict(value=rows[0]["value"],
                                           date=rows[0]["date"][:10])
        else:
            print(f"[macro] {name}: no data returned — omitted.",
                  file=sys.stderr)
    gdp = get("economic-indicators", name="realGDP", limit=5,
              use_cache=use_cache)
    if gdp and len(gdp) >= 5 and gdp[4]["value"]:
        out["indicators"]["realGDP_yoy"] = dict(
            value=round((gdp[0]["value"] / gdp[4]["value"] - 1) * 100, 2),
            date=gdp[0]["date"][:10])
    return out


def get_commodity_quote(symbol: str, use_cache: bool = True) -> dict:
    """Quote for a commodity symbol (e.g. GCUSD gold). Gated symbols fail
    loudly with the specific reason — no scraping fallback by design."""
    try:
        q = get("quote", symbol=symbol, use_cache=use_cache)
    except FMPError as e:
        if "402" in str(e) or "subscription" in str(e).lower():
            raise FMPError(
                f"{symbol}: commodity quote is gated on the FMP free tier "
                "(some symbols, e.g. gold GCUSD, are free; others need a "
                "paid plan). Not scraping an unreliable source instead — "
                "per project policy.") from e
        raise
    if not q:
        raise FMPError(f"{symbol}: no quote returned.")
    p = q[0]
    return dict(symbol=symbol.upper(), name=p.get("name", symbol),
                price=p.get("price"), change_pct=p.get("changePercentage"),
                year_high=p.get("yearHigh"), year_low=p.get("yearLow"))

"""
Peer trading-multiple data for the DCF/comps workbook.

Ported from analyst-toolkit/valuation-engine/fmp_data.py with one behavioral
fix: peers that fail (missing data, or FMP free-tier 402 "premium symbol")
are skipped LOUDLY with the specific reason on stderr — the old version
swallowed exceptions silently, which violates the repo standard.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.excel_utils import MM  # noqa: E402
from shared.fmp_client import FMPError, field, get  # noqa: E402


def get_peer_multiples(tickers: list[str], use_cache: bool = True) -> list[dict]:
    """LTM trading multiples per peer, in $mm. Skips failures loudly."""
    out = []
    for tk in tickers:
        try:
            prof = get("profile", symbol=tk, use_cache=use_cache)
            inc = get("income-statement", symbol=tk, limit=1, use_cache=use_cache)
            bs = get("balance-sheet-statement", symbol=tk, limit=1,
                     use_cache=use_cache)
        except FMPError as e:
            print(f"[peers] SKIPPING {tk}: {e}", file=sys.stderr)
            continue
        if not prof or not inc:
            print(f"[peers] SKIPPING {tk}: empty FMP payload", file=sys.stderr)
            continue
        p, i = prof[0], inc[0]
        b = bs[0] if bs else {}
        ctx = f"peer {tk}"
        mkt_cap = field(p, "marketCap", "mktCap", default=0, context=ctx)
        net_debt = (field(b, "totalDebt", default=0, context=ctx)
                    - field(b, "cashAndShortTermInvestments",
                            "cashAndCashEquivalents", default=0, context=ctx))
        ev = mkt_cap + net_debt if mkt_cap else None
        ebit = field(i, "operatingIncome", default=0, context=ctx)
        dna = field(i, "depreciationAndAmortization", default=0, context=ctx)
        ebitda = field(i, "ebitda", default=ebit + dna, context=ctx)
        revenue = field(i, "revenue", default=0, context=ctx)
        ni = field(i, "netIncome", default=0, context=ctx)
        out.append({
            "ticker": tk.upper(),
            "name": p.get("companyName", tk),
            "mkt_cap": mkt_cap / MM if mkt_cap else None,
            "ev": ev / MM if ev else None,
            "ev_ebitda": (ev / ebitda) if ev and ebitda > 0 else None,
            "ev_revenue": (ev / revenue) if ev and revenue > 0 else None,
            "pe": (mkt_cap / ni) if mkt_cap and ni > 0 else None,
        })
    if tickers and not out:
        raise FMPError(f"All {len(tickers)} peers failed — comps would be empty. "
                       "See [peers] messages above for reasons.")
    return out

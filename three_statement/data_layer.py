"""
Data layer for the three-statement model.

Fetches historical IS / BS / CF from FMP (stable API) and reshapes them into
the exact line items the model uses. Two rules, matching the repo standard:

  1. Fail loudly and specifically — required fields raise, optional fields log
     the default they fall back to. Never silently guess.
  2. Historicals must tie. The balance sheet is decomposed into modeled lines
     plus explicit "other" plug lines computed from reported subtotals, so
     Total Assets = Total Liabilities & Equity holds exactly in every
     historical year before a single formula is written.

All figures returned in $mm, lists ordered oldest -> newest.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.fmp_client import FMPError, field, get  # noqa: E402
from shared.excel_utils import MM  # noqa: E402


def fetch_financials(ticker: str, n_hist: int = 3, use_cache: bool = True) -> dict:
    """Fetch profile + n_hist years of IS/BS/CF (plus one prior IS for growth)."""
    prof = get("profile", symbol=ticker, use_cache=use_cache)
    if not prof:
        raise FMPError(f"{ticker}: not found on FMP (US-listed tickers work best).")
    inc = get("income-statement", symbol=ticker, limit=n_hist + 1, use_cache=use_cache)
    bs = get("balance-sheet-statement", symbol=ticker, limit=n_hist, use_cache=use_cache)
    cf = get("cash-flow-statement", symbol=ticker, limit=n_hist, use_cache=use_cache)
    for name, data, need in (("income statement", inc, n_hist),
                             ("balance sheet", bs, n_hist),
                             ("cash flow statement", cf, n_hist)):
        if not data or len(data) < need:
            raise FMPError(f"{ticker}: FMP returned {len(data or [])} years of "
                           f"{name}; need {need}.")
    return parse_financials(ticker, prof[0], inc, bs, cf, n_hist)


def parse_financials(ticker, prof, inc, bs, cf, n_hist=3) -> dict:
    """Pure transformation FMP JSON -> model inputs. Testable offline."""
    inc = sorted(inc, key=lambda x: x.get("date", ""))
    bs = sorted(bs, key=lambda x: x.get("date", ""))[-n_hist:]
    cf = sorted(cf, key=lambda x: x.get("date", ""))[-n_hist:]
    prior_inc = inc[-n_hist - 1] if len(inc) > n_hist else None
    inc = inc[-n_hist:]

    years = [int(x["date"][:4]) for x in inc]
    bs_years = [int(x["date"][:4]) for x in bs]
    if years != bs_years:
        raise FMPError(f"{ticker}: IS years {years} != BS years {bs_years} — "
                       "statements are misaligned; refusing to build.")

    def mm(v):
        return v / MM

    # ---- Income statement lines ------------------------------------------
    is_l = {"revenue": [], "cogs": [], "ebit": [], "dna": [], "int_exp": [],
            "int_inc": [], "other": [], "pretax": [], "tax": [], "ni": []}
    for i, c in zip(inc, cf):
        ctx = f"{ticker} FY{i['date'][:4]}"
        rev = field(i, "revenue", context=ctx)                       # required
        if rev <= 0:
            raise FMPError(f"{ctx}: non-positive revenue {rev} — refusing to build.")
        ebit = field(i, "operatingIncome", context=ctx)              # required
        ni = field(i, "netIncome", context=ctx)                      # required
        pretax = field(i, "incomeBeforeTax", default=ni, context=ctx)
        cogs = field(i, "costOfRevenue", default=0, context=ctx)
        dna = field(c, "depreciationAndAmortization", default=0, context=ctx + " (CF)")
        ie = field(i, "interestExpense", default=0, context=ctx)
        ii = field(i, "interestIncome", default=0, context=ctx)
        tax = field(i, "incomeTaxExpense", default=pretax - ni, context=ctx)
        # Plug so historical pre-tax income ties exactly to reported:
        # EBT = EBIT - int_exp + int_inc + other
        other = pretax - ebit + ie - ii
        for k, v in (("revenue", rev), ("cogs", cogs), ("ebit", ebit),
                     ("dna", dna), ("int_exp", ie), ("int_inc", ii),
                     ("other", other), ("pretax", pretax), ("tax", tax),
                     ("ni", ni)):
            is_l[k].append(mm(v))

    # ---- Balance sheet lines (plugs make each year tie exactly) ----------
    bs_l = {k: [] for k in
            ("cash", "ar", "inv", "other_ca", "ppe", "gw_intan", "other_nca",
             "total_assets", "ap", "other_cl", "debt", "other_ncl",
             "total_liab", "cs_apic", "re", "other_eq", "minority")}
    for b in bs:
        ctx = f"{ticker} FY{b['date'][:4]} (BS)"
        ta = field(b, "totalAssets", context=ctx)                    # required
        tl = field(b, "totalLiabilities", context=ctx)               # required
        tca = field(b, "totalCurrentAssets", default=0, context=ctx)
        tcl = field(b, "totalCurrentLiabilities", default=0, context=ctx)
        cash = field(b, "cashAndShortTermInvestments",
                     "cashAndCashEquivalents", default=0, context=ctx)
        ar = field(b, "netReceivables", default=0, context=ctx)
        inv = field(b, "inventory", default=0, context=ctx)
        ppe = field(b, "propertyPlantEquipmentNet", default=0, context=ctx)
        gwi = field(b, "goodwillAndIntangibleAssets", default=None, context=ctx) \
            if (b.get("goodwillAndIntangibleAssets") is not None) else \
            field(b, "goodwill", default=0, context=ctx) + \
            field(b, "intangibleAssets", default=0, context=ctx)
        ap = field(b, "accountPayables", "accountsPayables", default=0, context=ctx)
        std = field(b, "shortTermDebt", default=0, context=ctx)
        ltd = field(b, "longTermDebt", default=0, context=ctx)
        debt = std + ltd  # modeled as one line; revolver starts at zero
        cs = field(b, "commonStock", default=0, context=ctx) + \
            field(b, "additionalPaidInCapital", default=0, context=ctx)
        re = field(b, "retainedEarnings", default=0, context=ctx)
        tse = field(b, "totalStockholdersEquity", default=ta - tl, context=ctx)
        te = field(b, "totalEquity", default=tse, context=ctx)
        minority = te - tse

        other_ca = tca - cash - ar - inv
        other_nca = ta - tca - ppe - gwi
        other_cl = tcl - ap - std
        other_ncl = tl - tcl - ltd
        other_eq = tse - cs - re
        # Force the accounting identity if FMP's own totals are inconsistent.
        imbalance = ta - (tl + te)
        if abs(imbalance) > 1e6:
            print(f"[data] {ctx}: reported TA - (TL+TE) = {imbalance / MM:,.1f}mm; "
                  "absorbed into Other equity so the model ties.", file=sys.stderr)
            other_eq += imbalance

        for k, v in (("cash", cash), ("ar", ar), ("inv", inv),
                     ("other_ca", other_ca), ("ppe", ppe), ("gw_intan", gwi),
                     ("other_nca", other_nca), ("total_assets", ta),
                     ("ap", ap), ("other_cl", other_cl), ("debt", debt),
                     ("other_ncl", other_ncl), ("total_liab", tl),
                     ("cs_apic", cs), ("re", re), ("other_eq", other_eq),
                     ("minority", minority)):
            bs_l[k].append(mm(v))

    # ---- Cash flow reference lines (for driver seeding + memo display) ---
    cf_l = {"capex": [], "dividends": [], "cfo": []}
    for c in cf:
        ctx = f"{ticker} FY{c['date'][:4]} (CF)"
        cf_l["capex"].append(mm(abs(field(c, "capitalExpenditure", default=0,
                                          context=ctx))))
        cf_l["dividends"].append(mm(abs(field(c, "netDividendsPaid",
                                              "dividendsPaid", default=0,
                                              context=ctx))))
        cf_l["cfo"].append(mm(field(c, "netCashProvidedByOperatingActivities",
                                    default=0, context=ctx)))

    # Market data (used by the DCF layer; optional for the 3-statement build)
    price = field(prof, "price", default=0, context=f"{ticker} profile")
    mkt_cap = field(prof, "marketCap", "mktCap", default=0,
                    context=f"{ticker} profile")
    rng = (prof.get("range") or "0-0").split("-")

    return {
        "ticker": ticker.upper(),
        "name": prof.get("companyName", ticker),
        "currency": prof.get("currency", "USD"),
        "price": price,
        "shares_mm": mkt_cap / price / MM if price else 0,
        "beta": field(prof, "beta", default=1.0, context=f"{ticker} profile") or 1.0,
        "wk52_low": float(rng[0] or 0),
        "wk52_high": float(rng[-1] or 0),
        "years": years,
        "n_hist": n_hist,
        "prior_revenue": mm(field(prior_inc, "revenue", context=f"{ticker} prior yr"))
        if prior_inc else None,
        "is": is_l,
        "bs": bs_l,
        "cf": cf_l,
    }

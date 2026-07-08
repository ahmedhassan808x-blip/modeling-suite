"""
Brief assembly — S&P 500 vs. gold, as of today.

Division of labor (same contract as the pitch generator):
  - numbers: fetched/computed programmatically, dated, sourced
  - macro backdrop: templated prose with live numbers interpolated —
    deterministic, so the explanations can't drift from the data
  - the argumentative sections (case for each, reasoned view): one LLM call
    grounded strictly in the assembled facts pack, forced to state a lean
    (or "roughly balanced" if genuinely so) and what would change it

This is analysis to inform thinking, not a recommendation — stamped on
every artifact.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.llm import active_model, ask_json  # noqa: E402
from sp500_vs_gold.data_layer import fetch_market_data  # noqa: E402
from sp500_vs_gold.research import research_market_context  # noqa: E402

GAP = "not obtained this run"

SYNTH_KEYS = ("case_spx", "case_gold", "reasoned_view", "lean",
              "what_would_change")

SYNTH_SYSTEM = """You are a cross-asset strategist writing an allocation
brief for a thoughtful reader. Rules:
- Use ONLY the facts pack. Every claim must tie to a specific figure or
  sourced item in it. Figures marked "not obtained this run" must not be
  leaned on — acknowledge the gap if it matters.
- State a lean: "S&P 500", "Gold", or "Roughly balanced". Do not hedge into
  meaninglessness — if the retrieved data points one way, say so directly;
  if it is genuinely mixed, say that plainly and explain what makes it
  mixed.
- "what_would_change" items must be specific, observable data or events
  that would flip the lean.
- This is analysis, not advice; markets can move against sound reasoning
  in the short run. Assume the reader knows this — argue honestly anyway.
Return ONLY valid JSON."""

SYNTH_PROMPT = """Facts pack, retrieved {as_of}:

{facts}

Return JSON with exactly these keys:
- "case_spx": 4-5 bullets (strings) — the case for the S&P 500 right now,
  each tied to specific retrieved data
- "case_gold": 4-5 bullets — the case for gold right now, same standard
- "reasoned_view": 2-3 paragraphs weighing the two given the CURRENT data
  (not priors), naming the decisive factors and their values
- "lean": exactly one of "S&P 500", "Gold", "Roughly balanced"
- "what_would_change": 3-4 specific observable developments that would
  flip this lean"""


def _pct(v, dp=1):
    return f"{v:.{dp}%}" if v is not None else GAP


def _num(v, fmt=",.1f", suffix=""):
    return f"{v:{fmt}}{suffix}" if v is not None else GAP


def _r(research, key, fmt=",.1f", suffix=""):
    item = research[key]
    if item["value"] is None:
        return GAP, "", item.get("note", "no sourced figure found")
    return (f"{item['value']:{fmt}}{suffix}", item.get("as_of") or "",
            item.get("source") or "")


def derived_metrics(data, research):
    ten_y = data["macro"]["treasury"]["10y"]
    infl = data["macro"]["indicators"].get("inflationRate", {}).get("value")
    out = {"real_yield_approx": (ten_y - infl) if infl is not None else None,
           "ten_y": ten_y, "inflation": infl}
    pe = research["spx_trailing_pe"]["value"]
    if pe:
        out["earnings_yield"] = 100.0 / pe
        out["erp_proxy"] = 100.0 / pe - ten_y
    else:
        out["earnings_yield"] = out["erp_proxy"] = None
    return out


def snapshot_rows(data, research, der) -> list[dict]:
    spx, gold, ret = data["spx"], data["gold"], data["returns"]
    m = data["macro"]

    def row(metric, s, g, as_of, source):
        return dict(metric=metric, spx=s, gold=g, as_of=as_of, source=source)

    pe, pe_d, pe_s = _r(research, "spx_trailing_pe", ",.1f", "x")
    fpe, fpe_d, fpe_s = _r(research, "spx_forward_pe", ",.1f", "x")
    cape, cape_d, cape_s = _r(research, "cape", ",.1f", "x")
    dy, dy_d, dy_s = _r(research, "spx_dividend_yield_pct", ",.2f", "%")
    dxy, dxy_d, dxy_s = _r(research, "dxy", ",.1f")
    tips, tips_d, tips_s = _r(research, "tips_10y_real_yield_pct", ",.2f", "%")
    gr = data["gold_real"]

    return [
        row("Price / level", f"{spx['price']:,.0f}", f"${gold['price']:,.0f}",
            data["as_of"], "FMP quotes (^GSPC, GCUSD)"),
        row("52-week range", f"{spx['year_low']:,.0f}–{spx['year_high']:,.0f}",
            f"${gold['year_low']:,.0f}–${gold['year_high']:,.0f}",
            data["as_of"], "FMP quotes"),
        row("YTD return", _pct(ret["spx"]["ytd"]), _pct(ret["gold"]["ytd"]),
            data["as_of"], ret["source"]),
        row("1-year return", _pct(ret["spx"]["1y"]), _pct(ret["gold"]["1y"]),
            data["as_of"], ret["source"]),
        row("5-year return", _pct(ret["spx"]["5y"]), _pct(ret["gold"]["5y"]),
            data["as_of"], ret["source"]),
        row("Trailing P/E", pe, "n/a (no earnings)", pe_d, pe_s),
        row("Forward P/E", fpe, "n/a", fpe_d, fpe_s),
        row("Shiller CAPE", cape, "n/a", cape_d, cape_s),
        row("Dividend / carry yield", dy, "none (negative after storage)",
            dy_d, dy_s),
        row("Earnings yield − 10Y (ERP proxy)",
            _num(der["erp_proxy"], "+.2f", "pp") if der["erp_proxy"]
            is not None else GAP, "n/a", data["as_of"],
            "computed: 1/trailing P/E − 10Y treasury" if der["erp_proxy"]
            is not None else "needs trailing P/E"),
        row("Real 5-yr price range (today's $)", "n/a",
            f"${gr['low_5y']:,.0f}–${gr['high_5y']:,.0f} "
            f"(now at {gr['pctile']:.0%} of range)",
            gr["cpi_as_of"], "computed: FMP gold closes deflated by CPI index"),
        row("Key macro: 10Y / CPI YoY / Fed funds",
            f"{der['ten_y']:.2f}% / {_num(der['inflation'], '.2f', '%')} / "
            f"{_num(m['indicators'].get('federalFunds', {}).get('value'), '.2f', '%')}",
            "(same backdrop)", m["as_of"], "FMP treasury-rates, "
            "economic-indicators"),
        row("Real yield — approx (10Y − CPI YoY)",
            _num(der["real_yield_approx"], "+.2f", "pp"), "(opportunity cost "
            "of holding gold)", m["as_of"], "computed"),
        row("Real yield — 10Y TIPS (market)", tips, "", tips_d, tips_s),
        row("US dollar", f"DXY {dxy}" if dxy != GAP else f"DXY {GAP}",
            f"EURUSD {data['eurusd']['price']:.4f} (proxy, FMP)",
            dxy_d or data["as_of"], dxy_s or "DXY gated on FMP free tier; "
            "EURUSD proxy + web-sourced DXY"),
    ]


def macro_paragraphs(data, research, der) -> list[str]:
    m = data["macro"]
    ff = m["indicators"].get("federalFunds", {})
    tr = m["treasury"]
    rate_txt = research["rate_expectations"]["summary"] \
        if research["rate_expectations"].get("summary") else GAP
    tips_v = research["tips_10y_real_yield_pct"]["value"]
    dxy_v = research["dxy"]["value"]
    return [
        # rates
        f"Policy rates: fed funds sits at {_num(ff.get('value'), '.2f', '%')} "
        f"(as of {ff.get('date', '?')}), with the curve at "
        f"{tr['2y']:.2f}% (2Y) / {tr['10y']:.2f}% (10Y). Rate expectations, "
        f"per current research: {rate_txt} Cuts help both assets — equities "
        "through discount rates and gold through lower carry cost — but "
        "gold is the more mechanically rate-sensitive of the two because "
        "it pays nothing.",
        # inflation
        f"Inflation: CPI is running at "
        f"{_num(der['inflation'], '.2f', '%')} YoY (as of "
        f"{m['indicators'].get('inflationRate', {}).get('date', '?')}). "
        "Moderate, anchored inflation blunts gold's classic "
        "inflation-hedge pitch; a re-acceleration would revive it and "
        "simultaneously pressure equity multiples.",
        # dollar
        f"The dollar: {'DXY at ' + format(dxy_v, ',.1f') + ' (web-sourced)'
                       if dxy_v else 'DXY ' + GAP + ' (FMP free tier gates '
                       'it)'}; EURUSD at {data['eurusd']['price']:.4f} "
        f"(52-wk {data['eurusd']['year_low']:.3f}–"
        f"{data['eurusd']['year_high']:.3f}). Gold is priced in dollars — "
        "dollar weakness mechanically flatters it and typically "
        "accompanies looser policy; sustained dollar strength is a "
        "headwind.",
        # real yields + ERP
        f"Real yields — the single biggest driver of gold's opportunity "
        f"cost: the crude approximation (10Y minus CPI YoY) gives "
        f"{_num(der['real_yield_approx'], '+.2f', 'pp')}"
        + (f", and the market 10Y TIPS real yield is {tips_v:.2f}% "
           f"({research['tips_10y_real_yield_pct'].get('source', '')})"
           if tips_v else f"; the market TIPS figure was {GAP}")
        + ". Positive and rising real yields make a zero-yield asset "
        "expensive to hold; falling real yields historically do the "
        "opposite. For equities, the mirror metric is the ERP proxy "
        f"(earnings yield minus 10Y): "
        f"{_num(der['erp_proxy'], '+.2f', 'pp')} — thin compensation for "
        "equity risk when this is near or below zero.",
    ]


def facts_text(data, research, der, rows) -> str:
    lines = [f"SNAPSHOT (as of {data['as_of']}):"]
    for r in rows:
        lines.append(f"- {r['metric']}: S&P {r['spx']} | Gold {r['gold']} "
                     f"[{r['as_of']}; {r['source']}]")
    lines.append("\nRESEARCHED CONTEXT (web-sourced):")
    for k in ("rate_expectations", "gold_flows", "equity_flows",
              "notable_events"):
        item = research[k]
        lines.append(f"- {k}: {item.get('summary', GAP)} "
                     f"(sources: {', '.join(item.get('sources', [])) or '—'})")
    lines.append("\nSTRATEGIST VIEWS:")
    for v in research.get("strategist_views", []):
        lines.append(f"- [{v.get('date', '?')}] {v.get('source', '?')} on "
                     f"{v.get('asset', '?')}: {v.get('view', '')}")
    if research["gaps"]:
        lines.append(f"\nDATA GAPS THIS RUN (do not lean on these): "
                     f"{', '.join(research['gaps'])}")
    return "\n".join(lines)


def synthesize_view(facts: str, as_of: str, model: str | None = None,
                    llm=None) -> dict:
    view = ask_json(SYNTH_PROMPT.format(facts=facts, as_of=as_of),
                    required_keys=SYNTH_KEYS, system=SYNTH_SYSTEM,
                    max_tokens=4000, model=model, llm=llm)
    if view["lean"] not in ("S&P 500", "Gold", "Roughly balanced"):
        view["lean"] = "Roughly balanced"
    return view


def build_brief(use_cache_hist: bool = True, model: str | None = None,
                research_llm=None, synth_llm=None) -> dict:
    data = fetch_market_data(use_cache_hist=use_cache_hist)
    research = research_market_context(model=model, llm=research_llm)
    der = derived_metrics(data, research)
    rows = snapshot_rows(data, research, der)
    facts = facts_text(data, research, der, rows)
    view = synthesize_view(facts, data["as_of"], model=model, llm=synth_llm)
    label = model or (active_model() if synth_llm is None else "injected")
    return dict(as_of=data["as_of"], data=data, research=research, der=der,
                rows=rows, macro=macro_paragraphs(data, research, der),
                view=view, model=label)

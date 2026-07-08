"""
Web-research layer — the figures and context no free numeric API provides.

Uses Claude with the server-side web search tool, under a strict contract:
every numeric must come from a search result with a publication date and
source; anything not found comes back null and is rendered as an explicit
"not obtained this run" gap — never a training-data guess, never a stale
fallback (per project decision).
"""

import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.llm import DEFAULT_MODEL, LLMError, ask_json, ask_with_search  # noqa: E402

NUMERIC_KEYS = ("spx_trailing_pe", "spx_forward_pe", "cape",
                "spx_dividend_yield_pct", "dxy", "tips_10y_real_yield_pct")
TEXT_KEYS = ("rate_expectations", "gold_flows", "equity_flows",
             "notable_events")

SYSTEM = """You are a research assistant retrieving CURRENT market data via
web search. Non-negotiable rules:
- Every numeric value must come from a web search result. If you cannot find
  a figure with an identifiable source and date, return null for it — never
  estimate from memory, never use approximate recalled values.
- Prefer primary/standard sources (multpl, Yale/Shiller, WSJ, FT, Reuters,
  Bloomberg, US Treasury, CME FedWatch, fund-flow trackers).
- as_of is the date the figure refers to (or publication date), YYYY-MM-DD.
- Text summaries must only describe what the searches actually returned,
  with the source named inline.
Return ONLY a valid JSON object, no code fences."""

PROMPT = """Today is {today}. Retrieve the following via web search and
return JSON with exactly these keys.

Numeric (each an object {{"value": number|null, "as_of": str|null,
"source": str|null, "url": str|null}}):
- spx_trailing_pe: S&P 500 trailing twelve-month P/E
- spx_forward_pe: S&P 500 forward (next-12-months) P/E
- cape: Shiller CAPE ratio, current
- spx_dividend_yield_pct: S&P 500 dividend yield, percent
- dxy: US Dollar Index (DXY) level
- tips_10y_real_yield_pct: 10-year TIPS real yield, percent

Text (each an object {{"summary": str, "sources": [str, ...]}}; summary
2-4 sentences, sources named with dates):
- rate_expectations: what rate cuts/hikes are currently priced in
  (FedWatch or equivalent) and recent Fed commentary
- gold_flows: recent gold ETF flows / central-bank buying trend
- equity_flows: recent equity fund/ETF flow trend and the prevailing
  equity narrative (earnings, AI capex, breadth)
- notable_events: geopolitical/macro developments from the last few weeks
  that plausibly favor either asset

And one more key:
- strategist_views: a list of 3-5 objects {{"source": str, "date": str,
  "asset": "S&P 500"|"Gold"|"Both", "view": str (1-2 sentences)}} from
  named strategists/houses in the last ~2 months."""


def research_market_context(model: str = DEFAULT_MODEL, llm=None) -> dict:
    """Returns the researched dict; validates shape; counts gaps honestly."""
    prompt = PROMPT.format(today=date.today().isoformat())
    call = llm or (lambda p, s, m: ask_with_search(p, system=s, max_tokens=m,
                                                   model=model))
    data = ask_json(prompt, required_keys=NUMERIC_KEYS + TEXT_KEYS
                    + ("strategist_views",), system=SYSTEM, max_tokens=8000,
                    llm=call)
    def _decite(s):
        return re.sub(r"</?cite[^>]*>", "", s) if isinstance(s, str) else s

    for k in TEXT_KEYS:
        if isinstance(data.get(k), dict):
            data[k]["summary"] = _decite(data[k].get("summary", ""))
    for v in data.get("strategist_views", []) or []:
        if isinstance(v, dict):
            v["view"] = _decite(v.get("view", ""))
    for k in NUMERIC_KEYS:
        v = data[k]
        if not isinstance(v, dict) or "value" not in v:
            raise LLMError(f"research payload malformed at {k!r}: {v!r}")
        if v["value"] is not None and not v.get("source"):
            # sourced-or-nothing: an unsourced number is worse than a gap
            v["value"] = None
            v["note"] = "discarded: value returned without a source"
    data["gaps"] = [k for k in NUMERIC_KEYS if data[k]["value"] is None]
    return data

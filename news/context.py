"""
CLI: news & macro context brief for a ticker or commodity.

    python3 -m news.context AAPL
    python3 -m news.context --commodity GCUSD "Gold"

Writes {LABEL}_context.md: retrieved headlines + macro prints (data), then
the grounded AI synthesis (labeled).
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from news.data_layer import (  # noqa: E402
    get_commodity_quote, get_headlines, get_macro,
)
from news.synthesis import (  # noqa: E402
    format_headlines, format_macro, synthesize_context,
)


def build_context(label: str, ticker_for_news: str, extra_facts: str = "",
                  llm=None) -> str:
    headlines = get_headlines(ticker_for_news)
    macro = get_macro()
    brief = synthesize_context(label, headlines, macro, llm=llm)
    return "\n\n".join([
        f"# {label} — News & Macro Context",
        extra_facts,
        brief,
        "---\n## Retrieved material (verbatim)\n",
        f"**Headlines** — {headlines['source']}\n\n"
        + format_headlines(headlines["items"]),
        "**Macro prints**\n\n" + format_macro(macro),
    ])


def main():
    ap = argparse.ArgumentParser(description="News & macro context brief.")
    ap.add_argument("ticker", nargs="?", help="equity ticker")
    ap.add_argument("--commodity", help="commodity symbol, e.g. GCUSD")
    ap.add_argument("--out", help="output .md path")
    args = ap.parse_args()
    if not args.ticker and not args.commodity:
        ap.error("give a ticker or --commodity SYMBOL")

    if args.commodity:
        q = get_commodity_quote(args.commodity)
        label = f"{q['name']} ({q['symbol']})"
        facts = (f"Spot: {q['price']} ({q['change_pct']:+.2f}% today); "
                 f"52-week range {q['year_low']}–{q['year_high']}.")
        news_ticker = args.ticker or args.commodity
    else:
        label, facts, news_ticker = args.ticker.upper(), "", args.ticker

    md = build_context(label, news_ticker, facts)
    out = Path(args.out or f"{(args.commodity or args.ticker).upper()}"
               "_context.md")
    out.write_text(md)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()

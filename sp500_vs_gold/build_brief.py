"""
CLI: build today's S&P 500 vs. gold comparative brief.

    python3 -m sp500_vs_gold.build_brief
    python3 -m sp500_vs_gold.build_brief --outdir briefs --no-cache

Re-runnable on demand: quotes are always fetched fresh; historical series
and macro prints use the 24h cache unless --no-cache. Needs FMP_API_KEY
and ANTHROPIC_API_KEY (research layer uses Claude's web search tool).
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sp500_vs_gold.brief import build_brief  # noqa: E402
from sp500_vs_gold.report import build_outputs  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="S&P 500 vs. gold brief.")
    ap.add_argument("--outdir", default=".")
    ap.add_argument("--no-cache", action="store_true",
                    help="bypass the 24h cache for historical/macro data too")
    args = ap.parse_args()

    brief = build_brief(use_cache_hist=not args.no_cache)
    outputs = build_outputs(brief, args.outdir)
    v = brief["view"]
    print(f"As of {brief['as_of']} — lean: {v['lean']}")
    if brief["research"]["gaps"]:
        print(f"Data gaps: {', '.join(brief['research']['gaps'])}")
    for k, p in outputs.items():
        print(f"{k}: {p}")


if __name__ == "__main__":
    main()

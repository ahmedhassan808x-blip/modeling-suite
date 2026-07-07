"""
CLI: build a DCF valuation workbook linked to a live three-statement model.

    python3 -m dcf.build_model AAPL --peers MSFT,GOOGL,META

Output workbook: Assumptions (with scenario toggle) / Scenarios / IS / BS /
CF / Debt / Checks / DCF, plus Comps and a football-field Summary when peers
are given. The recalc gate runs automatically.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dcf.data_layer import get_peer_multiples  # noqa: E402
from dcf.model_builder import build_dcf_model  # noqa: E402
from shared.recalc import RecalcError, recalculate  # noqa: E402
from three_statement.assumptions import Assumptions  # noqa: E402
from three_statement.data_layer import fetch_financials  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="Build a live DCF valuation model.")
    ap.add_argument("ticker")
    ap.add_argument("--peers", help="comma-separated peer tickers for comps")
    ap.add_argument("--hist", type=int, default=3)
    ap.add_argument("--out", help="output path (default {TICKER}_dcf.xlsx)")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--skip-check", action="store_true")
    ap.add_argument("--report", action="store_true",
                    help="also build deck (.pptx), memo (.docx) and PDF")
    args = ap.parse_args()

    use_cache = not args.no_cache
    data = fetch_financials(args.ticker, n_hist=args.hist, use_cache=use_cache)
    assumptions = Assumptions.derive(data)
    peers = get_peer_multiples(args.peers.split(","), use_cache=use_cache) \
        if args.peers else None
    out = Path(args.out or f"{data['ticker']}_dcf.xlsx")
    build_dcf_model(data, assumptions, out, peers=peers)
    tabs = "3-stmt + DCF" + (" + Comps + Summary" if peers else "")
    print(f"Built {out} — {data['name']} ({tabs})")

    if args.skip_check:
        print("recalc gate SKIPPED — workbook is unverified.")
        return
    try:
        res = recalculate(out, probe_cells=["Checks!B9", "DCF!B37", "DCF!B39"])
    except RecalcError as e:
        print(f"recalc gate unavailable: {e}", file=sys.stderr)
        sys.exit(2)
    verdict = res.values.get("Checks!B9")
    ps, upside = res.values.get("DCF!B37"), res.values.get("DCF!B39")
    print(res.summary() + f" | Checks: {verdict} | DCF implied "
          f"${ps:,.2f}/sh ({upside:+.1%} vs price)" if ps else res.summary())
    if not res.ok or verdict != "PASS":
        sys.exit(1)
    if args.report:
        from dcf.report import build_reports
        for kind, p in build_reports(out).items():
            print(f"{kind}: {p}")


if __name__ == "__main__":
    main()

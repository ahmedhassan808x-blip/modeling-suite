"""
CLI: build a live LBO model for a ticker.

    python3 -m lbo.build_model AAPL
    python3 -m lbo.build_model AAPL --entry 12 --senior 4.0 --sub 1.5 --report

Entry/exit multiples seed from the company's actual market EV/EBITDA unless
overridden. The recalc gate runs automatically.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lbo.assumptions import LBOAssumptions  # noqa: E402
from lbo.model_builder import (  # noqa: E402
    CHECKS_PASS_CELL, R, build_lbo_model,
)
from shared.recalc import RecalcError, recalculate  # noqa: E402
from three_statement.assumptions import Assumptions  # noqa: E402
from three_statement.data_layer import fetch_financials  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="Build a live LBO model.")
    ap.add_argument("ticker")
    ap.add_argument("--entry", type=float, help="entry EV/EBITDA override")
    ap.add_argument("--exit", type=float, dest="exit_mult",
                    help="exit EV/EBITDA override (default: flat to entry)")
    ap.add_argument("--senior", type=float, help="senior x EBITDA (default 3.5)")
    ap.add_argument("--sub", type=float, help="sub x EBITDA (default 1.5)")
    ap.add_argument("--hist", type=int, default=3)
    ap.add_argument("--out", help="default {TICKER}_lbo.xlsx")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--skip-check", action="store_true")
    ap.add_argument("--report", action="store_true",
                    help="also build deck (.pptx), memo (.docx) and PDF")
    args = ap.parse_args()

    data = fetch_financials(args.ticker, n_hist=args.hist,
                            use_cache=not args.no_cache)
    a = Assumptions.derive(data)
    lb = LBOAssumptions.derive(data)
    if args.entry:
        lb.entry_mult = args.entry
        lb.exit_mult = args.exit_mult or args.entry
    elif args.exit_mult:
        lb.exit_mult = args.exit_mult
    if args.senior is not None:
        lb.senior_x = args.senior
    if args.sub is not None:
        lb.sub_x = args.sub

    out = Path(args.out or f"{data['ticker']}_lbo.xlsx")
    build_lbo_model(data, a, lb, out)
    print(f"Built {out} — {data['name']} LBO @ {lb.entry_mult:.1f}x entry, "
          f"{lb.senior_x + lb.sub_x:.1f}x total leverage")

    if args.skip_check:
        print("recalc gate SKIPPED — workbook is unverified.")
        return
    try:
        res = recalculate(out, probe_cells=["Checks!B9", CHECKS_PASS_CELL,
                                            f"Returns!B{R['irr']}",
                                            f"Returns!B{R['moic']}"])
    except RecalcError as e:
        print(f"recalc gate unavailable: {e}", file=sys.stderr)
        sys.exit(2)
    v = res.values
    print(res.summary() + f" | 3-stmt: {v.get('Checks!B9')} | LBO: "
          f"{v.get(CHECKS_PASS_CELL)} | IRR {v.get(f'Returns!B{R['irr']}'):.1%}"
          f" | MOIC {v.get(f'Returns!B{R['moic']}'):.2f}x")
    if not res.ok or v.get("Checks!B9") != "PASS" \
            or v.get(CHECKS_PASS_CELL) != "PASS":
        sys.exit(1)
    if args.report:
        from lbo.report import build_reports
        for kind, p in build_reports(out).items():
            print(f"{kind}: {p}")


if __name__ == "__main__":
    main()

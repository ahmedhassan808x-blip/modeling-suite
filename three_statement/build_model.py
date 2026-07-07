"""
CLI: build a live three-statement model for a ticker.

    python3 -m three_statement.build_model AAPL
    python3 -m three_statement.build_model AAPL --hist 3 --out AAPL_model.xlsx

The recalc gate runs automatically after the build (if LibreOffice is
installed): the workbook is only reported as done when it recalculates with
zero formula errors and the Checks sheet reads PASS.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.recalc import RecalcError, recalculate  # noqa: E402
from three_statement.assumptions import Assumptions  # noqa: E402
from three_statement.data_layer import fetch_financials  # noqa: E402
from three_statement.model_builder import build_model  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="Build a live 3-statement model.")
    ap.add_argument("ticker")
    ap.add_argument("--hist", type=int, default=3, help="historical years (default 3)")
    ap.add_argument("--out", help="output path (default {TICKER}_3stmt.xlsx)")
    ap.add_argument("--no-cache", action="store_true", help="bypass FMP disk cache")
    ap.add_argument("--skip-check", action="store_true",
                    help="skip the LibreOffice recalc gate (not recommended)")
    ap.add_argument("--report", action="store_true",
                    help="also build deck (.pptx), memo (.docx) and PDF")
    args = ap.parse_args()

    data = fetch_financials(args.ticker, n_hist=args.hist,
                            use_cache=not args.no_cache)
    assumptions = Assumptions.derive(data)
    out = Path(args.out or f"{data['ticker']}_3stmt.xlsx")
    build_model(data, assumptions, out)
    print(f"Built {out} — {data['name']}, FY{data['years'][0]}–"
          f"FY{data['years'][-1]}A + {assumptions.n_forecast}yr forecast")

    if args.skip_check:
        print("recalc gate SKIPPED — workbook is unverified.")
        return
    try:
        res = recalculate(out, probe_cells=["Checks!B9"])
    except RecalcError as e:
        print(f"recalc gate unavailable: {e}", file=sys.stderr)
        sys.exit(2)
    verdict = res.values.get("Checks!B9")
    print(res.summary() + f" | Checks sheet: {verdict}")
    if not res.ok or verdict != "PASS":
        sys.exit(1)
    if args.report:
        from three_statement.report import build_reports
        for kind, p in build_reports(out).items():
            print(f"{kind}: {p}")


if __name__ == "__main__":
    main()

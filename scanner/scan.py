"""
Mispricing scanner CLI.

    python3 -m scanner.scan                       # default universe
    python3 -m scanner.scan --universe my.txt --csv out.csv --build-top 2

Runs the Python DCF mirror across the universe (~4 FMP requests per ticker,
disk-cached 24h — a 30-name scan fits comfortably in the free tier's
250/day), ranks by Gordon-DCF upside, and attaches artifact flags so a
"mispricing" that is really a modeling artifact says so on its face.

Gated symbols (free-tier 402s) and failures are reported by name — a
scan that silently drops names isn't a scan.
"""

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scanner.engine import artifact_flags, quick_dcf, verdict  # noqa: E402
from scanner.universe import load_universe  # noqa: E402
from shared.fmp_client import FMPError  # noqa: E402
from three_statement.data_layer import fetch_financials  # noqa: E402


def scan(tickers, use_cache=True) -> dict:
    rows, gated, failed = [], [], []
    for i, tk in enumerate(tickers, 1):
        print(f"[scan] {i}/{len(tickers)} {tk}", file=sys.stderr)
        try:
            data = fetch_financials(tk, n_hist=3, use_cache=use_cache)
            r = quick_dcf(data)
        except FMPError as e:
            msg = str(e)
            if "402" in msg or "subscription" in msg.lower():
                gated.append(tk)
            else:
                failed.append((tk, msg.splitlines()[0][:120]))
            continue
        except Exception as e:  # loud, attributed, non-fatal to the run
            failed.append((tk, f"{type(e).__name__}: {e}"))
            continue
        r["flags"] = artifact_flags(r)
        r["verdict"] = verdict(r["flags"])
        rows.append(r)
    rows.sort(key=lambda r: r["upside"], reverse=True)
    return dict(rows=rows, gated=gated, failed=failed)


def format_table(rows) -> str:
    hdr = (f"{'#':>2}  {'Ticker':<7}{'Price':>9}{'DCF':>9}{'Exit':>9}"
           f"{'Upside':>9}{'TV%':>6}{'Grw':>6}  {'Verdict':<16}Flags")
    lines = [hdr, "-" * len(hdr)]
    for i, r in enumerate(rows, 1):
        lines.append(
            f"{i:>2}  {r['ticker']:<7}{r['price']:>9,.2f}{r['ps']:>9,.2f}"
            f"{r['ps_exit']:>9,.2f}{r['upside']:>9.1%}"
            f"{r['tv_share']:>6.0%}{r['trailing_growth']:>6.0%}  "
            f"{r['verdict']:<16}{'; '.join(r['flags']) or '—'}")
    return "\n".join(lines)


def write_csv(rows, path):
    cols = ["ticker", "name", "price", "ps", "ps_exit", "upside",
            "upside_exit", "wacc", "tv_share", "trailing_growth", "verdict",
            "flags"]
    with open(path, "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(cols)
        for r in rows:
            wr.writerow([r[c] if c != "flags" else "; ".join(r["flags"])
                         for c in cols])


def main():
    ap = argparse.ArgumentParser(description="DCF mispricing scanner.")
    ap.add_argument("--universe", help="file with one ticker per line "
                    "(# comments ok); default: built-in large-cap list")
    ap.add_argument("--limit", type=int, help="scan only the first N names")
    ap.add_argument("--csv", help="write results CSV")
    ap.add_argument("--build-top", type=int, default=0, metavar="N",
                    help="build full live DCF workbooks for the top N "
                    "non-artifact names by |upside|")
    ap.add_argument("--no-cache", action="store_true")
    args = ap.parse_args()

    tickers = load_universe(args.universe)[:args.limit or None]
    res = scan(tickers, use_cache=not args.no_cache)
    print(f"\nMispricing scan — {len(res['rows'])} of {len(tickers)} names "
          "priced (Gordon DCF vs market)\n")
    print(format_table(res["rows"]))
    if res["gated"]:
        print(f"\nGated on FMP free tier (skipped): {', '.join(res['gated'])}")
    for tk, why in res["failed"]:
        print(f"FAILED {tk}: {why}")
    print("\nHonesty note: rank ≠ conviction. 'likely artifact' rows are the "
          "model's own limitations showing, not alpha — see scanner/README.")

    if args.csv:
        write_csv(res["rows"], args.csv)
        print(f"\nCSV: {args.csv}")

    if args.build_top:
        from dcf.model_builder import build_dcf_model
        from three_statement.assumptions import Assumptions
        clean = [r for r in res["rows"] if r["verdict"] != "likely artifact"]
        clean.sort(key=lambda r: abs(r["upside"]), reverse=True)
        for r in clean[:args.build_top]:
            data = fetch_financials(r["ticker"], n_hist=3)
            out = Path(f"{r['ticker']}_dcf.xlsx")
            build_dcf_model(data, Assumptions.derive(data), out)
            print(f"Built full model: {out}")


if __name__ == "__main__":
    main()

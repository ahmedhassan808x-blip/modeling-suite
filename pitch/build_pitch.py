"""
CLI: generate a long or short investment pitch.

    python3 -m pitch.build_pitch AAPL --direction long --peers MSFT,GOOGL,META
    python3 -m pitch.build_pitch AAPL --direction short --dcf AAPL_dcf.xlsx

Outputs: {TICKER}_{direction}_pitch.md, _memo.docx, _deck.pptx, _deck.pdf.
Reuses an existing DCF workbook when given (--dcf), otherwise builds one.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pitch.generator import generate_pitch  # noqa: E402
from pitch.report import build_outputs  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="Generate an investment pitch.")
    ap.add_argument("ticker")
    ap.add_argument("--direction", choices=["long", "short"], default="long")
    ap.add_argument("--peers", help="comma-separated peers for comps")
    ap.add_argument("--dcf", help="existing DCF workbook to cite (skips build)")
    ap.add_argument("--outdir", default=".")
    ap.add_argument("--no-cache", action="store_true")
    args = ap.parse_args()

    pitch = generate_pitch(
        args.ticker, direction=args.direction,
        peers=args.peers.split(",") if args.peers else None,
        dcf_xlsx=args.dcf, use_cache=not args.no_cache)
    outputs = build_outputs(pitch, args.outdir)
    print(f"{pitch['direction']} {args.ticker.upper()} — "
          f"thesis: {pitch['sections']['thesis_summary'][:140]}...")
    for k, p in outputs.items():
        print(f"{k}: {p}")


if __name__ == "__main__":
    main()

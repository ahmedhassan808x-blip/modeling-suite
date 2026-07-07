"""
CLI: build an accretion/dilution merger model.

    python3 -m merger.build_model MSFT AAPL                # MSFT acquires AAPL
    python3 -m merger.build_model MSFT AAPL --premium 0.30 --mix 100,0,0
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from merger.assumptions import MergerAssumptions  # noqa: E402
from merger.model_builder import (  # noqa: E402
    CHECKS_PASS_CELL, PF, build_merger_model,
)
from shared.recalc import RecalcError, recalculate  # noqa: E402
from three_statement.data_layer import fetch_financials  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="Build a merger (A/D) model.")
    ap.add_argument("acquirer")
    ap.add_argument("target")
    ap.add_argument("--premium", type=float, default=0.25)
    ap.add_argument("--mix", default="50,20,30",
                    help="stock,cash,debt percentages (default 50,20,30)")
    ap.add_argument("--synergies", type=float,
                    help="pre-tax run-rate $mm (default: 10%% target EBITDA)")
    ap.add_argument("--out")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--skip-check", action="store_true")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    mix = [float(x) / 100 for x in args.mix.split(",")]
    if len(mix) != 3 or abs(sum(mix) - 1) > 1e-6:
        ap.error(f"--mix must be three percentages summing to 100, got {args.mix}")
    m = MergerAssumptions(premium=args.premium, mix_stock=mix[0],
                          mix_cash=mix[1], mix_debt=mix[2],
                          syn_runrate=args.synergies)

    use_cache = not args.no_cache
    acq = fetch_financials(args.acquirer, n_hist=3, use_cache=use_cache)
    tgt = fetch_financials(args.target, n_hist=3, use_cache=use_cache)
    out = Path(args.out or f"{acq['ticker']}_{tgt['ticker']}_merger.xlsx")
    build_merger_model(acq, tgt, m, out)
    print(f"Built {out} — {acq['ticker']} acquires {tgt['ticker']} at "
          f"{args.premium:.0%} premium, mix {args.mix} (stock/cash/debt)")

    if args.skip_check:
        print("recalc gate SKIPPED — workbook is unverified.")
        return
    try:
        probes = [CHECKS_PASS_CELL] + \
            [f"ProForma!{c}{PF['acc_pct']}" for c in "FGHIJ"]
        res = recalculate(out, probe_cells=probes)
    except RecalcError as e:
        print(f"recalc gate unavailable: {e}", file=sys.stderr)
        sys.exit(2)
    v = res.values
    acc = " ".join(f"Y{i + 1} {v[f'ProForma!{c}{PF['acc_pct']}']:+.1%}"
                   for i, c in enumerate("FGHIJ"))
    print(res.summary() + f" | Checks: {v[CHECKS_PASS_CELL]} | "
          f"Accretion/(dilution): {acc}")
    if not res.ok or v[CHECKS_PASS_CELL] != "PASS":
        sys.exit(1)
    if args.report:
        from merger.report import build_reports
        for kind, p in build_reports(out).items():
            print(f"{kind}: {p}")


if __name__ == "__main__":
    main()

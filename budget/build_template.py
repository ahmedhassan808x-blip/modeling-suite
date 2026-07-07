"""
CLI: generate a budget vs. actual variance template.

    python3 -m budget.build_template "My Company" --year 2026
"""

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from budget.model_builder import (  # noqa: E402
    CHECKS_PASS_CELL, build_budget_template,
)
from shared.recalc import RecalcError, recalculate  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="Budget vs actual template.")
    ap.add_argument("company")
    ap.add_argument("--year", type=int, default=date.today().year)
    ap.add_argument("--out")
    ap.add_argument("--skip-check", action="store_true")
    args = ap.parse_args()

    slug = "".join(c for c in args.company if c.isalnum()) or "company"
    out = Path(args.out or f"{slug}_budget_FY{args.year}.xlsx")
    build_budget_template(args.company, args.year, out)
    print(f"Built {out} — fill the blue cells on Budget and Actuals "
          "(costs negative).")
    if args.skip_check:
        return
    try:
        res = recalculate(out, probe_cells=[CHECKS_PASS_CELL])
    except RecalcError as e:
        print(f"recalc gate unavailable: {e}", file=sys.stderr)
        sys.exit(2)
    print(res.summary() + f" | Checks: {res.values[CHECKS_PASS_CELL]}")
    if not res.ok or res.values[CHECKS_PASS_CELL] != "PASS":
        sys.exit(1)


if __name__ == "__main__":
    main()

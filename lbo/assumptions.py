"""
LBO transaction assumptions — textbook-standard seeds, every one a visible
blue input in the workbook.

Entry is seeded from the company's ACTUAL market EV/EBITDA (not a fantasy
multiple), exit is seeded flat to entry (the discipline that forces returns
to come from EBITDA growth and deleveraging, not multiple expansion), and
the capital structure defaults to 3.5x senior + 1.5x subordinated — the
classic paper-LBO stack.
"""

from dataclasses import dataclass


def _clamp(v, lo, hi, fallback):
    return v if lo <= v <= hi else fallback


@dataclass
class LBOAssumptions:
    entry_mult: float = 10.0      # EV / LTM EBITDA at entry
    exit_mult: float = 10.0       # seeded flat to entry
    fees_pct: float = 0.02        # transaction fees, % of EV
    senior_x: float = 3.5         # senior debt, x LTM EBITDA
    sub_x: float = 1.5            # subordinated debt, x LTM EBITDA
    senior_rate: float = 0.08     # on beginning balances
    sub_rate: float = 0.115
    rv_rate: float = 0.085        # revolver (funds shortfalls vs. amort)
    amort_pct: float = 0.05       # senior mandatory amort, % of original/yr

    @classmethod
    def derive(cls, data: dict) -> "LBOAssumptions":
        import sys

        isl, bsl = data["is"], data["bs"]
        ltm_ebitda = isl["ebit"][-1] + isl["dna"][-1]
        net_debt = bsl["debt"][-1] - bsl["cash"][-1]
        mkt_cap = data.get("price", 0) * data.get("shares_mm", 0)
        implied = (mkt_cap + net_debt) / ltm_ebitda if ltm_ebitda > 0 else 0.0
        # Wide sanity range: guards against broken data, NOT against
        # expensive companies — an honest seed is the market's multiple,
        # however uncomfortable for the IRR. Never substitute silently.
        mult = round(_clamp(implied, 2.0, 60.0, 10.0), 1)
        if mult != round(implied, 1):
            print(f"[lbo] {data['ticker']}: implied EV/EBITDA {implied:.1f}x "
                  f"outside sanity range — seeding {mult:.1f}x instead. "
                  "Override with --entry.", file=sys.stderr)
        return cls(entry_mult=mult, exit_mult=mult)

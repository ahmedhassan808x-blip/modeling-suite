"""
Bear / Base / Bull scenario sets for the three-statement model.

Design: the scenario toggle lives IN the workbook, not in Python. The
Scenarios sheet holds three blocks of blue per-year inputs; the Assumptions
sheet's scenario-driven rows become CHOOSE() formulas keyed off a single
selector cell. Flipping the selector recalculates the entire model live —
statements, revolver, DCF and all. No hidden multipliers: every scenario
number is a visible, editable input.

Bear/bull are seeded as fixed deltas off the base drivers (documented below,
clamped to sane ranges) — deliberately mechanical starting points the analyst
is expected to overwrite with a view.
"""

# Seed deltas vs. base (percentage points per year)
BEAR = dict(growth=-0.03, gm=-0.015, opex=+0.015, capex=+0.010)
BULL = dict(growth=+0.03, gm=+0.010, opex=-0.010, capex=0.0)

SCENARIO_DRIVERS = ("growth", "gm", "opex", "capex")
SCENARIO_NAMES = ("Bear", "Base", "Bull")


def _clamped(vals, delta, lo, hi):
    return [max(lo, min(hi, v + delta)) for v in vals]


def seed_scenarios(a) -> dict:
    """Build {scenario: {driver: [per-year values]}} from base assumptions."""
    base = dict(growth=a.rev_growth, gm=a.gross_margin, opex=a.opex_pct,
                capex=a.capex_pct)
    bounds = dict(growth=(-0.50, 1.0), gm=(0.0, 1.0), opex=(0.0, 0.95),
                  capex=(0.0, 0.60))
    out = {"Base": {k: list(v) for k, v in base.items()}}
    for name, deltas in (("Bear", BEAR), ("Bull", BULL)):
        out[name] = {k: _clamped(base[k], deltas[k], *bounds[k])
                     for k in SCENARIO_DRIVERS}
    return out

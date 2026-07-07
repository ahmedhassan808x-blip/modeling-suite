"""
Merger model assumptions — banker-standard defaults, all blue inputs.

Base-case discipline (approved defaults):
  - COST synergies only; revenue synergies are excluded from the base case
    (assume them and you can justify any deal).
  - Synergy phase-in 50% / 75% / 100% over years 1-3.
  - 25% acquisition premium over the target's market price.
  - Consideration mix 50% stock / 20% balance-sheet cash / 30% new debt,
    fees financed with debt.
"""

from dataclasses import dataclass, field


@dataclass
class MergerAssumptions:
    premium: float = 0.25
    mix_stock: float = 0.50
    mix_cash: float = 0.20
    mix_debt: float = 0.30
    fees_pct: float = 0.015          # % of offer value, debt-financed
    debt_rate: float = 0.065         # on new acquisition debt
    cash_yield: float = 0.03         # foregone yield on cash used
    intang_pct: float = 0.30         # of premium-over-book to intangibles
    amort_years: int = 10            # straight-line intangible amortization
    syn_runrate: float | None = None  # pre-tax $mm; None -> seeded below
    phase_in: tuple = (0.50, 0.75, 1.0, 1.0, 1.0)

    def seed_synergies(self, target_data: dict) -> float:
        """Placeholder seed: 10% of target LTM EBITDA — deal-specific
        judgment the analyst must overwrite; labeled as such in the sheet."""
        if self.syn_runrate is not None:
            return self.syn_runrate
        isl = target_data["is"]
        return round(0.10 * (isl["ebit"][-1] + isl["dna"][-1]), 1)

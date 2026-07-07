# Merger Model (M&A — Accretion / Dilution)

One command → a **live merger consequences workbook**: offer terms and exchange ratio, sources & uses across a stock/cash/debt mix, purchase price allocation basics, synergies with phase-in, pro forma combined earnings, and per-year EPS accretion/(dilution) with a synergies × premium sensitivity.

```bash
python3 -m merger.build_model MSFT ADBE --report
python3 -m merger.build_model MSFT ADBE --premium 0.30 --mix 100,0,0 --synergies 800
```

Output: `MSFT_ADBE_merger.xlsx` with five tabs:

| Tab | Contents |
|---|---|
| **Acquirer / Target** | Compact 3yr-actual + 5yr driver-based earnings forecasts to EPS — deliberately simpler than the full three-statement build (a merger consequences model needs clean EPS paths, not revolver mechanics) |
| **Deal** | Premium → offer per share → exchange ratio; consideration mix (blue); fees (debt-financed); incremental financing cost; PPA: intangibles (amortized) vs goodwill (not) |
| **ProForma** | Combined NI ± after-tax adjustments → pro forma EPS vs standalone; **breakeven synergies per year**; live synergies × premium sensitivity |
| **ChecksMA** | Mix = 100%, sources = uses, goodwill ≥ 0, and Year-1 accretion **independently re-derived** in the sensitivity grid must equal the ProForma value |

## Base-case discipline (approved defaults, all blue inputs)

- **Cost synergies only** — revenue synergies excluded (assume them and any deal "works"). Seed is a labeled placeholder (10% of target EBITDA) that the analyst must overwrite.
- Synergy phase-in 50% / 75% / 100% over years 1–3.
- 25% premium; consideration 50% stock / 20% cash / 30% new debt.

## Design decisions (interview talking points)

- **The P/E rule is a test, not a footnote**: all-stock, no frictions — buying a lower-P/E target must accrete and a higher-P/E target must dilute. The suite asserts both directions against the recalculated workbook.
- **Breakeven synergies is self-consistent by test**: plug the model's own breakeven number into the synergy input and Year-1 accretion recalculates to exactly zero.
- **The sensitivity grid re-derives the whole chain** (offer → shares → financing → amortization → pro forma EPS) independently of the ProForma sheet — and the checks assert the center cell matches. Two implementations agreeing is how you catch formula drift.
- **Negative goodwill fails the checks on purpose** — an offer below book value is almost always an input error (and the test suite hit this honestly: a no-premium offer for a below-book stock was correctly rejected).

## Known limitations

- New debt carried flat (no paydown path); mildly conservative in later years.
- PPA basics only: no deferred-tax liabilities on write-ups, no PP&E step-up.
- EPS accretion is a screening lens, not value creation — accretive deals can destroy value and vice versa.
- No scenario toggle in this workbook (the compact company forecasts don't carry the Scenarios sheet).

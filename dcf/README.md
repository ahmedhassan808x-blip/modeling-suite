# DCF Model (linked to the Three-Statement Model)

One command → a **live DCF valuation workbook built on top of a fully linked three-statement model**: FCFF discounting with a WACC build-up, Gordon *and* exit-multiple terminal values, a WACC × growth sensitivity grid, trading comps, and a football-field summary chart.

```bash
python3 -m dcf.build_model AAPL --peers MSFT,GOOGL,META
```

Output: `AAPL_dcf.xlsx` = the full three-statement workbook (Assumptions with scenario toggle, Scenarios, IS, BS, CF, Debt, Checks) plus:

| Tab | Contents |
|---|---|
| **DCF** | UFCF pulled **live from the statement forecast** (EBIT, D&A, capex, ΔNWC as green links) → NOPAT → discounting; WACC build-up; Gordon TV + exit-multiple TV cross-check; 5×5 WACC × g sensitivity in $/share |
| **Comps** | Peer LTM multiples (median/quartiles) applied to the target's modeled last-reported metrics |
| **Summary** | Football field: 52-week range, three comps ranges, DCF sensitivity min–max, both DCF base cases, current price |

## What "linked" buys you (vs. the analyst-toolkit version)

The original valuation-engine DCF was a simplified standalone build (revenue × margin drivers straight to FCF). Here, UFCF is assembled from statements that must **balance**: ΔNWC comes from actual working-capital line movements, capex rolls PP&E, and the same Assumptions sheet drives everything. Two practical consequences:

- **Flip the scenario toggle (Assumptions B3: 1=Bear, 2=Base, 3=Bull) and the DCF reprices live** — statements, revolver, UFCF, implied value per share, sensitivity grid, football field, all of it. Scenario inputs are visible per-year numbers on the Scenarios sheet, not hidden multipliers.
- Net debt in the EV-to-equity bridge is a green link to the modeled balance sheet, not a hardcoded snapshot.

## Design decisions (interview talking points)

- **Ported, not rewritten.** WACC build-up, Gordon TV with the g < WACC discipline, sensitivity grid, comps quartiles, and the football field carry over from the earlier engine — plus two items from its own v2 wishlist: exit-multiple TV alongside Gordon (bankers show both), and per-share ranges everywhere because a valuation is an argument, not a number.
- **Unlevered means unlevered**: taxes in the DCF are the driver rate applied to EBIT, not the levered effective tax line — interest belongs in the financing decision, not the asset value.
- **Peers that fail are skipped loudly** with the specific reason (the old version swallowed exceptions silently — fixed to match the repo standard). If *all* peers fail, the build refuses to produce an empty comps tab.

## Known limitations

- The structural conservatism of a 5-year explicit DCF is inherited and real: on premium mega-caps (AAPL: Gordon ≈ $119/sh vs ≈ $313 market at build time; exit-multiple @ peer-median 18x ≈ $172) the model reads "expensive" almost by construction. This is documented honesty, not a signal — and exactly the artifact class the Phase 6 mispricing scanner must flag rather than report as alpha.
- Risk-free rate is a labeled blue input (default 4.25%), not fetched live — update it to the current 10Y when using the model.
- No mid-year convention or stub periods (matching the original); single currency.
- Exit-multiple seed is the peer median EV/EBITDA (10.0x fallback with no peers) — a starting point, not a view.

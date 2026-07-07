# LBO Model (linked to the Three-Statement Model)

One command → a **live LBO workbook on top of a fully linked three-statement forecast**: sources & uses, a three-tranche debt schedule (revolver + senior + subordinated) with mandatory amortization and a full cash sweep, IRR/MOIC from actual flows, a value-creation bridge, and sensitivity tables.

```bash
python3 -m lbo.build_model AAPL --report
python3 -m lbo.build_model AAPL --entry 12 --senior 4.0 --sub 1.5   # overrides
```

Output: `AAPL_lbo.xlsx` = the full three-statement workbook plus:

| Tab | Contents |
|---|---|
| **Deal** | Entry multiple (seeded from the company's **actual market EV/EBITDA** — no fantasy entry), tranche sizing (3.5x senior + 1.5x sub default), pricing, fees, exit multiple (seeded flat); Sources & Uses |
| **LBO** | FCF-for-debt-service build with operating lines as green links into the statement forecast; revolver → senior → sub sweep waterfall; interest on beginning balances |
| **Returns** | Exit EV → equity, `IRR()` over the sponsor flows, MOIC, value-creation bridge (EBITDA growth / multiple / deleveraging / fees), exit-multiple × exit-year sensitivity |
| **ChecksLBO** | Sources = uses; all balances ≥ 0; IRR from flows == closed-form MOIC^(1/5)−1 |

## Design decisions (interview talking points)

- **The scenario toggle reprices the IRR.** The LBO's operating engine is the linked three-statement forecast, so flipping Assumptions B3 (Bear/Base/Bull) re-runs everything: AAPL at its market multiple goes 0.8% / 6.8% / 11.7% IRR across scenarios, all check-verified.
- **The revolver exists because the bear case demanded it.** A fixed mandatory amortization can exceed FCF in weak years; the first version of this model let cash go negative and the integrity checks caught it. Real deals fund that gap with a revolver — so does this model. Persistent revolver usage is the visible signal that a structure doesn't work.
- **Honest entry, honest exit.** Entry seeds from the actual market multiple (a 32x AAPL entry produces a 6.8% IRR — the model telling you premium mega-caps don't work as LBOs, which is the correct answer). Exit seeds flat to entry, forcing returns to come from EBITDA growth and deleveraging, not assumed multiple expansion.
- **The leverage sensitivity is honest about what a formula can't do.** Each leverage level implies a different sweep path, which no single cell formula can re-solve — so the in-workbook grid is exit multiple × exit year (fully live), and the report's leverage × exit table is built by genuinely re-running the model per leverage point. Structures that break report "breaks", not a number.
- **IRR is cross-checked**: with a single exit flow, IRR must equal MOIC^(1/5)−1 exactly — a live check formula the recalc gate asserts.

## Known limitations

- Single exit flow — no dividend recaps or interim distributions.
- Interest on beginning-of-period balances; no interest income on accumulated cash (both mildly conservative, both suite-wide conventions for recalc-verifiability).
- No NOL carryforward (loss years get zero tax benefit, not a credit).
- No management rollover/options pool, monitoring fees, or minimum operating cash.
- Purchase price is EV-based (equity + net-debt refinance); no premium-over-market input — adjust the entry multiple instead.

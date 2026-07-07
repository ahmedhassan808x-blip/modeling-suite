# Budget Model (Budget vs. Actual Variance Template)

A **fill-in workbook** (per spec: template you populate, not auto-generated numbers): monthly Budget and Actuals grids, and a fully formula-driven Variance sheet with favorability, materiality flags, and a commentary column — the close-package pattern from audit practice.

```bash
python3 -m budget.build_template "My Company" --year 2026
```

Output: `MyCompany_budget_FY2026.xlsx` with four tabs:

| Tab | Contents |
|---|---|
| **Budget / Actuals** | Identical monthly P&L grids ($000s): revenue lines, COGS, opex categories → EBITDA. Blue input cells only; subtotals and margins are formulas |
| **Variance** | 100% formulas: actual − budget by month and full year, % of budget, favorable/unfavorable, **REVIEW flag** when a variance breaches BOTH the % and $ materiality thresholds (blue inputs, default 5% and $50k), and a commentary column for flagged lines |
| **ChecksB** | The variance grid re-derived two independent ways must agree; FY totals = sum of months; PASS cell asserted by the recalc gate |

## Design decisions (interview talking points)

- **One sign convention, one favorability rule.** Costs are entered as negatives, so `variance = actual − budget` is favorable when ≥ 0 on *every* line — beating revenue is positive, underspending a negative cost line is also positive. No per-line exception logic to get wrong.
- **Materiality needs both gates.** A variance flags REVIEW only when it breaches the % threshold *and* the $ threshold — a 40% variance on a $10 line and a 1% variance on a huge line both stay quiet, exactly as an auditor would scope it.
- **Commentary lives next to the flag.** Every flagged variance gets a blank blue cell demanding a sentence — variance analysis isn't done when the number is computed, it's done when it's explained.
- The empty template must recalculate clean (all ratio formulas are zero-guarded) — verified by the recalc gate before you type a single number.

## Known limitations

- Fixed P&L skeleton (two revenue lines, four opex categories) — relabel rows freely, but adding rows means updating the subtotal ranges.
- Single year, monthly granularity; no YTD-vs-full-year phasing view yet.
- No cash flow / balance sheet budget — P&L only by design.

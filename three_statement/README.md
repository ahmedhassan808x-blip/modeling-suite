# Three-Statement Model

One command → a **fully linked, live Excel three-statement model** for any US-listed company: Income Statement, Balance Sheet, and Cash Flow Statement, with a driver-based 5-year forecast, a debt schedule with a revolver/cash-sweep plug, and an integrity-check sheet that proves the balance sheet balances in every year.

```bash
python3 -m three_statement.build_model AAPL
```

Output: `AAPL_3stmt.xlsx` with six tabs:

| Tab | Contents |
|---|---|
| **Assumptions** | Every forecast driver as a blue, per-year input — seeded from the company's own historicals, yellow-flagged for challenge. Historical columns show the same ratios as memo formulas so you can see what the seed was based on. |
| **IS** | 3 years actuals (blue, tied to filings) + 5 years forecast (formulas). Revenue growth → gross margin → opex → EBITDA → D&A → EBIT → interest (from Debt) → taxes → net income. |
| **BS** | Working capital from days ratios (DSO/DIO/DPO), PP&E rolled from capex/D&A, retained earnings rolled from NI less dividends, cash linked from CF, debt linked from the Debt schedule. |
| **CF** | Forecast build: NI + D&A − ΔNWC − capex − dividends ± debt draws. Ending cash **is** the balance sheet cash line. |
| **Debt** | LTD schedule + revolver: draws when cash would fall below the minimum target, sweeps back down with excess cash. Interest on beginning-of-period balances. |
| **Checks** | TA − TL&E per year, revolver ≥ 0, cash ≥ minimum. B9 must read PASS — asserted by the automated test gate. |

## Conventions

- **Blue = hardcoded input, black = formula, green = cross-sheet link.** Enforced in code: the shared Excel writer auto-colors any formula containing a sheet reference green, so the convention can't drift.
- **Every forecast cell is a live Excel formula** — change any assumption and the whole model recalculates, revolver and all.
- Negatives in parentheses, units ($mm) declared, sources and build date on every sheet.
- Delivered with **zero formula errors**, verified by genuine recalculation in headless LibreOffice — not asserted, tested (`tests/test_model.py`).

## Setup

```bash
pip3 install -r ../requirements.txt        # openpyxl, requests, pytest
cp ../.env.example ../.env                 # add your FMP_API_KEY
python3 -m three_statement.build_model MSFT
```

LibreOffice is required for the recalc gate (the build runs it automatically; `--skip-check` bypasses it, unverified).

## Design decisions (interview talking points)

- **Interest on beginning-of-period balances, not average balances.** Average-balance interest creates a circular reference (interest → net income → cash → revolver → interest). Circularity requires Excel's iterative calc, can't be verified by an automated recalculation engine, and is the #1 way student models silently break. Beginning-balance interest is a legitimate convention used in practice, and it makes the model *provably* correct. The tradeoff — slightly understated interest in years balances grow — is documented, not hidden.
- **Historicals tie exactly by construction.** The balance sheet is decomposed into modeled lines plus explicit "Other" plug lines computed from reported subtotals (e.g. other current assets = reported TCA − cash − AR − inventory). Every historical column balances before a single forecast formula exists — so if a forecast year doesn't balance, the error is provably in the forecast logic.
- **Working capital from days ratios (DSO/DIO/DPO)**, not flat % of revenue — it's how operators and lenders think about the cash cycle, and it handles zero-inventory businesses naturally.
- **The revolver is the plug, and it's a real revolver** — draw to a minimum cash target, sweep excess to repay — not an abstract "plug" line. The stress test in the suite deliberately starves the model of cash and asserts the revolver draws *and* the balance sheet still balances.
- **The tool builds the model; the analyst owns the assumptions.** Every driver is seeded from the company's own history (with clamps so one weird year can't seed a nonsense forecast), then exposed as a visible input. Nothing judgment-based is buried in a formula.

## Known limitations

- **No share buybacks or issuance** — payout is dividends only, so cash-rich compounders (AAPL, MSFT) accumulate unrealistically large cash piles in later years, and interest income on that cash flatters late-year margins. Visible, documented, and the next natural extension.
- **FMP free tier restricts the symbol universe** — some large caps (e.g. PG) return HTTP 402 "premium symbol." The client fails loudly with the exact reason rather than substituting data.
- D&A embedded in reported COGS/opex is not restated: "Opex ex-D&A" is derived as Gross profit − EBITDA, so the gross margin line is as-reported while the operating build stays internally consistent.
- Single debt tranche + revolver; no scheduled amortization by default (editable input row); no minority-interest P&L allocation; other BS lines held flat.
- Tax is a flat effective rate on pre-tax income (loss years produce a tax benefit; no NOL tracking).

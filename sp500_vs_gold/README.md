# S&P 500 vs. Gold — Comparative Brief

A re-runnable, dated, sourced answer to one question: *given current conditions, which looks more reasonably positioned right now — US equities or gold — and why?* A strategist-note-style brief, not a backtest, not a prediction, and stamped on every artifact: **analysis to inform thinking, not a recommendation**.

```bash
python3 -m sp500_vs_gold.build_brief        # → .md, .xlsx, .docx, .pdf, dated today
```
Or the dashboard page: **⚖️ S&P 500 vs Gold → "Build today's brief."** Each run reflects that day's data — quotes always bypass the cache; slow-moving series use the 24h cache (`--no-cache` overrides).

## How each layer sources its data (and the honest gaps)

| Layer | Source | Notes |
|---|---|---|
| S&P level, gold spot, EURUSD | FMP quotes, fetched fresh every run | ✅ free |
| YTD/1y/5y returns | FMP daily closes (SPY as the S&P proxy) | ⚠️ **price** returns — excludes dividends, stated in the output |
| Treasury curve, CPI (YoY *and* index), fed funds | FMP `treasury-rates`, `economic-indicators` | ✅ free; the CPI **index series** lets us deflate gold to today's dollars over the 5-yr window (longer real history isn't in free data) |
| DXY | ❌ FMP-gated (402) | EURUSD shown as the stated proxy **plus** the actual DXY level web-sourced with citation |
| Trailing/forward P/E, CAPE, dividend yield, TIPS real yield, rate expectations, flows, strategist views | **Web research layer**: Claude with the server-side web-search tool | sourced-or-nothing: any figure returned without a source is discarded; anything not found appears as an explicit *"not obtained this run"* row |

**Derived metrics are computed by code, not the LLM**: real yield ≈ 10Y − CPI YoY (labeled approximation, shown alongside the market TIPS figure when sourced), earnings yield = 1/P/E, ERP proxy = earnings yield − 10Y. In the Excel export these are **live formulas** over blue sourced inputs, recalc-gate tested.

## How to read the "AI Summary & Reasoned View" responsibly

The synthesis model sees only the retrieved facts pack — not its training priors — and is required to: state a lean (or "roughly balanced" if genuinely so) tied to specific figures; include a **"what would change this view"** section with observable triggers; and avoid hedging into meaninglessness. Treat it as one disciplined input into your own thinking: the facts table above it is the part you can verify line-by-line; the view is an argument built on those facts, and arguments can be wrong even when well-grounded. Markets can move against sound reasoning for a long time.

## Known limitations

- The macro backdrop paragraphs are templated prose with live numbers — deliberately deterministic so explanation can't drift from data, at the cost of reading a little sameish run-to-run.
- Web-sourced figures are only as good as the page they came from; sources and dates are printed precisely so you can judge.
- No positioning data beyond what public flow reporting surfaces; no options/vol signals; single-currency (USD) perspective.
- Two Claude calls per run (researcher with ~8 web searches + synthesizer): expect ~1–2 minutes and nontrivial token usage.
- **The lean can vary between runs when the evidence is genuinely close** — back-to-back runs on the same day have produced "Gold" and then "Roughly balanced" as search results and emphasis shifted. That instability is itself information: a robust one-sided read shouldn't flip.

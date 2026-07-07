# Mispricing Scanner

Runs the suite's DCF across a configurable universe and ranks names by divergence between model value and market price — with an honesty layer that flags when a "mispricing" is more likely a modeling artifact than a signal.

```bash
python3 -m scanner.scan                                # default ~28-name universe
python3 -m scanner.scan --universe my.txt --csv out.csv --build-top 2
streamlit run scanner/app.py                           # ranked dashboard
```

## How it stays fast AND honest

Building and recalculating a live workbook per ticker would be slow and pointless for screening, so the scanner uses a **pure-Python mirror of the Excel DCF** (`engine.py`) — same driver derivation, same 4-decimal input rounding, same formulas. The mirror is only trustworthy because it's **agreement-tested**: the suite builds the real workbook, recalculates it in LibreOffice, and asserts the mirror reproduces the implied value per share to within 1e-6 relative. Fast path for ranking; `--build-top N` (or `python3 -m dcf.build_model TICKER --report`) produces the full live workbook for names worth real work.

## The artifact flags (rank ≠ conviction)

Each row carries the reasons its divergence may be the model's own limitations showing — mirroring the documented known-limitations of the valuation engine:

| Flag | Why it demotes the signal |
|---|---|
| hypergrowth (trailing ≥20%) | a 5-yr DCF fading to terminal growth structurally understates compounders — the known limitation inherited from the original valuation engine |
| terminal-value dominant (>80% of EV) | the "mispricing" is mostly one unknowable assumption |
| negative forecast FCF | Gordon math on negative/thin FCF is noise |
| extreme divergence (>60%) | 60% free money is more likely a broken input than alpha |
| data gaps | D&A or capex defaulted — the loud-logging data layer said so |

Verdict: no flags → *worth a look*; one → *caution*; two+ → *likely artifact*. A live scan of the default universe behaves as it should: NVDA (−80% "downside", 65% trailing growth) self-classifies as an artifact, while the clean readings surface names like ADBE (+27%, no flags) for actual diligence.

## Universe & quota

Default: ~28 liquid US large caps. The binding constraint is the FMP free tier: **250 requests/day AND a gated symbol set** — a scan costs ~4 requests per uncached name (24h disk cache), and gated symbols (11 of the default 28 at last run) are reported by name, never silently dropped. A materially broader universe is the paid-FMP conversation, flagged per project policy.

## Known limitations

- The scanner inherits every DCF limitation (see `dcf/README.md`); the flags exist precisely because of that.
- Gordon-DCF ranking is one lens: no comps-based cross-check in the ranking yet (peer selection is a judgment, and auto-selecting peers universe-wide would be false precision).
- Free-tier symbol gating skews the scannable universe toward mega-cap tech.

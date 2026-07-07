# News & Macro Context Layer

Given a ticker (or commodity), retrieves recent headlines and current macro prints, then has Claude synthesize **how these developments plausibly affect the asset's price** — grounded in the retrieved material, cited line-by-line, and labeled AI-generated.

```bash
python3 -m news.context AAPL              # → AAPL_context.md
python3 -m news.context --commodity GCUSD # gold
```

## Data sources (free-tier reality, probed honestly)

| Need | Source | Status |
|---|---|---|
| Ticker headlines (local) | yfinance `Ticker.news` | ✅ works locally; blocked on cloud hosts (suite-wide known caveat) |
| Ticker headlines (cloud) | FMP `fmp-articles` filtered by ticker tag | ✅ free; thinner coverage |
| Ticker news endpoints | FMP `news/stock`, `press-releases` | ❌ 402-gated on free tier — **documented, not scraped around** |
| Treasury curve | FMP `treasury-rates` | ✅ free |
| CPI / fed funds / unemployment / real GDP | FMP `economic-indicators` | ✅ free |
| Commodities | FMP `quote` (GCUSD etc.) | ⚠️ partially free — gold works, several energy symbols are gated; gated symbols fail loudly with the reason |

The active headline source is always stated in the output; empty retrievals are warned about, never papered over.

## Grounding rules (enforced in the prompt, tested)

- The model receives ONLY numbered headlines `[H1]…` and dated macro prints `[M:federalFunds]…` and must cite one for every claim.
- Price-impact statements use hypothesis language with confirm/refute conditions — mechanisms, not predictions.
- A mandatory **Confidence & Gaps** section states what the material cannot support.
- With nothing retrieved, `synthesize_context` raises rather than letting the model freewheel.
- Every artifact opens with an **AI-generated analysis** label naming the model, and appends the retrieved material verbatim for verification.

## Known limitations

- Free-tier headline coverage is the binding constraint: yfinance depth varies by ticker, and the FMP editorial fallback covers fewer names. If this layer becomes central to your workflow, a paid news API (FMP paid tier, or a dedicated provider) is the honest upgrade path — flagged per project policy rather than built on scrapers.
- Macro prints are point-in-time levels, not full history; no revisions handling.
- The synthesis is only as fresh as the retrieval — headline staleness is called out in the Gaps section.

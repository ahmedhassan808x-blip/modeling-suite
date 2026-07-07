# Investment Pitch Generator

Given a ticker, generates a structured **long or short pitch** — thesis, catalysts, valuation support, key risks, and "what would change my mind" — as a markdown memo, Word memo, branded deck, and PDF.

```bash
python3 -m pitch.build_pitch AAPL --direction short --dcf AAPL_dcf.xlsx
python3 -m pitch.build_pitch NVDA --direction long --peers AMD,AVGO
```

## The grounding architecture (the point of this module)

1. **Facts are assembled programmatically.** The DCF workbook is built (or an existing one reused via `--dcf`), recalculated in LibreOffice, and its outputs extracted — plus bear/base/bull re-runs of the full linked model, headlines from the news layer, and macro prints.
2. **The LLM argues, it does not compute.** Claude receives only that facts pack and returns structured JSON (thesis, catalysts, risks, change-my-mind, weakest link). It is instructed to cite headlines/macro ids and to address head-on any model output that cuts *against* the requested direction.
3. **Numbers render from the extraction, never from the model.** The valuation table, scenario table and football field on every artifact come straight from the recalculated workbook, so a hallucinated figure cannot reach the page.

Every artifact is labeled **AI-generated analysis — research thesis, not an order**.

## Long vs. short

The short pitch is not a negated long: the same facts pack is reframed around overvaluation, deteriorating fundamentals and negative catalysts, and the prompt demands the bear articulate what the market is getting wrong — plus a mandatory "weakest link" naming the pitch's most fragile assumption. (On AAPL, the generator correctly identified that the short case leans on a structurally conservative DCF and that "the valuation gap may never close within an investable horizon" — exactly the intellectual honesty the suite requires.)

## Design decisions (interview talking points)

- **"What would change my mind" is a required section** — items must be specific and observable, which is what separates a thesis from a narrative.
- **Scenario numbers are real re-runs**, not adjectives: the bear/base/bull DCF values in the memo come from flipping the in-workbook toggle and recalculating the full linked model.
- **The model is forced to argue against itself** in `risks` — the best case against the pitch, in the same document.

## Known limitations

- Pitch quality is bounded by headline coverage (see the news layer README) — thin news means catalysts skew structural rather than event-driven.
- One LLM call per pitch (~2,500 tokens); output varies run to run. The facts pack does not — regenerate freely.
- Defaults to `claude-sonnet-5`; override with `CLAUDE_MODEL`.

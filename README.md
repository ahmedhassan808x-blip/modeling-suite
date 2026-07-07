# Modeling Suite

**🎯 Open the live web app: https://ahmedhassan808x-blip-modeling-suite-scannerapp-zyfmku.streamlit.app** — mispricing scanner, plus pages to build any model (3-statement / DCF / LBO / merger) in the browser, pull news & macro context, generate long/short pitches, and download the budget template.

A financial modeling and research platform: live Excel models (three-statement, DCF, LBO, and more), a presentation/export layer, live market data with AI-assisted context, an investment pitch generator, and a mispricing scanner. Companion project to [analyst-toolkit](../analyst-toolkit) — built standalone first, designed to plug into the same Streamlit dashboard later.

Every model this suite produces is a **live Excel workbook** — formulas, not pasted values — following the industry color convention (blue = input, black = formula, green = cross-sheet link) and verified with **zero formula errors** by genuine recalculation in headless LibreOffice before being considered done.

## Status

| Phase | Contents | Status |
|---|---|---|
| 1 | Shared infrastructure (FMP client + cache, Excel writer, recalc gate) + **Three-Statement Model** | ✅ done |
| 2 | **DCF** (ported from analyst-toolkit, linked to the 3-statement) + scenario toggles (bear/base/bull) | ✅ done |
| 3 | Presentation & export layer (pptx/docx/pdf, navy & steel palette) | ✅ done |
| 4 | **LBO Model** (revolver + senior + sub, cash sweep, IRR/MOIC, returns bridge) | ✅ done |
| 5 | News/macro context layer + **Investment Pitch Generator** (long & short) | ✅ done |
| 6 | **Mispricing Scanner** (Python DCF mirror, artifact flags, ranked CLI + Streamlit) | ✅ done |
| 7 | **Merger Model** (accretion/dilution, PPA, synergies × premium) + **Budget Model** (fill-in variance template) | ✅ done |
| 8 | IPO / Consolidation models, dashboard integration (stretch) | — |

## Layout

```
shared/            fmp_client.py (stable API, 24h disk cache), excel_utils.py
                   (color-convention-enforcing writer), recalc.py (LibreOffice gate),
                   theme.py + charts.py (navy & steel, every chart defined once),
                   exports/ (pptx deck, docx memo, PDF via LibreOffice)
three_statement/   the foundation model (+ bear/base/bull scenario toggle)
dcf/               DCF + comps + football field, linked to the 3-statement
lbo/               LBO: sources & uses, 3-tranche debt schedule, IRR/MOIC
news/              headlines (yfinance local / FMP cloud) + macro + grounded AI synthesis
pitch/             long/short pitch generator (md/docx/pptx/pdf, AI-labeled)
scanner/           mispricing scanner: agreement-tested DCF mirror + artifact flags
merger/            M&A accretion/dilution: deal terms, PPA, pro forma EPS
budget/            budget vs. actual variance template (fill-in workbook)
tests/             offline suite on synthetic fixtures + `-m live` FMP/LLM tests
```

Every model ships in four formats: the live **.xlsx** model, a branded **.pptx** deck, a **.docx** memo, and a **.pdf** of the deck — add `--report` to any build command, or run reports on an existing workbook:

```bash
python3 -m dcf.build_model AAPL --peers MSFT,GOOGL,META --report
python3 -m three_statement.report AAPL_3stmt.xlsx   # from an existing workbook
```

Deck and memo numbers are extracted from the **recalculated workbook** (including re-running the scenario toggle per case), so presentation and model can never disagree.

Packages are `snake_case` (not the kebab-case used in analyst-toolkit) because models import the shared infrastructure — kebab-case directories aren't importable.

## Setup

```bash
pip3 install -r requirements.txt
cp .env.example .env            # add FMP_API_KEY
python3 -m three_statement.build_model AAPL
python3 -m pytest tests/ -m "not live"     # offline suite, recalc gate included
```

Requires LibreOffice for the recalc verification gate (`brew install --cask libreoffice`, or the direct download).

## Deploying the scanner web app (Streamlit Community Cloud)

The scanner runs cloud-natively (it uses the FMP stable API, no LibreOffice needed). To deploy or redeploy:

1. [One-click deploy](https://share.streamlit.io/deploy?repository=ahmedhassan808x-blip/modeling-suite&branch=main&mainModule=scanner/app.py) (sign in with GitHub). Main module: `scanner/app.py` — the extra tool pages under `scanner/pages/` are picked up automatically, and `packages.txt` installs LibreOffice so the recalc gate and PDF decks work on the cloud.
2. In the app's **Settings → Secrets**, add `FMP_API_KEY = "your_key"` (required) and `ANTHROPIC_API_KEY = "your_key"` (enables the news-synthesis and pitch pages). The app reads `st.secrets` and falls back to `.env` locally.

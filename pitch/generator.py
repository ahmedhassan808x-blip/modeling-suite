"""
Investment pitch generator — long OR short, same machinery.

Grounding architecture (the intellectual-honesty contract):
  1. FACTS are assembled programmatically: the DCF workbook is built (or
     reused) and its RECALCULATED outputs extracted; fundamentals come from
     the modeled statements; headlines and macro prints from the news layer.
  2. The LLM receives ONLY that facts pack and returns structured JSON
     (thesis, catalysts, risks, what-would-change-my-mind, weakest link).
     It is asked to argue the requested direction honestly — including
     acknowledging when the model outputs cut AGAINST the thesis.
  3. Rendering inserts all financial figures from the extraction, not from
     the LLM. Every artifact is labeled AI-generated.

The short pitch is not a negated long pitch: the prompt reframes the same
facts around overvaluation, deteriorating fundamentals and negative
catalysts, and demands the bear articulate what the market is getting wrong.
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dcf.model_builder import build_dcf_model  # noqa: E402
from dcf.report import extract_dcf  # noqa: E402
from news.data_layer import get_headlines, get_macro  # noqa: E402
from news.synthesis import format_headlines, format_macro  # noqa: E402
from shared.llm import active_model, ask_json  # noqa: E402
from three_statement.assumptions import Assumptions  # noqa: E402
from three_statement.data_layer import fetch_financials  # noqa: E402
from three_statement.report import N_HIST, scenario_runs  # noqa: E402
from dcf.model_builder import D  # noqa: E402

REQUIRED_KEYS = ("thesis_summary", "catalysts", "valuation_take", "risks",
                 "change_my_mind", "weakest_link")

SYSTEM = """You are a buy-side analyst writing an investment pitch for an
internal investment committee. Non-negotiable rules:
- Use ONLY the facts pack provided. Never invent numbers, events, or claims.
  Reference figures exactly as given.
- Argue the requested direction with conviction where the facts support it —
  and say plainly where they don't. If the valuation model output cuts
  against the thesis, address it head-on (e.g. why the model may be
  structurally conservative, or why it should be believed).
- Catalysts must be concrete and tied to the provided headlines or macro
  prints where possible (cite [H2], [M:federalFunds]); otherwise label them
  as structural rather than news-driven.
- "What would change my mind" items must be specific and observable.
- Return ONLY a valid JSON object, no code fences, no prose outside JSON."""

PROMPT = """Direction: {direction} {ticker} ({name})

=== FACTS PACK (all figures from a recalculated, integrity-checked model) ===

Fundamentals (modeled from filings, $mm):
{fundamentals}

Valuation model outputs:
{valuation}

Scenario re-runs of the full linked model:
{scenarios}

Headlines (source: {news_source}):
{headlines}

Macro prints:
{macro}

=== TASK ===
Write the {direction} pitch as JSON with exactly these keys:
- "thesis_summary": 2-3 sentences. The core argument.
- "catalysts": list of 3-4 objects {{"title": str, "why": str (1-2
  sentences, cited where possible)}}.
- "valuation_take": 3-5 sentences on what the DCF/comps outputs say for
  this thesis, referencing the given figures — including honestly where
  they cut against it.
- "risks": list of 3-4 objects {{"title": str, "why": str}} — the best
  arguments AGAINST this pitch.
- "change_my_mind": list of 3 specific, observable developments that would
  invalidate the thesis.
- "weakest_link": 1-2 sentences: the single most fragile assumption in
  this pitch."""


def gather_facts(ticker, peers=None, dcf_xlsx=None, workdir=None,
                 use_cache=True):
    """Build (or reuse) the DCF workbook and assemble the facts pack."""
    data = fetch_financials(ticker, n_hist=3, use_cache=use_cache)
    if dcf_xlsx and Path(dcf_xlsx).exists():
        xlsx = Path(dcf_xlsx)
    else:
        workdir = Path(workdir or tempfile.mkdtemp())
        xlsx = workdir / f"{data['ticker']}_dcf.xlsx"
        peer_data = None
        if peers:
            from dcf.data_layer import get_peer_multiples
            peer_data = get_peer_multiples(peers, use_cache=use_cache)
        build_dcf_model(data, Assumptions.derive(data), xlsx, peers=peer_data)
    d = extract_dcf(xlsx)
    scen = scenario_runs(xlsx, extra_probes=[f"DCF!B{D['ps']}"])
    headlines = get_headlines(ticker, use_cache=use_cache)
    macro = get_macro(use_cache=use_cache)
    return dict(data=data, xlsx=xlsx, dcf=d, scen=scen, headlines=headlines,
                macro=macro)


def _fundamentals_text(d):
    n = N_HIST
    rev, ni, m = d["revenue"], d["ni"], d["ebitda_m"]
    yrs = d["years"]
    return (f"Revenue {yrs[0]}–{yrs[n - 1]}: "
            + " → ".join(f"${x:,.0f}" for x in rev[:n])
            + f"; forecast {yrs[-1]}: ${rev[-1]:,.0f}\n"
            f"EBITDA margin: {m[n - 1]:.1%} last actual, {m[-1]:.1%} "
            f"terminal forecast\n"
            f"Net income last actual ${ni[n - 1]:,.0f}, forecast "
            f"${ni[-1]:,.0f} by {yrs[-1]}")


def _valuation_text(d):
    dc = d["dcf"]
    tv_share = dc["pv_tv"] / (dc["sum_pv"] + dc["pv_tv"])
    lines = [
        f"Market price: ${dc['cur']:,.2f}/share",
        f"Gordon-growth DCF: ${dc['ps']:,.2f}/share "
        f"({dc['upside']:+.1%} vs market), WACC {dc['wacc']:.2%}, "
        f"terminal growth {dc['tg']:.2%}",
        f"Exit-multiple DCF ({dc['exit_mult']:.1f}x EV/EBITDA): "
        f"${dc['ps_exit']:,.2f}/share",
        f"{tv_share:.0%} of DCF enterprise value sits in the terminal value",
        "NOTE: a 5-year DCF is structurally conservative on premium "
        "compounders — treat 'overvalued' readings on quality names with "
        "care.",
    ]
    for label, lo, hi in d["field"]:
        lines.append(f"{label}: ${lo:,.0f}–${hi:,.0f}/share")
    return "\n".join(lines)


def _scenario_text(facts):
    rows = []
    for lbl in ("Bear", "Base", "Bull"):
        s = facts["scen"][lbl]
        rows.append(f"{lbl}: DCF ${s[f'DCF!B{D['ps']}']:,.2f}/share, "
                    f"Y5 net income ${s['IS!J21']:,.0f}mm")
    return "\n".join(rows)


def generate_pitch(ticker, direction="long", peers=None, dcf_xlsx=None,
                   workdir=None, llm=None, model=None,
                   use_cache=True) -> dict:
    direction = direction.upper()
    if direction not in ("LONG", "SHORT"):
        raise ValueError(f"direction must be long or short, got {direction}")
    facts = gather_facts(ticker, peers, dcf_xlsx, workdir, use_cache)
    d = facts["dcf"]
    prompt = PROMPT.format(
        direction=direction, ticker=d["ticker"], name=d["name"],
        fundamentals=_fundamentals_text(d),
        valuation=_valuation_text(d),
        scenarios=_scenario_text(facts),
        news_source=facts["headlines"]["source"],
        headlines=format_headlines(facts["headlines"]["items"]),
        macro=format_macro(facts["macro"]))
    sections = ask_json(prompt, required_keys=REQUIRED_KEYS, system=SYSTEM,
                        model=model, llm=llm)
    return dict(direction=direction, facts=facts, sections=sections,
                model=model or (active_model() if llm is None else "injected"))

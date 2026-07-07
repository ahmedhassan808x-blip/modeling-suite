"""
Grounded macro/news synthesis.

The model is given ONLY retrieved material — numbered headlines and dated
macro prints — and must cite an item for every claim. Price-impact
statements are explicitly framed as hypotheses. Output is labeled
AI-generated at the top of every artifact. No retrieved material, no
synthesis — the function refuses rather than letting the model freewheel.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.llm import DEFAULT_MODEL, ask  # noqa: E402

SYSTEM = """You are a disciplined markets analyst. Rules, non-negotiable:
- Use ONLY the material provided. Never invent facts, numbers, events, or
  news items. If the material doesn't support a statement, don't make it.
- Cite every claim to its source id: [H3] for headline 3, [M:federalFunds]
  for a macro print.
- Price-impact statements are hypotheses about plausible mechanisms, not
  predictions. Use language like "could pressure", "supports", "cuts both
  ways".
- Be honest about thin evidence: if the headlines are stale or barely
  relevant, say exactly that."""

PROMPT = """Asset: {label}

=== HEADLINES (source: {news_source}) ===
{headlines}

=== MACRO PRINTS (FMP, latest available) ===
{macro}

Write a concise markdown brief with exactly these sections:

## Recent Developments
What the headlines actually say that matters for this asset (3-5 bullets,
each cited).

## Macro Backdrop
The current rate/inflation/growth picture and why it matters for this
specific asset (2-4 bullets, each cited).

## Plausible Price Impact
How these developments could plausibly affect the asset's price — mechanisms,
direction, and what would confirm or refute each (3-4 bullets, cited,
hypothesis language).

## Confidence & Gaps
What this brief CANNOT tell us: missing information, staleness of the
material, and where a diligent analyst would dig next (2-3 bullets)."""


def format_headlines(items) -> str:
    if not items:
        return "(none retrieved)"
    return "\n".join(f"[H{i}] {h['date']} — {h['title']} ({h['source']})"
                     + (f"\n     {h['summary'][:200]}" if h.get("summary")
                        else "")
                     for i, h in enumerate(items, 1))


def format_macro(macro) -> str:
    lines = [f"[M:treasury] {macro['as_of']}: "
             + ", ".join(f"{k} {v:.2f}%" for k, v in macro["treasury"].items()
                         if v is not None)]
    for name, d in macro.get("indicators", {}).items():
        lines.append(f"[M:{name}] {d['date']}: {d['value']}")
    return "\n".join(lines)


def synthesize_context(label: str, headlines: dict, macro: dict,
                       llm=None, model: str = DEFAULT_MODEL) -> str:
    """Markdown brief, headed by the AI-generated label. Raises if there is
    nothing retrieved to ground on."""
    if not headlines.get("items") and not macro.get("indicators"):
        raise ValueError(f"{label}: no retrieved material to synthesize — "
                         "refusing to generate ungrounded analysis.")
    prompt = PROMPT.format(label=label,
                           news_source=headlines.get("source", "?"),
                           headlines=format_headlines(headlines.get("items")),
                           macro=format_macro(macro))
    call = llm or (lambda p, s, m: ask(p, system=s, max_tokens=m, model=model))
    body = call(prompt, SYSTEM, 1500)
    header = (f"> **AI-generated analysis** ({model}) — grounded in the "
              "retrieved headlines and macro prints listed below; verify "
              "before relying on it.\n\n")
    return header + body

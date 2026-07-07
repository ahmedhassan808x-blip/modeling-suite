"""
Pitch rendering: markdown memo, Word memo, deck, PDF — via the Phase 3
export layer. All financial figures are inserted from the recalculated
workbook extraction; the LLM's words are clearly attributed as AI-generated.
"""

import shutil
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dcf.model_builder import D  # noqa: E402
from shared import charts  # noqa: E402
from shared.exports.docx_memo import Memo  # noqa: E402
from shared.exports.pdf import to_pdf  # noqa: E402
from shared.exports.pptx_deck import Deck  # noqa: E402


def _val_table(d):
    dc = d["dcf"]
    rows = [["Method", "Implied value / range"],
            ["Gordon-growth DCF", f"${dc['ps']:,.2f}  ({dc['upside']:+.1%})"],
            [f"Exit-multiple DCF ({dc['exit_mult']:.1f}x)",
             f"${dc['ps_exit']:,.2f}"]]
    for label, lo, hi in d["field"]:
        if "DCF" in label:
            continue
        rows.append([label, f"${lo:,.0f} – ${hi:,.0f}"])
    rows.append(["Market price", f"${dc['cur']:,.2f}"])
    return rows


def _scen_table(facts):
    rows = [["Scenario", "DCF $/share"]]
    for lbl in ("Bear", "Base", "Bull"):
        rows.append([lbl, f"${facts['scen'][lbl][f'DCF!B{D['ps']}']:,.2f}"])
    return rows


def _titled(items):
    return [f"{it['title']} — {it['why']}" for it in items]


def render_markdown(pitch) -> str:
    s, d = pitch["sections"], pitch["facts"]["dcf"]
    lines = [
        f"# {pitch['direction']}: {d['name']} ({d['ticker']})",
        f"*{date.today().isoformat()} | modeling-suite pitch generator*",
        f"\n> **AI-generated analysis** ({pitch['model']}), grounded in a "
        "recalculated valuation model and retrieved headlines/macro prints. "
        "Verify before acting. This is a research thesis, not an order.",
        "\n## Thesis", s["thesis_summary"],
        "\n## Catalysts",
        *[f"- **{c['title']}** — {c['why']}" for c in s["catalysts"]],
        "\n## Valuation support", s["valuation_take"], "",
        *[f"- {r[0]}: {r[1]}" for r in _val_table(d)[1:]],
        f"- Scenarios (full model re-runs): "
        + ", ".join(f"{lbl} ${pitch['facts']['scen'][lbl][f'DCF!B{D['ps']}']:,.2f}"
                    for lbl in ("Bear", "Base", "Bull")),
        "\n## Key risks",
        *[f"- **{r['title']}** — {r['why']}" for r in s["risks"]],
        "\n## What would change my mind",
        *[f"- {x}" for x in s["change_my_mind"]],
        "\n## Weakest link", s["weakest_link"],
    ]
    return "\n".join(lines)


def build_outputs(pitch, outdir=".") -> dict:
    outdir = Path(outdir)
    d, s = pitch["facts"]["dcf"], pitch["sections"]
    dc = d["dcf"]
    stem = f"{d['ticker']}_{pitch['direction'].lower()}_pitch"

    md_path = outdir / f"{stem}.md"
    md_path.write_text(render_markdown(pitch))

    tmp = Path(tempfile.mkdtemp())
    png_field = charts.football_field(d["field"], dc["cur"], tmp / "ff.png")

    footer = (f"{d['ticker']} {pitch['direction']} pitch | modeling-suite | "
              f"AI-generated ({pitch['model']}) — verify before use | "
              "research thesis, not an order")
    deck = Deck(footer)
    deck.title_slide(f"{pitch['direction']}: {d['name']}",
                     f"{d['ticker']} — investment pitch",
                     f"AI-generated analysis ({pitch['model']}), grounded in "
                     "the recalculated valuation model — verify before use")
    sl = deck.content_slide("Thesis")
    deck.add_bullets(sl, [s["thesis_summary"]], 0.5, 1.3, 12.3, 1.5, size=14)
    deck.add_image(sl, png_field, 0.5, 2.85, 6.4)
    deck.add_bullets(sl, [f"Weakest link: {s['weakest_link']}"],
                     7.3, 3.1, 5.4, 3.4, size=11)

    sl = deck.content_slide("Catalysts")
    deck.add_bullets(sl, _titled(s["catalysts"]), 0.5, 1.4, 12.0, 5.0,
                     size=13)

    sl = deck.content_slide("Valuation support")
    deck.add_bullets(sl, [s["valuation_take"]], 0.5, 1.3, 6.4, 4.8, size=12)
    deck.add_table(sl, _val_table(d), 7.2, 1.5, 5.6, first_col_w=2.9)
    deck.add_table(sl, _scen_table(pitch["facts"]), 7.2, 4.6, 5.6)

    sl = deck.content_slide("Key risks & what would change my mind")
    deck.add_bullets(sl, _titled(s["risks"]), 0.5, 1.4, 6.2, 5.0, size=12)
    deck.add_bullets(sl, [f"Changes my mind: {x}"
                          for x in s["change_my_mind"]],
                     7.0, 1.4, 5.8, 5.0, size=12)
    pptx_path = deck.save(outdir / f"{stem}_deck.pptx")

    memo = Memo(f"{pitch['direction']}: {d['name']} ({d['ticker']})",
                f"Investment pitch | AI-generated ({pitch['model']}) — "
                "verify before use")
    memo.heading("Thesis")
    memo.para(s["thesis_summary"])
    memo.heading("Catalysts")
    memo.bullets(_titled(s["catalysts"]))
    memo.heading("Valuation support")
    memo.para(s["valuation_take"])
    memo.table(_val_table(d))
    memo.table(_scen_table(pitch["facts"]))
    memo.image(png_field)
    memo.heading("Key risks")
    memo.bullets(_titled(s["risks"]))
    memo.heading("What would change my mind")
    memo.bullets(s["change_my_mind"])
    memo.heading("Weakest link")
    memo.para(s["weakest_link"])
    memo.para("AI-generated analysis grounded in a recalculated model and "
              "retrieved headlines; research thesis, not an order.",
              small=True)
    docx_path = memo.save(outdir / f"{stem}_memo.docx")

    pdf_path = to_pdf(pptx_path, outdir)
    shutil.rmtree(tmp, ignore_errors=True)
    return dict(md=md_path, pptx=pptx_path, docx=docx_path, pdf=pdf_path)

"""
News layer + pitch generator, fully offline: headline normalization for
both source shapes, macro parsing, synthesis grounding rules, JSON
robustness, and the end-to-end pitch render with an injected fake LLM.
"""

import json

import pytest

from dcf.model_builder import build_dcf_model
from news import data_layer as nd
from news.synthesis import format_headlines, format_macro, synthesize_context
from pitch.generator import REQUIRED_KEYS, generate_pitch
from pitch.report import build_outputs
from shared.llm import LLMError, ask_json
from three_statement.assumptions import Assumptions
from tests.test_dcf import FAKE_PEERS

FAKE_MACRO = {"as_of": "2026-07-06",
              "treasury": {"3m": 3.87, "2y": 4.13, "10y": 4.48, "30y": 4.99},
              "indicators": {"inflationRate": {"value": 2.24,
                                               "date": "2026-07-06"},
                             "federalFunds": {"value": 3.63,
                                              "date": "2026-06-01"}}}
FAKE_HEADLINES = {"source": "test", "items": [
    {"title": "SimpleCo wins large contract", "source": "Newswire",
     "date": "2026-07-01", "summary": "A big deal.", "url": "http://x"},
    {"title": "Rates held steady", "source": "Wire", "date": "2026-06-28",
     "summary": "", "url": ""}]}

FAKE_SECTIONS = {
    "thesis_summary": "SimpleCo compounds revenue at 10% with stable "
                      "margins; the market underprices its cash generation.",
    "catalysts": [{"title": "Contract ramp", "why": "Per [H1]."},
                  {"title": "Rate stability", "why": "Per [M:federalFunds]."}],
    "valuation_take": "The Gordon DCF implies meaningful upside vs the "
                      "market price given in the facts pack.",
    "risks": [{"title": "Margin fade", "why": "Competitive pressure."},
              {"title": "Single customer", "why": "Concentration."}],
    "change_my_mind": ["Two quarters of decelerating revenue",
                       "Gross margin below 55%", "Contract cancellation"],
    "weakest_link": "Terminal growth carries most of the DCF value.",
}


def fake_llm(prompt, system, max_tokens):
    fake_llm.last_prompt, fake_llm.last_system = prompt, system
    return json.dumps(FAKE_SECTIONS)


# ---- news layer -----------------------------------------------------------

def test_fmp_article_filtering(monkeypatch):
    arts = [{"title": "About SMPL", "date": "2026-07-01 10:00",
             "content": "<p>Body &amp; text</p>", "tickers": "NYSE:SMPL",
             "link": "http://a", "site": "FMP"},
            {"title": "Other co", "date": "2026-07-01", "content": "x",
             "tickers": "NASDAQ:OTHR", "link": "", "site": "FMP"}]
    monkeypatch.setattr(nd, "get", lambda *a, **k: arts)
    out = nd._from_fmp_articles("SMPL", 5)
    assert len(out) == 1
    assert out[0]["title"] == "About SMPL"
    assert "<p>" not in out[0]["summary"]


def test_macro_parsing(monkeypatch):
    def fake_get(path, **kw):
        if path == "treasury-rates":
            return [{"date": "2026-07-06", "month3": 3.87, "year2": 4.13,
                     "year10": 4.48, "year30": 4.99}]
        if kw.get("name") == "realGDP":
            return [{"value": 105.0, "date": "2026-01-01"}] * 4 + \
                [{"value": 100.0, "date": "2025-01-01"}]
        return [{"value": 2.24, "date": "2026-07-06"}]
    monkeypatch.setattr(nd, "get", fake_get)
    m = nd.get_macro()
    assert m["treasury"]["10y"] == 4.48
    assert m["indicators"]["realGDP_yoy"]["value"] == 5.0
    assert "inflationRate" in m["indicators"]


def test_synthesis_grounding_and_label():
    md = synthesize_context("SMPL", FAKE_HEADLINES, FAKE_MACRO, llm=fake_llm)
    assert md.startswith("> **AI-generated analysis**")
    # the model was given the retrieved material, with citation ids
    assert "[H1] 2026-07-01 — SimpleCo wins large contract" \
        in fake_llm.last_prompt
    assert "[M:federalFunds] 2026-06-01: 3.63" in fake_llm.last_prompt
    assert "Use ONLY the material provided" in fake_llm.last_system


def test_synthesis_refuses_empty_material():
    with pytest.raises(ValueError, match="refusing"):
        synthesize_context("X", {"items": []}, {"indicators": {}},
                           llm=fake_llm)


# ---- llm plumbing ---------------------------------------------------------

def test_ask_json_retries_then_fails():
    calls = []

    def bad_llm(prompt, system, max_tokens):
        calls.append(prompt)
        return "not json at all"
    with pytest.raises(LLMError, match="invalid JSON twice"):
        ask_json("p", llm=bad_llm)
    assert len(calls) == 2 and "not valid" in calls[1]


def test_ask_json_strips_fences_and_checks_keys():
    good = ask_json("p", required_keys=("a",),
                    llm=lambda p, s, m: '```json\n{"a": 1}\n```')
    assert good == {"a": 1}
    with pytest.raises(LLMError, match="missing keys"):
        ask_json("p", required_keys=("zz",), llm=lambda p, s, m: '{"a": 1}')


# ---- pitch end-to-end (offline) -------------------------------------------

@pytest.fixture(scope="module")
def pitch_outputs(simpleco_module, tmp_path_factory, module_mocker=None):
    tmp = tmp_path_factory.mktemp("pitch")
    xlsx = tmp / "SMPL_dcf.xlsx"
    build_dcf_model(simpleco_module, Assumptions.derive(simpleco_module),
                    xlsx, peers=FAKE_PEERS)
    import pitch.generator as pg
    orig_fetch = pg.fetch_financials
    orig_heads, orig_macro = pg.get_headlines, pg.get_macro
    pg.fetch_financials = lambda t, **k: simpleco_module
    pg.get_headlines = lambda t, **k: FAKE_HEADLINES
    pg.get_macro = lambda **k: FAKE_MACRO
    try:
        pitch = generate_pitch("SMPL", direction="short", dcf_xlsx=xlsx,
                               llm=fake_llm)
        outputs = build_outputs(pitch, tmp)
    finally:
        pg.fetch_financials = orig_fetch
        pg.get_headlines, pg.get_macro = orig_heads, orig_macro
    return pitch, outputs


def test_pitch_prompt_grounded_and_directional(pitch_outputs):
    pitch, _ = pitch_outputs
    p = fake_llm.last_prompt
    assert "Direction: SHORT SMPL" in p
    assert "Gordon-growth DCF" in p and "Market price: $50.00" in p
    assert "SimpleCo wins large contract" in p
    assert all(k in pitch["sections"] for k in REQUIRED_KEYS)


def test_pitch_outputs_complete_and_labeled(pitch_outputs):
    pitch, outputs = pitch_outputs
    for kind in ("md", "pptx", "docx", "pdf"):
        assert outputs[kind].exists(), f"{kind} missing"
    md = outputs["md"].read_text()
    assert md.startswith("# SHORT: SimpleCo Inc (SMPL)")
    assert "AI-generated analysis" in md
    assert "What would change my mind" in md
    assert "not an order" in md
    # valuation figures come from the extraction, not the LLM
    assert "$50.00" in md
    from pptx import Presentation
    prs = Presentation(outputs["pptx"])
    assert len(prs.slides) >= 5

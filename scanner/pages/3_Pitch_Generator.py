"""Pitch Generator — long/short thesis grounded in the recalculated model."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st  # noqa: E402

from shared.webutil import (  # noqa: E402
    anthropic_available, offer_download, secrets_to_env, soffice_available,
)

st.set_page_config(page_title="Pitch Generator", page_icon="🎤",
                   layout="wide")
secrets_to_env()

st.title("🎤 Investment Pitch Generator")
st.caption("Long or short. Facts come from a freshly built, recalculated DCF "
           "workbook plus retrieved headlines/macro; the AI argues but never "
           "computes — every number renders from the model. Labeled "
           "AI-generated; research thesis, not an order.")

c1, c2, c3 = st.columns([2, 1, 2])
ticker = c1.text_input("Ticker", "AAPL").strip().upper()
direction = c2.radio("Direction", ["long", "short"], horizontal=True)
peers = c3.text_input("Peers for comps (optional)", "MSFT,GOOGL,META").strip()

if not anthropic_available():
    st.info("Add ANTHROPIC_API_KEY or GEMINI_API_KEY (free: "
            "aistudio.google.com/apikey) in Settings → Secrets to enable "
            "this page.")
elif not soffice_available():
    st.warning("LibreOffice unavailable on this host — the pitch needs it to "
               "recalculate the model and scenario re-runs.")
elif st.button("Generate pitch", type="primary"):
    from pitch.generator import generate_pitch
    from pitch.report import build_outputs

    tmp = Path(tempfile.mkdtemp())
    try:
        with st.spinner("Building the DCF, re-running scenarios, retrieving "
                        "news, writing the pitch… (~1–2 minutes)"):
            p = generate_pitch(
                ticker, direction=direction,
                peers=[x.strip() for x in peers.split(",") if x.strip()]
                or None, workdir=tmp)
            outputs = build_outputs(p, tmp)
        st.markdown(outputs["md"].read_text())
        st.divider()
        for kind in ("md", "docx", "pptx", "pdf"):
            offer_download(f"Pitch {kind}", outputs[kind])
    except Exception as e:
        st.error(f"{type(e).__name__}: {e}")

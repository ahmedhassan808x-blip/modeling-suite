"""News & Macro Context — retrieved headlines + macro, AI synthesis."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st  # noqa: E402

from shared.webutil import anthropic_available, secrets_to_env  # noqa: E402

st.set_page_config(page_title="News & Macro Context", page_icon="📰",
                   layout="wide")
secrets_to_env()

st.title("📰 News & Macro Context")
st.caption("Retrieved headlines + current macro prints, with an AI synthesis "
           "of how the developments plausibly affect the asset — grounded, "
           "cited line-by-line, labeled, never fabricated.")

ticker = st.text_input("Ticker", "AAPL").strip().upper()

if st.button("Get context", type="primary"):
    from news.data_layer import get_headlines, get_macro
    from news.synthesis import format_headlines, format_macro, \
        synthesize_context

    with st.spinner("Retrieving headlines and macro prints…"):
        headlines = get_headlines(ticker)
        macro = get_macro()
    st.subheader("Retrieved material")
    st.caption(f"Headline source: {headlines['source']} — the active "
               "provider is always stated (cloud hosts can't use yfinance; "
               "the FMP editorial fallback has thinner coverage).")
    st.text(format_headlines(headlines["items"]))
    st.text(format_macro(macro))

    if not anthropic_available():
        st.info("No ANTHROPIC_API_KEY in the app secrets — showing "
                "retrieved data only, no AI synthesis. Add the key in "
                "Settings → Secrets to enable it.")
    else:
        with st.spinner("Synthesizing (grounded, cited)…"):
            try:
                st.markdown(synthesize_context(ticker, headlines, macro))
            except ValueError as e:
                st.warning(str(e))

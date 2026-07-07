"""
Mispricing scanner — Streamlit dashboard (matches the analyst-toolkit
dashboard patterns; designed to mount into that app as a page later).

Run:
    streamlit run scanner/app.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

try:
    for _k in ("FMP_API_KEY",):
        if _k in st.secrets:
            os.environ[_k] = st.secrets[_k]
except Exception:
    pass  # no secrets file (local run) — falls back to .env

from scanner.scan import scan  # noqa: E402
from scanner.universe import DEFAULT_UNIVERSE  # noqa: E402

st.set_page_config(page_title="Mispricing Scanner", page_icon="🎯",
                   layout="wide")
st.title("🎯 Mispricing Scanner")
st.caption("Gordon DCF (Python mirror of the live Excel engine, "
           "agreement-tested) vs. market price, ranked by divergence. "
           "Artifact flags tell you when a 'mispricing' is the model's own "
           "limitation showing — rank ≠ conviction.")
st.sidebar.caption("**More tools in the sidebar ↑** — build live Excel "
                   "models (3-statement, DCF, LBO, merger), pull news/macro "
                   "context, generate long/short pitches, or grab the "
                   "budget template.")

st.sidebar.title("Universe")
tickers_text = st.sidebar.text_area(
    "One ticker per line", value="\n".join(DEFAULT_UNIVERSE), height=320)
use_cache = st.sidebar.checkbox("Use 24h data cache", value=True)
st.sidebar.caption("~4 FMP requests per uncached name; free tier allows "
                   "250/day. Gated symbols are reported, not dropped.")


@st.cache_data(show_spinner="Scanning universe…", ttl=3600)
def run_scan(tickers, cached):
    return scan(tickers, use_cache=cached)


if st.button("Run scan", type="primary"):
    tickers = [t.strip().upper() for t in tickers_text.splitlines()
               if t.strip()]
    res = run_scan(tuple(tickers), use_cache)

    if res["rows"]:
        df = pd.DataFrame([{
            "Ticker": r["ticker"], "Name": r["name"], "Price": r["price"],
            "DCF $/sh": r["ps"], "Exit $/sh": r["ps_exit"],
            "Upside": r["upside"], "TV share": r["tv_share"],
            "Trail growth": r["trailing_growth"], "Verdict": r["verdict"],
            "Flags": "; ".join(r["flags"]) or "—",
        } for r in res["rows"]]).set_index("Ticker")
        st.dataframe(
            df.style
            .background_gradient(cmap="RdYlGn", subset=["Upside"],
                                 vmin=-0.8, vmax=0.8)
            .format({"Price": "${:,.2f}", "DCF $/sh": "${:,.2f}",
                     "Exit $/sh": "${:,.2f}", "Upside": "{:+.1%}",
                     "TV share": "{:.0%}", "Trail growth": "{:+.0%}"}),
            use_container_width=True, height=620)
        st.download_button(
            "⬇ Download results (.csv)", df.to_csv(),
            file_name="mispricing_scan.csv")
        st.caption("For any name worth a closer look: "
                   "`python3 -m dcf.build_model TICKER --report` builds the "
                   "full live workbook and deck.")
    if res["gated"]:
        st.warning("Gated on FMP free tier (skipped): "
                   + ", ".join(res["gated"]))
    for tk, why in res["failed"]:
        st.error(f"{tk}: {why}")

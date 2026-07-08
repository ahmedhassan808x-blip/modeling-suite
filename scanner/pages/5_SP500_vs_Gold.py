"""S&P 500 vs. Gold — comparative allocation brief, rebuilt on demand."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from shared.webutil import (  # noqa: E402
    anthropic_available, offer_download, secrets_to_env,
)

st.set_page_config(page_title="S&P 500 vs Gold", page_icon="⚖️",
                   layout="wide")
secrets_to_env()

st.title("⚖️ S&P 500 vs. Gold — today's read")
st.caption("A dated, sourced comparative brief: live prices and macro from "
           "FMP, current valuations/flows/commentary via web research, and "
           "a grounded AI reasoned view. Analysis to inform thinking — not "
           "a recommendation. Each run reflects that day's data.")

if not anthropic_available():
    st.info("Add ANTHROPIC_API_KEY in Settings → Secrets — the research "
            "layer (web search) and reasoned view need it.")
elif st.button("Build today's brief", type="primary"):
    from sp500_vs_gold.brief import build_brief
    from sp500_vs_gold.report import build_outputs, render_markdown

    try:
        with st.spinner("Fetching live data, researching current context "
                        "(web search), writing the brief… (~1–2 min)"):
            brief = build_brief()
            tmp = Path(tempfile.mkdtemp())
            outputs = build_outputs(brief, tmp)
        lean = brief["view"]["lean"]
        st.metric("Reasoned lean (one input, not the decision)", lean)
        st.dataframe(pd.DataFrame(brief["rows"]).rename(columns={
            "metric": "Metric", "spx": "S&P 500", "gold": "Gold",
            "as_of": "As of", "source": "Source"}).set_index("Metric"),
            use_container_width=True)
        st.markdown("\n\n".join(render_markdown(brief).split("\n\n")[2:]))
        st.divider()
        for kind in ("md", "xlsx", "docx", "pdf"):
            offer_download(f"Brief {kind}", outputs[kind])
    except Exception as e:
        st.error(f"{type(e).__name__}: {e}")
        st.caption("Loud by design — data gaps and gated endpoints say "
                   "exactly what's missing rather than showing stale or "
                   "fabricated numbers.")

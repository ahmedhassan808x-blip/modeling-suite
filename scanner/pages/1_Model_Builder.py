"""Model Builder — build any live Excel model in the browser."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st  # noqa: E402

from shared.webutil import offer_download, recalc_banner, secrets_to_env  # noqa: E402

st.set_page_config(page_title="Model Builder", page_icon="📊", layout="wide")
secrets_to_env()

st.title("📊 Model Builder")
st.caption("Live Excel workbooks — blue = input, black = formula, green = "
           "cross-sheet link. Every forecast cell is a real formula; change "
           "any assumption in Excel and the model recalculates.")

model = st.selectbox("Model", ["Three-Statement", "DCF (+ comps)", "LBO",
                               "Merger (accretion/dilution)"])
c1, c2 = st.columns(2)
ticker = c1.text_input("Ticker" if model != "Merger (accretion/dilution)"
                       else "Acquirer ticker", "AAPL").strip().upper()
target = peers = entry = None
if model == "Merger (accretion/dilution)":
    target = c2.text_input("Target ticker", "ADBE").strip().upper()
elif model == "DCF (+ comps)":
    peers = c2.text_input("Peers (comma-separated, optional)",
                          "MSFT,GOOGL,META").strip()
elif model == "LBO":
    entry = c2.number_input("Entry EV/EBITDA (0 = seed from market)",
                            value=0.0, step=0.5)
want_report = st.checkbox("Also build the deck / memo / PDF "
                          "(slower: re-runs scenarios)", value=False)

if st.button("Build model", type="primary"):
    from three_statement.assumptions import Assumptions
    from three_statement.data_layer import fetch_financials

    tmp = Path(tempfile.mkdtemp())
    try:
        with st.spinner(f"Fetching {ticker} and writing formulas…"):
            data = fetch_financials(ticker, n_hist=3)
            a = Assumptions.derive(data)
            reports = None
            if model == "Three-Statement":
                from three_statement.model_builder import build_model
                out = tmp / f"{ticker}_3stmt.xlsx"
                build_model(data, a, out)
                if want_report:
                    from three_statement.report import build_reports
                    reports = build_reports(out)
            elif model == "DCF (+ comps)":
                from dcf.model_builder import build_dcf_model
                peer_data = None
                if peers:
                    from dcf.data_layer import get_peer_multiples
                    peer_data = get_peer_multiples(
                        [p.strip() for p in peers.split(",") if p.strip()])
                out = tmp / f"{ticker}_dcf.xlsx"
                build_dcf_model(data, a, out, peers=peer_data)
                if want_report:
                    from dcf.report import build_reports
                    reports = build_reports(out)
            elif model == "LBO":
                from lbo.assumptions import LBOAssumptions
                from lbo.model_builder import build_lbo_model
                lb = LBOAssumptions.derive(data)
                if entry:
                    lb.entry_mult = lb.exit_mult = entry
                out = tmp / f"{ticker}_lbo.xlsx"
                build_lbo_model(data, a, lb, out)
                if want_report:
                    from lbo.report import build_reports
                    reports = build_reports(out)
            else:
                from merger.assumptions import MergerAssumptions
                from merger.model_builder import build_merger_model
                tgt = fetch_financials(target, n_hist=3)
                out = tmp / f"{ticker}_{target}_merger.xlsx"
                build_merger_model(data, tgt, MergerAssumptions(), out)
                if want_report:
                    from merger.report import build_reports
                    reports = build_reports(out)
        recalc_banner(out)
        offer_download("Live Excel model", out)
        if reports:
            for kind, p in reports.items():
                offer_download(kind, p)
    except Exception as e:
        st.error(f"{type(e).__name__}: {e}")
        st.caption("Loud and specific by design — gated FMP symbols, missing "
                   "data, and broken inputs all say exactly what went wrong.")

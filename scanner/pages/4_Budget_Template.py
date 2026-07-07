"""Budget Template — generate the fill-in variance workbook."""

import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st  # noqa: E402

from shared.webutil import offer_download, recalc_banner, secrets_to_env  # noqa: E402

st.set_page_config(page_title="Budget Template", page_icon="📋")
secrets_to_env()

st.title("📋 Budget vs. Actual Template")
st.caption("A fill-in workbook: monthly Budget and Actuals grids (blue "
           "cells, costs negative) and a fully formula-driven Variance "
           "sheet — uniform favorability, dual-threshold REVIEW flags, and "
           "a commentary column for every flagged line.")

company = st.text_input("Company name", "My Company")
year = st.number_input("Fiscal year", value=date.today().year, step=1)

if st.button("Generate template", type="primary"):
    from budget.model_builder import build_budget_template

    tmp = Path(tempfile.mkdtemp())
    slug = "".join(c for c in company if c.isalnum()) or "company"
    out = tmp / f"{slug}_budget_FY{int(year)}.xlsx"
    with st.spinner("Writing formulas…"):
        build_budget_template(company, int(year), out)
    recalc_banner(out)
    offer_download("Budget template", out)

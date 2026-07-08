"""
Shared helpers for the Streamlit pages: secrets -> env mapping (Streamlit
Cloud style, matching the analyst-toolkit dashboard pattern), capability
probes (LibreOffice / Anthropic key), and a download helper.
"""

import os
from pathlib import Path

import streamlit as st


def secrets_to_env():
    try:
        for k in ("FMP_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY",
                  "LLM_PROVIDER", "CLAUDE_MODEL", "GEMINI_MODEL"):
            if k in st.secrets:
                os.environ[k] = st.secrets[k]
    except Exception:
        pass  # no secrets file (local run) — modules fall back to .env


def soffice_available() -> bool:
    try:
        from shared.recalc import find_soffice
        find_soffice()
        return True
    except Exception:
        return False


def anthropic_available() -> bool:
    try:
        from shared.llm import provider
        provider()
        return True
    except Exception:
        return False


def offer_download(label: str, path, mime=None):
    path = Path(path)
    st.download_button(f"⬇ {label} ({path.name})", path.read_bytes(),
                       file_name=path.name, mime=mime, key=f"dl_{path.name}")


def recalc_banner(xlsx, extra_probes=None):
    """Run the recalc gate and show the verdict; warn if unavailable."""
    if not soffice_available():
        st.warning("LibreOffice not available on this host — the recalc "
                   "verification gate was skipped. The workbook's formulas "
                   "are unverified here (they are verified in CI/tests).")
        return None
    from shared.recalc import recalculate
    res = recalculate(xlsx, probe_cells=extra_probes or [])
    if res.ok:
        st.success("Recalculated in LibreOffice — zero formula errors.")
    else:
        st.error(res.summary())
    return res

"""PDF export via headless LibreOffice — reuses the recalc-gate install."""

import subprocess
import tempfile
from pathlib import Path

from shared.recalc import RecalcError, find_soffice


def to_pdf(input_path, outdir=None) -> Path:
    """Convert any Office document (pptx/docx/xlsx) to PDF alongside it."""
    input_path = Path(input_path).resolve()
    outdir = Path(outdir).resolve() if outdir else input_path.parent
    with tempfile.TemporaryDirectory() as tmp:
        proc = subprocess.run(
            [find_soffice(), "--headless", "--norestore",
             f"-env:UserInstallation=file://{tmp}/profile",
             "--convert-to", "pdf", "--outdir", str(outdir), str(input_path)],
            capture_output=True, text=True, timeout=180)
    out = outdir / (input_path.stem + ".pdf")
    if proc.returncode != 0 or not out.exists():
        raise RecalcError(f"PDF conversion failed for {input_path.name} "
                          f"(rc={proc.returncode}): {proc.stderr[:300]}")
    return out

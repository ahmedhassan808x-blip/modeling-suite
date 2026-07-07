"""
Navy & steel — the single visual identity for every export in the suite.

One palette, defined once, consumed by charts (matplotlib), decks
(python-pptx), memos (python-docx) and the Excel writer. Change it here and
every artifact follows.
"""

import matplotlib

matplotlib.use("Agg")  # headless — no GUI dependency
from matplotlib import pyplot as plt  # noqa: E402

# Core palette (hex, no leading #; helpers below add it where needed)
NAVY = "1F3864"
STEEL = "8EAADB"
SLATE = "44546A"      # secondary text / lines
MIST = "D6DCE5"       # light fill / table banding
INK = "222222"        # body text
GRAY = "7F7F7F"       # captions, footnotes
BEAR = "B84C4C"       # scenario accents (muted, not alarm-red)
BULL = "4C8C6A"

FONT = "Arial"


def hx(c: str) -> str:
    return f"#{c}"


def style_axes(ax, title=None, ylabel=None, currency=False, pct=False):
    """House style: open frame, light grid, navy title, labeled axes."""
    ax.spines[["top", "right"]].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(hx(GRAY))
    ax.tick_params(colors=hx(SLATE), labelsize=9)
    ax.grid(axis="y", color=hx(MIST), linewidth=0.8)
    ax.set_axisbelow(True)
    if title:
        ax.set_title(title, color=hx(NAVY), fontsize=12, fontweight="bold",
                     loc="left", pad=12, fontfamily=FONT)
    if ylabel:
        ax.set_ylabel(ylabel, color=hx(SLATE), fontsize=9, fontfamily=FONT)
    if currency:
        ax.yaxis.set_major_formatter(
            plt.FuncFormatter(lambda v, _: f"${v:,.0f}"))
    if pct:
        ax.yaxis.set_major_formatter(
            plt.FuncFormatter(lambda v, _: f"{v:.0%}"))


def new_figure(width=7.2, height=3.9):
    fig, ax = plt.subplots(figsize=(width, height), dpi=200)
    fig.patch.set_facecolor("white")
    return fig, ax


def save_png(fig, path):
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path

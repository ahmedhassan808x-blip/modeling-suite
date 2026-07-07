"""
Chart library — every chart in the suite is defined exactly once here and
reused across PowerPoint, Word and PDF outputs (as themed PNGs). Excel keeps
its own native chart where interactivity matters (the football field in the
workbook), but the *spec* — series, ordering, colors — matches.

All money in $mm unless a chart says otherwise.
"""

import numpy as np

from shared.theme import (BEAR, BULL, GRAY, MIST, NAVY, SLATE, STEEL, hx,
                          new_figure, save_png, style_axes)


def revenue_ebitda(years, revenue, ebitda_margin, n_hist, path,
                   title="Revenue & EBITDA margin"):
    """Bars: revenue (steel = actual, navy = forecast); line: EBITDA margin."""
    fig, ax = new_figure()
    x = np.arange(len(years))
    colors = [hx(STEEL)] * n_hist + [hx(NAVY)] * (len(years) - n_hist)
    ax.bar(x, revenue, color=colors, width=0.62)
    ax.axvline(n_hist - 0.5, color=hx(GRAY), linewidth=0.8, linestyle="--")
    ax.text(n_hist - 0.42, ax.get_ylim()[1] * 0.02, "forecast →",
            color=hx(GRAY), fontsize=8)
    style_axes(ax, title=title, ylabel="Revenue ($mm)", currency=True)
    ax.set_xticks(x, years)

    ax2 = ax.twinx()
    ax2.plot(x, ebitda_margin, color=hx(SLATE), marker="o", markersize=4,
             linewidth=1.6)
    ax2.set_ylabel("EBITDA margin", color=hx(SLATE), fontsize=9)
    ax2.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    ax2.set_ylim(0, max(ebitda_margin) * 1.6)
    ax2.spines[["top"]].set_visible(False)
    ax2.tick_params(colors=hx(SLATE), labelsize=9)
    return save_png(fig, path)


def scenario_paths(years_fc, paths, path, title="Revenue by scenario ($mm)"):
    """paths: {'Bear': [...], 'Base': [...], 'Bull': [...]} incl. anchor year."""
    fig, ax = new_figure()
    styles = {"Bear": (hx(BEAR), "--"), "Base": (hx(NAVY), "-"),
              "Bull": (hx(BULL), "--")}
    for name, series in paths.items():
        color, ls = styles.get(name, (hx(GRAY), ":"))
        ax.plot(years_fc, series, label=name, color=color, linestyle=ls,
                linewidth=2, marker="o", markersize=3.5)
        ax.annotate(f"{name}  ${series[-1]:,.0f}",
                    (years_fc[-1], series[-1]), textcoords="offset points",
                    xytext=(8, -3), fontsize=8.5, color=color)
    style_axes(ax, title=title, currency=True)
    ax.set_xticks(years_fc)
    ax.margins(x=0.12)
    return save_png(fig, path)


def cash_and_debt(years, cash, debt, path,
                  title="Cash vs. total debt ($mm)"):
    fig, ax = new_figure()
    x = np.arange(len(years))
    ax.bar(x - 0.18, cash, width=0.36, color=hx(STEEL), label="Cash")
    ax.bar(x + 0.18, debt, width=0.36, color=hx(NAVY), label="Total debt")
    style_axes(ax, title=title, currency=True)
    ax.set_xticks(x, years)
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    return save_png(fig, path)


def ufcf_bars(years_fc, ufcf, path, title="Unlevered free cash flow ($mm)"):
    fig, ax = new_figure()
    x = np.arange(len(years_fc))
    ax.bar(x, ufcf, color=hx(NAVY), width=0.6)
    for i, v in enumerate(ufcf):
        ax.text(i, v, f"${v:,.0f}", ha="center",
                va="bottom" if v >= 0 else "top", fontsize=8.5, color=hx(SLATE))
    style_axes(ax, title=title, currency=True)
    ax.set_xticks(x, years_fc)
    return save_png(fig, path)


def tv_split(sum_pv, pv_tv, path,
             title="Where the DCF value sits (share of enterprise value)"):
    """Honest-DCF bar: how much of EV is the terminal value."""
    fig, ax = new_figure(height=1.8)
    total = sum_pv + pv_tv
    ax.barh([0], [sum_pv / total], color=hx(STEEL), height=0.5,
            label="PV of explicit FCF (5 yrs)")
    ax.barh([0], [pv_tv / total], left=[sum_pv / total], color=hx(NAVY),
            height=0.5, label="PV of terminal value")
    for frac, x0, c in ((sum_pv / total, 0, "black"),
                        (pv_tv / total, sum_pv / total, "white")):
        ax.text(x0 + frac / 2, 0, f"{frac:.0%}", ha="center", va="center",
                color=c, fontsize=11, fontweight="bold")
    ax.set_xlim(0, 1)
    ax.set_yticks([])
    ax.set_xticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_title(title, color=hx(NAVY), fontsize=12, fontweight="bold",
                 loc="left", pad=10)
    ax.legend(frameon=False, fontsize=8.5, loc="upper center",
              bbox_to_anchor=(0.5, -0.1), ncol=2)
    return save_png(fig, path)


def pct_bars(labels, values, path, title="Accretion / (dilution) by year"):
    """Signed percentage bars, green/red by sign, zero line."""
    fig, ax = new_figure(height=3.4)
    x = np.arange(len(labels))
    colors = [hx(BULL) if v >= 0 else hx(BEAR) for v in values]
    ax.bar(x, values, color=colors, width=0.55)
    for i, v in enumerate(values):
        ax.text(i, v, f"{v:+.1%}", ha="center",
                va="bottom" if v >= 0 else "top", fontsize=9, color=hx(SLATE))
    ax.axhline(0, color=hx(GRAY), linewidth=0.9)
    style_axes(ax, title=title)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.1%}")
    ax.set_xticks(x, labels)
    ax.margins(y=0.25)
    return save_png(fig, path)


def waterfall(steps, path, title="Value-creation bridge ($mm)"):
    """steps: [(label, value, kind)] with kind in {'total', 'delta'}.
    Totals are full bars from zero; deltas float from the running level."""
    fig, ax = new_figure()
    x = np.arange(len(steps))
    level = 0.0
    for i, (label, val, kind) in enumerate(steps):
        if kind == "total":
            ax.bar(i, val, color=hx(NAVY), width=0.62)
            ax.text(i, val, f"${val:,.0f}", ha="center", va="bottom",
                    fontsize=8.5, color=hx(SLATE), fontweight="bold")
            level = val
        else:
            color = hx(BULL) if val >= 0 else hx(BEAR)
            ax.bar(i, val, bottom=level, color=color, width=0.62)
            ax.text(i, level + val + (0.5 if val >= 0 else -0.5),
                    f"{val:+,.0f}", ha="center",
                    va="bottom" if val >= 0 else "top", fontsize=8.5,
                    color=hx(SLATE))
            level += val
    style_axes(ax, title=title, currency=True)
    ax.set_xticks(x, [s[0] for s in steps], fontsize=8)
    fig.autofmt_xdate(rotation=15, ha="center")
    return save_png(fig, path)


def debt_paydown(years, tranches, path, title="Debt outstanding ($mm)"):
    """tranches: ordered {label: [balances]} stacked bottom-up."""
    fig, ax = new_figure()
    x = np.arange(len(years))
    bottom = np.zeros(len(years))
    colors = [hx(NAVY), hx(STEEL), hx(GRAY)]
    for (label, series), color in zip(tranches.items(), colors):
        ax.bar(x, series, bottom=bottom, color=color, width=0.6, label=label)
        bottom += np.asarray(series, dtype=float)
    for i, tot in enumerate(bottom):
        ax.text(i, tot, f"${tot:,.0f}", ha="center", va="bottom",
                fontsize=8.5, color=hx(SLATE))
    style_axes(ax, title=title, currency=True)
    ax.set_xticks(x, years)
    ax.legend(frameon=False, fontsize=9)
    return save_png(fig, path)


def football_field(methods, current_price, path,
                   title="Implied value per share ($)"):
    """methods: list of (label, low, high), plotted top-down as range bars."""
    fig, ax = new_figure(height=0.55 * len(methods) + 1.2)
    labels = [m[0] for m in methods]
    y = np.arange(len(methods))[::-1]
    lo_all = min(m[1] for m in methods)
    hi_all = max(max(m[2] for m in methods), current_price)
    span = hi_all - lo_all or 1
    for yi, (_, lo, hi) in zip(y, methods):
        if hi - lo < 0.02 * span:  # point estimate: marker + single label
            ax.plot([lo], [yi], marker="D", markersize=7, color=hx(NAVY))
            ax.text(lo + 0.015 * span, yi, f"${(lo + hi) / 2:,.0f}",
                    ha="left", va="center", fontsize=8, color=hx(SLATE))
            continue
        ax.barh(yi, hi - lo, left=lo, height=0.52, color=hx(NAVY))
        ax.text(lo - 0.01 * span, yi, f"${lo:,.0f}", ha="right", va="center",
                fontsize=8, color=hx(SLATE))
        ax.text(hi + 0.01 * span, yi, f"${hi:,.0f}", ha="left", va="center",
                fontsize=8, color=hx(SLATE))
    ax.axvline(current_price, color=hx(BEAR), linewidth=1.4, linestyle="--")
    ax.text(current_price, len(methods) - 0.3, f" current ${current_price:,.2f}",
            color=hx(BEAR), fontsize=8.5, fontweight="bold")
    ax.set_xlim(lo_all - 0.14 * span, hi_all + 0.14 * span)
    ax.set_yticks(y, labels)
    style_axes(ax, title=title)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=hx(MIST), linewidth=0.8)
    return save_png(fig, path)

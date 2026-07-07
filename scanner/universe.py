"""
Scan universe. Default: ~30 liquid US large caps chosen to be
free-tier-friendly (FMP's free plan gates many symbols — e.g. PG returns
402). Gated names in any universe are reported by the scanner, not
silently dropped, so a custom list is safe to try.

Custom universe: a text file, one ticker per line, # comments allowed.
"""

from pathlib import Path

DEFAULT_UNIVERSE = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA",
    "AMD", "AVGO", "QCOM", "INTC", "MU", "TXN", "AMAT",
    "ORCL", "CRM", "ADBE", "INTU", "CSCO", "NFLX",
    "PYPL", "UBER", "ABNB", "SHOP", "COIN", "PLTR", "SNOW", "CRWD",
]


def load_universe(path: str | None = None) -> list[str]:
    if not path:
        return list(DEFAULT_UNIVERSE)
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Universe file not found: {p}")
    tickers = []
    for line in p.read_text().splitlines():
        t = line.split("#")[0].strip().upper()
        if t:
            tickers.append(t)
    if not tickers:
        raise ValueError(f"{p}: no tickers found.")
    return tickers

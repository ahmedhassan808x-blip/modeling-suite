"""
Shared FMP client — STABLE API (legacy /api/v3 returns 403 for new accounts).

Generalized from analyst-toolkit/valuation-engine/fmp_data.py with two additions:
  1. cash-flow-statement endpoint support (needed by the 3-statement model)
  2. a 24h disk cache, because the free tier allows 250 requests/day and
     rebuilding a model during development should not burn quota.

Key resolution: FMP_API_KEY env var, then .env in cwd, then .env at repo root.
Failures are loud and specific — never silently return wrong data.
"""

import hashlib
import json
import os
import sys
import time
from pathlib import Path

import requests

BASE = "https://financialmodelingprep.com/stable"
REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = REPO_ROOT / ".cache" / "fmp"
CACHE_TTL_S = 24 * 3600


class FMPError(RuntimeError):
    """Raised for any FMP failure: missing key, HTTP error, empty payload."""


def _key() -> str:
    k = os.environ.get("FMP_API_KEY")
    if k:
        return k
    for env in (Path.cwd() / ".env", REPO_ROOT / ".env"):
        if env.exists():
            for line in env.read_text().splitlines():
                if line.strip().startswith("FMP_API_KEY"):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise FMPError("No FMP_API_KEY found (env var, ./.env, or repo-root .env). "
                   "Free key: https://site.financialmodelingprep.com")


def _cache_path(path: str, params: dict) -> Path:
    raw = path + "|" + json.dumps(params, sort_keys=True)
    digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
    symbol = params.get("symbol", "na")
    return CACHE_DIR / f"{path.replace('/', '_')}_{symbol}_{digest}.json"


def get(path: str, use_cache: bool = True, **params):
    """GET a stable-API route, e.g. get("income-statement", symbol="AAPL", limit=4)."""
    cf = _cache_path(path, params)
    if use_cache and cf.exists() and time.time() - cf.stat().st_mtime < CACHE_TTL_S:
        return json.loads(cf.read_text())

    q = dict(params, apikey=_key())
    r = requests.get(f"{BASE}/{path}", params=q, timeout=30)
    if r.status_code != 200:
        raise FMPError(f"FMP {path} for {params.get('symbol', '?')}: "
                       f"HTTP {r.status_code} — {r.text[:200]}")
    data = r.json()
    if isinstance(data, dict) and data.get("Error Message"):
        raise FMPError(f"FMP {path}: {data['Error Message']}")

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cf.write_text(json.dumps(data))
    return data


def field(d: dict, *keys, default=None, context=""):
    """First present numeric field among alternative key spellings.

    default=None means the field is required: raise loudly if absent.
    A non-None default logs the substitution to stderr instead of guessing silently.
    """
    for k in keys:
        v = d.get(k)
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                continue
    if default is None:
        raise FMPError(f"Required field missing ({context}): tried {keys}")
    print(f"[fmp] missing {keys[0]} ({context}) — using default {default}",
          file=sys.stderr)
    return float(default)

"""
Synthetic FMP-shaped fixtures: "SimpleCo", three clean years with round
numbers whose statements tie exactly. Everything here is hand-verifiable:
10% revenue growth, 40% COGS, 20% EBIT margin, flat debt of $200mm.
Offline by design — no API quota burned by the test suite.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

M = 1e6
YEARS = [2023, 2024, 2025]
REV = [1000, 1100, 1210]
COGS = [400, 440, 484]
EBIT = [200, 220, 242]
DNA = [50, 55, 60]
CASH = [300, 320, 340]
AR = [100, 110, 121]
INV = [40, 44, 48.4]
OTHER_CA = [20, 22, 24.2]
PPE = [500, 520, 540]
AP = [60, 66, 72.6]
OTHER_CL = [30, 33, 36.3]
RE = [600, 640, 680]


def _income(year, rev, cogs, ebit, dna):
    pretax = ebit - 10 + 5
    tax = round(pretax * 0.21, 2)
    return {
        "date": f"{year}-12-31", "revenue": rev * M, "costOfRevenue": cogs * M,
        "operatingIncome": ebit * M, "interestExpense": 10 * M,
        "interestIncome": 5 * M, "incomeBeforeTax": pretax * M,
        "incomeTaxExpense": tax * M, "netIncome": (pretax - tax) * M,
    }


def _balance(i, year):
    tca = CASH[i] + AR[i] + INV[i] + OTHER_CA[i]
    ta = tca + PPE[i] + 100 + 40                     # + goodwill + other NCA
    tcl = AP[i] + OTHER_CL[i]
    tl = tcl + 200 + 50                              # + LTD + other NCL
    te = ta - tl
    return {
        "date": f"{year}-12-31",
        "cashAndShortTermInvestments": CASH[i] * M, "netReceivables": AR[i] * M,
        "inventory": INV[i] * M, "totalCurrentAssets": tca * M,
        "propertyPlantEquipmentNet": PPE[i] * M, "goodwill": 100 * M,
        "intangibleAssets": 0, "totalAssets": ta * M,
        "accountPayables": AP[i] * M, "totalCurrentLiabilities": tcl * M,
        "shortTermDebt": 0, "longTermDebt": 200 * M, "totalLiabilities": tl * M,
        "commonStock": 100 * M, "retainedEarnings": RE[i] * M,
        "totalStockholdersEquity": te * M, "totalEquity": te * M,
    }


def _cashflow(i, year):
    return {
        "date": f"{year}-12-31", "capitalExpenditure": -(70 + 5 * i) * M,
        "dividendsPaid": -50 * M, "depreciationAndAmortization": DNA[i] * M,
        "netCashProvidedByOperatingActivities": 200 * M,
    }


@pytest.fixture
def simpleco_raw():
    prof = {"companyName": "SimpleCo Inc", "currency": "USD",
            "price": 50.0, "marketCap": 750 * M, "beta": 1.1, "range": "40-60"}
    inc = [_income(2022, 900, 360, 180, 45)] + [
        _income(YEARS[i], REV[i], COGS[i], EBIT[i], DNA[i]) for i in range(3)]
    bs = [_balance(i, YEARS[i]) for i in range(3)]
    cf = [_cashflow(i, YEARS[i]) for i in range(3)]
    return prof, inc, bs, cf


@pytest.fixture
def simpleco(simpleco_raw):
    from three_statement.data_layer import parse_financials
    prof, inc, bs, cf = simpleco_raw
    return parse_financials("SMPL", prof, inc, bs, cf, n_hist=3)


def company_data(ticker, name, price, mkt_cap_mm, scale=1.0):
    """A scaled SimpleCo clone with its own market data — statements stay
    internally consistent under linear scaling. For multi-company models."""
    from three_statement.data_layer import parse_financials

    def sc(d):
        return {k: (v * scale if isinstance(v, (int, float)) and k != "date"
                    else v) for k, v in d.items()}

    prof = {"companyName": name, "currency": "USD", "price": price,
            "marketCap": mkt_cap_mm * M, "beta": 1.0, "range": "10-99"}
    inc = [sc(_income(2022, 900, 360, 180, 45))] + \
        [sc(_income(YEARS[i], REV[i], COGS[i], EBIT[i], DNA[i]))
         for i in range(3)]
    bs = [sc(_balance(i, YEARS[i])) for i in range(3)]
    cf = [sc(_cashflow(i, YEARS[i])) for i in range(3)]
    return parse_financials(ticker, prof, inc, bs, cf, n_hist=3)


@pytest.fixture(scope="module")
def simpleco_module():
    """Module-scoped twin of `simpleco` for expensive report-build fixtures."""
    from three_statement.data_layer import parse_financials
    prof = {"companyName": "SimpleCo Inc", "currency": "USD",
            "price": 50.0, "marketCap": 750 * M, "beta": 1.1, "range": "40-60"}
    inc = [_income(2022, 900, 360, 180, 45)] + [
        _income(YEARS[i], REV[i], COGS[i], EBIT[i], DNA[i]) for i in range(3)]
    bs = [_balance(i, YEARS[i]) for i in range(3)]
    cf = [_cashflow(i, YEARS[i]) for i in range(3)]
    return parse_financials("SMPL", prof, inc, bs, cf, n_hist=3)

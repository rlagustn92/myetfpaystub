"""저장 파일에서 들어온 값을 얼마나 잘 견디는가 + 0 과 None 의 구분."""

from __future__ import annotations

from datetime import date

from models.distribution import Distribution, DistributionSeries
from models.numbers import is_finite_number, safe_float, safe_int
from models.portfolio import Holding, Portfolio


# ---------------------------------------------------------------- numbers
def test_true_is_not_a_number():
    # float(True) 가 1.0 이라 "shares": true 가 조용히 1주가 되어버립니다.
    assert is_finite_number(True) is False
    assert safe_float(True, default=0.0) == 0.0


def test_numeric_string_is_accepted():
    assert is_finite_number("100") is True
    assert safe_float("100") == 100.0


def test_infinity_and_nan_do_not_crash():
    assert safe_float(float("inf"), default=0.0) == 0.0
    assert safe_float(float("nan"), default=0.0) == 0.0
    assert safe_int("많이", default=0) == 0


def test_safe_float_clamps():
    assert safe_float(-5, minimum=0.0) == 0.0
    assert safe_float(500, maximum=100.0) == 100.0


# ---------------------------------------------------------------- Holding
def test_korean_code_keeps_leading_zero():
    # "5930" 을 정수로 다루다 앞의 0 이 날아가는 사고가 흔합니다.
    h = Holding.from_dict({"ticker": "5930", "market": "KR"})
    assert h.ticker == "005930"


def test_market_is_guessed_when_missing():
    assert Holding.from_dict({"ticker": "069500"}).market == "KR"
    assert Holding.from_dict({"ticker": "schd"}).market == "US"
    assert Holding.from_dict({"ticker": "schd"}).ticker == "SCHD"


def test_broken_row_returns_none_instead_of_raising():
    assert Holding.from_dict({}) is None
    assert Holding.from_dict({"ticker": "  "}) is None
    assert Holding.from_dict("문자열") is None


def test_garbage_numbers_become_zero_not_crash():
    h = Holding.from_dict({"ticker": "SCHD", "shares": "많이", "avg_price": None})
    assert h.shares == 0.0 and h.avg_price == 0.0


def test_cost_and_where():
    h = Holding(ticker="SCHD", market="US", shares=10, avg_price=70.0,
                broker="키움증권", account="일반")
    assert h.cost_native == 700.0
    assert h.currency == "USD"
    assert h.where() == "키움증권 · 일반"
    assert Holding(ticker="X", market="US").where() == "계좌 미지정"


# ---------------------------------------------------------------- Portfolio
def test_one_broken_row_does_not_lose_the_others():
    p = Portfolio.from_dict({"holdings": [
        {"ticker": "069500", "market": "KR", "shares": 10},
        {},                                   # 못 쓰는 줄
        {"ticker": "SCHD", "market": "US", "shares": 5},
    ]})
    assert [h.ticker for h in p.holdings] == ["069500", "SCHD"]


def test_same_etf_in_three_accounts_is_one_ticker():
    p = Portfolio()
    for broker in ("미래에셋증권", "키움증권", "삼성증권"):
        p.add(Holding(ticker="SCHD", market="US", broker=broker, shares=10))
    assert len(p.holdings) == 3
    assert p.tickers() == [("US", "SCHD")]      # 시세 조회는 한 번만
    assert len(p.brokers_in_use()) == 3


def test_remove_by_id():
    p = Portfolio()
    h = Holding(ticker="SCHD", market="US")
    p.add(h)
    assert p.remove(h.id) is True
    assert p.remove("없는id") is False


# ---------------------------------------------------------------- Distribution
def test_zero_tax_basis_is_known_but_none_is_not():
    """0원은 '발표된 값', None 은 '모름'. 이 둘을 섞으면 세금을 오해합니다."""
    announced_zero = Distribution(ticker="X", payment_date=date(2026, 9, 1),
                                  distribution_per_share=177.0, tax_basis_per_share=0.0)
    unknown = Distribution(ticker="X", payment_date=date(2026, 9, 1),
                           distribution_per_share=177.0, tax_basis_per_share=None)
    assert announced_zero.has_tax_basis is True
    assert unknown.has_tax_basis is False
    assert announced_zero.tax_basis_for(100) == 0.0
    assert unknown.tax_basis_for(100) is None


def test_amount_scales_with_shares():
    d = Distribution(ticker="X", payment_date=date(2026, 9, 1),
                     distribution_per_share=300.0, tax_basis_per_share=2.0)
    assert d.amount_for(500) == 150_000.0
    assert d.tax_basis_for(500) == 1_000.0


def test_series_filters_by_month_and_range():
    items = [
        Distribution(ticker="X", payment_date=date(2026, 7, 5), distribution_per_share=1),
        Distribution(ticker="X", payment_date=date(2026, 9, 5), distribution_per_share=2),
        Distribution(ticker="X", payment_date=date(2026, 9, 25), distribution_per_share=3),
    ]
    s = DistributionSeries(ticker="X", items=items)
    assert len(s.in_month(2026, 9)) == 2
    assert len(s.in_range(date(2026, 8, 1), date(2026, 12, 31))) == 2
    assert s.latest().payment_date == date(2026, 9, 25)


def test_empty_series_has_no_latest():
    assert DistributionSeries(ticker="X", items=[]).latest() is None

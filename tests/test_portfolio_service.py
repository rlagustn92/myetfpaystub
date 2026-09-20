"""자산 계산 — 국내/미국 섞임, 환율, 같은 ETF 여러 계좌, 수량 0, 데이터 없음."""

from __future__ import annotations

from datetime import date

from conftest import kr, us

from data.providers.base import PriceQuote
from models.portfolio import Holding, Portfolio
from services import portfolio_service as PS

FX = 1400.0


def q(ticker, price, currency, market_source="테스트"):
    return PriceQuote(ticker=ticker, price=price, currency=currency,
                      as_of=date(2026, 9, 18), source=market_source)


def test_korean_only():
    p = Portfolio()
    p.add(kr(shares=100, avg=30000))
    s = PS.summarize(p, quotes={("KR", "069500"): q("069500", 35000, "KRW")}, usdkrw=FX)
    assert s.total_value_krw == 3_500_000
    assert s.total_cost_krw == 3_000_000
    assert s.total_profit_krw == 500_000
    assert round(s.profit_rate, 4) == round(500_000 / 3_000_000 * 100, 4)


def test_us_is_converted_with_fx():
    p = Portfolio()
    p.add(us(shares=10, avg=70.0))
    s = PS.summarize(p, quotes={("US", "SCHD"): q("SCHD", 80.0, "USD")}, usdkrw=FX)
    assert s.total_value_krw == 10 * 80.0 * FX
    assert s.total_cost_krw == 10 * 70.0 * FX


def test_missing_price_is_excluded_not_counted_as_zero():
    """가격을 못 가져온 종목을 0 으로 세면 자산이 줄어든 것처럼 보입니다."""
    p = Portfolio()
    p.add(kr(shares=100, avg=30000))
    p.add(us(shares=10, avg=70.0))
    s = PS.summarize(p, quotes={
        ("KR", "069500"): q("069500", 35000, "KRW"),
        ("US", "SCHD"): "[SCHD] 가격을 확인하지 못했습니다.",
    }, usdkrw=FX)
    assert s.total_value_krw == 3_500_000          # 미국분이 0 으로 안 들어감
    assert s.total_cost_krw == 3_000_000           # 원가에서도 빠짐 (손익이 왜곡되지 않게)
    assert s.has_missing and len(s.missing) == 1


def test_missing_fx_excludes_us_holding():
    """환율을 모르면 달러 종목을 임의 환율로 채우지 않고 뺍니다."""
    p = Portfolio()
    p.add(us(shares=10, avg=70.0))
    s = PS.summarize(p, quotes={("US", "SCHD"): q("SCHD", 80.0, "USD")}, usdkrw=None)
    assert s.total_value_krw == 0
    assert s.has_missing


def test_zero_shares_contributes_nothing():
    p = Portfolio()
    p.add(kr(shares=0, avg=30000))
    s = PS.summarize(p, quotes={("KR", "069500"): q("069500", 35000, "KRW")}, usdkrw=FX)
    assert s.total_value_krw == 0 and s.total_cost_krw == 0
    assert not s.has_missing            # 값을 못 가져온 게 아니라 '0주'인 것


def test_same_etf_across_accounts_is_merged():
    p = Portfolio()
    p.add(Holding(ticker="SCHD", market="US", name="SCHD", broker="미래에셋증권",
                  account="ISA", shares=100, avg_price=70.0))
    p.add(Holding(ticker="SCHD", market="US", name="SCHD", broker="키움증권",
                  account="일반", shares=50, avg_price=72.0))
    p.add(Holding(ticker="SCHD", market="US", name="SCHD", broker="삼성증권",
                  account="일반", shares=30, avg_price=60.0))
    s = PS.summarize(p, quotes={("US", "SCHD"): q("SCHD", 80.0, "USD")}, usdkrw=FX)
    groups = PS.group_by_ticker(s)
    assert len(groups) == 1
    g = groups[0]
    assert g.total_shares == 180
    # 가중평균: (100*70 + 50*72 + 30*60) / 180
    assert round(g.avg_price, 6) == round((100 * 70 + 50 * 72 + 30 * 60) / 180, 6)
    assert g.value_krw(FX) == 180 * 80.0 * FX


def test_group_by_broker_splits_accounts():
    p = Portfolio()
    p.add(kr(broker="미래에셋증권", account="ISA", shares=100, avg=30000))
    p.add(kr(broker="미래에셋증권", account="연금저축", shares=50, avg=30000))
    p.add(kr(broker="키움증권", account="일반", shares=10, avg=30000))
    s = PS.summarize(p, quotes={("KR", "069500"): q("069500", 1000, "KRW")}, usdkrw=FX)
    groups = {g.broker: g for g in PS.group_by_broker(s)}
    assert groups["미래에셋증권"].value_krw == 150_000
    assert groups["미래에셋증권"].accounts == {"ISA": 100_000, "연금저축": 50_000}
    assert groups["키움증권"].value_krw == 10_000


def test_empty_portfolio_is_all_zero_and_does_not_crash():
    s = PS.summarize(Portfolio(), quotes={}, usdkrw=FX)
    assert s.total_value_krw == 0 and s.total_cost_krw == 0
    assert s.profit_rate is None
    assert PS.group_by_ticker(s) == []
    assert PS.group_by_broker(s) == []


def test_data_as_of_is_the_earliest_close_used():
    p = Portfolio()
    p.add(kr())
    p.add(us())
    s = PS.summarize(p, quotes={
        ("KR", "069500"): PriceQuote("069500", 1000, "KRW", date(2026, 9, 18), "t"),
        ("US", "SCHD"): PriceQuote("SCHD", 80.0, "USD", date(2026, 9, 17), "t"),
    }, usdkrw=FX)
    assert s.data_as_of == date(2026, 9, 17)

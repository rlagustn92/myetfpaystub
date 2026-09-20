"""
tests/conftest.py  --  테스트 공통 준비

여기 테스트는 **네트워크를 타지 않습니다.** 실제 시세/운용사 API 를 부르는 테스트는
`@pytest.mark.network` 를 붙이고 기본 실행에서 제외합니다. 인터넷이 끊겨도, 운용사
사이트가 잠깐 죽어도 단위 테스트는 전부 돌아야 합니다.
"""

from __future__ import annotations

import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402
from data.providers import cache  # noqa: E402
from models.distribution import Distribution, DistributionSeries  # noqa: E402
from models.portfolio import Holding, Portfolio  # noqa: E402
from services.distribution_service import TickerDistributions  # noqa: E402


@pytest.fixture(autouse=True)
def clean_cache():
    """테스트끼리 캐시가 새지 않게 합니다."""
    cache.invalidate()
    yield
    cache.invalidate()


def kr(ticker="069500", name="KODEX 200", broker="미래에셋증권", account="ISA",
       shares=100.0, avg=30000.0) -> Holding:
    return Holding(ticker=ticker, market="KR", name=name, broker=broker,
                   account=account, account_type=account, shares=shares, avg_price=avg)


def us(ticker="SCHD", name="Schwab US Dividend Equity ETF", broker="키움증권",
       account="일반", shares=100.0, avg=70.0) -> Holding:
    return Holding(ticker=ticker, market="US", name=name, broker=broker,
                   account=account, account_type=account, shares=shares, avg_price=avg)


def dist(ticker="069500", day=(2026, 9, 15), amount=300.0, tax=2.0,
         currency="KRW", status=config.STATUS_CONFIRMED) -> Distribution:
    return Distribution(
        ticker=ticker, payment_date=date(*day), distribution_per_share=amount,
        tax_basis_per_share=tax, currency=currency, source="테스트", status=status,
    )


def td(ticker="069500", items=None, supported=True, market="KR") -> TickerDistributions:
    items = items if items is not None else [dist(ticker)]
    return TickerDistributions(
        market=market, ticker=ticker, name=ticker,
        series=DistributionSeries(ticker=ticker, items=items, source="테스트",
                                  tax_basis_supported=supported),
    )


@pytest.fixture
def portfolio() -> Portfolio:
    p = Portfolio(name="테스트")
    p.add(kr())
    p.add(us())
    return p

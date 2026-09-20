"""
진짜로 살아 있는지 확인하는 테스트  (`pytest -m network`)
==========================================================

기본 실행에서는 **제외**됩니다. 인터넷이 끊겨도, 운용사 사이트가 잠깐 죽어도
단위 테스트는 전부 돌아야 하니까요.

이 파일의 목적은 하나입니다 — **운용사가 구조를 바꾸면 알아차리기.**
위 단위 테스트들은 우리가 저장해 둔 응답 조각으로만 검증하므로, 저쪽이 필드
이름을 바꾸면 조용히 통과합니다. 여기는 실제로 호출해서 확인합니다.

    python -m pytest -m network -q

느립니다(TIGER 는 달마다 호출해야 해서 20초쯤). 배포 전에 한 번씩 돌리세요.
"""

from __future__ import annotations

import pytest

from data.providers import fx_provider
from data.providers.issuer import registry
from data.providers.price_provider import get_price_provider

pytestmark = pytest.mark.network


# 브랜드별로 "분배금도 있고 과세표준도 발표하는" 대표 종목 하나씩.
LIVE_CASES = [
    ("498400", "KODEX 200타겟위클리커버드콜", "KODEX"),
    ("360750", "TIGER 미국S&P500", "TIGER"),
    ("402970", "ACE 미국배당다우존스", "ACE"),
    ("069500", "KODEX 200", "KODEX"),
    ("161510", "PLUS 고배당주", "PLUS"),
    ("473330", "SOL 미국30년국채커버드콜(합성)", "SOL"),
]


@pytest.mark.parametrize("code,name,brand", LIVE_CASES)
def test_issuer_still_serves_distributions_and_tax_basis(code, name, brand):
    s = registry.get_distributions("KR", code, name)
    assert s.source == brand, f"{code} 가 {brand} 가 아니라 {s.source} 로 떨어졌습니다"
    assert len(s) > 0, f"{code} 분배 이력이 비었습니다"
    assert s.tax_basis_supported is True
    # 최근 12건 중 과세표준이 하나도 없으면 필드 이름이 바뀐 것일 수 있습니다.
    recent = s.sorted_desc()[:12]
    assert any(d.has_tax_basis for d in recent), \
        f"{code} 최근 12건에 과세표준이 하나도 없습니다 — 응답 구조가 바뀌었는지 확인하세요"


@pytest.mark.parametrize("code,name,brand", LIVE_CASES)
def test_tax_basis_is_never_larger_than_the_distribution(code, name, brand):
    """과세표준이 분배금보다 크면 잘못된 필드를 읽고 있는 것입니다.

    SOL 의 TAX_PRI(과세기준가격, 9,102원) 를 과세표준으로 착각하면 여기서 걸립니다.
    """
    s = registry.get_distributions("KR", code, name)
    for d in s.sorted_desc()[:12]:
        if d.has_tax_basis:
            assert d.tax_basis_per_share <= d.distribution_per_share + 1e-9, \
                f"{code} {d.payment_date}: 과세표준 {d.tax_basis_per_share} > 분배금 {d.distribution_per_share}"


def test_unknown_issuer_falls_back_without_pretending_to_know_tax_basis():
    """조사하지 않은 운용사(KOSEF 등)는 분배금만 오고 과세표준은 '모름' 이어야 합니다."""
    s = registry.get_distributions("KR", "069660", "KOSEF 200")
    assert len(s) > 0
    assert s.tax_basis_supported is False
    assert all(d.tax_basis_per_share is None for d in s.items)


def test_us_distributions_are_fully_taxable():
    s = registry.get_distributions("US", "SCHD")
    assert len(s) > 0 and s.tax_basis_supported is True
    d = s.latest()
    assert d.tax_basis_per_share == d.distribution_per_share


def test_prices_and_fx():
    kr = get_price_provider("KR").get_latest_price("069500")
    us = get_price_provider("US").get_latest_price("SCHD")
    fx = fx_provider.get_latest_rate()
    assert kr.price > 0 and kr.currency == "KRW"
    assert us.price > 0 and us.currency == "USD"
    assert 500 < fx.rate < 3000       # 말이 되는 범위인지만 봅니다

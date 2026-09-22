"""
밖에 몇 번 나갔는지 세는 눈금.

왜 이 테스트가 있나
-------------------
무료 소스에 막히면 **앱이 통째로 쓸모없어집니다.** 그런데 운용사 호출만
세고 있었고 **시세·환율은 아무도 안 세고 있었습니다.** 세는 코드는 화면이
똑같아 보여서, 잘못 세도(또는 아예 안 세도) 눈으로는 모릅니다.
"""

from __future__ import annotations

import pytest

import config
from data.providers import callmeter
from data.providers.base import DataUnavailable


@pytest.fixture(autouse=True)
def clean():
    callmeter.reset()
    yield
    callmeter.reset()


def test_counts_are_kept_per_source():
    callmeter.spend("price")
    callmeter.spend("price")
    callmeter.spend("fx")
    assert callmeter.used_today("price") == 2
    assert callmeter.used_today("fx") == 1
    assert callmeter.used_today() == 3          # 비우면 전부 더합니다
    assert callmeter.breakdown_today() == {"price": 2, "fx": 1}


def test_an_unused_source_is_zero_not_an_error():
    assert callmeter.used_today("price") == 0


def test_the_budget_stops_us_before_someone_else_does():
    """남이 우리를 막기 전에 우리가 먼저 멈춥니다. 막히면 그 소스만 죽는 게
    아니라 화면 전체가 '가격을 확인하지 못했습니다' 가 됩니다."""
    for _ in range(3):
        callmeter.spend("price", budget=3)
    with pytest.raises(DataUnavailable):
        callmeter.spend("price", budget=3)
    # 한도를 넘은 호출은 **세지도 않습니다** — 나가지 않았으니까요.
    assert callmeter.used_today("price") == 3


def test_the_budget_is_shared_across_sources():
    """시세와 환율은 같은 주머니를 씁니다. 한쪽이 폭주해도 멈춰야 합니다."""
    callmeter.spend("price", budget=2)
    callmeter.spend("fx", budget=2)
    with pytest.raises(DataUnavailable):
        callmeter.spend("price", budget=2)


def test_the_default_budget_comes_from_config():
    assert config.PRICE_DAILY_CALL_BUDGET > 0
    for _ in range(5):
        callmeter.spend("price")
    assert callmeter.used_today() == 5          # 기본 한도에 한참 못 미침


def test_counting_happens_where_the_call_actually_goes_out():
    """⚠ 캐시에서 꺼내 쓴 것은 **안 셉니다.** 그래야 이 숫자가 "캐시가 잘
    듣고 있나" 를 말해 줍니다. 세는 자리가 캐시 **안쪽**(`_load`)이어야
    하는 이유입니다. 밖으로 한 줄만 옮기면 캐시 적중까지 세는데, 숫자가
    커질 뿐 에러가 안 나서 모릅니다.
    """
    import io
    import re

    from data.providers import fx_provider, price_provider

    allowed = {"_load", "_yf_history", "_fdr_history"}
    seen = 0
    for mod in (price_provider, fx_provider):
        src = io.open(mod.__file__, encoding="utf-8").read()
        for hit in re.finditer(r"callmeter\.spend\(", src):
            head = src.rindex("def ", 0, hit.start())
            name = src[head + 4:src.index("(", head)]
            assert name in allowed, f"{mod.__name__}: {name} 안에서 세고 있습니다"
            seen += 1
    assert seen == 4, "시세 2곳 · 환율 2곳에서 세야 합니다"

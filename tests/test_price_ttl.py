"""
최신가를 얼마나 오래 우려먹는가.

왜 이 테스트가 있나
-------------------
무료 소스에 막히면 **앱이 통째로 쓸모없어집니다.** 그런데 호출을 줄이는 코드는
줄여도 화면이 똑같아 보여서, 잘못 줄여도(또는 안 줄어들어도) 눈으로는 모릅니다.

제일 큰 낭비는 **장이 닫혀 있는 시간**이었습니다. 밤·주말에는 종가가 아예
안 바뀌는데 30분마다 다시 받고 있었습니다. 하루의 절반 이상이 그렇습니다.
"""

from __future__ import annotations

from datetime import datetime

import pytest

import config
from data.providers import price_provider as PP
from models.portfolio import MARKET_KR, MARKET_US

OPEN = config.CACHE_TTL_LATEST_PRICE_SECONDS
SHUT = config.CACHE_TTL_LATEST_PRICE_CLOSED_SECONDS


def at(y, m, d, hh, mm=0) -> datetime:
    return datetime(y, m, d, hh, mm)


# 2026-09-22 는 화요일입니다.
def test_korean_market_hours():
    assert PP.market_is_open(MARKET_KR, at(2026, 9, 22, 10)) is True
    assert PP.market_is_open(MARKET_KR, at(2026, 9, 22, 8, 59)) is False   # 개장 전
    assert PP.market_is_open(MARKET_KR, at(2026, 9, 22, 16)) is False      # 마감 후


def test_korean_market_is_shut_on_the_weekend():
    assert PP.market_is_open(MARKET_KR, at(2026, 9, 26, 11)) is False      # 토
    assert PP.market_is_open(MARKET_KR, at(2026, 9, 27, 11)) is False      # 일


def test_us_market_spans_midnight_in_korean_time():
    """미국장은 한국 시간으로 **밤에 열려 다음 날 새벽에 닫힙니다.**
    날짜가 넘어가므로 요일 판단을 그냥 하면 틀립니다."""
    assert PP.market_is_open(MARKET_US, at(2026, 9, 22, 23)) is True       # 화 밤
    assert PP.market_is_open(MARKET_US, at(2026, 9, 23, 3)) is True        # 수 새벽
    assert PP.market_is_open(MARKET_US, at(2026, 9, 22, 14)) is False      # 화 낮


def test_us_friday_night_runs_into_saturday_dawn():
    """금요일 밤 장은 **토요일 새벽**에 끝납니다. 토요일을 통째로 닫힌 것으로
    보면 그 시간 가격이 멈춘 것처럼 보입니다."""
    assert PP.market_is_open(MARKET_US, at(2026, 9, 26, 3)) is True        # 토 새벽
    assert PP.market_is_open(MARKET_US, at(2026, 9, 26, 23)) is False      # 토 밤
    assert PP.market_is_open(MARKET_US, at(2026, 9, 27, 23)) is False      # 일 밤


def test_each_market_gets_its_own_clock():
    """⭐ 한국과 미국은 **열리는 시간이 정반대**입니다. 하나의 시계로 판단하면
    한쪽은 반드시 틀립니다 — 한국 낮에 미국 종목을 '장중' 으로 보거나,
    한국 밤에 미국 종목을 '마감' 으로 보게 됩니다.
    """
    # 한국 낮 — 한국장만 열려 있습니다
    assert PP.latest_price_ttl(MARKET_KR, at(2026, 9, 22, 10)) == OPEN
    assert PP.latest_price_ttl(MARKET_US, at(2026, 9, 22, 10)) == SHUT
    # 한국 밤 — 미국장만 열려 있습니다
    assert PP.latest_price_ttl(MARKET_KR, at(2026, 9, 22, 23)) == SHUT
    assert PP.latest_price_ttl(MARKET_US, at(2026, 9, 22, 23)) == OPEN
    # 한국 새벽 — 미국장은 아직 열려 있습니다
    assert PP.latest_price_ttl(MARKET_US, at(2026, 9, 23, 3)) == OPEN


def test_ttl_is_long_while_that_market_is_shut():
    """닫혀 있으면 값이 안 바뀝니다. 다시 받을 이유가 없습니다."""
    assert PP.latest_price_ttl(MARKET_KR, at(2026, 9, 22, 16)) == SHUT   # 마감 후
    assert PP.latest_price_ttl(MARKET_KR, at(2026, 9, 26, 10)) == SHUT   # 토
    assert PP.latest_price_ttl(MARKET_US, at(2026, 9, 27, 23)) == SHUT   # 일 밤


def test_the_two_markets_never_use_the_short_ttl_at_the_same_time():
    """한국 낮과 미국 밤은 안 겹칩니다. 겹친다면 창을 잘못 잡은 것입니다."""
    for hour in range(24):
        when = at(2026, 9, 22, hour)
        both = (PP.latest_price_ttl(MARKET_KR, when) == OPEN
                and PP.latest_price_ttl(MARKET_US, when) == OPEN)
        assert not both, f"{hour}시에 두 시장이 같이 열려 있다고 봅니다"


def test_each_market_actually_gets_some_short_ttl_hours():
    """둘 다 항상 긴 주기면 이 기능이 아무것도 안 하는 것입니다."""
    kr = [h for h in range(24)
          if PP.latest_price_ttl(MARKET_KR, at(2026, 9, 22, h)) == OPEN]
    us = [h for h in range(24)
          if PP.latest_price_ttl(MARKET_US, at(2026, 9, 22, h)) == OPEN]
    assert kr == [9, 10, 11, 12, 13, 14, 15]
    assert us == [0, 1, 2, 3, 4, 5, 6, 22, 23]


def test_the_shut_ttl_is_actually_longer():
    """둘이 같으면 이 기능이 아무것도 안 하는 것입니다."""
    assert SHUT > OPEN


@pytest.mark.parametrize("market", [MARKET_KR, MARKET_US])
def test_price_lookup_asks_the_cache_to_recheck_the_ttl(market):
    """⚠ 유효기간을 **저장할 때** 고정하면, 장 마감 직전에 받은 값이 밤새
    30분마다 다시 받아집니다. 읽을 때마다 다시 정해야(`ttl_of`) 합니다."""
    src = io.open(PP.__file__, encoding="utf-8").read()
    assert src.count("ttl_of=lambda _q: latest_price_ttl(") == 2


import io  # noqa: E402  (위 테스트에서만 씁니다)

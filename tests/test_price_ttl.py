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


def test_ttl_is_long_while_the_market_is_shut():
    """닫혀 있으면 값이 안 바뀝니다. 다시 받을 이유가 없습니다."""
    assert PP.latest_price_ttl(MARKET_KR, at(2026, 9, 22, 10)) == OPEN     # 화 장중
    assert PP.latest_price_ttl(MARKET_KR, at(2026, 9, 22, 16)) == SHUT     # 마감 후
    assert PP.latest_price_ttl(MARKET_KR, at(2026, 9, 26, 10)) == SHUT     # 토


def test_quiet_hours_win_even_if_a_market_is_open():
    """밤 8시~아침 8시에는 **볼 사람이 없습니다.** 그 시간에 30분마다 다시
    받아봐야 무료 소스에 막힐 위험만 큽니다(사용자 결정).

    ⚠ 그 결과 **미국 종목은 사실상 항상 긴 주기**입니다. 미국장이 한국 시간
      22:00~06:30 이라 조용한 시간에 통째로 들어옵니다. 대신 한국 낮에는
      미국장이 닫혀 있어 종가가 안 바뀌므로 잃는 게 없습니다.
    """
    assert PP.is_quiet_hour(at(2026, 9, 23, 3)) is True
    assert PP.is_quiet_hour(at(2026, 9, 23, 21)) is True
    assert PP.is_quiet_hour(at(2026, 9, 23, 12)) is False

    assert PP.market_is_open(MARKET_US, at(2026, 9, 23, 3)) is True    # 열려 있어도
    assert PP.latest_price_ttl(MARKET_US, at(2026, 9, 23, 3)) == SHUT  # 길게 둡니다
    assert PP.latest_price_ttl(MARKET_US, at(2026, 9, 23, 14)) == SHUT


def test_the_short_ttl_only_happens_in_daytime_korean_hours():
    """짧은 주기가 걸리는 시간이 실제로 있어야 이 기능이 의미가 있습니다."""
    short = [h for h in range(24)
             if PP.latest_price_ttl(MARKET_KR, at(2026, 9, 22, h)) == OPEN]
    assert short == [9, 10, 11, 12, 13, 14, 15]


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

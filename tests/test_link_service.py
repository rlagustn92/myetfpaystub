"""
종목 바로가기 — 만들 수 있는 주소만 내보내는가.

왜 이 테스트가 있나
-------------------
**빈 페이지로 보내는 링크는 링크가 없는 것보다 나쁩니다.** 토스 웹은 SPA 라
아무 경로나 HTTP 200 을 돌려주고 화면만 "페이지를 찾을 수 없습니다" 가 됩니다.
즉 상태 코드로는 맞는 주소인지 알 수 없어서, 규칙이 확실한 것만 만듭니다.
주소 형태는 2026-09-21 에 브라우저로 직접 열어 확인했습니다.
"""

from __future__ import annotations

import pytest

from models.portfolio import MARKET_KR, MARKET_US
from services import link_service


def test_toss_korean_address_uses_the_krx_short_code():
    """토스는 6자리 코드 앞에 A 를 붙입니다 (확인: KODEX 200 화면이 열림)."""
    assert link_service.toss_url(MARKET_KR, "069500") == \
        "https://www.tossinvest.com/stocks/A069500"
    # 앞의 0 이 살아야 합니다. 정수로 다루면 69500 이 되어 다른 종목이 됩니다.
    assert link_service.toss_url(MARKET_KR, "69500").endswith("/A069500")
    # 영문이 섞인 코드도 그대로 (0219E0 같은 실제 코드가 있습니다)
    assert link_service.toss_url(MARKET_KR, "0219E0").endswith("/A0219E0")


def test_toss_has_no_address_for_us_stocks():
    """추측하면 빈 페이지로 보냅니다. /stocks/SCHD · /stocks/{ISIN} ·
    /us-stocks/SCHD 를 전부 열어 봤지만 종목 화면이 안 나왔습니다."""
    assert link_service.toss_url(MARKET_US, "SCHD") is None


def test_yahoo_uses_ks_for_kospi_and_kq_for_kosdaq(monkeypatch):
    """접미사를 틀리면 "Symbol not found" 로 갑니다."""
    monkeypatch.setattr(link_service.search_service, "kr_exchange",
                        lambda code: "KOSPI")
    assert link_service.yahoo_url(MARKET_KR, "069500") == \
        "https://finance.yahoo.com/quote/069500.KS"
    monkeypatch.setattr(link_service.search_service, "kr_exchange",
                        lambda code: "KOSDAQ GLOBAL")
    assert link_service.yahoo_url(MARKET_KR, "035720").endswith(".KQ")


def test_yahoo_falls_back_to_kospi_when_the_exchange_is_unknown(monkeypatch):
    """한국 ETF 는 전부 코스피입니다. 모를 때 .KS 가 맞는 기본값입니다."""
    monkeypatch.setattr(link_service.search_service, "kr_exchange", lambda code: "")
    assert link_service.yahoo_url(MARKET_KR, "498400").endswith("498400.KS")


def test_yahoo_us_is_just_the_ticker():
    assert link_service.yahoo_url(MARKET_US, "schd") == \
        "https://finance.yahoo.com/quote/SCHD"


@pytest.mark.parametrize("bad", ["", "   ", None])
def test_empty_ticker_makes_no_link(bad):
    assert link_service.toss_url(MARKET_KR, bad) is None
    assert link_service.yahoo_url(MARKET_US, bad) is None


def test_korean_gets_three_links_and_us_gets_two(monkeypatch):
    """미국에 토스가 없는 것은 **의도한 것**입니다. 네이버·야후가 덮습니다."""
    monkeypatch.setattr(link_service.naver_link_service, "url_for",
                        lambda m, t: "https://m.stock.naver.com/x")
    monkeypatch.setattr(link_service.search_service, "kr_exchange",
                        lambda code: "KOSPI")

    kr = dict(link_service.links_for(MARKET_KR, "069500"))
    assert set(kr) == {"Npay증권", "토스증권", "야후파이낸스"}

    us = dict(link_service.links_for(MARKET_US, "SCHD"))
    assert set(us) == {"Npay증권", "야후파이낸스"}


def test_a_source_that_fails_is_simply_left_out(monkeypatch):
    """네이버 자동완성이 죽어도 나머지 바로가기는 살아 있어야 합니다."""
    monkeypatch.setattr(link_service.naver_link_service, "url_for",
                        lambda m, t: None)
    monkeypatch.setattr(link_service.search_service, "kr_exchange",
                        lambda code: "KOSPI")
    labels = [n for n, _ in link_service.links_for(MARKET_KR, "069500")]
    assert labels == ["토스증권", "야후파이낸스"]

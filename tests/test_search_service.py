"""
종목 찾기 — 띄어쓰기를 몰라도 찾아지는가.

왜 이 테스트가 있나
-------------------
한국 ETF 이름은 "KODEX 200타겟위클리커버드콜" 처럼 길고, **어디서 띄는지 사람이
외울 수 없습니다.** 예전 검색은 친 글자가 이름에 통째로 들어 있어야만 찾았기
때문에 "커버 액티" 로는 아무것도 안 나왔습니다. 실제로 "검색 시스템이 너무
복잡하다" 는 지적을 받고 고쳤습니다.

목록을 실제로 받아오면 느리고 네트워크가 필요하므로, 여기서는 가짜 목록을
넣고 **고르는 규칙**만 검사합니다.
"""

from __future__ import annotations

import pytest

from models.portfolio import MARKET_KR, MARKET_US
from services import search_service as S

FAKE = [
    S.SearchHit(MARKET_KR, "069500", "KODEX 200", "ETF", "KOSPI"),
    S.SearchHit(MARKET_KR, "498400", "KODEX 200타겟위클리커버드콜", "ETF", "KOSPI"),
    S.SearchHit(MARKET_KR, "0219E0", "KODEX 200커버드콜액티브", "ETF", "KOSPI"),
    S.SearchHit(MARKET_KR, "441680", "TIGER 미국나스닥100커버드콜(합성)", "ETF", "KOSPI"),
    S.SearchHit(MARKET_KR, "402970", "ACE 미국배당다우존스", "ETF", "KOSPI"),
    S.SearchHit(MARKET_KR, "035720", "카카오", "STOCK", "KOSPI"),
    S.SearchHit(MARKET_KR, "247540", "에코프로비엠", "STOCK", "KOSDAQ"),
]


@pytest.fixture(autouse=True)
def fake_universe(monkeypatch):
    monkeypatch.setattr(S, "_kr_universe", lambda: list(FAKE))
    monkeypatch.setattr(S, "resolve_us_ticker", lambda t: None)


def names(query: str) -> list[str]:
    return [h.name for h in S.search(query)]


# ------------------------------------------------- 조각을 여러 개 치기
def test_two_fragments_match_in_any_order():
    """"커버 액티" 는 두 조각이 **다 들어간** 것만 찾아야 합니다."""
    assert names("커버 액티") == ["KODEX 200커버드콜액티브"]
    assert names("액티 커버") == ["KODEX 200커버드콜액티브"]


def test_fragments_do_not_need_the_real_spacing():
    """진짜 이름은 "200타겟위클리커버드콜" 처럼 다 붙어 있습니다."""
    got = names("200 커버")
    assert "KODEX 200타겟위클리커버드콜" in got
    assert "KODEX 200커버드콜액티브" in got
    assert "KODEX 200" not in got            # "커버" 가 없으므로 빠져야 합니다


def test_a_fragment_can_be_the_start_of_a_word():
    """"액티" 로 "액티브" 가 잡혀야 합니다. 앞글자만 알아도 되게."""
    assert names("액티") == ["KODEX 200커버드콜액티브"]


def test_all_fragments_must_match():
    """하나라도 안 들어가면 안 나와야 합니다(AND, OR 아님)."""
    assert names("커버 없는단어") == []


# ------------------------------------------------- 띄어쓰기·기호 무시
def test_spacing_and_brackets_do_not_matter():
    full = "TIGER 미국나스닥100커버드콜(합성)"
    for q in ["나스닥 커버", "나스닥100커버드콜", "미국 나스닥 100", "커버드콜 합성"]:
        assert full in names(q), q


def test_a_glued_fragment_must_really_be_contiguous():
    """조각 **안에서는** 건너뛰지 않습니다. "나스닥커버드콜" 은 실제 이름에서
    사이에 "100" 이 끼어 있어 붙은 말이 아닙니다. 조각을 나눠 쳐야 합니다
    ("나스닥 커버"). 이걸 허용하면 아무 종목이나 걸려서 목록이 쓸모없어집니다."""
    assert names("나스닥커버드콜합성") == []
    assert "TIGER 미국나스닥100커버드콜(합성)" in names("나스닥 커버드콜 합성")


# ------------------------------------------------- 한글 운용사명
def test_issuer_names_work_in_korean():
    assert "KODEX 200" in names("코덱스 200")
    assert "TIGER 미국나스닥100커버드콜(합성)" in names("타이거 나스닥")
    assert "KODEX 200" in names("삼성 200")       # 운용사 실명으로도


def test_korean_issuer_name_works_without_a_space():
    assert "KODEX 200" in names("코덱스200")


# ------------------------------------------------- 순위
def test_exact_ticker_comes_first():
    assert names("069500")[0] == "KODEX 200"


def test_shorter_names_come_first_among_equally_good_matches():
    """조각을 똑같이 만족하면 짧은 이름이 대개 사용자가 찾던 것입니다."""
    got = names("커버")
    assert got == sorted(got, key=len)


def test_us_ticker_is_found():
    assert S.search("SCHD")[0].market == MARKET_US


# ------------------------------------------------- 안 해야 하는 것
def test_korean_query_never_asks_yfinance(monkeypatch):
    """한글도 `isalpha()` 가 True 라, 못 찾으면 yfinance 에 한글을 물어보며
    쓸데없이 기다렸다 404 를 받던 버그가 있었습니다."""
    called = []
    monkeypatch.setattr(S, "resolve_us_ticker", lambda t: called.append(t))
    assert S.search("없는한글종목") == []
    assert called == []


def test_empty_query_returns_nothing():
    assert S.search("") == [] and S.search("   ") == []


# ------------------------------------------------- 거래소 (야후 주소용)
def test_kr_exchange_reports_the_listing_venue():
    from data.providers import cache
    cache.invalidate("search:")      # 다른 테스트가 채워둔 목록을 비웁니다
    assert S.kr_exchange("069500") == "KOSPI"
    assert S.kr_exchange("247540") == "KOSDAQ"
    assert S.kr_exchange("999999") == ""      # 모르면 빈 문자열


def test_normalize_never_changes_what_the_user_sees():
    """정규화는 **비교용**입니다. 화면 이름은 원래 이름 그대로여야 합니다."""
    hit = S.search("나스닥 커버")[0]
    assert hit.name == "TIGER 미국나스닥100커버드콜(합성)"

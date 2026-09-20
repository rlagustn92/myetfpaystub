"""
화면이 실제로 켜지는지 — AppTest 로 app.py 를 돌려 봅니다.

단위 테스트가 다 통과해도 app.py 에서 오타 하나로 앱이 아예 안 켜질 수 있습니다.
그건 사용자에게는 "서비스가 죽은 것"이라 가장 큰 사고입니다.

네트워크를 타지 않도록 시세·분배금·카운터를 전부 가짜로 바꿉니다.
"""

from __future__ import annotations

import os
from datetime import date

import pytest
from streamlit.testing.v1 import AppTest

from data.providers.base import PriceQuote, FxQuote

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")


@pytest.fixture
def offline(monkeypatch):
    """바깥 세상을 전부 끊습니다."""
    from services import distribution_service, fx_service, portfolio_service, visitor_service
    calls = {"visits": 0}

    def fake_visit():
        calls["visits"] += 1
        return (1, 1)

    monkeypatch.setattr(visitor_service, "count_visit", fake_visit)
    monkeypatch.setattr(fx_service, "latest",
                        lambda: FxQuote("USD/KRW", 1400.0, date(2026, 9, 18), "테스트"))
    monkeypatch.setattr(fx_service, "on",
                        lambda d: FxQuote("USD/KRW", 1400.0, d, "테스트"))
    monkeypatch.setattr(portfolio_service, "fetch_quotes", lambda p: {
        (h.market, h.ticker): PriceQuote(h.ticker, 1000.0 if h.market == "KR" else 80.0,
                                         h.currency, date(2026, 9, 18), "테스트")
        for h in p.holdings
    })
    monkeypatch.setattr(distribution_service, "fetch_all", lambda p: {})
    return calls


def test_app_starts_with_an_empty_portfolio(offline):
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    text = " ".join(m.value for m in at.markdown)
    assert "MY ETF 급여명세서" in text
    assert "아직 등록된 ETF 가 없습니다" in text


def test_version_is_next_to_the_service_name(offline):
    import config
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert config.APP_VERSION in " ".join(m.value for m in at.markdown)


def test_visitor_counter_is_called_once_per_session_not_per_click(offline):
    """Streamlit 은 클릭할 때마다 스크립트를 처음부터 다시 돌립니다.
    세션 체크가 없으면 한 사람이 30번 누를 때 30명으로 세집니다."""
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert offline["visits"] == 1
    at.run()
    at.run()
    assert offline["visits"] == 1


def test_example_button_fills_the_screen(offline):
    at = AppTest.from_file(APP, default_timeout=90).run()
    buttons = [b for b in at.button if "예시" in b.label]
    assert buttons, "빈 화면에 '예시로 시작해보기' 가 있어야 합니다"
    buttons[0].click().run()
    assert not at.exception
    text = " ".join(m.value for m in at.markdown)
    assert "지금 내 ETF 자산" in text
    assert "ETF 월급" in text


def test_disclaimer_is_always_on_screen(offline):
    at = AppTest.from_file(APP, default_timeout=60).run()
    text = " ".join(m.value for m in at.markdown)
    assert "참고용" in text


def test_update_button_exists(offline):
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert any("정보 업데이트" in b.label for b in at.button)


# --------------------------------------------------------- 종목 추가 흐름
@pytest.fixture
def fake_search(monkeypatch):
    """종목 검색이 FinanceDataReader 목록(무겁습니다)을 타지 않게 합니다."""
    from services import search_service
    from models.portfolio import MARKET_US

    def fake(query, market="ALL", limit=30):
        if not query:
            return []
        return [search_service.SearchHit(MARKET_US, "SCHD",
                                         "Schwab US Dividend Equity ETF", "ETF")]

    monkeypatch.setattr(search_service, "search", fake)


def test_adding_a_holding_puts_it_on_the_home_screen(offline, fake_search):
    at = AppTest.from_file(APP, default_timeout=90).run()

    box = [t for t in at.text_input if "어떤 ETF" in t.label][0]
    box.set_value("SCHD").run()

    # 종목은 골랐지만 수량이 0이면 아직 저장할 수 없어야 합니다.
    assert [b for b in at.button if b.label == "저장"][0].disabled is True

    qty = [n for n in at.number_input if "몇 주" in n.label][0]
    qty.set_value(180).run()
    price = [n for n in at.number_input if "얼마에 샀나요" in n.label][0]
    price.set_value(30.5).run()

    [b for b in at.button if b.label == "저장"][0].click().run()
    assert not at.exception

    text = " ".join(m.value for m in at.markdown)
    assert "지금 내 ETF 자산" in text          # 빈 화면에서 홈 화면으로 넘어감
    assert "Schwab US Dividend Equity ETF" in text


def test_save_button_is_blocked_until_a_stock_and_amount_are_chosen(offline, fake_search):
    at = AppTest.from_file(APP, default_timeout=90).run()
    save = [b for b in at.button if b.label == "저장"][0]
    assert save.disabled is True              # 아무것도 안 골랐으면 못 누릅니다


def test_example_portfolio_lands_in_every_tab_without_error(offline, fake_search):
    at = AppTest.from_file(APP, default_timeout=120).run()
    [b for b in at.button if "예시" in b.label][0].click().run()
    assert not at.exception
    text = " ".join(m.value for m in at.markdown)
    assert "KODEX 200" in text
    # 탭 다섯 개가 다 그려졌는지 (AppTest 는 숨은 탭도 실행합니다)
    assert "분배금 달력" in text          # 월별 탭
    assert "포트폴리오 여러 개 두기" in text   # 저장 탭


def test_pitch_is_on_the_home_screen(offline, fake_search):
    at = AppTest.from_file(APP, default_timeout=120).run()
    [b for b in at.button if "예시" in b.label][0].click().run()
    assert not at.exception
    text = " ".join(m.value for m in at.markdown)
    assert "전술판" in text
    assert "유니폼 숫자" in text        # 등번호가 무슨 뜻인지 화면이 말해줘야 합니다


def test_pitch_slots_are_saved_with_the_portfolio(offline, fake_search):
    """자리를 바꿔놨는데 새로고침하면 흩어져 있으면 쓸모가 없습니다."""
    import json
    at = AppTest.from_file(APP, default_timeout=120).run()
    [b for b in at.button if "예시" in b.label][0].click().run()
    assert not at.exception
    store = at.session_state["store"]
    saved = json.loads(__import__("services.storage_service", fromlist=["x"]).dumps(store))
    slots = saved["profiles"][store.current]["slots"]
    assert len(slots) == 4                     # 예시 4종목 전부 자리를 받음
    assert len(set(slots.values())) == 4       # 겹치지 않음

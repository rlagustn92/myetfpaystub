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

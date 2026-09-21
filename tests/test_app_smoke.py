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
    assert "class='panel'" in text
    # 금액 카드가 실제로 채워졌는지 — 문구가 아니라 **구조**를 봅니다.
    assert "class='paycard'" in text


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
    # 평단가는 세 자리 콤마를 찍어야 해서 글자 칸입니다(number_input 은 콤마를
    # 못 찍습니다). 사람이 콤마를 넣어 쳐도 그대로 읽혀야 합니다.
    price = [t for t in at.text_input if "얼마에 샀나요" in t.label][0]
    price.set_value("30.5").run()

    [b for b in at.button if b.label == "저장"][0].click().run()
    assert not at.exception

    text = " ".join(m.value for m in at.markdown)
    assert "class='panel'" in text          # 빈 화면에서 홈 화면으로 넘어감
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
    assert "⚽" in text        # 이름은 바뀌어도 ⚽ 는 남깁니다
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


def test_skin_picker_changes_the_pitch_and_is_saved(offline, fake_search):
    """스킨을 골랐는데 새로고침하면 기본 잔디로 돌아가면 쓸모가 없습니다."""
    at = AppTest.from_file(APP, default_timeout=120).run()
    [b for b in at.button if "예시" in b.label][0].click().run()
    assert not at.exception

    box = [s for s in at.selectbox if "스킨" in s.label][0]
    target = [o for o in box.options if "London Red" in o][0]
    box.set_value(target).run()
    assert not at.exception
    assert at.session_state["store"].active().skin == "london-red"


def test_price_box_adds_thousand_separators(offline, fake_search):
    """평단가는 세 자리 콤마가 붙어야 합니다. `st.number_input` 은 콤마를 못
    찍어서(format 이 printf 라 자릿수 구분 기호가 없습니다) 글자 칸으로 받고
    직접 찍습니다."""
    import app as app_module

    assert app_module._format_money("32000") == "32,000"
    assert app_module._format_money("1234567") == "1,234,567"
    assert app_module._format_money("30.5") == "30.5"        # 달러 평단가
    assert app_module._format_money("1234.567") == "1,234.567"
    assert app_module._format_money("") == ""
    # 이미 콤마가 붙은 것을 다시 넣어도 망가지면 안 됩니다(엔터를 두 번 칩니다)
    assert app_module._format_money("32,000") == "32,000"

    # 사람이 콤마를 넣어 쳐도 숫자로 읽혀야 합니다
    assert app_module._parse_money("32,000") == 32000.0
    assert app_module._parse_money("₩ 1,234.5") == 1234.5
    assert app_module._parse_money("") == 0.0
    assert app_module._parse_money("abc") == 0.0


def test_amount_boxes_reset_when_a_different_stock_is_picked(offline, fake_search):
    """앞 종목의 수량·평단가가 남아 있으면 그대로 저장하게 됩니다(실제로
    잘못 눌렀다는 지적을 받았습니다). 증권사·계좌는 **그대로 둡니다** —
    같은 계좌에 여러 종목을 연달아 넣는 일이 흔합니다."""
    at = AppTest.from_file(APP, default_timeout=90).run()

    box = [t for t in at.text_input if "어떤 ETF" in t.label][0]
    box.set_value("SCHD").run()
    [n for n in at.number_input if "몇 주" in n.label][0].set_value(180).run()
    [t for t in at.text_input if "얼마에 샀나요" in t.label][0].set_value("30.5").run()

    broker_before = [s for s in at.selectbox if "어디에" in s.label][0].value

    # 저장하면 검색어·수량·평단가는 비고, 증권사는 남습니다.
    [b for b in at.button if b.label == "저장"][0].click().run()
    assert not at.exception
    assert [n for n in at.number_input if "몇 주" in n.label][0].value == 0.0
    assert [t for t in at.text_input if "얼마에 샀나요" in t.label][0].value == ""
    assert [t for t in at.text_input if "어떤 ETF" in t.label][0].value == ""
    assert [s for s in at.selectbox if "어디에" in s.label][0].value == broker_before


def test_tidy_button_rearranges_the_pitch(offline, fake_search):
    """⚽ 포지션 자동 정리는 **눌렀을 때만** 움직여야 합니다. 화면을 열 때마다
    자동으로 정리하면 손으로 맞춰둔 배치가 말없이 흐트러집니다."""
    at = AppTest.from_file(APP, default_timeout=120).run()
    [b for b in at.button if "예시" in b.label][0].click().run()

    tidy = [b for b in at.button if "자동 정리" in b.label]
    assert tidy, "전술판에 자동 정리 버튼이 없습니다"

    # 채권을 손으로 최전방에 올려두고, 다시 그려도 그대로인지 봅니다.
    p = at.session_state["store"].active()
    key = next(iter(p.slots))
    p.slots[key] = "ST-L"
    at.run()
    assert at.session_state["store"].active().slots[key] == "ST-L", \
        "버튼을 안 눌렀는데 자리가 바뀌었습니다"

    [b for b in at.button if "자동 정리" in b.label][0].click().run()
    assert not at.exception
    text = " ".join(m.value for m in at.markdown)
    assert "지금 배치" in text          # 포메이션 안내가 보입니다


def test_paste_import_registers_many_holdings_at_once(offline, fake_search):
    """진입장벽 — 증권사 세 곳에 종목이 열 개면 쉰 번을 타이핑해야 합니다.
    붙여넣기 한 번으로 끝나야 합니다."""
    at = AppTest.from_file(APP, default_timeout=120).run()

    box = [t for t in at.text_area if "붙여넣기" in t.label]
    assert box, "종목 관리에 붙여넣기 칸이 있어야 합니다"

    box[0].set_value(
        "종목코드\t수량\t평균단가\n"
        "069500\t100\t32,000\n"
        "458730\t50\t11,200"
    ).run()
    assert not at.exception

    btn = [b for b in at.button if "한 번에 등록" in b.label]
    assert btn, "읽어낸 줄이 있으면 등록 버튼이 나와야 합니다"
    btn[0].click().run()
    assert not at.exception

    p = at.session_state["store"].active()
    assert len(p.holdings) == 2
    assert {h.ticker for h in p.holdings} == {"069500", "458730"}
    assert p.holdings[0].shares == 100


def test_paste_import_never_keeps_an_account_number(offline, fake_search):
    """절대규칙 6 — 계좌번호는 저장은커녕 화면에도 안 올립니다."""
    at = AppTest.from_file(APP, default_timeout=120).run()
    box = [t for t in at.text_area if "붙여넣기" in t.label][0]
    box.set_value("종목코드\t계좌번호\t수량\t평균단가\n"
                  "069500\t123-45-678901\t100\t32,000").run()
    assert not at.exception
    text = " ".join(m.value for m in at.markdown)
    assert "123-45-678901" not in text
    assert "계좌번호" in text          # 버렸다고 알려는 줍니다


def test_every_grid_size_the_app_uses_exists_in_the_css():
    """`grid_html(cards, cols=N)` 을 쓰는데 CSS 에 `.grid.cN` 이 없으면 카드가
    **한 줄로 쭉 쌓입니다.** 에러가 안 나서 화면을 볼 때까지 모릅니다
    (실제로 종목별 상세의 5칸이 그랬습니다)."""
    import re

    app_src = open(APP, encoding="utf-8").read()
    css = open(os.path.join(os.path.dirname(APP), "components", "ui.py"),
               encoding="utf-8").read()
    used = {int(n) for n in re.findall(r"cols=(\d+)", app_src)}
    used |= {int(n) for n in re.findall(r"grid_html\([^)]*?,\s*(\d+)\)", app_src)}
    for n in used:
        assert f".grid.c{n}" in css, f"grid_html(cols={n}) 을 쓰는데 CSS 에 .grid.c{n} 이 없습니다"

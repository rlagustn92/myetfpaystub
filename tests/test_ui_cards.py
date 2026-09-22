"""
값 카드가 칸을 넘지 않는가.

왜 이 테스트가 있나
-------------------
평가손익은 사람에 따라 몇천만원, 몇억이 됩니다. 글자 크기를 고정해 두면
언젠가 반드시 칸을 넘치는데, **에러가 안 나고 화면만 깨집니다.**
실제로 "+₩416,675" 가 부호에서 잘려 "+" 만 윗줄에 남은 적이 있습니다.

CSS 는 글자 수를 셀 수 없어서 파이썬이 세어 `calc()` 로 넘깁니다.
그 계산이 어긋나지 않는지를 봅니다.
"""

from __future__ import annotations

import io
import re

from components import ui


def _divisor(style: str) -> float:
    """fit_style 이 만든 글자 수(units). 클수록 글자가 작아집니다."""
    got = re.search(r"/ ([0-9.]+)\)", style)
    assert got, style
    return float(got.group(1))


def test_a_longer_number_gets_a_smaller_font():
    """억 단위가 백만 단위보다 작게 나와야 같은 칸에 들어갑니다."""
    assert _divisor(ui.fit_style("₩8,198,500")) < _divisor(ui.fit_style("₩1,234,567,890"))


def test_korean_counts_wider_than_digits():
    """한글은 숫자보다 두 배 가까이 넓습니다. 같은 글자 수로 세면 넘칩니다."""
    assert _divisor(ui.fit_style("데이터 없음")) > _divisor(ui.fit_style("123456"))


def test_short_values_still_reach_the_full_size():
    """짧은 값까지 줄어들면 안 됩니다 — 위쪽 한계가 살아 있어야 합니다."""
    assert "1.5rem" in ui.fit_style("100주")


def test_empty_value_has_no_style():
    assert ui.fit_style("") == ""


def test_value_cards_carry_the_fitting_style():
    """kcard_html 이 실제로 그 style 을 달아야 의미가 있습니다."""
    html = ui.kcard_html("+₩1,234,567,890", "평가손익")
    assert "font-size:clamp(" in html
    assert "100cqi" in html


def test_the_card_is_declared_a_container():
    """`cqi` 는 `container-type:inline-size` 가 있어야 동작합니다.
    이 줄을 지우면 글자 맞춤이 **조용히** 안 먹습니다."""
    src = io.open(ui.__file__, encoding="utf-8").read()
    kcard_rule = src.split(".kcard {", 1)[1].split("}", 1)[0]
    assert "container-type:inline-size" in kcard_rule


def test_big_numbers_never_wrap():
    """줄바꿈이 허용되면 부호만 윗줄에 남습니다."""
    src = io.open(ui.__file__, encoding="utf-8").read()
    rule = src.split(".kcard .v {", 1)[1].split("}", 1)[0]
    assert "white-space:nowrap" in rule


def test_the_date_picker_targets_the_widget_streamlit_actually_renders():
    """⚠ Streamlit 1.63 의 셀렉트박스는 **react-aria** 입니다. BaseWeb 선택자만
    남겨 두면 색이 아무 데도 안 붙는데 에러가 안 나서 모릅니다."""
    src = io.open(ui.__file__, encoding="utf-8").read()
    assert '.st-key-calpick .stSelectbox [role="group"]' in src

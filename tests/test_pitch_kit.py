"""
유니폼·이름표 색 — 운용사가 서로 구분되는가.

왜 이 테스트가 있나
-------------------
전술판에서 **이름표 배경색이 운용사**입니다. 두 운용사가 비슷한 색을 쓰면
에러 하나 없이 "어느 회사 상품인지" 를 못 알아보게 됩니다. 실제로 미국 종목
이름표를 남색(#0A2B5C)으로 뒀다가 **KODEX 남색(#0A1660)과 헷갈린다**는
지적을 받았습니다. 눈으로 볼 때까지 아무도 모르는 종류의 버그라 여기서 셉니다.
"""

from __future__ import annotations

import os

import pytest

from components import pitch_kit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND = os.path.join(ROOT, "components", "football_pitch", "frontend", "index.html")
with open(FRONTEND, encoding="utf-8") as _f:
    HTML = _f.read()


def _rgb(hex_color: str) -> tuple[int, int, int]:
    n = int(hex_color.lstrip("#"), 16)
    return ((n >> 16) & 255, (n >> 8) & 255, n & 255)


def _rel_lum(hex_color: str) -> float:
    """WCAG 상대 휘도. 프론트엔드의 relLum() 과 같은 식입니다."""
    out = []
    for c in _rgb(hex_color):
        c /= 255
        out.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]


def _contrast(a: str, b: str) -> float:
    hi, lo = sorted((_rel_lum(a), _rel_lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _text_on(bg: str) -> str:
    """프론트엔드 textOn() 과 같은 선택 — 흑·백 중 대비가 높은 쪽."""
    lum = _rel_lum(bg)
    white = 1.05 / (lum + 0.05)
    black = (lum + 0.05) / (_rel_lum("#111111") + 0.05)
    return "#FFFFFF" if white >= black else "#111111"


def _distance(a: str, b: str) -> float:
    """두 색이 눈으로 갈리는 정도. 0~441 (검정↔흰색)."""
    return sum((x - y) ** 2 for x, y in zip(_rgb(a), _rgb(b))) ** 0.5


# ---------------------------------------------------------- 이름표 색
ALL_TAGS: dict[str, str] = {
    **{brand: kit[1] for brand, kit in pitch_kit.BRAND_KITS.items()},
    "US": pitch_kit.US_KIT[1],
    "기본(회색)": pitch_kit.DEFAULT_KIT[1],
}


def test_us_tag_is_not_confusable_with_kodex_navy():
    """미국 이름표를 남색으로 뒀다가 KODEX 와 헷갈린다는 지적을 받았습니다."""
    d = _distance(pitch_kit.US_KIT[1], pitch_kit.BRAND_KITS["KODEX"][1])
    assert d > 120, f"미국 이름표가 KODEX 남색과 너무 가깝습니다 (거리 {d:.0f})"


@pytest.mark.parametrize("brand", sorted(ALL_TAGS))
def test_every_tag_colour_is_distinguishable(brand):
    """같은 운용사를 가리키는 별칭(KOSEF/KIWOOM, TIME/TIMEFOLIO)만 겹쳐도 됩니다."""
    same = {("KOSEF", "KIWOOM"), ("TIME", "TIMEFOLIO")}
    mine = ALL_TAGS[brand]
    for other, colour in ALL_TAGS.items():
        if other == brand:
            continue
        if {brand, other} in [set(p) for p in same]:
            continue
        d = _distance(mine, colour)
        assert d > 40, f"{brand} 와 {other} 의 이름표 색이 너무 비슷합니다 (거리 {d:.0f})"


@pytest.mark.parametrize("brand", sorted(ALL_TAGS))
def test_tag_label_is_readable(brand):
    """프론트엔드는 이름표 글자색을 `textOn(kit.dark)` 로 고릅니다 —
    흑·백 중 대비가 높은 쪽. 그래도 WCAG AA(4.5)를 넘는지 확인합니다."""
    bg = ALL_TAGS[brand]
    ratio = _contrast(bg, _text_on(bg))
    assert ratio >= 4.5, f"{brand}: 이름표 글자 대비 {ratio:.2f} (바탕 {bg})"


# ------------------------------------------------------- 미국 표시 방식
def test_only_us_kits_get_the_white_ring():
    """흰 테두리는 '빨강 + 흰색 = 성조기' 표시입니다. 한국 종목엔 안 붙입니다."""
    us = pitch_kit.kit_of("US", "Schwab US Dividend Equity ETF")
    kr = pitch_kit.kit_of("KR", "KODEX 200")
    assert us["band"] == pitch_kit.US_TAG_BAND
    assert us["dark"] == pitch_kit.US_KIT[1]
    assert kr["band"] == ""


def test_unknown_brand_still_gets_every_key():
    """키 하나가 없으면 프론트엔드에서 undefined 가 그대로 색으로 들어갑니다."""
    k = pitch_kit.kit_of("KR", "듣도보도못한 ETF")
    assert set(k) >= {"style", "brand", "main", "dark", "text", "band"}


# ------------------------------------------- 프론트엔드가 정말 쓰는가
def test_frontend_uses_the_computed_tag_colours():
    """화면이 글자색을 `#fff` 로 박아 두면 밝은 이름표에서 글자가 사라집니다."""
    assert "tagStyle(p.kit)" in HTML, "화면 이름표가 tagStyle 을 안 씁니다"
    assert "textOn(kit.dark)" in HTML, "tagStyle 이 글자색을 계산하지 않습니다"


def test_capture_draws_the_same_tag_as_the_screen():
    """📸 캡처만 이름표가 다르면 같은 포트폴리오가 두 군데서 달라 보입니다."""
    assert "textOn(p.kit.dark)" in HTML, "캡처가 이름표 글자색을 계산하지 않습니다"
    assert "TAG_RING_PX * scale" in HTML, "캡처가 흰 테두리를 안 그립니다"

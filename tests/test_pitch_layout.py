"""
전술판 기하 — 카드가 서로, 그리고 응원 배너와 겹치지 않는가.

왜 이 테스트가 있나
-------------------
카드에 반바지·양말이 붙으면서 세로로 1.5배가 됐습니다. 그 뒤로 **줄 간격과
배너 두께를 조금만 건드려도 카드가 겹칩니다.** 겹쳐도 에러가 안 나고 화면만
지저분해지기 때문에, 눈으로 볼 때까지 모릅니다. 실제로 모바일에서 맨 아랫줄이
배너를 파고들었고 줄 간격이 5px 까지 좁아진 적이 있습니다.

숫자를 여기에 베껴 적지 않고 **실제 CSS·JS·pitch_grid 에서 뽑아 읽습니다.**
베껴 적으면 코드만 바뀌고 테스트는 통과하는 상태가 됩니다.
"""

from __future__ import annotations

import os
import re

import pytest

from components import pitch_grid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND = os.path.join(ROOT, "components", "football_pitch", "frontend", "index.html")
APP = os.path.join(ROOT, "app.py")


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def _block(css: str, selector: str) -> str:
    """CSS 규칙 한 덩어리를 꺼냅니다."""
    m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css, re.S)
    assert m, f"{selector} 규칙을 못 찾았습니다 (선택자가 바뀌었나요?)"
    return m.group(1)


def _pct(block: str, prop: str) -> float:
    m = re.search(prop + r"\s*:\s*([\d.]+)%", block)
    assert m, f"{prop} 을(를) 못 찾았습니다"
    return float(m.group(1)) / 100.0


@pytest.fixture(scope="module")
def geo() -> dict:
    html = _read(FRONTEND)

    card = _block(html, ".card")
    shirt = _block(html, ".card .shirt")
    banner = _block(html, ".banner")
    top = _block(html, "#bannerTop")
    bot = _block(html, "#bannerBot")

    ratio = re.search(r"const SHIRT_RATIO\s*=\s*([\d.]+)", html)
    assert ratio, "SHIRT_RATIO 를 못 찾았습니다"

    aspect = re.search(r"aspect_ratio\s*=\s*([\d.]+)", _read(APP))
    assert aspect, "app.py 에서 aspect_ratio 를 못 찾았습니다"

    return {
        # 판 너비 W 에 대한 비율
        "card_w": _pct(card, "width"),
        "shirt_w": _pct(shirt, "width"),
        "shirt_ratio": float(ratio.group(1)),
        # 판 높이 H 에 대한 비율
        "banner_h": _pct(banner, "height"),
        "banner_top": _pct(top, "top"),
        "banner_bot": _pct(bot, "bottom"),
        "aspect": float(aspect.group(1)),      # H / W
    }


def tag_px(g: dict, w_px: float) -> float:
    """이름표 높이(px).

    프론트엔드의 `tagFontPx()` 와 `.tag` 여백을 그대로 옮긴 것입니다. 상수를
    적당히 넉넉하게 잡아두면 실제보다 훨씬 뚱뚱한 카드로 계산돼서, 멀쩡한
    배치를 실패로 만듭니다(처음에 22px 로 잡았다가 그랬습니다).
    """
    inner = w_px * g["card_w"] - 6.0
    fs = min(11.5, max(7.0, inner / 8.8))
    return fs * 1.34 + 5.0 + 2.0          # 글자 + 상하 여백 + 유니폼과의 간격


def card_height_px(g: dict, w_px: float) -> float:
    """카드 전체 높이(px). 유니폼 + 이름표."""
    shirt_h = w_px * g["card_w"] * g["shirt_w"] * g["shirt_ratio"]
    return shirt_h + tag_px(g, w_px)


@pytest.mark.parametrize("w_px", [317, 480, 699, 900], ids=lambda w: f"{w}px")
def test_rows_do_not_overlap(geo, w_px):
    """여섯 줄 어디에서도 카드끼리 겹치면 안 됩니다."""
    h_px = w_px * geo["aspect"]
    card_h = card_height_px(geo, w_px)

    ys = sorted(pitch_grid.ROW_Y.values())
    gaps = [(ys[i + 1] - ys[i]) * h_px - card_h for i in range(len(ys) - 1)]
    assert min(gaps) > 0, (
        f"판 폭 {w_px}px 에서 줄이 겹칩니다. 가장 좁은 간격 {min(gaps):.1f}px "
        f"(카드 높이 {card_h:.0f}px). pitch_grid.ROW_Y 나 .card .shirt 폭을 조정하세요."
    )


@pytest.mark.parametrize("w_px", [317, 480, 699, 900], ids=lambda w: f"{w}px")
def test_cards_do_not_hit_the_banners(geo, w_px):
    """맨 윗줄·맨 아랫줄 카드가 골대 뒤 응원 배너를 파고들면 안 됩니다."""
    h_px = w_px * geo["aspect"]
    card_h = card_height_px(geo, w_px)
    # 배너는 min-height 11px 이 있어서 좁은 화면에서는 비율보다 두꺼워집니다.
    banner_h = max(11.0, geo["banner_h"] * h_px)

    top_edge = geo["banner_top"] * h_px + banner_h
    first = min(pitch_grid.ROW_Y.values()) * h_px - card_h / 2
    assert first > top_edge, (
        f"판 폭 {w_px}px: 맨 윗줄 카드({first:.0f}px)가 위 배너({top_edge:.0f}px)와 겹칩니다."
    )

    bot_edge = h_px - geo["banner_bot"] * h_px - banner_h
    last = max(pitch_grid.ROW_Y.values()) * h_px + card_h / 2
    assert last < bot_edge, (
        f"판 폭 {w_px}px: 맨 아랫줄 카드({last:.0f}px)가 아래 배너({bot_edge:.0f}px)와 겹칩니다."
    )


def test_rows_are_evenly_spaced(geo):
    """줄 간격이 들쭉날쭉하면 **가장 좁은 칸부터** 겹칩니다.
    예전에 0.10/0.265/0.43/0.595/0.76/0.925 로 두었다가 마지막 칸만 좁아졌습니다."""
    ys = sorted(pitch_grid.ROW_Y.values())
    gaps = [ys[i + 1] - ys[i] for i in range(len(ys) - 1)]
    assert max(gaps) - min(gaps) < 0.01, f"줄 간격이 고르지 않습니다: {gaps}"


def test_screen_and_capture_use_the_same_shirt_width(geo):
    """화면(.card .shirt)과 캡처(canvas jerseyW)가 다르면 공유한 그림만 유니폼이
    다른 크기로 나옵니다."""
    html = _read(FRONTEND)
    m = re.search(r"const jerseyW = cardW \* ([\d.]+);", html)
    assert m, "캔버스의 jerseyW 계산을 못 찾았습니다"
    assert abs(float(m.group(1)) - geo["shirt_w"]) < 1e-6, (
        f"화면 {geo['shirt_w']} vs 캡처 {m.group(1)} — 둘을 같이 고쳐야 합니다."
    )


def test_all_slots_are_inside_the_pitch(geo):
    """슬롯 좌표가 0~1 밖으로 나가면 카드가 판 밖에 그려집니다."""
    for slot in pitch_grid.all_slots():
        x, y = pitch_grid.center(slot)
        assert 0.0 < x < 1.0 and 0.0 < y < 1.0, f"{slot} 좌표가 판을 벗어납니다: {x},{y}"

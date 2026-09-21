"""
경기장 스킨 — 데이터 무결성 + 고르기/저장.

스킨은 **데이터**입니다(components/skins.py). UI 프레임워크에 묶여 있지 않아서,
나중에 Streamlit 을 떠나도 정의는 그대로 따라갑니다. 그 성질을 여기서 지킵니다.
"""

from __future__ import annotations

import re

import pytest

from components import skins
from models.portfolio import Portfolio
from services import skin_service

HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
COLOR = re.compile(r"^(#[0-9A-Fa-f]{6}|rgba?\([\d.,\s]+\))$")


# ------------------------------------------------------------- 데이터
def test_twenty_club_skins_plus_the_default():
    assert len(skins.SKINS) == 21          # 기본 잔디 1 + 클럽 20
    assert skins.DEFAULT_ID in skins.BY_ID
    assert skins.get(skins.DEFAULT_ID).tier == skins.TIER_FREE


def test_ids_and_names_are_unique():
    assert len(set(skins.ids())) == len(skins.SKINS)
    assert len({s.name for s in skins.SKINS}) == len(skins.SKINS)


@pytest.mark.parametrize("skin", skins.SKINS, ids=lambda s: s.id)
def test_every_colour_is_a_real_colour(skin):
    """오타 하나가 CSS 에서 조용히 무시되면 그 스킨만 이상하게 보입니다."""
    for field in ("turf_a", "turf_b", "frame_a", "frame_b", "accent"):
        assert HEX.match(getattr(skin, field)), f"{skin.id}.{field}"
    for field in ("line", "slot"):
        assert COLOR.match(getattr(skin, field)), f"{skin.id}.{field}"


@pytest.mark.parametrize("skin", skins.SKINS, ids=lambda s: s.id)
def test_every_skin_has_korean_and_english_names(skin):
    assert skin.name.strip() and skin.korean.strip()
    assert skin.tier in (skins.TIER_FREE, skins.TIER_PREMIUM)


def test_no_real_club_names_or_nicknames():
    """색 조합과 지명은 괜찮지만 구단명·별칭은 등록상표입니다.

    실수로 팀 이름을 적어 넣는 것을 막습니다.
    """
    banned = [
        "arsenal", "chelsea", "tottenham", "spurs", "united", "liverpool",
        "newcastle", "real madrid", "barcelona", "barca", "atletico",
        "juventus", "juve", "inter", "napoli", "roma", "bayern", "dortmund",
        "psg", "saint-germain", "ajax", "celtic",
        "gunners", "blues", "red devils", "citizens", "magpies", "hotspur",
    ]
    blob = " ".join(f"{s.id} {s.name} {s.korean}" for s in skins.SKINS).lower()
    hits = [w for w in banned if w in blob]
    assert not hits, f"구단명/별칭이 들어갔습니다: {hits}"


def test_to_dict_uses_the_keys_the_frontend_reads():
    """프론트엔드(index.html 의 applySkin)가 읽는 키와 어긋나면
    스킨이 **조용히 적용되지 않습니다.** 에러도 안 납니다."""
    d = skins.get("london-red").to_dict()
    assert set(d) >= {"turfA", "turfB", "line", "slot", "frameA", "frameB", "accent"}
    assert d["frameA"] == skins.get("london-red").frame_a


def test_unknown_id_falls_back_to_the_default_grass():
    """저장 파일이 옛 버전에서 왔거나 스킨이 없어졌을 수 있습니다."""
    assert skins.get("없는스킨").id == skins.DEFAULT_ID
    assert skins.get(None).id == skins.DEFAULT_ID
    assert skins.get("").id == skins.DEFAULT_ID


# ------------------------------------------------------------- 고르기
def test_select_and_persist():
    p = Portfolio()
    assert skin_service.current(p).id == skins.DEFAULT_ID
    assert skin_service.select(p, "london-red") is True
    assert p.skin == "london-red"
    assert skin_service.current(p).id == "london-red"
    assert Portfolio.from_dict(p.to_dict()).skin == "london-red"


def test_selecting_the_same_skin_twice_reports_no_change():
    """바뀐 게 없는데 True 를 돌려주면 화면이 계속 다시 그려집니다."""
    p = Portfolio()
    skin_service.select(p, "paris-navy")
    assert skin_service.select(p, "paris-navy") is False


def test_default_grass_is_stored_as_empty():
    """저장 파일에 군더더기를 안 남깁니다."""
    p = Portfolio(skin="london-red")
    assert skin_service.select(p, skins.DEFAULT_ID) is True
    assert p.skin == ""
    assert skin_service.current(p).id == skins.DEFAULT_ID


def test_unknown_skin_id_is_ignored():
    """바깥에서 온 값을 그대로 믿지 않습니다."""
    p = Portfolio(skin="london-red")
    assert skin_service.select(p, "없는스킨") is False
    assert skin_service.select(p, "") is False
    assert p.skin == "london-red"


def test_saved_skin_that_no_longer_exists_falls_back():
    p = Portfolio(skin="사라진스킨")
    assert skin_service.current(p).id == skins.DEFAULT_ID


def test_everything_is_unlocked_for_now():
    """해금 조건이 생기면 skin_service.is_unlocked 하나만 바꾸면 됩니다.
    지금 잠긴 게 있으면 화면에서 고를 수 없는 스킨이 생깁니다."""
    p = Portfolio()
    assert len(skin_service.available(p)) == len(skins.SKINS)
    assert all(skin_service.is_unlocked(p, s.id) for s in skins.SKINS)


def test_skin_does_not_touch_jersey_colours():
    """유니폼 색은 운용사 브랜드를 나타내는 **정보**입니다.
    스킨이 유니폼까지 바꾸면 어느 운용사 상품인지 못 알아봅니다."""
    d = skins.get("ruhr-yellow").to_dict()
    assert not any("kit" in k.lower() or "jersey" in k.lower() for k in d)

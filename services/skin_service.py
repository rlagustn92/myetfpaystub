"""
services/skin_service.py  --  경기장 스킨 고르기 / 해금
========================================================

스킨 **정의**는 `components/skins.py` 에 데이터로만 있습니다. 여기는 "지금 이
사용자가 이 스킨을 쓸 수 있는가" 를 판단하고, 고른 스킨을 포트폴리오에 저장합니다.

⚠ 지금은 전부 열려 있습니다
---------------------------
`is_unlocked()` 가 항상 True 를 돌려줍니다. 해금 조건(광고·공유·후원 등)이
정해지면 **이 함수 하나만** 바꾸면 됩니다. 화면·저장·전술판은 손댈 필요가 없습니다.

없는 잠금을 미리 걸어두고 "곧 열립니다" 라고 적지 않습니다. 아직 만들지 않은 걸
있는 것처럼 보여주지 않는다는 이 앱의 규칙과 같습니다.

수익화 배경은 docs/호스팅-수익화-검토.md 를 보세요 — 요약하면 웹에서 보상형
광고(AdSense)는 사실상 게임 전용이라, 해금 조건은 광고가 아닌 다른 것이 될
가능성이 높습니다.
"""

from __future__ import annotations

from components import skins
from components.skins import Skin
from models.portfolio import Portfolio


def all_skins() -> tuple[Skin, ...]:
    return skins.SKINS


def is_unlocked(portfolio: Portfolio, skin_id: str) -> bool:
    """이 사용자가 이 스킨을 쓸 수 있는가.

    지금은 전부 True 입니다. 해금 조건이 생기면 여기만 바꿉니다. 예:

        if skins.get(skin_id).tier == skins.TIER_FREE:
            return True
        return skin_id in portfolio.unlocked_skins
    """
    return True


def available(portfolio: Portfolio) -> list[Skin]:
    """고를 수 있는 스킨 목록 (화면 순서 그대로)."""
    return [s for s in skins.SKINS if is_unlocked(portfolio, s.id)]


def current(portfolio: Portfolio) -> Skin:
    """지금 쓰는 스킨.

    저장된 id 가 사라진 스킨이거나 잠겨 있으면 **기본 잔디로 되돌립니다.**
    저장 파일이 옛 버전에서 왔거나, 해금이 풀린 경우에도 화면이 깨지지 않게 합니다.
    """
    sk = skins.get(portfolio.skin)
    if not is_unlocked(portfolio, sk.id):
        return skins.get(skins.DEFAULT_ID)
    return sk


def select(portfolio: Portfolio, skin_id: str) -> bool:
    """스킨을 고릅니다. 실제로 바뀌었으면 True.

    모르는 id 나 잠긴 스킨은 무시합니다 — 바깥에서 온 값을 그대로 믿지 않습니다.
    """
    sid = str(skin_id or "")
    if sid not in skins.BY_ID or not is_unlocked(portfolio, sid):
        return False
    # 기본 잔디는 빈 값으로 저장합니다. 저장 파일에 군더더기를 안 남기려고요.
    new_value = "" if sid == skins.DEFAULT_ID else sid
    if portfolio.skin == new_value:
        return False
    portfolio.skin = new_value
    return True

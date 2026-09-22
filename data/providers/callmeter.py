"""
data/providers/callmeter.py  --  바깥에 몇 번 나갔는지 세기
============================================================

왜 필요한가
-----------
무료 소스에 막히면 **앱이 통째로 쓸모없어집니다.** 그런데 호출이 몇 번
나가는지 아무도 안 보고 있으면, 막히고 나서야 알게 됩니다.

운용사 호출은 `issuer/base.py` 가 이미 세고 있었는데 **시세·환율은 아무도
안 세고 있었습니다.** 그래서 같은 눈금을 여기에 하나 더 둡니다.

세는 것은 **실제로 나간 횟수**입니다. 캐시에서 꺼내 쓴 것은 안 셉니다
(그래야 "캐시가 잘 듣고 있나" 를 이 숫자로 알 수 있습니다).

⚠ 프로세스 안에서만 셉니다
--------------------------
서버가 다시 켜지면 0 부터 다시 셉니다. 정확한 한도 관리가 아니라
**폭주를 끊는 안전장치 + 눈금**입니다. 무료 호스팅은 접속이 없으면 앱을
재우기 때문에, 이 숫자는 "이번에 깨어난 뒤로 몇 번" 에 가깝습니다.
"""

from __future__ import annotations

import config
from data.providers.base import DataUnavailable

# {"2026-09-22": {"price": 12, "fx": 3}}
_counts: dict[str, dict[str, int]] = {}


def _today() -> str:
    return config.today_local().isoformat()


def used_today(source: str = "") -> int:
    """오늘 나간 횟수. `source` 를 비우면 전부 더합니다."""
    day = _counts.get(_today(), {})
    return day.get(source, 0) if source else sum(day.values())


def breakdown_today() -> dict[str, int]:
    """{소스: 횟수}. 화면에 그대로 적을 수 있게."""
    return dict(_counts.get(_today(), {}))


def reset() -> None:
    """테스트용. 앱에서는 부르지 않습니다."""
    _counts.clear()


def spend(source: str, budget: int | None = None) -> None:
    """한 번 나간다고 세고, 하루 한도를 넘으면 **아예 안 나갑니다.**

    남이 우리를 막기 전에 우리가 먼저 멈춥니다. 막히면 그 소스만 죽는 게
    아니라 화면 전체가 "가격을 확인하지 못했습니다" 가 되기 때문입니다.
    """
    cap = config.PRICE_DAILY_CALL_BUDGET if budget is None else budget
    day = _today()
    # 날짜가 바뀌면 옛 날짜 칸은 필요 없습니다(메모리에 쌓이지 않게).
    if day not in _counts:
        _counts.clear()
        _counts[day] = {}
    used = sum(_counts[day].values())
    if used >= cap:
        raise DataUnavailable(
            f"오늘 시세·환율 조회 한도({cap}회)를 다 썼습니다. "
            f"잠시 뒤에 다시 시도해 주세요."
        )
    _counts[day][source] = _counts[day].get(source, 0) + 1

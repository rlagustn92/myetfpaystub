"""
formatting.py  --  화면에 숫자를 어떻게 적을지 (한 곳에서 관리)
================================================================

돈을 잘못 적으면 사용자가 그대로 오해합니다. app.py 안에 두면 테스트를 못 붙이므로
따로 뺐습니다.
"""

from __future__ import annotations

import config


def won(x) -> str:
    """기본 원화 표기. 예: ₩45,000,000"""
    if x is None:
        return config.NO_DATA_TEXT
    return f"₩{x:,.0f}"


def won_signed(x) -> str:
    """손익처럼 부호가 중요한 금액. 예: +₩12,340,000 / -₩310,000"""
    if x is None:
        return config.NO_DATA_TEXT
    sign = "+" if x > 0 else ("-" if x < 0 else "")
    return f"{sign}₩{abs(x):,.0f}"


def won_short(x) -> str:
    """자리가 좁은 곳에서 쓰는 짧은 금액 표기.

    "₩45,000,000" 은 카드 안에서 너무 길고 한눈에 안 읽힙니다.
    한국에서 실제로 말하는 단위(만/억)로 줄입니다.
        45,000,000 -> 4,500만     187,000 -> 18.7만     123,400,000 -> 1.23억

    만 단위에서 100만 미만은 소수 한 자리를 남깁니다("18.7만"). 안 그러면 월 분배금처럼
    작은 금액이 죄다 "19만" 으로 뭉개져서 종목끼리 비교가 안 됩니다.
    """
    if x is None:
        return config.NO_DATA_TEXT
    v = float(x)
    sign = "-" if v < 0 else ""
    v = abs(v)
    if v >= 100_000_000:
        # rstrip 은 소수점 아래만 건드립니다("10.00" -> "10." -> "10").
        return f"{sign}{v / 100_000_000:,.2f}".rstrip("0").rstrip(".") + "억"
    if v >= 10_000:
        man = v / 10_000
        return f"{sign}{man:,.0f}만" if man >= 100 else f"{sign}{man:,.1f}만"
    return f"{sign}{v:,.0f}원"


def pct(x, digits: int = 2) -> str:
    if x is None:
        return config.NO_DATA_TEXT
    return f"{x:.{digits}f}%"


def pct_signed(x, digits: int = 2) -> str:
    if x is None:
        return config.NO_DATA_TEXT
    sign = "+" if x > 0 else ""
    return f"{sign}{x:.{digits}f}%"


def native_amt(x, currency: str, usd_digits: int = 2) -> str:
    """그 종목의 "원래 통화" 기준 금액(가격/분배금 등).

    원화는 1원 미만 단위가 실질적으로 없어 소수점을 쓰지 않습니다.
    """
    if x is None:
        return config.NO_DATA_TEXT
    if currency == "KRW":
        return f"₩{x:,.0f}"
    return f"${x:,.{usd_digits}f}"


def shares(x) -> str:
    """보유수량. 소수점 주식은 필요할 때만 보여줍니다."""
    if x is None:
        return config.NO_DATA_TEXT
    v = float(x)
    if abs(v - round(v)) < 1e-9:
        return f"{int(round(v)):,}주"
    return f"{v:,.4f}".rstrip("0").rstrip(".") + "주"


def ymd(d) -> str:
    if d is None:
        return config.NO_DATA_TEXT
    return f"{d.year}.{d.month:02d}.{d.day:02d}"


def md(d) -> str:
    """'9/15' 처럼 짧게 (표 안에서)."""
    if d is None:
        return "-"
    return f"{d.month}/{d.day}"

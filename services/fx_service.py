"""
services/fx_service.py  --  환율을 쓰는 규칙
============================================

규칙은 두 줄입니다.

* **지금 내 자산**은 최신 환율로 환산한다.
* **과거에 받은 분배금**은 **그때의 환율**로 환산한다.
  (과거 금액 + 현재 환율 조합은 쓰지 않습니다. 환율만으로 금액이 20% 넘게 왜곡됩니다.)

환율을 못 가져오면 `None` 을 돌려주고, 화면은 "환율 데이터 없음" 으로 적습니다.
**임의의 값(1,300원 같은)으로 채우지 않습니다.**
"""

from __future__ import annotations

from datetime import date

from data.providers import fx_provider
from data.providers.base import DataUnavailable, FxQuote


def latest() -> FxQuote | None:
    """지금 환율. 실패하면 None."""
    try:
        return fx_provider.get_latest_rate()
    except DataUnavailable:
        return None


def on(d: date) -> FxQuote | None:
    """그날(또는 그 이전 가장 가까운 거래일) 환율. 실패하면 None."""
    try:
        return fx_provider.get_rate_on(d)
    except DataUnavailable:
        return None


def to_krw(amount: float, currency: str, rate: float | None) -> float | None:
    """원화로 환산. 달러인데 환율을 모르면 None (0 으로 채우지 않습니다)."""
    if amount is None:
        return None
    if (currency or "KRW").upper() == "KRW":
        return float(amount)
    if rate is None:
        return None
    return float(amount) * float(rate)

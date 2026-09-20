"""
models/distribution.py  --  분배금 한 건을 담는 그릇
====================================================

이 앱에서 가장 중요한 자료구조입니다. 규칙은 하나뿐입니다.

> **주당 과세표준액(`tax_basis_per_share`)은 주당 분배금과 완전히 별개의 필드다.**

실제로 얼마나 다른지는 docs/DATA_SOURCES.md §1 에 실측이 있습니다.
같은 종목에서 분배금 300원 / 과세표준 2원 같은 일이 매달 벌어집니다.
그래서 절대로 분배금에서 과세표준을 유도하지 않습니다.

`0` 과 `None` 도 다릅니다.
    0    -> 운용사가 "과세표준 0원" 이라고 **발표한** 값 (실제로 흔합니다)
    None -> 아직 모름 / 못 가져옴
이 둘을 섞으면 사용자가 "세금이 안 잡히는구나" 로 오해합니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import config


@dataclass(frozen=True)
class Distribution:
    """분배금 1건. 운용사가 발표한 값 그대로 담습니다."""

    ticker: str
    payment_date: date                      # 실지급일 — 달력/월별 명세서의 기준
    distribution_per_share: float           # 주당 분배금
    currency: str = "KRW"                   # "KRW" | "USD"
    record_date: date | None = None         # 지급기준일 (미국은 배당락일만 있어 None 일 수 있음)
    tax_basis_per_share: float | None = None  # 주당 과세표준액. **None = 모름, 0 = 발표된 0원**
    source: str = ""                        # "KODEX" | "TIGER" | "yfinance" ...
    source_url: str = ""
    status: str = config.STATUS_CONFIRMED   # confirmed | estimated
    note: str = ""

    # -- 화면에서 쓰는 보조 ------------------------------------------
    @property
    def has_tax_basis(self) -> bool:
        """과세표준을 아는가. (0원이라고 발표한 것도 '안다' 입니다)"""
        return self.tax_basis_per_share is not None

    @property
    def year_month(self) -> tuple[int, int]:
        return (self.payment_date.year, self.payment_date.month)

    def amount_for(self, shares: float) -> float:
        """내 보유수량 기준 받을 금액 (원래 통화)."""
        return self.distribution_per_share * shares

    def tax_basis_for(self, shares: float) -> float | None:
        """내 보유수량 기준 세금 계산에 잡히는 금액. 모르면 None."""
        if self.tax_basis_per_share is None:
            return None
        return self.tax_basis_per_share * shares

    def badge(self) -> str:
        return config.STATUS_BADGE.get(self.status, "")


@dataclass
class DistributionSeries:
    """한 종목의 분배 이력 + 어디서 가져왔는지.

    `tax_basis_supported` 가 중요합니다.
    - True  : 이 소스는 과세표준을 주는 소스다 (개별 건이 None 이면 '아직 미발표')
    - False : 이 소스는 애초에 과세표준을 안 준다 (예: yfinance)
    화면 문구가 달라집니다. "아직 발표 안 됐어요" 와 "여긴 알 수 없어요" 는 다른 말입니다.
    """

    ticker: str
    items: list[Distribution]
    source: str = ""
    source_url: str = ""
    tax_basis_supported: bool = False
    fetched_at: date | None = None

    def __len__(self) -> int:
        return len(self.items)

    def sorted_desc(self) -> list[Distribution]:
        return sorted(self.items, key=lambda d: d.payment_date, reverse=True)

    def in_range(self, start: date, end: date) -> list[Distribution]:
        return [d for d in self.items if start <= d.payment_date <= end]

    def in_month(self, year: int, month: int) -> list[Distribution]:
        return [d for d in self.items if d.payment_date.year == year
                and d.payment_date.month == month]

    def latest(self) -> Distribution | None:
        items = self.sorted_desc()
        return items[0] if items else None

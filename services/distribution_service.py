"""
services/distribution_service.py  --  분배금 가져오기 + 다음 달 예상하기
=========================================================================

두 가지 일을 합니다.

1. 종목별 분배 이력을 가져온다 (운용사 provider → 실패하면 폴백).
2. **아직 발표 안 된 다음 지급을 예상한다.**

예상 규칙 (일부러 단순하게 둡니다)
----------------------------------
- 이미 발표된 값이 있으면 → **그 값을 그대로** 씁니다 (예상 아님, 확인된 값).
- 발표값이 없으면 → 최근 지급 간격과 최근 금액으로 **단순 예상**하고 `🟡 예상` 을 붙입니다.
- 지급 이력이 2건 미만이면 → **예상하지 않습니다.** "예상 불가" 입니다.

머신러닝이나 통계 모델을 쓰지 않습니다. 정확하지 않은 값을 억지로 만들어내는 것보다
"모른다" 가 낫습니다. 다음 달 값을 확정값처럼 보여주는 일은 절대 없습니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from statistics import median

import config
from data.providers.base import DataUnavailable
from data.providers.issuer import registry
from models.distribution import Distribution, DistributionSeries
from models.portfolio import Portfolio

# 예상을 하려면 최소 이만큼의 지급 이력이 필요합니다.
MIN_HISTORY_FOR_ESTIMATE = 2
# 마지막 지급이 이보다 오래됐으면 예상하지 않습니다(분배를 멈춘 상품일 수 있음).
STALE_DAYS = 200


@dataclass
class TickerDistributions:
    """한 종목의 분배 자료 묶음. 화면은 이것만 보면 됩니다."""

    market: str
    ticker: str
    name: str = ""
    series: DistributionSeries | None = None
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.series is not None

    @property
    def source(self) -> str:
        return self.series.source if self.series else ""

    @property
    def source_url(self) -> str:
        return self.series.source_url if self.series else ""

    @property
    def tax_basis_supported(self) -> bool:
        return bool(self.series and self.series.tax_basis_supported)

    def items(self) -> list[Distribution]:
        return self.series.items if self.series else []


def fetch_all(portfolio: Portfolio) -> dict[tuple[str, str], TickerDistributions]:
    """포트폴리오에 있는 종목들의 분배 이력. 종목당 한 번씩만 조회합니다."""
    names = {(h.market, h.ticker): h.name for h in portfolio.holdings}
    out: dict[tuple[str, str], TickerDistributions] = {}
    for market, ticker in portfolio.tickers():
        name = names.get((market, ticker), "")
        try:
            series = registry.get_distributions(market, ticker, name)
            out[(market, ticker)] = TickerDistributions(market, ticker, name, series=series)
        except DataUnavailable as e:
            out[(market, ticker)] = TickerDistributions(market, ticker, name, error=str(e))
        except Exception as e:  # noqa: BLE001 - 종목 하나로 화면이 죽으면 안 됩니다
            out[(market, ticker)] = TickerDistributions(
                market, ticker, name,
                error=f"[{ticker}] 분배금 자료를 확인하지 못했습니다 ({type(e).__name__}).")
    return out


# ---------------------------------------------------------------------
# 지급 주기 파악
# ---------------------------------------------------------------------
def infer_interval_days(items: list[Distribution]) -> int | None:
    """최근 지급 간격(일). 이력이 부족하면 None.

    최근 6건까지만 봅니다. 아주 예전 주기는 지금과 다를 수 있습니다.
    """
    dates = sorted({d.payment_date for d in items}, reverse=True)[:6]
    if len(dates) < MIN_HISTORY_FOR_ESTIMATE:
        return None
    gaps = [(dates[i] - dates[i + 1]).days for i in range(len(dates) - 1)]
    gaps = [g for g in gaps if g > 0]
    if not gaps:
        return None
    return int(median(gaps))


def cycle_label(interval_days: int | None) -> str:
    """사람이 읽는 주기. 전문용어를 안 씁니다."""
    if interval_days is None:
        return "지급 주기를 알 수 없음"
    if interval_days <= 10:
        return "매주 지급"
    if interval_days <= 45:
        return "매달 지급"
    if interval_days <= 135:
        return "3개월마다 지급"
    if interval_days <= 250:
        return "6개월마다 지급"
    return "1년에 한 번 지급"


# ---------------------------------------------------------------------
# 예상
# ---------------------------------------------------------------------
def estimate_next(td: TickerDistributions, today: date | None = None) -> Distribution | None:
    """다음 지급 1건을 예상합니다. 근거가 부족하면 None ("예상 불가").

    금액은 **최근 실제 지급액**을 그대로 씁니다. 평균을 내거나 추세를 그리지 않습니다 —
    근거를 설명할 수 없는 숫자를 만들지 않기 위해서입니다.
    """
    today = today or config.today_local()
    items = td.items()
    if len(items) < MIN_HISTORY_FOR_ESTIMATE:
        return None

    interval = infer_interval_days(items)
    if interval is None:
        return None

    last = max(items, key=lambda d: d.payment_date)
    if (today - last.payment_date).days > STALE_DAYS:
        # 한참 전에 멈춘 상품일 수 있습니다. 예상하지 않습니다.
        return None

    next_date = last.payment_date + timedelta(days=interval)
    # 이미 지난 날짜면 오늘 이후로 밀어 줍니다(발표가 늦어지는 경우).
    while next_date < today:
        next_date += timedelta(days=interval)

    # 과세표준은 **최근에 값이 있었던 건**에서 가져옵니다. 없으면 None 그대로 둡니다.
    tax_basis = None
    for d in sorted(items, key=lambda x: x.payment_date, reverse=True):
        if d.tax_basis_per_share is not None:
            tax_basis = d.tax_basis_per_share
            break

    return Distribution(
        ticker=td.ticker,
        payment_date=next_date,
        record_date=None,
        distribution_per_share=last.distribution_per_share,
        tax_basis_per_share=tax_basis,
        currency=last.currency,
        source=last.source,
        source_url=last.source_url,
        status=config.STATUS_ESTIMATED,
        note=(f"{cycle_label(interval)} · 가장 최근 지급액({last.payment_date.year}."
              f"{last.payment_date.month:02d})을 그대로 적용한 예상값입니다. "
              f"실제 발표 금액과 다를 수 있습니다."),
    )


def upcoming(td: TickerDistributions, today: date | None = None) -> list[Distribution]:
    """오늘 이후로 잡혀 있는 지급 (발표된 것 + 없으면 예상 1건)."""
    today = today or config.today_local()
    future = [d for d in td.items() if d.payment_date >= today]
    if future:
        return sorted(future, key=lambda d: d.payment_date)
    est = estimate_next(td, today)
    return [est] if est else []

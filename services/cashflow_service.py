"""
services/cashflow_service.py  --  "이번 달 ETF 월급이 얼마인가"
================================================================

분배 이력 + 내 보유수량을 곱해서 **실제 내 금액**으로 바꾸는 곳입니다.
메인 화면의 큰 카드, 월별 급여명세서, 분배금 달력이 전부 여기서 나옵니다.

원화 환산 규칙
--------------
- **과거에 받은 것**은 그날의 환율로 환산합니다.
- **앞으로 받을 것**은 지금 환율로 환산합니다 (미래 환율은 아무도 모릅니다).

과세표준 합계의 규칙 — 여기가 제일 조심스러운 부분입니다
--------------------------------------------------------
과세표준을 모르는 건(`None`)은 **합계에 0으로 넣지 않습니다.** 대신
"몇 건은 자료가 없어서 빠졌다" 를 같이 들고 다니면서 화면에 적습니다.
0으로 세면 "세금 계산에 잡히는 금액이 적다" 고 오해하게 됩니다.
"""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date

import config
from models.distribution import Distribution
from models.portfolio import Holding, Portfolio
from services import fx_service
from services.distribution_service import TickerDistributions, upcoming


@dataclass
class PayslipRow:
    """급여명세서 한 줄 = (지급 1건 × 계좌 1개)."""

    payment_date: date
    holding: Holding
    dist: Distribution
    amount_krw: float | None = None
    tax_basis_krw: float | None = None
    fx_rate: float | None = None
    # 이 종목의 소스가 애초에 과세표준을 주는 소스인가.
    # ⚠ `tax_basis_krw is None` 하나로는 두 가지를 구별할 수 없습니다.
    #    (가) 운용사는 발표하는데 **그 달 값만 아직 안 올렸다**
    #    (나) 이 소스는 **애초에 과세표준을 안 준다** (yfinance 폴백)
    #    화면 문구가 달라야 해서 시리즈의 플래그를 줄까지 들고 옵니다.
    tax_basis_supported: bool = True

    @property
    def ticker(self) -> str:
        return self.holding.ticker

    @property
    def name(self) -> str:
        return self.holding.name or self.holding.ticker

    @property
    def is_estimated(self) -> bool:
        return self.dist.status == config.STATUS_ESTIMATED

    # ---- 세금 -------------------------------------------------------
    # 계좌 유형에 따라 **이야기가 완전히 다릅니다.**
    #   ISA·연금저축·IRP : 지급할 때 세금을 안 뗍니다(과세이연). 그대로 입금.
    #   일반(위탁)      : 과세표준액의 15.4% 를 떼고 줍니다.
    # 그래서 한 줄마다 계좌를 보고 갈라야 합니다. 포트폴리오 전체에 같은
    # 세율을 먹이면 ISA 를 가진 사람에게 있지도 않은 세금을 보여주게 됩니다.

    @property
    def is_tax_deferred(self) -> bool:
        """받을 때 세금을 안 떼는 계좌인가 (ISA·연금저축·IRP …)."""
        text = f"{self.holding.account or ''} {self.holding.account_type or ''}".upper()
        return any(w.upper() in text for w in config.TAX_DEFERRED_ACCOUNT_WORDS)

    @property
    def taxable_basis_krw(self) -> float:
        """세금 계산에 쓰는 과세표준액.

        ⚠ 운용사 미발표는 **0원으로 셉니다**(사용자 결정). 몇 건인지는
          `tax_basis_note` 로 따로 알립니다.
        """
        return float(self.tax_basis_krw or 0.0)

    @property
    def withholding_krw(self) -> float | None:
        """지급할 때 떼는 예상 세금. 세금을 안 떼는 계좌면 None.

        ⚠ **예상입니다.** 금융소득종합과세 대상이거나 해외 종목 외국납부세액이
          얽히면 달라집니다.
        """
        if self.is_tax_deferred:
            return None
        return self.taxable_basis_krw * config.WITHHOLDING_RATE

    @property
    def after_tax_krw(self) -> float | None:
        """세금 떼고 실제로 들어올 것으로 보이는 금액."""
        if self.amount_krw is None:
            return None
        tax = self.withholding_krw
        return self.amount_krw - (tax or 0.0)

    @property
    def record_note(self) -> str:
        """지급기준일이 **다른 달**이면 그 사실을 적을 짧은 문구. 아니면 빈 문자열.

        왜 필요한가
        -----------
        월말이 기준인 ETF 가 많습니다. 기준일 8/31 -> 실지급 9/2 처럼요
        (RISE 200위클리커버드콜은 31건이 **전부** 이렇습니다. TIGER·KODEX 의
        미국S&P500 류도 마찬가지입니다).

        이 앱은 **돈이 통장에 꽂히는 날**(실지급일)로 달을 묶습니다. 그게
        "이번 달에 얼마 들어오나" 라는 질문에 맞는 답이라서요. 그런데 화면에
        기준일이 안 보이면 **"8월분인데 왜 9월에 있지?"** 가 됩니다.
        그래서 달이 갈리는 건에만 기준일을 같이 적습니다.
        """
        rd = self.dist.record_date
        if rd is None:
            return ""
        if (rd.year, rd.month) == (self.payment_date.year, self.payment_date.month):
            return ""
        return f"{rd.month}/{rd.day} 기준"

    @property
    def tax_basis_note(self) -> str:
        """과세표준을 모를 때 화면에 적을 **이유**. 알고 있으면 빈 문자열.

        "자료 없음" 한 마디로는 앱이 못 가져온 건지 운용사가 안 낸 건지
        알 수 없어서 혼란스럽다는 지적을 받았습니다.
        """
        if self.tax_basis_krw is not None:
            return ""
        return config.TAX_BASIS_UNPUBLISHED

    @property
    def has_tax_basis(self) -> bool:
        return self.tax_basis_krw is not None

    def badge(self) -> str:
        return config.STATUS_BADGE.get(self.dist.status, "")


@dataclass
class PeriodTotal:
    """어떤 기간(이번 달 / 올해)의 합계."""

    label: str = ""
    amount_krw: float = 0.0
    tax_basis_krw: float = 0.0
    # 세금을 안 떼고 그대로 들어오는 금액 (ISA·연금저축·IRP)
    tax_deferred_krw: float = 0.0
    # 일반계좌에서 떼일 것으로 보이는 세금 (과세표준 x 15.4%)
    withholding_krw: float = 0.0
    rows: list[PayslipRow] = field(default_factory=list)
    unknown_tax_basis_rows: int = 0     # 과세표준을 모르는 줄 수
    estimated_rows: int = 0             # 예상값이 섞인 줄 수
    skipped_rows: int = 0               # 환율을 몰라 금액 자체를 못 낸 줄 수

    @property
    def has_estimate(self) -> bool:
        return self.estimated_rows > 0

    @property
    def status(self) -> str:
        return config.STATUS_ESTIMATED if self.has_estimate else config.STATUS_CONFIRMED

    @property
    def non_taxed_krw(self) -> float:
        """세금 계산에 안 잡히는 금액. 과세표준을 아는 줄만 가지고 계산합니다."""
        known = sum(r.amount_krw or 0.0 for r in self.rows if r.has_tax_basis)
        return max(0.0, known - self.tax_basis_krw)

    @property
    def after_tax_krw(self) -> float:
        """세금 떼고 실제로 들어올 것으로 보이는 합계."""
        return max(0.0, (self.amount_krw or 0.0) - self.withholding_krw)

    @property
    def has_tax_deferred(self) -> bool:
        return self.tax_deferred_krw > 0

    @property
    def has_withholding(self) -> bool:
        return self.withholding_krw > 0

    @property
    def tax_basis_is_partial(self) -> bool:
        return self.unknown_tax_basis_rows > 0


# ---------------------------------------------------------------------
def _fx_for(dist: Distribution, today: date, latest_rate: float | None) -> float | None:
    """그 지급 건에 쓸 환율. 원화 종목이면 필요 없습니다."""
    if dist.currency.upper() == "KRW":
        return None
    if dist.payment_date > today:
        return latest_rate           # 미래 = 지금 환율 (미래 환율은 모릅니다)
    q = fx_service.on(dist.payment_date)
    return q.rate if q else latest_rate


def build_rows(portfolio: Portfolio,
               dists: dict[tuple[str, str], TickerDistributions],
               start: date, end: date,
               include_estimates: bool = True,
               today: date | None = None,
               latest_rate: float | None = None) -> list[PayslipRow]:
    """[start, end] 구간의 급여명세서 줄들.

    한 종목을 세 계좌에 나눠 가지고 있으면 줄이 세 개 생깁니다(§15).
    """
    today = today or config.today_local()
    if latest_rate is None:
        q = fx_service.latest()
        latest_rate = q.rate if q else None

    rows: list[PayslipRow] = []
    for h in portfolio.holdings:
        if h.shares <= 0:
            continue
        td = dists.get((h.market, h.ticker))
        if td is None or not td.ok:
            continue

        events: list[Distribution] = td.series.in_range(start, end)
        if include_estimates:
            for e in upcoming(td, today):
                if e.status == config.STATUS_ESTIMATED and start <= e.payment_date <= end:
                    events.append(e)

        for d in events:
            rate = _fx_for(d, today, latest_rate)
            amount = fx_service.to_krw(d.amount_for(h.shares), d.currency, rate)
            tb_native = d.tax_basis_for(h.shares)
            tb = (fx_service.to_krw(tb_native, d.currency, rate)
                  if tb_native is not None else None)
            rows.append(PayslipRow(payment_date=d.payment_date, holding=h, dist=d,
                                   amount_krw=amount, tax_basis_krw=tb, fx_rate=rate,
                                   tax_basis_supported=td.series.tax_basis_supported))
    rows.sort(key=lambda r: (r.payment_date, r.name))
    return rows


def total_of(rows: list[PayslipRow], label: str = "") -> PeriodTotal:
    """줄들을 합칩니다. 모르는 값은 0으로 세지 않고 따로 셉니다."""
    t = PeriodTotal(label=label, rows=rows)
    for r in rows:
        if r.amount_krw is None:
            t.skipped_rows += 1
            continue
        # 세금은 계좌 유형별로 갈라서 셉니다.
        if r.is_tax_deferred:
            t.tax_deferred_krw += r.amount_krw
        else:
            t.withholding_krw += (r.withholding_krw or 0.0)
        t.amount_krw += r.amount_krw
        if r.tax_basis_krw is None:
            t.unknown_tax_basis_rows += 1
        else:
            t.tax_basis_krw += r.tax_basis_krw
        if r.is_estimated:
            t.estimated_rows += 1
    return t


def month_range(year: int, month: int) -> tuple[date, date]:
    last = monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def month_total(portfolio: Portfolio, dists: dict, year: int, month: int,
                **kw) -> PeriodTotal:
    start, end = month_range(year, month)
    rows = build_rows(portfolio, dists, start, end, **kw)
    return total_of(rows, label=f"{year}년 {month}월")


def year_total(portfolio: Portfolio, dists: dict, year: int,
               include_estimates: bool = False, **kw) -> PeriodTotal:
    """올해 누적. 기본은 **확인된 것만** 셉니다.

    "올해 지금까지 받은 돈" 에 예상값을 섞으면 그건 받은 돈이 아닙니다.
    """
    rows = build_rows(portfolio, dists, date(year, 1, 1), date(year, 12, 31),
                      include_estimates=include_estimates, **kw)
    return total_of(rows, label=f"{year}년")


# ---------------------------------------------------------------------
# 달력
# ---------------------------------------------------------------------
@dataclass
class CalendarDay:
    day: date
    amount_krw: float = 0.0
    rows: list[PayslipRow] = field(default_factory=list)

    @property
    def has_estimate(self) -> bool:
        return any(r.is_estimated for r in self.rows)


def calendar_of(rows: list[PayslipRow]) -> dict[date, CalendarDay]:
    """날짜별로 묶습니다. 달력 화면에서 씁니다."""
    out: dict[date, CalendarDay] = {}
    for r in rows:
        c = out.setdefault(r.payment_date, CalendarDay(day=r.payment_date))
        c.rows.append(r)
        if r.amount_krw is not None:
            c.amount_krw += r.amount_krw
    return out


def monthly_series(portfolio: Portfolio, dists: dict, year: int,
                   **kw) -> list[tuple[int, PeriodTotal]]:
    """1~12월 각 달의 합계. 월별 막대/표에 씁니다."""
    out: list[tuple[int, PeriodTotal]] = []
    for m in range(1, 13):
        out.append((m, month_total(portfolio, dists, year, m, **kw)))
    return out


# =====================================================================
# 연간 배당금 목표
# =====================================================================
@dataclass
class GoalProgress:
    """올해 목표 대비 어디까지 왔나.

    ⚠ **목표는 사용자가 정하는 값입니다.** 앱이 추천하거나 자동으로 잡지
      않습니다. 얼마를 목표로 할지는 투자 판단이라 우리가 낄 자리가 아닙니다.
    ⚠ 남은 금액을 "이만큼 더 사면 됩니다" 로 바꾸지 않습니다 — 그건 매수
      추천이고, 이 앱이 안 하기로 한 것입니다.
    """

    goal_krw: float
    received_krw: float          # 올해 지금까지 실제로 들어온 돈
    expected_krw: float          # 올해 남은 달에 들어올 것으로 보이는 돈(예상 포함)

    @property
    def has_goal(self) -> bool:
        return self.goal_krw > 0

    @property
    def percent(self) -> float:
        """받은 돈 기준 달성률. 100 을 넘어도 그대로 돌려줍니다 —
        넘겼으면 넘겼다고 보여주는 게 맞습니다."""
        if not self.has_goal:
            return 0.0
        return self.received_krw / self.goal_krw * 100.0

    @property
    def percent_with_expected(self) -> float:
        """예상까지 더했을 때의 달성률."""
        if not self.has_goal:
            return 0.0
        return (self.received_krw + self.expected_krw) / self.goal_krw * 100.0

    @property
    def remaining_krw(self) -> float:
        return max(0.0, self.goal_krw - self.received_krw)


def goal_progress(portfolio: Portfolio, dists: dict, year: int,
                  today: date | None = None,
                  latest_rate: float | None = None) -> GoalProgress:
    """올해 목표 대비 진행 상황.

    **이미 들어온 돈**과 **앞으로 들어올 것으로 보이는 돈**을 나눠 셉니다.
    섞으면 "벌써 다 받은 것" 처럼 보입니다 — 예상은 예상이라고 따로 둡니다.
    """
    today = today or config.today_local()
    rows = build_rows(portfolio, dists, date(year, 1, 1), date(year, 12, 31),
                      today=today, latest_rate=latest_rate)
    received = sum(r.amount_krw or 0.0 for r in rows
                   if r.payment_date <= today and not r.is_estimated)
    expected = sum(r.amount_krw or 0.0 for r in rows
                   if r.payment_date > today or r.is_estimated)
    return GoalProgress(goal_krw=float(portfolio.dividend_goal_krw or 0.0),
                        received_krw=received, expected_krw=expected)

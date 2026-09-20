"""예상 로직 — 근거가 부족하면 예상하지 않는다."""

from __future__ import annotations

from datetime import date

from conftest import dist, td

import config
from services import distribution_service as DS

TODAY = date(2026, 9, 20)


def test_monthly_cycle_is_detected():
    items = [dist(day=(2026, m, 15)) for m in (6, 7, 8, 9)]
    assert 28 <= DS.infer_interval_days(items) <= 32
    assert DS.cycle_label(DS.infer_interval_days(items)) == "매달 지급"


def test_quarterly_cycle_is_detected():
    items = [dist(day=(2026, m, 15)) for m in (3, 6, 9)]
    assert DS.cycle_label(DS.infer_interval_days(items)) == "3개월마다 지급"


def test_single_payment_gives_no_cycle_and_no_estimate():
    """1건만 있으면 주기를 알 수 없습니다. 억지로 만들지 않습니다."""
    one = td(items=[dist(day=(2026, 9, 1))])
    assert DS.infer_interval_days(one.items()) is None
    assert DS.estimate_next(one, TODAY) is None
    assert DS.cycle_label(None) == "지급 주기를 알 수 없음"


def test_no_history_gives_no_estimate():
    assert DS.estimate_next(td(items=[]), TODAY) is None


def test_estimate_uses_the_most_recent_amount_not_an_average():
    """평균을 내면 어떤 숫자인지 설명할 수 없습니다. 최근 실제 지급액을 그대로 씁니다."""
    items = [dist(day=(2026, 7, 15), amount=100.0),
             dist(day=(2026, 8, 15), amount=200.0),
             dist(day=(2026, 9, 15), amount=333.0)]
    est = DS.estimate_next(td(items=items), TODAY)
    assert est is not None
    assert est.distribution_per_share == 333.0
    assert est.status == config.STATUS_ESTIMATED
    assert est.payment_date > TODAY


def test_estimate_carries_a_reason_the_user_can_read():
    items = [dist(day=(2026, 8, 15)), dist(day=(2026, 9, 15))]
    est = DS.estimate_next(td(items=items), TODAY)
    assert "예상값" in est.note and "다를 수 있습니다" in est.note


def test_estimate_borrows_the_latest_known_tax_basis():
    items = [dist(day=(2026, 7, 15), tax=43.0),
             dist(day=(2026, 8, 15), tax=3.0),
             dist(day=(2026, 9, 15), tax=None)]      # 최근 건은 아직 미발표
    est = DS.estimate_next(td(items=items), TODAY)
    assert est.tax_basis_per_share == 3.0            # 값이 있던 가장 최근 건


def test_estimate_has_no_tax_basis_when_none_was_ever_published():
    items = [dist(day=(2026, 8, 15), tax=None), dist(day=(2026, 9, 15), tax=None)]
    est = DS.estimate_next(td(items=items), TODAY)
    assert est.tax_basis_per_share is None           # 0 으로 채우지 않습니다


def test_long_stopped_fund_is_not_estimated():
    """한참 전에 분배를 멈춘 상품을 '다음 달에 또 들어옵니다' 라고 하면 안 됩니다."""
    items = [dist(day=(2024, 1, 15)), dist(day=(2024, 2, 15))]
    assert DS.estimate_next(td(items=items), TODAY) is None


def test_upcoming_prefers_announced_over_estimate():
    announced = dist(day=(2026, 9, 25), amount=999.0)
    items = [dist(day=(2026, 8, 15)), dist(day=(2026, 9, 15)), announced]
    got = DS.upcoming(td(items=items), TODAY)
    assert len(got) == 1
    assert got[0].distribution_per_share == 999.0
    assert got[0].status == config.STATUS_CONFIRMED   # 발표된 값은 예상이 아닙니다

"""예상 로직 — 근거가 부족하면 예상하지 않는다."""

from __future__ import annotations

from datetime import date

from conftest import dist, td

import config
from models.distribution import DistributionSeries
from models.portfolio import Holding, Portfolio
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


# ================================================ 여러 갈래로 나눠 받기
def test_every_ticker_comes_back_even_though_they_are_fetched_in_parallel(monkeypatch):
    """나눠 받으면서 **한 종목이라도 빠지면** 그 종목의 배당금이 통째로
    화면에서 사라집니다. 에러는 안 납니다."""
    p = Portfolio()
    for code in ("069500", "498400", "402970", "360750", "133690"):
        p.add(Holding(ticker=code, market="KR", name=f"ETF {code}",
                      broker="증권사", account="일반", account_type="일반",
                      shares=10, avg_price=10000))

    def fake(market, ticker, name):
        return DistributionSeries(ticker=ticker, items=[], source="가짜",
                                  tax_basis_supported=True)

    monkeypatch.setattr(DS.registry, "get_distributions", fake)
    got = DS.fetch_all(p)
    assert set(got) == {("KR", c) for c in
                        ("069500", "498400", "402970", "360750", "133690")}
    assert all(td.ok for td in got.values())


def test_one_broken_ticker_does_not_take_the_others_down(monkeypatch):
    """종목 하나가 터져도 나머지는 살아야 합니다. 나눠 받으면 예외가 다른
    갈래에서 올라오므로 더 조심해야 합니다."""
    p = Portfolio()
    for code in ("069500", "498400", "402970"):
        p.add(Holding(ticker=code, market="KR", name=f"ETF {code}",
                      broker="증권사", account="일반", account_type="일반",
                      shares=10, avg_price=10000))

    def fake(market, ticker, name):
        if ticker == "498400":
            raise RuntimeError("펑")
        return DistributionSeries(ticker=ticker, items=[], source="가짜",
                                  tax_basis_supported=True)

    monkeypatch.setattr(DS.registry, "get_distributions", fake)
    got = DS.fetch_all(p)
    assert len(got) == 3
    assert got[("KR", "498400")].ok is False
    assert got[("KR", "498400")].error          # 왜 안 됐는지 말해 줘야 합니다
    assert got[("KR", "069500")].ok is True


def test_an_empty_portfolio_starts_no_threads(monkeypatch):
    called = []
    monkeypatch.setattr(DS.registry, "get_distributions",
                        lambda *a: called.append(a))
    assert DS.fetch_all(Portfolio()) == {}
    assert called == []


def test_we_do_not_hammer_the_issuer_servers():
    """빨라지자고 남의 서버를 한꺼번에 두드릴 이유는 없습니다.
    운용사가 우리를 막으면 과세표준이 통째로 사라집니다(실제로 겪었습니다)."""
    assert DS.MAX_WORKERS <= 4

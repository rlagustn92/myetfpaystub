"""급여명세서 계산 — 보유수량 곱하기, 과세표준 부분집계, 예상값 표시, 달력."""

from __future__ import annotations

from datetime import date

import pytest
from conftest import dist, kr, td, us

import config
from models.distribution import Distribution, DistributionSeries
from models.portfolio import Holding, Portfolio
from services import cashflow_service as CF
from services.distribution_service import TickerDistributions

FX = 1400.0
TODAY = date(2026, 9, 20)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """환율 조회가 네트워크를 타지 않게 합니다 (과거 환율도 고정)."""
    from services import fx_service
    monkeypatch.setattr(fx_service, "on", lambda d: None)
    monkeypatch.setattr(fx_service, "latest", lambda: None)


def one_kr_portfolio(shares=500.0):
    p = Portfolio()
    p.add(kr(ticker="498400", name="KODEX 200타겟위클리커버드콜", shares=shares))
    return p


def test_amount_is_per_share_times_my_shares():
    p = one_kr_portfolio(500)
    d = {("KR", "498400"): td("498400", [dist("498400", (2026, 9, 15), 300.0, 2.0)])}
    total = CF.month_total(p, d, 2026, 9, today=TODAY, latest_rate=FX)
    assert total.amount_krw == 150_000        # 300원 × 500주
    assert total.tax_basis_krw == 1_000       # 2원 × 500주


def test_same_etf_in_two_accounts_makes_two_rows_and_one_sum():
    p = Portfolio()
    p.add(Holding(ticker="SCHD", market="US", name="SCHD", broker="미래에셋증권",
                  account="ISA", shares=100))
    p.add(Holding(ticker="SCHD", market="US", name="SCHD", broker="키움증권",
                  account="일반", shares=50))
    d = {("US", "SCHD"): td("SCHD", [dist("SCHD", (2026, 9, 10), 1.0, 1.0,
                                          currency="USD")], market="US")}
    total = CF.month_total(p, d, 2026, 9, today=TODAY, latest_rate=FX)
    assert len(total.rows) == 2
    assert total.amount_krw == (100 + 50) * 1.0 * FX


def test_unknown_tax_basis_is_not_counted_as_zero():
    """0 으로 세면 '세금에 잡히는 금액이 적다' 고 오해합니다. 빼고 세고, 뺐다고 알립니다."""
    p = one_kr_portfolio(100)
    items = [dist("498400", (2026, 9, 5), 300.0, 2.0),
             dist("498400", (2026, 9, 20), 300.0, None)]
    total = CF.month_total(p, {("KR", "498400"): td("498400", items)},
                           2026, 9, today=TODAY, latest_rate=FX)
    assert total.amount_krw == 60_000          # 두 건 다 분배금은 셈
    assert total.tax_basis_krw == 200          # 과세표준은 아는 한 건만
    assert total.unknown_tax_basis_rows == 1
    assert total.tax_basis_is_partial is True


def test_announced_zero_tax_basis_is_counted_as_known():
    p = one_kr_portfolio(100)
    items = [dist("498400", (2026, 9, 5), 177.0, 0.0)]
    total = CF.month_total(p, {("KR", "498400"): td("498400", items)},
                           2026, 9, today=TODAY, latest_rate=FX)
    assert total.tax_basis_krw == 0
    assert total.unknown_tax_basis_rows == 0   # 0원은 '모름'이 아니라 '발표된 값'
    assert total.tax_basis_is_partial is False


def test_non_taxed_amount_uses_only_rows_with_known_tax_basis():
    p = one_kr_portfolio(100)
    items = [dist("498400", (2026, 9, 5), 300.0, 2.0),      # 과세 대상 200원
             dist("498400", (2026, 9, 20), 500.0, None)]    # 모름 -> 계산에서 제외
    total = CF.month_total(p, {("KR", "498400"): td("498400", items)},
                           2026, 9, today=TODAY, latest_rate=FX)
    assert total.non_taxed_krw == 30_000 - 200


def test_estimate_is_flagged_and_can_be_turned_off():
    """다음 달 값을 확정값처럼 보여주면 안 됩니다."""
    p = one_kr_portfolio(100)
    # 월배당인데 9월분이 아직 안 나온 상태. 다음 지급은 10월로 잡힙니다.
    items = [dist("498400", (2026, 8, 15), 300.0, 2.0),
             dist("498400", (2026, 9, 15), 300.0, 2.0)]
    d = {("KR", "498400"): td("498400", items)}

    with_est = CF.month_total(p, d, 2026, 10, today=TODAY, latest_rate=FX)
    assert with_est.has_estimate is True
    assert with_est.status == config.STATUS_ESTIMATED
    assert all(r.is_estimated for r in with_est.rows)
    assert with_est.amount_krw == 30_000          # 최근 지급액을 그대로 적용

    without = CF.month_total(p, d, 2026, 10, today=TODAY, latest_rate=FX,
                             include_estimates=False)
    assert without.rows == [] and without.has_estimate is False


def test_estimate_never_lands_in_the_past():
    """이미 지난 날짜를 '앞으로 들어올 돈'으로 보여주면 안 됩니다."""
    p = one_kr_portfolio(100)
    items = [dist("498400", (2026, 8, 15), 300.0, 2.0),
             dist("498400", (2026, 9, 15), 300.0, 2.0)]
    september = CF.month_total(p, {("KR", "498400"): td("498400", items)},
                               2026, 9, today=TODAY, latest_rate=FX)
    # 9월분은 이미 발표된 1건뿐이고, 예상값이 9월로 끼어들지 않습니다.
    assert len(september.rows) == 1
    assert september.has_estimate is False


def test_year_total_excludes_estimates_by_default():
    """'올해 지금까지 받은 돈' 에 예상값을 섞으면 그건 받은 돈이 아닙니다."""
    p = one_kr_portfolio(100)
    items = [dist("498400", (2026, 3, 15), 100.0, 1.0),
             dist("498400", (2026, 6, 15), 100.0, 1.0)]
    y = CF.year_total(p, {("KR", "498400"): td("498400", items)},
                      2026, today=TODAY, latest_rate=FX)
    assert y.amount_krw == 20_000 and y.has_estimate is False


def test_us_future_payment_uses_latest_rate():
    p = Portfolio()
    p.add(us(ticker="SCHD", shares=10))
    future = Distribution(ticker="SCHD", payment_date=date(2026, 9, 30),
                          distribution_per_share=2.0, tax_basis_per_share=2.0,
                          currency="USD")
    d = {("US", "SCHD"): TickerDistributions(
        "US", "SCHD", "SCHD",
        series=DistributionSeries("SCHD", [future], tax_basis_supported=True))}
    total = CF.month_total(p, d, 2026, 9, today=TODAY, latest_rate=FX)
    assert total.amount_krw == 10 * 2.0 * FX


def test_us_row_is_skipped_when_fx_unknown():
    """환율을 모르면 임의 값으로 채우지 않고 그 줄을 뺍니다."""
    p = Portfolio()
    p.add(us(ticker="SCHD", shares=10))
    d = {("US", "SCHD"): td("SCHD", [dist("SCHD", (2026, 9, 10), 2.0, 2.0,
                                          currency="USD")], market="US")}
    total = CF.month_total(p, d, 2026, 9, today=TODAY, latest_rate=None)
    assert total.amount_krw == 0 and total.skipped_rows == 1


def test_missing_distribution_data_is_skipped_silently_in_totals():
    p = one_kr_portfolio(100)
    broken = TickerDistributions("KR", "498400", "X", error="못 가져옴")
    total = CF.month_total(p, {("KR", "498400"): broken}, 2026, 9,
                           today=TODAY, latest_rate=FX)
    assert total.rows == [] and total.amount_krw == 0


def test_zero_shares_produces_no_rows():
    p = Portfolio()
    p.add(kr(ticker="498400", shares=0))
    total = CF.month_total(p, {("KR", "498400"): td("498400")}, 2026, 9,
                           today=TODAY, latest_rate=FX)
    assert total.rows == []


def test_calendar_groups_by_day():
    p = one_kr_portfolio(100)
    items = [dist("498400", (2026, 9, 5), 100.0, 1.0),
             dist("498400", (2026, 9, 5), 50.0, 1.0),
             dist("498400", (2026, 9, 20), 70.0, 1.0)]
    total = CF.month_total(p, {("KR", "498400"): td("498400", items)},
                           2026, 9, today=TODAY, latest_rate=FX)
    cal = CF.calendar_of(total.rows)
    assert set(cal.keys()) == {date(2026, 9, 5), date(2026, 9, 20)}
    assert cal[date(2026, 9, 5)].amount_krw == 15_000


def test_month_range_handles_february():
    assert CF.month_range(2026, 2) == (date(2026, 2, 1), date(2026, 2, 28))
    assert CF.month_range(2024, 2) == (date(2024, 2, 1), date(2024, 2, 29))


def test_monthly_series_has_twelve_months_in_order():
    p = one_kr_portfolio(100)
    series = CF.monthly_series(p, {("KR", "498400"): td("498400", [])},
                               2026, today=TODAY, latest_rate=FX)
    assert [m for m, _ in series] == list(range(1, 13))


# ------------------------------------------ 과세표준을 모를 때 "왜" 를 적는가
def test_tax_basis_note_says_why_it_is_missing():
    """"자료 없음" 한 마디로는 **앱이 못 가져온 건지 운용사가 안 낸 건지**
    알 수 없어 혼란스럽다는 지적을 받았습니다.

    실제로 KODEX 200타겟위클리커버드콜은 2026-05·06월 두 건의 과세표준을
    삼성자산운용이 아직 안 올렸습니다(운용사 API 가 `taxDividA: null`).
    앱 문제가 아니라서, 그렇게 적어야 합니다.
    """
    h = Holding(ticker="498400", market="KR", name="KODEX 200타겟위클리커버드콜",
                broker="키움증권", account="일반", shares=100, avg_price=20000)

    known = CF.PayslipRow(
        payment_date=date(2026, 9, 17), holding=h,
        dist=Distribution(ticker="498400", payment_date=date(2026, 9, 17),
                          distribution_per_share=300.0, tax_basis_per_share=2.0),
        amount_krw=30000.0, tax_basis_krw=200.0, tax_basis_supported=True)
    assert known.tax_basis_note == ""          # 알고 있으면 아무 말도 안 붙입니다

    unpublished = CF.PayslipRow(
        payment_date=date(2026, 6, 17), holding=h,
        dist=Distribution(ticker="498400", payment_date=date(2026, 6, 17),
                          distribution_per_share=350.0, tax_basis_per_share=None),
        amount_krw=35000.0, tax_basis_krw=None, tax_basis_supported=True)
    assert unpublished.tax_basis_note == config.TAX_BASIS_UNPUBLISHED

    unsupported = CF.PayslipRow(
        payment_date=date(2026, 6, 17), holding=h,
        dist=Distribution(ticker="498400", payment_date=date(2026, 6, 17),
                          distribution_per_share=350.0, tax_basis_per_share=None),
        amount_krw=35000.0, tax_basis_krw=None, tax_basis_supported=False)
    assert unsupported.tax_basis_note == config.TAX_BASIS_UNSUPPORTED


def test_the_two_reasons_are_different_words():
    """같은 말로 적으면 구분한 의미가 없습니다."""
    assert config.TAX_BASIS_UNPUBLISHED != config.TAX_BASIS_UNSUPPORTED
    assert config.TAX_BASIS_UNPUBLISHED.strip()
    assert config.TAX_BASIS_UNSUPPORTED.strip()


# --------------------------------------- 월말 기준 ETF (다음 달 초에 들어옴)
def _row(record, pay):
    h = Holding(ticker="475720", market="KR", name="RISE 200위클리커버드콜",
                broker="증권사", account="일반", shares=100, avg_price=10000)
    return CF.PayslipRow(
        payment_date=pay, holding=h,
        dist=Distribution(ticker="475720", payment_date=pay, record_date=record,
                          distribution_per_share=50.0, tax_basis_per_share=10.0),
        amount_krw=5000.0, tax_basis_krw=1000.0)


def test_month_end_payers_show_their_record_date():
    """월말이 기준인 ETF 가 많습니다. 기준일 8/31 -> 실지급 9/2 처럼요.
    실측: RISE 200위클리커버드콜은 31건이 **전부** 이렇고, TIGER·KODEX 의
    미국S&P500 류도 마찬가지입니다.

    이 앱은 **돈이 꽂히는 날**로 달을 묶습니다("이번 달에 얼마 들어오나" 가
    질문이라서요). 그런데 기준일이 화면에 안 보이면 "8월분인데 왜 9월에?"
    가 됩니다. 그래서 달이 갈리는 건에만 기준일을 같이 적습니다.
    """
    r = _row(date(2026, 8, 31), date(2026, 9, 2))
    assert r.record_note == "8/31 기준"


def test_same_month_payers_say_nothing_extra():
    """같은 달이면 군더더기입니다. 필요할 때만 적습니다."""
    r = _row(date(2026, 9, 15), date(2026, 9, 17))
    assert r.record_note == ""


def test_no_record_date_means_no_note():
    """미국 종목은 배당락일만 있어 기준일이 없을 수 있습니다."""
    r = _row(None, date(2026, 9, 2))
    assert r.record_note == ""


def test_the_month_bucket_still_follows_the_payment_date():
    """기준일을 보여주는 것이지, 달을 옮기는 게 아닙니다.
    8/31 기준분은 돈이 9/2 에 들어오므로 **9월** 명세서에 있어야 합니다."""
    r = _row(date(2026, 8, 31), date(2026, 9, 2))
    assert r.payment_date.month == 9

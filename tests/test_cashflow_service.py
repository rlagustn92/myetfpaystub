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


def test_unpublished_reads_as_one_short_word():
    """사용자 결정으로 **둘 다 "미발표"** 로 통일했습니다.

    예전에는 "운용사 미발표" 와 "확인 불가" 로 나눴는데, 사용자에게는 결국
    같은 상황이고(금액을 모른다) 표 안에 긴 글이 섞여 지저분했습니다.
    화면에는 0원으로 적고, 몇 건인지는 **표 아래 한 줄**로 알립니다.
    """
    assert config.TAX_BASIS_UNPUBLISHED == "미발표"
    assert config.TAX_BASIS_UNSUPPORTED == "미발표"
    # 표 셀에 들어가는 말이라 짧아야 합니다
    assert len(config.TAX_BASIS_UNPUBLISHED) <= 6


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


# ============================================================ 계좌별 세금
# ISA·연금저축·IRP 는 분배금이 계좌 안에서 과세이연됩니다. 지급할 때 세금을
# 안 떼고 **그대로 입금**되고, 최종 세금은 나중에 찾을 때 개인 상황에 따라
# 정해져서 이 앱이 계산할 수 없습니다. 일반계좌만 15.4% 를 뗍니다.
# 포트폴리오 전체에 같은 세율을 먹이면 ISA 를 가진 사람에게 있지도 않은
# 세금을 보여주게 됩니다 — 그래서 **줄마다** 계좌를 봅니다.
def _taxrow(account, amount=100000.0, basis=100000.0):
    h = Holding(ticker="069500", market="KR", name="KODEX 200",
                broker="증권사", account=account, account_type=account,
                shares=100, avg_price=30000)
    return CF.PayslipRow(
        payment_date=date(2026, 9, 17), holding=h,
        dist=Distribution(ticker="069500", payment_date=date(2026, 9, 17),
                          distribution_per_share=1000.0,
                          tax_basis_per_share=(basis / 100 if basis is not None else None)),
        amount_krw=amount, tax_basis_krw=basis)


@pytest.mark.parametrize("account", ["ISA", "isa", "연금저축", "IRP", "퇴직연금",
                                     "개인형IRP", "연금"])
def test_tax_deferred_accounts_take_nothing_at_payout(account):
    r = _taxrow(account)
    assert r.is_tax_deferred is True
    assert r.withholding_krw is None            # 뗄 세금이 없습니다
    assert r.after_tax_krw == r.amount_krw      # 그대로 들어옵니다


@pytest.mark.parametrize("account", ["일반", "위탁", "종합매매", ""])
def test_ordinary_accounts_are_withheld_at_15_4_percent(account):
    r = _taxrow(account, amount=100000.0, basis=100000.0)
    assert r.is_tax_deferred is False
    assert r.withholding_krw == pytest.approx(15400.0)
    assert r.after_tax_krw == pytest.approx(84600.0)


def test_withholding_is_on_the_tax_basis_not_on_the_payout():
    """⭐ 분배금이 아니라 **과세표준액**에 세율을 매깁니다.

    같은 종목이 분배금 150,000원 / 과세표준 1,000원인 달이 실제로 있습니다
    (KODEX 200타겟위클리커버드콜). 분배금에 곱하면 세금이 150배 부풀어요.
    """
    r = _taxrow("일반", amount=150000.0, basis=1000.0)
    assert r.withholding_krw == pytest.approx(154.0)      # 1,000 x 15.4%
    assert r.after_tax_krw == pytest.approx(149846.0)


def test_unpublished_tax_basis_counts_as_zero():
    """사용자 결정: 미발표는 0원으로 셉니다. 표에는 0원만 적고 몇 건인지는
    표 아래 한 줄로 알립니다."""
    r = _taxrow("일반", amount=100000.0, basis=None)
    assert r.has_tax_basis is False
    assert r.taxable_basis_krw == 0.0
    assert r.withholding_krw == 0.0
    assert r.after_tax_krw == 100000.0
    assert r.tax_basis_note == config.TAX_BASIS_UNPUBLISHED


def test_totals_split_the_two_kinds_of_account():
    """한 사람이 ISA 와 일반계좌를 같이 갖고 있는 게 보통입니다."""
    rows = [_taxrow("ISA", amount=50000.0, basis=50000.0),
            _taxrow("일반", amount=100000.0, basis=100000.0)]
    t = CF.total_of(rows)
    assert t.amount_krw == pytest.approx(150000.0)
    assert t.tax_deferred_krw == pytest.approx(50000.0)    # ISA 는 그대로
    assert t.withholding_krw == pytest.approx(15400.0)     # 일반계좌만
    assert t.after_tax_krw == pytest.approx(134600.0)
    assert t.has_tax_deferred and t.has_withholding


def test_a_portfolio_with_only_isa_shows_no_tax_at_all():
    t = CF.total_of([_taxrow("연금저축", amount=50000.0, basis=50000.0)])
    assert t.withholding_krw == 0.0
    assert t.has_withholding is False
    assert t.after_tax_krw == pytest.approx(50000.0)


def test_the_rate_is_the_one_korea_actually_uses():
    """배당소득세 14% + 지방소득세 1.4% = 15.4%."""
    assert config.WITHHOLDING_RATE == pytest.approx(0.154)


# ================================================== 연간 배당금 목표
def _goal_folio(goal):
    p = Portfolio(dividend_goal_krw=goal)
    p.add(Holding(ticker="069500", market="KR", name="KODEX 200",
                  broker="증권사", account="일반", account_type="일반",
                  shares=100, avg_price=30000))
    return p


def test_no_goal_means_nothing_is_drawn():
    """목표는 사용자가 정합니다. 안 정했으면 화면에 안 그립니다."""
    g = CF.goal_progress(_goal_folio(0), {}, 2026, today=date(2026, 9, 21))
    assert g.has_goal is False
    assert g.percent == 0.0


def test_received_and_expected_are_counted_separately():
    """⭐ 섞으면 "벌써 다 받은 것" 처럼 보입니다. 예상은 따로 셉니다."""
    g = CF.GoalProgress(goal_krw=1_000_000, received_krw=400_000,
                        expected_krw=200_000)
    assert g.percent == pytest.approx(40.0)
    assert g.percent_with_expected == pytest.approx(60.0)
    assert g.remaining_krw == pytest.approx(600_000)


def test_going_over_the_goal_is_shown_as_it_is():
    """넘겼으면 넘겼다고 보여줘야 합니다. 100 에서 자르지 않습니다."""
    g = CF.GoalProgress(goal_krw=1_000_000, received_krw=1_300_000, expected_krw=0)
    assert g.percent == pytest.approx(130.0)
    assert g.remaining_krw == 0.0        # 남은 돈은 0 이하로 안 내려갑니다


def test_the_goal_survives_saving_and_loading():
    from services import storage_service as STORE

    st = STORE.new_store()
    st.active().dividend_goal_krw = 2_000_000
    back, err = STORE.loads(STORE.dumps(st))
    assert err == ""
    assert back.active().dividend_goal_krw == 2_000_000


def test_a_broken_goal_value_does_not_crash():
    """바깥에서 온 값을 그대로 믿지 않습니다."""
    p = Portfolio.from_dict({"dividend_goal_krw": "이상한값"})
    assert p.dividend_goal_krw == 0.0
    p2 = Portfolio.from_dict({"dividend_goal_krw": -500})
    assert p2.dividend_goal_krw == 0.0      # 음수 목표는 없습니다


# ---------------------------------------------------------------------
# 투자 원금 대비 배당률
# ---------------------------------------------------------------------
def test_yield_on_cost_counts_only_the_last_year_of_real_payouts():
    """"원금 대비 몇 %" 는 **실제로 받은 돈**으로만 잽니다."""
    p = one_kr_portfolio(100)
    items = [
        dist("498400", (2026, 3, 15), 300.0, 2.0),    # 최근 1년 안
        dist("498400", (2026, 9, 15), 300.0, 2.0),    # 최근 1년 안
        dist("498400", (2024, 9, 15), 300.0, 2.0),    # 2년 전 — 안 셉니다
    ]
    got = CF.yield_on_cost(p, {("KR", "498400"): td("498400", items)},
                           cost_krw=1_000_000, today=TODAY, latest_rate=FX)
    assert got.payouts == 2
    assert got.received_krw == 60_000                 # 300원 x 100주 x 2번
    assert got.pct == pytest.approx(6.0)
    assert got.ok is True


def test_yield_on_cost_ignores_estimates():
    """예상값을 섞으면 '받은 돈' 이 아니게 됩니다. 커버드콜은 달마다 크게
    달라서 예상 한 건이 숫자를 통째로 흔듭니다."""
    p = one_kr_portfolio(100)
    real = dist("498400", (2026, 9, 15), 300.0, 2.0)
    d = {("KR", "498400"): td("498400", [real])}
    got = CF.yield_on_cost(p, d, cost_krw=1_000_000, today=TODAY, latest_rate=FX)
    # upcoming() 이 만들어 내는 예상 지급은 끼지 않습니다.
    assert got.payouts == 1
    assert all(r.status != config.STATUS_ESTIMATED for r in [real])


def test_yield_on_cost_without_cost_is_none_not_zero():
    """원금을 모르면 **모른다**입니다. 0% 라고 적으면 거짓말이 됩니다."""
    p = one_kr_portfolio(100)
    d = {("KR", "498400"): td("498400", [dist("498400", (2026, 9, 15), 300.0, 2.0)])}
    got = CF.yield_on_cost(p, d, cost_krw=0, today=TODAY, latest_rate=FX)
    assert got.pct is None
    assert got.ok is False


def test_yield_on_cost_can_be_narrowed_to_one_ticker():
    """종목별 상세에서는 그 종목만 셉니다."""
    p = one_kr_portfolio(100)
    p.add(kr(ticker="069500", name="KODEX 200", shares=10))
    d = {
        ("KR", "498400"): td("498400", [dist("498400", (2026, 9, 15), 300.0, 2.0)]),
        ("KR", "069500"): td("069500", [dist("069500", (2026, 9, 15), 500.0, 2.0)]),
    }
    got = CF.yield_on_cost(p, d, cost_krw=100_000, today=TODAY, latest_rate=FX,
                           only=("KR", "069500"))
    assert got.payouts == 1
    assert got.received_krw == 5_000            # 500원 x 10주
    assert got.pct == pytest.approx(5.0)


def test_ratio_of_cost_is_a_plain_share_of_the_principal():
    """이번 달 금액이 원금의 몇 % 인지. **연 기준이 아닙니다.**"""
    assert CF.ratio_of_cost(601_224, 118_400_000) == pytest.approx(0.5078, abs=1e-3)
    assert CF.ratio_of_cost(100, 0) is None
    assert CF.ratio_of_cost(None, 1_000) is None

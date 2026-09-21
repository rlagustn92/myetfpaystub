"""
전술판 — 등번호는 실제 보유 비중, 자리는 종목 단위로 기억.

⚠ 이 서비스의 등번호는 사용자가 입력하는 목표비중이 아니라 **수량 × 현재가로
저절로 정해지는 실제 비중**입니다. 원본(ETF MANAGER)과 다른 유일한 지점이라
여기서 확실히 못 박아 둡니다.
"""

from __future__ import annotations

from datetime import date

import pytest
from conftest import dist, kr, td, us

from components import pitch_grid
from data.providers.base import PriceQuote
from models.portfolio import Holding, Portfolio, ticker_key
from services import cashflow_service as CF, pitch_service
from services import portfolio_service as PS

FX = 1400.0


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    from services import fx_service
    monkeypatch.setattr(fx_service, "on", lambda d: None)
    monkeypatch.setattr(fx_service, "latest", lambda: None)


def q(ticker, price, currency):
    return PriceQuote(ticker=ticker, price=price, currency=currency,
                      as_of=date(2026, 9, 18), source="테스트")


def two_stock_summary():
    p = Portfolio()
    p.add(kr(ticker="069500", name="KODEX 200", shares=100, avg=30000))
    p.add(us(ticker="SCHD", shares=10, avg=70.0))
    s = PS.summarize(p, quotes={
        ("KR", "069500"): q("069500", 30000, "KRW"),     # 300만원
        ("US", "SCHD"): q("SCHD", 100.0, "USD"),          # 10 × 100 × 1400 = 140만원
    }, usdkrw=FX)
    return p, s


# ------------------------------------------------------------- 등번호
def test_jersey_number_is_the_real_share_of_my_assets():
    p, s = two_stock_summary()
    groups = PS.group_by_ticker(s)
    pitch_service.ensure_slots(p, groups)
    players = {pl["id"]: pl for pl in pitch_service.build_players(s, p, groups).players}

    total = 3_000_000 + 1_400_000
    assert players["KR:069500"]["weight_pct"] == pytest.approx(3_000_000 / total * 100)
    assert players["US:SCHD"]["weight_pct"] == pytest.approx(1_400_000 / total * 100)
    assert sum(pl["weight_pct"] for pl in players.values()) == pytest.approx(100.0)


def test_captain_is_the_biggest_holding():
    p, s = two_stock_summary()
    groups = PS.group_by_ticker(s)
    payload = pitch_service.build_players(s, p, groups)
    assert payload.captain_key == "KR:069500"
    assert [pl["id"] for pl in payload.players if pl["captain"]] == ["KR:069500"]


def test_unpriced_holding_gets_no_number_instead_of_zero():
    """가격을 못 가져왔는데 0% 로 찍으면 '거의 안 들고 있다' 로 오해합니다."""
    p = Portfolio()
    p.add(kr(ticker="069500", name="KODEX 200", shares=100, avg=30000))
    p.add(us(ticker="SCHD", shares=10, avg=70.0))
    s = PS.summarize(p, quotes={
        ("KR", "069500"): q("069500", 30000, "KRW"),
        ("US", "SCHD"): "[SCHD] 가격을 확인하지 못했습니다.",
    }, usdkrw=FX)
    payload = pitch_service.build_players(s, p, PS.group_by_ticker(s))
    schd = [pl for pl in payload.players if pl["id"] == "US:SCHD"][0]
    assert schd["weight_pct"] is None
    assert schd["has_warning"] is True
    assert payload.unpriced == ["Schwab US Dividend Equity ETF"]


def test_us_holdings_wear_the_away_kit():
    p, s = two_stock_summary()
    players = {pl["id"]: pl for pl in
               pitch_service.build_players(s, p, PS.group_by_ticker(s)).players}
    assert players["US:SCHD"]["kit"]["style"] == "us"
    assert players["KR:069500"]["kit"]["brand"] == "KODEX"


def test_long_korean_names_are_shortened_for_the_card():
    p = Portfolio()
    p.add(kr(ticker="498400", name="KODEX 200타겟위클리커버드콜", shares=10, avg=1))
    s = PS.summarize(p, quotes={("KR", "498400"): q("498400", 20000, "KRW")}, usdkrw=FX)
    label = pitch_service.build_players(s, p, PS.group_by_ticker(s)).players[0]["label"]
    assert label and len(label) < len("KODEX 200타겟위클리커버드콜")
    assert "KODEX" not in label           # 브랜드는 유니폼 색으로 이미 보입니다


# ------------------------------------------------------------- 자리
def test_same_etf_in_three_accounts_gets_one_card_and_one_slot():
    p = Portfolio()
    for broker in ("미래에셋증권", "키움증권", "삼성증권"):
        p.add(Holding(ticker="SCHD", market="US", name="SCHD", broker=broker,
                      shares=10, avg_price=70.0))
    s = PS.summarize(p, quotes={("US", "SCHD"): q("SCHD", 100.0, "USD")}, usdkrw=FX)
    groups = PS.group_by_ticker(s)
    pitch_service.ensure_slots(p, groups)
    payload = pitch_service.build_players(s, p, groups)
    assert len(payload.players) == 1
    assert len(p.slots) == 1
    assert payload.players[0]["weight_pct"] == pytest.approx(100.0)


def test_slots_do_not_collide():
    p = Portfolio()
    for i in range(8):
        p.add(kr(ticker=f"00000{i}", name=f"KODEX 배당{i}", shares=1, avg=1))
    s = PS.summarize(p, quotes={("KR", f"00000{i}"): q(f"00000{i}", 1000, "KRW")
                                for i in range(8)}, usdkrw=FX)
    groups = PS.group_by_ticker(s)
    pitch_service.ensure_slots(p, groups)
    assert len(set(p.slots.values())) == 8
    assert all(pitch_grid.is_slot(v) for v in p.slots.values())


def test_existing_slots_are_kept():
    p, s = two_stock_summary()
    p.slots["KR:069500"] = "ST-C"
    pitch_service.ensure_slots(p, PS.group_by_ticker(s))
    assert p.slots["KR:069500"] == "ST-C"


def test_sold_out_ticker_frees_its_slot():
    """안 지우면 종목을 판 뒤에도 그 자리가 계속 막혀 있습니다."""
    p, s = two_stock_summary()
    pitch_service.ensure_slots(p, PS.group_by_ticker(s))
    p.holdings = [h for h in p.holdings if h.ticker != "SCHD"]
    assert pitch_service.prune_slots(p) is True
    assert "US:SCHD" not in p.slots
    assert "KR:069500" in p.slots


def test_drag_result_is_applied_but_garbage_is_ignored():
    """컴포넌트에서 온 값을 그대로 믿지 않습니다."""
    p = Portfolio()
    assert pitch_service.apply_assignments(p, {"KR:069500": "DF-L"}) is True
    assert p.slots == {"KR:069500": "DF-L"}
    assert pitch_service.apply_assignments(p, {"KR:069500": "DF-L"}) is False   # 같은 값
    assert pitch_service.apply_assignments(p, {"KR:069500": "없는자리"}) is False
    assert pitch_service.apply_assignments(p, "문자열") is False
    assert p.slots == {"KR:069500": "DF-L"}


def test_slots_survive_save_and_load():
    p, s = two_stock_summary()
    pitch_service.ensure_slots(p, PS.group_by_ticker(s))
    before = dict(p.slots)
    back = Portfolio.from_dict(p.to_dict())
    assert back.slots == before


def test_broken_slots_in_a_saved_file_are_dropped_not_crashed():
    back = Portfolio.from_dict({"holdings": [], "slots": {"KR:069500": "DF-C", "x": 5, 7: "a"}})
    assert back.slots == {"KR:069500": "DF-C"}


# ------------------------------------------------------------- 초기 배치
@pytest.mark.parametrize("name,row", [
    ("KODEX 레버리지", "ST"),
    ("TIGER 미국S&P500", "AM"),
    ("KODEX 200", "AM"),
    ("ACE 미국배당다우존스", "MC"),
    ("KODEX 200타겟위클리커버드콜", "MC"),     # ⚠ "200" 보다 "커버드콜" 이 먼저
    ("KODEX 종합채권(AA-이상)액티브", "DF"),
    ("TIGER CD금리플러스액티브", "GK"),
    ("처음 보는 이름", "MC"),                  # 모르면 중앙
])
def test_initial_row_guess(name, row):
    assert pitch_service.guess_row("KR", "", name) == row


# ------------------------------------------------------------- 공유
def test_share_rows_match_what_the_pitch_shows():
    """📸 이미지와 📋 텍스트가 다른 숫자를 쓰면 같은 포트폴리오가 두 값으로 보입니다."""
    p, s = two_stock_summary()
    groups = PS.group_by_ticker(s)
    d = {("KR", "069500"): td("069500", [dist("069500", (2026, 9, 10), 100.0, 1.0)]),
         ("US", "SCHD"): td("SCHD", [], market="US")}
    tm = CF.month_total(p, d, 2026, 9, today=date(2026, 9, 20), latest_rate=FX)
    rows = pitch_service.share_rows(s, groups, tm)
    players = {pl["id"]: pl for pl in pitch_service.build_players(s, p, groups).players}

    assert [r.name for r in rows] == ["KODEX 200 (069500)", "SCHD"]
    assert rows[0].weight_pct == pytest.approx(players["KR:069500"]["weight_pct"])
    assert rows[0].month_krw == 100.0 * 100            # 100원 × 100주
    assert rows[1].month_krw is None                   # 이번 달 지급 없음


def test_comment_text_has_no_broker_or_account_names():
    """공유 글은 어디에 붙여넣을지 모릅니다. '미래에셋 ISA 에 얼마' 는 남에게
    보여줄 이유가 없는 정보라 넣지 않습니다."""
    from services import share_service
    p, s = two_stock_summary()
    rows = pitch_service.share_rows(
        s, PS.group_by_ticker(s),
        CF.total_of([], label=""))
    text = share_service.comment_text(
        portfolio_name="내 포트폴리오", rows=rows, total_value_krw=s.total_value_krw,
        month_krw=0.0, month_label="9월", year_krw=0.0, year_tax_basis_krw=0.0,
        today=date(2026, 9, 20))
    assert "미래에셋" not in text and "키움" not in text
    assert "ISA" not in text and "일반" not in text
    assert "MY ETF 급여명세서" in text
    assert "참고용" in text                      # 고지는 반드시 같이 갑니다
    assert "KODEX 200 (069500)" in text


def test_ticker_key_is_stable():
    assert ticker_key("kr", "069500") == "KR:069500"
    assert ticker_key("US", "schd") == "US:SCHD"


def test_more_tickers_than_slots_is_reported_not_silently_piled_up():
    """자리는 26개뿐입니다. 넘치는 종목을 조용히 가운데 겹쳐 두면
    '왜 카드가 사라졌지' 가 됩니다."""
    n = len(pitch_grid.all_slots()) + 3
    p = Portfolio()
    codes = [f"{i:06d}" for i in range(n)]
    for c in codes:
        p.add(kr(ticker=c, name=f"KODEX 배당{c}", shares=1, avg=1))
    s = PS.summarize(p, quotes={("KR", c): q(c, 1000, "KRW") for c in codes}, usdkrw=FX)
    groups = PS.group_by_ticker(s)
    pitch_service.ensure_slots(p, groups)
    payload = pitch_service.build_players(s, p, groups)
    assert len(p.slots) == len(pitch_grid.all_slots())
    assert len(payload.no_slot) == 3


# ------------------------------------------------ ⚽ 포지션 자동 정리
def _folio_with(*specs):
    """(market, ticker, name, value) 들로 포트폴리오와 그룹을 만듭니다."""
    p = Portfolio()
    groups = []
    for mk, tk, nm, val in specs:
        p.add(Holding(ticker=tk, market=mk, name=nm, broker="증권사", account="일반",
                      shares=1, avg_price=val))
        groups.append(_Group(mk, tk, nm, val))
    groups.sort(key=lambda g: -g.value)            # 평가금액 큰 순 (실제와 같게)
    return p, groups


class _Group:
    """TickerGroup 대신 쓰는 최소한의 그릇 (tidy 가 보는 것만 들고 있습니다)."""

    def __init__(self, market, ticker, name, value):
        self.market, self.ticker, self.name, self.value = market, ticker, name, value


def test_tidy_puts_each_kind_on_its_own_line():
    """채권은 뒤, 지수는 앞. 자리에 뜻이 생깁니다."""
    p, groups = _folio_with(
        ("KR", "069500", "KODEX 200", 400),
        ("KR", "273130", "KODEX 종합채권액티브", 300),
        ("KR", "498400", "KODEX 200타겟위클리커버드콜", 200),
        ("KR", "357870", "TIGER CD금리투자KIS", 100),
    )
    pitch_service.tidy(p, groups)
    row = lambda tk: pitch_grid.split(p.slots[ticker_key("KR", tk)])[0]
    assert row("069500") == "AM"          # 대표지수 -> 공격
    assert row("498400") == "MC"          # 커버드콜 -> 미드필드
    assert row("273130") == "DF"          # 채권 -> 수비
    assert row("357870") == "GK"          # 현금성 -> 골키퍼


def test_tidy_reports_how_many_moved_and_is_idempotent():
    """두 번 눌러도 또 옮기면 안 됩니다. 눌렀는데 아무 일도 안 일어난 것처럼
    보여야 정상입니다."""
    p, groups = _folio_with(
        ("KR", "069500", "KODEX 200", 400),
        ("KR", "273130", "KODEX 종합채권액티브", 300),
    )
    first = pitch_service.tidy(p, groups)
    assert first == 2
    assert pitch_service.tidy(p, groups) == 0


def test_tidy_overrides_a_hand_placed_slot():
    """`ensure_slots` 는 빈 종목만 채우지만, `tidy` 는 손으로 옮긴 것까지
    다시 놓습니다. 그게 이 버튼의 뜻입니다(그래서 버튼일 때만 부릅니다)."""
    p, groups = _folio_with(("KR", "273130", "KODEX 종합채권액티브", 300))
    key = ticker_key("KR", "273130")
    p.slots[key] = "ST-C"                      # 채권을 최전방에 손으로 올려둠
    pitch_service.ensure_slots(p, groups)
    assert p.slots[key] == "ST-C"              # 자동 배치는 건드리지 않습니다
    assert pitch_service.tidy(p, groups) == 1
    assert pitch_grid.split(p.slots[key])[0] == "DF"


def test_tidy_never_puts_two_tickers_on_one_slot():
    p, groups = _folio_with(*[
        ("KR", f"00{i:04d}", f"KODEX 커버드콜{i}", 100 - i) for i in range(12)
    ])
    pitch_service.tidy(p, groups)
    slots = list(p.slots.values())
    assert len(slots) == len(set(slots))


def test_tidy_drops_slots_it_cannot_place_instead_of_colliding():
    """26자리가 다 차면 남는 종목은 자리를 비웁니다. 옛 자리를 그대로 두면
    새로 놓은 종목과 겹쳐서 카드가 포개집니다."""
    total = len(pitch_grid.all_slots())
    p, groups = _folio_with(*[
        ("KR", f"{i:06d}", f"KODEX 종목{i}", 1000 - i) for i in range(total + 3)
    ])
    pitch_service.tidy(p, groups)
    slots = list(p.slots.values())
    assert len(slots) == total
    assert len(slots) == len(set(slots))


def test_formation_reads_the_actual_placement_not_the_kind():
    """손으로 옮겼으면 그게 사용자의 뜻입니다. 놓인 자리를 셉니다."""
    p, groups = _folio_with(("KR", "273130", "KODEX 종합채권액티브", 300))
    p.slots[ticker_key("KR", "273130")] = "ST-C"
    assert pitch_service.formation_counts(p) == {"공격": 1, "미드필드": 0, "수비": 0}
    assert pitch_service.formation(p) == "0-0-1"


def test_formation_is_empty_when_nothing_is_placed():
    assert pitch_service.formation(Portfolio()) == ""

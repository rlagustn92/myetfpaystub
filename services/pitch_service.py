"""
services/pitch_service.py  --  내 보유 ETF 를 축구 전술판 위에 세우는 곳
=========================================================================

전술판 컴포넌트(components/football_pitch)는 ETF MANAGER 2027 에서 검증된 것을
그대로 옮겨 왔습니다. **다른 건 여기서 넘겨주는 숫자뿐입니다.**

    ETF MANAGER  등번호 = 앞으로 담을 목표비중
    이 서비스     등번호 = **지금 실제로 들고 있는 비중**

그래서 이 앱에서는 사용자가 비중을 입력하지 않습니다. 수량 × 현재가로 저절로
정해지고, 값이 오르내리면 등번호도 같이 바뀝니다.

슬롯(자리)은 종목 단위로 기억합니다
-----------------------------------
같은 ETF 를 세 계좌에 나눠 갖고 있어도 전술판에는 카드가 **하나만** 섭니다.
그래서 자리는 보유 줄이 아니라 티커에 붙이고(`Portfolio.slots`), 저장 파일에
같이 들어갑니다.

처음 자리는 앱이 정해 주고, 마음에 안 들면 끌어다 옮기면 됩니다. 이건 데이터가
아니라 **보기 좋으라고 잡아주는 초기 배치**일 뿐입니다 — 어떤 평가나 추천도
아닙니다.
"""

from __future__ import annotations

from dataclasses import dataclass

from components import pitch_grid, pitch_kit
from models.portfolio import MARKET_US, Portfolio, ticker_key
from services.cashflow_service import PeriodTotal
from services.portfolio_service import PortfolioSummary, TickerGroup
from services.share_service import ShareRow, row_name

# 종목 이름에 이 말이 들어가면 이 라인에서 시작합니다.
# ⚠ 평가가 아니라 **초기 자리잡기**입니다. 사용자가 언제든 끌어다 옮깁니다.
#    긴 것부터 검사해야 "국고채권" 이 "채권" 보다 먼저 걸립니다.
_ROW_BY_KEYWORD: tuple[tuple[str, str], ...] = (
    ("레버리지", "ST"),
    ("인버스", "ST"),
    ("반도체", "AM"),
    ("나스닥", "AM"),
    ("빅테크", "AM"),
    ("성장", "AM"),
    ("커버드콜", "MC"),
    ("커콜", "MC"),
    ("배당", "MC"),
    ("리츠", "MC"),
    # 대표지수는 전방으로. ⚠ 반드시 커버드콜·배당 **뒤에** 둬야 합니다 —
    #    "200타겟위클리커버드콜" 이 "200" 에 먼저 걸리면 엉뚱한 라인으로 갑니다.
    ("S&P500", "AM"),
    ("나스닥100", "AM"),
    ("코스피", "AM"),
    ("코스닥", "AM"),
    ("200", "AM"),
    ("국고채", "DF"),
    ("종합채권", "DF"),
    ("회사채", "DF"),
    ("국채", "DF"),
    ("채권", "DF"),
    ("금현물", "DF"),
    ("머니마켓", "GK"),
    ("CD금리", "GK"),
    ("KOFR", "GK"),
    ("단기채", "GK"),
)


def guess_row(market: str, ticker: str, name: str) -> str:
    """이 종목이 어느 라인에서 시작하면 좋을지. 모르면 중앙(MC)."""
    if str(market).upper() == MARKET_US:
        return pitch_grid.guess_row(ticker)          # 미국은 티커 사전을 씁니다
    text = str(name or "")
    for word, row in _ROW_BY_KEYWORD:
        if word in text:
            return row
    return "MC"


# ---------------------------------------------------------------------
# 슬롯 배치
# ---------------------------------------------------------------------
def ensure_slots(portfolio: Portfolio, groups: list[TickerGroup]) -> bool:
    """자리가 없는 종목에 빈 자리를 하나씩 줍니다. 바뀐 게 있으면 True.

    평가금액이 큰 종목부터 배치합니다. 그래야 제일 큰 종목이 중앙을 차지해서
    화면을 열었을 때 눈이 먼저 갑니다.
    """
    changed = False
    used = {s for s in portfolio.slots.values() if pitch_grid.is_slot(s)}

    for g in groups:                                  # 이미 평가금액 큰 순
        key = ticker_key(g.market, g.ticker)
        current = portfolio.slots.get(key)
        if pitch_grid.is_slot(current) and current in used:
            continue
        row = guess_row(g.market, g.ticker, g.name)
        spot = pitch_grid.first_free_slot(used, preferred_row=row)
        if spot is None:
            break                                     # 26자리가 다 찼습니다
        portfolio.slots[key] = spot
        used.add(spot)
        changed = True
    return changed


# 라인을 축구식 세 덩어리로 묶습니다 (골키퍼는 수비에 넣습니다).
_GROUP_ROWS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("공격", ("ST", "AM")),
    ("미드필드", ("MC", "DM")),
    ("수비", ("DF", "GK")),
)


def tidy(portfolio: Portfolio, groups: list[TickerGroup]) -> int:
    """종목 성격에 맞는 라인으로 **전부 다시** 배치합니다. 옮긴 종목 수를 돌려줍니다.

    `ensure_slots` 와 뭐가 다른가
    -----------------------------
    `ensure_slots` 는 **자리가 없는 종목에만** 자리를 줍니다(화면을 열 때마다
    자동으로 불립니다). `tidy` 는 이미 자리가 있는 종목까지 싹 다시 놓습니다.

    ⚠ **버튼을 눌렀을 때만 부르세요.** 자동으로 부르면 사용자가 손으로 끌어다
      맞춰둔 배치가 말도 없이 흐트러집니다. 그건 화가 나는 일입니다.

    평가금액이 큰 종목부터 놓아서 큰 종목이 중앙을 차지하게 합니다
    (`first_free_slot` 이 중앙부터 채웁니다). 한 라인이 꽉 차면 이웃 라인으로
    밀려나는 것도 거기서 알아서 합니다.
    """
    before = dict(portfolio.slots)
    used: set[str] = set()
    for g in groups:                                  # 이미 평가금액 큰 순
        key = ticker_key(g.market, g.ticker)
        row = guess_row(g.market, g.ticker, g.name)
        spot = pitch_grid.first_free_slot(used, preferred_row=row)
        if spot is None:
            # 26자리가 다 찼습니다. 자리를 비워 둬야 다른 종목과 겹치지 않습니다
            # (판에 못 서는 종목은 build_players 가 no_slot 으로 알려줍니다).
            portfolio.slots.pop(key, None)
            continue
        portfolio.slots[key] = spot
        used.add(spot)
    keys = set(before) | set(portfolio.slots)
    return sum(1 for k in keys if before.get(k) != portfolio.slots.get(k))


def formation_counts(portfolio: Portfolio) -> dict[str, int]:
    """지금 **실제로 놓인 자리** 기준으로 공격/미드필드/수비에 몇 개인가.

    종목 성격이 아니라 놓인 자리를 셉니다 — 사용자가 손으로 옮겼으면 그게
    사용자의 뜻이고, 그대로 세는 게 맞습니다.
    """
    out = {name: 0 for name, _ in _GROUP_ROWS}
    for slot in portfolio.slots.values():
        if not pitch_grid.is_slot(slot):
            continue
        row = pitch_grid.split(slot)[0]
        for name, rows in _GROUP_ROWS:
            if row in rows:
                out[name] += 1
                break
    return out


def formation(portfolio: Portfolio) -> str:
    """축구식 표기. 뒤에서부터 수비-미드필드-공격 (예: "1-2-1").

    0 이 들어가도 그대로 씁니다 — "0-0-4" 는 **전부 공격에 몰려 있다**는 뜻이고,
    그걸 보여주는 게 이 표기의 쓸모입니다. 숨기면 볼 이유가 없어집니다.
    """
    c = formation_counts(portfolio)
    if sum(c.values()) == 0:
        return ""
    return f"{c['수비']}-{c['미드필드']}-{c['공격']}"


def prune_slots(portfolio: Portfolio) -> bool:
    """더 이상 갖고 있지 않은 종목의 자리를 비웁니다. 바뀐 게 있으면 True.

    안 지우면 종목을 팔고 지운 뒤에도 그 자리가 계속 막혀 있어서, 새 종목이
    엉뚱한 자리로 밀려납니다.
    """
    alive = {ticker_key(m, t) for m, t in portfolio.tickers()}
    dead = [k for k in portfolio.slots if k not in alive]
    for k in dead:
        portfolio.slots.pop(k, None)
    return bool(dead)


def apply_assignments(portfolio: Portfolio, assignments: dict) -> bool:
    """전술판에서 끌어다 놓은 결과를 반영합니다. 바뀐 게 있으면 True.

    컴포넌트가 돌려주는 id 는 우리가 넘긴 티커 열쇠입니다. 모르는 자리(슬롯이
    아닌 값)는 그냥 무시합니다 — 바깥에서 온 값을 그대로 믿지 않습니다.
    """
    if not isinstance(assignments, dict):
        return False
    changed = False
    for key, slot_id in assignments.items():
        if not isinstance(key, str) or not pitch_grid.is_slot(slot_id):
            continue
        if portfolio.slots.get(key) != slot_id:
            portfolio.slots[key] = slot_id
            changed = True
    return changed


# ---------------------------------------------------------------------
# 컴포넌트에 넘길 짐 싸기
# ---------------------------------------------------------------------
@dataclass
class PitchPayload:
    players: list[dict]
    captain_key: str | None
    total_value_krw: float
    unpriced: list[str]          # 가격을 못 가져와 비중을 못 매긴 종목
    no_slot: list[str]           # 자리가 모자라 판에 못 세운 종목 (26자리 초과)


def build_players(summary: PortfolioSummary, portfolio: Portfolio,
                  groups: list[TickerGroup]) -> PitchPayload:
    """전술판 카드 목록.

    등번호(`weight_pct`)는 **내 전체 ETF 자산에서 이 종목이 차지하는 비율**입니다.
    가격을 못 가져온 종목은 비율을 만들어내지 않고 `None` 으로 둡니다
    (컴포넌트가 등번호 자리를 비워 둡니다).
    """
    total = summary.total_value_krw
    players: list[dict] = []
    unpriced: list[str] = []
    no_slot: list[str] = []
    captain_key: str | None = None
    best = -1.0

    for g in groups:
        key = ticker_key(g.market, g.ticker)
        value = g.value_krw(summary.usdkrw)
        if value is None:
            unpriced.append(g.name or g.ticker)
            weight = None
        else:
            weight = (value / total * 100.0) if total > 0 else 0.0
            if value > best:
                best, captain_key = value, key

        slot = portfolio.slots.get(key)
        if not pitch_grid.is_slot(slot):
            # 자리가 26개뿐이라 그보다 많이 들고 있으면 못 세웁니다.
            # 조용히 가운데 겹쳐 두면 "왜 카드가 사라졌지" 가 되므로 알려 줍니다.
            no_slot.append(g.name or g.ticker)

        players.append({
            "id": key,
            "ticker": g.ticker,
            "display_name": g.name or g.ticker,
            "market": g.market,
            "label": pitch_kit.card_label(g.market, g.ticker, g.name),
            "kit": pitch_kit.kit_of(g.market, g.name),
            "weight_pct": weight,
            "slot": slot,
            # 가격을 못 가져온 종목은 카드에 경고 표시를 답니다.
            "has_warning": value is None,
            "captain": False,
        })

    for p in players:                                 # 주장 완장 = 제일 큰 종목
        p["captain"] = (p["id"] == captain_key)

    return PitchPayload(players=players, captain_key=captain_key,
                        total_value_krw=total, unpriced=unpriced, no_slot=no_slot)


def share_rows(summary: PortfolioSummary, groups: list[TickerGroup],
               this_month: PeriodTotal) -> list[ShareRow]:
    """📸 캡처 이미지의 명단과 📋 텍스트가 **함께** 쓰는 줄 목록.

    둘을 따로 만들면 같은 포트폴리오를 두 군데에 올렸을 때 숫자가 어긋나 보입니다.
    """
    month_by_ticker: dict[str, float] = {}
    for r in this_month.rows:
        if r.amount_krw is None:
            continue
        k = ticker_key(r.holding.market, r.holding.ticker)
        month_by_ticker[k] = month_by_ticker.get(k, 0.0) + r.amount_krw

    total = summary.total_value_krw
    out: list[ShareRow] = []
    for g in groups:                                  # 이미 평가금액 큰 순
        value = g.value_krw(summary.usdkrw)
        kit = pitch_kit.kit_of(g.market, g.name)
        out.append(ShareRow(
            name=row_name(g.market, g.ticker, g.name),
            weight_pct=((value / total * 100.0) if (value is not None and total > 0) else None),
            value_krw=value,
            month_krw=month_by_ticker.get(ticker_key(g.market, g.ticker)),
            color=kit["dark"],
            is_us=(kit["style"] == "us"),
        ))
    return out

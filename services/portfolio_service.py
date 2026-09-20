"""
services/portfolio_service.py  --  "지금 내 돈이 얼마인가"
==========================================================

화면과 완전히 분리된 순수 계산입니다. 여기서 만드는 숫자가 메인 화면의 맨 위
세 카드입니다.

    내 ETF 자산      = 보유수량 × 현재가 (달러는 최신 환율로 원화 환산)
    내가 넣은 돈      = 보유수량 × 평균 매입가격
    지금까지 벌거나 잃은 돈 = 위 둘의 차이

가격을 못 가져온 종목은 **0 으로 세지 않고 계산에서 빼고, 뺐다고 화면에 알립니다.**
0 으로 세면 자산이 갑자기 줄어든 것처럼 보여서 사용자가 놀랍니다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from data.providers.base import DataUnavailable, PriceQuote
from data.providers.price_provider import get_price_provider
from models.portfolio import Holding, Portfolio
from services import fx_service


@dataclass
class PricedHolding:
    """보유 종목 한 줄 + 지금 가격."""

    holding: Holding
    quote: PriceQuote | None = None
    error: str = ""

    @property
    def price(self) -> float | None:
        return self.quote.price if self.quote else None

    @property
    def value_native(self) -> float | None:
        if self.quote is None:
            return None
        return self.holding.shares * self.quote.price

    def value_krw(self, usdkrw: float | None) -> float | None:
        return fx_service.to_krw(self.value_native, self.holding.currency, usdkrw) \
            if self.value_native is not None else None

    def cost_krw(self, usdkrw: float | None) -> float | None:
        return fx_service.to_krw(self.holding.cost_native, self.holding.currency, usdkrw)

    def profit_krw(self, usdkrw: float | None) -> float | None:
        v, c = self.value_krw(usdkrw), self.cost_krw(usdkrw)
        if v is None or c is None:
            return None
        return v - c


@dataclass
class PortfolioSummary:
    """메인 화면 맨 위에 그대로 올라가는 값들."""

    total_value_krw: float = 0.0        # 내 ETF 자산
    total_cost_krw: float = 0.0         # 내가 넣은 돈
    usdkrw: float | None = None
    priced: list[PricedHolding] = field(default_factory=list)
    missing: list[PricedHolding] = field(default_factory=list)   # 가격을 못 가져온 것
    as_of_dates: list = field(default_factory=list)

    @property
    def total_profit_krw(self) -> float:
        return self.total_value_krw - self.total_cost_krw

    @property
    def profit_rate(self) -> float | None:
        if self.total_cost_krw <= 0:
            return None
        return self.total_profit_krw / self.total_cost_krw * 100.0

    @property
    def has_missing(self) -> bool:
        return bool(self.missing)

    @property
    def data_as_of(self):
        """화면에 적는 '데이터 기준일' — 쓴 종가들 중 가장 이른 날."""
        return min(self.as_of_dates) if self.as_of_dates else None


def fetch_quotes(portfolio: Portfolio) -> dict[tuple[str, str], PriceQuote | str]:
    """종목별 현재가를 한 번씩만 조회합니다.

    같은 ETF 를 세 계좌에 나눠 가지고 있어도 시세 호출은 한 번입니다.
    실패하면 그 자리에 **사용자에게 보여줄 한국어 메시지 문자열**을 넣습니다.
    """
    out: dict[tuple[str, str], PriceQuote | str] = {}
    for market, ticker in portfolio.tickers():
        try:
            out[(market, ticker)] = get_price_provider(market).get_latest_price(ticker)
        except DataUnavailable as e:
            out[(market, ticker)] = str(e)
        except Exception as e:  # noqa: BLE001 - 종목 하나 때문에 화면이 죽으면 안 됩니다
            out[(market, ticker)] = f"[{ticker}] 가격을 확인하지 못했습니다 ({type(e).__name__})."
    return out


# "환율을 안 넘겼다" 와 "환율을 알 수 없다(None)" 는 다른 뜻입니다.
# 둘 다 None 으로 받으면, 환율을 못 가져온 상황을 테스트할 수도 없고 실제로도
# 조용히 실시간 조회를 타버립니다. 그래서 '안 넘김' 전용 표시를 따로 둡니다.
_UNSET = object()


def summarize(portfolio: Portfolio, quotes: dict | None = None,
              usdkrw: float | None | object = _UNSET) -> PortfolioSummary:
    """포트폴리오 전체 요약. 네트워크는 quotes/usdkrw 를 안 넘겼을 때만 탑니다."""
    if quotes is None:
        quotes = fetch_quotes(portfolio)
    if usdkrw is _UNSET:
        q = fx_service.latest()
        usdkrw = q.rate if q else None

    s = PortfolioSummary(usdkrw=usdkrw)
    for h in portfolio.holdings:
        got = quotes.get((h.market, h.ticker))
        if isinstance(got, PriceQuote):
            ph = PricedHolding(holding=h, quote=got)
            s.as_of_dates.append(got.as_of)
        else:
            ph = PricedHolding(holding=h, error=str(got or "가격을 확인하지 못했습니다."))
        s.priced.append(ph)

        v = ph.value_krw(usdkrw)
        c = ph.cost_krw(usdkrw)
        if v is None or c is None:
            # 가격이나 환율이 없으면 **합계에 넣지 않습니다.** 0 으로 세면 자산이
            # 줄어든 것처럼 보입니다. 대신 빠졌다고 화면에 알립니다.
            s.missing.append(ph)
            continue
        s.total_value_krw += v
        s.total_cost_krw += c
    return s


# ---------------------------------------------------------------------
# 묶어 보기
# ---------------------------------------------------------------------
@dataclass
class TickerGroup:
    """같은 ETF 를 여러 증권사/계좌에 가진 것을 하나로 합친 것."""

    market: str
    ticker: str
    name: str
    currency: str
    rows: list[PricedHolding] = field(default_factory=list)

    @property
    def total_shares(self) -> float:
        return sum(r.holding.shares for r in self.rows)

    @property
    def price(self) -> float | None:
        for r in self.rows:
            if r.price is not None:
                return r.price
        return None

    @property
    def avg_price(self) -> float | None:
        """가중평균 매입가격. 수량이 0이면 None."""
        qty = self.total_shares
        if qty <= 0:
            return None
        return sum(r.holding.cost_native for r in self.rows) / qty

    def value_krw(self, usdkrw: float | None) -> float | None:
        vals = [r.value_krw(usdkrw) for r in self.rows]
        good = [v for v in vals if v is not None]
        return sum(good) if len(good) == len(vals) and good else (sum(good) if good else None)

    def cost_krw(self, usdkrw: float | None) -> float | None:
        vals = [r.cost_krw(usdkrw) for r in self.rows]
        good = [v for v in vals if v is not None]
        return sum(good) if good else None


def group_by_ticker(summary: PortfolioSummary) -> list[TickerGroup]:
    """종목별로 합칩니다. 평가금액이 큰 순으로 정렬."""
    groups: dict[tuple[str, str], TickerGroup] = {}
    for ph in summary.priced:
        h = ph.holding
        key = (h.market, h.ticker)
        if key not in groups:
            groups[key] = TickerGroup(market=h.market, ticker=h.ticker,
                                      name=h.name or h.ticker, currency=h.currency)
        if h.name and not groups[key].name.strip():
            groups[key].name = h.name
        groups[key].rows.append(ph)
    out = list(groups.values())
    out.sort(key=lambda g: (g.value_krw(summary.usdkrw) or 0), reverse=True)
    return out


@dataclass
class BrokerGroup:
    """'내 돈은 어디에 있나요' 화면용."""

    broker: str
    value_krw: float = 0.0
    accounts: dict[str, float] = field(default_factory=dict)
    rows: list[PricedHolding] = field(default_factory=list)


def group_by_broker(summary: PortfolioSummary) -> list[BrokerGroup]:
    groups: dict[str, BrokerGroup] = {}
    for ph in summary.priced:
        name = ph.holding.broker or "증권사 미지정"
        g = groups.setdefault(name, BrokerGroup(broker=name))
        g.rows.append(ph)
        v = ph.value_krw(summary.usdkrw)
        if v is not None:
            g.value_krw += v
            acc = ph.holding.account or "계좌 미지정"
            g.accounts[acc] = g.accounts.get(acc, 0.0) + v
    out = list(groups.values())
    out.sort(key=lambda g: g.value_krw, reverse=True)
    return out

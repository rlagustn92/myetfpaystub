"""
models/portfolio.py  --  내가 가진 ETF 를 담는 그릇
==================================================

구조는 프롬프트 §5 그대로입니다.

    증권사
     └─ 계좌
         └─ 보유 종목
             ├─ 수량
             └─ 평균 매입가격

실제 저장은 평평한 목록(`Holding` 의 리스트)으로 합니다. 증권사/계좌는 문자열
필드로 들고, 화면에서 필요할 때 묶습니다. 이렇게 하면 같은 ETF 를 여러 증권사에
가지고 있어도 합치기/쪼개기가 둘 다 쉽습니다.

**최초 매수일과 과거 거래내역은 일부러 안 받습니다.** 이 앱은 투자일지가 아니라
"지금 내가 가진 것" 을 관리하는 도구입니다.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from models.numbers import safe_float, safe_int

MARKET_US = "US"
MARKET_KR = "KR"

CURRENCY_BY_MARKET = {MARKET_US: "USD", MARKET_KR: "KRW"}


def new_id() -> str:
    """보유 종목 한 줄을 구분하는 id. 사용자에게는 안 보입니다."""
    return uuid.uuid4().hex[:12]


@dataclass
class Holding:
    """증권사 + 계좌 + 종목 한 줄. 같은 종목을 다른 계좌에 가지고 있으면 줄이 따로 생깁니다."""

    ticker: str                   # 미국은 "SCHD", 한국은 6자리 "069500" / "0219E0"
    market: str                   # "US" | "KR"
    name: str = ""                # 화면에 보여줄 종목명
    broker: str = ""              # 어디에 가지고 있나요
    account: str = ""             # 어떤 계좌인가요 (사용자가 직접 쓴 이름)
    account_type: str = ""        # 일반 / ISA / 연금저축 / IRP — 세금·현금흐름 분석용
    shares: float = 0.0           # 보유수량
    avg_price: float = 0.0        # 평균 매입가격 (그 종목의 원래 통화 기준)
    memo: str = ""
    id: str = field(default_factory=new_id)

    # -- 파생값 ------------------------------------------------------
    @property
    def currency(self) -> str:
        return CURRENCY_BY_MARKET.get(self.market, "KRW")

    @property
    def cost_native(self) -> float:
        """내가 넣은 돈 (원래 통화 기준)."""
        return self.shares * self.avg_price

    def where(self) -> str:
        """'미래에셋증권 · ISA' 같은 표시용 문자열."""
        parts = [p for p in (self.broker, self.account) if p]
        return " · ".join(parts) if parts else "계좌 미지정"

    # -- 직렬화 ------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "ticker": self.ticker,
            "market": self.market,
            "name": self.name,
            "broker": self.broker,
            "account": self.account,
            "account_type": self.account_type,
            "shares": self.shares,
            "avg_price": self.avg_price,
            "memo": self.memo,
        }

    @staticmethod
    def from_dict(d: dict) -> "Holding | None":
        """저장 파일 한 줄 -> Holding. 못 쓰는 줄이면 None (앱을 죽이지 않습니다).

        저장 파일은 사용자가 손으로 고칠 수도 있고, 예전 버전이 만든 것일 수도 있습니다.
        한 줄이 이상하다고 전체를 못 불러오면 안 됩니다.
        """
        if not isinstance(d, dict):
            return None
        ticker = str(d.get("ticker") or "").strip()
        if not ticker:
            return None
        market = str(d.get("market") or "").strip().upper()
        if market not in (MARKET_US, MARKET_KR):
            # 6자리면 한국, 아니면 미국으로 봅니다. (예전 파일 호환)
            market = MARKET_KR if len(ticker) == 6 else MARKET_US
        if market == MARKET_KR:
            ticker = ticker.zfill(6)     # "5930" -> "005930". 앞의 0 을 살립니다.
        else:
            ticker = ticker.upper()
        return Holding(
            ticker=ticker,
            market=market,
            name=str(d.get("name") or ""),
            broker=str(d.get("broker") or ""),
            account=str(d.get("account") or ""),
            account_type=str(d.get("account_type") or ""),
            shares=safe_float(d.get("shares"), minimum=0.0),
            avg_price=safe_float(d.get("avg_price"), minimum=0.0),
            memo=str(d.get("memo") or ""),
            id=str(d.get("id") or new_id()),
        )


def ticker_key(market: str, ticker: str) -> str:
    """전술판 슬롯을 기억하는 열쇠. 'US:SCHD' / 'KR:069500'.

    슬롯은 **보유 줄이 아니라 종목**에 붙습니다. 같은 ETF 를 세 계좌에 나눠
    갖고 있어도 전술판에는 카드가 하나만 서기 때문입니다.
    """
    return f"{str(market).upper()}:{str(ticker).strip().upper()}"


@dataclass
class Portfolio:
    """저장/불러오기의 단위. 사용자는 이걸 여러 개 만들어 둘 수 있습니다."""

    name: str = "내 포트폴리오"
    holdings: list[Holding] = field(default_factory=list)
    brokers: list[str] = field(default_factory=list)        # 사용자가 추가한 증권사
    account_types: list[str] = field(default_factory=list)  # 사용자가 추가한 계좌 유형
    # 전술판 배치 { "KR:069500": "DF-C", ... }. 사용자가 끌어다 놓은 자리입니다.
    slots: dict[str, str] = field(default_factory=dict)

    # -- 조회 --------------------------------------------------------
    def by_id(self, holding_id: str) -> Holding | None:
        for h in self.holdings:
            if h.id == holding_id:
                return h
        return None

    def tickers(self) -> list[tuple[str, str]]:
        """중복 없는 (market, ticker) 목록. 시세 조회를 종목당 한 번만 하려고 씁니다."""
        seen: list[tuple[str, str]] = []
        for h in self.holdings:
            key = (h.market, h.ticker)
            if key not in seen:
                seen.append(key)
        return seen

    def brokers_in_use(self) -> list[str]:
        out: list[str] = []
        for h in self.holdings:
            if h.broker and h.broker not in out:
                out.append(h.broker)
        return out

    # -- 편집 --------------------------------------------------------
    def add(self, holding: Holding) -> None:
        self.holdings.append(holding)

    def remove(self, holding_id: str) -> bool:
        before = len(self.holdings)
        self.holdings = [h for h in self.holdings if h.id != holding_id]
        return len(self.holdings) != before

    # -- 직렬화 ------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "holdings": [h.to_dict() for h in self.holdings],
            "brokers": list(self.brokers),
            "account_types": list(self.account_types),
            "slots": dict(self.slots),
        }

    @staticmethod
    def from_dict(d: dict) -> "Portfolio":
        if not isinstance(d, dict):
            return Portfolio()
        raw = d.get("holdings")
        holdings: list[Holding] = []
        if isinstance(raw, list):
            for item in raw:
                h = Holding.from_dict(item)
                if h is not None:
                    holdings.append(h)
        raw_slots = d.get("slots")
        slots: dict[str, str] = {}
        if isinstance(raw_slots, dict):
            # 저장 파일을 손으로 고쳤을 수도 있어서 문자열인 것만 받습니다.
            for k, v in raw_slots.items():
                if isinstance(k, str) and isinstance(v, str) and k and v:
                    slots[k] = v

        return Portfolio(
            name=str(d.get("name") or "내 포트폴리오"),
            holdings=holdings,
            brokers=[str(x) for x in (d.get("brokers") or []) if str(x).strip()],
            account_types=[str(x) for x in (d.get("account_types") or []) if str(x).strip()],
            slots=slots,
        )

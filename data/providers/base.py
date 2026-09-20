"""
data/providers/base.py  --  데이터 제공자 공통 인터페이스
========================================================

    UI  ->  Service  ->  provider(인터페이스)  ->  Yahoo / KRX / 운용사

**위층에서 yfinance 나 requests 를 직접 부르지 마세요.** 무료 소스는 언제든 막히고,
없어지고, 유료화됩니다. 인터페이스 뒤에 숨겨두면 그날이 와도 파일 하나만 갈아끼우면
됩니다. 이거 하나가 나중에 며칠을 아껴줍니다.

데이터가 없을 때의 절대 원칙
----------------------------
- 추측값을 만들지 않는다. 0 으로 채우지 않는다 (0 은 "없다", 사실은 "모른다").
- 다른 종목/유사 종목 값을 대신 쓰지 않는다.
- `DataUnavailable` 을 던지고, 상위에서 "데이터 없음" 으로 표시한다.
- 예외 메시지는 **그대로 화면에 띄울 수 있는 한국어 문장**으로 쓴다.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from datetime import date

import pandas as pd


class DataUnavailable(Exception):
    """가격/환율/분배금을 확인할 수 없을 때. 메시지는 사용자에게 보여줄 한국어 문장."""


@dataclass
class PriceQuote:
    ticker: str
    price: float       # 그 종목의 "원래 통화" 기준 1주 가격
    currency: str      # "USD" | "KRW"
    as_of: date        # 이 가격의 데이터 기준일
    source: str        # "yfinance" | "FinanceDataReader" | ...


@dataclass
class FxQuote:
    pair: str          # "USD/KRW"
    rate: float        # 1 USD = rate KRW
    as_of: date
    source: str


# 가격 히스토리 DataFrame 규약
# ---------------------------
# index : DatetimeIndex (tz 제거, 날짜만), 이름 "date"
# 열    : "close"  -- 분할은 소급 반영, 배당은 미반영 (세 소스 모두 같은 성질로 맞춤)
# attrs : df.attrs["currency"], df.attrs["source"]
HISTORY_CLOSE_COL = "close"


class PriceProvider(abc.ABC):
    """시장별(미국/한국) 가격 제공자."""

    name: str = "base"

    @abc.abstractmethod
    def get_latest_price(self, ticker: str) -> PriceQuote:
        """가장 최근 일별 종가. 없으면 DataUnavailable."""

    @abc.abstractmethod
    def get_price_history(self, ticker: str, start: date, end: date) -> pd.DataFrame:
        """[start, end] 구간 일별 가격. 위 규약을 따름. 데이터가 없으면 DataUnavailable."""

"""
data/providers/price_provider.py  --  현재가 / 가격 히스토리 (미국 + 한국)
=========================================================================

    미국: yfinance          Ticker.history(auto_adjust=False)
    한국: FinanceDataReader DataReader()  (한국 종가는 원래 수정주가)

⚠ 조용히 틀리는 함정 셋 — 전부 여기서 막습니다.

1. **yfinance 의 `end` 는 배타적(exclusive)** 입니다. 그날을 포함하려면 하루를
   더해야 합니다. 안 더하면 마지막 하루가 소리 없이 빠집니다.
2. **인덱스가 tz-aware(America/New_York)** 입니다. 한국 데이터와 합치면 인덱스가
   안 맞아 교집합이 비어버립니다. 날짜만 남겨 tz 를 죽입니다.
3. **장중에는 마지막 행 Close 가 NaN** 일 수 있습니다. dropna 필수.
   한국은 거래정지 등으로 종가 0 이 들어오는 행이 있어 `Close > 0` 로 거릅니다.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

import config
from data.providers import cache
from data.providers.base import (
    DataUnavailable,
    HISTORY_CLOSE_COL,
    PriceProvider,
    PriceQuote,
)
from models.portfolio import MARKET_KR, MARKET_US

try:
    import yfinance as yf
except Exception as _e:  # pragma: no cover
    yf = None
    _YF_ERROR = _e
else:
    _YF_ERROR = None

try:
    import FinanceDataReader as fdr
except Exception as _e:  # pragma: no cover
    fdr = None
    _FDR_ERROR = _e
else:
    _FDR_ERROR = None


def _to_daily_index(idx) -> pd.DatetimeIndex:
    """tz 와 시각(HH:MM)을 버리고 날짜만 남긴 인덱스."""
    return pd.DatetimeIndex(
        pd.to_datetime([d.date() if hasattr(d, "date") else d for d in idx]), name="date"
    )


# =====================================================================
# 미국
# =====================================================================
class USPriceProvider(PriceProvider):
    name = "Yahoo Finance"

    def get_price_history(self, ticker: str, start: date, end: date) -> pd.DataFrame:
        if yf is None:
            raise DataUnavailable(f"yfinance 를 불러올 수 없습니다: {_YF_ERROR}")
        key = f"us:hist:{ticker}:{start}:{end}"

        def _load() -> pd.DataFrame:
            raw = yf.Ticker(ticker).history(
                start=start.isoformat(),
                end=(end + timedelta(days=1)).isoformat(),   # end 가 배타적이라 +1일
                auto_adjust=config.YFINANCE_AUTO_ADJUST,
                actions=False,
            )
            if raw is None or raw.empty or "Close" not in raw.columns:
                raise DataUnavailable(f"[{ticker}] 가격 데이터를 가져오지 못했습니다.")
            raw = raw.dropna(subset=["Close"])
            if raw.empty:
                raise DataUnavailable(f"[{ticker}] 유효한 종가가 없습니다.")
            df = pd.DataFrame(index=_to_daily_index(raw.index))
            df[HISTORY_CLOSE_COL] = raw["Close"].to_numpy()
            df.attrs["currency"] = "USD"
            df.attrs["source"] = self.name
            return df

        return cache.get_or_set(key, config.CACHE_TTL_PRICE_SECONDS, _load)

    def get_latest_price(self, ticker: str) -> PriceQuote:
        key = f"us:last:{ticker}"

        def _load() -> PriceQuote:
            today = config.today_local()
            df = self.get_price_history(ticker, today - timedelta(days=12), today)
            last = df.index.max()
            return PriceQuote(ticker=ticker, price=float(df.loc[last, HISTORY_CLOSE_COL]),
                              currency="USD", as_of=last.date(), source=self.name)

        return cache.get_or_set(key, config.CACHE_TTL_LATEST_PRICE_SECONDS, _load)


# =====================================================================
# 한국
# =====================================================================
class KRPriceProvider(PriceProvider):
    name = "FinanceDataReader"

    def get_price_history(self, ticker: str, start: date, end: date) -> pd.DataFrame:
        if fdr is None:
            raise DataUnavailable(f"FinanceDataReader 를 불러올 수 없습니다: {_FDR_ERROR}")
        key = f"kr:hist:{ticker}:{start}:{end}"

        def _load() -> pd.DataFrame:
            raw = fdr.DataReader(str(ticker), start.isoformat(), end.isoformat())
            if raw is None or raw.empty or "Close" not in raw.columns:
                raise DataUnavailable(f"[{ticker}] 가격 데이터를 가져오지 못했습니다.")
            raw = raw.dropna(subset=["Close"])
            raw = raw[raw["Close"] > 0]          # 거래정지 등으로 0 이 들어옵니다
            if raw.empty:
                raise DataUnavailable(f"[{ticker}] 유효한 종가가 없습니다.")
            df = pd.DataFrame(index=_to_daily_index(raw.index))
            df[HISTORY_CLOSE_COL] = raw["Close"].to_numpy()
            df.attrs["currency"] = "KRW"
            df.attrs["source"] = self.name
            return df

        return cache.get_or_set(key, config.CACHE_TTL_PRICE_SECONDS, _load)

    def get_latest_price(self, ticker: str) -> PriceQuote:
        key = f"kr:last:{ticker}"

        def _load() -> PriceQuote:
            today = config.today_local()
            df = self.get_price_history(ticker, today - timedelta(days=16), today)
            last = df.index.max()
            return PriceQuote(ticker=str(ticker), price=float(df.loc[last, HISTORY_CLOSE_COL]),
                              currency="KRW", as_of=last.date(), source=self.name)

        return cache.get_or_set(key, config.CACHE_TTL_LATEST_PRICE_SECONDS, _load)


# =====================================================================
# 교체 지점 — 소스를 바꾸려면 여기만 고칩니다
# =====================================================================
_US = USPriceProvider()
_KR = KRPriceProvider()


def get_price_provider(market: str) -> PriceProvider:
    m = (market or "").upper()
    if m == MARKET_US:
        return _US
    if m == MARKET_KR:
        return _KR
    raise ValueError(f"알 수 없는 시장: {market!r} (US 또는 KR)")

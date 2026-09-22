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

from datetime import date, datetime, time as _time, timedelta

import pandas as pd

import config
from data.providers import cache, callmeter
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


# =====================================================================
# 장이 열려 있는가 — 최신가를 얼마나 오래 우려먹을지 정합니다
# =====================================================================
# 전부 **한국시간(KST)** 기준입니다.
_KR_OPEN, _KR_CLOSE = _time(9, 0), _time(15, 40)
# 미국장은 한국 시간으로 밤에 열려 다음 날 새벽에 닫힙니다. 서머타임에 따라
# 22:30~05:00 또는 23:30~06:00 이라 **양쪽을 다 덮는 넉넉한 창**으로 잡습니다.
# 좁게 잡아 장중을 놓치면 가격이 멈춘 것처럼 보이지만, 넓게 잡으면 호출이
# 조금 더 나갈 뿐입니다 — 틀릴 거면 넓은 쪽으로 틀리는 게 낫습니다.
_US_OPEN, _US_CLOSE = _time(22, 0), _time(6, 30)


def market_is_open(market: str, at: datetime | None = None) -> bool:
    """지금 그 시장이 열려 있는가 (한국시간 기준).

    ⚠ **공휴일은 모릅니다.** 휴장일에 열려 있다고 판단하면 호출이 몇 번 더
      나갈 뿐 값이 틀리지는 않습니다.
    """
    at = at or config.now_local()
    weekday, clock = at.weekday(), at.time()          # 월요일 = 0
    if market == MARKET_US:
        # 월~금 밤에 열려서 다음 날 새벽에 닫힙니다 → 새벽 쪽은 화~토입니다.
        if weekday <= 4 and clock >= _US_OPEN:
            return True
        return 1 <= weekday <= 5 and clock <= _US_CLOSE
    return weekday <= 4 and _KR_OPEN <= clock <= _KR_CLOSE


def latest_price_ttl(market: str, at: datetime | None = None) -> int:
    """최신가를 얼마나 오래 쓸 것인가(초). 장중 15분 / 장 마감 6시간.

    ⭐ **시장마다 따로 봅니다.** 한국과 미국은 열리는 시간이 정반대입니다.

        한국 종목  한국시간 09:00~15:40 에만 15분, 나머지 6시간
        미국 종목  한국시간 22:00~06:30 에만 15분, 나머지 6시간

    그래서 한국 낮에는 한국 종목만, 한국 밤에는 미국 종목만 자주 갱신됩니다.
    닫힌 시장의 종가는 **아무리 기다려도 안 바뀌므로** 다시 받는 게 순수한
    낭비이고, 무료 소스에 막힐 위험만 키웁니다.

    ⚠ 캐시가 **비어 있으면** 이 값과 상관없이 한 번은 받아옵니다. 그래야
      새벽에 들어온 사람에게 자산이 통째로 "데이터 없음" 이 되지 않습니다.
    """
    return (config.CACHE_TTL_LATEST_PRICE_SECONDS if market_is_open(market, at)
            else config.CACHE_TTL_LATEST_PRICE_CLOSED_SECONDS)


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
            # ⚠ **캐시에서 꺼내 쓴 것은 안 셉니다.** 여기는 진짜로 밖에
            #   나가는 자리라서, 이 숫자가 곧 "캐시가 잘 듣고 있나" 입니다.
            callmeter.spend("price")
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

        # ⚠ 유효기간을 **읽을 때마다 다시 정합니다**(`ttl_of`). 저장할 때
        #   고정하면 장 마감 직전에 받은 값이 밤새 30분마다 다시 받아집니다.
        return cache.get_or_set(key, config.CACHE_TTL_LATEST_PRICE_SECONDS, _load,
                                ttl_of=lambda _q: latest_price_ttl(MARKET_US))


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
            callmeter.spend("price")
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

        return cache.get_or_set(key, config.CACHE_TTL_LATEST_PRICE_SECONDS, _load,
                                ttl_of=lambda _q: latest_price_ttl(MARKET_KR))


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

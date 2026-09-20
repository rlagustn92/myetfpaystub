"""
data/providers/fx_provider.py  --  USD/KRW 환율
===============================================

미국 ETF 를 원화로 보여주는 서비스라 환율이 틀리면 나머지가 아무리 정확해도
의미가 없습니다. 원/달러가 1,100원에서 1,360원으로 움직이면 환율만으로 금액이
20% 넘게 달라집니다.

1순위 yfinance `USDKRW=X` → 2순위 FinanceDataReader `USD/KRW`.
둘 다 실패하면 `DataUnavailable` 입니다. **추정하지 않습니다.**
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

import config
from data.providers import cache
from data.providers.base import DataUnavailable, FxQuote

try:
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None

try:
    import FinanceDataReader as fdr
except Exception:  # pragma: no cover
    fdr = None


def _daily_index(idx) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(
        pd.to_datetime([d.date() if hasattr(d, "date") else d for d in idx]), name="date"
    )


def _yf_history(start: date, end: date) -> pd.Series:
    if yf is None:
        raise DataUnavailable("yfinance 를 사용할 수 없습니다.")
    raw = yf.Ticker(config.FX_PAIR_USDKRW).history(
        start=start.isoformat(), end=(end + timedelta(days=1)).isoformat(), auto_adjust=False
    )
    if raw is None or raw.empty or "Close" not in raw.columns:
        raise DataUnavailable("USD/KRW 환율(yfinance)을 가져오지 못했습니다.")
    raw = raw.dropna(subset=["Close"])
    if raw.empty:
        raise DataUnavailable("유효한 USD/KRW 환율(yfinance)이 없습니다.")
    return pd.Series(raw["Close"].to_numpy(), index=_daily_index(raw.index), name="usdkrw")


def _fdr_history(start: date, end: date) -> pd.Series:
    if fdr is None:
        raise DataUnavailable("FinanceDataReader 를 사용할 수 없습니다.")
    raw = fdr.DataReader("USD/KRW", start.isoformat(), end.isoformat())
    if raw is None or raw.empty or "Close" not in raw.columns:
        raise DataUnavailable("USD/KRW 환율(FDR)을 가져오지 못했습니다.")
    raw = raw.dropna(subset=["Close"])
    raw = raw[raw["Close"] > 0]
    if raw.empty:
        raise DataUnavailable("유효한 USD/KRW 환율(FDR)이 없습니다.")
    return pd.Series(raw["Close"].to_numpy(), index=_daily_index(raw.index), name="usdkrw")


def get_history(start: date, end: date) -> pd.Series:
    key = f"fx:usdkrw:{start}:{end}"

    def _load() -> pd.Series:
        errors: list[str] = []
        for loader in (_yf_history, _fdr_history):
            try:
                s = loader(start, end)
                if s is not None and len(s) > 0:
                    return s.sort_index()
            except Exception as e:  # noqa: BLE001 - 다음 소스로 폴백
                errors.append(str(e))
        raise DataUnavailable(
            "USD/KRW 환율을 어떤 소스에서도 가져오지 못했습니다. " + " / ".join(errors)
        )

    return cache.get_or_set(key, config.CACHE_TTL_FX_SECONDS, _load)


def get_latest_rate() -> FxQuote:
    """가장 최근 환율. 현재 평가금액 계산에 씁니다."""
    key = "fx:usdkrw:latest"

    def _load() -> FxQuote:
        today = config.today_local()
        s = get_history(today - timedelta(days=14), today)
        last = s.index.max()
        return FxQuote(pair="USD/KRW", rate=float(s.loc[last]), as_of=last.date(),
                       source="Yahoo Finance")

    return cache.get_or_set(key, config.CACHE_TTL_FX_SECONDS, _load)


def get_rate_on(d: date) -> FxQuote:
    """날짜 d 의 환율. d 가 거래일이 아니면 **d 이전** 가장 가까운 거래일 값을 씁니다.

    뒤(미래)로 가면 그 시점에 알 수 없던 정보를 쓰는 셈이라 반칙입니다.
    과거에 받은 분배금을 원화로 환산할 때 이 함수를 씁니다.
    """
    key = f"fx:usdkrw:on:{d}"

    def _load() -> FxQuote:
        s = get_history(d - timedelta(days=14), d + timedelta(days=1))
        on_or_before = s.loc[s.index <= pd.Timestamp(d)]
        if on_or_before.empty:
            raise DataUnavailable(f"{d} 또는 그 이전의 USD/KRW 환율을 가져올 수 없습니다.")
        last = on_or_before.index.max()
        return FxQuote(pair="USD/KRW", rate=float(on_or_before.loc[last]),
                       as_of=last.date(), source="Yahoo Finance")

    return cache.get_or_set(key, config.CACHE_TTL_FX_SECONDS, _load)

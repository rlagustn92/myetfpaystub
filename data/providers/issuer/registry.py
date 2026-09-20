"""
data/providers/issuer/registry.py  --  종목 -> 어느 운용사 provider 를 쓸지
===========================================================================

**provider 를 갈아끼우려면 이 파일만 고칩니다.** services / UI 는
`get_distributions(market, ticker, name)` 하나만 부릅니다.

고르는 순서
-----------
1. 미국 종목이면 -> 미국 provider (yfinance)
2. 한국 종목이면
   a. 시드 매핑(`data/issuer_index.csv`)에 브랜드가 적혀 있으면 그걸 씁니다
   b. 없으면 종목명 앞부분("KODEX 200" -> KODEX)으로 찾습니다
   c. 둘 다 안 되거나 운용사 조회가 실패하면 -> 일반 폴백(yfinance, 과세표준 없음)

실패하면 조용히 넘어가되, **어디서 온 값인지는 끝까지 들고 갑니다**
(`DistributionSeries.source`). 화면에 출처를 그대로 적기 위해서입니다.
"""

from __future__ import annotations

from data.providers.base import DataUnavailable
from data.providers.issuer import index
from data.providers.issuer.ace_provider import AceProvider
from data.providers.issuer.base import IssuerDistributionProvider, normalize_kr_code
from data.providers.issuer.generic_provider import GenericKrProvider, UsDistributionProvider
from data.providers.issuer.html_table_provider import PlusProvider, TimefolioProvider
from data.providers.issuer.kodex_provider import KodexProvider
from data.providers.issuer.rise_provider import RiseProvider
from data.providers.issuer.sol_provider import SolProvider
from data.providers.issuer.tiger_provider import TigerProvider
from models.distribution import DistributionSeries
from models.portfolio import MARKET_KR, MARKET_US

# 등록 순서가 곧 우선순위입니다. 새 운용사를 지원하면 여기에 한 줄 추가합니다.
KR_ISSUERS: tuple[IssuerDistributionProvider, ...] = (
    KodexProvider(),
    TigerProvider(),
    AceProvider(),
    RiseProvider(),
    SolProvider(),
    PlusProvider(),
    TimefolioProvider(),
)

_BY_BRAND = {p.brand.upper(): p for p in KR_ISSUERS}
_GENERIC_KR = GenericKrProvider()
_US = UsDistributionProvider()


def supported_brands() -> list[str]:
    return [p.brand for p in KR_ISSUERS]


def pick_kr_provider(ticker: str, etf_name: str = "") -> IssuerDistributionProvider | None:
    """그 한국 ETF 를 다룰 운용사 provider. 못 고르면 None."""
    code = normalize_kr_code(ticker)

    brand = index.brand_of(code)              # 1. 시드 매핑이 제일 정확합니다
    if brand and brand.upper() in _BY_BRAND:
        return _BY_BRAND[brand.upper()]

    for p in KR_ISSUERS:                      # 2. 종목명 앞부분으로
        if p.matches(etf_name):
            return p
    return None


def get_distributions(market: str, ticker: str, etf_name: str = "") -> DistributionSeries:
    """분배 이력 전체. 자르는 건 위층(서비스)이 합니다.

    어디서도 못 가져오면 `DataUnavailable` 을 던집니다.
    빈 목록으로 얼버무리지 않습니다 — "지급 이력이 없다" 와 "못 가져왔다" 는 다릅니다.
    """
    m = (market or "").upper()
    if m == MARKET_US:
        return _US.fetch(ticker)
    if m != MARKET_KR:
        raise ValueError(f"알 수 없는 시장: {market!r}")

    provider = pick_kr_provider(ticker, etf_name)
    errors: list[str] = []
    if provider is not None:
        try:
            return provider.fetch(ticker)
        except DataUnavailable as e:
            errors.append(str(e))

    try:
        return _GENERIC_KR.fetch(ticker)      # 3. 마지막 폴백 (과세표준 없음)
    except DataUnavailable as e:
        errors.append(str(e))

    raise DataUnavailable(" / ".join(errors) if errors
                          else f"[{ticker}] 분배금 자료를 확인하지 못했습니다.")

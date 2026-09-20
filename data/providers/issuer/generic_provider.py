"""
일반 폴백 — 운용사를 못 찾았을 때 (yfinance)
=============================================

한국 ETF 중 우리가 조사하지 않은 운용사(KOSEF, HANARO, WON 등)와, 시드 매핑에
없는 종목이 여기로 옵니다.

**분배금은 받아오지만 과세표준은 받을 수 없습니다.**
그래서 `tax_basis_supported = False` 이고, 모든 건의 `tax_basis_per_share` 가
`None` 입니다. 화면에는 "이 종목은 과세표준 자료를 확인할 수 없습니다" 라고 적습니다.
분배금의 몇 %쯤 되겠거니 하고 채워 넣지 **않습니다**.

⚠ 날짜 기준이 다릅니다. yfinance 의 인덱스는 **배당락일**이라 운용사가 말하는
"지급기준일" 과 하루 차이가 날 수 있습니다. 그래서 note 에 그 사실을 적어 둡니다.

⚠ `.KS`(코스피) → `.KQ`(코스닥) 순으로 시도합니다. 6자리이기만 하면 붙입니다 —
`isdigit()` 로 거르면 `0219E0` 같은 영문 섞인 코드를 놓칩니다(실제로 데이터가 있습니다).
"""

from __future__ import annotations

import config
from data.providers import cache
from data.providers.base import DataUnavailable
from data.providers.issuer.base import IssuerDistributionProvider, normalize_kr_code
from models.distribution import Distribution, DistributionSeries

try:
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None

NOTE_EXDATE = "날짜는 배당락일 기준이라 운용사가 안내하는 지급일과 하루 정도 다를 수 있습니다."


def _yf_symbols(ticker: str) -> list[str]:
    t = str(ticker).strip().upper()
    if len(t) == 6:
        return [f"{t}.KS", f"{t}.KQ"]
    return [t]


class GenericKrProvider(IssuerDistributionProvider):
    brand = ""
    issuer_name = "Yahoo Finance"
    home_url = "https://finance.yahoo.com"
    tax_basis_supported = False       # ← 이 소스는 애초에 과세표준을 안 줍니다

    def matches(self, etf_name: str) -> bool:
        return True                   # 마지막 폴백이라 무엇이든 받습니다

    def fetch(self, ticker: str) -> DistributionSeries:
        if yf is None:
            raise DataUnavailable("yfinance 를 사용할 수 없습니다.")
        code = normalize_kr_code(ticker)
        key = f"kr:dist:generic:{code}"

        def _load() -> DistributionSeries:
            for sym in _yf_symbols(code):
                try:
                    s = yf.Ticker(sym).dividends
                except Exception:      # noqa: BLE001 - 다음 심볼로
                    continue
                if s is None or len(s) == 0:
                    continue
                items = [
                    Distribution(
                        ticker=code,
                        payment_date=(ts.date() if hasattr(ts, "date") else ts),
                        record_date=None,
                        distribution_per_share=float(v),
                        tax_basis_per_share=None,      # 모릅니다. 0 이 아닙니다.
                        currency="KRW",
                        source="Yahoo Finance",
                        source_url=f"https://finance.yahoo.com/quote/{sym}",
                        status=config.STATUS_CONFIRMED,
                        note=NOTE_EXDATE,
                    )
                    for ts, v in s.items() if v and float(v) > 0
                ]
                if items:
                    return DistributionSeries(
                        ticker=code, items=items, source="Yahoo Finance",
                        source_url=f"https://finance.yahoo.com/quote/{sym}",
                        tax_basis_supported=False, fetched_at=config.today_local(),
                    )
            raise DataUnavailable(
                f"[{code}] 분배금 자료를 자동으로 확인하지 못했습니다."
            )

        return cache.get_or_set(key, config.CACHE_TTL_DISTRIBUTION_SECONDS, _load)


class UsDistributionProvider(IssuerDistributionProvider):
    """미국 ETF 분배금 (yfinance).

    미국 상장 ETF 에는 한국 ETF 의 "주당 과세표준액" 에 해당하는 개념이 없습니다.
    한국 거주자에게는 지급액 전체가 원천징수 대상이므로, 이 앱에서는
    **세금 계산에 잡히는 금액 = 분배금 전액**으로 봅니다(따로 조회하지 않습니다).
    자세한 근거는 docs/DATA_SOURCES.md §4.
    """

    brand = "US"
    issuer_name = "Yahoo Finance"
    home_url = "https://finance.yahoo.com"
    tax_basis_supported = True

    def matches(self, etf_name: str) -> bool:
        return False                  # 시장으로 고르지 이름으로 고르지 않습니다

    def fetch(self, ticker: str) -> DistributionSeries:
        if yf is None:
            raise DataUnavailable("yfinance 를 사용할 수 없습니다.")
        sym = str(ticker).strip().upper()
        key = f"us:dist:{sym}"

        def _load() -> DistributionSeries:
            try:
                s = yf.Ticker(sym).dividends
            except Exception as e:     # noqa: BLE001
                raise DataUnavailable(f"[{sym}] 분배금 자료를 가져오지 못했습니다.") from e
            if s is None:
                raise DataUnavailable(f"[{sym}] 분배금 자료를 가져오지 못했습니다.")
            items = [
                Distribution(
                    ticker=sym,
                    payment_date=(ts.date() if hasattr(ts, "date") else ts),
                    record_date=None,
                    distribution_per_share=float(v),
                    # 미국 ETF 는 분배금 전액이 과세 대상입니다.
                    tax_basis_per_share=float(v),
                    currency="USD",
                    source="Yahoo Finance",
                    source_url=f"https://finance.yahoo.com/quote/{sym}",
                    status=config.STATUS_CONFIRMED,
                    note=NOTE_EXDATE,
                )
                for ts, v in s.items() if v and float(v) > 0
            ]
            # 분배 이력이 없는 종목(성장형 ETF 등)은 정상입니다. 빈 목록으로 둡니다.
            return DistributionSeries(
                ticker=sym, items=items, source="Yahoo Finance",
                source_url=f"https://finance.yahoo.com/quote/{sym}",
                tax_basis_supported=True, fetched_at=config.today_local(),
            )

        return cache.get_or_set(key, config.CACHE_TTL_DISTRIBUTION_SECONDS, _load)

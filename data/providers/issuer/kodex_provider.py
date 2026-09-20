"""
KODEX (삼성자산운용) 분배금/과세표준
====================================

    GET https://www.samsungfund.com/api/v1/kodex/distribution.do
        ?pageNo=1&ordrColm=BASIC_D&period=0&ordrSort=DESC&srchVal={종목코드}

**6자리 종목코드를 그대로 넣으면 됩니다.** 별도 매핑이 필요 없어서 제일 편합니다.
`period=0` 이 전체 기간이고, 한 페이지에 12건씩 옵니다.

응답 `dividList[]` 에서 쓰는 필드 (2026-09-20 실측):
    stkTicker  종목코드 ("0219E0" 처럼 영문 섞인 것도 있음)
    basicD     지급기준일 YYYYMMDD
    payD       실지급일   YYYYMMDD
    dividA     주당 분배금
    taxDividA  **주당 과세표준액** (아직 발표 전이면 null)

⚠ 검색어가 섞여 들어올 수 있으므로 `stkTicker` 완전일치로 한 번 더 거릅니다.
안 그러면 비슷한 이름의 다른 종목이 같이 잡힙니다.
"""

from __future__ import annotations

import config
from data.providers import cache
from data.providers.base import DataUnavailable
from data.providers.issuer.base import (
    IssuerDistributionProvider,
    http_get,
    json_of,
    normalize_kr_code,
    parse_amount,
    parse_date,
)
from models.distribution import Distribution, DistributionSeries

API = "https://www.samsungfund.com/api/v1/kodex/distribution.do"
REFERER = "https://www.samsungfund.com/etf/product/distribution.do"
PAGE_SIZE = 12          # 서버가 정한 값. 우리가 바꿀 수 없습니다.
MAX_PAGES = 20          # 무한 페이징 방지 (240건 = 20년치 월배당)


class KodexProvider(IssuerDistributionProvider):
    brand = "KODEX"
    issuer_name = "삼성자산운용"
    home_url = "https://www.kodex.com"
    tax_basis_supported = True

    def fetch(self, ticker: str) -> DistributionSeries:
        code = normalize_kr_code(ticker)
        key = f"kr:dist:kodex:{code}"

        def _load() -> DistributionSeries:
            rows: list[dict] = []
            page = 1
            total = None
            while page <= MAX_PAGES:
                data = json_of(http_get(API, referer=REFERER, params={
                    "pageNo": page, "ordrColm": "BASIC_D", "period": 0,
                    "ordrSort": "DESC", "srchVal": code,
                }))
                chunk = data.get("dividList") or []
                total = data.get("totalCnt") if total is None else total
                rows.extend(chunk)
                if not chunk or page * PAGE_SIZE >= int(total or 0):
                    break
                page += 1

            items: list[Distribution] = []
            for r in rows:
                # 검색 결과에 다른 종목이 섞여 올 수 있습니다.
                if str(r.get("stkTicker") or "").strip().upper() != code:
                    continue
                pay = parse_date(r.get("payD")) or parse_date(r.get("basicD"))
                amount = parse_amount(r.get("dividA"))
                if pay is None or amount is None:
                    continue
                items.append(Distribution(
                    ticker=code,
                    payment_date=pay,
                    record_date=parse_date(r.get("basicD")),
                    distribution_per_share=amount,
                    # taxDividA 가 null 이면 None 그대로 둡니다 (0 으로 바꾸지 않습니다).
                    tax_basis_per_share=parse_amount(r.get("taxDividA")),
                    currency="KRW",
                    source=self.brand,
                    source_url=REFERER,
                    status=config.STATUS_CONFIRMED,
                ))

            if not items:
                raise DataUnavailable(
                    f"[{code}] KODEX 분배금 자료에서 이 종목을 찾지 못했습니다."
                )
            return DistributionSeries(
                ticker=code, items=items, source=self.brand, source_url=REFERER,
                tax_basis_supported=True, fetched_at=config.today_local(),
            )

        return cache.get_or_set(key, config.CACHE_TTL_DISTRIBUTION_SECONDS, _load)

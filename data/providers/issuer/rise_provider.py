"""
RISE (KB자산운용) 분배금/과세표준
=================================

    GET https://kbam.co.kr/api/products/etfs/{fund_cd}/dividend

**한 번 호출로 전체 이력이 옵니다.** `history[]` 안에 (2026-09-20 실측):

    base_date            지급기준일 YYYY-MM-DD
    payment_date         실지급일
    amount               주당 분배금
    tax_standard_amount  **주당 과세표준액**
    dividend_ratio       분배율(%)

`fund_cd` 는 4자리 내부 코드(`4435`)라 매핑이 필요합니다 (index.py 참고).
"""

from __future__ import annotations

import config
from data.providers import cache
from data.providers.base import DataUnavailable
from data.providers.issuer import index
from data.providers.issuer.base import (
    IssuerDistributionProvider,
    http_get,
    json_of,
    normalize_kr_code,
    parse_amount,
    parse_date,
)
from models.distribution import Distribution, DistributionSeries

API = "https://kbam.co.kr/api/products/etfs/{fund_cd}/dividend"
REFERER = "https://www.riseetf.co.kr/"


class RiseProvider(IssuerDistributionProvider):
    brand = "RISE"
    issuer_name = "KB자산운용"
    home_url = "https://www.riseetf.co.kr"
    tax_basis_supported = True

    def fetch(self, ticker: str) -> DistributionSeries:
        code = normalize_kr_code(ticker)
        fund_cd = index.fund_id_of(code, self.brand)
        if not fund_cd:
            raise DataUnavailable(
                f"[{code}] RISE 펀드코드를 찾지 못했습니다. "
                f"(tools/build_issuer_index.py 로 매핑을 갱신하세요)"
            )
        key = f"kr:dist:rise:{code}"

        def _load() -> DistributionSeries:
            data = json_of(http_get(API.format(fund_cd=fund_cd), referer=REFERER))
            items: list[Distribution] = []
            for r in data.get("history") or []:
                pay = parse_date(r.get("payment_date")) or parse_date(r.get("base_date"))
                amount = parse_amount(r.get("amount"))
                if pay is None or amount is None:
                    continue
                items.append(Distribution(
                    ticker=code,
                    payment_date=pay,
                    record_date=parse_date(r.get("base_date")),
                    distribution_per_share=amount,
                    tax_basis_per_share=parse_amount(r.get("tax_standard_amount")),
                    currency="KRW",
                    source=self.brand,
                    source_url=f"{self.home_url}/product/{fund_cd}",
                    status=config.STATUS_CONFIRMED,
                ))
            if not items:
                raise DataUnavailable(f"[{code}] RISE 분배 이력을 찾지 못했습니다.")
            return DistributionSeries(
                ticker=code, items=items, source=self.brand,
                source_url=f"{self.home_url}/product/{fund_cd}",
                tax_basis_supported=True, fetched_at=config.today_local(),
            )

        return cache.get_or_set(key, config.CACHE_TTL_DISTRIBUTION_SECONDS, _load)

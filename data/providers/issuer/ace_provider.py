"""
ACE (한국투자신탁운용) 분배금/과세표준
======================================

    GET https://papi.aceetf.co.kr/api/funds/{fundCd}/dividend?page=1

검증한 운용사 중 가장 깔끔한 JSON 입니다. 필드 (2026-09-20 실측):

    std_DT        지급기준일 YYYYMMDD
    dividend_DT   실지급일   YYYYMMDD
    dividend_PRI  주당 분배금
    tax_PRI       **주당 과세표준액**
    dividend_RATE 분배율(%)

ACE 는 6자리 종목코드가 아니라 펀드코드(`K55101DU0363`)로 조회합니다.
매핑은 시드 CSV(`data/issuer_index.csv`)에서 읽습니다 — index.py 설명 참고.
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

API = "https://papi.aceetf.co.kr/api/funds/{fund_cd}/dividend"
REFERER = "https://www.aceetf.co.kr/"
MAX_PAGES = 12


class AceProvider(IssuerDistributionProvider):
    brand = "ACE"
    issuer_name = "한국투자신탁운용"
    home_url = "https://www.aceetf.co.kr"
    tax_basis_supported = True

    def fetch(self, ticker: str) -> DistributionSeries:
        code = normalize_kr_code(ticker)
        fund_cd = index.fund_id_of(code, self.brand)
        if not fund_cd:
            raise DataUnavailable(
                f"[{code}] ACE 펀드코드를 찾지 못했습니다. "
                f"(tools/build_issuer_index.py 로 매핑을 갱신하세요)"
            )
        key = f"kr:dist:ace:{code}"

        def _load() -> DistributionSeries:
            items: list[Distribution] = []
            page = 1
            while page <= MAX_PAGES:
                data = json_of(http_get(API.format(fund_cd=fund_cd), referer=REFERER,
                                        params={"page": page}))
                rows = data.get("dividendList") or []
                for r in rows:
                    pay = parse_date(r.get("dividend_DT")) or parse_date(r.get("std_DT"))
                    amount = parse_amount(r.get("dividend_PRI"))
                    if pay is None or amount is None:
                        continue
                    items.append(Distribution(
                        ticker=code,
                        payment_date=pay,
                        record_date=parse_date(r.get("std_DT")),
                        distribution_per_share=amount,
                        tax_basis_per_share=parse_amount(r.get("tax_PRI")),
                        currency="KRW",
                        source=self.brand,
                        source_url=f"{self.home_url}/fund/{fund_cd}",
                        status=config.STATUS_CONFIRMED,
                    ))
                info = data.get("page") or {}
                if page >= int(info.get("totalPages") or 1) or not rows:
                    break
                page += 1

            if not items:
                raise DataUnavailable(f"[{code}] ACE 분배 이력을 찾지 못했습니다.")
            return DistributionSeries(
                ticker=code, items=items, source=self.brand,
                source_url=f"{self.home_url}/fund/{fund_cd}",
                tax_basis_supported=True, fetched_at=config.today_local(),
            )

        return cache.get_or_set(key, config.CACHE_TTL_DISTRIBUTION_SECONDS, _load)

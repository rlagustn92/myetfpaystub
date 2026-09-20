"""
SOL (신한자산운용) 분배금/과세표준  — ⚠ 필드 이름에 속지 말 것
================================================================

    GET https://www.soletf.com/api/etf/pds/dividend/{fundId}

`items[]` 의 필드 이름과 실제 뜻이 어긋납니다. 사이트 화면 표와 32건 전부를
대조해서 확인했습니다 (2026-09-20).

    WORK_DT         지급기준일
    DIVIDEND_DT     실지급일
    DIVIDEND_PRI    주당 분배금
    **WEEK_PRI**    **주당 과세표준액**  ← 이름은 "주간"처럼 보이지만 과세표준입니다
    TAX_PRI         과세기준가격 (9,102.27 같은 큰 수). **과세표준이 아닙니다**
    BFAS_STAS_STPR  전일 과세기준가격

⚠ `TAX_PRI` 를 과세표준으로 쓰면 주당 9,102원짜리 과세표준이 되어 숫자가 45배쯤
틀립니다. **에러는 안 납니다.** 그래서 더 위험합니다.

검증 예 (SOL 미국30년국채커버드콜(합성), 화면 표와 일치):
    2026-08-31  분배금 60원  WEEK_PRI 0   -> 화면 0
    2026-06-30  분배금 85원  WEEK_PRI 85  -> 화면 85
    2026-01-30  분배금 75원  WEEK_PRI 11  -> 화면 11
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

API = "https://www.soletf.com/api/etf/pds/dividend/{fund_id}"
REFERER = "https://www.soletf.com/ko/fund"


class SolProvider(IssuerDistributionProvider):
    brand = "SOL"
    issuer_name = "신한자산운용"
    home_url = "https://www.soletf.com"
    tax_basis_supported = True

    def fetch(self, ticker: str) -> DistributionSeries:
        code = normalize_kr_code(ticker)
        fund_id = index.fund_id_of(code, self.brand)
        if not fund_id:
            raise DataUnavailable(
                f"[{code}] SOL 내부 상품번호를 찾지 못했습니다. "
                f"(tools/build_issuer_index.py 로 매핑을 갱신하세요)"
            )
        key = f"kr:dist:sol:{code}"
        page = f"{self.home_url}/ko/fund/etf/{fund_id}"

        def _load() -> DistributionSeries:
            data = json_of(http_get(API.format(fund_id=fund_id), referer=page))
            items: list[Distribution] = []
            for r in data.get("items") or []:
                pay = parse_date(r.get("DIVIDEND_DT")) or parse_date(r.get("WORK_DT"))
                amount = parse_amount(r.get("DIVIDEND_PRI"))
                if pay is None or amount is None:
                    continue
                items.append(Distribution(
                    ticker=code,
                    payment_date=pay,
                    record_date=parse_date(r.get("WORK_DT")),
                    distribution_per_share=amount,
                    # ⚠ TAX_PRI 가 아니라 WEEK_PRI 입니다. 위 설명을 반드시 읽으세요.
                    tax_basis_per_share=parse_amount(r.get("WEEK_PRI")),
                    currency="KRW",
                    source=self.brand,
                    source_url=page,
                    status=config.STATUS_CONFIRMED,
                ))
            if not items:
                raise DataUnavailable(f"[{code}] SOL 분배 이력을 찾지 못했습니다.")
            return DistributionSeries(
                ticker=code, items=items, source=self.brand, source_url=page,
                tax_basis_supported=True, fetched_at=config.today_local(),
            )

        return cache.get_or_set(key, config.CACHE_TTL_DISTRIBUTION_SECONDS, _load)

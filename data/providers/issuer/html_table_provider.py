"""
PLUS (한화) · TIME (타임폴리오) 분배금/과세표준 — 서버가 만든 HTML 표를 읽습니다
=================================================================================

두 운용사는 API 가 따로 없고, 상품 상세 페이지가 완성된 HTML 로 옵니다.
표 구조가 거의 같아서 한 클래스로 처리하고, 주소 규칙만 다르게 둡니다.

    PLUS  https://www.plusetf.co.kr/product/detail?n={상품번호}
          표: 지급 기준일 / 실 지급일 / 분배금(원) / 주당과세표준액(원)

    TIME  https://timeetf.co.kr/m11_view.php?idx={번호}
          표: 지급기준일 / 실지급일 / 분배금액(원) / 주당과세표준액(원)

⚠ PLUS 상세 페이지는 250KB 쯤 됩니다. 반드시 캐시하고, 목록 크롤링은
`tools/build_issuer_index.py` 배치로만 합니다.

표를 찾는 방법: 페이지의 모든 `<table>` 중에서 헤더에 **"과세표준"** 이 들어간
것을 고릅니다. 표의 순서나 클래스 이름에 기대지 않습니다 — 그쪽이 바뀌면 조용히
엉뚱한 표를 읽게 되기 때문입니다.
"""

from __future__ import annotations

import html as _html
import re

import config
from data.providers import cache
from data.providers.base import DataUnavailable
from data.providers.issuer import index
from data.providers.issuer.base import (
    IssuerDistributionProvider,
    http_get,
    normalize_kr_code,
    parse_amount,
    parse_date,
)
from models.distribution import Distribution, DistributionSeries

_TABLE_RE = re.compile(r"<table[^>]*>(.*?)</table>", re.S | re.I)
_ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
_CELL_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S | re.I)


def _cell_text(fragment: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def _find_distribution_table(page_html: str) -> list[list[str]] | None:
    """헤더에 '과세표준' 이 있는 표를 찾아 셀 텍스트 2차원 배열로 돌려줍니다."""
    for table in _TABLE_RE.findall(page_html):
        rows = [[_cell_text(c) for c in _CELL_RE.findall(tr)] for tr in _ROW_RE.findall(table)]
        rows = [r for r in rows if r]
        if not rows:
            continue
        header = " ".join(rows[0])
        if "과세표준" in header:
            return rows
    return None


class HtmlTableIssuerProvider(IssuerDistributionProvider):
    """상세 페이지 HTML 표에서 분배 이력을 읽는 provider."""

    url_template: str = ""      # "{fund_id}" 를 포함해야 합니다
    cache_prefix: str = ""

    def fetch(self, ticker: str) -> DistributionSeries:
        code = normalize_kr_code(ticker)
        fund_id = index.fund_id_of(code, self.brand)
        if not fund_id:
            raise DataUnavailable(
                f"[{code}] {self.brand} 내부 상품번호를 찾지 못했습니다. "
                f"(tools/build_issuer_index.py 로 매핑을 갱신하세요)"
            )
        url = self.url_template.format(fund_id=fund_id)
        key = f"kr:dist:{self.cache_prefix}:{code}"

        def _load() -> DistributionSeries:
            page = http_get(url, referer=self.home_url).text
            rows = _find_distribution_table(page)
            if rows is None:
                raise DataUnavailable(
                    f"[{code}] {self.brand} 상세 페이지에서 분배금 표를 찾지 못했습니다."
                )
            items: list[Distribution] = []
            for r in rows[1:]:
                if len(r) < 4:
                    continue
                record = parse_date(r[0])
                pay = parse_date(r[1]) or record
                amount = parse_amount(r[2])
                if pay is None or amount is None:
                    continue
                items.append(Distribution(
                    ticker=code,
                    payment_date=pay,
                    record_date=record,
                    distribution_per_share=amount,
                    tax_basis_per_share=parse_amount(r[3]),
                    currency="KRW",
                    source=self.brand,
                    source_url=url,
                    status=config.STATUS_CONFIRMED,
                ))
            if not items:
                # 표는 있는데 줄이 없으면 "아직 지급 이력이 없는 종목" 입니다.
                # 이건 못 가져온 것과 다르므로 빈 목록을 정상으로 돌려줍니다.
                return DistributionSeries(
                    ticker=code, items=[], source=self.brand, source_url=url,
                    tax_basis_supported=True, fetched_at=config.today_local(),
                )
            return DistributionSeries(
                ticker=code, items=items, source=self.brand, source_url=url,
                tax_basis_supported=True, fetched_at=config.today_local(),
            )

        return cache.get_or_set(key, config.CACHE_TTL_DISTRIBUTION_SECONDS, _load)


class PlusProvider(HtmlTableIssuerProvider):
    brand = "PLUS"
    issuer_name = "한화자산운용"
    home_url = "https://www.plusetf.co.kr"
    url_template = "https://www.plusetf.co.kr/product/detail?n={fund_id}"
    cache_prefix = "plus"
    tax_basis_supported = True


class TimefolioProvider(HtmlTableIssuerProvider):
    brand = "TIME"
    issuer_name = "타임폴리오자산운용"
    home_url = "https://timeetf.co.kr"
    url_template = "https://timeetf.co.kr/m11_view.php?idx={fund_id}"
    cache_prefix = "time"
    tax_basis_supported = True

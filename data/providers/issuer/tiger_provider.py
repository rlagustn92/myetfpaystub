"""
TIGER (미래에셋자산운용) 분배금/과세표준
========================================

    POST https://investments.miraeasset.com/tigeretf/ko/distribution/overall/list.ajax
    form: pageIndex listCnt orderType orderB selectYear selectMonth q

응답은 `<tr>` HTML 조각이고, 열 순서가 곧 스키마입니다.

    종목명 / 유형 / 지급기준일 / 실지급일 / 주당분배금 / **주당과세표준액** / 분배율

⚠ 두 가지가 중요합니다.

1. **`selectMonth` 를 비우면 그 해의 합계만 오고 날짜가 빕니다.**
   개별 지급 건을 받으려면 반드시 월을 지정해야 합니다.
2. 그래서 이 provider 는 **종목 단위가 아니라 (연, 월) 단위로 받아서 캐시**합니다.
   한 번 호출하면 그 달의 TIGER 전 종목이 다 옵니다. 종목마다 12번 부르는 것보다
   훨씬 가볍고, 종목이 늘어도 호출이 안 늘어납니다.

종목코드는 행 안의 `getEtfDtlPop('KR7360750004', ...)` 에서 꺼냅니다 (ISIN 3~8자리).
"""

from __future__ import annotations

import html as _html
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import config
from data.providers import cache
from data.providers.base import DataUnavailable
from data.providers.issuer.base import (
    IssuerDistributionProvider,
    code_from_isin,
    http_post,
    normalize_kr_code,
    parse_amount,
    parse_date,
)
from data.providers.issuer import tiger_seed
from models.distribution import Distribution, DistributionSeries

API = "https://investments.miraeasset.com/tigeretf/ko/distribution/overall/list.ajax"
REFERER = "https://investments.miraeasset.com/tigeretf/ko/distribution/overall/list.do"

# 화면에서 실제로 필요한 범위만 받습니다.
# TIGER 는 달마다 한 번씩 불러야 해서, 이 숫자가 곧 **첫 조회 때의 요청 수**입니다.
# 14개월이면 "올해 누적"과 "최근 1년 지급내역"을 다 그릴 수 있고, 캐시가 프로세스
# 전역이라 두 번째 종목부터는 요청이 0 입니다. 과거를 무한정 긁지 않습니다.
MONTHS_BACK = 14

_ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
_ISIN_RE = re.compile(r"getEtfDtlPop\('([A-Z0-9]+)'", re.I)
_TD_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
_TITLE_RE = re.compile(r'class="title">(.*?)</p>', re.S)


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def _months_back(n: int) -> list[tuple[int, int]]:
    """오늘부터 거슬러 n개월치 (연, 월) 목록."""
    today = config.today_local()
    y, m = today.year, today.month
    out: list[tuple[int, int]] = []
    for _ in range(n):
        out.append((y, m))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return out


PAGE_SIZE = 20     # ⚠ 서버가 정한 값입니다 (§ _fetch_month 설명)
MAX_PAGES = 30

_TOTCNT_RE = re.compile(r'data-tot-cnt="(\d+)"')


def _month_is_finished(year: int, month: int) -> bool:
    """그 달이 이미 지났는가. 이번 달은 아직 지급 건이 더 붙을 수 있습니다."""
    today = config.today_local()
    return (year, month) < (today.year, today.month)


def _month_ttl(year: int, month: int, rows: dict[str, dict]) -> int:
    """이 달 자료를 얼마나 오래 그대로 쓸 것인가.

    **끝난 달은 30일, 아직 채워지는 중이면 24시간.**

    "끝났다" = 그 달이 지났고 + 받아온 자료에 과세표준 빈 칸이 없음.
    과세표준은 운용사가 나중에 채우는 일이 있어서(실측: 2026-05·06 이 몇 달째
    빈 칸), 빈 칸이 남아 있는 달은 계속 다시 확인합니다. 숫자를 지어내지 않는
    대신, 채워지면 바로 보이게 하는 쪽을 택했습니다.
    """
    if not _month_is_finished(year, month):
        return config.CACHE_TTL_DISTRIBUTION_SECONDS
    if not rows:
        # 빈 달(그 달에 지급이 없었음)도 지나갔으면 안 바뀝니다.
        return config.CACHE_TTL_DISTRIBUTION_FINAL_SECONDS
    if any(not str(r.get("tax_basis") or "").strip() for r in rows.values()):
        return config.CACHE_TTL_DISTRIBUTION_SECONDS
    return config.CACHE_TTL_DISTRIBUTION_FINAL_SECONDS


def _month_is_settled(year: int, month: int, rows: dict[str, dict]) -> bool:
    """이 달 자료가 **더 이상 안 바뀌는가.**

    파일에서 읽을지 정하는 규칙과, 캐시를 오래 둘지 정하는 규칙은 **같아야**
    합니다. 따로 두면 한쪽만 고쳤을 때 조용히 어긋나서, 아직 채워지는 중인
    달을 영영 안 받아오게 됩니다. 그래서 `_month_ttl` 하나로 판단합니다.
    """
    return _month_ttl(year, month, rows) == config.CACHE_TTL_DISTRIBUTION_FINAL_SECONDS


def _fetch_month_live(year: int, month: int) -> dict[str, dict]:
    """그 달에 지급된 TIGER 전 종목을 **실제로 받아옵니다**. {종목코드: {...}}.

    ⚠ **`listCnt` 를 크게 보내도 서버는 한 번에 20건만 줍니다.** 화면의 "더보기" 가
    `pageIndex` 를 올려 가며 부르는 구조라서요. 이걸 모르고 listCnt=500 으로 한 번만
    부르면 그 달 상위 20종목만 들어오고, **나머지 종목은 조용히 "분배 이력 없음" 이
    됩니다.** 에러가 안 나서 더 위험합니다(실제로 TIGER 미국S&P500 이 빠졌습니다).
    전체 건수는 첫 행의 `data-tot-cnt` 에 들어 있으니 그걸 보고 페이징합니다.
    """
    out: dict[str, dict] = {}
    total: int | None = None
    page = 1
    while page <= MAX_PAGES:
        r = http_post(API, referer=REFERER, data={
            "pageIndex": page, "listCnt": PAGE_SIZE, "orderC": "", "orderType": "B",
            "selectYear": str(year), "selectMonth": str(month),
            "orderB": "ratioDESC", "q": "",
        })
        rows = _ROW_RE.findall(r.text)
        if total is None:
            m = _TOTCNT_RE.search(r.text)
            total = int(m.group(1)) if m else 0
        seen_in_page = 0
        for tr in rows:
            isin = _ISIN_RE.search(tr)
            code = code_from_isin(isin.group(1)) if isin else None
            if not code:
                continue
            cells = [_text(td) for td in _TD_RE.findall(tr)]
            # cells[0] 은 종목명 칸(링크 전체)이라 제목만 따로 꺼냅니다.
            if len(cells) < 7:
                continue
            seen_in_page += 1
            title = _TITLE_RE.search(tr)
            out[code] = {
                "name": _html.unescape(title.group(1)).strip() if title else "",
                "record_date": cells[2],
                "payment_date": cells[3],
                "amount": cells[4],
                "tax_basis": cells[5],
            }
        if seen_in_page == 0 or len(out) >= (total or 0):
            break
        page += 1
    return out


def _fetch_month(year: int, month: int) -> dict[str, dict]:
    """그 달 표. **저장소 파일에 있고 끝난 달이면 네트워크를 안 탑니다.**

    캐시는 서버 메모리라 재시작하면 날아갑니다(무료 호스팅은 접속이 없으면
    앱을 재웁니다). 그래서 깨어날 때마다 43번을 다시 쓰게 되는데, 지나간 달은
    어차피 안 바뀌므로 `data/tiger_months.csv` 에서 읽습니다.
    """
    key = f"kr:dist:tiger:{year}-{month:02d}"

    def _load() -> dict[str, dict]:
        seeded = tiger_seed.month_rows(year, month)
        # ⚠ None(파일에 없음)과 {}(그 달엔 지급이 없었음)은 다른 뜻입니다.
        if seeded is not None and _month_is_settled(year, month, seeded):
            return seeded                      # HTTP 0회
        return _fetch_month_live(year, month)

    # ⚠ 끝난 달은 30일, 아직 채워지는 중이면 24시간. 값을 보고 정합니다.
    return cache.get_or_set(key, config.CACHE_TTL_DISTRIBUTION_SECONDS, _load,
                            ttl_of=lambda rows: _month_ttl(year, month, rows))


class TigerProvider(IssuerDistributionProvider):
    brand = "TIGER"
    issuer_name = "미래에셋자산운용"
    home_url = "https://www.tigeretf.com"
    tax_basis_supported = True

    def fetch(self, ticker: str) -> DistributionSeries:
        code = normalize_kr_code(ticker)
        items: list[Distribution] = []

        # 달마다 따로 불러야 해서 순서대로 하면 처음 한 번이 30초를 넘깁니다(실측 35초).
        # 스레드 4개로 나눠 받아 10초 아래로 줄입니다. 4개로 제한하는 이유는 남의
        # 서버에 한꺼번에 몰아치지 않기 위해서입니다 — 빨라지자고 무례해질 이유는 없습니다.
        # 한 번 받아두면 12시간 동안 프로세스 전역 캐시에 남아, 두 번째 종목부터는
        # 네트워크 호출이 0 입니다.
        months = _months_back(MONTHS_BACK)
        tables: dict[tuple[int, int], dict] = {}
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {pool.submit(_fetch_month, y, m): (y, m) for y, m in months}
            for fut in as_completed(futures):
                try:
                    tables[futures[fut]] = fut.result()
                except DataUnavailable:
                    # 한 달이 실패했다고 전체를 포기하지 않습니다.
                    tables[futures[fut]] = {}

        for ym in months:
            row = tables.get(ym, {}).get(code)
            if not row:
                continue
            pay = parse_date(row["payment_date"]) or parse_date(row["record_date"])
            amount = parse_amount(row["amount"])
            if pay is None or amount is None:
                continue
            items.append(Distribution(
                ticker=code,
                payment_date=pay,
                record_date=parse_date(row["record_date"]),
                distribution_per_share=amount,
                tax_basis_per_share=parse_amount(row["tax_basis"]),
                currency="KRW",
                source=self.brand,
                source_url=REFERER,
                status=config.STATUS_CONFIRMED,
            ))

        if not items:
            raise DataUnavailable(
                f"[{code}] 최근 {MONTHS_BACK}개월 TIGER 분배 내역에서 이 종목을 찾지 못했습니다."
            )
        return DistributionSeries(
            ticker=code, items=items, source=self.brand, source_url=REFERER,
            tax_basis_supported=True, fetched_at=config.today_local(),
        )

"""
data/providers/issuer/tiger_seed.py  --  TIGER 월별 분배 표를 저장소에 굳혀 둔 것
=================================================================================

왜 이게 있나
------------
TIGER 는 **달마다 따로** 불러야 개별 지급 건을 줍니다(`selectMonth` 를 비우면
그 해 합계만 오고 날짜가 빕니다). 그래서 종목 하나를 보려고 14개월 × 페이지를
훑어 **HTTP 43번**이 나갔습니다 — 정작 받는 자료는 4건인데요.

캐시는 서버 **메모리**에만 있습니다. Streamlit Community Cloud 는 접속이 없으면
앱을 재우고, 깨어날 때는 빈 컨테이너로 시작합니다. 그러면 **깨어날 때마다 43번**
입니다. 메모리 캐시로는 이걸 못 막습니다.

그래서 **지나간 달은 파일로 굳혀 저장소에 넣습니다.** 배포될 때 코드와 같이
서버로 복사되므로 서버가 몇 번 재시작해도 그대로 있습니다.
`data/issuer_index.csv` 와 똑같은 방식입니다.

    data/tiger_months.csv
        year,month,code,name,record_date,payment_date,amount,tax_basis

⭐ 핵심 — **월별 표는 종목이 아니라 달에 붙습니다.** 한 달치를 받으면 그 달
TIGER 전 종목이 다 들어옵니다. 그래서 달만 굳혀 두면 **모든 TIGER ETF 가
공짜**가 됩니다. 종목이 몇 개든 파일 크기는 안 늘어납니다.

언제 파일을 쓰고 언제 받아오나
------------------------------
    그 달이 지났고 + 과세표준 빈 칸이 없음  ->  파일에서 읽음 (HTTP 0회)
    이번 달                                ->  받아옴 (지급이 더 붙을 수 있음)
    지났는데 빈 칸이 남아 있음              ->  받아옴 (나중에 채워지는 일이 있음)

판단은 `tiger_provider._month_ttl()` 한 곳에서 합니다 — 파일을 쓸지 정하는
규칙과 캐시 유효기간 규칙이 **같아야** 하기 때문입니다. 따로 두면 한쪽만
고쳤을 때 조용히 어긋납니다.

파일을 다시 만드는 것
---------------------
`tools/build_tiger_months.py` 를 **개발자 PC 에서만** 돌립니다. 배포된 앱은
읽기만 합니다. 덮어쓰지 않고 **새 달을 더합니다** — 돌릴수록 이력이 길어지고,
한 번 들어간 지난 달은 다시 건드리지 않습니다.

파일이 없거나 깨져도 앱은 그대로 돕니다. 그냥 전부 받아올 뿐입니다.
"""

from __future__ import annotations

import csv
import os

import config
from data.providers import cache

CSV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "tiger_months.csv",
)

FIELDS = ("year", "month", "code", "name", "record_date", "payment_date",
          "amount", "tax_basis")


def _load() -> dict[tuple[int, int], dict[str, dict]]:
    """{(연, 월): {종목코드: 행}}. 파일이 없거나 깨졌으면 빈 dict."""
    out: dict[tuple[int, int], dict[str, dict]] = {}
    if not os.path.exists(CSV_PATH):
        return out
    try:
        with open(CSV_PATH, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                try:
                    ym = (int(row["year"]), int(row["month"]))
                except (KeyError, TypeError, ValueError):
                    continue
                code = str(row.get("code") or "").strip().upper()
                if not code:
                    continue
                # ⚠ 프로바이더가 쓰는 모양과 **똑같이** 돌려줘야 합니다.
                #    파일에서 온 것과 받아온 것이 구별되면 안 됩니다.
                out.setdefault(ym, {})[code] = {
                    "name": str(row.get("name") or "").strip(),
                    "record_date": str(row.get("record_date") or "").strip(),
                    "payment_date": str(row.get("payment_date") or "").strip(),
                    "amount": str(row.get("amount") or "").strip(),
                    "tax_basis": str(row.get("tax_basis") or "").strip(),
                }
    except (OSError, csv.Error):
        # 파일이 깨졌다고 앱이 죽으면 안 됩니다. 전부 받아오는 쪽으로 내려갑니다.
        return {}
    return out


def all_months() -> dict[tuple[int, int], dict[str, dict]]:
    return cache.get_or_set("tiger:seed", config.CACHE_TTL_ISSUER_INDEX_SECONDS, _load)


def month_rows(year: int, month: int) -> dict[str, dict] | None:
    """그 달 표. 파일에 없으면 None.

    ⚠ `None`(파일에 없음)과 `{}`(그 달엔 지급이 없었음)은 **다른 뜻**입니다.
      빈 dict 를 "없음" 으로 다루면 지급이 없던 달을 매번 다시 받아옵니다.
    """
    return all_months().get((int(year), int(month)))


def stats() -> dict:
    table = all_months()
    return {
        "path": CSV_PATH,
        "exists": os.path.exists(CSV_PATH),
        "months": len(table),
        "rows": sum(len(v) for v in table.values()),
    }

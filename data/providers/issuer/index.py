"""
data/providers/issuer/index.py  --  종목코드 -> 운용사 내부 ID 매핑
===================================================================

ACE·RISE·SOL·PLUS·TIME 은 6자리 종목코드로 바로 조회할 수 없고, 운용사가 쓰는
내부 ID(펀드코드/상품번호)를 알아야 합니다.

**그 매핑을 실행할 때마다 사이트에서 긁으면 안 됩니다.** 첫 화면이 수십 초씩 걸리고,
남의 서버를 매번 두드리는 일이라 예의도 아닙니다. 그래서 저장소에 시드 CSV 를 넣어
두고 거기서 읽습니다.

    data/issuer_index.csv      code,brand,fund_id,name

시드를 다시 만드는 스크립트는 `tools/build_issuer_index.py` 이고, **개발자 PC 에서만**
돌립니다. 배포된 앱은 CSV 를 읽기만 합니다.

시드에 없는 종목은? **지어내지 않습니다.** 운용사 provider 를 건너뛰고 일반
폴백(yfinance 분배금, 과세표준 없음)으로 내려가고, 화면에는 과세표준을
`데이터 없음` 으로 표시합니다.
"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass

import config
from data.providers import cache

_CSV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "issuer_index.csv",
)


@dataclass(frozen=True)
class IndexRow:
    code: str        # 6자리 종목코드
    brand: str       # "ACE" | "RISE" | "SOL" | "PLUS" | "TIME" | ...
    fund_id: str     # 그 운용사의 내부 ID
    name: str = ""


def _load() -> dict[str, IndexRow]:
    out: dict[str, IndexRow] = {}
    if not os.path.exists(_CSV_PATH):
        return out
    try:
        with open(_CSV_PATH, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                code = str(row.get("code") or "").strip().upper()
                brand = str(row.get("brand") or "").strip().upper()
                fund_id = str(row.get("fund_id") or "").strip()
                if not (code and brand and fund_id):
                    continue
                out[code] = IndexRow(code=code, brand=brand, fund_id=fund_id,
                                     name=str(row.get("name") or "").strip())
    except (OSError, csv.Error):
        # 매핑 파일이 깨졌다고 앱이 죽으면 안 됩니다. 폴백으로 내려갑니다.
        return {}
    return out


def all_rows() -> dict[str, IndexRow]:
    return cache.get_or_set("issuer:index", config.CACHE_TTL_ISSUER_INDEX_SECONDS, _load)


def lookup(code: str) -> IndexRow | None:
    return all_rows().get(str(code).strip().upper().zfill(6))


def brand_of(code: str) -> str | None:
    row = lookup(code)
    return row.brand if row else None


def fund_id_of(code: str, brand: str) -> str | None:
    """그 종목이 해당 브랜드 상품일 때만 내부 ID 를 돌려줍니다."""
    row = lookup(code)
    if row is None or row.brand.upper() != brand.upper():
        return None
    return row.fund_id


def csv_path() -> str:
    return _CSV_PATH


def is_available() -> bool:
    return bool(all_rows())

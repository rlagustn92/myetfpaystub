"""
tools/build_issuer_index.py  --  종목코드 -> 운용사 내부 ID 매핑 시드 만들기
=============================================================================

**개발자 PC 에서만 돌립니다.** 배포된 앱은 결과 CSV(`data/issuer_index.csv`)를
읽기만 합니다. 실행할 때마다 운용사 사이트를 긁으면 첫 화면이 수십 초 걸리고,
남의 서버를 매번 두드리는 일이라 예의도 아닙니다.

    python tools/build_issuer_index.py

만드는 것:

    data/issuer_index.csv       code,brand,fund_id,name

ACE·RISE·SOL·PLUS·TIME 은 6자리 종목코드로 바로 조회할 수 없어서 내부 ID 가 꼭
필요하고, KODEX·TIGER 는 코드로 바로 되지만 **어느 운용사 상품인지 판별**하는 데
쓰려고 같이 넣습니다(그 둘의 fund_id 는 종목코드와 같습니다).

안전장치
--------
- 새로 만든 결과가 기존보다 **20% 넘게 줄면 덮어쓰지 않습니다.**
  네트워크가 반쯤 죽은 상태로 돌려서 멀쩡한 시드를 날리는 사고를 막습니다.
- 운용사 한 곳이 실패해도 나머지는 그대로 모읍니다.
"""

from __future__ import annotations

import csv
import html as _html
import os
import re
import sys
import time

import requests

# `python tools/build_issuer_index.py` 로 실행하면 sys.path 에 tools/ 만 들어가서
# 저장소 루트의 data/ 패키지를 못 찾습니다. 루트를 직접 넣어 줍니다.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
TIMEOUT = 20
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "data", "issuer_index.csv")

Row = tuple[str, str, str, str]   # code, brand, fund_id, name


def _get(url: str, **kw) -> requests.Response:
    r = requests.get(url, headers={**HEADERS, **kw.pop("headers", {})}, timeout=TIMEOUT, **kw)
    r.raise_for_status()
    return r


def _post(url: str, data: dict, **kw) -> requests.Response:
    r = requests.post(url, data=data, headers={**HEADERS, **kw.pop("headers", {})},
                      timeout=TIMEOUT, **kw)
    r.raise_for_status()
    return r


def _text(s: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def _code_from_isin(isin: str) -> str | None:
    s = str(isin or "").strip().upper()
    return s[3:9] if len(s) >= 9 and s.startswith("KR") else None


# ---------------------------------------------------------------------
def collect_kodex() -> list[Row]:
    """KODEX 는 종목코드로 바로 조회됩니다. 브랜드 판별용으로만 모읍니다."""
    out: list[Row] = []
    seen: set[str] = set()
    page = 1
    while page <= 200:
        d = _get("https://www.samsungfund.com/api/v1/kodex/distribution.do",
                 params={"pageNo": page, "ordrColm": "BASIC_D", "period": 0,
                         "ordrSort": "DESC", "srchVal": ""},
                 headers={"Referer": "https://www.samsungfund.com/etf/product/distribution.do"}
                 ).json()
        rows = d.get("dividList") or []
        for r in rows:
            code = str(r.get("stkTicker") or "").strip().upper()
            if code and code not in seen:
                seen.add(code)
                out.append((code, "KODEX", code, str(r.get("fNm") or "")))
        if not rows or page * 12 >= int(d.get("totalCnt") or 0):
            break
        page += 1
    return out


def collect_tiger() -> list[Row]:
    """TIGER 도 종목코드로 조회됩니다. 브랜드 판별용.

    ⚠ 이 목록은 앱이 실제로 쓰는 provider 와 **같은 함수**로 받습니다.
    예전에는 여기서 따로 긁었는데, provider 쪽 페이징 버그를 고쳐도 시드는 그대로라
    두 곳의 결과가 어긋났습니다. 한 군데서만 받도록 합쳤습니다.
    """
    from data.providers.issuer import tiger_provider

    out: list[Row] = []
    seen: set[str] = set()
    year = time.localtime().tm_year
    for y in (year, year - 1):
        for m in range(1, 13):
            try:
                table = tiger_provider._fetch_month(y, m)
            except Exception:  # noqa: BLE001
                continue
            for code, row in table.items():
                if code not in seen:
                    seen.add(code)
                    out.append((code, "TIGER", code, row.get("name") or ""))
    return out


def collect_ace() -> list[Row]:
    d = _get("https://papi.aceetf.co.kr/api/funds",
             params={"page": 1, "size": 1000},
             headers={"Referer": "https://www.aceetf.co.kr/"}).json()
    out: list[Row] = []
    for f in d.get("data") or []:
        code = _code_from_isin(f.get("stockCd") or "")
        fund_cd = str(f.get("fundCd") or "").strip()
        if code and fund_cd:
            out.append((code, "ACE", fund_cd, str(f.get("fundNm") or "")))
    return out


def collect_rise() -> list[Row]:
    out: list[Row] = []
    page = 1
    while page <= 30:
        d = _get("https://kbam.co.kr/api/products/etfs",
                 params={"page": page, "size": 200},
                 headers={"Referer": "https://www.riseetf.co.kr/"}).json()
        items = d.get("page_items") or []
        for f in items:
            code = str(f.get("krx_cd") or "").strip().upper()
            fund_cd = str(f.get("fund_cd") or "").strip()
            if code and fund_cd:
                out.append((code, "RISE", fund_cd, str(f.get("name") or "")))
        info = d.get("page_info") or {}
        # ⚠ 키 이름이 total_page(단수) 이고, size 파라미터는 무시돼 한 번에 20건씩만 옵니다.
        total = int(info.get("total_page") or 1)
        if page >= total or not items:
            break
        page += 1
    return out


def collect_sol() -> list[Row]:
    t = _get("https://www.soletf.com/ko/fund",
             headers={"Referer": "https://www.soletf.com/"}).text
    out: list[Row] = []
    # 카드 한 장: <a href="/ko/fund/etf/211044"> ... <span class="fd-name">이름 <br> (473330)</span>
    pattern = re.compile(
        r'/ko/fund/etf/(\d+)".*?class="fd-name">(.*?)</span>', re.S)
    for fund_id, block in pattern.findall(t):
        text = _text(block)
        # ⚠ 이름 칸 안에 주석(<!-- ... -->)이 들어 있어 태그를 지워도 "-->" 가 남습니다.
        #    그래서 문자열 끝($)에 앵커를 걸면 안 되고, 마지막 (코드) 를 찾습니다.
        found = re.findall(r"\(([0-9A-Z]{6})\)", text)
        if not found:
            continue
        m = re.search(r"\(" + found[-1] + r"\)", text)
        name = text[:m.start()].strip() if m else ""
        out.append((found[-1], "SOL", fund_id, name))
    return out


def collect_plus() -> list[Row]:
    """PLUS 는 상세 페이지에 종목코드가 있습니다. 목록에서 먼저 시도하고, 없으면 상세로."""
    t = _get("https://www.plusetf.co.kr/product/overview",
             headers={"Referer": "https://www.plusetf.co.kr/"}).text
    # ⚠ findall 로 꼬리까지 한 번에 잡으면 그 꼬리 안에 있는 다음 링크를 건너뜁니다
    #    (매치가 겹치지 않기 때문). 번호만 먼저 모읍니다. 실제로 86개 중 40개를 놓쳤습니다.
    numbers: list[str] = []
    seen: set[str] = set()
    for n in re.findall(r"/product/detail\?n=(\d+)", t):
        if n not in seen:
            seen.add(n)
            numbers.append(n)

    out: list[Row] = []
    started, streak = time.time(), 0
    for n in numbers:
        if time.time() - started > 8 * 60:      # 시간 예산
            print(f"  PLUS: 시간 예산 초과, {len(out)}건까지만 수집")
            break
        try:
            page = _get(f"https://www.plusetf.co.kr/product/detail?n={n}",
                        headers={"Referer": "https://www.plusetf.co.kr/"}).text
        except requests.RequestException:
            streak += 1
            if streak >= 10:                     # 회로차단기
                print("  PLUS: 연속 실패, 중단")
                break
            continue
        streak = 0
        m = re.search(r'class="summary__product-code"[^>]*>\s*([0-9A-Z]{6})\s*<', page)
        if not m:
            continue
        title = re.search(r"<title>(.*?)</title>", page, re.S)
        name = _text(title.group(1)).split("|")[0].strip() if title else ""
        out.append((m.group(1), "PLUS", n, name))
    return out


def collect_timefolio() -> list[Row]:
    idxs: set[str] = set()
    for cate in ("001", "002"):
        try:
            t = _get(f"https://timeetf.co.kr/m11_list.php?cate={cate}",
                     headers={"Referer": "https://timeetf.co.kr/"}).text
        except requests.RequestException:
            continue
        idxs.update(re.findall(r"m11_view\.php\?idx=(\d+)", t))
    out: list[Row] = []
    for i in sorted(idxs, key=int):
        try:
            page = _get(f"https://timeetf.co.kr/m11_view.php?idx={i}",
                        headers={"Referer": "https://timeetf.co.kr/"}).text
        except requests.RequestException:
            continue
        title = re.search(r"<title>(.*?)</title>", page, re.S)
        if not title:
            continue
        text = _text(title.group(1))
        m = re.search(r"\(([0-9A-Z]{6})\)", text)
        if not m:
            continue
        out.append((m.group(1), "TIME", i, text[:m.start()].strip()))
    return out


COLLECTORS = {
    "KODEX": collect_kodex,
    "TIGER": collect_tiger,
    "ACE": collect_ace,
    "RISE": collect_rise,
    "SOL": collect_sol,
    "PLUS": collect_plus,
    "TIME": collect_timefolio,
}


def main(only: list[str] | None = None) -> int:
    """`python tools/build_issuer_index.py TIGER ACE` 처럼 브랜드를 골라 갱신할 수 있습니다.
    고르면 나머지 브랜드는 기존 CSV 값을 그대로 유지합니다(다시 긁지 않습니다)."""
    rows: list[Row] = []
    for brand, fn in COLLECTORS.items():
        if only and brand not in only:
            continue
        try:
            got = fn()
        except Exception as e:  # noqa: BLE001 - 한 곳이 죽어도 나머지는 모읍니다
            print(f"{brand:6} 실패: {type(e).__name__} {e}")
            continue
        print(f"{brand:6} {len(got):4}건")
        rows.extend(got)

    # 코드 중복 제거 (먼저 들어온 브랜드 우선 — COLLECTORS 순서가 곧 우선순위)
    merged: dict[str, Row] = {}
    for r in rows:
        merged.setdefault(r[0].upper(), r)

    before = 0
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8", newline="") as f:
            existing = list(csv.DictReader(f))
        before = len(existing)
        for e in existing:
            code = str(e.get("code") or "").upper()
            brand = str(e.get("brand") or "").upper()
            if not code:
                continue
            if only and brand not in only:
                # 이번에 안 긁은 브랜드는 기존 값을 그대로 둡니다.
                merged.setdefault(code, (code, brand, str(e.get("fund_id") or ""),
                                         str(e.get("name") or "")))
    if before and len(merged) < before * 0.8:
        print(f"새 매핑이 너무 줄었습니다 ({before} -> {len(merged)}). 덮어쓰지 않습니다.")
        return 1

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["code", "brand", "fund_id", "name"])
        for code in sorted(merged):
            w.writerow(merged[code])
    print(f"\n저장: {OUT}  ({len(merged)}건)")
    return 0


if __name__ == "__main__":
    sys.exit(main([a.strip().upper() for a in sys.argv[1:]] or None))

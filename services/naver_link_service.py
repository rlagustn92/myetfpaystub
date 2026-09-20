"""
services/naver_link_service.py  --  "네이버 증권에서 보기" 바로가기
====================================================================

종목 상세 화면에서 네이버(Npay) 증권 페이지로 넘어가는 링크입니다.
차트·뉴스·재무처럼 이 앱이 안 만드는 것들을 보고 싶을 때 쓰라고 두는 통로입니다.

국내는 주소를 직접 만들 수 있습니다
-----------------------------------
    https://m.stock.naver.com/domestic/stock/{6자리코드}/total

미국은 만들 수 없습니다 — ⚠ 추측하면 빈 페이지로 보냅니다
--------------------------------------------------------
티커 뒤에 붙는 거래소 표시가 종목마다 다르고, **규칙이 없습니다.**

    SCHD -> /worldstock/etf/SCHD.K      (네이버 기준 AMEX)
    VOO  -> /worldstock/etf/VOO         (같은 AMEX 인데 아무것도 안 붙음)
    TQQQ -> /worldstock/etf/TQQQ.O
    TSLA -> /worldstock/stock/TSLA.O/total   (ETF 와 경로도 다름)

그래서 **자동완성에 물어보고, 돌려준 주소를 그대로 씁니다.**

    GET https://ac.stock.naver.com/ac?q=SCHD&target=stock
    -> {"items":[{"code":"SCHD","url":"/worldstock/etf/SCHD.K","nationCode":"USA", ...}]}

비슷한 이름이 같이 오므로 `code` 완전일치 + `nationCode` 로 걸러야 합니다.

호출량
------
이 앱에서 미국 종목은 **사용자가 직접 등록한 것뿐**이라 많아야 수십 개입니다.
그래서 배치나 시드 CSV 없이, 필요할 때 한 번 물어보고 24시간 캐시합니다.
(종목이 수천 개인 서비스라면 결과를 저장소에 넣어 둬야 합니다.)

실패하면 **링크를 안 그립니다.** 빈 페이지로 보내는 것보다 낫습니다.
공식 문서가 있는 API 가 아니므로 언제든 바뀔 수 있다는 전제로 씁니다.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request

import config
from data.providers import cache
from models.portfolio import MARKET_KR, MARKET_US

BASE = "https://m.stock.naver.com"
AC = "https://ac.stock.naver.com/ac"
HEADERS = {"User-Agent": config.HTTP_USER_AGENT, "Referer": f"{BASE}/"}
TIMEOUT = 6.0


def korean_url(code: str) -> str:
    """국내는 코드로 조립합니다. 물어볼 필요가 없습니다."""
    return f"{BASE}/domestic/stock/{str(code).strip().upper().zfill(6)}/total"


def _lookup_us(ticker: str) -> str | None:
    want = str(ticker).strip().upper()
    if not want:
        return None
    q = urllib.parse.urlencode({"q": want, "target": "stock"})
    req = urllib.request.Request(f"{AC}?{q}", headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception:      # noqa: BLE001 - 바로가기 때문에 화면이 죽으면 안 됩니다
        return None
    for item in data.get("items") or []:
        # ⚠ code 완전일치 + nationCode 로 걸러야 합니다. 안 그러면 이름이 비슷한
        #    다른 나라 종목이 잡힙니다.
        if (str(item.get("code", "")).upper() == want
                and item.get("nationCode") == "USA"
                and item.get("url")):
            # ⚠ 돌려준 url 을 **그대로** 씁니다. ETF 와 일반주식은 경로가 다릅니다.
            return BASE + str(item["url"])
    return None


def us_url(ticker: str) -> str | None:
    """미국 종목 주소. 못 찾으면 None (링크를 안 그립니다)."""
    sym = str(ticker).strip().upper()
    if not sym:
        return None
    return cache.get_or_set(f"naver:us:{sym}", config.CACHE_TTL_SEARCH_SECONDS,
                            lambda: _lookup_us(sym))


def url_for(market: str, ticker: str) -> str | None:
    m = (market or "").upper()
    if m == MARKET_KR:
        return korean_url(ticker)
    if m == MARKET_US:
        return us_url(ticker)
    return None

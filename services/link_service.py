"""
services/link_service.py  --  종목 바로가기 모음 (네이버 · 토스 · 야후)
=======================================================================

차트·뉴스·재무처럼 **이 앱이 안 만드는 것**을 보고 싶을 때 넘어가는 통로입니다.
위층(app.py)은 `links_for()` 하나만 부르고, 어디를 붙일지는 여기서 정합니다.

대원칙 — 못 만드는 주소는 안 그립니다
-------------------------------------
빈 페이지나 "종목을 찾을 수 없습니다" 로 보내는 것은 링크가 없는 것보다 나쁩니다.
그래서 **주소를 확실히 만들 수 있을 때만** 내보냅니다.

어디까지 되나 (2026-09-21 브라우저로 실제 확인)
-----------------------------------------------
                    한국                               미국
    네이버   ✅ 코드로 조립                      ✅ 자동완성에 물어봄
    토스     ✅ /stocks/A{6자리}                 ❌ **주소를 만들 수 없음**
    야후     ✅ /quote/{6자리}.KS 또는 .KQ       ✅ /quote/{티커}

⚠ **토스의 미국 종목 주소는 추측하면 안 됩니다.** 토스 웹은 SPA 라서 아무 경로나
   HTTP 200 을 돌려주고, 화면만 "페이지를 찾을 수 없습니다" 가 됩니다. 즉
   **상태 코드로는 맞는 주소인지 알 수 없습니다.** 실제로 `/stocks/SCHD`,
   `/stocks/US8085247976`, `/us-stocks/SCHD` 를 전부 열어 봤지만 종목 화면이
   안 나왔고, 검색 API 는 로그인을 요구합니다. 그래서 미국은 토스를 뺍니다
   (미국은 네이버와 야후가 이미 있습니다).

⚠ **야후의 한국 주소는 `.KS`(코스피) / `.KQ`(코스닥)가 갈립니다.** 잘못 붙이면
   "Symbol not found" 페이지로 갑니다. 거래소는 `search_service.kr_exchange()`
   가 알려줍니다 — 검색이 쓰는 목록과 **같은 24시간 캐시**라 따로 부르는 값이
   없습니다. 한국 ETF 는 전부 코스피라서, 모르면 `.KS` 로 둡니다.
"""

from __future__ import annotations

from services import naver_link_service, search_service
from models.portfolio import MARKET_KR, MARKET_US

TOSS_BASE = "https://www.tossinvest.com"
YAHOO_BASE = "https://finance.yahoo.com"


def toss_url(market: str, ticker: str) -> str | None:
    """토스증권. 한국만 만들 수 있습니다(위 docstring 참고)."""
    if (market or "").upper() != MARKET_KR:
        return None
    # ⚠ 빈 값을 먼저 걸러야 합니다. `"".zfill(6)` 은 "000000" 이라서
    #    그냥 두면 있지도 않은 /stocks/A000000 으로 보냅니다.
    raw = str(ticker or "").strip().upper()
    if not raw:
        return None
    code = raw.zfill(6)
    if len(code) != 6:
        return None
    # 앞의 "A" 는 KRX 단축코드 표기입니다. 토스가 그대로 씁니다.
    return f"{TOSS_BASE}/stocks/A{code}"


def yahoo_url(market: str, ticker: str) -> str | None:
    """야후 파이낸스. 한국은 거래소에 따라 접미사가 갈립니다."""
    m = (market or "").upper()
    sym = str(ticker or "").strip().upper()
    if not sym:
        return None
    if m == MARKET_US:
        return f"{YAHOO_BASE}/quote/{sym}"
    if m == MARKET_KR:
        code = sym.zfill(6)
        if len(code) != 6:
            return None
        # 코스닥이면 .KQ, 그 외(코스피 · 모르면)는 .KS.
        exchange = search_service.kr_exchange(code).upper()
        suffix = ".KQ" if "KOSDAQ" in exchange else ".KS"
        return f"{YAHOO_BASE}/quote/{code}{suffix}"
    return None


def links_for(market: str, ticker: str) -> list[tuple[str, str]]:
    """(보여줄 이름, 주소) 목록. 만들 수 있는 것만 담깁니다.

    순서는 **한국 사람이 실제로 많이 쓰는 순서**입니다. 야후는 영문이라 뒤로.
    """
    out: list[tuple[str, str]] = []
    naver = naver_link_service.url_for(market, ticker)
    if naver:
        out.append(("Npay증권", naver))
    toss = toss_url(market, ticker)
    if toss:
        out.append(("토스증권", toss))
    yahoo = yahoo_url(market, ticker)
    if yahoo:
        out.append(("야후파이낸스", yahoo))
    return out

"""
services/search_service.py  --  종목 찾기
==========================================

"어떤 ETF 인가요?" 칸에서 쓰는 검색입니다. 사용자는 이렇게 칩니다.

    SCHD          영문 티커
    069500        6자리 종목코드
    코덱스 / KODEX  이름 일부
    미국배당       이름 일부

한국 목록은 FinanceDataReader 의 KRX + ETF/KR 을 합쳐 씁니다(24시간 캐시, 목록이
제일 무겁습니다). 미국은 전체 목록 API 가 마땅치 않아서 **자주 쓰는 ETF 시드**를
두고, 시드에 없으면 yfinance 로 실제 조회해서 존재를 확인합니다.
"""

from __future__ import annotations

from dataclasses import dataclass

import config
from data.providers import cache
from data.providers.issuer import index as issuer_index
from models.portfolio import MARKET_KR, MARKET_US

try:
    import FinanceDataReader as fdr
except Exception:  # pragma: no cover
    fdr = None

try:
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None


# 미국은 상장 종목이 너무 많고 무료 전체목록이 마땅치 않습니다.
# 한국 투자자가 실제로 많이 가지고 있는 것들만 시드로 둡니다.
# 여기 없어도 티커를 정확히 치면 yfinance 로 확인해서 추가됩니다.
US_SEED: tuple[tuple[str, str], ...] = (
    ("SCHD", "Schwab US Dividend Equity ETF"),
    ("JEPI", "JPMorgan Equity Premium Income ETF"),
    ("JEPQ", "JPMorgan Nasdaq Equity Premium Income ETF"),
    ("QQQ", "Invesco QQQ Trust"),
    ("QQQM", "Invesco NASDAQ 100 ETF"),
    ("SPY", "SPDR S&P 500 ETF Trust"),
    ("VOO", "Vanguard S&P 500 ETF"),
    ("VTI", "Vanguard Total Stock Market ETF"),
    ("VYM", "Vanguard High Dividend Yield ETF"),
    ("DGRO", "iShares Core Dividend Growth ETF"),
    ("DIVO", "Amplify CWP Enhanced Dividend Income ETF"),
    ("SPYD", "SPDR Portfolio S&P 500 High Dividend ETF"),
    ("O", "Realty Income Corporation"),
    ("TLT", "iShares 20+ Year Treasury Bond ETF"),
    ("SGOV", "iShares 0-3 Month Treasury Bond ETF"),
    ("XYLD", "Global X S&P 500 Covered Call ETF"),
    ("QYLD", "Global X NASDAQ 100 Covered Call ETF"),
    ("RYLD", "Global X Russell 2000 Covered Call ETF"),
    ("SCHG", "Schwab U.S. Large-Cap Growth ETF"),
    ("VT", "Vanguard Total World Stock ETF"),
)


@dataclass
class SearchHit:
    market: str
    ticker: str
    name: str
    asset_type: str = "ETF"

    @property
    def currency(self) -> str:
        return "USD" if self.market == MARKET_US else "KRW"

    def label(self) -> str:
        if self.market == MARKET_KR:
            return f"{self.name} ({self.ticker})"
        return f"{self.ticker} — {self.name}"


# ---------------------------------------------------------------------
def _kr_universe() -> list[SearchHit]:
    """한국 상장 종목 목록. ETF 를 앞에 둡니다 (이 앱은 ETF 용이라서)."""

    def _load() -> list[SearchHit]:
        hits: list[SearchHit] = []
        seen: set[str] = set()

        if fdr is not None:
            try:
                etf = fdr.StockListing("ETF/KR")
                code_col = "Symbol" if "Symbol" in etf.columns else etf.columns[0]
                name_col = "Name" if "Name" in etf.columns else etf.columns[1]
                for _, r in etf.iterrows():
                    code = str(r[code_col]).strip().upper().zfill(6)
                    if code in seen:
                        continue
                    seen.add(code)
                    hits.append(SearchHit(MARKET_KR, code, str(r[name_col]), "ETF"))
            except Exception:  # noqa: BLE001 - 목록 하나 실패로 검색을 못 쓰게 두지 않습니다
                pass
            try:
                krx = fdr.StockListing("KRX")
                code_col = "Code" if "Code" in krx.columns else krx.columns[0]
                name_col = "Name" if "Name" in krx.columns else krx.columns[2]
                for _, r in krx.iterrows():
                    code = str(r[code_col]).strip().upper().zfill(6)
                    if code in seen:
                        continue
                    seen.add(code)
                    hits.append(SearchHit(MARKET_KR, code, str(r[name_col]), "STOCK"))
            except Exception:  # noqa: BLE001
                pass

        # 목록을 못 가져왔더라도 운용사 매핑에 있는 ETF 만큼은 찾을 수 있게 합니다.
        for code, row in issuer_index.all_rows().items():
            if code not in seen and row.name:
                seen.add(code)
                hits.append(SearchHit(MARKET_KR, code, row.name, "ETF"))
        return hits

    return cache.get_or_set("search:kr", config.CACHE_TTL_SEARCH_SECONDS, _load)


def _us_seed_hits() -> list[SearchHit]:
    return [SearchHit(MARKET_US, t, n, "ETF") for t, n in US_SEED]


def resolve_us_ticker(ticker: str) -> SearchHit | None:
    """시드에 없는 미국 티커를 yfinance 로 실제 확인합니다. 없으면 None."""
    sym = str(ticker).strip().upper()
    if not sym or yf is None:
        return None
    key = f"search:us:{sym}"

    def _load() -> SearchHit | None:
        try:
            info = yf.Ticker(sym).fast_info
            price = info.get("lastPrice") if hasattr(info, "get") else info["lastPrice"]
        except Exception:  # noqa: BLE001
            return None
        if not price:
            return None
        name = sym
        try:
            got = yf.Ticker(sym).info.get("shortName")
            if got:
                name = str(got)
        except Exception:  # noqa: BLE001 - 이름은 부가정보라 없어도 됩니다
            pass
        return SearchHit(MARKET_US, sym, name, "ETF")

    return cache.get_or_set(key, config.CACHE_TTL_SEARCH_SECONDS, _load)


def search(query: str, market: str = "ALL", limit: int = 30) -> list[SearchHit]:
    """티커/종목코드/이름으로 찾습니다. 정확히 맞는 것을 맨 위로 올립니다."""
    q = str(query or "").strip()
    if not q:
        return []
    qu = q.upper()

    pool: list[SearchHit] = []
    if market in ("ALL", MARKET_KR):
        pool += _kr_universe()
    if market in ("ALL", MARKET_US):
        pool += _us_seed_hits()

    exact = [h for h in pool if h.ticker.upper() == qu]
    starts = [h for h in pool if h.ticker.upper().startswith(qu)
              or h.name.upper().startswith(qu)]
    contains = [h for h in pool if qu in h.name.upper()]

    out: list[SearchHit] = []
    seen: set[tuple[str, str]] = set()
    for group in (exact, starts, contains):
        for h in group:
            key = (h.market, h.ticker)
            if key in seen:
                continue
            seen.add(key)
            out.append(h)
            if len(out) >= limit:
                return out

    # 미국 티커를 정확히 쳤는데 시드에 없으면 실제로 있는지 물어봅니다.
    if not out and market in ("ALL", MARKET_US) and 1 <= len(qu) <= 6 and qu.isalpha():
        hit = resolve_us_ticker(qu)
        if hit:
            out.append(hit)
    return out

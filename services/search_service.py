"""
services/search_service.py  --  종목 찾기
==========================================

"어떤 ETF 인가요?" 칸에서 쓰는 검색입니다. 사용자는 이렇게 칩니다.

    SCHD          영문 티커
    069500        6자리 종목코드
    코덱스 / KODEX  이름 일부 (한글로 쳐도 찾습니다)
    미국배당       이름 일부

한국 ETF 이름은 길고 띄어쓰기가 제각각입니다
--------------------------------------------
"KODEX 200타겟위클리커버드콜", "TIGER 미국나스닥100커버드콜(합성)" 처럼
**어디서 띄는지 사람이 외울 수 없습니다.** 그래서 이렇게 찾습니다.

1. **띄어쓰기와 기호를 아예 지우고 비교합니다.** 사용자가 어떻게 띄든 같아집니다.
2. **단어를 여러 개 치면 전부 들어간 것만** 보여줍니다(AND). 순서는 상관없습니다.

       "커버 액티"  ->  KODEX 200커버드콜액티브   ✅ (두 조각이 다 들어감)
       "나스닥 커버" ->  TIGER 미국나스닥100커버드콜(합성)  ✅
       "200 커버"   ->  KODEX 200타겟위클리커버드콜  ✅

   앞글자만 알아도 됩니다 — "액티" 로 "액티브" 가 잡힙니다.
3. **운용사는 한글로 쳐도 됩니다** (코덱스 -> KODEX). `_BRAND_ALIASES` 참고.

⚠ 사용자가 친 것을 **정규화해서 비교만** 합니다. 화면에 보여주는 이름은 언제나
운용사가 쓰는 원래 이름 그대로입니다(줄이거나 바꾸지 않습니다).

한국 목록은 FinanceDataReader 의 KRX + ETF/KR 을 합쳐 씁니다(24시간 캐시, 목록이
제일 무겁습니다). 미국은 전체 목록 API 가 마땅치 않아서 **자주 쓰는 ETF 시드**를
두고, 시드에 없으면 yfinance 로 실제 조회해서 존재를 확인합니다.
"""

from __future__ import annotations

import re
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


# 운용사를 한글로 치는 사람이 많습니다. 정규화한 글자열 안에서 그대로 치환합니다
# ("코덱스200" 처럼 붙여 써도 "KODEX200" 이 됩니다).
# ⚠ 긴 것부터 적용해야 합니다 — "타임폴리오" 가 "타임" 보다 먼저여야 합니다.
_BRAND_ALIASES: tuple[tuple[str, str], ...] = (
    ("타임폴리오", "TIMEFOLIO"),
    ("네비게이터", "TIMEFOLIO"),
    ("미래에셋", "TIGER"),
    ("삼성", "KODEX"),
    ("한국투자", "ACE"),
    ("코덱스", "KODEX"),
    ("타이거", "TIGER"),
    ("에이스", "ACE"),
    ("라이즈", "RISE"),
    ("케이비", "RISE"),
    ("하나로", "HANARO"),
    ("플러스", "PLUS"),
    ("키움", "KIWOOM"),
    ("코세프", "KOSEF"),
    ("신한", "SOL"),
    ("우리", "WON"),
    ("타임", "TIME"),
)

# 비교하기 전에 지우는 것들 — 띄어쓰기·가운뎃점·괄호·하이픈 등.
_STRIP = re.compile(r"[\s·・\-_,.()\[\]{}/'\"&+:;]+")


def normalize(text: str) -> str:
    """비교용으로만 쓰는 형태. 띄어쓰기·기호를 지우고 대문자로 맞춥니다.

    ⚠ 화면에 이 값을 쓰면 안 됩니다. 보여주는 이름은 언제나 원래 이름입니다.
    """
    return _STRIP.sub("", str(text or "")).upper()


def tokenize(query: str) -> list[str]:
    """사용자가 친 것을 조각으로. 조각마다 한글 운용사명을 영문으로 바꿉니다.

    "커버 액티" -> ["커버", "액티"]     (둘 다 들어간 것만 찾습니다)
    "코덱스200"  -> ["KODEX200"]
    """
    out: list[str] = []
    for raw in str(query or "").split():
        tok = normalize(raw)
        for ko, en in _BRAND_ALIASES:
            tok = tok.replace(normalize(ko), en)
        if tok:
            out.append(tok)
    return out


@dataclass
class SearchHit:
    market: str
    ticker: str
    name: str
    asset_type: str = "ETF"
    # "KOSPI" | "KOSDAQ" | "" (모름). 야후 파이낸스 주소의 .KS/.KQ 를 정할 때 씁니다.
    exchange: str = ""

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
                    # ETF/KR 목록에는 거래소 칸이 없습니다. 한국 ETF 는 전부
                    # 유가증권시장(KOSPI) 상장이라 KOSPI 로 둡니다.
                    hits.append(SearchHit(MARKET_KR, code, str(r[name_col]), "ETF",
                                          exchange="KOSPI"))
            except Exception:  # noqa: BLE001 - 목록 하나 실패로 검색을 못 쓰게 두지 않습니다
                pass
            try:
                krx = fdr.StockListing("KRX")
                code_col = "Code" if "Code" in krx.columns else krx.columns[0]
                name_col = "Name" if "Name" in krx.columns else krx.columns[2]
                has_market = "Market" in krx.columns
                for _, r in krx.iterrows():
                    code = str(r[code_col]).strip().upper().zfill(6)
                    if code in seen:
                        continue
                    seen.add(code)
                    # KRX 목록에는 KOSPI/KOSDAQ 이 들어 있습니다. 야후 주소가
                    # .KS 냐 .KQ 냐가 여기서 갈립니다.
                    hits.append(SearchHit(MARKET_KR, code, str(r[name_col]), "STOCK",
                                          exchange=(str(r["Market"]).strip()
                                                    if has_market else "")))
            except Exception:  # noqa: BLE001
                pass

        # 목록을 못 가져왔더라도 운용사 매핑에 있는 ETF 만큼은 찾을 수 있게 합니다.
        for code, row in issuer_index.all_rows().items():
            if code not in seen and row.name:
                seen.add(code)
                hits.append(SearchHit(MARKET_KR, code, row.name, "ETF",
                                      exchange="KOSPI"))
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
    """티커/종목코드/이름으로 찾습니다.

    조각을 여러 개 치면 **전부 들어간 것만** 나옵니다(AND, 순서 무관).
    띄어쓰기와 기호는 양쪽 다 지우고 비교하므로 어떻게 띄든 상관없습니다.
    """
    q = str(query or "").strip()
    if not q:
        return []
    tokens = tokenize(q)
    if not tokens:
        return []
    whole = "".join(tokens)          # 조각을 다 붙인 것 = 티커 비교용

    pool: list[SearchHit] = []
    if market in ("ALL", MARKET_KR):
        pool += _kr_universe()
    if market in ("ALL", MARKET_US):
        pool += _us_seed_hits()

    exact: list[SearchHit] = []
    starts: list[SearchHit] = []
    contains: list[SearchHit] = []
    for h in pool:
        tk = normalize(h.ticker)
        nm = normalize(h.name)
        # 조각이 전부 들어가야 후보입니다. 티커 쪽에 들어가도 인정합니다
        # ("SCHD" 를 쳤을 때 이름에 SCHD 가 없어도 찾히도록).
        if not all((t in nm) or (t in tk) for t in tokens):
            continue
        if tk == whole:
            exact.append(h)
        elif tk.startswith(whole) or nm.startswith(tokens[0]):
            starts.append(h)
        else:
            contains.append(h)

    # 조각을 다 만족하는 것끼리는 **이름이 짧은 것**이 대개 더 가깝습니다
    # ("커버 액티" -> "KODEX 200커버드콜액티브" 가 긴 파생상품명보다 위로).
    contains.sort(key=lambda h: (len(h.name), h.name))
    starts.sort(key=lambda h: (len(h.name), h.name))

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
    # ⚠ `isascii()` 를 꼭 같이 봐야 합니다. 한글도 `isalpha()` 가 True 라서,
    #    "미배당 다우" 처럼 한글로 못 찾았을 때 yfinance 에 한글을 물어보며
    #    쓸데없이 기다렸다 404 를 받습니다(실제로 그랬습니다).
    if not out and market in ("ALL", MARKET_US) and 1 <= len(whole) <= 6 \
            and whole.isascii() and whole.isalpha():
        hit = resolve_us_ticker(whole)
        if hit:
            out.append(hit)
    return out


def kr_exchange(code: str) -> str:
    """한국 종목의 거래소. "KOSPI" | "KOSDAQ" | "" (모름).

    야후 파이낸스 주소가 `.KS` 냐 `.KQ` 냐를 여기서 정합니다. 목록은 검색이
    쓰는 것과 **같은 24시간 캐시**라 따로 부르는 값이 없습니다.
    """
    want = str(code or "").strip().upper().zfill(6)
    if not want:
        return ""

    def _load() -> dict[str, str]:
        return {h.ticker: h.exchange for h in _kr_universe() if h.exchange}

    table = cache.get_or_set("search:kr:exchange", config.CACHE_TTL_SEARCH_SECONDS,
                             _load)
    return table.get(want, "")

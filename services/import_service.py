"""
services/import_service.py  --  증권사 잔고를 **붙여넣기** 로 가져오기
=======================================================================

왜 만들었나
-----------
이 앱의 가장 큰 진입장벽은 **일일이 입력하는 것**입니다. 증권사 세 곳에
종목이 열 개면 쉰 번을 타이핑해야 하고, 거기서 대부분 그만둡니다.

증권사 잔고 화면을 **그대로 긁어서 붙여넣으면** 되게 했습니다.
파일을 내려받을 필요도, 형식을 맞출 필요도 없습니다.

    KODEX 200          069500    100주    32,000원
    TIGER 미국배당다우존스  458730    50주     11,200원

탭이든 쉼표든 여러 칸 띄어쓰기든 다 받습니다. 증권사마다 열 순서와 이름이
다르므로 **머리글 이름으로 찾고**, 머리글이 없으면 **값의 생김새로** 찾습니다.

⚠ 개인정보는 받지 않습니다 (절대규칙 6)
---------------------------------------
증권사에서 긁으면 **계좌번호가 같이 딸려옵니다.** 그건 이 앱이 절대 안 받는
정보입니다. 그래서 계좌번호처럼 생긴 것(숫자-숫자-숫자, 8자리 이상 숫자
덩어리)은 **읽는 단계에서 버립니다.** 저장은커녕 화면에도 안 올립니다.

⚠ 숫자를 지어내지 않습니다 (절대규칙 1)
---------------------------------------
못 읽은 줄은 조용히 건너뛰지 않고 **"왜 못 읽었는지" 와 함께 돌려줍니다.**
사용자가 그 줄만 손으로 고치면 됩니다. 반쯤 읽은 줄을 0 으로 채워
넣는 일은 하지 않습니다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from models.portfolio import MARKET_KR, MARKET_US

# ---------------------------------------------------------------------
# 열 찾기 — 증권사마다 이름이 다릅니다
# ---------------------------------------------------------------------
# 실제 증권사 잔고 화면에서 쓰는 말들을 모았습니다. 긴 것부터 봅니다.
_COLUMN_WORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("ticker", ("종목코드", "단축코드", "종목번호", "표준코드", "코드", "심볼", "티커")),
    ("name", ("종목명", "상품명", "종목이름", "펀드명", "종목")),
    ("shares", ("보유수량", "잔고수량", "결제수량", "보유주식수", "주식수", "수량")),
    ("avg_price", ("매입평균단가", "평균매입단가", "매입단가", "평균단가", "취득단가",
                   "평균가", "평단가", "평단", "매입가")),
    ("account", ("계좌명", "계좌별칭", "상품유형", "계좌구분", "계좌")),
)

# 계좌번호처럼 생긴 것 — **읽는 단계에서 버립니다.**
_ACCOUNT_NO = re.compile(r"\b(?:\d{2,}-\d{2,}-\d{2,}|\d{8,})\b")

# 6자리 한국 종목코드. 영문이 섞일 수 있습니다 (`0219E0`).
_KR_CODE = re.compile(r"^[0-9][0-9A-Z]{5}$")
# 미국 티커
_US_TICKER = re.compile(r"^[A-Z][A-Z.\-]{0,5}$")


@dataclass
class ParsedRow:
    """읽어낸 한 줄. 못 읽은 것은 `problem` 에 이유가 들어갑니다."""

    ticker: str = ""
    name: str = ""
    shares: float | None = None
    avg_price: float | None = None
    account: str = ""
    market: str = MARKET_KR
    problem: str = ""
    raw: str = ""

    @property
    def ok(self) -> bool:
        return not self.problem and bool(self.ticker or self.name) and bool(self.shares)


@dataclass
class ParseResult:
    rows: list[ParsedRow] = field(default_factory=list)
    dropped_account_numbers: int = 0

    @property
    def good(self) -> list[ParsedRow]:
        return [r for r in self.rows if r.ok]

    @property
    def bad(self) -> list[ParsedRow]:
        return [r for r in self.rows if not r.ok]


# ---------------------------------------------------------------------
def strip_account_numbers(text: str) -> tuple[str, int]:
    """계좌번호처럼 생긴 것을 지웁니다. (지운 글, 지운 개수).

    ⚠ 이 앱은 계좌번호를 **입력칸조차 만들지 않습니다**(절대규칙 6).
      붙여넣기로 딸려 들어오는 것도 같은 규칙을 지켜야 합니다.
    """
    found = _ACCOUNT_NO.findall(text)
    return _ACCOUNT_NO.sub(" ", text), len(found)


def _cells(line: str) -> list[str]:
    """한 줄을 칸으로 쪼갭니다. 탭 / 쉼표 / 여러 칸 띄어쓰기를 다 받습니다.

    ⚠ **빈 칸을 버리면 안 됩니다.** 탭이나 쉼표로 나뉜 표에서 빈 칸 하나를
      지우면 그 뒤 열이 전부 한 칸씩 밀려서 **수량 자리에 단가가 들어옵니다.**
      에러는 안 나고 자산만 엉뚱해져서 눈으로 볼 때까지 모릅니다
      (실제로 `KODEX 200,,32000` 에서 32,000 이 수량이 됐습니다).

      띄어쓰기로 나눌 때는 반대입니다 — "빈 칸" 이라는 개념이 없으므로 버립니다.
    """
    def clean(parts: list[str]) -> list[str]:
        return [p.strip().strip('"').strip() for p in parts]

    if "\t" in line:
        return clean(line.split("\t"))
    if line.count(",") >= 2:
        return clean(_split_csv(line))
    parts = re.split(r"\s{2,}", line)
    if len(parts) < 3:                         # 한 칸 띄어쓰기로 붙여 넣은 경우
        parts = line.split()
    return [p for p in clean(parts) if p]


def _split_csv(line: str) -> list[str]:
    """쉼표로 쪼개되 **따옴표 안의 쉼표는 안 쪼갭니다.**

    금액에 천 단위 쉼표가 들어간 채로 오는 일이 흔합니다 — `"₩32,000"`.
    그냥 쪼개면 한 칸이 두 칸이 되어 그 뒤 열이 전부 밀립니다.
    """
    out: list[str] = []
    buf: list[str] = []
    quoted = False
    for ch in line:
        if ch == '"':
            quoted = not quoted
            continue
        if ch == "," and not quoted:
            out.append("".join(buf))
            buf = []
            continue
        buf.append(ch)
    out.append("".join(buf))
    return out


def _number(text: str) -> float | None:
    """"32,000원" · "1,234.56" · "100주" -> 숫자. 못 읽으면 None."""
    cleaned = re.sub(r"[^0-9.\-]", "", str(text or ""))
    if not cleaned or cleaned in ("-", "."):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _header_map(cells: list[str]) -> dict[str, int]:
    """머리글 줄이면 {필드: 열번호}. 아니면 빈 dict."""
    found: dict[str, int] = {}
    for i, cell in enumerate(cells):
        flat = re.sub(r"[\s()\[\]/]", "", cell)
        for field_name, words in _COLUMN_WORDS:
            if field_name in found:
                continue
            if any(w in flat for w in words):
                found[field_name] = i
                break
    # 수량과 종목을 둘 다 못 찾으면 머리글이 아닙니다.
    return found if ("shares" in found and ("ticker" in found or "name" in found)) else {}


def _guess_market(ticker: str, name: str) -> str:
    if _KR_CODE.match(ticker.upper()):
        return MARKET_KR
    if _US_TICKER.match(ticker.upper()):
        return MARKET_US
    # 코드가 없으면 이름으로: 한글이 있으면 한국.
    return MARKET_KR if re.search(r"[가-힣]", name) else MARKET_US


def _from_header(cells: list[str], cols: dict[str, int], raw: str) -> ParsedRow:
    def get(key: str) -> str:
        i = cols.get(key)
        return cells[i] if i is not None and i < len(cells) else ""

    ticker = get("ticker").upper().strip()
    name = get("name").strip()
    row = ParsedRow(ticker=ticker, name=name, account=get("account").strip(), raw=raw)
    row.shares = _number(get("shares"))
    row.avg_price = _number(get("avg_price"))
    row.market = _guess_market(ticker, name)
    if not (ticker or name):
        row.problem = "종목을 못 찾았습니다"
    elif not row.shares:
        row.problem = "수량을 못 찾았습니다"
    return row


def _from_shape(cells: list[str], raw: str) -> ParsedRow:
    """머리글이 없을 때 — **값의 생김새로** 찾습니다.

    종목코드처럼 생긴 칸, 한글이 든 칸(종목명), 숫자 칸들을 나눠 봅니다.
    숫자가 둘 이상이면 **작은 쪽이 수량, 큰 쪽이 단가**인 경우가 대부분이지만
    그렇게 단정하면 틀립니다(10주 × 5,000원 vs 5,000주 × 10원). 그래서
    **나온 순서**를 그대로 씁니다 — 증권사 화면이 수량을 먼저 보여줍니다.
    """
    row = ParsedRow(raw=raw)

    # ⭐ 종목코드를 **먼저** 찾습니다. 그게 이 줄에서 가장 확실한 단서고,
    #    찾고 나면 "앞은 이름, 뒤는 숫자" 로 깔끔하게 갈립니다.
    #    이걸 안 하고 왼쪽부터 훑으면 "KODEX 200 069500 5000 10" 에서
    #    KODEX 를 미국 티커로, 200 을 수량으로 읽습니다(실제로 그랬습니다).
    at = next((i for i, c in enumerate(cells) if _KR_CODE.match(c.upper())), None)
    if at is None:
        # 한국 코드가 없으면 미국 티커를 찾습니다. 숫자가 아닌 대문자 토막.
        at = next((i for i, c in enumerate(cells)
                   if _US_TICKER.match(c.upper()) and _number(c) is None), None)
    if at is not None:
        row.ticker = cells[at].upper()
        head, tail = cells[:at], cells[at + 1:]
    else:
        head, tail = cells, []

    # 이름 = 코드 앞의 글자 조각들 (띄어쓰기로 쪼개졌으면 다시 붙입니다)
    name_parts = [c for c in head if re.search(r"[가-힣A-Za-z]", c) or _number(c) is None]
    row.name = " ".join(p for p in name_parts if p).strip()

    # 수량·단가 = 코드 뒤의 숫자. 뒤에 없으면 앞에서 찾습니다.
    numbers = [n for n in (_number(c) for c in tail) if n is not None]
    if not numbers:
        numbers = [n for n in (_number(c) for c in head) if n is not None]
        # 이름에 숫자가 섞인 경우("KODEX 200")를 수량으로 오해하면 안 됩니다.
        if row.name and numbers:
            numbers = numbers[1:] if len(numbers) > 2 else numbers
    if numbers:
        row.shares = numbers[0]
    if len(numbers) > 1:
        row.avg_price = numbers[1]
    row.market = _guess_market(row.ticker, row.name)
    if not (row.ticker or row.name):
        row.problem = "종목을 못 찾았습니다"
    elif not row.shares:
        row.problem = "수량을 못 찾았습니다"
    return row


def parse(text: str) -> ParseResult:
    """붙여넣은 글을 줄 단위로 읽습니다."""
    cleaned, dropped = strip_account_numbers(str(text or ""))
    result = ParseResult(dropped_account_numbers=dropped)

    lines = [ln for ln in cleaned.splitlines() if ln.strip()]
    cols: dict[str, int] = {}
    for line in lines:
        cells = _cells(line)
        if len(cells) < 2:
            continue
        if not cols:
            found = _header_map(cells)
            if found:
                cols = found
                continue                       # 머리글 줄은 자료가 아닙니다
        row = _from_header(cells, cols, line) if cols else _from_shape(cells, line)
        # 합계 줄("합계", "총계")은 종목이 아닙니다.
        if re.search(r"합\s*계|총\s*계|소\s*계", row.name or ""):
            continue
        result.rows.append(row)
    return result

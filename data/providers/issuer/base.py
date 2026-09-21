"""
data/providers/issuer/base.py  --  운용사별 분배금 provider 의 공통 부분
========================================================================

운용사마다 데이터를 주는 방식이 전부 다릅니다 (JSON API / POST HTML 조각 / SSR HTML).
그래서 **한 파일에 다 몰아넣지 않고** 운용사별 파일로 나눕니다. 한 곳이 바뀌어도
나머지가 멀쩡하도록.

각 provider 가 할 일은 하나입니다.

    fetch(ticker) -> DistributionSeries     (전체 이력. 자르는 건 위층이 함)

찾지 못하면 `DataUnavailable` 을 던집니다. **빈 목록으로 얼버무리지 않습니다** —
"분배 이력이 없다" 와 "못 가져왔다" 는 다른 말이기 때문입니다.
"""

from __future__ import annotations

import abc
import re
from datetime import date, datetime

import requests

import config
from data.providers.base import DataUnavailable
from models.distribution import DistributionSeries


# ---------------------------------------------------------------------
# 하루 호출 한도 — 운용사 서버에 대한 예의
# ---------------------------------------------------------------------
# 왜 필요한가
# -----------
# 캐시는 **모든 접속자가 함께 씁니다.** 그래서 코드 실수로 반복 호출이 생기거나
# 접속이 몰리면, 운용사 한 곳을 짧은 시간에 수백 번 두드리게 됩니다. 실제로
# 개발 중에 삼성자산운용 API 가 한동안 `{"dividList":[],"totalCnt":0}` 만
# 돌려준 적이 있습니다 — HTTP 200 에 정상 JSON 인데 내용만 비어서, **에러도
# 안 나고** 앱이 조용히 폴백으로 내려가 과세표준이 전부 사라졌습니다.
#
# 그래서 남이 우리를 막기 전에 **우리가 먼저 멈춥니다.**
#
# ⚠ 이건 프로세스 안에서만 셉니다. 서버가 재시작되면 0 부터 다시 셉니다.
#    완벽한 한도가 아니라 **폭주를 끊는 안전장치**입니다. 정확한 한도가
#    필요해지면 외부 저장소가 있어야 합니다.
_call_counts: dict[str, int] = {}


def calls_today() -> int:
    """오늘(한국 날짜) 이 프로세스가 운용사 서버를 부른 횟수."""
    return _call_counts.get(config.today_local().isoformat(), 0)


def budget_left() -> int:
    return max(0, config.ISSUER_DAILY_CALL_BUDGET - calls_today())


def reset_calls() -> None:
    """테스트용. 앱에서는 부르지 않습니다."""
    _call_counts.clear()


def _spend_one_call() -> None:
    """한 번 쓰고 셉니다. 한도를 넘으면 아예 부르지 않고 막습니다."""
    key = config.today_local().isoformat()
    used = _call_counts.get(key, 0)
    if used >= config.ISSUER_DAILY_CALL_BUDGET:
        raise DataUnavailable(
            f"오늘 운용사 자료 조회 한도({config.ISSUER_DAILY_CALL_BUDGET}회)를 "
            f"다 썼습니다. 내일 다시 받아옵니다."
        )
    # 날짜가 바뀌면 옛 날짜 칸은 필요 없습니다(메모리에 쌓이지 않게).
    if key not in _call_counts:
        _call_counts.clear()
    _call_counts[key] = used + 1


# ---------------------------------------------------------------------
# 공통 HTTP
# ---------------------------------------------------------------------
def http_get(url: str, *, params: dict | None = None, referer: str = "",
             headers: dict | None = None, timeout: float | None = None) -> requests.Response:
    """공용 GET. 실패는 전부 DataUnavailable 한 종류로 바꿔서 올립니다.

    위층이 폴백을 깔끔하게 하려면 올라오는 예외가 한 종류여야 합니다.
    """
    _spend_one_call()
    h = {"User-Agent": config.HTTP_USER_AGENT, "Accept": "application/json, text/html, */*"}
    if referer:
        h["Referer"] = referer
    if headers:
        h.update(headers)
    try:
        r = requests.get(url, params=params, headers=h,
                         timeout=timeout or config.HTTP_TIMEOUT_SECONDS)
    except requests.RequestException as e:
        raise DataUnavailable(f"자료를 받아오는 중 연결에 실패했습니다: {type(e).__name__}") from e
    if r.status_code != 200:
        raise DataUnavailable(f"자료 서버가 응답하지 않습니다 (HTTP {r.status_code}).")
    return r


def http_post(url: str, *, data: dict, referer: str = "",
              headers: dict | None = None, timeout: float | None = None) -> requests.Response:
    _spend_one_call()
    h = {"User-Agent": config.HTTP_USER_AGENT, "X-Requested-With": "XMLHttpRequest"}
    if referer:
        h["Referer"] = referer
    if headers:
        h.update(headers)
    try:
        r = requests.post(url, data=data, headers=h,
                          timeout=timeout or config.HTTP_TIMEOUT_SECONDS)
    except requests.RequestException as e:
        raise DataUnavailable(f"자료를 받아오는 중 연결에 실패했습니다: {type(e).__name__}") from e
    if r.status_code != 200:
        raise DataUnavailable(f"자료 서버가 응답하지 않습니다 (HTTP {r.status_code}).")
    return r


def json_of(r: requests.Response) -> dict:
    """응답이 JSON 이 아닐 때도 DataUnavailable 로 바꿉니다 (ValueError 가 위로 새지 않게)."""
    try:
        return r.json()
    except ValueError as e:
        raise DataUnavailable("자료 서버가 예상과 다른 형식으로 응답했습니다.") from e


# ---------------------------------------------------------------------
# 파싱 헬퍼
# ---------------------------------------------------------------------
def parse_date(value) -> date | None:
    """'20260915' / '2026-09-15' / '2026.09.15' 를 date 로. 못 읽으면 None."""
    if value is None:
        return None
    s = re.sub(r"[^0-9]", "", str(value))
    if len(s) < 8:
        return None
    try:
        return datetime.strptime(s[:8], "%Y%m%d").date()
    except ValueError:
        return None


def parse_amount(value) -> float | None:
    """'1,234' / '300' / 300.0 을 float 로.

    ⚠ **못 읽으면 None 입니다. 0 이 아닙니다.**
    0 은 "0원이라고 발표했다" 는 뜻이고, None 은 "모른다" 는 뜻입니다.
    이 둘을 섞으면 사용자가 세금 계산을 오해합니다.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace(",", "").replace("원", "")
    if s in ("", "-", "—", "N/A", "null", "None"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def strip_tags(html_text: str) -> str:
    """태그를 지우고 공백을 하나로 줄인 텍스트."""
    import html as _html
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", html_text))).strip()


def code_from_isin(isin: str) -> str | None:
    """'KR7360750004' -> '360750'. ISIN 의 3~8번째 글자가 6자리 단축코드입니다.

    'KR70177R0000' -> '0177R0' 처럼 영문이 섞인 코드도 그대로 나옵니다.
    """
    s = str(isin or "").strip().upper()
    if len(s) < 9 or not s.startswith("KR"):
        return None
    return s[3:9]


def normalize_kr_code(ticker: str) -> str:
    """한국 종목코드를 6자리로. '5930' -> '005930'.

    정수로 다루다 앞의 0 이 날아가는 사고가 흔합니다.
    """
    return str(ticker).strip().upper().zfill(6)


# ---------------------------------------------------------------------
# 인터페이스
# ---------------------------------------------------------------------
class IssuerDistributionProvider(abc.ABC):
    """운용사 한 곳의 분배금/과세표준 제공자."""

    brand: str = ""                 # "KODEX" — 종목명 앞에 붙는 브랜드
    issuer_name: str = ""           # "삼성자산운용"
    home_url: str = ""
    tax_basis_supported: bool = True   # 이 소스가 과세표준을 주는가

    def matches(self, etf_name: str) -> bool:
        """종목명이 이 운용사 상품인가. 기본은 브랜드 이름으로 시작하는지."""
        n = str(etf_name or "").strip().upper()
        return bool(self.brand) and n.startswith(self.brand.upper())

    @abc.abstractmethod
    def fetch(self, ticker: str) -> DistributionSeries:
        """그 종목의 분배 이력 전체. 못 가져오면 DataUnavailable."""

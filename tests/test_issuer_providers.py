"""
운용사 파서 — 네트워크 없이, 실제 응답을 그대로 복사해 넣고 검증합니다.

여기 있는 응답 조각은 **2026-09-20 에 실제로 받은 것**입니다. 운용사 쪽이 구조를
바꾸면 이 테스트가 먼저 깨져서 알려줍니다.

가장 중요한 테스트는 `test_sol_uses_week_pri_not_tax_pri` 입니다.
SOL 은 `TAX_PRI` 가 과세기준가격(9,102원 같은 큰 수)이고 `WEEK_PRI` 가 주당
과세표준액입니다. 잘못 쓰면 **에러 없이 숫자가 45배쯤 틀립니다.**
"""

from __future__ import annotations

import json
from datetime import date

import pytest

from data.providers.base import DataUnavailable
from data.providers.issuer import base as IB
from data.providers.issuer import index as issuer_index
from data.providers.issuer.ace_provider import AceProvider
from data.providers.issuer.html_table_provider import PlusProvider, _find_distribution_table
from data.providers.issuer.kodex_provider import KodexProvider
from data.providers.issuer.rise_provider import RiseProvider
from data.providers.issuer.sol_provider import SolProvider
from data.providers.issuer.tiger_provider import TigerProvider
from data.providers.issuer import tiger_provider as TP


# --------------------------------------------------------------- 파싱 헬퍼
def test_parse_amount_distinguishes_zero_from_unknown():
    """0 은 '발표된 0원', None 은 '모름'. 이걸 섞으면 세금 계산을 오해합니다."""
    assert IB.parse_amount(0) == 0.0
    assert IB.parse_amount("0") == 0.0
    assert IB.parse_amount(None) is None
    assert IB.parse_amount("") is None
    assert IB.parse_amount("-") is None
    assert IB.parse_amount("자료 없음") is None


def test_parse_amount_handles_commas_and_won():
    assert IB.parse_amount("1,234") == 1234.0
    assert IB.parse_amount("19,170원") == 19170.0


def test_parse_date_accepts_every_format_we_saw():
    assert IB.parse_date("20260915") == date(2026, 9, 15)
    assert IB.parse_date("2026-09-15") == date(2026, 9, 15)
    assert IB.parse_date("2026.09.15") == date(2026, 9, 15)
    assert IB.parse_date("2026-05-15 14:22:05") == date(2026, 5, 15)
    assert IB.parse_date("") is None
    assert IB.parse_date(None) is None


def test_code_from_isin_keeps_letters():
    assert IB.code_from_isin("KR7360750004") == "360750"
    assert IB.code_from_isin("KR70177R0000") == "0177R0"   # 영문 섞인 코드
    assert IB.code_from_isin("US0378331005") is None


def test_normalize_kr_code_keeps_leading_zero():
    assert IB.normalize_kr_code("5930") == "005930"
    assert IB.normalize_kr_code("0219e0") == "0219E0"


# --------------------------------------------------------------- KODEX
KODEX_JSON = {
    "totalCnt": 2,
    "dividList": [
        {"stkTicker": "498400", "fNm": "KODEX 200타겟위클리커버드콜",
         "basicD": "20260915", "payD": "20260917",
         "dividA": "300", "taxDividA": "2", "dividY": "1.4468"},
        {"stkTicker": "498400", "fNm": "KODEX 200타겟위클리커버드콜",
         "basicD": "20260615", "payD": "20260617",
         "dividA": "350", "taxDividA": None, "dividY": "1.4383"},
    ],
}


def test_kodex_parses_amount_and_tax_basis(monkeypatch):
    monkeypatch.setattr(IB, "http_get", lambda *a, **k: _Resp(KODEX_JSON))
    monkeypatch.setattr("data.providers.issuer.kodex_provider.http_get",
                        lambda *a, **k: _Resp(KODEX_JSON))
    s = KodexProvider().fetch("498400")
    assert s.tax_basis_supported is True
    first = s.sorted_desc()[0]
    assert first.payment_date == date(2026, 9, 17)
    assert first.record_date == date(2026, 9, 15)
    assert first.distribution_per_share == 300.0
    assert first.tax_basis_per_share == 2.0          # 분배금과 전혀 다른 값
    # 아직 발표 안 된 건은 None 이어야 합니다 (0 이 아니라)
    assert s.sorted_desc()[1].tax_basis_per_share is None


def test_kodex_filters_out_other_tickers(monkeypatch):
    mixed = {"totalCnt": 1, "dividList": [
        {"stkTicker": "999999", "basicD": "20260915", "payD": "20260917",
         "dividA": "300", "taxDividA": "2"}]}
    monkeypatch.setattr("data.providers.issuer.kodex_provider.http_get",
                        lambda *a, **k: _Resp(mixed))
    with pytest.raises(DataUnavailable):
        KodexProvider().fetch("498400")


# --------------------------------------------------------------- TIGER
TIGER_HTML = """
<tr data-tot-cnt="2">
  <td class="text-left"><a href="javascript:cmmCtrl.getEtfDtlPop('KR7360750004','TIGER 미국S&amp;P500');">
     <p class="title">TIGER 미국S&amp;P500</p><p class="code">()</p></a></td>
  <td>해외지수</td><td>2026-01-30</td><td>2026-02-03</td><td>65</td><td>65</td><td>0.26%</td>
</tr>
<tr>
  <td class="text-left"><a href="javascript:cmmCtrl.getEtfDtlPop('KR70177R0000','TIGER 반도체TOP10커버드콜액티브');">
     <p class="title">TIGER 반도체TOP10커버드콜액티브</p></a></td>
  <td>국내주식</td><td>2026-01-15</td><td>2026-01-17</td><td>177</td><td>0</td><td>1.55%</td>
</tr>
"""


def test_tiger_reads_the_table_and_keeps_announced_zero(monkeypatch):
    monkeypatch.setattr("data.providers.issuer.tiger_provider.http_post",
                        lambda *a, **k: _Resp(text=TIGER_HTML))
    table = TP._fetch_month(2026, 1)
    assert set(table) == {"360750", "0177R0"}
    assert table["360750"]["amount"] == "65"
    assert table["0177R0"]["tax_basis"] == "0"       # 발표된 0원


def test_tiger_zero_tax_basis_stays_zero_not_none(monkeypatch):
    monkeypatch.setattr("data.providers.issuer.tiger_provider.http_post",
                        lambda *a, **k: _Resp(text=TIGER_HTML))
    s = TigerProvider().fetch("0177R0")
    assert s.latest().tax_basis_per_share == 0.0
    assert s.latest().has_tax_basis is True


def test_tiger_pages_until_it_has_everything(monkeypatch):
    """listCnt 를 크게 보내도 서버는 20건만 줍니다. 페이징을 안 하면 종목이 조용히 빠집니다."""
    calls = {"n": 0}
    page2 = TIGER_HTML.replace('KR7360750004', 'KR7999999009')

    def fake_post(*a, **k):
        calls["n"] += 1
        # data-tot-cnt 를 4 로 속여서 두 번째 페이지를 요구하게 합니다.
        body = (TIGER_HTML if calls["n"] == 1 else page2).replace(
            'data-tot-cnt="2"', 'data-tot-cnt="4"')
        return _Resp(text=body)

    monkeypatch.setattr("data.providers.issuer.tiger_provider.http_post", fake_post)
    table = TP._fetch_month(2026, 2)
    assert calls["n"] >= 2
    assert "999999" in table


# --------------------------------------------------------------- ACE
ACE_JSON = {
    "dividendList": [
        {"std_DT": "20260430", "dividend_DT": "20260506", "dividend_PRI": 280,
         "tax_PRI": 280, "dividend_RATE": 0.3195},
        {"std_DT": "20250430", "dividend_DT": "20250507", "dividend_PRI": 215,
         "tax_PRI": 197, "dividend_RATE": 1.0469},
    ],
    "page": {"size": 10, "totalElements": 2, "totalPages": 1, "page": 1},
}


def test_ace_parses_tax_pri(monkeypatch):
    monkeypatch.setattr(issuer_index, "fund_id_of", lambda c, b: "K55101DU0363")
    monkeypatch.setattr("data.providers.issuer.ace_provider.http_get",
                        lambda *a, **k: _Resp(ACE_JSON))
    s = AceProvider().fetch("433500")
    rows = s.sorted_desc()
    assert rows[0].distribution_per_share == 280.0 and rows[0].tax_basis_per_share == 280.0
    assert rows[1].distribution_per_share == 215.0 and rows[1].tax_basis_per_share == 197.0


def test_ace_without_mapping_says_so(monkeypatch):
    monkeypatch.setattr(issuer_index, "fund_id_of", lambda c, b: None)
    with pytest.raises(DataUnavailable) as e:
        AceProvider().fetch("433500")
    assert "펀드코드" in str(e.value)


# --------------------------------------------------------------- RISE
RISE_JSON = {
    "fund_cd": "4435", "name": "RISE 200",
    "history": [
        {"base_date": "2026-07-31", "payment_date": "2026-08-04", "amount": 120.0,
         "tax_standard_amount": 120.0, "dividend_ratio": 0.13},
    ],
}


def test_rise_parses_tax_standard_amount(monkeypatch):
    monkeypatch.setattr(issuer_index, "fund_id_of", lambda c, b: "4435")
    monkeypatch.setattr("data.providers.issuer.rise_provider.http_get",
                        lambda *a, **k: _Resp(RISE_JSON))
    s = RiseProvider().fetch("252400")
    d = s.latest()
    assert d.payment_date == date(2026, 8, 4) and d.record_date == date(2026, 7, 31)
    assert d.tax_basis_per_share == 120.0


# --------------------------------------------------------------- SOL (⚠ 핵심)
SOL_JSON = {
    "workDt": "20260831", "fundName": "SOL 미국30년국채커버드콜(합성)", "totalCount": 3,
    "items": [
        # 화면 표에서 확인한 값: 분배금 60 / 주당과세표준액 0
        {"WORK_DT": "20260831", "DIVIDEND_DT": "20260901", "DIVIDEND_PRI": 60,
         "WEEK_PRI": 0, "TAX_PRI": 9102.27, "BFAS_STAS_STPR": 9204.01},
        # 분배금 85 / 주당과세표준액 85
        {"WORK_DT": "20260630", "DIVIDEND_DT": "20260701", "DIVIDEND_PRI": 85,
         "WEEK_PRI": 85, "TAX_PRI": 10567.93, "BFAS_STAS_STPR": 10525.83},
        # 분배금 75 / 주당과세표준액 11
        {"WORK_DT": "20260130", "DIVIDEND_DT": "20260202", "DIVIDEND_PRI": 75,
         "WEEK_PRI": 11, "TAX_PRI": 10087.54, "BFAS_STAS_STPR": 10050.00},
    ],
}


def test_sol_uses_week_pri_not_tax_pri(monkeypatch):
    """⚠ TAX_PRI 는 과세기준가격(9,102원)입니다. 이걸 쓰면 숫자가 45배 틀립니다."""
    monkeypatch.setattr(issuer_index, "fund_id_of", lambda c, b: "211044")
    monkeypatch.setattr("data.providers.issuer.sol_provider.http_get",
                        lambda *a, **k: _Resp(SOL_JSON))
    rows = SolProvider().fetch("473330").sorted_desc()
    assert [r.distribution_per_share for r in rows] == [60.0, 85.0, 75.0]
    assert [r.tax_basis_per_share for r in rows] == [0.0, 85.0, 11.0]
    # 과세표준이 분배금보다 클 수 없는 상품인데, TAX_PRI 를 썼다면 여기서 걸립니다.
    assert all(r.tax_basis_per_share <= r.distribution_per_share for r in rows)


# --------------------------------------------------------------- PLUS / TIME
PLUS_HTML = """
<html><body>
<table><tr><th>일자</th><th>종가</th></tr><tr><td>2026.09.18</td><td>10,360</td></tr></table>
<table>
 <tr><th>지급 기준일</th><th>실 지급일</th><th>분배금 (원)</th><th>주당과세표준액 (원)</th></tr>
 <tr><td>2026.08.31</td><td>2026.09.02</td><td>103</td><td>103</td></tr>
 <tr><td>2026.02.27</td><td>2026.03.04</td><td>86</td><td>44</td></tr>
</table>
</body></html>
"""


def test_html_table_picks_the_one_with_tax_basis_header():
    """표 순서나 클래스에 기대면 그쪽이 바뀔 때 조용히 엉뚱한 표를 읽습니다."""
    rows = _find_distribution_table(PLUS_HTML)
    assert rows is not None
    assert "주당과세표준액 (원)" in rows[0]
    assert rows[1] == ["2026.08.31", "2026.09.02", "103", "103"]


def test_plus_parses_rows(monkeypatch):
    monkeypatch.setattr(issuer_index, "fund_id_of", lambda c, b: "006273")
    monkeypatch.setattr("data.providers.issuer.html_table_provider.http_get",
                        lambda *a, **k: _Resp(text=PLUS_HTML))
    rows = PlusProvider().fetch("161510").sorted_desc()
    assert rows[0].payment_date == date(2026, 9, 2)
    assert rows[0].distribution_per_share == 103.0
    assert rows[1].tax_basis_per_share == 44.0        # 분배금 86 과 다릅니다


def test_html_table_with_no_rows_is_not_an_error(monkeypatch):
    """아직 지급 이력이 없는 신규 ETF 는 '못 가져온 것'과 다릅니다."""
    empty = PLUS_HTML.split("<tr><td>2026.08.31")[0] + "</table></body></html>"
    monkeypatch.setattr(issuer_index, "fund_id_of", lambda c, b: "006410")
    monkeypatch.setattr("data.providers.issuer.html_table_provider.http_get",
                        lambda *a, **k: _Resp(text=empty))
    s = PlusProvider().fetch("161510")
    assert len(s) == 0 and s.tax_basis_supported is True


def test_missing_table_is_an_error(monkeypatch):
    monkeypatch.setattr(issuer_index, "fund_id_of", lambda c, b: "006410")
    monkeypatch.setattr("data.providers.issuer.html_table_provider.http_get",
                        lambda *a, **k: _Resp(text="<html><body>없음</body></html>"))
    with pytest.raises(DataUnavailable):
        PlusProvider().fetch("161510")


# --------------------------------------------------------------- 매핑 시드
def test_issuer_index_seed_covers_the_big_seven():
    """저장소의 시드 CSV 가 비면 ACE/RISE/SOL/PLUS/TIME 이 통째로 폴백으로 내려갑니다."""
    rows = issuer_index.all_rows()
    assert len(rows) > 300
    brands = {r.brand for r in rows.values()}
    assert {"KODEX", "TIGER", "ACE", "RISE", "SOL", "PLUS", "TIME"} <= brands


def test_issuer_index_lookup_is_case_and_padding_safe():
    assert issuer_index.lookup("069500") is not None
    assert issuer_index.fund_id_of("069500", "ACE") is None    # 브랜드가 다르면 안 줍니다


# --------------------------------------------------------------- 가짜 응답
class _Resp:
    """requests.Response 흉내. json() 과 .text 만 쓰면 충분합니다."""

    def __init__(self, payload=None, text: str = ""):
        self._payload = payload
        self.status_code = 200
        self.text = text if text else json.dumps(payload or {}, ensure_ascii=False)

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


# --------------------------------------------------- 열 순서가 바뀌어도 (회귀 방지)
REORDERED_HTML = """
<table>
 <tr><th>분배금 지급 기준일</th><th>분배금 지급일</th><th>주당분배금</th>
     <th>분배율(%)</th><th>주당과세표준액</th></tr>
 <tr><td>2026.08.31</td><td>2026.09.02</td><td>103</td><td>1.55%</td><td>7</td></tr>
</table>
"""


def test_columns_are_found_by_header_name_not_position(monkeypatch):
    """⚠ 열 위치를 숫자로 박아두면, 운용사가 열을 하나 끼워 넣는 순간
    **에러 없이 분배율을 과세표준으로 읽습니다.** 그래서 이름으로 찾습니다."""
    monkeypatch.setattr(issuer_index, "fund_id_of", lambda c, b: "X")
    monkeypatch.setattr("data.providers.issuer.html_table_provider.http_get",
                        lambda *a, **k: _Resp(text=REORDERED_HTML))
    d = PlusProvider().fetch("161510").latest()
    assert d.distribution_per_share == 103.0
    assert d.tax_basis_per_share == 7.0        # 1.55(분배율)를 읽으면 실패합니다


def test_unreadable_header_refuses_instead_of_guessing(monkeypatch):
    weird = ("<table><tr><th>가</th><th>나</th><th>다</th><th>주당과세표준액</th></tr>"
             "<tr><td>1</td><td>2</td><td>3</td><td>4</td></tr></table>")
    monkeypatch.setattr(issuer_index, "fund_id_of", lambda c, b: "X")
    monkeypatch.setattr("data.providers.issuer.html_table_provider.http_get",
                        lambda *a, **k: _Resp(text=weird))
    with pytest.raises(DataUnavailable):
        PlusProvider().fetch("161510")

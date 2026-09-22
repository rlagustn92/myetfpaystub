"""
붙여넣기로 가져오기 — 진입장벽을 낮추는 기능.

왜 이 테스트가 있나
-------------------
이 앱의 가장 큰 진입장벽은 **일일이 입력하는 것**입니다. 증권사 세 곳에
종목이 열 개면 쉰 번을 타이핑해야 하고 거기서 대부분 그만둡니다.

증권사마다 열 이름도 순서도 다릅니다. 그래서 잘못 읽으면 **수량과 단가가
바뀌어** 자산이 엉뚱하게 나오는데, 에러가 안 나서 눈으로 볼 때까지 모릅니다.
그리고 증권사 화면을 긁으면 **계좌번호가 딸려옵니다** — 이 앱이 절대 안 받는
정보(절대규칙 6)라 읽는 단계에서 버려야 합니다.
"""

from __future__ import annotations

import pytest

from models.portfolio import MARKET_KR, MARKET_US
from services import import_service as IMP


# ------------------------------------------------- 개인정보를 안 받는가
@pytest.mark.parametrize("account_no", [
    "123-45-678901", "12345678901", "270-01-234567", "50412345678",
])
def test_account_numbers_are_dropped_before_anything_else(account_no):
    """절대규칙 6 — 계좌번호는 입력칸조차 만들지 않습니다.
    붙여넣기로 딸려 들어오는 것도 같은 규칙입니다."""
    text = f"KODEX 200\t069500\t{account_no}\t100\t32000"
    cleaned, dropped = IMP.strip_account_numbers(text)
    assert account_no not in cleaned
    assert dropped == 1

    got = IMP.parse(text)
    assert got.dropped_account_numbers == 1
    blob = " ".join(r.raw for r in got.rows)
    assert account_no not in blob        # 화면에 올라가는 raw 에도 없어야 합니다


def test_a_short_number_is_not_mistaken_for_an_account_number():
    """수량 100 이나 단가 32000 을 계좌번호로 오해하면 자료가 사라집니다."""
    cleaned, dropped = IMP.strip_account_numbers("KODEX 200 069500 100 32000")
    assert dropped == 0
    assert "32000" in cleaned


# ------------------------------------------------- 머리글이 있는 표
def test_reads_a_table_with_headers_in_any_column_order():
    text = """종목명\t보유수량\t매입평균단가\t종목코드
KODEX 200\t100\t32,000\t069500
TIGER 미국배당다우존스\t50\t11,200\t458730"""
    got = IMP.parse(text)
    assert len(got.good) == 2
    a, b = got.good
    assert (a.ticker, a.shares, a.avg_price) == ("069500", 100.0, 32000.0)
    assert b.name == "TIGER 미국배당다우존스"
    assert b.shares == 50.0 and b.avg_price == 11200.0


@pytest.mark.parametrize("header", ["수량", "잔고수량", "보유수량", "주식수"])
def test_brokers_call_quantity_different_things(header):
    got = IMP.parse(f"종목코드,{header},평균단가\n069500,100,32000")
    assert got.good[0].shares == 100.0


@pytest.mark.parametrize("header", ["평균단가", "매입단가", "평단가", "취득단가",
                                    "매입평균단가"])
def test_brokers_call_the_average_price_different_things(header):
    got = IMP.parse(f"종목코드,수량,{header}\n069500,100,32000")
    assert got.good[0].avg_price == 32000.0


def test_the_header_row_itself_is_not_a_holding():
    got = IMP.parse("종목코드,수량,평균단가\n069500,100,32000")
    assert len(got.rows) == 1


def test_a_total_row_is_skipped():
    """증권사 화면 맨 아래 "합계" 줄이 종목으로 들어가면 안 됩니다."""
    text = "종목명,수량,평균단가\nKODEX 200,100,32000\n합계,100,-"
    got = IMP.parse(text)
    assert [r.name for r in got.rows] == ["KODEX 200"]


# ------------------------------------------------- 머리글이 없는 경우
def test_reads_a_plain_paste_without_headers():
    text = """KODEX 200          069500    100주    32,000원
TIGER 미국배당다우존스   458730    50주     11,200원"""
    got = IMP.parse(text)
    assert len(got.good) == 2
    assert got.good[0].ticker == "069500"
    assert got.good[0].shares == 100.0
    assert got.good[0].avg_price == 32000.0


def test_quantity_comes_before_price_when_there_are_no_headers():
    """⭐ 둘을 바꿔 읽으면 자산이 엉뚱하게 나오는데 **에러가 안 납니다.**
    "작은 쪽이 수량" 으로 단정하면 5,000주 x 10원 에서 틀립니다.
    증권사 화면이 수량을 먼저 보여주므로 **나온 순서**를 그대로 씁니다."""
    got = IMP.parse("KODEX 200 069500 5000 10")
    assert got.good[0].shares == 5000.0
    assert got.good[0].avg_price == 10.0


# ------------------------------------------------- 한국 / 미국
def test_korean_codes_keep_their_leading_zero_and_letters():
    got = IMP.parse("종목코드,수량,평균단가\n0219E0,10,9000")
    assert got.good[0].ticker == "0219E0"     # 영문 섞인 실제 코드
    assert got.good[0].market == MARKET_KR


def test_us_tickers_are_recognised():
    got = IMP.parse("종목코드,수량,평균단가\nSCHD,180,30.5")
    assert got.good[0].ticker == "SCHD"
    assert got.good[0].market == MARKET_US
    assert got.good[0].avg_price == 30.5      # 소수점이 살아야 합니다


# ------------------------------------------------- 못 읽은 줄
def test_a_line_we_cannot_read_says_why_instead_of_guessing():
    """절대규칙 1 — 반쯤 읽은 줄을 0 으로 채우지 않습니다."""
    got = IMP.parse("종목명,수량,평균단가\nKODEX 200,,32000")
    assert not got.good
    assert got.bad and "수량" in got.bad[0].problem


def test_empty_input_is_simply_empty():
    assert IMP.parse("").rows == []
    assert IMP.parse("   \n  \n").rows == []


def test_money_symbols_and_commas_do_not_break_numbers():
    """금액에 천 단위 쉼표가 든 채로 옵니다. 그냥 쪼개면 한 칸이 두 칸이 되어
    그 뒤 열이 전부 밀립니다. **따옴표 안의 쉼표는 안 쪼갭니다.**"""
    got = IMP.parse('종목코드,수량,평균단가\n069500,"1,000","₩32,000"')
    assert got.good[0].shares == 1000.0
    assert got.good[0].avg_price == 32000.0


def test_a_tab_pasted_table_keeps_commas_inside_cells():
    """엑셀에서 긁으면 탭으로 옵니다 — 이때는 쉼표가 그냥 글자입니다."""
    got = IMP.parse("종목코드\t수량\t평균단가\n069500\t1,000\t32,000")
    assert got.good[0].shares == 1000.0
    assert got.good[0].avg_price == 32000.0



def test_the_example_on_screen_actually_parses():
    """화면에 보여 주는 예시는 **실제로 읽혀야 합니다.**

    예시가 파서와 어긋나면 사용자는 "시키는 대로 했는데 안 된다" 를 겪습니다.
    머리글 줄을 넣은 것도 사용자 지적이었습니다 — 숫자만 늘어놓으면
    100 이 수량인지 32,000 이 총액인지 알 수가 없어서입니다.
    """
    import app

    got = IMP.parse(app.PASTE_EXAMPLE)
    assert not got.bad, [r.problem for r in got.bad]
    assert len(got.good) == 2          # 머리글 줄은 종목이 아닙니다

    kodex, tiger = got.good
    assert (kodex.ticker, kodex.shares, kodex.avg_price) == ("069500", 100.0, 32000.0)
    assert kodex.name == "KODEX 200"
    assert kodex.market == MARKET_KR
    assert (tiger.ticker, tiger.shares, tiger.avg_price) == ("458730", 50.0, 11200.0)

"""저장/불러오기 — 왕복, 잘못된 파일, 빠진 필드, 포트폴리오 여러 개."""

from __future__ import annotations

from conftest import kr, us

from models.portfolio import Holding, Portfolio
from services import storage_service as STORE


def sample() -> STORE.Store:
    s = STORE.new_store()
    p = s.active()
    p.add(kr(shares=100, avg=30000))
    p.add(us(shares=10, avg=70.0))
    return s


def test_round_trip_keeps_everything():
    s = sample()
    back, err = STORE.loads(STORE.dumps(s))
    assert err == "" and back is not None
    assert back.current == s.current
    got = back.active()
    assert [h.ticker for h in got.holdings] == ["069500", "SCHD"]
    assert got.holdings[0].shares == 100 and got.holdings[1].avg_price == 70.0
    assert got.holdings[0].broker == "미래에셋증권"


def test_bad_json_does_not_raise():
    back, err = STORE.loads("{이건 JSON 이 아님")
    assert back is None and "JSON" in err


def test_empty_text_is_reported_not_crashed():
    back, err = STORE.loads("")
    assert back is None and err


def test_other_apps_file_is_refused():
    back, err = STORE.loads('{"schema": "etf_manager_2027", "holdings": []}')
    assert back is None and "저장한 파일이 아닌" in err


def test_missing_fields_fall_back_to_defaults():
    back, err = STORE.loads('{"schema": "my_etf_paystub"}')
    assert err == "" and back is not None
    assert back.names() == [STORE.DEFAULT_PROFILE]
    assert back.active().holdings == []


def test_old_single_portfolio_format_is_accepted():
    text = '{"schema": "my_etf_paystub", "name": "옛날거", ' \
           '"holdings": [{"ticker": "069500", "market": "KR", "shares": 5}]}'
    back, err = STORE.loads(text)
    assert err == "" and back.names() == ["옛날거"]
    assert back.active().holdings[0].shares == 5


def test_broken_row_inside_a_good_file_is_skipped():
    text = ('{"schema": "my_etf_paystub", "profiles": {"A": {"holdings": ['
            '{"ticker": "069500", "market": "KR", "shares": 1}, {}, '
            '{"ticker": "SCHD", "market": "US", "shares": 2}]}}}')
    back, err = STORE.loads(text)
    assert err == ""
    assert [h.ticker for h in back.active().holdings] == ["069500", "SCHD"]


# ------------------------------------------------------------ 여러 개 두기
def test_create_does_not_overwrite_an_existing_name():
    s = STORE.new_store()
    first = s.current
    made = s.create(first)
    assert made != first and made.startswith(first)
    assert len(s.names()) == 2


def test_rename_keeps_order_and_moves_current():
    s = STORE.new_store()
    s.create("두번째")
    s.current = STORE.DEFAULT_PROFILE
    s.rename(STORE.DEFAULT_PROFILE, "첫번째")
    assert s.names() == ["첫번째", "두번째"]
    assert s.current == "첫번째"
    assert s.profiles["첫번째"].name == "첫번째"


def test_rename_refuses_to_clobber():
    s = STORE.new_store()
    s.create("두번째")
    assert s.rename("두번째", STORE.DEFAULT_PROFILE) == "두번째"
    assert len(s.names()) == 2


def test_last_profile_cannot_be_deleted():
    """화면이 텅 비면 사용자가 당황합니다."""
    s = STORE.new_store()
    s.delete(s.current)
    assert len(s.names()) == 1


def test_delete_moves_current():
    s = STORE.new_store()
    s.create("두번째")
    s.delete("두번째")
    assert s.current in s.names()


def test_duplicate_copies_holdings_without_sharing_them():
    s = sample()
    src = s.current
    new = s.duplicate(src)
    assert new != src
    assert len(s.profiles[new].holdings) == 2
    s.profiles[new].holdings[0].shares = 999
    assert s.profiles[src].holdings[0].shares == 100      # 원본이 안 바뀜


def test_active_repairs_a_dangling_current():
    s = STORE.Store(profiles={"A": Portfolio(name="A")}, current="없는거")
    assert s.active().name == "A" and s.current == "A"


def test_active_creates_one_when_empty():
    s = STORE.Store()
    assert s.active() is not None
    assert s.names() == [STORE.DEFAULT_PROFILE]


def test_count_holdings_across_profiles():
    s = sample()
    s.duplicate(s.current)
    assert STORE.count_holdings(s) == 4


# =========================================== 남의 파일로 내 자료를 날리지 않기
def test_a_foreign_json_file_is_refused_instead_of_wiping_everything():
    """⭐ 데이터 손실 버그였습니다.

    예전에는 `schema` 키가 **없으면** 그냥 통과시켰습니다. 그래서 아무 JSON
    (`{"nope":1}`, `[]`, 다른 앱의 내보내기)이나 넣어도 "성공" 으로 받고
    **빈 포트폴리오**를 돌려줬습니다. 화면 맨 아래에서 그 빈 내용이 브라우저
    저장소에 덮여 쓰이므로, 파일 하나 잘못 열면 등록해 둔 ETF 가 **전부
    조용히 사라집니다.**
    """
    for foreign in ['{"nope":1}', "[]", '{"a":{"b":[1,2]}}', "123", '"hello"']:
        got, err = STORE.loads(foreign)
        assert got is None, f"{foreign} 을(를) 받아들였습니다 — 자료가 날아갑니다"
        assert err, "왜 못 읽었는지 말해 줘야 합니다"


def test_our_own_file_still_loads():
    """막느라 정작 우리 파일을 못 읽으면 안 됩니다."""
    st = STORE.new_store()
    p = st.active()
    p.add(Holding(ticker="069500", market="KR", name="KODEX 200",
                  broker="증권사", account="일반", account_type="일반",
                  shares=100, avg_price=32000))
    got, err = STORE.loads(STORE.dumps(st))
    assert err == "" and got is not None
    assert len(got.active().holdings) == 1


def test_an_older_save_without_a_schema_key_still_loads():
    """옛 저장본에는 `schema` 가 없을 수 있습니다. 그것까지 막으면 안 됩니다."""
    import json

    d = json.loads(STORE.dumps(STORE.new_store()))
    d.pop("schema", None)
    got, err = STORE.loads(json.dumps(d))
    assert got is not None, err

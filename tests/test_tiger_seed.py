"""
TIGER 월별 시드 — 지나간 달을 다시 안 받는가.

왜 이 테스트가 있나
-------------------
TIGER 는 **달마다 따로** 불러야 개별 지급 건을 줍니다. 그래서 종목 하나에
HTTP 43번이 나갔습니다(받는 자료는 4건인데). 캐시는 서버 **메모리**에만 있어서
재시작하면 날아가고, 무료 호스팅은 접속이 없으면 앱을 재웁니다 —
**깨어날 때마다 43번**이었습니다.

그래서 지나간 달을 `data/tiger_months.csv` 로 굳혀 저장소에 넣습니다.
실측: 캐시가 완전히 빈 상태(= 서버 재시작 직후)에서 43회 -> 1회.

여기서 지키는 것은 **"언제 파일을 쓰고 언제 받아오는가"** 입니다. 잘못되면
에러 없이 조용히 틀립니다 — 다 받아오거나(느려짐), 낡은 값을 최종본으로
믿거나(과세표준이 영영 안 채워짐).
"""

from __future__ import annotations

from datetime import date

import pytest

import config
from data.providers import cache
from data.providers.issuer import tiger_provider as tp
from data.providers.issuer import tiger_seed

FULL = {"name": "TIGER 아무거나", "record_date": "2026.07.31",
        "payment_date": "2026.08.04", "amount": "100", "tax_basis": "80"}
PENDING = {**FULL, "tax_basis": ""}          # 과세표준이 아직 안 나온 건


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    cache.invalidate()
    monkeypatch.setattr(config, "today_local", lambda: date(2026, 9, 21))
    yield
    cache.invalidate()


def _no_network(monkeypatch):
    """네트워크를 타면 바로 실패하게 만듭니다."""
    def boom(*a, **k):
        raise AssertionError("파일에 있는 달인데 네트워크를 탔습니다")
    monkeypatch.setattr(tp, "_fetch_month_live", boom)
    return boom


# --------------------------------------------- 파일을 쓰는가
def test_a_finished_month_in_the_file_never_hits_the_network(monkeypatch):
    monkeypatch.setattr(tiger_seed, "month_rows",
                        lambda y, m: {"360750": FULL} if (y, m) == (2026, 8) else None)
    _no_network(monkeypatch)
    assert tp._fetch_month(2026, 8) == {"360750": FULL}


def test_a_month_with_no_payouts_is_still_worth_remembering(monkeypatch):
    """`None`(파일에 없음)과 `{}`(그 달엔 지급이 없었음)은 다른 뜻입니다.
    빈 dict 를 '없음' 으로 다루면 지급이 없던 달을 매번 다시 받아옵니다."""
    monkeypatch.setattr(tiger_seed, "month_rows",
                        lambda y, m: {} if (y, m) == (2026, 7) else None)
    _no_network(monkeypatch)
    assert tp._fetch_month(2026, 7) == {}


# --------------------------------------------- 받아와야 하는 경우
def test_the_current_month_is_always_fetched(monkeypatch):
    """이번 달은 지급이 더 붙을 수 있습니다. 파일에 있어도 믿으면 안 됩니다."""
    monkeypatch.setattr(tiger_seed, "month_rows", lambda y, m: {"360750": FULL})
    called = []
    monkeypatch.setattr(tp, "_fetch_month_live",
                        lambda y, m: called.append((y, m)) or {"360750": FULL})
    tp._fetch_month(2026, 9)
    assert called == [(2026, 9)]


def test_a_month_with_a_missing_tax_basis_is_refetched(monkeypatch):
    """과세표준은 나중에 채워지는 일이 있습니다(실측: 2026-05·06 이 몇 달째
    빈 칸). 빈 칸이 남은 달을 최종본으로 믿으면 영영 못 봅니다."""
    monkeypatch.setattr(tiger_seed, "month_rows", lambda y, m: {"360750": PENDING})
    called = []
    monkeypatch.setattr(tp, "_fetch_month_live",
                        lambda y, m: called.append((y, m)) or {"360750": FULL})
    tp._fetch_month(2026, 8)
    assert called == [(2026, 8)]


def test_a_month_missing_from_the_file_is_fetched(monkeypatch):
    monkeypatch.setattr(tiger_seed, "month_rows", lambda y, m: None)
    called = []
    monkeypatch.setattr(tp, "_fetch_month_live",
                        lambda y, m: called.append((y, m)) or {})
    tp._fetch_month(2024, 1)
    assert called == [(2024, 1)]


# --------------------------------------------- 규칙이 한 곳인가
def test_the_file_rule_and_the_cache_rule_are_the_same():
    """파일을 쓸지 정하는 규칙과 캐시를 오래 둘지 정하는 규칙이 어긋나면,
    아직 채워지는 중인 달을 영영 안 받아오게 됩니다."""
    for rows in ({"x": FULL}, {"x": PENDING}, {}):
        for ym in ((2026, 8), (2026, 9), (2025, 1)):
            settled = tp._month_is_settled(*ym, rows)
            long_ttl = (tp._month_ttl(*ym, rows)
                        == config.CACHE_TTL_DISTRIBUTION_FINAL_SECONDS)
            assert settled is long_ttl, f"{ym} {rows} 에서 두 규칙이 다릅니다"


# --------------------------------------------- 파일이 없거나 깨져도
def test_a_missing_file_just_means_everything_is_fetched(monkeypatch):
    monkeypatch.setattr(tiger_seed, "CSV_PATH", "없는파일.csv")
    assert tiger_seed._load() == {}
    assert tiger_seed.month_rows(2026, 8) is None


def test_a_broken_file_does_not_crash_the_app(tmp_path, monkeypatch):
    bad = tmp_path / "tiger_months.csv"
    bad.write_text("year,month,code\n이건,숫자가,아님\n", encoding="utf-8")
    monkeypatch.setattr(tiger_seed, "CSV_PATH", str(bad))
    assert tiger_seed._load() == {}


# --------------------------------------------- 실제 파일
def test_the_committed_file_is_real_and_usable():
    """저장소에 든 파일이 실제로 읽히는지. 배포본이 이걸 그대로 씁니다."""
    st = tiger_seed.stats()
    assert st["exists"], "data/tiger_months.csv 가 없습니다 — 커밋됐나요?"
    assert st["months"] >= 12, f"굳혀 둔 달이 너무 적습니다: {st}"
    assert st["rows"] >= 300, f"줄이 너무 적습니다: {st}"


def test_the_file_never_holds_an_unfinished_month():
    """아직 안 끝난 달이 파일에 들어가면, 앱이 그걸 최종본으로 믿고 나중에
    발표된 과세표준을 영영 못 봅니다. 빌더가 걸러야 합니다."""
    today = config.today_local()
    for (y, m), rows in tiger_seed._load().items():
        assert (y, m) < (today.year, today.month), f"{y}-{m:02d} 은 아직 이번 달입니다"
        blank = [c for c, r in rows.items() if not str(r.get("tax_basis") or "").strip()]
        assert not blank, f"{y}-{m:02d} 에 과세표준 빈 칸이 있습니다: {blank[:3]}"

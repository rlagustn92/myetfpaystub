"""
운용사 서버에 대한 예의 — 관리자 가림막 + 하루 호출 한도.

왜 이 테스트가 있나
-------------------
캐시는 **모든 접속자가 함께 씁니다.** 그래서 '🔄 정보 업데이트' 한 번이 모든
종목을 다시 받아오게 만들고, 여러 명이 번갈아 누르면 운용사 서버가 우리를
막습니다. 개발 중 실제로 삼성자산운용 API 가 한동안
`{"dividList":[],"totalCnt":0}` 만 돌려줬습니다 — **HTTP 200 에 정상 JSON 이라
에러도 안 나고** 앱이 조용히 폴백으로 내려가 과세표준이 전부 사라집니다.
눈으로 볼 때까지 모르는 종류의 사고라, 막는 장치를 테스트로 지킵니다.
"""

from __future__ import annotations

import pytest

import config
from data.providers.base import DataUnavailable
from data.providers.issuer import base as ib


@pytest.fixture(autouse=True)
def clean_budget():
    ib.reset_calls()
    yield
    ib.reset_calls()


# ------------------------------------------------------- 하루 호출 한도
def test_budget_starts_full_and_counts_down(monkeypatch):
    assert ib.calls_today() == 0
    assert ib.budget_left() == config.ISSUER_DAILY_CALL_BUDGET
    ib._spend_one_call()
    ib._spend_one_call()
    assert ib.calls_today() == 2
    assert ib.budget_left() == config.ISSUER_DAILY_CALL_BUDGET - 2


def test_going_over_the_budget_stops_us_before_we_call(monkeypatch):
    """한도를 넘으면 **요청을 보내지 않고** 막아야 합니다. 보내고 나서 세면
    이미 늦습니다."""
    monkeypatch.setattr(config, "ISSUER_DAILY_CALL_BUDGET", 3)
    for _ in range(3):
        ib._spend_one_call()
    with pytest.raises(DataUnavailable) as e:
        ib._spend_one_call()
    assert "한도" in str(e.value)


def test_http_get_is_blocked_once_the_budget_is_gone(monkeypatch):
    """폴백이 깔끔하려면 올라오는 예외가 DataUnavailable 한 종류여야 합니다."""
    monkeypatch.setattr(config, "ISSUER_DAILY_CALL_BUDGET", 0)

    def boom(*a, **k):                      # 네트워크를 타면 안 됩니다
        raise AssertionError("한도를 넘었는데 실제로 요청을 보냈습니다")

    monkeypatch.setattr(ib.requests, "get", boom)
    monkeypatch.setattr(ib.requests, "post", boom)
    with pytest.raises(DataUnavailable):
        ib.http_get("https://example.com/x")
    with pytest.raises(DataUnavailable):
        ib.http_post("https://example.com/x", data={})


def test_http_get_spends_exactly_one_call(monkeypatch):
    class OK:
        status_code = 200

    monkeypatch.setattr(ib.requests, "get", lambda *a, **k: OK())
    ib.http_get("https://example.com/x")
    assert ib.calls_today() == 1


def test_the_counter_does_not_pile_up_day_after_day(monkeypatch):
    """날짜가 바뀌면 옛 날짜 칸은 필요 없습니다. 안 비우면 프로세스가 오래
    살아 있을수록 메모리에 쌓입니다."""
    from datetime import date

    monkeypatch.setattr(config, "today_local", lambda: date(2026, 9, 21))
    ib._spend_one_call()
    monkeypatch.setattr(config, "today_local", lambda: date(2026, 9, 22))
    ib._spend_one_call()
    assert ib.calls_today() == 1
    assert len(ib._call_counts) == 1


# ------------------------------------------------------- 관리자 가림막
def test_refresh_button_is_hidden_from_visitors(monkeypatch):
    """키를 설정했으면 주소에 맞는 키를 붙인 사람만 새로고침할 수 있습니다."""
    import app as app_module

    class FakeSecrets(dict):
        def get(self, k, default=None):
            return super().get(k, default)

    monkeypatch.setattr(app_module.st, "secrets", FakeSecrets({"ADMIN_KEY": "열려라참깨"}))

    monkeypatch.setattr(app_module.st, "query_params", {})
    assert app_module.is_admin() is False

    monkeypatch.setattr(app_module.st, "query_params", {"admin": "틀린키"})
    assert app_module.is_admin() is False

    monkeypatch.setattr(app_module.st, "query_params", {"admin": "열려라참깨"})
    assert app_module.is_admin() is True


def test_without_a_key_everything_is_open(monkeypatch):
    """개인 PC 에서 혼자 쓸 때는 키가 없습니다. 그때 막아버리면 나도 못 씁니다."""
    import app as app_module

    monkeypatch.setattr(app_module.st, "secrets", {})
    monkeypatch.setattr(app_module.st, "query_params", {})
    assert app_module.is_admin() is True


def test_admin_key_is_never_written_in_the_repo():
    """저장소가 **공개**라 코드에 키를 적으면 그대로 노출됩니다.

    ⚠ 문서(.md)는 검사하지 않습니다 — DEPLOY.md 에 `ADMIN_KEY = "..."` 라는
      **예시**를 적어야 하기 때문입니다. 진짜 키가 들어갈 자리는 코드(.py)와
      설정(.toml)뿐이고, 실제 키가 담기는 `.streamlit/secrets.toml` 은
      `.gitignore` 로 막혀 있습니다(아래 테스트가 확인합니다).
    """
    import os
    import re

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bad = []
    for folder, _, files in os.walk(root):
        if any(part in folder for part in
               (".git", "__pycache__", ".pytest_cache", ".venv")):
            continue
        for name in files:
            if not name.endswith((".py", ".toml")):
                continue
            if name == "test_admin_and_budget.py":
                continue                      # 이 테스트 자신의 가짜 키
            path = os.path.join(folder, name)
            with open(path, encoding="utf-8", errors="ignore") as f:
                text = f.read()
            if re.search(r"ADMIN_KEY\s*[=:]\s*['\"][^'\"]+['\"]", text):
                bad.append(os.path.relpath(path, root))
    assert not bad, f"관리자 키가 저장소에 적혀 있습니다: {bad}"


def test_the_secrets_file_is_never_committed():
    """진짜 키가 담기는 파일입니다. 올라가면 키도 카운터 이름도 같이 샙니다."""
    import os
    import subprocess

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, ".gitignore"), encoding="utf-8") as f:
        assert ".streamlit/secrets.toml" in f.read()

    tracked = subprocess.run(["git", "ls-files"], cwd=root,
                             capture_output=True, text=True).stdout
    assert "secrets.toml" not in tracked


# ------------------------------------- 끝난 달은 다시 안 받는다
def test_finished_months_are_kept_much_longer(monkeypatch):
    """지나간 달의 분배금은 다시 안 바뀝니다. 그런데 TTL 이 하나뿐이면 몇 년
    전 자료까지 하루마다 다시 받아옵니다 — TIGER 는 달마다 따로 불러야 해서
    한 종목에 HTTP 43번이 나갔습니다(자료는 4건인데).

    실측: 이 구분을 넣고 나서 하루 뒤 재조회가 43회 -> 1회가 됐습니다.
    """
    from datetime import date

    from data.providers.issuer import tiger_provider as tp

    monkeypatch.setattr(config, "today_local", lambda: date(2026, 9, 21))

    done = {"069500": {"tax_basis": "168"}}          # 과세표준이 다 있는 달
    pending = {"069500": {"tax_basis": ""}}          # 아직 안 채워진 건이 있는 달

    # 지나갔고 + 값이 다 있으면 오래 둡니다
    assert tp._month_ttl(2026, 8, done) == config.CACHE_TTL_DISTRIBUTION_FINAL_SECONDS
    # 지나갔어도 빈 칸이 남아 있으면 계속 확인합니다 (나중에 채워지는 일이 있습니다)
    assert tp._month_ttl(2026, 8, pending) == config.CACHE_TTL_DISTRIBUTION_SECONDS
    # 이번 달은 지급이 더 붙을 수 있으니 절대 오래 두지 않습니다
    assert tp._month_ttl(2026, 9, done) == config.CACHE_TTL_DISTRIBUTION_SECONDS
    # 지급이 없었던 지난 달도 이제 안 바뀝니다
    assert tp._month_ttl(2026, 7, {}) == config.CACHE_TTL_DISTRIBUTION_FINAL_SECONDS


def test_cache_can_decide_the_ttl_from_the_stored_value():
    """`ttl_of` 가 없으면 '끝난 달은 오래 두기' 를 만들 수 없습니다."""
    from data.providers import cache

    cache.invalidate()
    calls = []
    cache.get_or_set("k", 10, lambda: calls.append(1) or "값")
    # 저장된 값을 보고 '이미 만료' 라고 답하면 다시 받아옵니다
    cache.get_or_set("k", 10, lambda: calls.append(1) or "값", ttl_of=lambda v: 0)
    assert len(calls) == 2
    # 오래 두라고 답하면 안 받아옵니다
    cache.get_or_set("k", 0, lambda: calls.append(1) or "값", ttl_of=lambda v: 9999)
    assert len(calls) == 2
    cache.invalidate()

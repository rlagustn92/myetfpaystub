"""
방문자 수 — 카운터 때문에 앱이 느려지거나 죽으면 안 됩니다.

틀리기 쉬운 곳이 정확히 세 군데이고, 셋 다 **에러 없이 조용히** 틀립니다.
1. 네임스페이스를 안 바꿔서 다른 서비스와 숫자가 섞이는 것
2. 세션 체크를 안 해서 클릭할 때마다 올라가는 것  (app 쪽 동작 — test_app_smoke.py)
3. UTC 를 써서 오전 9시에 날짜가 바뀌는 것
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import config
from services import visitor_service


class FakeResponse:
    def __init__(self, status=200, payload=None, raise_exc=None):
        self.status_code = status
        self._payload = payload if payload is not None else {}
        self._raise = raise_exc

    def json(self):
        if self._raise:
            raise self._raise
        return self._payload


def test_counts_are_returned_as_today_and_total(monkeypatch):
    seen = []

    def fake_get(url, timeout=None):
        seen.append(url)
        return FakeResponse(payload={"value": 7 if "/d-" in url else 5171})

    monkeypatch.setattr(visitor_service.requests, "get", fake_get)
    assert visitor_service.count_visit() == (7, 5171)
    assert all("/hit/" in u for u in seen)


def test_today_key_uses_korean_date_not_server_date(monkeypatch):
    urls = []
    monkeypatch.setattr(visitor_service.requests, "get",
                        lambda u, timeout=None: (urls.append(u),
                                                 FakeResponse(payload={"value": 1}))[1])
    visitor_service.count_visit()
    assert f"d-{config.today_local().isoformat()}" in " ".join(urls)


def test_korean_date_helper_is_nine_hours_ahead_of_utc():
    utc = datetime.now(timezone.utc)
    kst = config.now_local()
    assert abs((kst.utcoffset() - timedelta(hours=9)).total_seconds()) < 1
    assert abs((kst - utc).total_seconds()) < 5       # 같은 순간을 가리켜야 합니다


def test_network_failure_returns_none_and_does_not_raise(monkeypatch):
    def boom(*a, **k):
        raise visitor_service.requests.RequestException("끊김")
    monkeypatch.setattr(visitor_service.requests, "get", boom)
    assert visitor_service.count_visit() is None      # 예외가 위로 새지 않습니다


def test_server_error_returns_none(monkeypatch):
    monkeypatch.setattr(visitor_service.requests, "get",
                        lambda *a, **k: FakeResponse(status=500))
    assert visitor_service.count_visit() is None


def test_bad_json_returns_none(monkeypatch):
    monkeypatch.setattr(visitor_service.requests, "get",
                        lambda *a, **k: FakeResponse(raise_exc=ValueError("not json")))
    assert visitor_service._call("get", "아무키") is None


def test_missing_key_counts_as_zero(monkeypatch):
    """404 는 오류가 아니라 '아직 0' 이라는 뜻입니다."""
    monkeypatch.setattr(visitor_service.requests, "get",
                        lambda *a, **k: FakeResponse(status=404))
    assert visitor_service._call("get", "아무키") == 0


def test_read_counts_does_not_increment(monkeypatch):
    urls = []
    monkeypatch.setattr(visitor_service.requests, "get",
                        lambda u, timeout=None: (urls.append(u),
                                                 FakeResponse(payload={"value": 3}))[1])
    visitor_service.read_counts()
    assert urls and all("/get/" in u for u in urls)
    assert not any("/hit/" in u for u in urls)


def test_disabled_switch_skips_network_entirely(monkeypatch):
    called = []
    monkeypatch.setattr(visitor_service.requests, "get",
                        lambda *a, **k: called.append(1) or FakeResponse())
    monkeypatch.setattr(config, "COUNTER_ENABLED", False)
    assert visitor_service.count_visit() is None
    assert visitor_service.read_counts() is None
    assert called == []


def test_timeout_is_short_so_page_load_is_not_blocked():
    """카운터가 느리다고 첫 화면을 10초씩 붙잡으면 그게 더 큰 손해입니다."""
    assert config.COUNTER_TIMEOUT_SECONDS <= 3.0


def test_namespace_is_not_the_other_services_name():
    """복사해 쓴 이름을 그대로 두면 두 서비스의 방문자 수가 한 통에 섞입니다."""
    assert config.COUNTER_NAMESPACE_DEFAULT != "etfmanager2027"
    assert config.COUNTER_NAMESPACE_DEFAULT


def test_last_updated_is_korean_time():
    assert config.today_local() == config.now_local().date()
    assert isinstance(config.today_local(), date)

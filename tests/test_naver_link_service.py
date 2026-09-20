"""네이버 증권 바로가기 — 주소를 추측하지 않는다."""

from __future__ import annotations

import json

import pytest

from services import naver_link_service as NL


def test_korean_url_is_built_from_the_code():
    assert NL.korean_url("069500") == "https://m.stock.naver.com/domestic/stock/069500/total"
    assert NL.korean_url("5930").endswith("/005930/total")   # 앞의 0 을 살립니다


def test_us_url_uses_whatever_the_server_returns(monkeypatch):
    """⚠ SCHD 는 .K 가 붙고 VOO 는 안 붙습니다. 규칙이 없어서 조립하면 안 됩니다."""
    payload = {"items": [{"code": "SCHD", "name": "Schwab US Dividend Equity ETF",
                          "url": "/worldstock/etf/SCHD.K", "nationCode": "USA"}]}
    monkeypatch.setattr(NL, "_lookup_us", lambda t: NL.BASE + payload["items"][0]["url"])
    assert NL.us_url("SCHD") == "https://m.stock.naver.com/worldstock/etf/SCHD.K"


def test_us_lookup_filters_by_code_and_nation(monkeypatch):
    """비슷한 이름이 같이 옵니다. code 완전일치 + nationCode 로 걸러야 합니다."""
    payload = {"items": [
        {"code": "SCHDX", "url": "/worldstock/etf/SCHDX", "nationCode": "USA"},
        {"code": "SCHD", "url": "/domestic/stock/SCHD/total", "nationCode": "KOR"},
        {"code": "SCHD", "url": "/worldstock/etf/SCHD.K", "nationCode": "USA"},
    ]}
    monkeypatch.setattr(NL.urllib.request, "urlopen", _fake_urlopen(payload))
    assert NL._lookup_us("SCHD").endswith("/worldstock/etf/SCHD.K")


def test_no_match_draws_no_link(monkeypatch):
    monkeypatch.setattr(NL.urllib.request, "urlopen", _fake_urlopen({"items": []}))
    assert NL._lookup_us("없는티커") is None


def test_network_failure_draws_no_link_instead_of_guessing(monkeypatch):
    def boom(*a, **k):
        raise OSError("끊김")
    monkeypatch.setattr(NL.urllib.request, "urlopen", boom)
    assert NL._lookup_us("SCHD") is None


def test_url_for_dispatches_by_market(monkeypatch):
    monkeypatch.setattr(NL, "us_url", lambda t: "US-URL")
    assert NL.url_for("KR", "069500").endswith("/069500/total")
    assert NL.url_for("US", "SCHD") == "US-URL"
    assert NL.url_for("XX", "SCHD") is None


def _fake_urlopen(payload):
    class _Ctx:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps(payload).encode("utf-8")

    return lambda *a, **k: _Ctx()

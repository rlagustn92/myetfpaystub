"""금액 표기 — 돈을 잘못 적으면 사용자가 그대로 오해합니다."""

from __future__ import annotations

from datetime import date

import config
import formatting as F


def test_won_basic():
    assert F.won(45_000_000) == "₩45,000,000"
    assert F.won(0) == "₩0"
    assert F.won(None) == config.NO_DATA_TEXT


def test_won_signed_shows_direction():
    assert F.won_signed(12_340_000) == "+₩12,340,000"
    assert F.won_signed(-310_000) == "-₩310,000"
    assert F.won_signed(0) == "₩0"


def test_won_short_uses_korean_units():
    assert F.won_short(45_000_000) == "4,500만"
    assert F.won_short(123_400_000) == "1.23억"
    assert F.won_short(9_500) == "9,500원"


def test_won_short_keeps_one_decimal_for_small_man():
    """월 분배금처럼 작은 금액이 죄다 '19만' 으로 뭉개지면 비교가 안 됩니다."""
    assert F.won_short(187_000) == "18.7만"
    assert F.won_short(1_870_000) == "187만"


def test_won_short_strips_trailing_zeros_in_eok():
    assert F.won_short(1_000_000_000) == "10억"


def test_native_amt_has_no_decimals_for_won():
    """원화는 1원 미만 단위가 실질적으로 없습니다."""
    assert F.native_amt(9850, "KRW") == "₩9,850"
    assert F.native_amt(72.35, "USD") == "$72.35"
    assert F.native_amt(None, "USD") == config.NO_DATA_TEXT


def test_shares_drops_meaningless_decimals():
    assert F.shares(180) == "180주"
    assert F.shares(180.0) == "180주"
    assert F.shares(0.5) == "0.5주"


def test_dates():
    assert F.ymd(date(2026, 9, 5)) == "2026.09.05"
    assert F.md(date(2026, 9, 5)) == "9/5"
    assert F.ymd(None) == config.NO_DATA_TEXT
    assert F.md(None) == "-"


def test_percent():
    assert F.pct(1.5) == "1.50%"
    assert F.pct_signed(38.7) == "+38.70%"
    assert F.pct_signed(-4.0) == "-4.00%"
    assert F.pct(None) == config.NO_DATA_TEXT


def test_version_is_shown_next_to_the_name():
    """이름 옆에 버전이 보여야 어떤 판을 보고 있는지 알 수 있습니다."""
    assert config.APP_VERSION in config.app_title()
    assert config.APP_NAME in config.app_title()
    assert config.APP_VERSION in config.PAGE_TITLE

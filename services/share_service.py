"""
services/share_service.py  --  전술판 "📋 텍스트" 버튼이 복사할 글자
=====================================================================

📸 캡처는 이미지라, 네이버 댓글처럼 **이미지를 아예 못 올리는 곳**에서는 쓸 수
없습니다. 거기서도 보여줄 수 있게 같은 내용을 글자로 냅니다.

⚠ **캡처 이미지와 같은 숫자, 같은 순서여야 합니다.** 둘이 다르면 같은 포트폴리오를
두 군데에 올렸을 때 숫자가 어긋나 보이고, 어느 쪽이 맞는지 알 수 없게 됩니다.
그래서 이 파일과 app.render_pitch 의 capture_legend 는 **같은 함수에서** 줄을
만듭니다(`_line`).

개인정보
--------
증권사·계좌 이름은 **넣지 않습니다.** 공유용 글이라 어디에 붙여넣을지 모르고,
"미래에셋 ISA 에 얼마" 는 남에게 보여줄 이유가 없는 정보입니다.
종목·비율·금액까지만 냅니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import config
import formatting as F
from models.portfolio import MARKET_KR


@dataclass
class ShareRow:
    """공유용 한 줄. 캡처 이미지 명단과 텍스트가 같은 값을 쓰도록 여기서 만듭니다."""

    name: str            # "KODEX 200 (069500)" / "SCHD"
    weight_pct: float | None
    value_krw: float | None
    month_krw: float | None
    color: str = ""
    is_us: bool = False

    def amount_text(self, month_label: str) -> str:
        parts = [
            F.pct(self.weight_pct) if self.weight_pct is not None else config.NO_DATA_TEXT,
            F.won_short(self.value_krw) if self.value_krw is not None else config.NO_DATA_TEXT,
        ]
        if self.month_krw is not None:
            parts.append(f"{month_label} {F.won_short(self.month_krw)}")
        return " · ".join(parts)


def row_name(market: str, ticker: str, display_name: str) -> str:
    """공유 글에 적을 정식 이름. 카드에는 줄여 쓰므로 여기서 보증합니다."""
    if str(market).upper() == MARKET_KR:
        return f"{display_name} ({ticker})" if display_name else str(ticker)
    return str(ticker or display_name)


def comment_text(*, portfolio_name: str, rows: list[ShareRow],
                 total_value_krw: float, month_krw: float, month_label: str,
                 year_krw: float, year_tax_basis_krw: float,
                 today: date | None = None) -> str:
    """커뮤니티 댓글에 그대로 붙여넣을 수 있는 글자 요약."""
    today = today or config.today_local()
    lines = [
        f"[{config.APP_NAME}] {portfolio_name or '내 ETF'}",
        f"내 ETF 자산 {F.won_short(total_value_krw)}"
        f" · {month_label} ETF 월급 {F.won_short(month_krw)}"
        f" · {today.year}년 누적 {F.won_short(year_krw)}"
        f" (세금 계산 기준 {F.won_short(year_tax_basis_krw)})",
        f"※ 참고용 · 실제 입금액·세금은 증권사 내역과 다를 수 있음 · {today:%Y-%m-%d} 기준",
        "",
    ]
    for r in rows:
        lines.append(f"· {r.name} {r.amount_text(month_label)}")
    return "\n".join(lines)

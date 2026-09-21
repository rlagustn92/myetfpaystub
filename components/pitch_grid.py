"""
components/pitch_grid.py  --  전술판 포지션 슬롯 격자 (한 곳에서 관리)
=====================================================================

- 세로 방향. 화면 아래 = 우리 진영(골키퍼), 화면 위 = 공격 방향.
- 가로 5칸 (L·CL·C·CR·R) x 세로 6라인 (ST·AM·MC·DM·DF·GK).
- GK 라인은 중앙 1칸만.  => 슬롯 26개.
- 한 슬롯에 한 종목(슬롯 스냅 전용).

좌표는 정규화(0.0~1.0). y 는 "화면 기준"(0=위/공격, 1=아래/우리 골문).

이 서비스에서는 슬롯 배치를 종목(티커) 단위로 기억합니다. 같은 ETF 를 세 계좌에
나눠 갖고 있어도 전술판에는 카드가 하나만 서기 때문입니다
(models/portfolio.py 의 Portfolio.slots).
"""

from __future__ import annotations

import math

# 라인(세로): 위(공격) -> 아래(우리 골문)
ROW_CODES = ["ST", "AM", "MC", "DM", "DF", "GK"]
ROW_LABELS_KR = {
    "ST": "최전방", "AM": "공격형 MID", "MC": "중앙 MID",
    "DM": "수비형 MID", "DF": "수비", "GK": "골키퍼",
}
# ⚠ 맨 윗줄(ST)과 맨 아랫줄(GK)은 골대 뒤 응원 배너를 피해야 합니다.
# 카드에 반바지·양말이 붙으면서 세로로 길어져, 예전 값(0.10 / 0.925)이면
# 배너와 겹칩니다.
# 여섯 줄을 **고르게** 벌립니다. 눈대중으로 두면 줄 간격이 들쭉날쭉해서, 좁은
# 화면에서 가장 좁은 칸부터 카드가 겹칩니다(모바일에서 5px 까지 좁아졌었습니다).
ROW_Y = {"ST": 0.105, "AM": 0.261, "MC": 0.417, "DM": 0.573, "DF": 0.729, "GK": 0.885}

# 칸(가로): 왼쪽 -> 오른쪽
COL_CODES = ["L", "CL", "C", "CR", "R"]
COL_X = {"L": 0.13, "CL": 0.315, "C": 0.5, "CR": 0.685, "R": 0.87}

# GK 라인은 중앙만
ROW_COLS = {code: (["C"] if code == "GK" else list(COL_CODES)) for code in ROW_CODES}

# 내부 포지션 그룹 (인수인계서 9, 83)
ROW_GROUP = {
    "ST": "ATTACK", "AM": "ATTACK",
    "MC": "MIDFIELD", "DM": "MIDFIELD",
    "DF": "DEFENSE",
    "GK": "GOALKEEPER",
}

# 슬롯에 표시할 짧은 포지션 라벨
_WIDE = {"L": "L", "R": "R"}
def slot_label(slot_id: str) -> str:
    row, col = split(slot_id)
    if row == "GK":
        return "GK"
    if col in ("L", "R"):
        # 예: DF-L -> "DL", MC-R -> "MR", ST-L -> "STL"
        base = {"DF": "D", "MC": "M", "DM": "DM", "AM": "AM", "ST": "ST"}[row]
        return f"{base}{_WIDE[col]}"
    return row


def all_slots() -> list[str]:
    out: list[str] = []
    for r in ROW_CODES:
        for c in ROW_COLS[r]:
            out.append(f"{r}-{c}")
    return out


def split(slot_id: str) -> tuple[str, str]:
    row, col = slot_id.split("-", 1)
    return row, col


def is_slot(slot_id: str | None) -> bool:
    if not slot_id or "-" not in str(slot_id):
        return False
    r, c = split(slot_id)
    return r in ROW_COLS and c in ROW_COLS[r]


def center(slot_id: str) -> tuple[float, float]:
    """슬롯 중심의 정규화 좌표 (x, y).  y 는 화면 기준(0=위)."""
    row, col = split(slot_id)
    return COL_X[col], ROW_Y[row]


def group_of(slot_id: str) -> str:
    return ROW_GROUP[split(slot_id)[0]]


def nearest(x: float, y: float) -> str:
    """정규화 좌표 (x, y) 에서 가장 가까운 슬롯 id."""
    best, best_d = None, 1e9
    for s in all_slots():
        cx, cy = center(s)
        d = (cx - x) ** 2 + (cy - y) ** 2
        if d < best_d:
            best, best_d = s, d
    return best  # type: ignore[return-value]


def slot_meta() -> list[dict]:
    """프론트엔드로 넘길 슬롯 레이아웃."""
    out = []
    for s in all_slots():
        r, c = split(s)
        cx, cy = center(s)
        out.append({
            "id": s, "row": r, "col": c, "x": cx, "y": cy,
            "label": slot_label(s), "group": ROW_GROUP[r],
        })
    return out


# 티커별 기본 라인 추정 (단순 기본값. 사용자가 자유롭게 재배치)
_ROW_GUESS = {
    "TQQQ": "ST", "SOXL": "ST", "QLD": "ST", "UPRO": "ST", "SPXL": "ST",
    "QQQ": "AM", "QQQM": "AM", "SOXX": "AM", "SMH": "AM", "XLK": "AM",
    "VOO": "MC", "SPY": "MC", "IVV": "MC", "VTI": "MC", "SCHD": "MC",
    "JEPI": "MC", "JEPQ": "MC", "DIVO": "MC", "QYLD": "MC", "XYLD": "MC",
    "RYLD": "MC", "VYM": "MC", "DGRO": "MC", "O": "MC",
    "TLT": "DF", "IEF": "DF", "BND": "DF", "SHY": "DF", "GLD": "DF", "TIP": "DF",
    "SGOV": "GK", "BIL": "GK",
}


def guess_row(ticker: str) -> str:
    return _ROW_GUESS.get(str(ticker).upper(), "MC")


def _row_order_from(row: str) -> list[str]:
    i = ROW_CODES.index(row)
    order = [row]
    for d in range(1, len(ROW_CODES)):
        if i - d >= 0:
            order.append(ROW_CODES[i - d])
        if i + d < len(ROW_CODES):
            order.append(ROW_CODES[i + d])
    return order


def _col_order() -> list[str]:
    return ["C", "CL", "CR", "L", "R"]


def first_free_slot(used: set[str], preferred_row: str | None = None) -> str | None:
    """비어 있는 슬롯 하나. 선호 라인의 중앙부터, 없으면 인접 라인으로 확장."""
    rows = _row_order_from(preferred_row) if preferred_row in ROW_CODES else ROW_CODES
    for r in rows:
        for c in _col_order():
            if c not in ROW_COLS[r]:
                continue
            s = f"{r}-{c}"
            if s not in used:
                return s
    return None

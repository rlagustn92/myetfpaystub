"""
components/skins.py  --  전술판 스킨 (경기장 테마)
===================================================

전술판의 **경기장**을 바꿉니다. 잔디 두 톤, 라인 색, 빈 자리 점선, 그리고
판을 두르는 광고보드(테두리) 두 색.

⚠ 유니폼은 스킨이 바꾸지 않습니다
---------------------------------
카드의 유니폼 색은 **운용사 브랜드**(KODEX 남색, TIGER 주황 …)이고, 흰 유니폼은
**미국 종목**이라는 뜻입니다. 즉 유니폼 색은 장식이 아니라 **정보**입니다.
스킨이 유니폼까지 물들이면 그 정보가 사라집니다. 그래서 스킨은 경기장만 바꿉니다.

이름에 대하여
-------------
실제 구단 이름·별칭·엠블럼은 쓰지 않습니다. **지명 + 색**으로만 부릅니다
("London Red Edition"). 색 조합 자체는 누구의 것도 아니지만, 구단명과 별칭
("Gunners" 류)은 등록상표이고 엠블럼은 저작물입니다.

해금(수익화) 연결 지점
----------------------
`tier` 필드가 이미 있지만 **지금은 전부 무료로 열려 있습니다.** 해금 조건이
정해지면 `services/skin_service.is_unlocked()` **한 함수만** 바꾸면 됩니다.
없는 잠금을 미리 걸어두고 "곧 열립니다" 라고 적지 않습니다 — 아직 없는 걸
있는 것처럼 보여주지 않는다는 이 앱의 규칙과 같습니다.
자세한 배경은 docs/호스팅-수익화-검토.md 를 보세요.
"""

from __future__ import annotations

from dataclasses import dataclass

TIER_FREE = "free"
TIER_PREMIUM = "premium"


@dataclass(frozen=True)
class Skin:
    """경기장 한 벌.

    turf_a/turf_b  잔디 두 톤 (가로 줄무늬로 번갈아 깔립니다)
    line           흰 선(라인) 색
    slot           빈 자리 점선 색
    frame_a/frame_b  판을 두르는 광고보드 두 색. 같은 값이면 단색이 됩니다
    accent         고른 카드·끌어다 놓을 자리에 켜지는 강조색
    """

    id: str
    name: str            # 화면에 보이는 이름 (영문)
    korean: str          # 한 줄 한글 설명
    turf_a: str
    turf_b: str
    line: str
    slot: str
    frame_a: str
    frame_b: str
    accent: str
    tier: str = TIER_PREMIUM

    def to_dict(self) -> dict:
        """프론트엔드(components/football_pitch)로 넘길 모양."""
        return {
            "id": self.id, "name": self.name,
            "turfA": self.turf_a, "turfB": self.turf_b,
            "line": self.line, "slot": self.slot,
            "frameA": self.frame_a, "frameB": self.frame_b,
            "accent": self.accent,
        }


# 기본 잔디. 스킨을 고르지 않았을 때 이게 나옵니다.
DEFAULT_ID = "classic"

# 순서가 곧 화면에 보이는 순서입니다.
SKINS: tuple[Skin, ...] = (
    Skin("classic", "Classic Green", "기본 잔디",
         "#2F8F3F", "#2B8639", "rgba(255,255,255,0.78)", "rgba(255,255,255,0.45)",
         "#1F6F3A", "#1F6F3A", "#FFCF33", tier=TIER_FREE),

    # ---- 잉글랜드 ----------------------------------------------------
    Skin("london-red", "London Red Edition", "런던 레드 — 붉은색과 흰색",
         "#2E8B3E", "#2A8238", "rgba(255,255,255,0.82)", "rgba(255,255,255,0.45)",
         "#C8102E", "#FFFFFF", "#E8C34A"),
    Skin("london-blue", "London Blue Edition", "런던 블루 — 로열블루",
         "#2C8A3C", "#288136", "rgba(255,255,255,0.82)", "rgba(255,255,255,0.45)",
         "#034694", "#FFFFFF", "#DBA111"),
    Skin("thames-white", "Thames White Edition", "템스 화이트 — 흰색과 네이비",
         "#2F9040", "#2B873A", "rgba(255,255,255,0.86)", "rgba(255,255,255,0.48)",
         "#FFFFFF", "#132257", "#132257"),
    Skin("manchester-red", "Manchester Red Edition", "맨체스터 레드 — 붉은색과 검정",
         "#2C8A3C", "#287F36", "rgba(255,255,255,0.82)", "rgba(255,255,255,0.45)",
         "#DA020E", "#1A1A1A", "#FBE122"),
    Skin("manchester-sky", "Manchester Sky Edition", "맨체스터 스카이 — 하늘색",
         "#309242", "#2C893C", "rgba(255,255,255,0.86)", "rgba(255,255,255,0.48)",
         "#6CABDD", "#FFFFFF", "#1C2C5B"),
    Skin("merseyside-red", "Merseyside Red Edition", "머지사이드 레드 — 온통 붉은색",
         "#2B8739", "#277E34", "rgba(255,255,255,0.82)", "rgba(255,255,255,0.45)",
         "#C8102E", "#F6EB61", "#00B2A9"),
    Skin("tyneside-stripes", "Tyneside Stripes Edition", "타인사이드 — 검정·흰색 줄무늬",
         "#2A8438", "#267B33", "rgba(255,255,255,0.86)", "rgba(255,255,255,0.48)",
         "#241F20", "#FFFFFF", "#41B6E6"),

    # ---- 스페인 ------------------------------------------------------
    Skin("madrid-white", "Madrid White Edition", "마드리드 화이트 — 흰색과 금색",
         "#319543", "#2D8B3D", "rgba(255,255,255,0.88)", "rgba(255,255,255,0.5)",
         "#FFFFFF", "#FEBE10", "#00529F"),
    Skin("catalonia-claret", "Catalonia Claret Edition", "카탈루냐 — 자주색과 감청색",
         "#2C8A3C", "#288136", "rgba(255,255,255,0.82)", "rgba(255,255,255,0.45)",
         "#A50044", "#004D98", "#EDBB00"),
    Skin("madrid-red-stripes", "Madrid Red Stripes Edition", "마드리드 — 붉은·흰 줄무늬",
         "#2E8B3E", "#2A8238", "rgba(255,255,255,0.84)", "rgba(255,255,255,0.46)",
         "#CB3524", "#FFFFFF", "#1E2860"),

    # ---- 이탈리아 ----------------------------------------------------
    Skin("turin-monochrome", "Turin Monochrome Edition", "토리노 — 흑백",
         "#2A8036", "#267731", "rgba(255,255,255,0.88)", "rgba(255,255,255,0.5)",
         "#1A1A1A", "#FFFFFF", "#C8A24A"),
    Skin("milan-red-black", "Milan Red & Black Edition", "밀라노 — 붉은색과 검정",
         "#2C8A3C", "#287F36", "rgba(255,255,255,0.82)", "rgba(255,255,255,0.45)",
         "#C8102E", "#111111", "#C0A062"),
    Skin("milan-blue-black", "Milan Blue & Black Edition", "밀라노 — 감청색과 검정",
         "#2A8438", "#267B33", "rgba(255,255,255,0.84)", "rgba(255,255,255,0.46)",
         "#0B5FA5", "#111111", "#C9A227"),
    Skin("naples-azure", "Naples Azure Edition", "나폴리 — 하늘색",
         "#309242", "#2C893C", "rgba(255,255,255,0.86)", "rgba(255,255,255,0.48)",
         "#12A0D7", "#FFFFFF", "#003D6B"),
    Skin("rome-crimson", "Rome Crimson & Gold Edition", "로마 — 진홍과 금색",
         "#2B8739", "#277E34", "rgba(255,255,255,0.82)", "rgba(255,255,255,0.45)",
         "#8E1F2F", "#F0BC42", "#F0BC42"),

    # ---- 독일 --------------------------------------------------------
    Skin("bavaria-red", "Bavaria Red Edition", "바이에른 — 붉은색과 흰색",
         "#2E8B3E", "#2A8238", "rgba(255,255,255,0.84)", "rgba(255,255,255,0.46)",
         "#DC052D", "#FFFFFF", "#0066B2"),
    Skin("ruhr-yellow", "Ruhr Yellow Edition", "루르 — 노랑과 검정",
         "#2D8C3D", "#298337", "rgba(255,255,255,0.86)", "rgba(255,255,255,0.48)",
         "#FDE100", "#111111", "#FDE100"),

    # ---- 프랑스 · 네덜란드 · 스코틀랜드 --------------------------------
    Skin("paris-navy", "Paris Navy Edition", "파리 — 감청색과 붉은색",
         "#2A8438", "#267B33", "rgba(255,255,255,0.84)", "rgba(255,255,255,0.46)",
         "#0B2B57", "#DA291C", "#FFFFFF"),
    Skin("amsterdam-red", "Amsterdam Red Edition", "암스테르담 — 흰색과 붉은색",
         "#2F9040", "#2B873A", "rgba(255,255,255,0.86)", "rgba(255,255,255,0.48)",
         "#FFFFFF", "#D2122E", "#D2122E"),
    Skin("glasgow-hoops", "Glasgow Hoops Edition", "글래스고 — 초록·흰 가로줄",
         "#2C8A3C", "#288136", "rgba(255,255,255,0.86)", "rgba(255,255,255,0.48)",
         "#018749", "#FFFFFF", "#FFD700"),
)

BY_ID: dict[str, Skin] = {s.id: s for s in SKINS}


def get(skin_id: str | None) -> Skin:
    """스킨 하나. 모르는 id 면 기본 잔디로 (저장 파일이 오래됐을 수 있습니다)."""
    return BY_ID.get(str(skin_id or ""), BY_ID[DEFAULT_ID])


def ids() -> list[str]:
    return [s.id for s in SKINS]


def free_ids() -> list[str]:
    return [s.id for s in SKINS if s.tier == TIER_FREE]

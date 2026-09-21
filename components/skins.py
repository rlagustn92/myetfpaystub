"""
components/skins.py  --  전술판 스킨 (경기장 + 키트)
=====================================================

스킨 하나가 바꾸는 것
---------------------
    경기장   잔디 두 톤 · **깎기 무늬** · 라인 · 빈 자리 점선 · 광고보드 두 색
    관중석   전술판 바깥 배경
    유니폼   **소매 · 깃 · 무늬(줄무늬/가로줄/중앙띠)**

⚠ 유니폼 몸통 바탕색은 스킨이 절대 안 바꿉니다
-----------------------------------------------
몸통 색 = **운용사 브랜드**(KODEX 남색, TIGER 주황 …), 흰 몸통 + 성조기 = **미국 종목**.
가슴의 태극 = 한국 종목. 이건 장식이 아니라 **정보**라서 스킨이 물들이면 어느
운용사 상품인지 못 알아보게 됩니다.

그래서 유니폼에서 **비어 있는 자리만** 씁니다 — 소매, 깃, 그리고 몸통 위에 덧입히는
무늬. 실제 축구 유니폼도 그렇게 생겼습니다(빨간 몸통에 흰 소매처럼). 결과적으로
"같은 팀 유니폼을 입었는데 선수마다 가슴 색이 다르다" 가 되어, 팀 느낌과 정보가
둘 다 삽니다.

미국 종목 카드는 소매를 바꾸지 않습니다. 빨간 소매 + 가슴 성조기가 "미국 상장"
표시라서요. 깃 색만 스킨을 따릅니다.

이름에 대하여
-------------
실제 구단 이름·별칭·엠블럼은 쓰지 않습니다. **지명 + 색**으로만 부릅니다
("London Red Edition"). 색 조합 자체는 누구의 것도 아니지만, 구단명과 별칭
("Gunners" 류)은 등록상표이고 엠블럼은 저작물입니다.

해금(수익화) 연결 지점
----------------------
`tier` 필드가 이미 있지만 **지금은 전부 무료로 열려 있습니다.** 해금 조건이
정해지면 `services/skin_service.is_unlocked()` **한 함수만** 바꾸면 됩니다.
없는 잠금을 미리 걸어두고 "곧 열립니다" 라고 적지 않습니다.
배경은 docs/호스팅-수익화-검토.md 를 보세요.
"""

from __future__ import annotations

from dataclasses import dataclass

TIER_FREE = "free"
TIER_PREMIUM = "premium"

# 잔디 깎기 무늬. 프론트엔드(index.html)의 applySkin / drawTurf 가 아는 값입니다.
MOWS = ("bands", "vertical", "checks", "diagonal")
# 유니폼 무늬. 몸통 바탕(운용사 색) 위에 덧입힙니다.
PATTERNS = ("plain", "stripes", "hoops", "center", "sash")


@dataclass(frozen=True)
class Skin:
    """경기장 + 키트 한 벌.

    turf_a/turf_b   잔디 두 톤
    mow             깎기 무늬 (bands 가로띠 / vertical 세로띠 / checks 체크 / diagonal 대각)
    line            흰 선(라인) 색
    slot            빈 자리 점선 색
    frame_a/frame_b 판을 두르는 광고보드 두 색 (같으면 단색)
    stand           관중석(판 바깥) 배경색
    accent          고른 카드·끌어다 놓을 자리에 켜지는 강조색
    sleeve          유니폼 소매 색 (미국 카드는 적용 안 함)
    trim            깃 색
    pattern         몸통 무늬 종류
    pattern_color   몸통 무늬 색
    shorts          반바지 색   ⭐ 실제 그 팀 조합을 그대로 씁니다
    socks           양말 색     ⭐
    sock_band       양말 상단 띠 색 (없으면 안 그림)
    chant           골대 뒤 응원 배너 글자. **그 나라 말**로 적습니다
    """

    id: str
    name: str
    korean: str
    turf_a: str
    turf_b: str
    mow: str
    line: str
    slot: str
    frame_a: str
    frame_b: str
    stand: str
    accent: str
    sleeve: str
    trim: str
    pattern: str = "plain"
    pattern_color: str = ""
    shorts: str = ""
    socks: str = ""
    sock_band: str = ""
    chant: str = ""
    tier: str = TIER_PREMIUM

    def to_dict(self) -> dict:
        """프론트엔드(components/football_pitch)로 넘길 모양.

        ⚠ 키 이름을 바꾸면 프론트엔드의 applySkin 이 조용히 못 읽습니다(에러가
        안 납니다). tests/test_skins.py 가 이 짝을 지키고 있습니다.
        """
        return {
            "id": self.id, "name": self.name,
            "turfA": self.turf_a, "turfB": self.turf_b, "mow": self.mow,
            "line": self.line, "slot": self.slot,
            "frameA": self.frame_a, "frameB": self.frame_b,
            "stand": self.stand, "accent": self.accent,
            "sleeve": self.sleeve, "trim": self.trim,
            "pattern": self.pattern, "patternColor": self.pattern_color or self.sleeve,
            # 하의는 **전부 팀 색**입니다. 몸통(= 운용사)에서 아무것도 끌어오지
            # 않습니다. 끌어오면 카드마다 하의가 달라져서 한 팀으로 안 보입니다.
            "shorts": self.shorts, "socks": self.socks, "sockBand": self.sock_band,
            "chant": self.chant,
        }


DEFAULT_ID = "classic"

# 순서가 곧 화면에 보이는 순서입니다.
SKINS: tuple[Skin, ...] = (
    Skin("classic", "Classic Green", "기본 잔디",
         "#2F8F3F", "#2B8639", "bands",
         "rgba(255,255,255,0.78)", "rgba(255,255,255,0.45)",
         "#1F6F3A", "#1F6F3A", "#EDF1F5", "#FFCF33",
         sleeve="", trim="", pattern="plain", tier=TIER_FREE,
         shorts="#FFFFFF", socks="#2C3238",
         chant="MY ETF PAYSTUB"),

    # ---- 잉글랜드 ----------------------------------------------------
    Skin("london-red", "London Red Edition", "런던 레드 — 붉은 몸통에 흰 소매",
         "#2E8B3E", "#2A8238", "bands",
         "rgba(255,255,255,0.82)", "rgba(255,255,255,0.45)",
         "#C8102E", "#FFFFFF", "#F4E3E5", "#E8C34A",
         sleeve="#FFFFFF", trim="#E8C34A", pattern="plain",
         shorts="#FFFFFF", socks="#FFFFFF", sock_band="#C8102E",
         chant="COME ON YOU REDS"),
    Skin("london-blue", "London Blue Edition", "런던 블루 — 로열블루",
         "#2C8A3C", "#288136", "vertical",
         "rgba(255,255,255,0.82)", "rgba(255,255,255,0.45)",
         "#034694", "#FFFFFF", "#E4ECF7", "#DBA111",
         sleeve="#034694", trim="#DBA111", pattern="plain",
         shorts="#034694", socks="#FFFFFF", sock_band="#034694",
         chant="COME ON YOU BLUES"),
    Skin("thames-white", "Thames White Edition", "템스 화이트 — 흰색과 네이비",
         "#2F9040", "#2B873A", "bands",
         "rgba(255,255,255,0.86)", "rgba(255,255,255,0.48)",
         "#FFFFFF", "#132257", "#EEF1F7", "#132257",
         sleeve="#FFFFFF", trim="#132257", pattern="plain",
         shorts="#132257", socks="#FFFFFF", sock_band="#132257",
         chant="COME ON YOU WHITES"),
    Skin("manchester-red", "Manchester Red Edition", "맨체스터 레드 — 붉은색과 검정",
         "#2C8A3C", "#287F36", "checks",
         "rgba(255,255,255,0.82)", "rgba(255,255,255,0.45)",
         "#DA020E", "#1A1A1A", "#F6E3E4", "#FBE122",
         sleeve="#DA020E", trim="#FBE122", pattern="plain",
         shorts="#FFFFFF", socks="#1A1A1A", sock_band="#DA020E",
         chant="PRIDE OF MANCHESTER"),
    Skin("manchester-sky", "Manchester Sky Edition", "맨체스터 스카이 — 하늘색",
         "#309242", "#2C893C", "bands",
         "rgba(255,255,255,0.86)", "rgba(255,255,255,0.48)",
         "#6CABDD", "#FFFFFF", "#E7F1FA", "#1C2C5B",
         sleeve="#6CABDD", trim="#1C2C5B", pattern="plain",
         shorts="#FFFFFF", socks="#6CABDD", sock_band="#1C2C5B",
         chant="MANCHESTER SKY BLUE"),
    Skin("merseyside-red", "Merseyside Red Edition", "머지사이드 레드 — 온통 붉은색",
         "#2B8739", "#277E34", "bands",
         "rgba(255,255,255,0.82)", "rgba(255,255,255,0.45)",
         "#C8102E", "#F6EB61", "#F5E2E5", "#00B2A9",
         sleeve="#C8102E", trim="#F6EB61", pattern="plain",
         shorts="#C8102E", socks="#C8102E", sock_band="#FFFFFF",
         chant="COME ON MERSEYSIDE"),
    Skin("tyneside-stripes", "Tyneside Stripes Edition", "타인사이드 — 검정·흰 세로줄",
         "#2A8438", "#267B33", "vertical",
         "rgba(255,255,255,0.86)", "rgba(255,255,255,0.48)",
         "#241F20", "#FFFFFF", "#ECECEE", "#41B6E6",
         sleeve="#241F20", trim="#FFFFFF", pattern="stripes", pattern_color="#241F20",
         shorts="#241F20", socks="#241F20", sock_band="#FFFFFF",
         chant="HOWAY THE LADS"),

    # ---- 스페인 ------------------------------------------------------
    Skin("madrid-white", "Madrid White Edition", "마드리드 화이트 — 흰색과 금색",
         "#319543", "#2D8B3D", "checks",
         "rgba(255,255,255,0.88)", "rgba(255,255,255,0.5)",
         "#FFFFFF", "#FEBE10", "#F4F2EA", "#00529F",
         sleeve="#FFFFFF", trim="#FEBE10", pattern="plain",
         shorts="#FFFFFF", socks="#FFFFFF", sock_band="#FEBE10",
         chant="¡VAMOS MADRID!"),
    Skin("catalonia-claret", "Catalonia Claret Edition", "카탈루냐 — 자주·감청 세로줄",
         "#2C8A3C", "#288136", "vertical",
         "rgba(255,255,255,0.82)", "rgba(255,255,255,0.45)",
         "#A50044", "#004D98", "#F0E4EA", "#EDBB00",
         sleeve="#A50044", trim="#EDBB00", pattern="stripes", pattern_color="#004D98",
         shorts="#004D98", socks="#004D98", sock_band="#A50044",
         chant="FORÇA CATALUNYA"),
    Skin("madrid-red-stripes", "Madrid Red Stripes Edition", "마드리드 — 붉은·흰 세로줄",
         "#2E8B3E", "#2A8238", "vertical",
         "rgba(255,255,255,0.84)", "rgba(255,255,255,0.46)",
         "#CB3524", "#FFFFFF", "#F6E6E3", "#1E2860",
         sleeve="#CB3524", trim="#FFFFFF", pattern="stripes", pattern_color="#FFFFFF",
         shorts="#1E2860", socks="#CB3524", sock_band="#FFFFFF",
         chant="¡AÚPA MADRID!"),

    # ---- 이탈리아 ----------------------------------------------------
    Skin("turin-monochrome", "Turin Monochrome Edition", "토리노 — 흑백 세로줄",
         "#2A8036", "#267731", "bands",
         "rgba(255,255,255,0.88)", "rgba(255,255,255,0.5)",
         "#1A1A1A", "#FFFFFF", "#EDEDEF", "#C8A24A",
         sleeve="#1A1A1A", trim="#FFFFFF", pattern="stripes", pattern_color="#1A1A1A",
         shorts="#FFFFFF", socks="#FFFFFF", sock_band="#1A1A1A",
         chant="FORZA PIEMONTE"),
    Skin("milan-red-black", "Milan Red & Black Edition", "밀라노 — 붉은색과 검정 세로줄",
         "#2C8A3C", "#287F36", "vertical",
         "rgba(255,255,255,0.82)", "rgba(255,255,255,0.45)",
         "#C8102E", "#111111", "#F2E3E4", "#C0A062",
         sleeve="#111111", trim="#C0A062", pattern="stripes", pattern_color="#111111",
         shorts="#FFFFFF", socks="#FFFFFF", sock_band="#C8102E",
         chant="FORZA MILANO"),
    Skin("milan-blue-black", "Milan Blue & Black Edition", "밀라노 — 감청·검정 세로줄",
         "#2A8438", "#267B33", "vertical",
         "rgba(255,255,255,0.84)", "rgba(255,255,255,0.46)",
         "#0B5FA5", "#111111", "#E6EDF4", "#C9A227",
         sleeve="#111111", trim="#C9A227", pattern="stripes", pattern_color="#0B5FA5",
         shorts="#111111", socks="#111111", sock_band="#0B5FA5",
         chant="AVANTI MILANO"),
    Skin("naples-azure", "Naples Azure Edition", "나폴리 — 하늘색",
         "#309242", "#2C893C", "bands",
         "rgba(255,255,255,0.86)", "rgba(255,255,255,0.48)",
         "#12A0D7", "#FFFFFF", "#E4F2FA", "#003D6B",
         sleeve="#12A0D7", trim="#003D6B", pattern="plain",
         shorts="#12A0D7", socks="#12A0D7", sock_band="#FFFFFF",
         chant="FORZA NAPOLI"),
    Skin("rome-crimson", "Rome Crimson & Gold Edition", "로마 — 진홍과 금색",
         "#2B8739", "#277E34", "checks",
         "rgba(255,255,255,0.82)", "rgba(255,255,255,0.45)",
         "#8E1F2F", "#F0BC42", "#F3E7DC", "#F0BC42",
         sleeve="#8E1F2F", trim="#F0BC42", pattern="plain",
         shorts="#FFFFFF", socks="#8E1F2F", sock_band="#F0BC42",
         chant="FORZA ROMA"),

    # ---- 독일 --------------------------------------------------------
    Skin("bavaria-red", "Bavaria Red Edition", "바이에른 — 붉은색과 흰색",
         "#2E8B3E", "#2A8238", "bands",
         "rgba(255,255,255,0.84)", "rgba(255,255,255,0.46)",
         "#DC052D", "#FFFFFF", "#F6E3E6", "#0066B2",
         sleeve="#DC052D", trim="#0066B2", pattern="plain",
         shorts="#DC052D", socks="#DC052D", sock_band="#FFFFFF",
         chant="AUF GEHT'S BAYERN"),
    Skin("ruhr-yellow", "Ruhr Yellow Edition", "루르 — 노랑과 검정",
         "#2D8C3D", "#298337", "diagonal",
         "rgba(255,255,255,0.86)", "rgba(255,255,255,0.48)",
         "#FDE100", "#111111", "#FAF3D6", "#FDE100",
         sleeve="#111111", trim="#FDE100", pattern="plain",
         shorts="#111111", socks="#FDE100", sock_band="#111111",
         chant="AUF GEHT'S RUHRPOTT"),

    # ---- 프랑스 · 네덜란드 · 스코틀랜드 --------------------------------
    Skin("paris-navy", "Paris Navy Edition", "파리 — 감청색에 붉은 중앙띠",
         "#2A8438", "#267B33", "bands",
         "rgba(255,255,255,0.84)", "rgba(255,255,255,0.46)",
         "#0B2B57", "#DA291C", "#E5E9F1", "#FFFFFF",
         sleeve="#0B2B57", trim="#FFFFFF", pattern="center", pattern_color="#DA291C",
         shorts="#0B2B57", socks="#0B2B57", sock_band="#DA291C",
         chant="ALLEZ PARIS"),
    Skin("amsterdam-red", "Amsterdam Red Edition", "암스테르담 — 흰색에 붉은 중앙띠",
         "#2F9040", "#2B873A", "bands",
         "rgba(255,255,255,0.86)", "rgba(255,255,255,0.48)",
         "#FFFFFF", "#D2122E", "#F6E7E9", "#D2122E",
         sleeve="#FFFFFF", trim="#D2122E", pattern="center", pattern_color="#D2122E",
         shorts="#FFFFFF", socks="#D2122E", sock_band="#FFFFFF",
         chant="KOM OP AMSTERDAM"),
    Skin("glasgow-hoops", "Glasgow Hoops Edition", "글래스고 — 초록·흰 가로줄",
         "#2C8A3C", "#288136", "bands",
         "rgba(255,255,255,0.86)", "rgba(255,255,255,0.48)",
         "#018749", "#FFFFFF", "#E4F1E8", "#FFD700",
         sleeve="#018749", trim="#FFD700", pattern="hoops", pattern_color="#018749",
         shorts="#FFFFFF", socks="#FFFFFF", sock_band="#018749",
         chant="GLASGOW GREEN"),
)

BY_ID: dict[str, Skin] = {s.id: s for s in SKINS}


def get(skin_id: str | None) -> Skin:
    """스킨 하나. 모르는 id 면 기본 잔디로 (저장 파일이 오래됐을 수 있습니다)."""
    return BY_ID.get(str(skin_id or ""), BY_ID[DEFAULT_ID])


def ids() -> list[str]:
    return [s.id for s in SKINS]


def free_ids() -> list[str]:
    return [s.id for s in SKINS if s.tier == TIER_FREE]

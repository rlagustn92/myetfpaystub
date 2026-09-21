"""
components/skins.py  --  전술판 스킨 (경기장 + 키트)
=====================================================

스킨 하나가 바꾸는 것
---------------------
    경기장   잔디 두 톤 · **깎기 무늬** · 라인 · 빈 자리 점선 · 광고보드 두 색
    관중석   전술판 바깥 배경
    유니폼   **몸통 · 소매 · 깃 · 무늬** · 반바지 · 양말
    센터서클 지명 약자 + **그 나라·지역 깃발 색띠**

⚠ 기본 스킨(classic)은 몸통을 안 바꿉니다 — 여기가 정보의 기준선
--------------------------------------------------------------
기본 잔디에서는 몸통 색 = **운용사 브랜드**(KODEX 남색, TIGER 주황 …)입니다.
`body` 를 **비워 두면** 지금까지와 똑같이 운용사 색으로 그려집니다. 기본값이
곧 "정보 우선" 모드입니다.

클럽풍 스킨에서는 `body` 를 그 팀 몸통색으로 채웁니다. 그러면 카드 넉 장이
같은 유니폼을 입어서 "딱 보면 그 팀" 이 됩니다. 소매·깃·무늬만 물들여서는
몸통 면적(유니폼의 70%)을 못 이겨서 팀이 전혀 안 떠올랐습니다 — 실제로
"마드리드인지 잘 모르겠다" 는 지적을 받고 바꾼 것입니다.

몸통을 내주는 대신 **운용사는 세 곳에서 계속 보입니다.**

    이름표 배경   카드 바로 아래 큰 색 막대 (`kit.dark`) — 가장 눈에 띕니다
    유니폼 테두리 상의 외곽선 (`kit.dark`)
    가슴 두 글자  KO · TI · AC …  (`kit.brand`)

시장 구분(한국 태극 / 미국 성조기)은 **가슴 문장**이 그대로 지고 있습니다.
몸통색이 아니라 가슴 문장이 시장 표시라서, 몸통을 물들여도 안 깨집니다.

이름에 대하여
-------------
실제 구단 이름·별칭·엠블럼은 쓰지 않습니다. **지명 + 색**으로만 부릅니다
("London Red Edition"). 색 조합 자체는 누구의 것도 아니지만, 구단명과 별칭
("Gunners" 류)은 등록상표이고 엠블럼은 저작물입니다.

센터서클 배지도 마찬가지입니다. 구단 엠블럼을 **연상시키는 도형도 그리지
않습니다.** 대신 **국기·지역기**(공공 상징이라 누구나 쓸 수 있습니다)를
색띠로 깔고 그 위에 지명 약자를 얹습니다. 도시 상징 도형(곰·벌·화산 …)도
검토했지만 사용자가 "카탈루냐 깃발만 예쁘다" 고 해서 깃발 쪽으로 갔습니다.

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
# 유니폼 무늬. 몸통 바탕 위에 덧입힙니다.
PATTERNS = ("plain", "stripes", "hoops", "center", "sash", "pinstripe", "diamonds")
# 센터서클 깃발을 그리는 방식. 프론트엔드의 badgeParts() 가 아는 값입니다.
BADGE_DIRS = ("v", "h", "cross", "saltire", "diamond")


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
    body            유니폼 몸통 색. ⭐ **비우면 운용사 색**(기본 스킨이 그렇습니다)
    sleeve          유니폼 소매 색
    trim            깃 색
    pattern         몸통 무늬 종류
    pattern_color   몸통 무늬 색
    shorts          반바지 색   ⭐ 실제 그 팀 조합을 그대로 씁니다
    socks           양말 색     ⭐
    sock_band       양말 상단 띠 색 (없으면 안 그림)
    chant           위(상대 골문) 배너 글자. **그 나라 말**로 적습니다
    chant_home      아래(우리 진영) 배너 글자
    badge           센터서클에 칠할 짧은 글자. **지명 약자**만 씁니다(구단 약칭 아님)
    badge_bars      센터서클 깃발 색띠. **국기·지역기**만 (공공 상징)
    badge_dir       깃발 그리는 방식 — BADGE_DIRS 참고. 빈 badge_bars 면 무시
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
    body: str = ""
    pattern: str = "plain"
    pattern_color: str = ""
    shorts: str = ""
    socks: str = ""
    sock_band: str = ""
    chant: str = ""
    chant_home: str = ""
    badge: str = ""
    badge_bars: tuple[str, ...] = ()
    badge_dir: str = "v"
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
            # 몸통. **빈 문자열이면 프론트엔드가 운용사 색을 씁니다** — 기본
            # 스킨이 예전 그대로 보이는 이유가 이것입니다. 지우지 마세요.
            "body": self.body,
            "sleeve": self.sleeve, "trim": self.trim,
            "pattern": self.pattern, "patternColor": self.pattern_color or self.sleeve,
            # 하의는 **전부 팀 색**입니다. 운용사 색을 끌어오면 카드마다 하의가
            # 달라져서 한 팀으로 안 보입니다.
            "shorts": self.shorts, "socks": self.socks, "sockBand": self.sock_band,
            "chant": self.chant, "chantHome": self.chant_home, "badge": self.badge,
            "badgeBars": list(self.badge_bars), "badgeDir": self.badge_dir,
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
         chant="MY ETF PAYSTUB",
         badge="ETF",
         chant_home="내 ETF 전술판"),

    # ---- 잉글랜드 ----------------------------------------------------
    Skin("london-red", "London Red Edition", "런던 레드 — 붉은 몸통에 흰 소매",
         "#2E8B3E", "#2A8238", "bands",
         "rgba(255,255,255,0.82)", "rgba(255,255,255,0.45)",
         "#C8102E", "#FFFFFF", "#F4E3E5", "#E8C34A",
         sleeve="#FFFFFF", trim="#E8C34A", pattern="plain",
         shorts="#FFFFFF", socks="#FFFFFF", sock_band="#C8102E",
         chant="NORTH LONDON RED",
         badge="LDN",
         # #EF0107 은 흰 글자 대비가 4.49 로 WCAG AA(4.5) 에 아슬아슬하게
         # 못 미쳐서 가슴 두 글자가 묻혔습니다. 한 톤만 낮췄습니다.
         body="#E30613",
         badge_dir="cross", badge_bars=("#FFFFFF", "#CE1124"),
         chant_home="RED & WHITE"),
    Skin("london-blue", "London Blue Edition", "런던 블루 — 로열블루",
         "#2C8A3C", "#288136", "vertical",
         "rgba(255,255,255,0.82)", "rgba(255,255,255,0.45)",
         "#034694", "#FFFFFF", "#E4ECF7", "#DBA111",
         sleeve="#034694", trim="#DBA111", pattern="plain",
         shorts="#034694", socks="#FFFFFF", sock_band="#034694",
         chant="WEST LONDON BLUE",
         badge="LDN",
         body="#034694",
         badge_dir="cross", badge_bars=("#FFFFFF", "#CE1124"),
         chant_home="BLUE & WHITE"),
    Skin("thames-white", "Thames White Edition", "템스 화이트 — 흰색과 네이비",
         "#2F9040", "#2B873A", "bands",
         "rgba(255,255,255,0.86)", "rgba(255,255,255,0.48)",
         "#FFFFFF", "#132257", "#EEF1F7", "#132257",
         sleeve="#FFFFFF", trim="#132257", pattern="plain",
         shorts="#132257", socks="#FFFFFF", sock_band="#132257",
         chant="NORTH LONDON WHITE",
         badge="LDN",
         body="#FFFFFF",
         badge_dir="cross", badge_bars=("#FFFFFF", "#CE1124"),
         chant_home="WHITE & NAVY"),
    Skin("manchester-red", "Manchester Red Edition", "맨체스터 레드 — 붉은색과 검정",
         "#2C8A3C", "#287F36", "checks",
         "rgba(255,255,255,0.82)", "rgba(255,255,255,0.45)",
         "#DA020E", "#1A1A1A", "#F6E3E4", "#FBE122",
         sleeve="#DA020E", trim="#FBE122", pattern="plain",
         shorts="#FFFFFF", socks="#1A1A1A", sock_band="#DA020E",
         chant="MANCHESTER RED",
         badge="MCR",
         body="#DA020E",
         badge_dir="cross", badge_bars=("#FFFFFF", "#CE1124"),
         chant_home="RED · WHITE · BLACK"),
    Skin("manchester-sky", "Manchester Sky Edition", "맨체스터 스카이 — 하늘색",
         "#309242", "#2C893C", "bands",
         "rgba(255,255,255,0.86)", "rgba(255,255,255,0.48)",
         "#6CABDD", "#FFFFFF", "#E7F1FA", "#1C2C5B",
         sleeve="#6CABDD", trim="#1C2C5B", pattern="plain",
         shorts="#FFFFFF", socks="#6CABDD", sock_band="#1C2C5B",
         chant="MANCHESTER SKY",
         badge="MCR",
         body="#6CABDD",
         badge_dir="cross", badge_bars=("#FFFFFF", "#CE1124"),
         chant_home="SKY BLUE"),
    Skin("merseyside-red", "Merseyside Red Edition", "머지사이드 레드 — 온통 붉은색",
         "#2B8739", "#277E34", "bands",
         "rgba(255,255,255,0.82)", "rgba(255,255,255,0.45)",
         "#C8102E", "#F6EB61", "#F5E2E5", "#00B2A9",
         sleeve="#C8102E", trim="#F6EB61", pattern="plain",
         shorts="#C8102E", socks="#C8102E", sock_band="#FFFFFF",
         chant="MERSEYSIDE RED",
         badge="LIV",
         body="#C8102E",
         badge_dir="cross", badge_bars=("#FFFFFF", "#CE1124"),
         chant_home="ALL RED"),
    Skin("tyneside-stripes", "Tyneside Stripes Edition", "타인사이드 — 검정·흰 세로줄",
         "#2A8438", "#267B33", "vertical",
         "rgba(255,255,255,0.86)", "rgba(255,255,255,0.48)",
         "#241F20", "#FFFFFF", "#ECECEE", "#41B6E6",
         sleeve="#241F20", trim="#FFFFFF", pattern="stripes", pattern_color="#241F20",
         shorts="#241F20", socks="#241F20", sock_band="#FFFFFF",
         chant="HOWAY TYNESIDE",
         badge="TYN",
         body="#FFFFFF",
         badge_dir="cross", badge_bars=("#FFFFFF", "#CE1124"),
         chant_home="BLACK & WHITE"),

    # ---- 스페인 ------------------------------------------------------
    Skin("madrid-white", "Madrid White Edition", "마드리드 화이트 — 흰색과 금색",
         "#319543", "#2D8B3D", "checks",
         "rgba(255,255,255,0.88)", "rgba(255,255,255,0.5)",
         "#FFFFFF", "#FEBE10", "#F4F2EA", "#00529F",
         sleeve="#FFFFFF", trim="#00529F",
         pattern="pinstripe", pattern_color="#FEBE10",
         shorts="#FFFFFF", socks="#FFFFFF", sock_band="#00529F",
         chant="¡VAMOS MADRID!",
         badge="MAD",
         body="#FFFFFF",
         badge_dir="v", badge_bars=("#AA151B", "#F1BF00", "#AA151B"),
         chant_home="BLANCO Y ORO"),
    Skin("catalonia-claret", "Catalonia Claret Edition", "카탈루냐 — 자주·감청 세로줄",
         "#2C8A3C", "#288136", "vertical",
         "rgba(255,255,255,0.82)", "rgba(255,255,255,0.45)",
         "#A50044", "#004D98", "#F0E4EA", "#EDBB00",
         sleeve="#A50044", trim="#EDBB00", pattern="stripes", pattern_color="#004D98",
         shorts="#004D98", socks="#004D98", sock_band="#A50044",
         chant="FORÇA CATALUNYA",
         badge="CAT",
         body="#A50044",
         badge_dir="v", badge_bars=("#FCDD09", "#DA121A", "#FCDD09", "#DA121A", "#FCDD09", "#DA121A", "#FCDD09", "#DA121A", "#FCDD09"),
         chant_home="GRANA I BLAU"),
    Skin("madrid-red-stripes", "Madrid Red Stripes Edition", "마드리드 — 붉은·흰 세로줄",
         "#2E8B3E", "#2A8238", "vertical",
         "rgba(255,255,255,0.84)", "rgba(255,255,255,0.46)",
         "#CB3524", "#FFFFFF", "#F6E6E3", "#1E2860",
         sleeve="#CB3524", trim="#FFFFFF", pattern="stripes", pattern_color="#FFFFFF",
         shorts="#1E2860", socks="#CB3524", sock_band="#FFFFFF",
         chant="¡AÚPA MADRID!",
         badge="MAD",
         body="#CB3524",
         badge_dir="v", badge_bars=("#AA151B", "#F1BF00", "#AA151B"),
         chant_home="ROJO Y BLANCO"),

    # ---- 이탈리아 ----------------------------------------------------
    Skin("turin-monochrome", "Turin Monochrome Edition", "토리노 — 흑백 세로줄",
         "#2A8036", "#267731", "bands",
         "rgba(255,255,255,0.88)", "rgba(255,255,255,0.5)",
         "#1A1A1A", "#FFFFFF", "#EDEDEF", "#C8A24A",
         sleeve="#1A1A1A", trim="#FFFFFF", pattern="stripes", pattern_color="#1A1A1A",
         shorts="#FFFFFF", socks="#FFFFFF", sock_band="#1A1A1A",
         chant="FORZA PIEMONTE",
         badge="TOR",
         body="#FFFFFF",
         badge_dir="v", badge_bars=("#008C45", "#F4F5F0", "#CD212A"),
         chant_home="BIANCO E NERO"),
    Skin("milan-red-black", "Milan Red & Black Edition", "밀라노 — 붉은색과 검정 세로줄",
         "#2C8A3C", "#287F36", "vertical",
         "rgba(255,255,255,0.82)", "rgba(255,255,255,0.45)",
         "#C8102E", "#111111", "#F2E3E4", "#C0A062",
         sleeve="#111111", trim="#C0A062", pattern="stripes", pattern_color="#111111",
         shorts="#FFFFFF", socks="#FFFFFF", sock_band="#C8102E",
         chant="FORZA MILANO",
         badge="MIL",
         body="#C8102E",
         badge_dir="v", badge_bars=("#008C45", "#F4F5F0", "#CD212A"),
         chant_home="ROSSO E NERO"),
    Skin("milan-blue-black", "Milan Blue & Black Edition", "밀라노 — 감청·검정 세로줄",
         "#2A8438", "#267B33", "vertical",
         "rgba(255,255,255,0.84)", "rgba(255,255,255,0.46)",
         "#0B5FA5", "#111111", "#E6EDF4", "#C9A227",
         sleeve="#111111", trim="#C9A227", pattern="stripes", pattern_color="#0B5FA5",
         shorts="#111111", socks="#111111", sock_band="#0B5FA5",
         chant="AVANTI MILANO",
         badge="MIL",
         body="#111111",
         badge_dir="v", badge_bars=("#008C45", "#F4F5F0", "#CD212A"),
         chant_home="NERO E AZZURRO"),
    Skin("naples-azure", "Naples Azure Edition", "나폴리 — 하늘색",
         "#309242", "#2C893C", "bands",
         "rgba(255,255,255,0.86)", "rgba(255,255,255,0.48)",
         "#12A0D7", "#FFFFFF", "#E4F2FA", "#003D6B",
         sleeve="#12A0D7", trim="#003D6B", pattern="plain",
         shorts="#12A0D7", socks="#12A0D7", sock_band="#FFFFFF",
         chant="FORZA NAPOLI",
         badge="NAP",
         body="#12A0D7",
         badge_dir="v", badge_bars=("#008C45", "#F4F5F0", "#CD212A"),
         chant_home="CIELO DI NAPOLI"),
    Skin("rome-crimson", "Rome Crimson & Gold Edition", "로마 — 진홍과 금색",
         "#2B8739", "#277E34", "checks",
         "rgba(255,255,255,0.82)", "rgba(255,255,255,0.45)",
         "#8E1F2F", "#F0BC42", "#F3E7DC", "#F0BC42",
         sleeve="#8E1F2F", trim="#F0BC42", pattern="plain",
         shorts="#FFFFFF", socks="#8E1F2F", sock_band="#F0BC42",
         chant="FORZA ROMA",
         badge="ROM",
         body="#8E1F2F",
         badge_dir="v", badge_bars=("#008C45", "#F4F5F0", "#CD212A"),
         chant_home="ROSSO E ORO"),

    # ---- 독일 --------------------------------------------------------
    Skin("bavaria-red", "Bavaria Red Edition", "바이에른 — 붉은색과 흰색",
         "#2E8B3E", "#2A8238", "bands",
         "rgba(255,255,255,0.84)", "rgba(255,255,255,0.46)",
         "#DC052D", "#FFFFFF", "#F6E3E6", "#0066B2",
         # 마름모 격자 = 바이에른 주 깃발 문양. 지역 공공 상징이라 씁니다.
         sleeve="#DC052D", trim="#0066B2", pattern="diamonds", pattern_color="#FFFFFF",
         shorts="#DC052D", socks="#DC052D", sock_band="#FFFFFF",
         chant="AUF GEHT'S BAYERN",
         badge="BAY",
         body="#DC052D",
         badge_dir="diamond", badge_bars=("#FFFFFF", "#0066B2"),
         chant_home="ROT UND WEISS"),
    Skin("ruhr-yellow", "Ruhr Yellow Edition", "루르 — 노랑과 검정",
         "#2D8C3D", "#298337", "diagonal",
         "rgba(255,255,255,0.86)", "rgba(255,255,255,0.48)",
         "#FDE100", "#111111", "#FAF3D6", "#FDE100",
         sleeve="#111111", trim="#FDE100", pattern="plain",
         shorts="#111111", socks="#FDE100", sock_band="#111111",
         chant="AUF GEHT'S RUHRPOTT",
         badge="RUHR",
         body="#FDE100",
         badge_dir="h", badge_bars=("#000000", "#DD0000", "#FFCE00"),
         chant_home="GELB UND SCHWARZ"),

    # ---- 프랑스 · 네덜란드 · 스코틀랜드 --------------------------------
    Skin("paris-navy", "Paris Navy Edition", "파리 — 감청색에 붉은 중앙띠",
         "#2A8438", "#267B33", "bands",
         "rgba(255,255,255,0.84)", "rgba(255,255,255,0.46)",
         "#0B2B57", "#DA291C", "#E5E9F1", "#FFFFFF",
         sleeve="#0B2B57", trim="#FFFFFF", pattern="center", pattern_color="#DA291C",
         shorts="#0B2B57", socks="#0B2B57", sock_band="#DA291C",
         chant="ALLEZ PARIS",
         badge="PAR",
         body="#0B2B57",
         badge_dir="v", badge_bars=("#002395", "#FFFFFF", "#ED2939"),
         chant_home="BLEU ET ROUGE"),
    Skin("amsterdam-red", "Amsterdam Red Edition", "암스테르담 — 흰색에 붉은 중앙띠",
         "#2F9040", "#2B873A", "bands",
         "rgba(255,255,255,0.86)", "rgba(255,255,255,0.48)",
         "#FFFFFF", "#D2122E", "#F6E7E9", "#D2122E",
         sleeve="#FFFFFF", trim="#D2122E", pattern="center", pattern_color="#D2122E",
         shorts="#FFFFFF", socks="#D2122E", sock_band="#FFFFFF",
         chant="KOM OP AMSTERDAM",
         badge="AMS",
         body="#FFFFFF",
         badge_dir="h", badge_bars=("#AE1C28", "#FFFFFF", "#21468B"),
         chant_home="ROOD EN WIT"),
    Skin("glasgow-hoops", "Glasgow Hoops Edition", "글래스고 — 초록·흰 가로줄",
         "#2C8A3C", "#288136", "bands",
         "rgba(255,255,255,0.86)", "rgba(255,255,255,0.48)",
         "#018749", "#FFFFFF", "#E4F1E8", "#FFD700",
         sleeve="#018749", trim="#FFD700", pattern="hoops", pattern_color="#018749",
         shorts="#FFFFFF", socks="#FFFFFF", sock_band="#018749",
         chant="GLASGOW GREEN",
         badge="GLA",
         body="#FFFFFF",
         badge_dir="saltire", badge_bars=("#005EB8", "#FFFFFF"),
         chant_home="GREEN & WHITE"),
)

BY_ID: dict[str, Skin] = {s.id: s for s in SKINS}


def get(skin_id: str | None) -> Skin:
    """스킨 하나. 모르는 id 면 기본 잔디로 (저장 파일이 오래됐을 수 있습니다)."""
    return BY_ID.get(str(skin_id or ""), BY_ID[DEFAULT_ID])


def ids() -> list[str]:
    return [s.id for s in SKINS]


def free_ids() -> list[str]:
    return [s.id for s in SKINS if s.tier == TIER_FREE]

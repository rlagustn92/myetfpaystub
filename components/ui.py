"""
components/ui.py  --  화면 조각과 스타일 (보이는 것만 담당, 계산은 안 함)
=========================================================================

디자인 원칙 (프롬프트 §43)

> **숫자 하나만 던지지 않는다.** 항상 그 숫자가 무슨 뜻인지 한 줄을 바로 아래 붙인다.

그래서 이 파일의 카드 함수들은 전부 `value` 와 `label` 을 같이 받습니다.
라벨 없이 숫자만 그리는 함수는 일부러 만들지 않았습니다.
"""

from __future__ import annotations

import html
import unicodedata

import streamlit as st

import config

# 색은 한 곳에서만 정합니다. 여기 안 거치고 코드에 색을 직접 쓰지 마세요.
CSS = """
<style>
  /* 본고딕(Noto Sans KR). 한글·숫자·영문이 한 가족이라 화면이 고르게 보입니다.
     ⚠ 폰트가 늦게 오면 글자가 잠깐 다른 모양으로 보입니다(FOUT). `display=swap`
       이라 글자가 사라지진 않습니다 — 비어 보이는 것보다 낫습니다. */
  @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700;900&display=swap');

  html, body, .stApp, [class*="st-"], button, input, select, textarea,
  h1, h2, h3, h4, h5, h6 {
    font-family: 'Noto Sans KR', system-ui, sans-serif !important;
  }
  /* ⚠ 위 규칙이 **아이콘 폰트까지 덮어씁니다.** 그러면 펼침 화살표가
     `keyboard_arrow_right` 라는 **글자 그대로** 나와서 제목을 덮습니다
     (실제로 그랬습니다). 아이콘만 원래 폰트로 되돌립니다. */
  [data-testid="stIconMaterial"], .material-icons, .material-symbols-rounded,
  span[class*="material-"] {
    font-family: 'Material Symbols Rounded', 'Material Icons' !important;
  }
  /* ===================================================================
     색 — 한 곳에서만 정합니다. 여기 안 거치고 코드에 색을 직접 쓰지 마세요.

     차가운 회색(#F5F7FA)에서 **미색·흙빛**으로 옮겼습니다. 화면이 어수선한
     이유의 절반은 색이 많아서였습니다. 지금 남은 것은 네 가지뿐입니다.

         종이(미색) · 먹(글자) · 은은한 채움 · 선 하나

     오르내림(빨강/파랑)은 장식이 아니라 **정보**라서 남깁니다.
     =================================================================== */
  :root {
    --paper:      #FAF9F6;   /* 화면 바탕 — 순백이 아닌 미색 */
    --panel:      #FFFFFF;   /* 패널 바탕 */
    --tint:       #F4F2ED;   /* 은은한 채움 (카드 안쪽) */
    --tint-deep:  #EDEAE3;   /* 한 단 더 눌러야 할 때 */
    --line:       #E4E0D8;   /* 머리카락 선 */
    --line-soft:  #EFECE5;
    --ink:        #16181A;   /* 먹 */
    --ink-soft:   #5E6268;
    --ink-faint:  #93918C;
    --brand:      #1454FF;
    --up:         #C7362F;   /* 한국 관습: 오른 것이 빨강 */
    --down:       #1F5FD0;
    /* 월급 카드 — 먹색이 너무 무거워서 초록으로 갔는데, #2C4A3E 는
       "너무 찐한 초록" 이라는 지적을 받았습니다. 채도를 낮추고 한 단 밝혀
       **이끼빛**에 가깝게 맞췄습니다. 흰 글자 대비 7.4:1 로 넉넉합니다. */
    --money:      #3A5A4C;
    --money-line: rgba(255,255,255,.15);
    /* 바로가기 — 각 서비스 색 (사용자 요청) */
    --naver:      #0A8040;   /* 대비 5.03 — #0B8A43 은 4.44 라 AA 미달 */
    --toss:       #2E6FE8;
    --yahoo:      #5E35B1;
    --warn-bg:    #FBF6E8;
    --warn-line:  #E6D8AE;
    --bg-soft:    #F4F2ED;   /* 옛 이름 — 쓰던 곳이 안 깨지게 둡니다 */
    --card:       #FFFFFF;
  }

  .stApp { background: var(--paper); }
  .block-container { padding-top: 1.4rem; padding-bottom: 3.5rem; max-width: 1040px; }

  /* ---- 머리 ---- */
  .app-head { display:flex; align-items:baseline; gap:10px; flex-wrap:wrap; }
  .app-title { font-size: 1.4rem; font-weight: 800; color: var(--ink); margin:0;
               letter-spacing:-.03em; }
  .app-ver { font-size:.72rem; font-weight:700; color:var(--ink-faint);
             background:var(--tint); border-radius:999px; padding:2px 8px; }
  .app-tag { font-size:.86rem; color:var(--ink-soft); margin:.25rem 0 0; }

  .visitors { display:flex; justify-content:flex-end; gap:14px; padding-top:12px;
              font-size:12px; color:var(--ink-faint);
              font-variant-numeric: tabular-nums;   /* 갱신될 때 안 흔들리게 */
              white-space:nowrap; }
  .visitors b { font-size:10.5px; font-weight:700; letter-spacing:.06em;
                color:var(--ink-faint); margin-right:3px; }

  /* ===================================================================
     패널 — "이게 한 제목의 테두리구나" 가 보이게 하는 그릇
     -------------------------------------------------------------------
     예전에는 제목이 그냥 #### 글자였고, 카드는 흰 바탕 위의 흰 카드였습니다.
     그래서 뭐가 뭐에 속하는지 안 보이고 화면이 떠다녔습니다.

     지금은 **테두리를 패널 하나만 가집니다.** 안의 카드는 선을 안 긋고
     은은한 채움으로만 구분합니다. 선이 겹치지 않아야 조용해집니다.
     =================================================================== */
  .panel { background:var(--panel); border:1px solid var(--line); border-radius:18px;
           padding:20px 22px; margin:0 0 14px; }
  .panel-h { font-size:.95rem; font-weight:800; color:var(--ink);
             letter-spacing:-.02em; }
  .panel-s { font-size:.78rem; color:var(--ink-faint); margin-top:3px; }
  .panel-b { margin-top:14px; }

  /* 패널 안의 격자 — 카드 여러 장 */
  .grid { display:grid; gap:10px; }
  .grid.c2 { grid-template-columns:repeat(2,1fr); }
  .grid.c3 { grid-template-columns:repeat(3,1fr); }
  .grid.c4 { grid-template-columns:repeat(4,1fr); }
  .grid.c5 { grid-template-columns:repeat(5,1fr); }
  .grid.c6 { grid-template-columns:repeat(6,1fr); }

  /* ---- 값 카드 — 테두리 없이 은은한 채움만 ---- */
  /* ⚠ 카드를 **컨테이너로 선언**합니다. 그래야 아래 `cqi`(카드 폭의 1%)를
     쓸 수 있습니다. 칸이 좁아지면 글자가 같이 작아집니다 — 엑셀의 "셀에 맞춤". */
  .kcard { background:var(--tint); border:none; border-radius:14px;
           padding:16px 18px; height:100%; container-type:inline-size; }
  /* ⚠ 큰 금액은 **줄바꿈 금지**입니다. "+₩416,675" 가 부호에서 잘려
     "+" 만 윗줄에 남은 적이 있습니다(실제로 당했습니다).
     ⚠ 대신 폭에 맞춰 줄어들게 합니다. 평가손익은 몇천만원까지 커질 수
       있어서 고정 크기로 두면 언젠가 반드시 삐져나옵니다. 칸이 넓으면
       1.5rem 그대로, 좁아지면 .85rem 까지 내려갑니다. */
  .kcard .v { font-size:clamp(.85rem, 10cqi, 1.5rem); font-weight:600;
              color:var(--ink); white-space:nowrap;
              letter-spacing:-.04em; font-variant-numeric: tabular-nums;
              line-height:1.15; }
  .kcard .l { font-size:.8rem; color:var(--ink-soft); margin-top:5px; }
  .kcard .s { font-size:.74rem; color:var(--ink-faint); margin-top:7px; }
  .kcard.up .v  { color:var(--up); }
  .kcard.down .v{ color:var(--down); }

  /* ---- 이번 달 월급 — 화면에서 가장 무거운 한 덩어리 ----
     파랑 그라디언트를 먹색 단색으로 바꿨습니다. 그라디언트는 시선을 끄는
     대신 화면을 시끄럽게 합니다. 한 덩어리가 조용히 무거운 편이 낫습니다. */
  .paycard { background:var(--money); border-radius:16px; padding:24px 26px; color:#fff; }
  /* ⚠ 투명도가 곧 대비입니다. .62 는 흰 글자여도 대비 4.0 이라 AA 미달이었습니다.
     .72 부터 4.5 를 넘습니다 — 은은하게 보이려다 안 읽히면 안 됩니다. */
  .paycard .cap { font-size:.76rem; opacity:.72; font-weight:500;
                  letter-spacing:.04em; }
  /* 숫자가 "무식하게 크고 두껍다" 는 지적을 받았습니다.
     ⚠ 굵기를 낮추면(800 -> 500) 같은 크기라도 훨씬 가볍고 우아해집니다.
       크기는 오히려 조금 키우고 **자간을 더 좁혀** 덩어리로 보이게 했습니다.
       큰 숫자는 굵기가 아니라 **크기와 여백**으로 무게를 갖는 편이 낫습니다. */
  .paycard .v { font-size:2.7rem; font-weight:500; letter-spacing:-.052em;
                white-space:nowrap;
                margin:.3rem 0 .18rem; font-variant-numeric: tabular-nums;
                line-height:1; }
  .paycard .l { font-size:.78rem; opacity:.72; }
  /* 금액 옆 알약. 큰 숫자와 같은 줄에 앉되 **크기로 서열을 분명히** 합니다 —
     비슷하게 크면 둘 중 뭐가 본값인지 헷갈립니다. */
  .paycard .vb { font-size:.8rem; font-weight:500; letter-spacing:0;
                 margin-left:10px; padding:3px 9px; border-radius:999px;
                 background:rgba(255,255,255,.16); vertical-align:middle;
                 white-space:nowrap; }
  .paycard .sub { margin-top:16px; padding-top:13px;
                  border-top:1px solid var(--money-line);
                  display:flex; gap:26px; flex-wrap:wrap; }
  .paycard .sub .k { font-size:.7rem; opacity:.72; letter-spacing:.02em; }
  .paycard .sub .n { font-size:1.02rem; font-weight:600; margin-top:3px;
                     font-variant-numeric: tabular-nums;
                     letter-spacing:-.02em; }

  /* ---- 목록 한 줄 ---- */
  .row { display:flex; align-items:center; justify-content:space-between;
         padding:11px 2px; border-bottom:1px solid var(--line-soft); gap:12px; }
  .row:last-child { border-bottom:none; }
  .row .nm { font-weight:700; color:var(--ink); font-size:.92rem; }
  .row .sb { font-size:.76rem; color:var(--ink-faint); margin-top:2px; }
  .row .rt { text-align:right; white-space:nowrap; }
  .row .amt { font-weight:700; font-variant-numeric: tabular-nums; }
  /* 손익은 **한국 관습**대로 오른 것이 빨강, 내린 것이 파랑입니다.
     회색으로 두면 플러스인지 마이너스인지 눈으로 안 잡힙니다. */
  .row .sb.up   { color:var(--up);   font-weight:700; }
  .row .sb.down { color:var(--down); font-weight:700; }

  .chip { display:inline-block; font-size:.7rem; font-weight:700; border-radius:999px;
          padding:2px 8px; background:var(--tint-deep); color:var(--ink-soft);
          margin-left:6px; white-space:nowrap; }
  /* 바로가기 — 어디로 가는지 색으로 바로 알게 합니다.
     글자에만 색을 쓰고 배경은 비워 둡니다. 배경까지 칠하면 한 줄에 세 개라
     목록이 알록달록해집니다. */
  a.chip.link { text-decoration:none; border:1px solid var(--line);
                background:var(--panel); color:var(--ink-soft); }
  a.chip.link:hover { background:var(--tint); }
  a.chip.naver { color:var(--naver); border-color:#BFE6CE; }
  a.chip.toss  { color:var(--toss);  border-color:#C8D9F8; }
  a.chip.yahoo { color:var(--yahoo); border-color:#D6CBEC; }

  /* ---- 스킨 미리보기 ---- */
  .skins { display:grid; grid-template-columns:repeat(auto-fill,minmax(148px,1fr)); gap:8px; }
  .skinbox { border:1px solid var(--line); border-radius:10px; overflow:hidden;
             background:var(--panel); }
  .skinbox.on { border-color:var(--ink); box-shadow:0 0 0 2px var(--tint-deep); }
  .skinbox .band { height:10px; }
  .skinbox .turf { height:26px; position:relative; }
  .skinbox .turf i { position:absolute; left:50%; top:50%; width:34%; height:56%;
                     transform:translate(-50%,-50%); border:1.5px solid rgba(255,255,255,.8);
                     border-radius:3px; }
  .skinbox .nm { font-size:.72rem; font-weight:700; color:var(--ink);
                 padding:6px 8px 2px; line-height:1.25; }
  .skinbox .kr { font-size:.68rem; color:var(--ink-faint); padding:0 8px 7px; }

  /* ---- 목표 진행 막대 ----
     받은 돈은 진한 색, 들어올 것으로 보이는 돈은 흐린 색. 섞으면
     "벌써 다 받은 것" 처럼 보입니다. */
  .goalbar { display:flex; height:10px; border-radius:999px; overflow:hidden;
             background:var(--tint-deep); margin-top:10px; }
  .goalbar i { display:block; height:100%; }
  .goalbar .got  { background:var(--money); }
  .goalbar .more { background:var(--money); opacity:.3; }

  /* 안내(※) 가 너무 작아 안 읽힌다는 지적을 받았습니다. 한 단 키우고
     색도 한 단 진하게 — 읽으라고 적은 글이면 읽히게 해야 합니다. */
  .note { font-size:.86rem; color:var(--ink-soft); line-height:1.5; }
  .warn { background:var(--warn-bg); border:1px solid var(--warn-line); border-radius:12px;
          padding:10px 14px; font-size:.84rem; color:#6E5A20; }

  /* ---- 분배금 달력 ---- */
  .cal { display:grid; grid-template-columns:repeat(7,1fr); gap:6px; }
  .cal .h { text-align:center; font-size:.72rem; color:var(--ink-faint); padding:4px 0; }
  .cal .d { border:1px solid var(--line-soft); border-radius:10px; min-height:62px;
            padding:6px 7px; background:var(--panel); }
  .cal .d.empty { border:none; background:transparent; }
  .cal .d .n { font-size:.72rem; color:var(--ink-faint); }
  .cal .d .m { font-size:.78rem; font-weight:800; color:var(--ink); margin-top:6px;
               font-variant-numeric: tabular-nums; line-height:1.2; }
  .cal .d.pay { background:var(--tint); border-color:var(--line); }
  /* 오늘 — 달력에서 눈이 헤매지 않게 한 칸만 또렷하게 */
  .cal .d.today { border-color:var(--ink); box-shadow:inset 0 0 0 1px var(--ink); }
  .cal .d.today .n { color:var(--ink); font-weight:800; }

  /* ===================================================================
     펼쳐 보는 칸 — 누를 수 있다는 걸 눈에 보이게
     -------------------------------------------------------------------
     달력 아래 날짜 고르는 칸을 못 알아보고 달력 숫자를 누르고 있었다는
     이야기를 들었습니다. 누를 수 있는 것은 **눌러 보이게** 생겨야 합니다.
     =================================================================== */
  div[data-testid="stExpander"] details {
    border:1px solid var(--line) !important; border-radius:14px !important;
    background:var(--panel) !important; overflow:hidden;
  }
  div[data-testid="stExpander"] summary { background:var(--tint) !important;
    font-weight:700 !important; }
  div[data-testid="stExpander"] summary:hover { background:var(--tint-deep) !important; }

  /* 눌러 달라는 표시 — 살짝 흔들립니다(한 번만) */
  .tapme { display:inline-block; font-size:.72rem; font-weight:700; color:var(--ink-soft);
           background:var(--tint-deep); border-radius:999px; padding:2px 9px;
           margin-left:6px; white-space:nowrap;
           animation:tap 1.6s ease-in-out 3; }
  @keyframes tap { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-2px)} }

  /* 고르는 칸을 감싸 눈에 띄게 (달력 아래 날짜 고르기 등) */
  /* 날짜 고르는 상자. **안내·고르는 칸·결과가 한 테두리 안**에 있어야
     칸을 알아봅니다 — 예전에는 안내만 상자에 있고 칸은 밖에 떠 있어서
     달력 숫자를 누르고 있었다는 이야기를 들었습니다.
     ⚠ 위젯은 우리 HTML 로 감쌀 수 없어서, Streamlit 컨테이너에 key 를 주고
       (`st.container(border=True, key="calpick")`) 그 클래스에 색만 입힙니다.
       key 를 바꾸면 여기 선택자도 같이 바꿔야 합니다. */
  .st-key-calpick { border-color:var(--naver) !important;
                    background:#F3FAF5; border-radius:14px; }
  .st-key-calpick .pt { font-size:.82rem; font-weight:700; color:var(--naver);
                        margin-bottom:2px; }
  /* 고르는 칸 자체가 "여기를 눌러라" 라고 말해야 합니다. 연한 초록 상자 위에
     **흰 바탕 + 굵은 초록 테두리**를 올려 한 단 떠 보이게 했습니다.
     ⚠ BaseWeb 이 인라인 스타일을 얹기 때문에 `!important` 가 필요합니다. */
  /* ⚠ Streamlit 1.63 의 셀렉트박스는 **BaseWeb 이 아니라 react-aria** 입니다.
       `[data-baseweb="select"]` 로 잡으면 아무 일도 안 일어납니다(에러도 안
       납니다). 실제 DOM 은 `.stSelectbox .react-aria-ComboBox > [role=group]`.
       버전이 또 바뀔 수 있어 옛 선택자도 같이 남겨 둡니다. */
  .st-key-calpick .stSelectbox [role="group"],
  .st-key-calpick [data-baseweb="select"] > div {
      border:2px solid var(--naver) !important;
      background:#FFFFFF !important; border-radius:10px !important;
      box-shadow:0 1px 0 rgba(10,128,64,.18) !important; }
  .st-key-calpick .stSelectbox [role="group"]:hover,
  .st-key-calpick [data-baseweb="select"] > div:hover {
      background:#F7FEF9 !important; }
  .st-key-calpick label p { font-weight:700; color:var(--naver); }

  /* ---- 큰 날짜 (월별 급여명세서) ---- */
  .bigdate { display:flex; align-items:baseline; gap:10px; }
  .bigdate .y { font-size:1.15rem; font-weight:700; color:var(--ink-faint);
                font-variant-numeric:tabular-nums; }
  .bigdate .m { font-size:2.4rem; font-weight:900; color:var(--ink);
                letter-spacing:-.04em; line-height:1;
                font-variant-numeric:tabular-nums; }
  .bigdate .u { font-size:1rem; font-weight:700; color:var(--ink-soft); }

  /* ===================================================================
     월별 막대 — st.bar_chart 를 직접 그린 막대로 바꿨습니다
     -------------------------------------------------------------------
     기본 차트는 월 라벨이 **누워서** 나오고, 막대에 값이 안 적히고,
     가로로 스크롤돼서 "뭐가 얼마인지" 를 못 읽었습니다. 열두 달은 한눈에
     들어와야 하는 양이라 직접 그립니다.
     =================================================================== */
  .bars { display:grid; grid-template-columns:repeat(12,1fr); gap:5px;
          align-items:end; }
  .bars .col { display:flex; flex-direction:column; align-items:center;
               justify-content:flex-end; }
  .bars .val { font-size:.66rem; font-weight:700; color:var(--ink-soft);
               margin-bottom:4px; font-variant-numeric:tabular-nums;
               white-space:nowrap; }
  /* 막대는 겹쳐 그립니다 — 뒤가 작년, 앞이 올해. */
  .bars .stack { position:relative; width:100%; display:flex;
                 align-items:flex-end; justify-content:center; }
  .bars .bar { width:100%; background:var(--money); border-radius:5px 5px 0 0;
               min-height:2px; position:relative; z-index:1; }
  .bars .ghost { position:absolute; left:0; right:0; bottom:0;
                 background:var(--money); opacity:.22; border-radius:5px 5px 0 0; }
  .bars .col.zero .bar { background:var(--tint-deep); }
  .bars .col.now .bar { background:var(--ink); }
  /* ⚠ 라벨은 **똑바로** 세웁니다. 기본 차트가 눕혀서 읽기 나빴습니다. */
  .bars .lab { font-size:.7rem; color:var(--ink-faint); margin-top:6px;
               writing-mode:horizontal-tb; font-variant-numeric:tabular-nums; }
  .bars .col.now .lab { color:var(--ink); font-weight:700; }

  /* 좁아지면 접습니다. `.cN` 이 CSS 에 없으면 한 줄로 쌓여 버리므로,
     새 칸수를 쓸 때는 위의 정의와 아래 접기 규칙에 **둘 다** 넣어야 합니다. */
  @media (max-width: 1000px) {
    .grid.c5 { grid-template-columns:repeat(3,1fr); }
    .grid.c6 { grid-template-columns:repeat(3,1fr); }
  }
  @media (max-width: 720px) {
    .grid.c3, .grid.c4, .grid.c5, .grid.c6 { grid-template-columns:repeat(2,1fr); }
  }
  @media (max-width: 460px) {
    .panel { padding:16px 15px; border-radius:15px; }
    .grid.c2, .grid.c3, .grid.c4, .grid.c5, .grid.c6 { grid-template-columns:1fr; }
    .paycard .v { font-size:2rem; }
    .kcard .v { font-size:1.3rem; }
  }
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def _esc(x) -> str:
    return html.escape(str(x))


def header(counts: tuple[int, int] | None) -> None:
    left, right = st.columns([3, 1])
    with left:
        st.markdown(
            f"<div class='app-head'>"
            f"<h1 class='app-title'>{config.APP_ICON} {_esc(config.APP_NAME)}</h1>"
            f"<span class='app-ver'>v{_esc(config.APP_VERSION)}</span></div>"
            f"<p class='app-tag'>{_esc(config.APP_TAGLINE)}</p>",
            unsafe_allow_html=True,
        )
    with right:
        if counts:
            today, total = counts
            st.markdown(
                "<div class='visitors'>"
                f"<span><b>TODAY</b> {today:,}</span>"
                f"<span><b>TOTAL</b> {total:,}</span>"
                "</div>",
                unsafe_allow_html=True,
            )


def fit_style(value: str, max_rem: float = 1.5, min_rem: float = 0.8,
              pad_px: int = 36) -> str:
    """긴 값이 칸을 넘지 않게 **글자 크기를 칸 폭에 맞춥니다** (엑셀 "셀에 맞춤").

    왜 필요한가 — 평가손익은 사람에 따라 몇천만원, 몇억이 됩니다. 크기를
    고정해 두면 언제 넘칠지 모르고, 넘치면 "+₩416,675" 가 부호에서 잘려
    **"+" 만 윗줄에 남습니다**(실제로 당했습니다).

    CSS 는 글자 수를 셀 수 없습니다. 그래서 여기서 세어 `calc()` 에 넘깁니다.
    칸 폭은 CSS 가 아는 값(`100cqi` = 카드 폭)이라 둘을 곱하면 딱 맞습니다.

    ⚠ 한글은 숫자보다 두 배 가까이 넓어서 따로 셉니다("데이터 없음").
    ⚠ `cqi` 는 `.kcard` 에 `container-type:inline-size` 가 있어야 동작합니다.
    """
    units = sum(1.9 if unicodedata.east_asian_width(ch) in "WF" else 1.0
                for ch in str(value or ""))
    if units <= 0:
        return ""
    # 0.58em ≈ 숫자 한 자 폭(tabular-nums + 자간 -0.04em). 1.72 = 1 / 0.58.
    return (f"font-size:clamp({min_rem}rem,"
            f"calc((100cqi - {pad_px}px) * 1.72 / {units:.1f}),{max_rem}rem)")


def kcard(value: str, label: str, sub: str = "", tone: str = "") -> None:
    """숫자 하나 + 그게 무슨 뜻인지 한 줄. tone: "" | "up" | "down"."""
    cls = f"kcard {tone}".strip()
    sub_html = f"<div class='s'>{_esc(sub)}</div>" if sub else ""
    st.markdown(
        f"<div class='{cls}'>"
        f"<div class='v' style='{fit_style(value)}'>{_esc(value)}</div>"
        f"<div class='l'>{_esc(label)}</div>{sub_html}</div>",
        unsafe_allow_html=True,
    )


def paycard(amount: str, caption: str, label: str, subs: list[tuple[str, str]]) -> None:
    """이번 달 ETF 월급 — 화면에서 제일 큰 카드."""
    sub_html = "".join(
        f"<div><div class='k'>{_esc(k)}</div><div class='n'>{_esc(v)}</div></div>"
        for k, v in subs
    )
    st.markdown(
        f"<div class='paycard'><div class='cap'>{_esc(caption)}</div>"
        f"<div class='v'>{_esc(amount)}</div><div class='l'>{_esc(label)}</div>"
        f"<div class='sub'>{sub_html}</div></div>",
        unsafe_allow_html=True,
    )


# 바로가기 이름 -> CSS 종류. 어디로 가는지 **색으로** 알게 합니다.
_CHIP_KINDS: tuple[tuple[str, str], ...] = (
    ("Npay", "naver"), ("네이버", "naver"),
    ("토스", "toss"),
    ("야후", "yahoo"),
)


def _chip_kind(label: str) -> str:
    for word, kind in _CHIP_KINDS:
        if word in str(label):
            return kind
    return ""


def linkchips(links: list[tuple[str, str]]) -> str:
    """(이름, 주소) 목록을 바로가기 칩 HTML 로. 한 곳에서 만들어야 목록과
    상세 화면의 칩이 따로 놀지 않습니다.

    ⚠ 칩 글자는 짧게 두세요. "Npay증권(PC·모바일)" 처럼 길게 달았더니 종목명이
    조금만 길어져도 칩이 다음 줄로 밀렸습니다. 설명은 툴팁으로 답니다.
    """
    return "".join(
        f"<a class='chip link {_chip_kind(label)}' href='{_esc(url)}'"
        f" target='_blank' rel='noopener'"
        f" title='{_esc(label)} 에서 보기 — PC·모바일 모두 같은 주소로 열립니다'>"
        f"{_esc(label)} ↗</a>"
        for label, url in links if url
    )


def listrow(name: str, subtitle: str, amount: str, amount_sub: str = "",
            chip: str = "", link: str = "", link_text: str = "Npay증권 ↗",
            links: list[tuple[str, str]] | None = None) -> None:
    """목록 한 줄. `links` 를 주면 이름 옆에 바로가기 칩이 줄줄이 붙습니다.

    `link`/`link_text` 는 칩 하나만 붙이던 예전 방식입니다(그대로 둡니다).
    """
    chip_html = f"<span class='chip'>{_esc(chip)}</span>" if chip else ""
    if links:
        chip_html += linkchips(links)
    elif link:
        chip_html += (f"<a class='chip link' href='{_esc(link)}' target='_blank'"
                      f" rel='noopener' title='PC·모바일 모두 같은 주소로 열립니다'>"
                      f"{_esc(link_text)}</a>")
    sub_html = f"<div class='sb'>{_esc(amount_sub)}</div>" if amount_sub else ""
    st.markdown(
        f"<div class='row'><div><div class='nm'>{_esc(name)}{chip_html}</div>"
        f"<div class='sb'>{_esc(subtitle)}</div></div>"
        f"<div class='rt'><div class='amt'>{_esc(amount)}</div>{sub_html}</div></div>",
        unsafe_allow_html=True,
    )


def skin_gallery(skins: list, current_id: str) -> None:
    """스킨 전체를 작은 띠로 늘어놓습니다. 보여주기 전용 — 고르는 건 셀렉트박스가 합니다.

    Streamlit 에서 21개를 전부 버튼으로 만들면 클릭 한 번마다 화면을 통째로 다시
    그려서 무겁습니다. 그래서 "눈으로 고르고, 셀렉트박스로 선택" 으로 나눴습니다.
    """
    cells = []
    for sk in skins:
        on = " on" if sk.id == current_id else ""
        cells.append(
            f"<div class='skinbox{on}'>"
            f"<div class='band' style='background:repeating-linear-gradient(90deg,"
            f"{_esc(sk.frame_a)} 0 8px,{_esc(sk.frame_b)} 8px 16px)'></div>"
            f"<div class='turf' style='background:repeating-linear-gradient(0deg,"
            f"{_esc(sk.turf_a)} 0 6px,{_esc(sk.turf_b)} 6px 12px)'><i></i></div>"
            f"<div class='nm'>{_esc(sk.name)}</div>"
            f"<div class='kr'>{_esc(sk.korean)}</div></div>"
        )
    st.markdown(f"<div class='skins'>{''.join(cells)}</div>", unsafe_allow_html=True)


def note(text: str) -> None:
    st.markdown(f"<div class='note'>{_esc(text)}</div>", unsafe_allow_html=True)


def warn(text: str) -> None:
    st.markdown(f"<div class='warn'>{_esc(text)}</div>", unsafe_allow_html=True)


def section(title: str, hint: str = "") -> None:
    st.markdown(f"#### {title}")
    if hint:
        note(hint)


# =====================================================================
# 패널 — 한 제목이 하나의 테두리를 갖게 하는 그릇
# =====================================================================
# ⚠ **Streamlit 에서는 여는 <div> 만 따로 뱉는 방법이 없습니다.**
#    `st.markdown` 은 블록마다 자기 래퍼 안에 넣고 브라우저가 태그를 닫아버려서,
#    "여기서 열고 저 아래서 닫기" 가 안 됩니다. 그래서 패널 하나는 **HTML 한
#    덩어리로 한 번에** 그립니다. 아래 `*_html()` 들이 그 조각입니다.
#
#    위젯(셀렉트박스·버튼)이 들어가야 하는 자리는 패널로 감쌀 수 없습니다.
#    그런 곳은 `section()` 을 그대로 씁니다.


def kcard_html(value: str, label: str, sub: str = "", tone: str = "") -> str:
    """값 하나 + 그게 무슨 뜻인지 한 줄. tone: "" | "up" | "down"."""
    cls = f"kcard {tone}".strip()
    sub_html = f"<div class='s'>{_esc(sub)}</div>" if sub else ""
    return (f"<div class='{cls}'>"
            f"<div class='v' style='{fit_style(value)}'>{_esc(value)}</div>"
            f"<div class='l'>{_esc(label)}</div>{sub_html}</div>")


def paycard_html(amount: str, caption: str, label: str,
                 subs: list[tuple[str, str]], badge: str = "") -> str:
    """월급 카드.

    `badge` — 큰 금액 **바로 옆**에 붙는 작은 알약. 그 금액에서 바로 나온
    값만 넣습니다. 기준이 다른 값을 옆에 붙이면 사람들은 무조건 큰 금액에서
    나온 값으로 읽습니다.
    """
    sub_html = "".join(
        f"<div><div class='k'>{_esc(k)}</div><div class='n'>{_esc(v)}</div></div>"
        for k, v in subs
    )
    tag = f"<span class='vb'>{_esc(badge)}</span>" if badge else ""
    return (f"<div class='paycard'><div class='cap'>{_esc(caption)}</div>"
            f"<div class='v'>{_esc(amount)}{tag}</div>"
            f"<div class='l'>{_esc(label)}</div>"
            f"<div class='sub'>{sub_html}</div></div>")


def row_html(name: str, subtitle: str, amount: str, amount_sub: str = "",
             chip: str = "", links: list[tuple[str, str]] | None = None,
             sub_tone: str = "") -> str:
    """목록 한 줄.

    `sub_tone` — 오른쪽 아래 작은 글씨의 색. "up"(빨강) | "down"(파랑) | "".
    손익을 회색으로 두면 플러스인지 마이너스인지 눈으로 안 잡힙니다.
    """
    chips = f"<span class='chip'>{_esc(chip)}</span>" if chip else ""
    if links:
        chips += linkchips(links)
    sub_cls = f"sb {sub_tone}".strip()
    sub = f"<div class='{sub_cls}'>{_esc(amount_sub)}</div>" if amount_sub else ""
    return (f"<div class='row'><div><div class='nm'>{_esc(name)}{chips}</div>"
            f"<div class='sb'>{_esc(subtitle)}</div></div>"
            f"<div class='rt'><div class='amt'>{_esc(amount)}</div>{sub}</div></div>")


def grid_html(cards: list[str], cols: int = 3) -> str:
    """카드 여러 장을 한 격자에. 좁은 화면에서는 CSS 가 알아서 접습니다."""
    return f"<div class='grid c{int(cols)}'>{''.join(cards)}</div>"


def panel(title: str, body: str, hint: str = "") -> None:
    """제목 하나 + 그 아래 내용을 **테두리 하나**로 감싸 그립니다.

    `body` 는 위의 `*_html()` 들을 이어 붙인 문자열입니다.
    """
    head = f"<div class='panel-h'>{_esc(title)}</div>" if title else ""
    sub = f"<div class='panel-s'>{_esc(hint)}</div>" if hint else ""
    st.markdown(f"<div class='panel'>{head}{sub}<div class='panel-b'>{body}</div></div>",
                unsafe_allow_html=True)


def goalbar_html(percent: float, expected_percent: float = 0.0) -> str:
    """목표 진행 막대.

    **받은 돈**은 진한 색, **들어올 것으로 보이는 돈**은 흐린 색으로 잇대어
    그립니다. 섞어 버리면 "벌써 다 받은 것" 처럼 보입니다 — 예상은 예상이라고
    눈에도 구분되어야 합니다.

    100% 를 넘으면 막대는 가득 차고 숫자로 넘긴 만큼을 보여줍니다.
    """
    got = max(0.0, min(100.0, percent))
    more = max(0.0, min(100.0 - got, expected_percent - percent))
    return (f"<div class='goalbar'>"
            f"<i class='got' style='width:{got:.1f}%'></i>"
            f"<i class='more' style='width:{more:.1f}%'></i></div>")

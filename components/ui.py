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

import streamlit as st

import config

# 색은 한 곳에서만 정합니다. 여기 안 거치고 코드에 색을 직접 쓰지 마세요.
CSS = """
<style>
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

  /* ---- 값 카드 — 테두리 없이 은은한 채움만 ---- */
  .kcard { background:var(--tint); border:none; border-radius:14px;
           padding:16px 18px; height:100%; }
  .kcard .v { font-size:1.5rem; font-weight:800; color:var(--ink);
              letter-spacing:-.035em; font-variant-numeric: tabular-nums;
              line-height:1.15; }
  .kcard .l { font-size:.8rem; color:var(--ink-soft); margin-top:5px; }
  .kcard .s { font-size:.74rem; color:var(--ink-faint); margin-top:7px; }
  .kcard.up .v  { color:var(--up); }
  .kcard.down .v{ color:var(--down); }

  /* ---- 이번 달 월급 — 화면에서 가장 무거운 한 덩어리 ----
     파랑 그라디언트를 먹색 단색으로 바꿨습니다. 그라디언트는 시선을 끄는
     대신 화면을 시끄럽게 합니다. 한 덩어리가 조용히 무거운 편이 낫습니다. */
  .paycard { background:var(--ink); border-radius:16px; padding:22px 24px; color:#fff; }
  .paycard .cap { font-size:.8rem; opacity:.7; font-weight:600; }
  .paycard .v { font-size:2.5rem; font-weight:800; letter-spacing:-.045em;
                margin:.18rem 0 .1rem; font-variant-numeric: tabular-nums;
                line-height:1.05; }
  .paycard .l { font-size:.8rem; opacity:.66; }
  .paycard .sub { margin-top:16px; padding-top:13px;
                  border-top:1px solid rgba(255,255,255,.16);
                  display:flex; gap:26px; flex-wrap:wrap; }
  .paycard .sub .k { font-size:.72rem; opacity:.6; }
  .paycard .sub .n { font-size:1.02rem; font-weight:700; margin-top:2px;
                     font-variant-numeric: tabular-nums; }

  /* ---- 목록 한 줄 ---- */
  .row { display:flex; align-items:center; justify-content:space-between;
         padding:11px 2px; border-bottom:1px solid var(--line-soft); gap:12px; }
  .row:last-child { border-bottom:none; }
  .row .nm { font-weight:700; color:var(--ink); font-size:.92rem; }
  .row .sb { font-size:.76rem; color:var(--ink-faint); margin-top:2px; }
  .row .rt { text-align:right; white-space:nowrap; }
  .row .amt { font-weight:700; font-variant-numeric: tabular-nums; }

  .chip { display:inline-block; font-size:.7rem; font-weight:700; border-radius:999px;
          padding:2px 8px; background:var(--tint-deep); color:var(--ink-soft);
          margin-left:6px; white-space:nowrap; }
  a.chip.link { color:var(--ink-soft); text-decoration:none; border:1px solid var(--line);
                background:var(--panel); }
  a.chip.link:hover { background:var(--tint); color:var(--ink); }

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

  .note { font-size:.78rem; color:var(--ink-faint); }
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

  @media (max-width: 720px) {
    .grid.c3, .grid.c4 { grid-template-columns:repeat(2,1fr); }
  }
  @media (max-width: 460px) {
    .panel { padding:16px 15px; border-radius:15px; }
    .grid.c2, .grid.c3, .grid.c4 { grid-template-columns:1fr; }
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


def kcard(value: str, label: str, sub: str = "", tone: str = "") -> None:
    """숫자 하나 + 그게 무슨 뜻인지 한 줄. tone: "" | "up" | "down"."""
    cls = f"kcard {tone}".strip()
    sub_html = f"<div class='s'>{_esc(sub)}</div>" if sub else ""
    st.markdown(
        f"<div class='{cls}'><div class='v'>{_esc(value)}</div>"
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


def linkchips(links: list[tuple[str, str]]) -> str:
    """(이름, 주소) 목록을 바로가기 칩 HTML 로. 한 곳에서 만들어야 목록과
    상세 화면의 칩이 따로 놀지 않습니다.

    ⚠ 칩 글자는 짧게 두세요. "Npay증권(PC·모바일)" 처럼 길게 달았더니 종목명이
    조금만 길어져도 칩이 다음 줄로 밀렸습니다. 설명은 툴팁으로 답니다.
    """
    return "".join(
        f"<a class='chip link' href='{_esc(url)}' target='_blank' rel='noopener'"
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
    return (f"<div class='{cls}'><div class='v'>{_esc(value)}</div>"
            f"<div class='l'>{_esc(label)}</div>{sub_html}</div>")


def paycard_html(amount: str, caption: str, label: str,
                 subs: list[tuple[str, str]]) -> str:
    sub_html = "".join(
        f"<div><div class='k'>{_esc(k)}</div><div class='n'>{_esc(v)}</div></div>"
        for k, v in subs
    )
    return (f"<div class='paycard'><div class='cap'>{_esc(caption)}</div>"
            f"<div class='v'>{_esc(amount)}</div><div class='l'>{_esc(label)}</div>"
            f"<div class='sub'>{sub_html}</div></div>")


def row_html(name: str, subtitle: str, amount: str, amount_sub: str = "",
             chip: str = "", links: list[tuple[str, str]] | None = None) -> str:
    """목록 한 줄."""
    chips = f"<span class='chip'>{_esc(chip)}</span>" if chip else ""
    if links:
        chips += linkchips(links)
    sub = f"<div class='sb'>{_esc(amount_sub)}</div>" if amount_sub else ""
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

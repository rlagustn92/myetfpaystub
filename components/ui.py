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
  :root {
    --ink:        #111418;
    --ink-soft:   #5C6470;
    --ink-faint:  #8A9199;
    --line:       #E7EAEE;
    --card:       #FFFFFF;
    --bg-soft:    #F5F7FA;
    --brand:      #1454FF;
    --up:         #E3342F;   /* 한국 관습: 오른 것이 빨강 */
    --down:       #1266F1;
    --warn-bg:    #FFF8E6;
    --warn-line:  #F2D48A;
  }

  /* 기본 여백을 줄여서 첫 화면에 핵심 숫자가 다 들어오게 합니다. */
  .block-container { padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1080px; }

  .app-head { display:flex; align-items:baseline; gap:10px; flex-wrap:wrap; }
  .app-title { font-size: 1.45rem; font-weight: 800; color: var(--ink); margin:0;
               letter-spacing:-.02em; }
  .app-ver { font-size:.78rem; font-weight:700; color:var(--ink-faint);
             background:var(--bg-soft); border-radius:999px; padding:2px 8px; }
  .app-tag { font-size:.9rem; color:var(--ink-soft); margin:.25rem 0 0; }

  /* 오른쪽 위 방문자 수 */
  .visitors { display:flex; justify-content:flex-end; gap:14px; padding-top:12px;
              font-size:12.5px; color:#8a8f98;
              font-variant-numeric: tabular-nums;   /* 숫자 폭 고정 — 갱신될 때 안 흔들림 */
              white-space:nowrap; }
  .visitors b { font-size:11px; font-weight:700; letter-spacing:.04em;
                color:#8a8f98; margin-right:3px; }

  /* 값 + 설명 카드 */
  .kcard { background:var(--card); border:1px solid var(--line); border-radius:16px;
           padding:18px 20px; height:100%; }
  .kcard .v { font-size:1.6rem; font-weight:800; color:var(--ink);
              letter-spacing:-.03em; font-variant-numeric: tabular-nums; }
  .kcard .l { font-size:.82rem; color:var(--ink-soft); margin-top:4px; }
  .kcard .s { font-size:.78rem; color:var(--ink-faint); margin-top:8px; }
  .kcard.up .v  { color:var(--up); }
  .kcard.down .v{ color:var(--down); }

  /* 이번 달 월급 — 화면에서 제일 큰 카드 */
  .paycard { background:linear-gradient(135deg,#1454FF 0%,#3E7BFF 100%);
             border-radius:20px; padding:24px 26px; color:#fff; }
  .paycard .cap { font-size:.9rem; opacity:.85; font-weight:600; }
  .paycard .v { font-size:2.6rem; font-weight:800; letter-spacing:-.04em;
                margin:.15rem 0 .1rem; font-variant-numeric: tabular-nums; }
  .paycard .l { font-size:.85rem; opacity:.9; }
  .paycard .sub { margin-top:14px; padding-top:12px; border-top:1px solid rgba(255,255,255,.25);
                  display:flex; gap:26px; flex-wrap:wrap; }
  .paycard .sub .k { font-size:.75rem; opacity:.85; }
  .paycard .sub .n { font-size:1.05rem; font-weight:700;
                     font-variant-numeric: tabular-nums; }

  /* 목록 한 줄 */
  .row { display:flex; align-items:center; justify-content:space-between;
         padding:12px 4px; border-bottom:1px solid var(--line); }
  .row:last-child { border-bottom:none; }
  .row .nm { font-weight:700; color:var(--ink); font-size:.95rem; }
  .row .sb { font-size:.78rem; color:var(--ink-faint); margin-top:2px; }
  .row .rt { text-align:right; }
  .row .amt { font-weight:700; font-variant-numeric: tabular-nums; }

  .chip { display:inline-block; font-size:.72rem; font-weight:700; border-radius:999px;
          padding:2px 8px; background:var(--bg-soft); color:var(--ink-soft);
          margin-left:6px; white-space:nowrap; }
  a.chip.link { color:var(--brand); text-decoration:none; border:1px solid #D7E3FF;
                background:#F3F7FF; }
  a.chip.link:hover { background:#E6EFFF; }

  .note { font-size:.8rem; color:var(--ink-faint); }
  .warn { background:var(--warn-bg); border:1px solid var(--warn-line); border-radius:12px;
          padding:10px 14px; font-size:.85rem; color:#7A5B00; }

  /* 분배금 달력 */
  .cal { display:grid; grid-template-columns:repeat(7,1fr); gap:6px; }
  .cal .h { text-align:center; font-size:.72rem; color:var(--ink-faint); padding:4px 0; }
  .cal .d { border:1px solid var(--line); border-radius:10px; min-height:62px;
            padding:6px 7px; background:var(--card); }
  .cal .d.empty { border:none; background:transparent; }
  .cal .d .n { font-size:.72rem; color:var(--ink-faint); }
  .cal .d .m { font-size:.78rem; font-weight:800; color:var(--brand); margin-top:6px;
               font-variant-numeric: tabular-nums; line-height:1.2; }
  .cal .d.pay { background:#F3F7FF; border-color:#CFE0FF; }

  @media (max-width: 640px) {
    .paycard .v { font-size:2.1rem; }
    .kcard .v { font-size:1.35rem; }
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


def listrow(name: str, subtitle: str, amount: str, amount_sub: str = "",
            chip: str = "", link: str = "", link_text: str = "Npay증권 ↗") -> None:
    """목록 한 줄. `link` 를 주면 이름 옆에 작은 바로가기 칩이 붙습니다.

    ⚠ 칩 글자는 짧게 두세요. "Npay증권(PC·모바일)" 처럼 길게 달았더니 종목명이
    조금만 길어져도 칩이 다음 줄로 밀렸습니다. 설명은 툴팁으로 답니다.
    """
    chip_html = f"<span class='chip'>{_esc(chip)}</span>" if chip else ""
    if link:
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


def note(text: str) -> None:
    st.markdown(f"<div class='note'>{_esc(text)}</div>", unsafe_allow_html=True)


def warn(text: str) -> None:
    st.markdown(f"<div class='warn'>{_esc(text)}</div>", unsafe_allow_html=True)


def section(title: str, hint: str = "") -> None:
    st.markdown(f"#### {title}")
    if hint:
        note(hint)

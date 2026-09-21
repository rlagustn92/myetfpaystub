"""
app.py  --  MY ETF 급여명세서 (화면)
=====================================

계산은 전부 services/ 에 있습니다. 이 파일은 **보여주는 일만** 합니다.

화면을 열었을 때 5초 안에 이 두 가지를 알 수 있어야 합니다.
    1. 내 ETF 가 지금 얼마인가
    2. 이번 달에 얼마가 들어오는가

⚠ Streamlit 에서 `app.py` 만 핫리로드됩니다. services/ · config.py · models/ 를
고쳤으면 서버를 다시 켜야 합니다. 이걸 모르면 "왜 안 바뀌지?" 로 시간을 날립니다.
"""

from __future__ import annotations

import re
import warnings
from calendar import monthrange
from datetime import date

warnings.filterwarnings("ignore")   # yfinance/pandas 의 FutureWarning 이 화면에 뜨지 않게

import pandas as pd
import streamlit as st

import config
import formatting as F
from components import pitch_grid
from components.football_pitch import football_pitch
from components.local_store import local_store
from components.ui import (
    header,
    inject_css,
    kcard,
    linkchips,
    listrow,
    note,
    paycard,
    section,
    skin_gallery,
    warn,
)
from data.providers import cache
from data.providers.issuer import base as issuer_base
from models.portfolio import MARKET_KR, MARKET_US, Holding
from services import (
    cashflow_service as CF,
    distribution_service as DS,
    fx_service,
    link_service,
    naver_link_service,
    pitch_service,
    portfolio_service as PS,
    search_service,
    share_service,
    skin_service,
    storage_service as STORE,
    visitor_service,
)

st.set_page_config(page_title=config.PAGE_TITLE, page_icon=config.APP_ICON,
                   layout="wide", initial_sidebar_state="collapsed")
inject_css()


# =====================================================================
# 1. 브라우저 저장소에서 복원  — ⚠ 위젯을 하나라도 만들기 전에 해야 합니다
# =====================================================================
_restored = local_store(mode="read", key="ls_read")

if "store" not in st.session_state:
    st.session_state["store"] = STORE.new_store()
    st.session_state["storage_writable"] = True
    st.session_state["restored"] = False

if (not st.session_state["restored"]) and isinstance(_restored, dict) \
        and _restored.get("mode") == "read":
    st.session_state["restored"] = True
    st.session_state["storage_writable"] = bool(_restored.get("writable", True))
    text = _restored.get("data")
    if text:
        loaded, err = STORE.loads(text)
        if loaded is not None:
            st.session_state["store"] = loaded
        else:
            st.session_state["restore_error"] = err

store: STORE.Store = st.session_state["store"]
portfolio = store.active()


# =====================================================================
# 2. 방문자 수 — ⚠ 세션당 한 번만 (안 그러면 클릭할 때마다 +1)
# =====================================================================
if "visitor_counts" not in st.session_state:
    st.session_state["visitor_counts"] = visitor_service.count_visit()

header(st.session_state["visitor_counts"])

if st.session_state.get("restore_error"):
    warn(f"저장해 둔 내용을 불러오지 못했습니다 — {st.session_state.pop('restore_error')}")


# =====================================================================
# 3. 데이터 준비
# =====================================================================
def load_market_data():
    """현재가 · 환율 · 분배금. 전부 TTL 캐시를 타므로 매 렌더마다 네트워크를 타지 않습니다."""
    quotes = PS.fetch_quotes(portfolio)
    fx = fx_service.latest()
    summary = PS.summarize(portfolio, quotes=quotes, usdkrw=fx.rate if fx else None)
    dists = DS.fetch_all(portfolio)
    return summary, dists, fx


has_holdings = bool(portfolio.holdings)
summary = dists = fx = None
if has_holdings:
    with st.spinner("가격과 분배금을 확인하고 있습니다…"):
        summary, dists, fx = load_market_data()

today = config.today_local()


# =====================================================================
# 4. 빈 화면 — 처음 온 사람에게 다음에 뭘 눌러야 하는지 말해 줍니다
# =====================================================================
def render_empty() -> None:
    st.markdown("### 아직 등록된 ETF 가 없습니다")
    note("증권사에 흩어져 있는 ETF 를 하나씩 등록하면, 전부 합쳐서 "
         "지금 얼마이고 매달 얼마가 들어오는지 보여드립니다.")
    st.write("")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**① 아래 `➕ 내 ETF 추가` 에서 등록하기**")
        note("증권사 · 계좌 · 종목 · 수량 · 평균 매입가격, 다섯 가지만 넣으면 됩니다.")
    with c2:
        st.markdown("**② 어떤 화면인지 먼저 보고 싶다면**")
        if st.button("예시로 시작해보기", type="secondary", width="stretch"):
            for t, mk, nm, br, ac, sh, ap in [
                ("069500", MARKET_KR, "KODEX 200", "미래에셋증권", "ISA", 100, 32000),
                ("498400", MARKET_KR, "KODEX 200타겟위클리커버드콜", "키움증권", "일반", 500, 20000),
                ("402970", MARKET_KR, "ACE 미국배당다우존스", "미래에셋증권", "연금저축", 300, 11000),
                ("SCHD", MARKET_US, "Schwab US Dividend Equity ETF", "키움증권", "일반", 180, 30.5),
            ]:
                portfolio.add(Holding(ticker=t, market=mk, name=nm, broker=br,
                                      account=ac, account_type=ac, shares=sh, avg_price=ap))
            st.rerun()


# =====================================================================
# 5. 홈
# =====================================================================
def render_home() -> None:
    # -- 맨 위 세 숫자 --------------------------------------------------
    c1, c2, c3 = st.columns(3)
    with c1:
        kcard(F.won(summary.total_value_krw), "지금 내 ETF 자산",
              f"{len(portfolio.holdings)}개 계좌 · {len(portfolio.tickers())}개 종목")
    with c2:
        kcard(F.won(summary.total_cost_krw), "내가 넣은 돈",
              "입력한 평균 매입가격 기준")
    with c3:
        profit = summary.total_profit_krw
        kcard(F.won_signed(profit), "지금까지 벌거나 잃은 돈",
              F.pct_signed(summary.profit_rate) if summary.profit_rate is not None else "",
              tone="up" if profit > 0 else ("down" if profit < 0 else ""))

    if summary.has_missing:
        names = ", ".join(sorted({m.holding.name or m.holding.ticker
                                  for m in summary.missing}))
        warn(f"{names} 은(는) 지금 가격을 확인하지 못해 위 합계에서 빠졌습니다. "
             f"0원으로 세지 않았습니다. 잠시 뒤 '🔄 정보 업데이트' 를 눌러 보세요.")

    st.write("")

    # -- 이번 달 ETF 월급 ------------------------------------------------
    this_month = CF.month_total(portfolio, dists, today.year, today.month,
                                latest_rate=summary.usdkrw)
    left, right = st.columns([3, 2])
    with left:
        subs = [("세금 계산에 잡히는 금액", F.won(this_month.tax_basis_krw))]
        if this_month.tax_basis_is_partial:
            subs.append(("자료가 없는 건", f"{this_month.unknown_tax_basis_rows}건"))
        paycard(
            F.won(this_month.amount_krw),
            f"💰 {today.year}년 {today.month}월 ETF 월급",
            "이번 달에 들어오는(들어온) 분배금 합계"
            + (" · 일부는 예상값입니다" if this_month.has_estimate else ""),
            subs,
        )
    with right:
        year = CF.year_total(portfolio, dists, today.year, latest_rate=summary.usdkrw)
        kcard(F.won(year.amount_krw), f"{today.year}년에 지금까지 받은 ETF 월급",
              f"세금 계산 기준 {F.won(year.tax_basis_krw)} · "
              f"세금에 안 잡힌 금액 {F.won(year.non_taxed_krw)}")
        st.write("")
        ny, nm = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
        nxt = CF.month_total(portfolio, dists, ny, nm, latest_rate=summary.usdkrw)
        kcard(F.won(nxt.amount_krw) if nxt.rows else config.NO_DATA_TEXT,
              f"{nm}월에 들어올 것으로 보이는 돈",
              "🟡 예상값입니다. 실제 발표 금액과 다를 수 있습니다." if nxt.has_estimate
              else ("확정된 지급만 있습니다" if nxt.rows else "아직 알 수 있는 게 없습니다"))

    if this_month.tax_basis_is_partial or year.tax_basis_is_partial:
        note("※ '세금 계산에 잡히는 금액' 은 운용사가 발표한 자료가 있는 건만 더한 값입니다. "
             "아직 발표 전이거나 자료를 확인할 수 없는 건은 0원으로 세지 않고 빼두었습니다.")

    st.write("")

    # -- 이번 달 지급 내역 -----------------------------------------------
    section(f"{today.month}월 지급 내역",
            "날짜 · 종목 · 어느 증권사로 들어오는지" if this_month.rows else "")
    if not this_month.rows:
        note("이번 달에는 예정된 분배금이 없습니다. (자료가 없는 종목은 여기에 안 나옵니다)")
    else:
        if any(r.record_note for r in this_month.rows):
            note("※ '기준' 날짜는 그날 갖고 있어야 받는다는 뜻입니다. "
                 "월말이 기준인 ETF 는 돈이 다음 달 초에 들어와서, "
                 "여기에는 들어온 달 기준으로 적혀 있습니다.")
        for r in this_month.rows:
            listrow(
                f"{F.md(r.payment_date)}  {r.name}",
                f"{r.holding.where()} · {F.shares(r.holding.shares)}"
                + (f" · {r.record_note}" if r.record_note else ""),
                F.won(r.amount_krw),
                f"세금 기준 {F.won(r.tax_basis_krw)}" if r.has_tax_basis
                else f"세금 기준 {r.tax_basis_note}",
                chip="예상" if r.is_estimated else "",
            )

    st.write("")

    # -- 증권사별 --------------------------------------------------------
    section("내 돈은 어디에 있나요?", "증권사를 누르면 계좌별로 쪼개서 볼 수 있습니다.")
    for g in PS.group_by_broker(summary):
        share = (f" · 전체의 {g.value_krw / summary.total_value_krw * 100:.0f}%"
                 if summary.total_value_krw > 0 else "")
        with st.expander(f"**{g.broker}**　{F.won(g.value_krw)}{share}"):
            for account, value in sorted(g.accounts.items(), key=lambda x: -x[1]):
                st.markdown(f"**{account}** — {F.won(value)}")
                for r in g.rows:
                    if (r.holding.account or "계좌 미지정") != account:
                        continue
                    listrow(r.holding.name or r.holding.ticker,
                            f"{F.shares(r.holding.shares)} · 평균 "
                            f"{F.native_amt(r.holding.avg_price, r.holding.currency)}",
                            F.won(r.value_krw(summary.usdkrw)),
                            F.won_signed(r.profit_krw(summary.usdkrw))
                            if r.profit_krw(summary.usdkrw) is not None else "")

    st.write("")

    # -- 내 ETF 목록 -----------------------------------------------------
    section("내 ETF")
    for g in PS.group_by_ticker(summary):
        v = g.value_krw(summary.usdkrw)
        c = g.cost_krw(summary.usdkrw)
        profit = (v - c) if (v is not None and c is not None) else None
        places = len({r.holding.where() for r in g.rows})
        listrow(
            g.name,
            f"{F.shares(g.total_shares)} · 평균 {F.native_amt(g.avg_price, g.currency)}"
            + (f" · {places}개 계좌에 나눠 보유" if places > 1 else ""),
            F.won(v) if v is not None else config.NO_DATA_TEXT,
            F.won_signed(profit) if profit is not None else "",
            # 차트·뉴스처럼 이 앱이 안 만드는 건 증권사 화면으로 넘깁니다.
            # 만들 수 있는 주소만 옵니다(빈 페이지로 보내지 않으려고).
            links=link_service.links_for(g.market, g.ticker),
        )

    st.write("")
    render_pitch(this_month, year)


# =====================================================================
# 5-1. 전술판 — 내가 가진 걸 한 장의 그림으로
# =====================================================================
def is_admin() -> bool:
    """관리자(= 앱 주인)인가. 전체에 영향을 주는 기능을 가립니다.

    주소 뒤에 `?admin=<키>` 를 붙였을 때만 True. 키는 secrets 의 `ADMIN_KEY`
    와 비교합니다. **로그인이 아니라 "남이 실수로 못 누르게" 하는 가림막**입니다.

    ⚠ `ADMIN_KEY` 를 안 넣으면 항상 관리자로 봅니다(개인 PC 에서 혼자 쓸 때).
       배포본에서 가리려면 Streamlit Cloud 의 Secrets 에 키를 넣어야 합니다.
    ⚠ 키를 **코드에 적으면 안 됩니다.** 저장소가 공개라 그대로 노출됩니다.
    """
    try:
        expected = str(st.secrets.get("ADMIN_KEY", "") or "")
    except Exception:  # noqa: BLE001 - secrets 파일이 없어도 로컬에서 돌아야 합니다
        expected = ""
    if not expected:
        return True
    return st.query_params.get(config.ADMIN_QUERY_KEY) == expected


def render_pitch(this_month: CF.PeriodTotal, year_total: CF.PeriodTotal) -> None:
    """축구 전술판 위에 내 보유 ETF 를 세웁니다.

    등번호는 **내 ETF 자산에서 그 종목이 차지하는 비율**입니다. 사용자가 비중을
    입력하는 게 아니라 수량 × 현재가로 저절로 정해집니다.

    자리는 끌어서 바꿀 수 있고, 바꾼 자리는 저장 파일에 같이 남습니다.
    이건 평가나 추천이 아니라 **내가 가진 걸 한눈에 보는 그림**일 뿐입니다.
    """
    section("⚽ 내 포트폴리오 전술판",
            "유니폼 숫자 = 내 ETF 자산에서 그 종목이 차지하는 비율 · "
            "흰 유니폼 = 미국 종목 · C = 지금 가장 많이 들고 있는 종목. "
            "카드를 끌어다 자리를 바꿀 수 있습니다.")

    render_skin_picker()

    groups = PS.group_by_ticker(summary)
    pitch_service.prune_slots(portfolio)          # 판 종목의 자리를 비웁니다
    pitch_service.ensure_slots(portfolio, groups)  # 새 종목에 자리를 줍니다
    render_tidy_bar(groups)
    payload = pitch_service.build_players(summary, portfolio, groups)

    # 📸 이미지와 📋 텍스트는 **같은 줄**에서 만듭니다. 따로 만들면 같은
    # 포트폴리오를 두 군데 올렸을 때 숫자가 어긋나 보입니다.
    month_label = f"{today.month}월"
    rows = pitch_service.share_rows(summary, groups, this_month)

    capture_summary = {
        "cells": [
            {"k": "내 ETF 자산", "v": F.won_short(summary.total_value_krw)},
            {"k": f"{month_label} ETF 월급", "v": F.won_short(this_month.amount_krw)},
            {"k": f"{today.year}년 누적", "v": F.won_short(year_total.amount_krw)},
            {"k": "세금 계산 기준", "v": F.won_short(year_total.tax_basis_krw)},
        ],
        "note": f"※ 참고용 · 실제 입금액·세금은 증권사 내역과 다를 수 있음 · "
                f"{today:%Y-%m-%d} 기준",
        "key_note": "유니폼 숫자 = 내 ETF 자산에서 차지하는 비율 · 흰 유니폼 = 미국 종목",
    }
    capture_legend = [
        {"name": r.name, "amount": r.amount_text(month_label),
         "color": r.color, "us": r.is_us}
        for r in rows
    ]
    comment = share_service.comment_text(
        portfolio_name=portfolio.name, rows=rows,
        total_value_krw=summary.total_value_krw,
        month_krw=this_month.amount_krw, month_label=month_label,
        year_krw=year_total.amount_krw, year_tax_basis_krw=year_total.tax_basis_krw,
        today=today,
    )

    # 전술판을 가운데로 모으되 넉넉하게 씁니다. 카드에 반바지·양말이 붙어 세로로
    # 길어졌기 때문에, 판이 좁으면 위아래 줄끼리 카드가 겹칩니다.
    # 비율(세로/가로)도 실제 축구장에 가깝게 늘렸습니다(96/72=1.33 -> 1.45).
    skin_now = skin_service.current(portfolio)
    _, mid, _ = st.columns([1, 8, 1])
    with mid:
        result = football_pitch(
            players=payload.players,
            slots=pitch_grid.slot_meta(),
            height=1100,
            aspect_ratio=1.45,
            # 골대 뒤 배너 — 위는 **그 나라 말 응원 구호**, 아래는 서비스 이름.
            # 영어 스킨 이름을 적었더니 팀이 전혀 연상되지 않아서 바꿨습니다.
            # (스킨 이름은 📸 캡처 이미지 아래에 따로 새겨집니다)
            banner_top=skin_now.chant or skin_now.name.replace(" Edition", ""),
            banner_bottom=skin_now.chant_home or config.APP_NAME,
            summary=capture_summary,
            legend=capture_legend,
            footer=f"{config.APP_ICON} {config.APP_NAME} v{config.APP_VERSION}",
            capture_filename=f"내_ETF_전술판_{today:%Y%m%d}.png",
            comment_text=comment,
            skin=skin_now.to_dict(),
            key="pitch",
        )

    if result and pitch_service.apply_assignments(portfolio, result.get("assignments") or {}):
        st.rerun()

    if payload.unpriced:
        note(f"※ {', '.join(payload.unpriced)} 은(는) 지금 가격을 확인하지 못해 "
             f"등번호를 비워 두었습니다. 0% 라는 뜻이 아닙니다.")
    if payload.no_slot:
        warn(f"전술판 자리는 {len(pitch_grid.all_slots())}개뿐이라 "
             f"{', '.join(payload.no_slot)} 은(는) 판에 세우지 못했습니다. "
             f"위 '내 ETF' 목록에는 그대로 다 있습니다.")


def render_tidy_bar(groups) -> None:
    """⚽ 포지션 자동 정리 버튼 + 지금 포메이션.

    ⚠ 정리는 **버튼을 눌렀을 때만** 합니다. 화면을 열 때마다 자동으로 하면
      사용자가 손으로 끌어다 맞춰둔 배치가 말도 없이 흐트러집니다.
    """
    c1, c2 = st.columns([2, 3])
    with c1:
        if st.button("⚽ 포지션 자동 정리", width="stretch",
                     disabled=not groups,
                     help="종목 성격에 맞는 자리로 다시 늘어놓습니다. "
                          "손으로 옮겨둔 자리는 없어집니다."):
            moved = pitch_service.tidy(portfolio, groups)
            if moved:
                st.session_state["tidy_moved"] = moved
                st.rerun()
            else:
                st.session_state["tidy_moved"] = 0
    with c2:
        st.write("")
        shape = pitch_service.formation(portfolio)
        if shape:
            c = pitch_service.formation_counts(portfolio)
            note(f"지금 배치 {shape} — 수비 {c['수비']} · 미드필드 {c['미드필드']} · "
                 f"공격 {c['공격']} (자리에 세운 종목 수입니다)")

    moved = st.session_state.pop("tidy_moved", None)
    if moved:
        st.success(f"{moved}개 종목의 자리를 옮겼습니다.")
    elif moved == 0:
        note("이미 정리되어 있습니다. 옮길 자리가 없었습니다.")


def render_skin_picker() -> None:
    """경기장 스킨 고르기.

    스킨은 **경기장만** 바꿉니다. 유니폼 색은 운용사 브랜드를 나타내는 정보라
    스킨이 물들이지 않습니다(물들이면 어느 운용사 상품인지 못 알아봅니다).
    """
    options = skin_service.available(portfolio)
    # 이름만으로 고릅니다. "London Red Edition — 런던 레드 — 붉은색과 흰색" 처럼
    # 줄표가 두 번 들어가면 읽기 나빠져서, 설명은 아래 한 줄로 따로 답니다.
    labels = {sk.name: sk for sk in options}
    now = skin_service.current(portfolio)
    current_label = next((k for k, v in labels.items() if v.id == now.id),
                         list(labels)[0])

    c1, c2 = st.columns([2, 3])
    with c1:
        picked = st.selectbox("경기장 스킨", list(labels.keys()),
                              index=list(labels).index(current_label), key="skin_pick")
        if skin_service.select(portfolio, labels[picked].id):
            st.rerun()
    with c2:
        st.write("")
        # ⚠ note() 는 글자를 그대로 이스케이프합니다(마크다운이 아닙니다).
        #    여기에 ** 를 쓰면 별표가 그대로 찍힙니다.
        note(f"{labels[picked].korean}")
        # ⚠ v0.9.0 부터 **클럽풍 스킨은 유니폼 몸통까지 팀 색으로** 바꿉니다.
        #    기본 잔디만 몸통을 운용사 색으로 둡니다. 문구가 옛 설명으로
        #    남아 있으면 화면과 말이 달라집니다.
        note("기본 잔디는 유니폼 몸통 색이 운용사입니다. "
             "클럽풍 스킨을 고르면 몸통까지 팀 색이 되고, 운용사는 "
             "이름표 색과 가슴 두 글자로 남습니다.")
        # 접힌 칸 안이 아니라 **항상 보이는 자리**에 둡니다. 의도를 분명히 하는 문구라
        # 사용자가 펼쳐야 보이면 의미가 없습니다.
        note(config.SKIN_DISCLAIMER)

    with st.expander(f"스킨 전체 보기 ({len(options)}개)"):
        skin_gallery(options, now.id)
        note(config.SKIN_DISCLAIMER)


# =====================================================================
# 6. 월별 급여명세서 + 달력
# =====================================================================
def render_payslip() -> None:
    c1, c2 = st.columns([1, 3])
    with c1:
        year = st.number_input("연도", min_value=2000, max_value=2100,
                               value=today.year, step=1, key="ps_year")
        month = st.selectbox("월", list(range(1, 13)), index=today.month - 1, key="ps_month")
    year, month = int(year), int(month)

    total = CF.month_total(portfolio, dists, year, month, latest_rate=summary.usdkrw)

    with c2:
        a, b, c = st.columns(3)
        with a:
            kcard(F.won(total.amount_krw), f"{month}월 ETF 월급",
                  "예상값 포함" if total.has_estimate else "확인된 금액")
        with b:
            kcard(F.won(total.tax_basis_krw), "세금 계산에 잡히는 금액",
                  f"자료 없는 건 {total.unknown_tax_basis_rows}건"
                  if total.tax_basis_is_partial else "전부 확인됨")
        with c:
            kcard(F.won(total.non_taxed_krw), "세금에 안 잡힌 금액",
                  "과세표준 자료가 있는 건만 계산")

    st.write("")
    section(f"{year}년 {month}월 급여명세서")
    if not total.rows:
        note("이 달에는 지급 내역이 없습니다.")
    else:
        st.dataframe(
            [
                {
                    "날짜": F.md(r.payment_date),
                    "ETF": r.name,
                    "증권사": r.holding.broker or "-",
                    "계좌": r.holding.account or "-",
                    "수량": F.shares(r.holding.shares),
                    "받는 금액": F.won(r.amount_krw),
                    "세금 계산 기준": (F.won(r.tax_basis_krw) if r.has_tax_basis
                                  else r.tax_basis_note),
                    # 월말이 기준인 ETF 는 돈이 다음 달 초에 들어옵니다.
                    # 기준일을 같이 보여주지 않으면 "왜 이 달에 있지?" 가 됩니다.
                    "지급기준일": (F.ymd(r.dist.record_date) if r.dist.record_date
                              else config.NO_DATA_TEXT),
                    "": "🟡 예상" if r.is_estimated else "🟢 확인",
                }
                for r in total.rows
            ],
            width="stretch", hide_index=True,
        )

    st.write("")
    render_calendar(year, month, total)

    st.write("")
    section(f"{year}년 월별 추이", "막대가 높을수록 그 달에 많이 들어온 달입니다.")
    series = CF.monthly_series(portfolio, dists, year, latest_rate=summary.usdkrw)
    # ⚠ 라벨을 "1월".."12월" 로 두면 문자열 순으로 정렬돼 10·11·12월이 앞으로 갑니다.
    #    두 자리로 맞춰야("01월") 1월부터 제대로 늘어섭니다.
    st.bar_chart(
        pd.DataFrame({"ETF 월급(원)": [t.amount_krw for _, t in series]},
                     index=[f"{m:02d}월" for m, _ in series]),
        height=220,
    )


def render_calendar(year: int, month: int, total: CF.PeriodTotal) -> None:
    """분배금 달력. 돈이 들어오는 날을 눈으로 찾게 해 줍니다."""
    section(f"{month}월 분배금 달력")
    by_day = CF.calendar_of(total.rows)
    first_weekday, days_in_month = monthrange(year, month)   # 월요일=0
    # 한국 달력은 일요일부터 시작합니다.
    lead = (first_weekday + 1) % 7

    cells = ["<div class='cal'>"]
    for name in ("일", "월", "화", "수", "목", "금", "토"):
        cells.append(f"<div class='h'>{name}</div>")
    for _ in range(lead):
        cells.append("<div class='d empty'></div>")
    for day in range(1, days_in_month + 1):
        d = date(year, month, day)
        got = by_day.get(d)
        if got:
            mark = "🟡" if got.has_estimate else ""
            cells.append(f"<div class='d pay'><div class='n'>{day}</div>"
                         f"<div class='m'>+{F.won_short(got.amount_krw)}{mark}</div></div>")
        else:
            cells.append(f"<div class='d'><div class='n'>{day}</div></div>")
    cells.append("</div>")
    st.markdown("".join(cells), unsafe_allow_html=True)

    if by_day:
        picked = st.selectbox(
            "날짜를 고르면 그날 들어오는 종목을 볼 수 있습니다",
            sorted(by_day.keys()),
            format_func=lambda d: f"{d.month}월 {d.day}일 — {F.won(by_day[d].amount_krw)}",
            key=f"cal_{year}_{month}",
        )
        for r in by_day[picked].rows:
            listrow(r.name,
                    f"{r.holding.where()} · {F.shares(r.holding.shares)}"
                    + (f" · {r.record_note}" if r.record_note else ""),
                    F.won(r.amount_krw),
                    f"세금 기준 {F.won(r.tax_basis_krw)}" if r.has_tax_basis
                    else f"세금 기준 {r.tax_basis_note}",
                    chip="예상" if r.is_estimated else "")


# =====================================================================
# 7. 종목별 상세
# =====================================================================
def render_detail() -> None:
    groups = PS.group_by_ticker(summary)
    if not groups:
        note("등록된 종목이 없습니다.")
        return
    labels = {f"{g.name} ({g.ticker})": g for g in groups}
    picked = st.selectbox("종목", list(labels.keys()), key="detail_pick")
    g = labels[picked]
    td = dists.get((g.market, g.ticker))

    st.markdown(f"### {g.name}")
    # 차트·뉴스처럼 이 앱이 안 만드는 것은 증권사 화면으로 넘깁니다.
    # 만들 수 있는 주소만 옵니다(빈 페이지로 보내지 않으려고).
    links = link_service.links_for(g.market, g.ticker)
    where = "미국" if g.market == MARKET_US else "한국"
    if links:
        st.markdown(
            f"<span class='note'>{g.ticker} · {where} 상장</span>&nbsp;&nbsp;"
            + linkchips(links),
            unsafe_allow_html=True,
        )
    else:
        note(f"{g.ticker} · {where} 상장")

    v = g.value_krw(summary.usdkrw)
    c = g.cost_krw(summary.usdkrw)
    a, b, cc, dd = st.columns(4)
    with a:
        kcard(F.shares(g.total_shares), "내가 가진 수량",
              f"{len(g.rows)}개 계좌")
    with b:
        kcard(F.native_amt(g.avg_price, g.currency), "평균 매입가격")
    with cc:
        kcard(F.native_amt(g.price, g.currency), "지금 가격",
              "Yahoo Finance" if g.market == MARKET_US else "FinanceDataReader")
    with dd:
        profit = (v - c) if (v is not None and c is not None) else None
        kcard(F.won(v), "지금 내 돈",
              F.won_signed(profit) if profit is not None else "",
              tone="up" if (profit or 0) > 0 else ("down" if (profit or 0) < 0 else ""))

    st.write("")
    section("계좌별 보유 현황")
    st.dataframe(
        [
            {
                "증권사": r.holding.broker or "-",
                "계좌": r.holding.account or "-",
                "수량": F.shares(r.holding.shares),
                "평균 매입가격": F.native_amt(r.holding.avg_price, g.currency),
                "지금 내 돈": F.won(r.value_krw(summary.usdkrw)),
            }
            for r in g.rows
        ],
        width="stretch", hide_index=True,
    )

    st.write("")
    section("💰 이 ETF 의 월급")
    if td is None or not td.ok:
        warn(f"분배금 자료를 가져오지 못했습니다. {td.error if td else ''}")
        return

    items = td.series.sorted_desc()
    last = items[0] if items else None
    interval = DS.infer_interval_days(items)
    nxt = DS.estimate_next(td, today)

    a, b, cc = st.columns(3)
    with a:
        kcard(F.native_amt(last.distribution_per_share if last else None, g.currency),
              "가장 최근 주당 분배금",
              F.ymd(last.payment_date) if last else "")
    with b:
        mine = (last.distribution_per_share * g.total_shares) if last else None
        kcard(F.won(fx_service.to_krw(mine, g.currency, summary.usdkrw)),
              "그때 내 수량이면 받는 금액", DS.cycle_label(interval))
    with cc:
        if nxt:
            mine_next = nxt.distribution_per_share * g.total_shares
            kcard(F.won(fx_service.to_krw(mine_next, g.currency, summary.usdkrw)),
                  f"다음 예상 ({F.ymd(nxt.payment_date)})", "🟡 예상값입니다")
        else:
            kcard(config.NO_DATA_TEXT, "다음 지급 예상", "근거가 부족해 예상하지 않았습니다")

    if nxt:
        note(f"※ {nxt.note}")

    st.write("")
    section("세금 계산에 잡히는 금액",
            "운용사가 발표하는 '주당 과세표준액' 입니다. 분배금과 전혀 다른 금액일 수 있습니다.")
    if not td.tax_basis_supported:
        warn("이 종목은 과세표준 자료를 제공하는 소스를 찾지 못했습니다. "
             f"금액을 추측해서 채우지 않고 '{config.TAX_BASIS_UNSUPPORTED}' 로 둡니다. "
             "실제 원천징수 금액은 증권사 거래내역에서 확인하세요.")
    else:
        latest_tb = next((d for d in items if d.tax_basis_per_share is not None), None)
        a, b = st.columns(2)
        with a:
            kcard(F.native_amt(latest_tb.tax_basis_per_share if latest_tb else None, g.currency),
                  "가장 최근 주당 과세표준액",
                  F.ymd(latest_tb.payment_date) if latest_tb else "아직 발표된 값이 없습니다")
        with b:
            mine_tb = (latest_tb.tax_basis_per_share * g.total_shares) if latest_tb else None
            kcard(F.won(fx_service.to_krw(mine_tb, g.currency, summary.usdkrw)),
                  "내 수량 기준 세금 계산 금액")

    st.write("")
    section("최근 지급 내역")
    st.dataframe(
        [
            {
                "지급월": f"{d.payment_date.year}.{d.payment_date.month:02d}",
                "지급기준일": (F.ymd(d.record_date) if d.record_date
                          else config.NO_DATA_TEXT),
                "지급일": F.ymd(d.payment_date),
                "주당 분배금": F.native_amt(d.distribution_per_share, g.currency),
                "주당 과세표준액": (F.native_amt(d.tax_basis_per_share, g.currency)
                              if d.has_tax_basis
                              else (config.TAX_BASIS_UNPUBLISHED
                                    if td.tax_basis_supported
                                    else config.TAX_BASIS_UNSUPPORTED)),
                "내 수량 기준": F.won(fx_service.to_krw(
                    d.distribution_per_share * g.total_shares, g.currency, summary.usdkrw)),
            }
            for d in items[:24]
        ],
        width="stretch", hide_index=True,
    )
    note(f"출처 · {td.source}" + (f" ({td.source_url})" if td.source_url else ""))


# =====================================================================
# 8. 종목 추가 / 수정 / 삭제
# =====================================================================
def broker_options() -> list[str]:
    used = portfolio.brokers_in_use()
    extra = [b for b in portfolio.brokers if b not in used]
    base = [b for b in config.DEFAULT_BROKERS if b not in used and b not in extra]
    return used + extra + base


def account_options() -> list[str]:
    used: list[str] = []
    for h in portfolio.holdings:
        if h.account and h.account not in used:
            used.append(h.account)
    extra = [a for a in portfolio.account_types if a not in used]
    base = [a for a in config.DEFAULT_ACCOUNT_TYPES if a not in used and a not in extra]
    return used + extra + base


def _reset_amount_inputs() -> None:
    """수량·평단가만 0 으로 되돌립니다. 증권사·계좌는 그대로 둡니다.

    왜 이렇게 나누나
    ----------------
    같은 계좌에 여러 종목을 연달아 넣는 일이 흔합니다. 증권사·계좌는 직전 것을
    그대로 쓰는 게 편하지만, **수량·평단가가 남아 있으면 앞 종목 숫자를 그대로
    저장**하게 됩니다(실제로 잘못 눌렀다는 지적을 받았습니다).

    ⚠ Streamlit 은 위젯이 이미 만들어진 뒤에 그 키의 값을 바꾸면 예외를 냅니다.
       그래서 **위젯을 만들기 전**(render_manage 맨 위)에만 부릅니다.
    """
    st.session_state["add_qty"] = 0.0
    st.session_state["add_price_text"] = ""


def _parse_money(text: str) -> float:
    """사람이 친 금액 문자열 -> 숫자. 콤마·공백·통화기호를 무시합니다."""
    cleaned = re.sub(r"[^0-9.]", "", str(text or ""))
    if not cleaned or cleaned == ".":
        return 0.0
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _format_money(text: str) -> str:
    """사람이 친 그대로를 세 자리 콤마가 붙은 모양으로. 소수점은 친 대로 남깁니다.

    "32000"    -> "32,000"
    "30.5"     -> "30.5"        (달러 평단가)
    "1234.567" -> "1,234.567"
    """
    cleaned = re.sub(r"[^0-9.]", "", str(text or ""))
    if not cleaned:
        return ""
    whole, dot, frac = cleaned.partition(".")
    whole = whole.lstrip("0") or "0"
    try:
        grouped = f"{int(whole):,}"
    except ValueError:
        return cleaned
    return grouped + (("." + frac) if dot else "")


def _on_price_changed() -> None:
    """평단가 칸을 벗어나거나 엔터를 치면 콤마를 붙여 다시 씁니다."""
    st.session_state["add_price_text"] = _format_money(
        st.session_state.get("add_price_text", ""))


def render_manage() -> None:
    # ⚠ 위젯을 만들기 **전에** 초기화해야 합니다. 만든 뒤에 session_state 를
    #    건드리면 Streamlit 이 예외를 냅니다.
    if st.session_state.pop("add_reset", False):
        st.session_state["add_query"] = ""
        _reset_amount_inputs()
    # ⚠ 위젯에 value= 를 주면서 session_state 로도 건드리면 Streamlit 이 경고를
    #    찍습니다. 기본값을 session_state 한 곳에서만 정합니다.
    st.session_state.setdefault("add_qty", 0.0)
    st.session_state.setdefault("add_price_text", "")

    section("➕ 내 ETF 추가", "다섯 가지만 넣으면 됩니다. 처음 산 날짜는 안 물어봅니다.")

    q = st.text_input("어떤 ETF 인가요?",
                      placeholder="커버 액티 · 코덱스 200 · SCHD · 069500",
                      key="add_query")
    note("이름을 조각으로 나눠 쳐도 됩니다. 띄어쓰기는 신경 쓰지 않아도 되고, "
         "조각이 전부 들어간 종목을 찾아 줍니다. 예: `커버 액티`")
    hit = None
    if q:
        hits = search_service.search(q, limit=20)
        if not hits:
            note("찾지 못했습니다. 종목코드(6자리)나 정확한 티커로 다시 시도해 보세요.")
        else:
            labels = {h.label(): h for h in hits}
            picked = st.selectbox("찾은 종목", list(labels.keys()), key="add_pick")
            hit = labels[picked]

    # 고른 종목이 바뀌면 수량·평단가를 0 으로. 앞 종목 숫자를 그대로 저장하는
    # 사고를 막습니다. (증권사·계좌는 직전 것을 그대로 씁니다)
    now_key = f"{hit.market}:{hit.ticker}" if hit else ""
    if st.session_state.get("add_last_pick") != now_key:
        st.session_state["add_last_pick"] = now_key
        if now_key:
            _reset_amount_inputs()

    c1, c2 = st.columns(2)
    with c1:
        broker = st.selectbox("어디에 가지고 있나요?", broker_options() + ["+ 직접 입력"],
                              key="add_broker")
        if broker == "+ 직접 입력":
            broker = st.text_input("증권사 이름", key="add_broker_custom").strip()
    with c2:
        account = st.selectbox("어떤 계좌인가요?", account_options() + ["+ 직접 입력"],
                               key="add_account")
        if account == "+ 직접 입력":
            account = st.text_input("계좌 이름", key="add_account_custom").strip()

    c3, c4 = st.columns(2)
    with c3:
        qty = st.number_input("몇 주 가지고 있나요?", min_value=0.0, step=1.0,
                              key="add_qty")
    with c4:
        unit = "$" if (hit and hit.market == MARKET_US) else "₩"
        # ⚠ st.number_input 은 세 자리 콤마를 못 찍습니다(format 이 printf 라
        #    자릿수 구분 기호가 없습니다). 그래서 글자 칸으로 받고 직접 찍습니다.
        st.text_input(f"평균적으로 얼마에 샀나요? ({unit})",
                      key="add_price_text", placeholder="32,000",
                      on_change=_on_price_changed)
        price = _parse_money(st.session_state.get("add_price_text", ""))
        if price > 0:
            note(f"{unit}{_format_money(str(price))} 로 저장됩니다.")

    if st.button("저장", type="primary", disabled=(hit is None or qty <= 0)):
        portfolio.add(Holding(
            ticker=hit.ticker, market=hit.market, name=hit.name,
            broker=broker or "", account=account or "", account_type=account or "",
            shares=float(qty), avg_price=float(price),
        ))
        if broker and broker not in portfolio.brokers \
                and broker not in config.DEFAULT_BROKERS:
            portfolio.brokers.append(broker)
        if account and account not in portfolio.account_types \
                and account not in config.DEFAULT_ACCOUNT_TYPES:
            portfolio.account_types.append(account)
        st.success(f"{hit.name} {qty:g}주를 추가했습니다.")
        # 다음 종목을 바로 넣을 수 있게 검색어·수량·평단가를 비웁니다.
        # (증권사·계좌는 직전 것을 그대로 씁니다 — 같은 계좌에 여러 종목을
        #  넣는 일이 흔합니다). 실제 초기화는 다음 실행 맨 위에서 합니다 —
        # 위젯이 만들어진 뒤에 값을 바꾸면 Streamlit 이 예외를 냅니다.
        st.session_state["add_reset"] = True
        st.rerun()

    st.write("")
    st.divider()
    section("✏️ 등록한 ETF 고치기",
            "표에서 바로 고칠 수 있습니다. 지우려면 맨 왼쪽의 '삭제' 를 체크하고 아래 버튼을 누르세요.")

    if not portfolio.holdings:
        note("아직 등록된 ETF 가 없습니다.")
        return

    rows = [
        {
            "삭제": False,
            "ETF": h.name or h.ticker,
            "종목코드": h.ticker,
            "증권사": h.broker,
            "계좌": h.account,
            "수량": float(h.shares),
            "평균 매입가격": float(h.avg_price),
            "_id": h.id,
        }
        for h in portfolio.holdings
    ]
    edited = st.data_editor(
        rows,
        key="editor",
        width="stretch",
        hide_index=True,
        column_config={
            "삭제": st.column_config.CheckboxColumn(width="small"),
            "ETF": st.column_config.TextColumn(disabled=True),
            "종목코드": st.column_config.TextColumn(disabled=True, width="small"),
            "수량": st.column_config.NumberColumn(min_value=0.0, step=1.0),
            "평균 매입가격": st.column_config.NumberColumn(min_value=0.0, format="%.4f"),
            "_id": None,
        },
    )

    if st.button("고친 내용 적용", type="primary"):
        keep: list[Holding] = []
        for row in edited:
            h = portfolio.by_id(str(row.get("_id")))
            if h is None or row.get("삭제"):
                continue
            h.broker = str(row.get("증권사") or "")
            h.account = str(row.get("계좌") or "")
            h.account_type = h.account
            h.shares = max(0.0, float(row.get("수량") or 0))
            h.avg_price = max(0.0, float(row.get("평균 매입가격") or 0))
            keep.append(h)
        portfolio.holdings = keep
        st.success("반영했습니다.")
        st.rerun()


# =====================================================================
# 9. 저장
# =====================================================================
def render_save() -> None:
    section("💾 저장", "이 브라우저에 자동으로 저장됩니다. 회원가입도 서버 저장도 없습니다.")

    if st.session_state.get("storage_writable", True):
        note("✅ 바꾸는 즉시 이 브라우저에 저장됩니다. "
             "다른 기기·다른 브라우저에서는 보이지 않으니, 옮기려면 아래에서 파일로 내려받으세요.")
    else:
        warn("이 브라우저는 저장이 막혀 있습니다(시크릿 모드 등). "
             "창을 닫으면 내용이 사라지니 아래에서 파일로 내려받아 두세요.")

    st.write("")
    section("포트폴리오 여러 개 두기", "'내 계좌', '와이프 계좌' 처럼 나눠서 관리할 수 있습니다.")

    names = store.names()
    c1, c2 = st.columns([2, 3])
    with c1:
        picked = st.radio("지금 보고 있는 것", names,
                          index=names.index(store.current), key="profile_pick")
        if picked != store.current:
            store.current = picked
            st.rerun()
    with c2:
        new_name = st.text_input("새로 만들기", placeholder="예: 와이프 계좌", key="profile_new")
        b1, b2, b3 = st.columns(3)
        with b1:
            if st.button("만들기", width="stretch", disabled=not new_name.strip()):
                store.create(new_name)
                st.rerun()
        with b2:
            if st.button("복사하기", width="stretch"):
                store.duplicate(store.current)
                st.rerun()
        with b3:
            if st.button("삭제", width="stretch", disabled=len(names) <= 1):
                store.delete(store.current)
                st.rerun()

        rename_to = st.text_input("이름 바꾸기", value=store.current, key="profile_rename")
        if st.button("이름 바꾸기 적용", disabled=(rename_to.strip() == store.current)):
            store.rename(store.current, rename_to)
            st.rerun()

    st.write("")
    section("파일로 내려받기 / 올리기", "다른 기기로 옮기거나 백업할 때 씁니다.")
    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            "💾 저장 파일 내려받기 (JSON)",
            data=STORE.dumps(store).encode("utf-8"),
            file_name=config.EXPORT_FILENAME,
            mime="application/json",
            width="stretch",
        )
        note(f"포트폴리오 {len(names)}개 · 종목 {STORE.count_holdings(store)}줄")
    with c2:
        up = st.file_uploader("📂 저장 파일 올리기", type=["json"], key="upload")
        if up is not None:
            loaded, err = STORE.loads(up.getvalue().decode("utf-8", "replace"))
            if loaded is None:
                warn(err)
            else:
                if st.button("이 파일로 바꾸기", type="primary"):
                    st.session_state["store"] = loaded
                    st.rerun()
                note(f"읽었습니다 — 포트폴리오 {len(loaded.names())}개 · "
                     f"종목 {STORE.count_holdings(loaded)}줄. 위 버튼을 누르면 교체됩니다.")


# =====================================================================
# 10. 화면 조립
# =====================================================================
if not has_holdings:
    render_empty()
    st.divider()
    render_manage()
    st.divider()
    render_save()
else:
    tabs = st.tabs(["🏠 홈", "📅 월별 급여명세서", "🔎 종목별 상세", "➕ 종목 관리", "💾 저장"])
    with tabs[0]:
        render_home()
    with tabs[1]:
        render_payslip()
    with tabs[2]:
        render_detail()
    with tabs[3]:
        render_manage()
    with tabs[4]:
        render_save()

# ---------------------------------------------------------------------
st.divider()
c1, c2 = st.columns([3, 1])
with c1:
    note(f"※ {config.DISCLAIMER_SHORT}")
    stamps = []
    if summary is not None and summary.data_as_of:
        stamps.append(f"데이터 기준일 {F.ymd(summary.data_as_of)}")
    if fx is not None:
        stamps.append(f"환율 1 USD = {fx.rate:,.1f}원 ({F.ymd(fx.as_of)})")
    stamps.append(f"마지막 계산 {config.now_local():%Y.%m.%d %H:%M} {config.TIMEZONE_LABEL}")
    note(" · ".join(stamps))
with c2:
    # ⚠ 캐시는 **모든 접속자가 함께 씁니다.** 한 사람이 누르면 그 순간 모든
    #    종목을 다시 받아오고, 여러 명이 번갈아 누르면 운용사 서버가 우리를
    #    막습니다. 그래서 주소에 ?admin=<키> 를 붙인 사람만 누를 수 있습니다.
    if is_admin():
        if st.button("🔄 정보 업데이트", width="stretch",
                     help="가격·환율·분배금·과세표준 캐시를 비우고 새로 받아옵니다. "
                          "(관리자 전용)"):
            n = cache.invalidate()
            st.success(f"저장해 둔 자료 {n}건을 비웠습니다. 다시 받아옵니다.")
            st.rerun()
        used = issuer_base.calls_today()
        note(f"오늘 운용사 자료 조회 {used}회 / 한도 {config.ISSUER_DAILY_CALL_BUDGET}회 "
             f"(서버가 다시 켜지면 0부터 셉니다)")
    else:
        note(f"시세와 분배금은 자동으로 새로 받아옵니다 "
             f"(가격 {config.CACHE_TTL_LATEST_PRICE_SECONDS // 60}분 · "
             f"분배금 {config.CACHE_TTL_DISTRIBUTION_SECONDS // 3600}시간 주기).")

# =====================================================================
# 11. 브라우저 저장소에 쓰기 — ⚠ 반드시 맨 아래
#     (이번 렌더에서 사용자가 고친 내용까지 반영된 뒤여야 합니다)
# =====================================================================
local_store(mode="write", data=STORE.dumps(store), key="ls_write")

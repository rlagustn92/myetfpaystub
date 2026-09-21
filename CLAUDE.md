# MY ETF 급여명세서 — 작업 규칙

여러 증권사에 흩어진 내 ETF 를 한곳에 모아, **매달 받는 돈**과 **세금 계산 기준**을
쉽게 확인하는 개인 투자 관리 도구. 한국어 Streamlit 앱.

- 배포 예정 주소: `MYETFPAYSTUB` (Streamlit Community Cloud)
- 데이터 소스 검증 기록: **[docs/DATA_SOURCES.md](docs/DATA_SOURCES.md)** — 코드를 깊게
  건드리기 전에 §1(분배금 ≠ 과세표준)과 §2-5(SOL 필드 함정)를 먼저 읽으세요.

---

## 대원칙 — 금융의 벽을 넘겨주는 엘리베이터

**보는 사람은 금융 초보라고 가정합니다.** 과세표준이 뭔지, 배당락이 뭔지 모르는 사람이
아무 설명 없이 들어와서, 배우지 않고도 "내 ETF 가 얼마이고 이번 달에 얼마 들어오는지"
를 알고 나가야 합니다. 사용자를 공부시키지 않습니다.

그래서 이렇게 씁니다.

| 전문용어 | 기본 화면에서 쓰는 말 |
|---|---|
| 평가금액 | 지금 내 돈 / 지금 내 ETF 자산 |
| 평가손익 | 지금까지 벌거나 잃은 돈 |
| 분배금 | ETF 월급 |
| 과세표준 | 세금 계산에 잡히는 금액 |
| 원천징수세액 | 세금으로 빠진 돈 |
| 증권사 | 어디에 가지고 있나요? |
| 계좌 | 어떤 계좌인가요? |

상세 화면에서는 `주당 과세표준액` 처럼 원래 용어를 병기해도 됩니다.
**숫자 하나만 던지지 않습니다** — 항상 바로 아래 한 줄로 그게 무슨 뜻인지 적습니다.

새 기능을 만들 때 자문할 것: **"금융 모르는 사람이 이 화면만 보고 이해할까?"**
아니라면 기능이 아니라 문구가 잘못된 것입니다.

---

## 절대 규칙

1. **데이터를 지어내지 않는다.** 값이 없으면 화면에 `데이터 없음` 이라고 적습니다.
   - `0` 과 `None` 을 섞지 않습니다. 과세표준 `0원` 은 **운용사가 발표한 값**이고,
     `None` 은 **모른다**는 뜻입니다. 코드에서도 화면에서도 구분합니다.
   - 합계를 낼 때 모르는 값을 0 으로 세지 않습니다. 빼고 세고, **뺐다고 화면에 적습니다.**
   - 추정이면 `🟡 예상` 을 붙이고 근거를 같이 보여줍니다. 다음 달 값을 확정값처럼
     보여주는 일은 절대 없습니다.
2. **분배금에서 과세표준을 유도하지 않는다.** 반드시 운용사가 발표한 별도 필드를 씁니다.
   같은 종목이 분배금 300원 / 과세표준 2원인 달이 실제로 있습니다.
3. **세금액을 확정값처럼 계산해 보여주지 않는다.** 이 앱은 세무 프로그램이 아닙니다.
   상품 기준 과세표준 금액까지만 보여주고, 실제 원천징수는 증권사 내역을 보라고 안내합니다.
4. **배포는 사용자가 승인한다.** 커밋까지는 해도, "이 버전 배포할까요?" 를 묻고
   답을 받은 뒤에 push 합니다.
5. **사용자에게 보이는 변화가 있으면 `config.APP_VERSION` 을 올린다.** 아주 작은
   수정이라도 올립니다. 화면 헤더의 서비스 이름 옆에 그대로 표시됩니다.
6. **개인정보를 받지 않는다.** 주민번호·계좌번호·증권사 로그인정보·API secret 은
   입력칸조차 만들지 않습니다. 투자 정보는 브라우저 저장소와 JSON 파일에만 남습니다.
7. **다른 프로젝트 폴더를 고치지 않는다.** 데스크톱의 `ETF MANAGER 2027` 등은
   참고 전용입니다. 코드를 재사용할 땐 이 저장소로 복사해 와서 고칩니다.

---

## 실행과 테스트

```bash
python -m pytest -q          # 전체 (네트워크 테스트는 자동 제외)
python -m pytest -m network  # 실제 운용사/시세 호출 (20초쯤)
streamlit run app.py         # 로컬 실행
```

기능을 하나 만들 때마다 테스트도 같이 만들고 돌립니다. 몰아서 하지 않습니다.
**항상 건너뛰는(skip) 테스트는 아무것도 검증하지 않습니다.**

`-m network` 는 배포 전에 한 번씩 돌리세요. 단위 테스트는 저장해 둔 응답 조각으로만
검증하므로, 운용사가 필드 이름을 바꿔도 조용히 통과합니다. 그걸 잡는 게 network 테스트입니다.

---

## 꼭 알아야 할 함정

- **`app.py` 만 핫리로드됩니다.** `services/`, `data/`, `config.py`, `models/`,
  `components/` 를 고치면 서버 재시작(클라우드는 Reboot 또는 새 커밋 push)이 필요합니다.
  이걸 모르고 "안 바뀌는데?" 로 시간을 날리기 쉽습니다.
- **SOL 의 `TAX_PRI` 는 과세표준이 아닙니다.** 과세기준가격(9,102원 같은 큰 수)입니다.
  주당 과세표준액은 **`WEEK_PRI`** 입니다. 잘못 쓰면 에러 없이 숫자가 45배 틀립니다.
- **TIGER 는 `listCnt` 를 크게 보내도 20건만 줍니다.** 페이징을 안 하면 그 달 상위
  20종목만 들어오고 나머지는 조용히 "분배 이력 없음"이 됩니다. 실제로 당했습니다.
- **TIGER 는 `selectMonth` 를 비우면 그 해 합계만 오고 날짜가 빕니다.** 개별 지급 건을
  받으려면 반드시 월을 지정해야 합니다. 그래서 (연,월) 단위로 받아 캐시합니다.
- **한국 종목코드는 6자리 문자열이고 영문이 섞일 수 있습니다** (`0219E0`).
  `zfill(6)` 로 앞의 0 을 살리고, `.KS/.KQ` 접미사는 `isdigit()` 이 아니라
  **길이가 6이면** 붙입니다.
- **브라우저 저장소는 화면 맨 위에서 읽고 맨 아래에서 씁니다.** 읽기를 아래로 내리면
  `StreamlitWidgetAlreadyInstantiatedError`, 쓰기를 위로 올리면 이번에 고친 내용이 안 남습니다.
- **방문자 카운터는 세션당 한 번만 부릅니다.** 안 그러면 클릭할 때마다 +1 입니다.
  `st.session_state["visitor_counts"]` 가 막고 있습니다.
- **KIWOOM(키움)은 과세표준을 공개하지만 붙이지 못했습니다.** 그 서버가 TLS 중간
  인증서를 안 보내서 파이썬에서 검증이 실패합니다. `verify=False` 로 끄지 마세요.
  자세한 건 docs/DATA_SOURCES.md §2-8.
- **전술판 자리는 보유 줄이 아니라 종목(티커)에 붙습니다.** 같은 ETF 를 세 계좌에
  나눠 가져도 카드는 하나만 섭니다. `Portfolio.slots` 의 열쇠는 `"KR:069500"` 형태.
- **📸 캡처 이미지와 📋 텍스트는 같은 줄에서 만듭니다**(`pitch_service.share_rows`).
  따로 만들면 같은 포트폴리오를 두 군데 올렸을 때 숫자가 어긋나 보입니다.
- **전술판 카드의 등번호는 실제 보유 비중입니다.** 원본(ETF MANAGER)은 사용자가
  입력한 목표비중이었습니다. 여기서는 수량 × 현재가로 저절로 정해집니다.
- **`pitch_service._ROW_BY_KEYWORD` 는 순서가 중요합니다.** "커버드콜" 이 "200"
  보다 앞에 있어야 "KODEX 200타겟위클리커버드콜" 이 제 라인으로 갑니다.
- **스킨은 유니폼 몸통 바탕색을 절대 건드리면 안 됩니다.** 몸통색 = 운용사 브랜드,
  흰 몸통+성조기 = 미국 종목, 가슴 태극 = 한국 종목. 전부 **정보**입니다.
  스킨이 쓸 수 있는 건 **소매 · 깃 · 몸통 위 무늬**뿐입니다.
- **유니폼 무늬 좌표는 화면(`patternSVG`)과 캔버스(`drawPattern`)가 같아야 합니다.**
  어긋나면 화면과 📸 캡처 이미지의 유니폼이 달라 보입니다. 잔디 깎기 무늬도 같습니다
  (`applySkin` ↔ 캔버스의 `mow` 분기).
- **등번호에는 몸통색 후광(stroke)을 두릅니다.** 줄무늬 위에 숫자가 걸치면 안 읽혀서요.
- **스킨 색은 CSS 변수 한 벌로만 넘깁니다.** 📸 캡처 이미지가 화면에서 계산된
  값을 그대로 읽어 그리기 때문에, 한 곳만 바꾸면 화면과 이미지가 저절로 같아집니다.
  따로 칠하면 둘이 어긋납니다.
- **`components/ui.py` 의 `note()` 는 마크다운이 아닙니다.** `**굵게**` 를 넣으면
  별표가 그대로 찍힙니다(실제로 당했습니다).
- **스킨은 지금 전부 열려 있습니다.** `tier` 필드는 있지만 `is_unlocked()` 가 항상
  True 입니다. 아직 없는 잠금을 "곧 열립니다" 로 보여주지 않습니다.
  수익화 배경은 docs/호스팅-수익화-검토.md.
- **날짜는 전부 `config.today_local()`** 을 씁니다. 서버가 UTC 라 `date.today()` 를 쓰면
  한국 시간 오전 9시에 날짜가 바뀝니다.

---

## 구조

```
app.py                     화면 전체 (여기만 핫리로드)
config.py                  APP_VERSION · 캐시 시간 · 한국시간 · 문구 상수
formatting.py              금액/날짜 표기 (won, won_short, native_amt …)

models/
  portfolio.py             Holding(증권사·계좌·종목·수량·평단) / Portfolio
  distribution.py          Distribution — 분배금과 과세표준은 별도 필드
  numbers.py               바깥에서 온 값을 계산에 넣기 전에 거르는 곳

services/                  순수 계산 (테스트는 주로 여기)
  portfolio_service.py     자산·원금·손익, 종목별/증권사별 묶기
  distribution_service.py  분배 이력 가져오기 + 다음 지급 예상
  cashflow_service.py      월별 급여명세서 · 올해 누적 · 달력
  fx_service.py            환율 규칙 (과거는 그때 환율, 현재는 최신 환율)
  storage_service.py       저장/불러오기 (포트폴리오 여러 개)
  search_service.py        종목 검색
  pitch_service.py         전술판 — 보유 비중을 등번호로, 자리 배치
  skin_service.py          경기장 스킨 고르기/해금 (⭐ 해금 조건은 is_unlocked 하나만)
  share_service.py         📸 이미지 명단 · 📋 텍스트 (같은 줄에서 만듭니다)
  naver_link_service.py    네이버 증권 바로가기
  visitor_service.py       TODAY / TOTAL

data/providers/
  base.py cache.py         인터페이스 · TTL 캐시
  price_provider.py        미국 yfinance / 한국 FinanceDataReader
  fx_provider.py           USD/KRW
  issuer/                  ⭐ 운용사별 분배금·과세표준
    kodex_provider.py  tiger_provider.py  ace_provider.py  rise_provider.py
    sol_provider.py    html_table_provider.py (PLUS·TIME)
    generic_provider.py    폴백 (분배금만, 과세표준 없음) + 미국
    index.py               종목코드 -> 운용사 내부 ID (시드 CSV)
    registry.py            ⭐ 소스 교체 지점. 위층은 여기만 부릅니다

data/issuer_index.csv      843건 매핑 시드 (tools/build_issuer_index.py 로 갱신)
components/
  ui.py                    카드·목록·달력 + CSS (색은 여기서만 정합니다)
  local_store/             브라우저 저장소 통로 (순수 HTML/JS, 빌드 단계 없음)
  football_pitch/          ⚽ 전술판 (ETF MANAGER 2027 에서 옮겨 옴, 순수 HTML/JS)
  pitch_grid.py            슬롯 격자 5칸 × 6라인 = 26자리
  pitch_kit.py             유니폼 색(운용사 브랜드) + 긴 한국 ETF 이름 축약
  skins.py                 스킨 21벌 (기본 + 클럽풍 20) — 순수 데이터
                           잔디/깎기무늬/광고보드/관중석 + 유니폼 소매·깃·무늬
tools/build_issuer_index.py  매핑 시드 배치 — 개발자 PC 에서만 실행
tests/                     pytest
```

**계산 로직은 UI 와 분리합니다.** `app.py` 에서 금액을 직접 계산하지 마세요.

### 어디를 고치면 되나

| 바꾸고 싶은 것 | 파일 |
|---|---|
| 버전·캐시 시간·기본 증권사 목록·문구 | `config.py` |
| 금액 표기 | `formatting.py` |
| 자산/손익 계산 | `services/portfolio_service.py` |
| 예상 로직 | `services/distribution_service.py` |
| 월별 명세서·달력 | `services/cashflow_service.py` |
| 운용사 추가 | `data/providers/issuer/` 에 파일 추가 + `registry.KR_ISSUERS` 에 한 줄 |
| 시세 소스 교체 | `data/providers/price_provider.py` 의 `get_price_provider` |
| 색·카드 모양 | `components/ui.py` |
| 전술판 자리 배치·등번호 | `services/pitch_service.py` |
| 전술판 모양·캡처 이미지 | `components/football_pitch/frontend/index.html` |
| 유니폼 색 / 이름 축약 | `components/pitch_kit.py` |
| 스킨 추가·색 | `components/skins.py` (데이터만 추가하면 끝) |
| 스킨 해금 조건 | `services/skin_service.py` 의 `is_unlocked()` |
| 공유용 텍스트 | `services/share_service.py` |
| 화면 배치 | `app.py` |

---

## 배포 (Streamlit Community Cloud)

한 줄씩 지워 나가는 체크리스트는 **[DEPLOY.md](DEPLOY.md)** 에 있습니다.

1. 이 폴더를 GitHub 저장소로 push
2. share.streamlit.io 에서 저장소 연결, main 파일 `app.py`
3. 앱 URL 을 `MYETFPAYSTUB` 으로 지정

**빠뜨리면 앱이 아예 안 켜지는 것들**

- 새로 만든 파일(특히 `services/`, `components/`, `data/providers/issuer/`)을
  git 에 반드시 포함시킵니다. 빠지면 `ModuleNotFoundError` 입니다.
- `data/issuer_index.csv` 를 올려야 합니다. 없으면 ACE·RISE·SOL·PLUS·TIME 이
  통째로 폴백으로 내려가 과세표준이 전부 "데이터 없음" 이 됩니다.
- `.streamlit/config.toml` 을 올려야 합니다(밝은 테마 고정 — 안 올리면 다크모드
  기기에서 글자가 안 보입니다). `.streamlit/secrets.toml` 은 **절대 올리지 않습니다.**
- 새 서드파티 패키지를 쓰면 `requirements.txt` 에 직접 적습니다. 다른 패키지에
  딸려오는 것에 얹혀 가면 그쪽이 의존성을 빼는 순간 앱이 안 켜집니다.
- 배포 후 Streamlit Cloud 대시보드 Secrets 에 `COUNTER_NS` 를 넣습니다
  (방문자 카운터 네임스페이스. 공개 저장소에 적히면 남이 숫자를 올릴 수 있습니다).

---

## 아직 안 만든 것 (1차 버전 범위 밖)

AI 종목 추천 · 매수/매도 추천 · 종목 점수 · 시장 예측 · 뉴스 · 복잡한 차트 ·
리밸런싱 · 자동 주문 · 증권사 로그인/연동 · 종합소득세 신고 · 미래 세금 확정 계산 ·
최초 매수일 관리 · 과거 거래내역 관리 · 회원가입 · 결제.

나중에 붙일 수 있게 데이터 구조만 열어 두었습니다(실제 입금액 기록, 증권사 CSV
가져오기, 연간 금융소득 관리, 월별 자산 변화).

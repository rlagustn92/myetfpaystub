# 방문자 수 (TODAY / TOTAL) 구현 방법 — 전수 인계서

> 이 문서를 읽는 AI/개발자에게.
>
> Streamlit 앱 오른쪽 위에 이렇게 뜨는 방문자 카운터를 **그대로 옮겨 붙이는** 문서입니다.
>
> ```
>                                          TODAY 31   TOTAL 5,171
> ```
>
> 서버·DB·회원가입 **전부 필요 없습니다.** 무료 공개 카운터 API 하나만 씁니다.
> 코드는 전부 여기 있고, 복사해서 붙이면 5분이면 끝납니다.
> 다만 **§2의 네임스페이스**와 **§4의 "세션당 한 번"** 두 가지는 틀리면 숫자가 망가지니
> 그 부분만은 꼭 읽고 넘어가세요.

---

## 0. 먼저 알아야 할 것 — 왜 파일에 저장하면 안 되나

처음 떠올리는 방법은 "서버에 숫자 파일 하나 만들어서 +1 하기" 입니다. **이건 안 됩니다.**

Streamlit Community Cloud 는 **앱이 잠들거나 재배포되면 파일 시스템이 초기화**됩니다.
방문자 수를 파일에 적어두면 며칠마다 **0 으로 돌아갑니다.** 커밋을 푸시할 때마다도 날아갑니다.

DB 를 붙이면 되지만, 고작 숫자 두 개 때문에 DB 를 붙이는 건 과합니다.
그래서 **숫자만 외부 카운터에 맡깁니다.** 앱은 상태를 하나도 안 들고 있습니다.

---

## 1. 쓰는 API — Abacus (무료, 가입 없음, 키 없음)

```
https://abacus.jasoncameron.dev
```

가입도 API 키도 없습니다. URL 만 부르면 됩니다.

| 엔드포인트 | 하는 일 |
|---|---|
| `GET /hit/{네임스페이스}/{키}` | 숫자를 **1 올리고** 올린 값을 돌려줍니다. 키가 없으면 자동으로 만듭니다 |
| `GET /get/{네임스페이스}/{키}` | 숫자를 **올리지 않고** 읽기만 합니다 |

응답은 JSON 한 줄입니다.

```json
{"value": 5171}
```

없는 키를 `get` 하면 **404** 에 `{"error":"Key not found"}` 가 옵니다.
이건 오류가 아니라 **"아직 0"** 이라는 뜻입니다. → 코드에서 `0` 으로 처리합니다.

**실제 응답 (2026-09-19 확인):**

```
200  /get/etfmanager2027/total          {"value":5171}
404  /get/etfmanager2027/d-2026-09-19   {"error":"Key not found"}   ← 오늘 아직 방문 없음
```

---

## 2. ⚠ 제일 중요 — 네임스페이스를 새로 정하세요

```python
COUNTER_NAMESPACE_DEFAULT: str = "etfmanager2027"   # ← 이걸 그대로 쓰면 안 됩니다
```

네임스페이스는 **전 세계 공용 공간에서 내 앱의 방을 구분하는 이름**입니다.
그대로 복사해 쓰면 **두 서비스의 방문자 수가 한 통에 섞입니다.**

새 서비스마다 **다른 이름**으로 바꾸세요. 소문자·숫자·하이픈이면 됩니다.

```python
COUNTER_NAMESPACE_DEFAULT: str = "내서비스이름2027"
```

### 그리고 이름은 가능하면 숨기세요

공개 저장소에 네임스페이스가 그대로 적혀 있으면, **누구나 그 URL 을 눌러서 숫자를 올릴 수
있습니다.** 인증이 없는 무료 API 라서요. 그래서 진짜 이름은 `secrets.toml` 에 넣고,
코드에는 들러리 기본값만 둡니다.

`.streamlit/secrets.toml` (git 에 올리지 않는 파일):

```toml
COUNTER_NS = "아무도-모르는-이름-a9f3"
```

배포할 때는 Streamlit Cloud 대시보드의 **Secrets** 에 같은 줄을 넣습니다.
secrets 가 없으면 코드의 기본값으로 조용히 돌아갑니다(로컬에서도 그냥 돌아가야 하니까).

---

## 3. 무엇을 세는가 (정직하게)

- **TOTAL** → 키 `total`
- **TODAY** → 키 `d-2026-09-19` 처럼 **날짜가 들어간 키**. 날짜가 바뀌면 키가 바뀌고,
  새 키는 자동으로 0부터 시작합니다. **"오늘" 로직을 따로 짤 필요가 없습니다.** 이게 요령입니다.

세는 단위는 **접속 1회(세션 1개)당 1** 입니다.

> ⚠ **정확한 순방문자가 아닙니다.** 같은 사람이 새로고침하거나 다른 기기로 들어오면 각각 세집니다.
> "대략 얼마나 들어오는지" 보는 용도입니다. 정확한 수치가 필요하면
> **Streamlit Cloud 관리 화면의 Analytics** 를 보세요. 그쪽이 진짜 기준입니다.
>
> 화면에 "방문자 수" 라고 쓰되, 이 숫자를 **광고나 지표로 내세우지는 마세요.**

### ⚠ 날짜는 한국 시간으로

**서버는 UTC 로 돕니다.** 그냥 `date.today()` 를 쓰면 **한국 시간 오전 9시에 날짜가 바뀝니다.**
아침 8시에 들어온 사람이 "어제" 로 세집니다. 반드시 한국 날짜 헬퍼를 만들어 쓰세요.

```python
from datetime import datetime, timezone, timedelta, date

KST = timezone(timedelta(hours=9))

def now_local() -> datetime:
    return datetime.now(KST)

def today_local() -> date:
    return now_local().date()
```

---

## 4. ⚠ 두 번째로 중요 — 세션당 한 번만 부르기

**Streamlit 은 버튼을 누를 때마다 스크립트를 처음부터 다시 실행합니다.**
카운터 호출을 그냥 써놓으면 **클릭할 때마다 +1** 이 됩니다. 한 사람이 30번 클릭하면 30명이 됩니다.

`st.session_state` 로 "이번 세션에 이미 셌는지" 를 기억해서 딱 한 번만 부릅니다.

```python
if "visitor_counts" not in st.session_state:          # ← 세션당 최초 1회에만 들어옴
    st.session_state["visitor_counts"] = visitor_service.count_visit()
counts = st.session_state["visitor_counts"]
```

두 번째 실행부터는 `if` 안으로 안 들어가고 **저장된 숫자를 그대로 씁니다.**
네트워크 호출도 0번이라 화면도 빨라집니다.

---

## 5. 코드 (그대로 복사하세요)

### 5-1. `config.py` 에 추가

```python
from datetime import datetime, timezone, timedelta, date

# ---- 방문자 카운터 ----------------------------------------------------
# 배포 서버(Streamlit Cloud)는 앱이 잠들거나 재배포되면 파일이 초기화됩니다.
# 그래서 숫자를 서버에 적어두면 계속 0 으로 돌아가므로, 외부 카운터에 맡깁니다.
# 무료 서비스라 언제든 멈출 수 있으니 실패해도 앱은 그대로 동작해야 합니다.
COUNTER_ENABLED: bool = True
COUNTER_BASE_URL: str = "https://abacus.jasoncameron.dev"
COUNTER_NAMESPACE_DEFAULT: str = "바꾸세요-내서비스이름"   # ⚠ §2
COUNTER_TIMEOUT_SECONDS: float = 2.5   # 느려도 화면을 오래 붙잡지 않도록 짧게

# ---- 한국 시간 --------------------------------------------------------
KST = timezone(timedelta(hours=9))

def now_local() -> datetime:
    """화면 표시용 '지금' (한국 시간)."""
    return datetime.now(KST)

def today_local() -> date:
    """화면 표시용 '오늘' (한국 날짜)."""
    return now_local().date()
```

### 5-2. `services/visitor_service.py` (새 파일, 전문)

```python
"""
services/visitor_service.py  --  방문자 수 (오늘 / 전체)

왜 외부 서비스를 쓰나
---------------------
배포 서버(Streamlit Cloud)는 앱이 잠들거나 재배포될 때 파일 시스템이 초기화됩니다.
방문자 수를 서버 파일에 적어두면 며칠마다 0 으로 돌아가므로, 숫자만 외부 카운터에 맡깁니다.

무엇을 세나
-----------
**접속 1회(세션 1개)당 1** 입니다. 화면이 다시 그려질 때마다(버튼 클릭 등) 올라가면
숫자가 엉터리가 되므로, app.py 에서 "이번 세션에 이미 셌는지"를 확인하고 한 번만 부릅니다.

- 전체: 키 `total`
- 오늘: 키 `d-YYYY-MM-DD` (한국 날짜 기준. 서버가 UTC 라서 config.today_local() 을 씁니다)

한계 (알고 쓰세요)
------------------
- 같은 사람이 새로고침하거나 다른 기기로 들어오면 각각 세집니다. "정확한 순방문자"가
  아니라 "대략 얼마나 들어오는지" 보는 용도입니다.
- 무료 공개 API 라 누군가 주소를 알아내 숫자를 부풀릴 수 있습니다. 정확한 수치가
  필요하면 Streamlit Cloud 관리 화면의 Analytics 를 보세요(그쪽이 진짜 기준입니다).
- 카운터가 죽어도 앱은 그대로 동작해야 합니다. 모든 실패는 조용히 무시하고 None 을 돌려줍니다.
"""

from __future__ import annotations

import requests

import config


def _namespace() -> str:
    """카운터 이름 공간. 공개 저장소에 그대로 적히면 남이 숫자를 올릴 수 있으므로,
    secrets 에 COUNTER_NS 를 넣으면 그 값을 우선 씁니다."""
    try:
        import streamlit as st
        ns = str(st.secrets.get("COUNTER_NS", "") or "")
        if ns:
            return ns
    except Exception:
        pass
    return config.COUNTER_NAMESPACE_DEFAULT


def _call(action: str, key: str) -> int | None:
    """action: 'hit'(1 올리고 값 반환) | 'get'(값만 읽기). 실패하면 None."""
    url = f"{config.COUNTER_BASE_URL}/{action}/{_namespace()}/{key}"
    try:
        r = requests.get(url, timeout=config.COUNTER_TIMEOUT_SECONDS)
    except requests.RequestException:
        return None
    if r.status_code == 404:
        return 0          # 아직 한 번도 기록되지 않은 키 (예: 오늘 첫 방문 전)
    if r.status_code != 200:
        return None
    try:
        value = r.json().get("value")
    except ValueError:
        return None
    return int(value) if isinstance(value, (int, float)) else None


def count_visit() -> tuple[int, int] | None:
    """이번 접속을 기록하고 (오늘, 전체) 를 돌려줍니다. 실패하면 None.

    ⚠ 세션당 한 번만 부르세요 (app.py 가 session_state 로 보장합니다).
    """
    if not config.COUNTER_ENABLED:
        return None
    today_key = f"d-{config.today_local().isoformat()}"
    today = _call("hit", today_key)
    total = _call("hit", "total")
    if today is None or total is None:
        return None
    return today, total


def read_counts() -> tuple[int, int] | None:
    """숫자를 올리지 않고 읽기만 합니다 (표시 갱신용)."""
    if not config.COUNTER_ENABLED:
        return None
    today = _call("get", f"d-{config.today_local().isoformat()}")
    total = _call("get", "total")
    if today is None or total is None:
        return None
    return today, total
```

### 5-3. `app.py` — 헤더 오른쪽에 붙이기

```python
from services import visitor_service

tc1, tc2 = st.columns([3, 1])          # 왼쪽 제목 / 오른쪽 카운터

with tc1:
    st.markdown("<h2 class='app-title'>내 서비스 이름</h2>", unsafe_allow_html=True)

with tc2:
    # 방문자 수: 접속(세션) 1회당 1 만 올립니다. 화면이 다시 그려질 때마다 올리면
    # 숫자가 엉터리가 되므로, 이번 세션에 이미 셌는지를 session_state 로 확인합니다.
    if "visitor_counts" not in st.session_state:
        st.session_state["visitor_counts"] = visitor_service.count_visit()
    _counts = st.session_state["visitor_counts"]
    if _counts:                                    # ← 실패(None)면 아무것도 안 그림
        _today, _total = _counts
        st.markdown(
            "<div class='visitors'>"
            f"<span><b>TODAY</b> {_today:,}</span>"
            f"<span><b>TOTAL</b> {_total:,}</span>"
            "</div>",
            unsafe_allow_html=True,
        )
```

`{_today:,}` 의 쉼표가 `5171` 을 `5,171` 로 만들어 줍니다.

### 5-4. CSS (`st.markdown(..., unsafe_allow_html=True)` 로 한 번 주입)

```css
/* 오른쪽 위 방문자 수 (TODAY / TOTAL) */
.visitors {
  display: flex; justify-content: flex-end; gap: 14px;
  padding-top: 12px;
  font-size: 12.5px; color: #8a8f98;
  font-variant-numeric: tabular-nums;   /* 숫자 폭 고정 — 갱신될 때 안 흔들림 */
  white-space: nowrap;                  /* 좁은 화면에서 줄바꿈 방지 */
}
.visitors b {
  font-size: 11px; font-weight: 700; letter-spacing: .04em;
  color: #8a8f98; margin-right: 3px;
}
```

`tabular-nums` 를 꼭 넣으세요. 없으면 숫자가 바뀔 때마다 글자 폭이 달라져서 살짝 덜컹거립니다.

### 5-5. `requirements.txt`

```
requests>=2.31,<3
```

`requests` 는 streamlit 이 딸려 오지만, **직접 쓰는 패키지는 직접 적습니다.**
남의 의존성에 얹혀 가면 그쪽이 빼는 순간 앱이 안 켜집니다.

---

## 6. 실패하면 어떻게 되나 — "조용히 사라진다"

이 기능의 설계 원칙은 하나입니다.

> **카운터 때문에 앱이 느려지거나 죽으면 안 된다.**

방문자 수는 **있으면 좋은 것**이지, 서비스의 본질이 아닙니다. 그래서 전부 이렇게 처리합니다.

| 상황 | 처리 |
|---|---|
| 네트워크 끊김 | `RequestException` 잡고 `None` |
| 카운터 서비스 다운 (500 등) | `None` |
| 응답이 JSON 이 아님 | `ValueError` 잡고 `None` |
| 키가 아직 없음 (404) | **`0`** (오류 아님) |
| `COUNTER_ENABLED = False` | 네트워크 **아예 안 탐** |

그리고 `None` 이면 **화면에 아무것도 안 그립니다.** 에러 메시지도 안 띄웁니다.
사용자 입장에서는 그냥 카운터가 안 보일 뿐, 앱은 멀쩡합니다.

**타임아웃 2.5초**도 같은 이유입니다. 카운터가 느리다고 첫 화면을 10초씩 붙잡으면
그게 더 큰 손해입니다. 짧게 끊고 포기합니다.

---

## 7. 테스트 (네트워크 없이 전부 검증됩니다)

`requests.get` 을 monkeypatch 로 가짜로 바꾸면 인터넷 없이 다 테스트할 수 있습니다.
실제로 쓰고 있는 테스트 이름 11개입니다. 그대로 옮기세요.

```
test_counts_are_returned_as_today_and_total      정상 응답 → (오늘, 전체)
test_today_key_uses_korean_date_not_server_date  ⚠ UTC 가 아니라 KST 키를 쓰는지
test_korean_date_helper_is_nine_hours_ahead_of_utc
test_network_failure_returns_none_and_does_not_raise   ⚠ 터지지 않는지
test_server_error_returns_none
test_bad_json_returns_none
test_missing_key_counts_as_zero                  404 → 0
test_read_counts_does_not_increment              ⚠ get 이 hit 을 부르지 않는지
test_disabled_switch_skips_network_entirely      꺼두면 호출 0번
test_timeout_is_short_so_page_load_is_not_blocked
test_last_updated_is_korean_time
```

가짜 응답은 이런 모양이면 충분합니다.

```python
class FakeResponse:
    def __init__(self, status=200, payload=None, raise_exc=None):
        self.status_code = status
        self._payload = payload or {}
        self._raise = raise_exc
    def json(self):
        if self._raise:
            raise self._raise
        return self._payload

def test_missing_key_counts_as_zero(monkeypatch):
    monkeypatch.setattr(visitor_service.requests, "get",
                        lambda *a, **k: FakeResponse(status=404))
    assert visitor_service._call("get", "아무키") == 0
```

**"세션당 한 번" 은 app.py 쪽 동작이라** 여기선 안 잡힙니다.
`streamlit.testing.v1.AppTest` 로 앱을 두 번 실행해서 **호출이 1번인지** 따로 확인하세요.
이게 제일 틀리기 쉬운 부분이라 테스트를 붙여두는 게 좋습니다.

---

## 8. 옮겨 붙이는 순서 (5분)

1. `config.py` 에 §5-1 붙이고 **`COUNTER_NAMESPACE_DEFAULT` 를 새 이름으로 바꾸기** ⚠
2. `services/visitor_service.py` 새로 만들고 §5-2 통째로 붙이기
3. `app.py` 헤더에 §5-3 붙이기
4. CSS §5-4 주입
5. `requirements.txt` 에 `requests` 추가
6. `.streamlit/secrets.toml` 에 `COUNTER_NS` 넣기 (배포 시 Cloud Secrets 에도)
7. 로컬 실행 → 오른쪽 위에 `TODAY 1  TOTAL 1` 이 뜨는지 확인
8. **버튼을 몇 번 눌러보고 숫자가 안 올라가는지 확인** ← 세션당 한 번이 잘 걸렸다는 뜻

### 체크리스트

- [ ] 네임스페이스를 **새 이름**으로 바꿨다 (안 바꾸면 다른 서비스와 숫자가 섞임)
- [ ] `st.session_state` 로 **세션당 한 번**만 부른다 (안 하면 클릭마다 +1)
- [ ] 오늘 날짜가 **한국 시간(KST)** 기준이다 (UTC 면 오전 9시에 날짜가 바뀜)
- [ ] 404 를 오류가 아니라 **0** 으로 처리한다
- [ ] 실패하면 **아무것도 안 그린다** (에러 메시지 금지)
- [ ] 타임아웃이 짧다 (2.5초)
- [ ] `requests` 를 requirements.txt 에 적었다
- [ ] CSS 에 `tabular-nums` 를 넣었다

---

## 9. 더 하고 싶으면

- **어제/이번 주** — 키만 바꾸면 됩니다. `d-2026-09-18`, 주간은 `w-2026-38` 식으로.
  로직을 짤 필요 없이 **키 이름이 곧 집계 단위**입니다.
- **페이지별 카운트** — `p-backtest`, `p-calendar` 처럼 키를 나눠 `hit` 하면 됩니다.
  어느 기능을 실제로 쓰는지 알 수 있습니다.
- **숫자를 다시 읽기만** — `read_counts()` 를 쓰세요. `hit` 이 아니라 `get` 이라 안 올라갑니다.

## 10. 마지막 한마디

이 기능은 코드가 100줄도 안 됩니다. 그런데 **틀리기 쉬운 곳이 정확히 세 군데**고,
셋 다 에러 없이 조용히 틀립니다.

1. 네임스페이스를 안 바꿔서 **남의 숫자와 섞이는** 것
2. 세션 체크를 안 해서 **클릭마다 올라가는** 것
3. UTC 를 써서 **오전 9시에 날짜가 바뀌는** 것

이 셋만 피하면 나머지는 그냥 복사해서 붙이면 됩니다.

그리고 잊지 마세요 — **카운터 때문에 앱이 죽으면 안 됩니다.**
실패는 전부 삼키고, 안 되면 그냥 안 보이게 두세요.

건투를 빕니다. 🙏

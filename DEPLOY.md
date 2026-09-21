# 배포 체크리스트 (Streamlit Community Cloud)

배포는 **사용자가 승인할 때만** 합니다. 이 문서는 그때 둘이 같이 보면서 한 줄씩
지워 나가는 종이입니다.

---

## 0. 배포 전에 반드시

```bash
python -m pytest -q          # 전부 통과해야 합니다
python -m pytest -m network  # ⭐ 이게 제일 중요합니다 (아래 설명)
```

**`-m network` 를 꼭 돌리세요.** 평소 단위 테스트는 저장해 둔 응답 조각으로만
검증하므로, 운용사가 필드 이름을 바꿔도 **조용히 통과합니다.** 실제로 호출해서
"과세표준이 여전히 그 자리에 있는지" 를 보는 게 이 테스트입니다.

배포 직전 상태 (2026-09-21 확인):

- 오프라인 테스트 151개 통과
- 실데이터 테스트 15개 통과 (KODEX·TIGER·ACE·PLUS·SOL 5개 운용사 실호출)
- 깨끗한 복제본에서 import·테스트 전부 통과

---

## 1. GitHub 저장소

**2026-09-21 완료.** `https://github.com/rlagustn92/myetfpaystub` (**공개**),
기본 브랜치 `main`.

```bash
git branch -M main
gh repo create <저장소> --public --source=. --remote=origin
git push -u origin main
```

**왜 공개인가** — Streamlit Community Cloud 무료 플랜은 **공개 앱은 무제한,
비공개 앱은 1개**입니다. 비공개로 만들었다가 그 한 자리를 쓰게 돼서 공개로
바꿨습니다. 저장소에 개인정보가 들어가는 파일은 없습니다(투자 정보는 사용자
브라우저에만 남습니다). `COUNTER_NS` 만 예외라 §3 처럼 Secrets 로 뺍니다.

### ⚠ 공개로 돌리기 전에 반드시 확인할 것

1. **커밋에 박힌 실명·개인 이메일.** 처음 21개 커밋 중 17개가
   `김현수 <wjsghks001@gmail.com>` 이었습니다. 공개하면 수집 봇이 긁어갑니다.
   **공개 전에** 다시 써야 합니다(공개 후에는 늦습니다).

   ```bash
   git log --format='%an <%ae>' | sort -u          # 먼저 확인
   FILTER_BRANCH_SQUELCH_WARNING=1 git filter-branch -f --env-filter '
     export GIT_AUTHOR_NAME="rlagustn92";  export GIT_AUTHOR_EMAIL="myetfpaystub@example.com"
     export GIT_COMMITTER_NAME="rlagustn92"; export GIT_COMMITTER_EMAIL="myetfpaystub@example.com"
   ' --tag-name-filter cat -- --branches --tags
   git for-each-ref --format='%(refname)' refs/original | xargs -n1 git update-ref -d
   git push --force-with-lease origin main
   git config user.email "myetfpaystub@example.com"   # 다음 커밋부터 자동 적용
   ```

   `example.com` 은 RFC 2606 이 문서용으로 예약한 도메인이라 **누구도 등록할 수
   없습니다.** "존재하지 않는 주소" 로 쓰기에 안전합니다.

   ⚠ `git log --all` 로 확인하면 `origin/main`(옛 히스토리를 가리킴) 때문에
   force push 전까지는 계속 옛 이메일이 보입니다. push 뒤에 다시 보세요.

2. **예시 데이터가 실제 보유와 같은지.** `app.py` 의 "예시로 시작해보기" 에
   증권사·계좌유형·종목·수량·평단이 들어 있습니다. 코드에 개인정보가 없어도
   예시 데이터에는 있을 수 있습니다. (2026-09-21 확인: 지어낸 값이라 그대로 둠)

## 2. share.streamlit.io

1. **New app** → 저장소 연결
2. **Main file path**: `app.py`
3. **App URL**: `MYETFPAYSTUB` → `https://myetfpaystub.streamlit.app`
4. Python 3.11 이상 (개발·검증 환경은 3.13)

## 3. Secrets (배포 후 대시보드에서)

```toml
COUNTER_NS = "아무도-모르는-이름-XXXX"
```

방문자 카운터 네임스페이스입니다. 인증이 없는 무료 API 라, 공개 저장소에 적힌
이름을 아는 사람은 누구나 그 URL 을 눌러 숫자를 올릴 수 있습니다. 그래서
`config.py` 에는 들러리 기본값(`myetfpaystub`)만 두고 진짜 이름은 여기 넣습니다.
**안 넣어도 앱은 그대로 돌아갑니다** (기본값으로 셉니다).

```toml
ADMIN_KEY = "아무도-모르는-긴-문자열"
```

**이건 넣는 걸 권합니다.** `🔄 정보 업데이트` 버튼을 가립니다.

- 캐시는 **모든 접속자가 함께 씁니다.** 한 사람이 누르면 그 순간 모든 종목을
  다시 받아오고, 여러 명이 번갈아 누르면 운용사 서버가 우리를 막습니다.
- 실제로 개발 중에 삼성자산운용 API 가 한동안 `{"dividList":[],"totalCnt":0}`
  만 돌려줬습니다. **HTTP 200 에 정상 JSON 이라 에러도 안 나고**, 앱이 조용히
  폴백으로 내려가 과세표준이 전부 "확인 불가" 가 됩니다.
- 키를 넣으면 관리자만 누를 수 있습니다:
  `https://myetfpaystub.streamlit.app/?admin=아무도-모르는-긴-문자열`
- **안 넣으면 모두가 관리자**입니다(개인 PC 에서 혼자 쓸 때를 위한 기본값).
- ⚠ 키를 **코드나 README 에 적지 마세요.** 저장소가 공개입니다.
  테스트가 막고 있습니다(`tests/test_admin_and_budget.py`).

하루 호출 한도(`config.ISSUER_DAILY_CALL_BUDGET`, 기본 600회)도 같이 겁니다.
프로세스 안에서만 세므로 서버가 다시 켜지면 0 부터 셉니다 — 완벽한 한도가
아니라 **폭주를 끊는 안전장치**입니다.

---

## 4. 빠뜨리면 앱이 아예 안 켜지는 것들

전부 지금 저장소에 들어 있는지 확인했습니다. 나중에 파일을 추가할 때 다시 보세요.

| 파일 | 빠뜨리면 |
|---|---|
| `data/issuer_index.csv` | ACE·RISE·SOL·PLUS·TIME 이 통째로 폴백으로 내려가 **과세표준이 전부 "데이터 없음"** 이 됩니다 |
| `components/*/frontend/index.html` | 전술판·브라우저 저장이 빈 칸으로 뜹니다 |
| `.streamlit/config.toml` | 밝은 테마 고정이 풀려서 **다크모드 기기에서 글자가 안 보입니다** |
| `services/` · `data/providers/issuer/` 의 새 파일 | `ModuleNotFoundError` 로 앱이 안 켜집니다 |
| `requirements.txt` 의 새 패키지 | 같은 이유로 안 켜집니다 |

확인하는 법:

```bash
git ls-files | grep -E "issuer_index|frontend/index.html|config.toml"
```

`.streamlit/secrets.toml` 은 **절대 올리지 않습니다.** `.gitignore` 에 들어 있습니다.

---

## 5. 배포 직후 눈으로 볼 것

1. 빈 화면에서 **예시로 시작해보기** → 숫자가 채워지는지
2. 🏠 홈 맨 아래 **⚽ 전술판**에 카드가 서는지 (유니폼 색·등번호)
3. 📸 복사 / 💾 저장 / 📋 텍스트 세 버튼
   - ⚠ 클립보드는 **창이 포커스를 가지고 있어야** 동작합니다. 브라우저 탭을
     클릭한 뒤 눌러 보세요. 실패하면 버튼이 `❌ 실패` 로 바뀝니다
4. 종목별 상세 → **Npay증권 ↗** 링크가 실제 종목 페이지로 가는지
5. 오른쪽 위 **TODAY / TOTAL** 이 뜨는지 (안 떠도 앱은 정상 — 카운터는 부가기능)
6. 새로고침 → 등록한 ETF 와 전술판 자리가 **그대로 남아 있는지**
7. 폰에서 한 번 — 가로 스크롤이 생기지 않아야 합니다

## 6. 첫 화면이 느린 이유 (정상입니다)

TIGER 종목이 있으면 **처음 한 번만 20초쯤** 걸립니다. TIGER 는 분배금을 달마다
따로 조회해야 해서 14개월치를 받아옵니다(스레드 4개로 나눠서). 한 번 받아두면
12시간 동안 프로세스 전역 캐시에 남아, 그다음부터는 즉시 뜹니다.

Streamlit Cloud 는 한동안 접속이 없으면 앱이 잠듭니다. 그때 첫 로딩은 30초쯤
더 걸릴 수 있습니다.

---

## 7. 배포 뒤에 코드를 고치면

`git push` 하면 자동으로 다시 배포됩니다.

⚠ **`app.py` 만 핫리로드됩니다.** `services/`, `data/`, `config.py`, `models/`,
`components/` 를 고쳤으면 push(또는 대시보드 Reboot)가 필요합니다.

그리고 **사용자에게 보이는 변화가 있으면 `config.APP_VERSION` 을 올립니다.**
화면 헤더의 서비스 이름 옆에 그대로 표시돼서, 지금 어떤 판을 보고 있는지
사용자와 같이 확인할 수 있습니다.

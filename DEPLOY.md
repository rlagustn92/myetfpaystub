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

```bash
git remote add origin https://github.com/<계정>/<저장소>.git
git branch -M main
git push -u origin main
```

저장소는 **공개(public)** 여도 됩니다. 개인정보가 들어가는 파일이 없습니다
(투자 정보는 사용자 브라우저에만 남습니다). 다만 §3 의 `COUNTER_NS` 는 예외입니다.

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

"""
tools/build_tiger_months.py  --  TIGER 월별 분배 표 시드 만들기
================================================================

**개발자 PC 에서만 돌립니다.** 배포된 앱은 결과 CSV 를 읽기만 합니다.

    python tools/build_tiger_months.py              # 빠진 달만 채웁니다
    python tools/build_tiger_months.py --months 24  # 거슬러 올라갈 개월 수
    python tools/build_tiger_months.py --dry-run    # 뭘 받을지만 보여줍니다

만드는 것:

    data/tiger_months.csv
        year,month,code,name,record_date,payment_date,amount,tax_basis

왜 필요한가
-----------
TIGER 는 **달마다 따로** 불러야 개별 지급 건을 줍니다. 그래서 종목 하나를 보려고
14개월 × 페이지를 훑어 **HTTP 43번**이 나갔습니다(받는 자료는 4건인데).

캐시는 서버 **메모리**에만 있어서 재시작하면 날아갑니다. 무료 호스팅은 접속이
없으면 앱을 재우므로, 메모리 캐시만으로는 **깨어날 때마다 43번**입니다.
지나간 달은 어차피 안 바뀌니 파일로 굳혀 저장소에 넣습니다.

⭐ 월별 표는 **종목이 아니라 달에 붙습니다.** 한 달치를 받으면 그 달 TIGER 전
종목이 다 들어옵니다. 그래서 달만 굳혀 두면 모든 TIGER ETF 가 공짜입니다.

덮어쓰지 않고 **더합니다**
--------------------------
기존 CSV 를 읽어서 **없는 달만** 받아 합칩니다. 그래서

- 돌릴수록 이력이 길어집니다. 14개월 창에 갇히지 않습니다.
- 이미 끝난 달은 다시 안 받습니다 — 실행 비용이 회를 거듭할수록 줄어듭니다.
- 네트워크가 반쯤 죽은 상태로 돌려도 **멀쩡한 기존 자료를 날리지 않습니다.**

아직 안 끝난 달(이번 달, 또는 과세표준 빈 칸이 남은 달)은 파일에 **넣지 않습니다.**
넣어 두면 앱이 그걸 최종본으로 믿고 나중에 발표된 과세표준을 영영 못 봅니다.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)          # 이 스크립트를 어디서 돌려도 import 가 되도록

# ⚠ 윈도우 콘솔은 기본이 cp949 라, 한글 외 기호(— ✅ 등)에서 UnicodeEncodeError 로
#    **스크립트가 통째로 죽습니다.** 실제로 그래서 한 번 멈췄습니다.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):   # 파이프로 넘길 때 등
    pass

import config                                                   # noqa: E402
from data.providers.issuer import base as issuer_base           # noqa: E402
from data.providers.issuer import tiger_provider as tp          # noqa: E402
from data.providers.issuer import tiger_seed                    # noqa: E402


def read_existing() -> dict[tuple[int, int], dict[str, dict]]:
    """이미 굳혀 둔 달들. 파일이 없으면 빈 dict."""
    return tiger_seed._load()          # 캐시를 안 타는 쪽으로 직접 읽습니다


def write_csv(table: dict[tuple[int, int], dict[str, dict]], path: str) -> int:
    """최신 달이 위로 오게 정렬해서 씁니다. 쓴 줄 수를 돌려줍니다."""
    rows = 0
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(tiger_seed.FIELDS)
        for (y, m) in sorted(table, reverse=True):
            for code in sorted(table[(y, m)]):
                r = table[(y, m)][code]
                w.writerow([y, m, code, r.get("name", ""), r.get("record_date", ""),
                            r.get("payment_date", ""), r.get("amount", ""),
                            r.get("tax_basis", "")])
                rows += 1
    os.replace(tmp, path)              # 쓰다 실패해도 기존 파일이 안 깨지게
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", type=int, default=tp.MONTHS_BACK * 2,
                    help="오늘부터 거슬러 올라갈 개월 수 (기본 28)")
    ap.add_argument("--dry-run", action="store_true", help="받지 않고 계획만 보여줍니다")
    args = ap.parse_args()

    existing = read_existing()
    print(f"기존 파일: {len(existing)}개월 / {sum(len(v) for v in existing.values())}줄")

    wanted = tp._months_back(args.months)
    todo = [ym for ym in wanted if ym not in existing]
    skip = [ym for ym in wanted if ym in existing]

    print(f"이미 있어서 건너뜀: {len(skip)}개월")
    print(f"새로 받을 달      : {len(todo)}개월  "
          f"{[f'{y}-{m:02d}' for y, m in todo[:6]]}{' …' if len(todo) > 6 else ''}")
    if args.dry_run:
        print("\n--dry-run 이라 여기서 멈춥니다.")
        return 0
    if not todo:
        print("\n받을 게 없습니다. 파일 그대로 둡니다.")
        return 0

    issuer_base.reset_calls()
    added_months = 0
    unsettled: list[str] = []
    for y, m in todo:
        try:
            rows = tp._fetch_month_live(y, m)
        except Exception as e:                       # noqa: BLE001
            print(f"  {y}-{m:02d}  실패 {type(e).__name__} — 건너뜁니다")
            continue
        # ⚠ 아직 안 끝난 달은 굳히지 않습니다. 넣어 두면 앱이 최종본으로 믿고
        #    나중에 발표된 과세표준을 영영 못 봅니다.
        if not tp._month_is_settled(y, m, rows):
            unsettled.append(f"{y}-{m:02d}")
            print(f"  {y}-{m:02d}  {len(rows):>3}건 — 아직 안 끝난 달이라 안 넣습니다")
            continue
        existing[(y, m)] = rows
        added_months += 1
        print(f"  {y}-{m:02d}  {len(rows):>3}건  ✅")

    if added_months == 0:
        print("\n새로 굳힐 달이 없었습니다. 파일 그대로 둡니다.")
        return 0

    total = write_csv(existing, tiger_seed.CSV_PATH)
    size = os.path.getsize(tiger_seed.CSV_PATH)
    print(f"\n{tiger_seed.CSV_PATH}")
    print(f"  {len(existing)}개월 / {total}줄 / {size:,}바이트")
    print(f"  이번에 더한 달 {added_months}개, HTTP {issuer_base.calls_today()}회")
    if unsettled:
        print(f"  아직 안 끝나서 뺀 달: {', '.join(unsettled)} "
              f"(앱이 그 달만 직접 받아옵니다)")
    print("\n⚠ 이 파일을 git 에 커밋해야 배포본에 반영됩니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

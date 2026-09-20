"""
services/storage_service.py  --  저장과 불러오기
=================================================

회원가입도 서버 저장도 없습니다. 두 가지 방법으로 남깁니다.

1. **브라우저에 저장** (기본) — 이 컴퓨터의 이 브라우저에만 남습니다.
2. **JSON 파일로 내려받기 / 올리기** — 다른 기기로 옮기거나 백업할 때.

포트폴리오를 **여러 개** 만들어 둘 수 있습니다("내 계좌", "와이프 계좌"처럼).
그래서 저장 단위는 `Store` 이고, 그 안에 이름별 포트폴리오가 들어 있습니다.

잘못된 파일을 올려도 **앱이 죽으면 안 됩니다.** 못 읽는 줄은 건너뛰고, 아예 못 읽는
파일이면 이유를 한국어로 돌려줍니다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import config
from models.portfolio import Portfolio

SCHEMA = "my_etf_paystub"
SCHEMA_VERSION = 1
DEFAULT_PROFILE = "내 포트폴리오"


@dataclass
class Store:
    """저장되는 것 전체."""

    profiles: dict[str, Portfolio] = field(default_factory=dict)
    current: str = DEFAULT_PROFILE
    saved_at: str = ""

    # -- 조회 --------------------------------------------------------
    def names(self) -> list[str]:
        return list(self.profiles.keys())

    def active(self) -> Portfolio:
        """지금 보고 있는 포트폴리오. 없으면 빈 것을 만들어 줍니다."""
        if self.current not in self.profiles:
            if self.profiles:
                self.current = next(iter(self.profiles))
            else:
                self.profiles[DEFAULT_PROFILE] = Portfolio(name=DEFAULT_PROFILE)
                self.current = DEFAULT_PROFILE
        return self.profiles[self.current]

    # -- 편집 --------------------------------------------------------
    def create(self, name: str) -> str:
        """새 포트폴리오. 이름이 겹치면 뒤에 숫자를 붙입니다(덮어쓰지 않습니다)."""
        base = (name or DEFAULT_PROFILE).strip() or DEFAULT_PROFILE
        final, n = base, 2
        while final in self.profiles:
            final, n = f"{base} {n}", n + 1
        self.profiles[final] = Portfolio(name=final)
        self.current = final
        return final

    def rename(self, old: str, new: str) -> str:
        new = (new or "").strip()
        if old not in self.profiles or not new or new == old:
            return old
        if new in self.profiles:
            return old                      # 남의 것을 덮어쓰지 않습니다
        self.profiles[old].name = new
        # 목록 순서는 사용자가 만든 순서입니다. 키만 바꾸고 순서는 그대로 둡니다.
        self.profiles = {(new if k == old else k): v for k, v in self.profiles.items()}
        if self.current == old:
            self.current = new
        return new

    def delete(self, name: str) -> None:
        """마지막 하나는 지우지 않습니다. 화면이 텅 비면 사용자가 당황합니다."""
        if name in self.profiles and len(self.profiles) > 1:
            self.profiles.pop(name)
            if self.current == name:
                self.current = next(iter(self.profiles))

    def duplicate(self, name: str) -> str:
        if name not in self.profiles:
            return self.current
        src = self.profiles[name]
        new_name = self.create(f"{name} 복사본")
        self.profiles[new_name] = Portfolio.from_dict(src.to_dict())
        self.profiles[new_name].name = new_name
        return new_name


# ---------------------------------------------------------------------
def new_store() -> Store:
    s = Store()
    s.profiles[DEFAULT_PROFILE] = Portfolio(name=DEFAULT_PROFILE)
    s.current = DEFAULT_PROFILE
    return s


def to_dict(store: Store) -> dict:
    return {
        "schema": SCHEMA,
        "version": SCHEMA_VERSION,
        "app_version": config.APP_VERSION,
        "saved_at": config.now_local().isoformat(timespec="seconds"),
        "current": store.current,
        "profiles": {name: p.to_dict() for name, p in store.profiles.items()},
    }


def dumps(store: Store) -> str:
    return json.dumps(to_dict(store), ensure_ascii=False, indent=1)


def from_dict(d: dict) -> Store:
    """dict -> Store. 못 읽는 부분은 버리고 읽을 수 있는 만큼만 복원합니다."""
    if not isinstance(d, dict):
        return new_store()

    raw = d.get("profiles")
    profiles: dict[str, Portfolio] = {}
    if isinstance(raw, dict):
        for name, pd in raw.items():
            p = Portfolio.from_dict(pd if isinstance(pd, dict) else {})
            p.name = str(name)
            profiles[str(name)] = p
    elif isinstance(d.get("holdings"), list):
        # 포트폴리오 하나만 들어 있는 옛 형식도 받아 줍니다.
        p = Portfolio.from_dict(d)
        profiles[p.name] = p

    if not profiles:
        return new_store()

    current = str(d.get("current") or "")
    if current not in profiles:
        current = next(iter(profiles))
    return Store(profiles=profiles, current=current, saved_at=str(d.get("saved_at") or ""))


def loads(text: str) -> tuple[Store | None, str]:
    """JSON 문자열 -> (Store, 오류메시지).

    실패해도 예외를 던지지 않습니다. 화면이 빨간 에러로 죽는 대신
    "이 파일은 못 읽었어요" 를 보여주게 하려고요.
    """
    if not text or not str(text).strip():
        return None, "내용이 비어 있습니다."
    try:
        d = json.loads(text)
    except (ValueError, TypeError):
        return None, "JSON 형식이 아니어서 읽지 못했습니다. 저장했던 파일이 맞는지 확인해 주세요."
    if isinstance(d, dict) and d.get("schema") not in (None, SCHEMA):
        return None, f"이 앱에서 저장한 파일이 아닌 것 같습니다 (schema={d.get('schema')!r})."
    try:
        return from_dict(d), ""
    except Exception:  # noqa: BLE001
        return None, "파일 구조가 예상과 달라 읽지 못했습니다."


def count_holdings(store: Store) -> int:
    return sum(len(p.holdings) for p in store.profiles.values())

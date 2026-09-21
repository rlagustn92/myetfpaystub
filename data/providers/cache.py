"""
data/providers/cache.py  --  아주 단순한 TTL 캐시
=================================================

무료 소스로 버티는 비결의 90% 가 여기 있습니다. 본체는 20줄인데, 중요한 건
코드가 아니라 **키를 어떻게 설계하느냐**입니다 (docs/DATA_SOURCES.md §5).

핵심 성질 셋:

1. **프로세스 전역**입니다. Streamlit 에서는 모든 접속자가 같은 캐시를 공유합니다.
   먼저 들어온 사람이 SCHD 를 조회해두면 다음 사람은 호출이 안 나갑니다.
   사용자가 늘어도 API 호출은 거의 안 늘어납니다.
2. **실패는 절대 캐싱하지 않습니다.** 예외가 나면 저장 없이 그대로 던집니다.
   실패를 캐싱하면 "🔄 정보 업데이트" 버튼이 무력해집니다.
3. **디스크를 안 씁니다.** 무료 호스팅은 파일 쓰기가 막혀 있거나 재시작 때 날아갑니다.
"""

from __future__ import annotations

import time
from typing import Any, Callable

_STORE: dict[str, tuple[float, Any]] = {}


def get_or_set(key: str, ttl_seconds: int, producer: Callable[[], Any],
               *, ttl_of: Callable[[Any], int] | None = None) -> Any:
    """key 에 유효한 캐시가 있으면 반환, 없으면 producer() 를 실행해 저장 후 반환.

    `ttl_of` — **이미 받아둔 값을 보고 유효기간을 다시 정하는** 콜백.

    왜 필요한가: 지나간 달의 분배금은 **다시 안 바뀝니다.** 그런데 TTL 을 하나로
    두면 몇 년 전 자료까지 하루마다 다시 받아옵니다(TIGER 는 달마다 따로 불러야
    해서 한 종목에 HTTP 43번이 나갔습니다). 값을 보고 "이 달은 끝났다" 를
    판단할 수 있으면, 끝난 달은 아주 길게 두고 **아직 채워지는 중인 달만**
    자주 받으면 됩니다.

    `ttl_of` 는 저장된 값을 받아 그 값에 맞는 유효기간(초)을 돌려줍니다.
    안 주면 `ttl_seconds` 를 그대로 씁니다.
    """
    now = time.time()
    hit = _STORE.get(key)
    if hit is not None:
        ttl = ttl_seconds if ttl_of is None else ttl_of(hit[1])
        if (now - hit[0]) < ttl:
            return hit[1]
    value = producer()          # 예외가 나면 저장하지 않고 그대로 전파
    _STORE[key] = (now, value)
    return value


def invalidate(prefix: str | None = None) -> int:
    """캐시 무효화. prefix 를 주면 그 접두사로 시작하는 키만 삭제. 삭제한 개수를 반환."""
    global _STORE
    if prefix is None:
        n = len(_STORE)
        _STORE = {}
        return n
    keys = [k for k in _STORE if k.startswith(prefix)]
    for k in keys:
        _STORE.pop(k, None)
    return len(keys)


def stats() -> dict:
    return {"entries": len(_STORE), "keys": sorted(_STORE.keys())}

"""写接口限流（需求 5.2）：进程内滑动窗口计数器。

单机单进程部署下够用（见项目报告 §3.3 已知限制）。
多实例部署时把 _BUCKETS 换成 Redis 等共享存储即可，接口保持不变。
"""
from __future__ import annotations

import threading
import time
from collections import deque

_LOCK = threading.Lock()
_BUCKETS: dict[str, deque[float]] = {}
# 键容量上限：超限时清理已过窗口的空桶，避免长期运行内存无界增长
_MAX_KEYS = 20000


def allow(key: str, limit: int, window_seconds: int = 60) -> tuple[bool, int]:
    """滑动窗口判定：返回 (是否放行, 建议 Retry-After 秒数)。

    limit <= 0 表示不限流。
    """
    if limit <= 0:
        return True, 0

    now = time.monotonic()
    cutoff = now - window_seconds
    with _LOCK:
        if len(_BUCKETS) >= _MAX_KEYS:
            _prune(cutoff)
        bucket = _BUCKETS.setdefault(key, deque())
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= limit:
            retry = max(1, int(window_seconds - (now - bucket[0])) + 1)
            return False, retry
        bucket.append(now)
        return True, 0


def _prune(cutoff: float) -> None:
    """清理已过窗口的桶。调用方需持有 _LOCK。"""
    for key in [k for k, v in _BUCKETS.items() if not v or v[-1] <= cutoff]:
        _BUCKETS.pop(key, None)


def reset() -> None:
    """仅供测试/排查：清空全部计数。"""
    with _LOCK:
        _BUCKETS.clear()

"""限流验证脚本：纯标准库，验证写接口限流（需求 5.2）真的生效。

用法（在 backend 目录下，先启动 uvicorn）：
    .venv\\Scripts\\python.exe scripts\\check_ratelimit.py

做法：用一个**不存在的用户名**连续登录若干次。
- 前 RATE_LIMIT_LOGIN_PER_MINUTE 次应返回 401（用户名或密码错误）；
- 之后应返回 429（限流）。
用户名不存在 → 不会触发「5 次错误锁定」，不污染演示账号。

注意：登录限流按来源 IP 计数，本脚本会占满该 IP 的登录配额，
跑完后请等 60 秒再执行 e2e_check.py / demo_flow.py。
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402

settings = get_settings()
BASE = "http://127.0.0.1:8000/api/v1"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def post_login() -> tuple[int, str, str]:
    payload = json.dumps({"username": "__ratelimit_probe__", "password": "x"}).encode()
    req = urllib.request.Request(
        BASE + "/auth/login",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.read().decode("utf-8", "replace"), ""
    except urllib.error.HTTPError as exc:
        retry_after = exc.headers.get("Retry-After", "") if exc.headers else ""
        return exc.code, exc.read().decode("utf-8", "replace"), retry_after


def main() -> int:
    if not settings.RATE_LIMIT_ENABLED:
        print("RATE_LIMIT_ENABLED=false，限流已关闭，跳过验证。")
        return 0
    limit = settings.RATE_LIMIT_LOGIN_PER_MINUTE
    if limit <= 0:
        print(f"RATE_LIMIT_LOGIN_PER_MINUTE={limit}，未开启登录限流，跳过验证。")
        return 0

    attempts = limit + 5
    print(f"对 POST /auth/login 连发 {attempts} 次（限流阈值 {limit}/分钟）…")

    first_429: int | None = None
    retry_after = ""
    counts: dict[int, int] = {}

    for i in range(1, attempts + 1):
        status, body, ra = post_login()
        counts[status] = counts.get(status, 0) + 1
        if status == 429 and first_429 is None:
            first_429 = i
            retry_after = ra
            print(f"  第 {i} 次起被限流：{body[:80]}（Retry-After={ra}）")
        if i == 1:
            print(f"  第 1 次返回 {status}：{body[:60]}")

    print("\n结果统计：" + "，".join(f"HTTP {k} × {v}" for k, v in sorted(counts.items())))

    # 注意：登录限流按来源 IP 计数，若本分钟内已跑过 e2e_check/demo_flow，
    # 窗口里已经有记录，则 401 的次数会少于 limit —— 只要满足「先 401 后 429、
    # 且 429 出现在 limit+1 次以内、之后不再出现 401」即视为限流生效。
    n_401 = counts.get(401, 0)
    n_429 = counts.get(429, 0)
    ok = (
        first_429 is not None
        and n_401 == first_429 - 1
        and n_429 == attempts - first_429 + 1
        and n_401 <= limit
        and first_429 <= limit + 1
    )
    if ok:
        print(
            f"[PASS] 限流生效：前 {n_401} 次 401，第 {first_429} 次起连续 {n_429} 次 429"
            f"（阈值 {limit}/分钟，窗口内已有 {limit - n_401} 次历史计数）。"
        )
        return 0
    print(
        f"[FAIL] 预期「先 401 后 429 且第 {limit + 1} 次以内开始 429」，"
        f"实际 401 × {n_401}、429 × {n_429}，首次 429 出现在第 {first_429} 次"
        f"（Retry-After={retry_after or '-'}）。"
    )
    if n_429 == 0:
        print("提示：后端可能未加载新增中间件，请重启 uvicorn 后再试。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

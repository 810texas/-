"""字段提取层自测：**不需要安装 PaddleOCR**，纯标准库喂「文本行」验证 10 个字段。

用法（在 backend 目录下，无需后端服务）：
    .venv\\Scripts\\python.exe scripts\\check_ocr_fields.py

覆盖：
1. 三个真实版式样例（增值税专用发票 / 数电票 / 红字发票，含 ¥、千分位、大写小写同行、负数）；
2. `normalize_amount` / `normalize_date` 的边界；
3. 字段名与 `app.services.ocr.service.FIELD_MAP` 一致（防止两边漂移）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.ocr.invoice_fields import (  # noqa: E402
    FIELD_NAMES,
    TextLine,
    extract_invoice_fields,
    normalize_amount,
    normalize_date,
)
from app.services.ocr.service import FIELD_MAP  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PASSED: list[str] = []
FAILED: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    if ok:
        PASSED.append(name)
        print(f"[PASS] {name}" + (f" — {detail}" if detail else ""))
    else:
        FAILED.append(name)
        print(f"[FAIL] {name}" + (f" — {detail}" if detail else ""))


def lines_of(*texts: str) -> list[TextLine]:
    """把文本行列表包成 OCR 结果（置信度给个稳定值，便于断言）。"""
    return [TextLine(text=t, confidence=0.97) for t in texts]


# ---------------------------------------------------------------- 样例 1：增值税专用发票
CASE_SPECIAL = lines_of(
    "浙江增值税专用发票",
    "发票代码 044001900111",
    "发票号码 12345678",
    "开票日期 2026年09月24日",
    "购买方信息",
    "名 称: 示例科技有限公司",
    "纳税人识别号: 91330100MA2XXXXXXX",
    "销售方信息",
    "名 称: 杭州云启网络科技有限公司",
    "纳税人识别号: 91330100123456789X",
    "金额 838.57",
    "税额 50.31",
    "价税合计(大写) 捌佰捌拾捌圆捌角捌分 (小写) ¥888.88",
)

# ---------------------------------------------------------------- 样例 2：数电票（无发票代码）
CASE_ESIGN = lines_of(
    "电子发票（数电票）",
    "发票号码: 24312000000087654321",
    "开票日期: 2026/08/15",
    "购买方名称: 示例科技有限公司",
    "统一社会信用代码/纳税人识别号: 91330100MA2XXXXXXX",
    "销售方名称: 上海远景办公用品有限公司",
    "统一社会信用代码/纳税人识别号: 91310115MA1H88888Y",
    "合计金额 ¥ 1,234.50",
    "合计税额 ¥ 74.07",
    "价税合计(小写) ¥ 1,308.57",
)

# ---------------------------------------------------------------- 样例 3：红字发票（负数）
CASE_RED = lines_of(
    "红字发票",
    "发票代码 044001900222",
    "发票号码 87654321",
    "开票日期 2026年7月1日",
    "购买方",
    "名称: 示例科技有限公司",
    "纳税人识别号: 91330100MA2XXXXXXX",
    "销售方",
    "名称: 北京中科出行服务有限公司",
    "金额 -200.00",
    "税额 -12.00",
    "价税合计(小写) -¥212.00",
)

# ---------------------------------------------------------------- 样例 4：脏数据（应该不抛异常）
CASE_GARBAGE = lines_of("这是一张看不清的图", "", "OCR 什么也没识别出来")


def expect(case_name: str, texts: list[TextLine], expected: dict[str, str | None]) -> None:
    got = extract_invoice_fields(texts)
    for field, want in expected.items():
        value = got[field].value
        check(
            f"{case_name} · {field}",
            value == want,
            f"得到 {value!r}，期望 {want!r}",
        )


def main() -> int:
    print("=== 0. 字段名一致性 ===")
    check(
        "提取层字段名与 service.FIELD_MAP 一致",
        tuple(FIELD_NAMES) == tuple(FIELD_MAP),
        f"{FIELD_NAMES} vs {tuple(FIELD_MAP)}",
    )
    check("字段数为 10", len(FIELD_NAMES) == 10, str(len(FIELD_NAMES)))

    print("\n=== 1. 增值税专用发票（含大写小写同行、千分位）===")
    expect(
        "专票",
        CASE_SPECIAL,
        {
            "invoice_type": "蓝字",
            "invoice_code": "044001900111",
            "invoice_no": "12345678",
            "invoice_date": "2026-09-24",
            "buyer_name": "示例科技有限公司",
            "buyer_tax_no": "91330100MA2XXXXXXX",
            "seller_name": "杭州云启网络科技有限公司",
            "amount_excl_tax": "838.57",
            "tax_amount": "50.31",
            "total_amount": "888.88",
        },
    )

    print("\n=== 2. 数电票（20 位号码、无发票代码、¥ 与千分位）===")
    expect(
        "数电票",
        CASE_ESIGN,
        {
            "invoice_type": "数电票",
            "invoice_code": None,
            "invoice_no": "24312000000087654321",
            "invoice_date": "2026-08-15",
            "buyer_name": "示例科技有限公司",
            "buyer_tax_no": "91330100MA2XXXXXXX",
            "seller_name": "上海远景办公用品有限公司",
            "amount_excl_tax": "1234.50",
            "tax_amount": "74.07",
            "total_amount": "1308.57",
        },
    )

    print("\n=== 3. 红字发票（负数金额，负号在货币符号前）===")
    expect(
        "红字",
        CASE_RED,
        {
            "invoice_type": "红字",
            "invoice_code": "044001900222",
            "invoice_no": "87654321",
            "invoice_date": "2026-07-01",
            "buyer_name": "示例科技有限公司",
            "buyer_tax_no": "91330100MA2XXXXXXX",
            "seller_name": "北京中科出行服务有限公司",
            "amount_excl_tax": "-200.00",
            "tax_amount": "-12.00",
            "total_amount": "-212.00",
        },
    )

    print("\n=== 4. 脏数据：字段全部为 None，且不抛异常 ===")
    try:
        garbage = extract_invoice_fields(CASE_GARBAGE)
        check(
            "无法识别时返回 None 而不是异常",
            all(garbage[f].value is None for f in FIELD_NAMES),
            str({f: garbage[f].value for f in FIELD_NAMES}),
        )
    except Exception as exc:  # noqa: BLE001
        check("无法识别时返回 None 而不是异常", False, f"抛了 {type(exc).__name__}: {exc}")

    print("\n=== 5. 空输入 ===")
    empty = extract_invoice_fields([])
    check("空文本行列表不报错", all(empty[f].value is None for f in FIELD_NAMES))

    print("\n=== 6. 金额/日期归一化 ===")
    for raw, want in (
        ("¥ 1,234.50", "1234.50"),
        ("￥888.88", "888.88"),
        ("1，234.50", "1234.50"),  # 全角逗号
        ("-¥212.00", "-212.00"),
        ("+88", "88.00"),
        ("12", "12.00"),
        ("12.5", "12.50"),
        ("abc", None),
        ("", None),
        (None, None),
    ):
        got = normalize_amount(raw)
        check(f"金额 {raw!r} → {want!r}", got == want, f"得到 {got!r}")

    for raw, want in (
        ("2026年09月24日", "2026-09-24"),
        ("2026-08-15", "2026-08-15"),
        ("2026/8/5", "2026-08-05"),
        ("开票日期 2026.7.1", "2026-07-01"),
        ("2026年13月40日", None),  # 非法日期不能崩
        ("没有日期", None),
    ):
        got = normalize_date(raw)
        check(f"日期 {raw!r} → {want!r}", got == want, f"得到 {got!r}")

    total = len(PASSED) + len(FAILED)
    print(f"\n===== 结果：{len(PASSED)}/{total} 通过 =====")
    if FAILED:
        print("失败项：")
        for name in FAILED:
            print(f"  - {name}")
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

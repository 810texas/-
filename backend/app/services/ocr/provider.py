"""OCR 抽象与 provider 注册：mock（默认）/ paddle（本地部署，需自装依赖）。"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Protocol


@dataclass
class OcrField:
    """单个识别字段：值 + 置信度。"""

    value: str = ""
    confidence: float = 0.0


@dataclass
class OcrResult:
    """识别结果：字段字典 + 整体置信度 + provider 标识。"""

    fields: dict[str, OcrField] = field(default_factory=dict)
    confidence: float = 0.0
    provider: str = "mock"
    raw_text: str = ""


class OcrProvider(Protocol):
    name: str

    def recognize(self, image_bytes: bytes, hint: str = "") -> OcrResult: ...


class MockOcrProvider:
    """开发期 provider：由文件哈希派生稳定结果，无需模型与网络（需求 2.2）。"""

    name = "mock"

    SELLERS = ["杭州云启网络科技有限公司", "上海远景办公用品有限公司", "北京中科出行服务有限公司"]
    ITEMS = ["技术服务费", "办公用品", "差旅住宿费", "城市交通费", "会议餐饮费"]

    def recognize(self, image_bytes: bytes, hint: str = "") -> OcrResult:
        seed = int(hashlib.sha256(image_bytes).hexdigest()[:12], 16)
        rnd = random.Random(seed)

        invoice_type = rnd.choices(["蓝字", "红字", "数电票"], weights=[60, 10, 30])[0]
        invoice_no = str(rnd.randint(10_000_000, 99_999_999))
        # 数电票无发票代码（需求 4.2）
        invoice_code = None if invoice_type == "数电票" else str(rnd.randint(0, 9999)).zfill(10)

        amount_excl = round(rnd.uniform(30, 2000), 2)
        tax = round(amount_excl * rnd.choice([0.03, 0.06, 0.09, 0.13]), 2)
        total = round(amount_excl + tax, 2)
        if invoice_type == "红字":
            amount_excl, tax, total = -amount_excl, -tax, -total

        invoice_day = date.today() - timedelta(days=rnd.randint(0, 45))

        def f(value: str, low: float, high: float) -> OcrField:
            return OcrField(value=value, confidence=round(rnd.uniform(low, high), 2))

        fields = {
            "invoice_type": f(invoice_type, 0.90, 0.99),
            "invoice_code": f(invoice_code or "", 0.88, 0.99),
            "invoice_no": f(invoice_no, 0.90, 0.99),
            "invoice_date": f(invoice_day.isoformat(), 0.88, 0.99),
            "buyer_name": f("示例科技有限公司", 0.86, 0.99),
            "buyer_tax_no": f("91330100MA2XXXXXXX", 0.85, 0.98),
            "seller_name": f(rnd.choice(self.SELLERS), 0.85, 0.99),
            "amount_excl_tax": f(f"{amount_excl:.2f}", 0.83, 0.99),
            "tax_amount": f(f"{tax:.2f}", 0.83, 0.99),
            "total_amount": f(f"{total:.2f}", 0.83, 0.99),
            "item_name": f(rnd.choice(self.ITEMS), 0.80, 0.98),
        }
        overall = round(sum(x.confidence for x in fields.values()) / len(fields), 2)
        text = "\n".join(f"{k}: {v.value}" for k, v in fields.items())
        return OcrResult(fields=fields, confidence=overall, provider=self.name, raw_text=text)


class PaddleOcrProvider:
    """二期/生产 provider 占位：本地 PaddleOCR 部署后在此接入（需求 2.1）。

    注意：OCR 属 CPU 密集任务，正式接入时应交后台 Worker 进程池，
    不应在请求线程内直接调用（需求 5.1）。
    """

    name = "paddle"

    def recognize(self, image_bytes: bytes, hint: str = "") -> OcrResult:
        raise NotImplementedError(
            "PaddleOCR provider 未安装。请执行 pip install paddleocr paddlepaddle，"
            "并在 app/services/ocr/paddle_provider.py 中接入识别与字段映射逻辑。"
        )


_REGISTRY: dict[str, OcrProvider] = {
    "mock": MockOcrProvider(),
    "paddle": PaddleOcrProvider(),
}


def get_provider(name: str) -> OcrProvider:
    provider = _REGISTRY.get(name)
    if provider is None:
        raise ValueError(f"未知 OCR provider：{name}（可选 {'/'.join(_REGISTRY)}）")
    return provider

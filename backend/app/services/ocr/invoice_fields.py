"""发票字段提取层：把 PaddleOCR 的「文本行」转成 10 个结构化字段。

设计要点
--------
1. **纯标准库**（只用 ``re`` / ``datetime``）：不依赖 paddleocr / numpy / cv2，
   因此可以完全离线单测（见 ``scripts/check_ocr_fields.py``），也方便后续换 OCR 引擎时复用。
2. **关键词定位 + 正则** 两步走：先用关键词把票面切成「购买方区 / 销售方区」，
   再在区块内套正则，避免「名称」这类重复标签互相串味。
3. **命中不了就返回 None，绝不抛异常**：字段缺失由上层（provider）兜底成空串，
   这样上传链路只会得到一张「待人工确认」的发票，而不是 500。
4. 关键词与正则全部是模块级常量，**改这里就能调识别口径**，不必动引擎代码。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Sequence

# 提取层输出的字段名，必须与 app.services.ocr.service.FIELD_MAP 一致
# （scripts/check_ocr_fields.py 会断言两者相等，防止两边漂移）
FIELD_NAMES: tuple[str, ...] = (
    "invoice_type",
    "invoice_code",
    "invoice_no",
    "invoice_date",
    "buyer_name",
    "buyer_tax_no",
    "seller_name",
    "amount_excl_tax",
    "tax_amount",
    "total_amount",
)

AMOUNT_FIELDS: tuple[str, ...] = ("amount_excl_tax", "tax_amount", "total_amount")

# 与 models/document.py 的 INVOICE_TYPES 保持一致
INVOICE_TYPE_BLUE = "蓝字"
INVOICE_TYPE_RED = "红字"
INVOICE_TYPE_ESIGN = "数电票"


@dataclass(frozen=True)
class TextLine:
    """一行 OCR 文本：文本 + PaddleOCR 给出的置信度。"""

    text: str
    confidence: float = 0.0


@dataclass(frozen=True)
class Extracted:
    """单个字段的提取结果；没命中时 value / confidence 均为 None。"""

    value: str | None = None
    confidence: float | None = None
    source: str = ""  # 命中的原始文本行，排查用


# --------------------------------------------------------------------------
# 关键词表（调口径改这里）
# --------------------------------------------------------------------------

# 发票类型：按优先级从上到下判定
TYPE_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (INVOICE_TYPE_RED, ("红字", "红字发票", "负数发票")),
    (INVOICE_TYPE_ESIGN, ("数电票", "全电发票", "电子发票(数电票)")),
    (
        INVOICE_TYPE_BLUE,
        ("增值税专用发票", "专用发票", "增值税普通发票", "电子普通发票", "普通发票", "电子发票"),
    ),
)

# 区块分隔词：用于把「购买方信息」和「销售方信息」两段分开
BUYER_SECTION_KEYWORDS: tuple[str, ...] = ("购买方", "购方", "买方")
SELLER_SECTION_KEYWORDS: tuple[str, ...] = ("销售方", "销方", "卖方")

NAME_LABELS: tuple[str, ...] = ("名称", "名 称")
TAX_NO_LABELS: tuple[str, ...] = (
    "纳税人识别号",
    "统一社会信用代码",
    "纳税人识别号码",
    "税号",
)

EXCL_TAX_LABELS: tuple[str, ...] = (
    "不含税金额",
    "金额合计",
    "合计金额",
    "不含税价",
    "金额",
)
TAX_AMOUNT_LABELS: tuple[str, ...] = ("税额合计", "增值税额", "税额")
TOTAL_LABELS: tuple[str, ...] = ("价税合计", "小写")

# 公司名兜底：命中这些后缀却没有「名称」标签时也认
COMPANY_SUFFIXES: tuple[str, ...] = (
    "有限公司",
    "有限责任公司",
    "股份有限公司",
    "公司",
    "厂",
    "店",
    "中心",
    "事务所",
    "银行",
    "酒店",
    "宾馆",
    "超市",
)

_NUM_TOKEN = r"([-+]?[¥￥]?\s*[-+]?\d[\d,]*(?:\.\d{1,2})?)"


def _label_regex(labels: Sequence[str], *, gap: int = 24) -> re.Pattern[str]:
    """生成「标签 + 最多 gap 个非数字字符 + 数字」的正则。

    间隔字符里 **排除数字、货币符号与正负号**，否则 ``价税合计(小写)-¥212.00``
    的前导负号会被间隔吃掉，金额符号就丢了。
    """
    alt = "|".join(re.escape(x) for x in labels)
    return re.compile(r"(?:%s)[^0-9¥￥+\-]{0,%d}%s" % (alt, gap, _NUM_TOKEN))


INVOICE_CODE_RE = re.compile(r"发票代码[^0-9]{0,8}(\d{10,12})")
INVOICE_NO_RE = re.compile(r"发票号码[^0-9]{0,8}(\d{8,20})")
DATE_RE = re.compile(r"(\d{4})\s*[年\-/.]\s*(\d{1,2})\s*[月\-/.]\s*(\d{1,2})\s*日?")
TAX_NO_VALUE_RE = re.compile(r"([0-9A-Z]{15,20})")

EXCL_TAX_RE = _label_regex(EXCL_TAX_LABELS)
TAX_AMOUNT_RE = _label_regex(TAX_AMOUNT_LABELS)
TOTAL_RE = _label_regex(TOTAL_LABELS)

# 金额字段的互斥词：避免把「价税合计」的金额当成「不含税金额」
EXCL_TAX_FORBID: tuple[str, ...] = ("价税合计", "大写")
TAX_AMOUNT_FORBID: tuple[str, ...] = ("价税合计", "税率", "不含税")
# 价税合计行常把大写、小写印在同一行（大写是中文数字，正则不会命中），因此这里不排除「大写」
TOTAL_FORBID: tuple[str, ...] = ()


# --------------------------------------------------------------------------
# 归一化小工具
# --------------------------------------------------------------------------

def _to_halfwidth(text: str) -> str:
    """全角 ASCII（含全角数字/字母/冒号/括号）转半角。中文字符不受影响。"""
    out = []
    for ch in text:
        code = ord(ch)
        if code == 0x3000:
            out.append(" ")
        elif 0xFF01 <= code <= 0xFF5E:
            out.append(chr(code - 0xFEE0))
        else:
            out.append(ch)
    return "".join(out)


def _compact(text: str) -> str:
    """去空白 + 全角转半角，用于关键词与正则匹配。"""
    return re.sub(r"\s+", "", _to_halfwidth(text))


def normalize_amount(raw: str | None) -> str | None:
    """金额格式化：去掉 ¥ / ￥ / 空格 / 千分位，全角转半角，输出两位小数字符串。

    ``"¥ 1,234.5"`` → ``"1234.50"``；无法解析时返回 None。
    """
    if not raw:
        return None
    s = _compact(raw).lstrip("+")
    for symbol in ("¥", "￥", ",", "元"):
        s = s.replace(symbol, "")
    s = s.replace("。", ".")
    match = re.fullmatch(r"(-?)(\d+)(?:\.(\d{1,2}))?", s)
    if not match:
        return None
    sign = "-" if match.group(1) else ""
    decimals = (match.group(3) or "0").ljust(2, "0")
    return f"{sign}{match.group(2)}.{decimals}"


def normalize_date(raw: str | None) -> str | None:
    """日期归一化为 ISO ``YYYY-MM-DD``（``service._coerce`` 只认这个格式）。"""
    if not raw:
        return None
    match = DATE_RE.search(_compact(raw))
    if not match:
        return None
    year, month, day = (int(x) for x in match.groups())
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


# --------------------------------------------------------------------------
# 逐字段提取
# --------------------------------------------------------------------------

def _iter_matches(line: TextLine) -> str:
    return _compact(line.text)


def _scan(
    lines: Sequence[TextLine],
    pattern: re.Pattern[str],
    *,
    forbid: Sequence[str] = (),
    start: int = 0,
    end: int | None = None,
    group: int = 1,
) -> Extracted:
    """在指定行范围内找第一个命中：返回匹配文本 + 该行置信度。

    ``group=0`` 用于取整个匹配（例如日期，DATE_RE 的 group(1) 只是年份）。
    """
    for line in lines[start:end]:
        text = _iter_matches(line)
        if not text:
            continue
        if any(word in text for word in forbid):
            continue
        match = pattern.search(text)
        if match:
            return Extracted(value=match.group(group), confidence=line.confidence, source=line.text)
    return Extracted()


def _looks_like_company(text: str) -> bool:
    return any(suffix in text for suffix in COMPANY_SUFFIXES)


def _zone_bounds(lines: Sequence[TextLine]) -> tuple[int, int, int | None]:
    """返回 (购买方区起点, 销售方区起点或 len, 销售方关键词行号或 None)。"""
    buyer_start: int | None = None
    seller_start: int | None = None
    for idx, line in enumerate(lines):
        text = _iter_matches(line)
        if buyer_start is None and any(k in text for k in BUYER_SECTION_KEYWORDS):
            buyer_start = idx
        if seller_start is None and any(k in text for k in SELLER_SECTION_KEYWORDS):
            seller_start = idx
    if buyer_start is None:
        buyer_start = 0
    if seller_start is None:
        return buyer_start, len(lines), None
    if seller_start < buyer_start:
        # 关键词顺序异常时退化为「整段都是购买方」
        return buyer_start, len(lines), seller_start
    return buyer_start, seller_start, seller_start


def _extract_party(
    lines: Sequence[TextLine], start: int, end: int, *, kind: str
) -> tuple[Extracted, Extracted]:
    """在区块内提取 (名称, 税号)。"""
    name = Extracted()
    tax_no = Extracted()

    for offset, line in enumerate(lines[start:end]):
        text = _iter_matches(line)
        if not text:
            continue

        # 名称：优先带「名称」标签，其次含公司后缀的整行
        if name.value is None:
            for label in NAME_LABELS:
                idx = text.find(_compact(label))
                if idx < 0:
                    continue
                tail = text[idx + len(_compact(label)):].lstrip(":：")
                tail = tail.strip(":：")
                if tail and not any(t in tail for t in TAX_NO_LABELS):
                    candidate = _clean_party_name(tail)
                    if candidate:
                        name = Extracted(
                            value=candidate, confidence=line.confidence, source=line.text
                        )
                        break
            if name.value is None and "名称" not in text and _looks_like_company(text):
                candidate = _clean_party_name(text)
                if candidate and not any(t in text for t in TAX_NO_LABELS):
                    name = Extracted(value=candidate, confidence=line.confidence, source=line.text)

        # 税号：带标签优先，其次整行 15–20 位大写字母数字
        if tax_no.value is None:
            if any(label in text for label in TAX_NO_LABELS):
                match = TAX_NO_VALUE_RE.search(text)
                if match:
                    tax_no = Extracted(
                        value=match.group(1), confidence=line.confidence, source=line.text
                    )
            elif re.fullmatch(r"[0-9A-Z]{15,20}", text) and re.search(r"\d", text):
                tax_no = Extracted(value=text, confidence=line.confidence, source=line.text)

    if name.value is None:
        name = Extracted(source=f"（{kind}区未命中名称）")
    return name, tax_no


def _clean_party_name(text: str) -> str | None:
    """去掉冒号、标签残留与括号内容，返回公司名；空则 None。"""
    value = text.strip(":：")
    value = re.sub(r"^(名称|名\s*称)", "", value)
    value = value.strip(":：")
    value = re.sub(r"[(（].*?[)）]", "", value).strip()
    if not value or len(value) < 2:
        return None
    return value


def _detect_invoice_type(full_text: str) -> str | None:
    for invoice_type, keywords in TYPE_KEYWORDS:
        if any(_compact(k) in full_text for k in keywords):
            return invoice_type
    return None


def _fallback_invoice_no(lines: Sequence[TextLine]) -> Extracted:
    """没有「发票号码」标签时：找独立的 8 位或 20 位数字串（传统票 8 位 / 数电票 20 位）。"""
    for line in lines:
        text = _iter_matches(line)
        if not text:
            continue
        for candidate in re.findall(r"\d{8}|\d{20}", text):
            if re.fullmatch(r"0+", candidate):
                continue
            return Extracted(value=candidate, confidence=line.confidence, source=line.text)
    return Extracted()


def extract_invoice_fields(lines: Sequence[TextLine]) -> dict[str, Extracted]:
    """把 OCR 文本行转成 10 个字段；未命中一律返回 value=None。"""
    lines = list(lines)
    result: dict[str, Extracted] = {name: Extracted() for name in FIELD_NAMES}
    full_text = _compact("".join(line.text for line in lines))

    buyer_start, seller_start, _ = _zone_bounds(lines)

    # 发票类型：先按关键词判定，再用「有没有发票代码」互校（数电票没有代码）
    invoice_type = _detect_invoice_type(full_text)
    invoice_code = _scan(lines, INVOICE_CODE_RE)
    if invoice_code.value and invoice_type == INVOICE_TYPE_ESIGN:
        invoice_type = INVOICE_TYPE_BLUE

    invoice_no = _scan(lines, INVOICE_NO_RE)
    if invoice_no.value is None:
        invoice_no = _fallback_invoice_no(lines)

    date_hit = _scan(lines, DATE_RE, group=0)
    invoice_date = Extracted(
        value=normalize_date(date_hit.value),
        confidence=date_hit.confidence if date_hit.value else None,
        source=date_hit.source,
    )

    buyer_name, buyer_tax_no = _extract_party(lines, buyer_start, seller_start, kind="购买方")
    seller_name, _ = _extract_party(lines, seller_start, len(lines), kind="销售方")

    excl_hit = _scan(lines, EXCL_TAX_RE, forbid=EXCL_TAX_FORBID)
    tax_hit = _scan(lines, TAX_AMOUNT_RE, forbid=TAX_AMOUNT_FORBID)
    total_hit = _scan(lines, TOTAL_RE, forbid=TOTAL_FORBID)

    result["invoice_type"] = Extracted(value=invoice_type, confidence=None, source="")
    result["invoice_code"] = Extracted(
        value=invoice_code.value, confidence=invoice_code.confidence, source=invoice_code.source
    )
    result["invoice_no"] = Extracted(
        value=invoice_no.value, confidence=invoice_no.confidence, source=invoice_no.source
    )
    result["invoice_date"] = invoice_date
    result["buyer_name"] = buyer_name
    result["buyer_tax_no"] = buyer_tax_no
    result["seller_name"] = seller_name
    result["amount_excl_tax"] = Extracted(
        value=normalize_amount(excl_hit.value),
        confidence=excl_hit.confidence if excl_hit.value else None,
        source=excl_hit.source,
    )
    result["tax_amount"] = Extracted(
        value=normalize_amount(tax_hit.value),
        confidence=tax_hit.confidence if tax_hit.value else None,
        source=tax_hit.source,
    )
    result["total_amount"] = Extracted(
        value=normalize_amount(total_hit.value),
        confidence=total_hit.confidence if total_hit.value else None,
        source=total_hit.source,
    )
    return result

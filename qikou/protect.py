# -*- coding: utf-8 -*-
"""特殊片段保护：代码块 + URL。"""

from __future__ import annotations

import re
from typing import List, Sequence, Tuple

from .patterns import (
    CODE_RE, URL_RE, PH_RE,
    PH_OPEN, PH_CLOSE, PH_ESCAPE,
)

__all__ = ["protect_special", "restore_special", "visible_len", "index_at_len"]


def _escape(text: str) -> str:
    """把与占位符冲突的字符转义，保证占位符可唯一识别。

    规则：``U+E002``（转义符）自身加倍；``U+E000`` / ``U+E001`` 各加一个
    转义符前缀。:func:`_unescape` 严格按"遇到转义符就吃两个字符"解码，
    因此对任意输入都是可逆的（含嵌套转义符）。
    """
    out = text.replace(PH_ESCAPE, PH_ESCAPE + PH_ESCAPE)
    for ch in (PH_OPEN, PH_CLOSE):
        out = out.replace(ch, PH_ESCAPE + ch)
    return out


def _unescape(text: str) -> str:
    out = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] == PH_ESCAPE and i + 1 < n:
            out.append(text[i + 1])
            i += 2
        else:
            out.append(text[i])
            i += 1
    return ''.join(out)


def protect_special(text: str) -> Tuple[str, List[str]]:
    """把代码块和 URL 替换成占位符，返回 (替换后文本, 片段列表)。

    顺序：代码块先整体收走，URL 最后匹配；URL 的字符类排除占位符字符，以免
    一口吞掉刚插入的占位符。``"URL 紧贴代码块"``（如
    ``https://a.com/a`` + 三个反引号 + ``code`` + 三个反引号）曾因此把代码块
    整段丢掉，输出里留下字面的占位符。

    占位符使用私有使用区字符（``U+E000`` / ``U+E001``），与常见文本不重叠；
    输入自身若含这两个字符，会先被转义到 ``U+E002`` / ``U+E003``，
    :func:`restore_special` 还原时再转回，因此**往返无损**（包括输入里带
    NUL 或占位符形状片段的场景，见 2026-11 审计 QK-06）。
    """
    blocks: List[str] = []

    def repl(m: "re.Match[str]") -> str:
        blocks.append(m.group(0))
        return PH_OPEN + str(len(blocks) - 1) + PH_CLOSE

    text = _escape(text)
    text = CODE_RE.sub(repl, text)
    text = URL_RE.sub(repl, text)
    return text, blocks


def _block(blocks: Sequence[str], idx: int) -> "str | None":
    """占位符下标 -> 原片段；越界时返回 None（安全网，正常路径不会走到）。"""
    if 0 <= idx < len(blocks):
        return blocks[idx]
    return None


def restore_special(text: str, blocks: Sequence[str]) -> str:
    """把占位符换回原片段（**单趟**），并还原转义字符。

    刻意不做多趟"展开到不动点"：展开后的文本可能因拼接重新拼出占位符形状，
    被下一趟误当成占位符替换掉；片段互相引用时更会指数膨胀。嵌套已在
    :func:`protect_special` 的源头堵死，单趟就足够，而且行为完全可预测。
    """
    if not blocks:
        return _unescape(text)

    def sub(m: "re.Match[str]") -> str:
        b = _block(blocks, int(m.group(1)))
        return m.group(0) if b is None else b

    return _unescape(PH_RE.sub(sub, text))


def visible_len(text: str, blocks: Sequence[str]) -> int:
    """真实字符长度（占位符按原片段长度计）。"""
    if not blocks:
        return len(text)
    total = 0
    i = 0
    n = len(text)
    while i < n:
        m = PH_RE.match(text, i)
        if m:
            b = _block(blocks, int(m.group(1)))
            if b is not None:
                total += len(b)
                i = m.end()
                continue
        total += 1
        i += 1
    return total


def index_at_len(text: str, limit: int, blocks: Sequence[str]) -> int:
    """返回索引 i，使 visible_len(text[:i]) <= limit 且尽量大。"""
    real = 0
    i = 0
    n = len(text)
    while i < n:
        m = PH_RE.match(text, i)
        b = _block(blocks, int(m.group(1))) if m else None
        if b is not None:
            w = len(b)
            step = m.end() - i          # type: ignore[union-attr]
        else:
            w = 1
            step = 1
        if real + w > limit:
            break
        real += w
        i += step
    return i

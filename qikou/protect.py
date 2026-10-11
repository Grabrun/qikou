# -*- coding: utf-8 -*-
"""特殊片段保护：代码块 + URL。"""

from __future__ import annotations

import re
from typing import List, Sequence, Tuple

from .patterns import CODE_RE, URL_RE, PH_RE

__all__ = ["protect_special", "restore_special", "visible_len", "index_at_len"]


def protect_special(text: str) -> Tuple[str, List[str]]:
    """把代码块和 URL 替换成占位符，返回 (替换后文本, 片段列表)。

    顺序：代码块先整体收走，URL 最后匹配；URL 的字符类排除 ``\\x00``，以免
    一口吞掉刚插入的占位符。``"URL 紧贴代码块"``（如
    ``https://a.com/a`` + 三个反引号 + ``code`` + 三个反引号）曾因此把代码块
    整段丢掉，输出里留下字面的 ``\\x00N\\x00``。

    **已知限制**：占位符格式是 ``\\x00N\\x00``。若输入文本自身就含 NUL 控制
    字符（正常文本不会有），其中形如 ``\\x00<数字>\\x00`` 的片段会被误当作
    占位符。这里保证的是**不崩溃**（越界按下标安全网处理），不保证往返无损。
    """
    blocks = []

    def repl(m: "re.Match[str]") -> str:
        blocks.append(m.group(0))
        return '\x00%d\x00' % (len(blocks) - 1)

    text = CODE_RE.sub(repl, text)
    text = URL_RE.sub(repl, text)
    return text, blocks


def _block(blocks: Sequence[str], idx: int) -> "str | None":
    """占位符下标 -> 原片段；越界时返回 None（安全网，正常路径不会走到）。"""
    if 0 <= idx < len(blocks):
        return blocks[idx]
    return None


def restore_special(text: str, blocks: Sequence[str]) -> str:
    """把占位符换回原片段（**单趟**）。

    刻意不做多趟"展开到不动点"：展开后的文本可能因拼接重新拼出占位符形状，
    被下一趟误当成占位符替换掉（实测 NUL 被吃掉、URL 被凭空复制）；片段互相
    引用时更会指数膨胀。嵌套已在 :func:`protect_special` 的源头堵死，单趟
    就足够，而且行为完全可预测。
    """
    if not blocks:
        return text

    def sub(m: "re.Match[str]") -> str:
        b = _block(blocks, int(m.group(1)))
        return m.group(0) if b is None else b

    return PH_RE.sub(sub, text)


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

# -*- coding: utf-8 -*-
"""特殊片段保护：代码块 + URL。"""

from __future__ import annotations

import re
from typing import List, Sequence, Tuple

from .patterns import CODE_RE, URL_RE, PH_RE

__all__ = ["protect_special", "restore_special", "visible_len", "index_at_len"]


def protect_special(text: str) -> Tuple[str, List[str]]:
    """把代码块和 URL 替换成占位符，返回 (替换后文本, 片段列表)。"""
    blocks = []

    def repl(m: "re.Match[str]") -> str:
        blocks.append(m.group(0))
        return '\x00%d\x00' % (len(blocks) - 1)

    text = CODE_RE.sub(repl, text)
    text = URL_RE.sub(repl, text)
    return text, blocks


def restore_special(text: str, blocks: Sequence[str]) -> str:
    if not blocks:
        return text
    return PH_RE.sub(lambda m: blocks[int(m.group(1))], text)


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
            total += len(blocks[int(m.group(1))])
            i = m.end()
        else:
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
        if m:
            w = len(blocks[int(m.group(1))])
            step = m.end() - i
        else:
            w = 1
            step = 1
        if real + w > limit:
            break
        real += w
        i += step
    return i

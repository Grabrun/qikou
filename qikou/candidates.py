# -*- coding: utf-8 -*-
"""v3.0 候选切点：生成、分类、密度上限与覆盖骨架裁剪。

坐标与 ``splitter`` 一致：输入是 ``protect_special`` 之后的文本，切点位置
是 Python 字符串下标；占位符内部不产生候选。
"""

from __future__ import annotations

import math
from typing import Dict, List, Sequence, Set, Tuple

from .lexicon import SEPS, SEP_BASE_SCORE
from .patterns import PH_RE

__all__ = [
    "candidate_positions",
    "prune_candidates",
    "sep_base_at",
    "visible_prefix",
]

# 每 100 个可见字符最多保留的候选数（方案 rev.2 §3.3）。
CANDIDATE_CAP_PER_100 = 12

# 数字后常见的单位，用于「30 分钟」这类边界。
_UNIT_CHARS = set("元万亿个次天年月日时分秒人条款项%℃度米克斤")

# 与 splitter 的 _is_cjk 保持同一范围，避免循环导入。
_CJK_RANGES = (
    (0x4E00, 0x9FFF), (0x3400, 0x4DBF),
    (0x3040, 0x30FF), (0xAC00, 0xD7AF), (0xF900, 0xFAFF),
)


def _is_cjk(ch: str) -> bool:
    if not ch:
        return False
    o = ord(ch)
    return any(lo <= o <= hi for lo, hi in _CJK_RANGES)


def visible_prefix(text: str, blocks: Sequence[str]) -> List[int]:
    """返回每个位置之前的可见长度；占位符按原片段长度计。"""
    n = len(text)
    vis = [0] * (n + 1)
    i = 0
    total = 0
    while i < n:
        m = PH_RE.match(text, i)
        if m is not None:
            end = m.end()
            for k in range(i + 1, end):
                vis[k] = total
            idx = int(m.group(1))
            if 0 <= idx < len(blocks):
                total += len(blocks[idx])
            else:
                total += end - i
            vis[end] = total
            i = end
        else:
            total += 1
            vis[i + 1] = total
            i += 1
    return vis


def _spans(text: str) -> List[Tuple[int, int]]:
    return [(m.start(), m.end()) for m in PH_RE.finditer(text)]


def _inside_span(pos: int, spans: Sequence[Tuple[int, int]]) -> bool:
    return any(start < pos < end for start, end in spans)


def candidate_positions(text: str, blocks: Sequence[str],
                        max_chars: int) -> List[int]:
    """按 v3.0 第 6 章口径生成候选点（保护后坐标）。"""
    if max_chars <= 0:
        raise ValueError("max_chars 必须为正整数")
    n = len(text)
    if n == 0:
        return []
    cands: Set[int] = set()

    for sep in SEPS:
        p = text.find(sep)
        while p >= 0:
            cands.add(p + len(sep))
            p = text.find(sep, p + 1)

    for i in range(1, n):
        a, b = text[i - 1], text[i]
        if (_is_cjk(a) and b.isascii() and b.isalpha()) or (
                a.isascii() and a.isalpha() and _is_cjk(b)):
            cands.add(i)
        if a.isdigit() and b in _UNIT_CHARS:
            cands.add(i + 1)

    spans = _spans(text)
    for start, end in spans:
        cands.add(start)
        cands.add(end)

    vis = visible_prefix(text, blocks)
    total = vis[-1]
    for limit in range(max_chars, total, max_chars):
        k = 0
        # 长度安全点：第一个达到 limit 的位置。二分会让占位符内部位置
        # 也进入候选，这里直接线性找，文本通常只有几百字。
        while k < len(vis) and vis[k] < limit:
            k += 1
        if 0 < k < n:
            cands.add(k)

    cands = {p for p in cands
             if 0 < p < n and not _inside_span(p, spans)}
    return sorted(cands)


def sep_base_at(text: str, pos: int) -> int:
    """pos 前一个分隔符的基础分；没有则 0。"""
    for sep in sorted(SEPS, key=len, reverse=True):
        if text.endswith(sep, 0, pos):
            return SEP_BASE_SCORE[sep]
    return 0


def _priority(text: str, pos: int) -> int:
    base = sep_base_at(text, pos)
    if base >= 80:
        return 5
    if base >= 60:
        return 4
    if base >= 35:
        return 3
    if base >= 20:
        return 2
    return 1


def prune_candidates(text: str, blocks: Sequence[str],
                     cands: Sequence[int], total: int,
                     max_chars: int,
                     cap_per_100: int = CANDIDATE_CAP_PER_100) -> List[int]:
    """按密度上限裁剪，但保留覆盖骨架。

    只按优先级裁剪会删空可切点；骨架保证每个 ``max_chars`` 可见窗口至少
    有一个候选（方案 rev.2 §3.3）。
    """
    if max_chars <= 0:
        raise ValueError("max_chars 必须为正整数")
    if cap_per_100 <= 0:
        raise ValueError("cap_per_100 必须为正整数")
    if not cands or total <= 0:
        return []
    limit = max(3, int(math.ceil(cap_per_100 * total / 100.0)))
    if len(cands) <= limit:
        return sorted(cands)

    vis = visible_prefix(text, blocks)
    pri: Dict[int, int] = {p: _priority(text, p) for p in cands}
    keep: Set[int] = set()

    start_vis = 0
    while start_vis < total:
        end_vis = min(total, start_vis + max_chars)
        win = [p for p in cands if start_vis < vis[p] <= end_vis]
        if not win:
            start_vis = end_vis
            continue
        pick = max(win, key=lambda p: (pri[p], p))
        keep.add(pick)
        start_vis = vis[pick]

    for p in sorted(cands, key=lambda p: (-pri[p], p)):
        if len(keep) >= limit:
            break
        keep.add(p)

    return sorted(keep)

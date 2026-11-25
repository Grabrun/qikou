# -*- coding: utf-8 -*-
"""v3.0 的段级 DP 求解器。

公式（方案 rev.2 §7.1）::

    U(i, j) = q(j) + L(i, j) - λ
    dp[j]   = max_i (dp[i] + U(i, j))

``q(j)`` 是切点 j 的边界收益（归一化到 [-1, 1]），``L`` 是长度效用，
``λ`` 是每切一次的成本。终点必须满足 ``vis <= max_chars``；严格遍无解时
才允许结构内切点/超长终点，并返回 ``fallback=True``。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, Iterable, List, Sequence, Set, Tuple

from .candidates import sep_base_at
from .config import Config
from .lexicon import EN_ABBREV, ZH_HEAD_BAD, ZH_TAIL_BAD
from .patterns import is_list_start

if TYPE_CHECKING:                       # pragma: no cover - 仅供类型检查
    from .splitter import _State

__all__ = ["DP_CHUNK_CHARS", "DPResult", "dp_cut"]

DP_CHUNK_CHARS = 2000
LEN_BONUS = 0.20
SHORT_PENALTY = 0.30
UNSAFE_PENALTY = 1.00
_NEG = -1e18


@dataclass(frozen=True)
class DPResult:
    """一次 DP 的结果。``cuts`` 是不含 0、不含文本末尾的切点。"""

    cuts: Tuple[int, ...]
    score: float
    fallback: bool
    unsafe_cuts: int


def _is_abbrev(text: str, dot_pos: int) -> bool:
    i = dot_pos - 1
    while i >= 0 and (text[i].isalnum() or text[i] in ".'"):
        i -= 1
    prev = text[i + 1:dot_pos].lower()
    if prev in EN_ABBREV:
        return True
    head = text[max(0, dot_pos - 24):dot_pos + 1]
    return bool(re.search(r'\b[A-Z](?:\.[A-Z])+\.$', head))


def boundary_scores(text: str, cands: Sequence[int],
                    state: "_State") -> Dict[int, float]:
    """预计算每个候选点的位置内禀收益，避免在 DP 边内做字符串扫描。"""
    out: Dict[int, float] = {}
    for p in cands:
        s = sep_base_at(text, p)
        if state.md_span(p):
            s -= 100
        if state.unclosed_bracket(p):
            s -= 80
        if p > 0 and text[p - 1] == "." and _is_abbrev(text, p - 1):
            s -= 100
        for w in ZH_TAIL_BAD:
            if text.endswith(w, 0, p):
                s -= 50
                break
        for w in ZH_HEAD_BAD:
            if text.startswith(w, p):
                s -= 50
                break
        if is_list_start(text[p:p + 24]):
            s += 30
        out[p] = s / 100.0
    return out


def _solve(text: str, state: "_State", cfg: Config,
           cands: Sequence[int], cut_cost: float,
           allow_over: bool, allow_unsafe: bool) -> "Tuple[Tuple[int, ...], float] | None":
    n = len(text)
    nodes = [0] + list(cands) + [n]
    unsafe: Set[int] = {
        p for p in cands
        if state.md_span(p) or state.unclosed_bracket(p)
    }
    score_at = boundary_scores(text, cands, state)

    best: List[float] = [_NEG] * len(nodes)
    prev: List[int] = [-1] * len(nodes)
    best[0] = 0.0

    for j in range(1, len(nodes)):
        pj = nodes[j]
        final = j == len(nodes) - 1
        if not final and pj in unsafe and not allow_unsafe:
            continue
        i = j - 1
        while i >= 0:
            pi = nodes[i]
            vis = state.vis[pj] - state.vis[pi]
            if vis > cfg.max_chars and (not final or not allow_over):
                break
            if best[i] == _NEG:
                i -= 1
                continue
            if pi != 0 and vis < cfg.min_chars:
                i -= 1
                continue
            if pi != 0 and pi in unsafe and not allow_unsafe:
                i -= 1
                continue

            gain = 0.0 if final else score_at.get(pj, 0.0)
            if cfg.target_chars <= vis <= cfg.max_chars:
                gain += LEN_BONUS
            elif vis < cfg.min_chars:
                gain -= SHORT_PENALTY
            if not final and pj in unsafe:
                gain -= UNSAFE_PENALTY
            if final and vis > cfg.max_chars:
                gain -= 2.0 * (vis - cfg.max_chars) / cfg.max_chars

            cand_score = best[i] + gain - cut_cost
            if cand_score > best[j] or (
                    cand_score == best[j] and i < prev[j]):
                best[j] = cand_score
                prev[j] = i
            i -= 1

    if best[-1] == _NEG:
        return None

    cuts: List[int] = []
    k = len(nodes) - 1
    while k > 0:
        i = prev[k]
        if i < 0:
            return None
        if i > 0:
            cuts.append(nodes[i])
        k = i
    cuts.reverse()
    return tuple(cuts), best[-1]


def dp_cut(text: str, state: "_State", cfg: Config,
           cands: Iterable[int]) -> DPResult:
    """对一段文本求最优切分；严格遍无解时进入兜底遍。"""
    ordered = sorted({p for p in cands if 0 < p < len(text)})
    if not ordered:
        return DPResult((), 0.0, True, 0)

    strict = _solve(text, state, cfg, ordered, cfg.dp_cut_cost,
                    allow_over=False, allow_unsafe=False)
    if strict is not None:
        cuts, score = strict
        unsafe = sum(1 for p in cuts
                     if state.md_span(p) or state.unclosed_bracket(p))
        return DPResult(cuts, score, False, unsafe)

    relaxed = _solve(text, state, cfg, ordered, cfg.dp_cut_cost,
                     allow_over=True, allow_unsafe=True)
    if relaxed is None:                  # 理论上不会发生；保留明确结果
        return DPResult((), _NEG, True, 0)
    cuts, score = relaxed
    unsafe = sum(1 for p in cuts
                 if state.md_span(p) or state.unclosed_bracket(p))
    return DPResult(cuts, score, True, unsafe)

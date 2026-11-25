# -*- coding: utf-8 -*-
"""气口核心切分逻辑。

性能结构（2026-11 审计 QK-02 之后）：每段文本先建一份 :class:`_State`
前缀状态（可见长度、括号深度、各标记位置），此后每个候选切点的判定都是
常数级或对数级。旧实现每个候选都切一次 ``text[:pos]`` 再逐字符统计，
长文本因此平方增长（37k 字 20 s、118k 字 136 s）。
"""

from __future__ import annotations

import heapq
import re
from array import array
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from . import kaomoji
from .config import Config
from .lexicon import (
    EN_ABBREV, ZH_TAIL_BAD, ZH_HEAD_BAD,
    EN_TAIL_BAD, EN_HEAD_BAD,
    SEP_BASE_SCORE, SEPS, MIN_RIGHT_LEN, ASCII_PUNCT_END,
)
from .patterns import (
    CLOSE_CHARS, CLOSE_BRACKETS, OPEN_BRACKETS,
    LEADING_MOVE_CHARS, REAL_CHAR_RE, TILDE_CHARS,
    LIST_RE, TABLE_SEP_RE, TABLE_ROW_RE, HEADING_RE, HR_RE,
    HTML_BR_RE, PH_RE,
    is_list_start, is_heading, is_hr,
    is_table_msg,
)
from .protect import (
    protect_special, restore_special, visible_len,
)
from .postprocess import postprocess_message

__all__ = ["split"]


# 原子单元 —— (文本, 块号, 类型)；块号即空行分段编号。
Unit = Tuple[str, int, str]
Blocks = Sequence[str]


@dataclass
class _Msg:
    """打包后的一条消息：文本 + 段号（合并时只改这两个字段）。"""

    text: str
    bid: int


# ============================================================
# 前缀状态
# ============================================================

_TOKENS = ('**', '__', '~~', '`')
_QUOTE_PAIRS = (('“', '”'), ('「', '」'), ('『', '』'))
_SINGLE_CHARS = frozenset('“”「」『』"*_')


def _visible_prefix(text: str, blocks: Blocks) -> "Tuple[array[int], List[Tuple[int, int]]]":
    """返回 (每个位置的可见前缀长度, 占位符区间列表)。

    占位符内部的位置统一记为"占位符之前的长度"，切点若要落在里面，
    由 :meth:`_State.hard_index` 夹回占位符起点。
    """
    n = len(text)
    vis = array('i', [0]) * (n + 1)
    spans: List[Tuple[int, int]] = []
    i = 0
    total = 0
    while i < n:
        m = PH_RE.match(text, i)
        block = blocks[int(m.group(1))] if m else None
        if m is not None and block is not None:
            end = m.end()
            for k in range(i + 1, end):
                vis[k] = total
            total += len(block)
            vis[end] = total
            spans.append((i, end))
            i = end
        else:
            total += 1
            vis[i + 1] = total
            i += 1
    return vis, spans


class _State:
    """一段文本的前缀状态：所有"切点是否落在未闭合结构内"的判定都查表完成。"""

    __slots__ = (
        "text", "n", "vis", "span_starts", "spans", "depth",
        "quote_open", "quote_close", "quote_rfind",
        "dq_pos", "dq_rfind",
        "tok_ends", "tok_rfind",
        "star_pos", "star_rfind", "us_pos", "us_rfind",
        "last_close",
    )

    def __init__(self, text: str, blocks: Blocks) -> None:
        self.text = text
        self.n = len(text)
        self.vis, self.spans = _visible_prefix(text, blocks)
        self.span_starts = [s for s, _ in self.spans]

        # 括号深度：遇到左括号 +1，右括号在 depth>0 时 -1。
        depth = array('i', [0]) * (self.n + 1)
        d = 0
        for i, ch in enumerate(text):
            if ch in OPEN_BRACKETS:
                d += 1
            elif ch in CLOSE_BRACKETS and d > 0:
                d -= 1
            depth[i + 1] = d
        self.depth = depth
        last_close = -1
        for ch in CLOSE_BRACKETS:
            last_close = max(last_close, text.rfind(ch))
        self.last_close = last_close

        # 引号、星号、下划线的位置表：一次遍历收集。
        pos_of: Dict[str, List[int]] = {c: [] for c in _SINGLE_CHARS}
        for i, ch in enumerate(text):
            bucket = pos_of.get(ch)
            if bucket is not None:
                bucket.append(i)
        self.quote_open = [pos_of[op] for op, _ in _QUOTE_PAIRS]
        self.quote_close = [pos_of[cl] for _, cl in _QUOTE_PAIRS]
        self.quote_rfind = [text.rfind(cl) for _, cl in _QUOTE_PAIRS]
        self.dq_pos = pos_of['"']
        self.dq_rfind = text.rfind('"')
        self.star_pos = pos_of['*']
        self.star_rfind = text.rfind('*')
        self.us_pos = pos_of['_']
        self.us_rfind = text.rfind('_')

        # 各类标记的结束位置（贪婪、不重叠），用于前缀计数与奇偶判定。
        ends: Dict[str, List[int]] = {}
        rfind: Dict[str, int] = {}
        for tok in _TOKENS:
            cur: List[int] = []
            p = text.find(tok)
            while p >= 0:
                cur.append(p + len(tok))
                p = text.find(tok, p + len(tok))
            ends[tok] = cur
            rfind[tok] = text.rfind(tok)
        self.tok_ends = ends
        self.tok_rfind = rfind

    # ---- 查询 ----

    def md_span(self, pos: int) -> bool:
        """pos 是否落在某个未闭合的 Markdown 标记内（且后面还有配对机会）。"""
        for tok in _TOKENS:
            if (bisect_right(self.tok_ends[tok], pos) % 2
                    and self.tok_rfind[tok] >= pos):
                return True
        # 去掉成对标记后剩下单个 * / _ 时才计入（与 str.replace 的语义一致）
        stars = bisect_left(self.star_pos, pos) - 2 * bisect_right(
            self.tok_ends['**'], pos)
        if stars % 2 and self.star_rfind >= pos:
            return True
        unders = bisect_left(self.us_pos, pos) - 2 * bisect_right(
            self.tok_ends['__'], pos)
        if unders % 2 and self.us_rfind >= pos:
            return True
        return False

    def unclosed_bracket(self, pos: int) -> bool:
        """pos 是否落在未闭合的括号/引号内（且后面还有闭合机会）。"""
        if self.depth[pos] > 0 and self.last_close >= pos:
            return True
        for k, (op, _cl) in enumerate(_QUOTE_PAIRS):
            opens = bisect_left(self.quote_open[k], pos)
            closes = bisect_left(self.quote_close[k], pos)
            if opens > closes and self.quote_rfind[k] >= pos:
                return True
        # 半角双引号：与全角引号同等对待（2026-11 审计 QK-15）。
        # 半角单引号不参与配对：它同时是英文撇号，无法可靠区分。
        if bisect_left(self.dq_pos, pos) % 2 and self.dq_rfind >= pos:
            return True
        return False

    def hard_index(self, start: int, max_chars: int) -> int:
        """从 start 起，可见长度不超过 max_chars 的最远边界。"""
        limit = self.vis[start] + max_chars
        i = bisect_right(self.vis, limit) - 1
        if i > self.n:
            i = self.n
        if i < 0:
            return 0
        k = bisect_left(self.span_starts, i)
        if k > 0:
            span_start, span_end = self.spans[k - 1]
            if span_start < i < span_end:
                i = span_start
        return i


# ============================================================
# 词与字符判定
# ============================================================

def _prev_word_raw(text: str, dot_pos: int) -> str:
    i = dot_pos - 1
    while i >= 0 and (text[i].isalnum() or text[i] in ".'"):
        i -= 1
    return text[i + 1:dot_pos]


def _is_abbrev(text: str, dot_pos: int) -> bool:
    """dot_pos（'.' 的下标）是否属于英文缩写。"""
    prev = _prev_word_raw(text, dot_pos).lower()
    if prev in EN_ABBREV:
        return True
    head = text[max(0, dot_pos - 24):dot_pos + 1]
    return bool(re.search(r'\b[A-Z](?:\.[A-Z])+\.$', head))


def _is_single_upper_letter(text: str, dot_pos: int) -> bool:
    w = _prev_word_raw(text, dot_pos)
    return len(w) == 1 and w.isupper()


def _is_cjk(ch: str) -> bool:
    if not ch:
        return False
    o = ord(ch)
    return (0x4E00 <= o <= 0x9FFF or
            0x3400 <= o <= 0x4DBF or
            0x3040 <= o <= 0x30FF or
            0xAC00 <= o <= 0xD7AF or
            0xF900 <= o <= 0xFAFF)


# ============================================================
# 分句
# ============================================================

def merge_leading_punct(parts: List[str]) -> List[str]:
    if len(parts) < 2:
        return parts
    fixed = [parts[0]]
    for p in parts[1:]:
        if p and p[0] in LEADING_MOVE_CHARS:
            fixed[-1] = fixed[-1] + p[0]
            rest = p[1:].strip()
            if rest:
                fixed.append(rest)
        else:
            fixed.append(p)
    return fixed


def _split_by_br(line: str) -> List[str]:
    if not HTML_BR_RE.search(line):
        return [line]
    result = []
    last = 0
    for m in HTML_BR_RE.finditer(line):
        result.append(line[last:m.end()])
        last = m.end()
    if last < len(line):
        result.append(line[last:])
    return result


def _split_sentences_core(line: str, blocks: Blocks) -> List[str]:
    result = []
    buf: List[str] = []
    state = _State(line, blocks)
    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        buf.append(ch)
        i += 1

        is_end = ch in '\u3002\uff01\uff1f!?\u2026'
        if ch == '.':
            if _is_abbrev(line, i - 1):
                is_end = False
            elif (_is_single_upper_letter(line, i - 1)
                  and i < n and line[i].isspace()):
                is_end = False
            elif i >= n or line[i].isspace() or _is_cjk(line[i]):
                is_end = True
        if ch in TILDE_CHARS:
            prev_ch = line[i - 2] if i >= 2 else ''
            next_ch = line[i] if i < n else ''
            if prev_ch in TILDE_CHARS:
                is_end = False
            elif next_ch in TILDE_CHARS:
                is_end = False
            elif next_ch in '=<>!':
                is_end = False
            elif (next_ch and next_ch.isdigit()
                  and prev_ch and not prev_ch.isspace()
                  and not _is_cjk(prev_ch)):
                is_end = False
            elif (prev_ch and prev_ch.isascii() and prev_ch.isalnum()
                  and next_ch and next_ch.isascii() and next_ch.isalnum()):
                is_end = False
            elif not prev_ch or prev_ch.isspace():
                is_end = False
            else:
                is_end = True

        if is_end:
            if state.md_span(i) or state.unclosed_bracket(i):
                is_end = False
            else:
                while i < n and line[i] in CLOSE_CHARS:
                    buf.append(line[i])
                    i += 1
                j = i
                while j < n and line[j] in ' \t':
                    j += 1
                k = kaomoji.kaomoji_len(line, j)
                if k > 0:
                    buf.append(line[i:j + k])
                    i = j + k
                result.append(''.join(buf).strip())
                buf = []

    if buf:
        result.append(''.join(buf).strip())
    result = [s for s in result if s]
    return merge_leading_punct(result)


def split_sentences(line: str, blocks: Blocks) -> List[str]:
    parts: List[str] = []
    for seg in _split_by_br(line):
        parts.extend(_split_sentences_core(seg, blocks))
    return parts


def build_units(text: str, blocks: Blocks) -> List[Unit]:
    units = []
    blocks_split = re.split(r'\n\s*\n', text)
    bid = 0
    for block in blocks_split:
        block = block.strip()
        if not block:
            continue
        bid += 1
        lines = [raw.strip() for raw in block.split('\n') if raw.strip()]
        i = 0
        while i < len(lines):
            line = lines[i]
            if HEADING_RE.match(line):
                units.append((line, bid, 'heading'))
                i += 1
            elif HR_RE.match(line):
                units.append((line, bid, 'hr'))
                i += 1
            elif TABLE_ROW_RE.match(line):
                table_lines = [line]
                j = i + 1
                while j < len(lines) and TABLE_ROW_RE.match(lines[j]):
                    table_lines.append(lines[j])
                    j += 1
                units.append(('\n'.join(table_lines), bid, 'table'))
                i = j
            elif LIST_RE.match(line):
                units.append((line, bid, 'list'))
                i += 1
            else:
                for s in split_sentences(line, blocks):
                    units.append((s, bid, 'text'))
                i += 1
    return units


# ============================================================
# 拼接
# ============================================================

def join_text(a: str, b: str) -> str:
    if not a:
        return b
    if not b:
        return a
    if a[-1].isspace() or b[0].isspace():
        return a + b
    if re.match(r'[A-Za-z0-9]', a[-1]) and re.match(r'[A-Za-z0-9]', b[0]):
        return a + ' ' + b
    if a[-1] in ASCII_PUNCT_END and re.match(
            r'[A-Za-z0-9\u4e00-\u9fff]', b[0]):
        return a + ' ' + b
    if a[-1] in TILDE_CHARS and re.match(
            r'[A-Za-z0-9\u4e00-\u9fff]', b[0]):
        return a + ' ' + b
    return a + b


def smart_merge(a: str, b: str) -> str:
    if not a:
        return b
    if not b:
        return a
    if LIST_RE.match(b.lstrip()):
        return a.rstrip() + '\n' + b.lstrip()
    return join_text(a, b)


# ============================================================
# 打分切点
# ============================================================

_WINDOW = 48


def score_cut(state: _State, start: int, pos: int, base: int,
              cfg: Config) -> int:
    """给"在 pos 处切开"打分。left/right 都以 start 为界。"""
    text = state.text
    s = base

    p_end = pos
    while p_end > start and text[p_end - 1].isspace():
        p_end -= 1
    r_start = pos
    n = state.n
    while r_start < n and text[r_start].isspace():
        r_start += 1

    # 以点号结尾的英文缩写（与分句阶段共用同一个判定）
    if p_end > start and text[p_end - 1] == '.' and _is_abbrev(text, p_end - 1):
        s -= 100

    tail = text[max(start, p_end - _WINDOW):p_end]

    for w in ZH_TAIL_BAD:
        if text.endswith(w, start, p_end):
            s -= 50
            break
    for w in ZH_HEAD_BAD:
        if text.startswith(w, r_start):
            s -= 50
            break

    m = re.search(r'([A-Za-z]+)$', tail)
    if m and m.group(1).lower() in EN_TAIL_BAD:
        s -= 50
    m = re.match(r'([A-Za-z]+)', text[r_start:r_start + 32])
    if m and m.group(1).lower() in EN_HEAD_BAD:
        s -= 50

    if state.md_span(pos):
        s -= 100
    if state.unclosed_bracket(pos):
        s -= 80

    if is_list_start(text[pos:pos + 24]):
        s += 30

    base_vis = state.vis[start]
    vis = state.vis[pos] - base_vis
    if cfg.target_chars <= vis <= cfg.max_chars:
        span = cfg.max_chars - cfg.target_chars
        if span > 0:
            s += int(20 * min((vis - cfg.target_chars) / span, 1.0))

    right_len = (state.vis[n] - base_vis) - vis
    if right_len < MIN_RIGHT_LEN:
        s -= 30

    return s


def find_cut(state: _State, start: int, cfg: Config) -> int:
    """从 start 起找最合适的切点（返回绝对下标；无可切时返回文本末尾）。"""
    text = state.text
    n = state.n
    hard = state.hard_index(start, cfg.max_chars)
    if hard <= start:
        m = PH_RE.match(text, start)
        return m.end() if m else min(start + 1, n)

    candidates: Dict[int, int] = {}
    for sep in SEPS:
        base = SEP_BASE_SCORE[sep]
        p = text.find(sep, start, hard)
        while p >= 0:
            end = p + len(sep)
            if end not in candidates or candidates[end] < base:
                candidates[end] = base
            p = text.find(sep, p + 1, hard)

    if not candidates:
        if state.md_span(hard) or state.unclosed_bracket(hard):
            return n
        vis_before = state.vis[hard] - state.vis[start]
        total = state.vis[n] - state.vis[start]
        if total - vis_before < cfg.target_chars // 2:
            return n
        return hard

    best_pos = hard
    best_score = -1e9
    for pos, base in candidates.items():
        sc = score_cut(state, start, pos, base, cfg)
        if sc > best_score:
            best_score = sc
            best_pos = pos

    if best_score < 0:
        return n
    return best_pos


def split_long(text: str, cfg: Config, blocks: Blocks) -> List[str]:
    if visible_len(text, blocks) <= cfg.max_chars:
        return [text]

    # 列表项：标记（"- " / "1. "）不可与内容分离，先从标记后切开内容，
    # 再把标记粘回第一段（2026-11 审计 QK-05）。
    marker = LIST_RE.match(text)
    if marker is not None and marker.end() < len(text):
        head = text[:marker.end()]
        tail_parts = split_long(text[marker.end():], cfg, blocks)
        return [head + tail_parts[0]] + tail_parts[1:]

    state = _State(text, blocks)
    n = state.n
    parts: List[str] = []
    start = 0
    while start < n and text[start].isspace():
        start += 1
    # 迭代次数按可见长度估，旧实现的固定 200 会在超长文本上悄悄把整段
    # 尾巴并成一条（2026-11 审计 QK-09 的一半成因）。
    guard_limit = state.vis[n] // max(cfg.max_chars, 1) + 64
    guard = 0
    while state.vis[n] - state.vis[start] > cfg.max_chars:
        guard += 1
        if guard > guard_limit:
            break
        cut = find_cut(state, start, cfg)
        if cut <= start or cut >= n:
            break
        parts.append(text[start:cut].strip())
        start = cut
        while start < n and text[start].isspace():
            start += 1

    rest = text[start:].strip()
    if rest:
        parts.append(rest)
    return [p for p in parts if p]


# ============================================================
# 打包
# ============================================================

def is_fragment(text: str) -> bool:
    t = text.strip()
    if not t:
        return True
    if kaomoji.is_kaomoji(t):
        return False
    if TABLE_SEP_RE.match(t):
        return False
    if HR_RE.match(t):
        return False
    return not REAL_CHAR_RE.search(t)


def ends_with_tilde(text: str) -> bool:
    t = text.rstrip()
    return bool(t) and t[-1] in TILDE_CHARS


def pack_units(units: List[Unit], cfg: Config,
               blocks: Blocks) -> List[_Msg]:
    msgs: List[_Msg] = []
    for text, bid, kind in units:
        if kind in ('table', 'heading', 'hr'):
            msgs.append(_Msg(text, bid))
            continue

        for part in split_long(text, cfg, blocks):
            if msgs:
                prev = msgs[-1]
                plen = visible_len(prev.text, blocks)
                clen = visible_len(part, blocks)

                if is_fragment(part):
                    prev.text = join_text(prev.text, part)
                    continue

                if kind == 'list':
                    msgs.append(_Msg(part, bid))
                    continue

                if is_heading(prev.text) or is_hr(prev.text):
                    msgs.append(_Msg(part, bid))
                    continue

                if PH_RE.fullmatch(part):
                    if (clen > cfg.max_chars
                            and plen <= cfg.atomic_merge_prefix
                            and prev.bid == bid):
                        prev.text = join_text(prev.text, part)
                        continue
                    msgs.append(_Msg(part, bid))
                    continue

                if prev.bid == bid and ends_with_tilde(prev.text):
                    msgs.append(_Msg(part, bid))
                    continue

                if (prev.bid == bid
                        and plen < cfg.min_chars
                        and plen + clen <= cfg.max_chars):
                    prev.text = join_text(prev.text, part)
                    continue
            msgs.append(_Msg(part, bid))
    return msgs


def _merge_blocked(text: str) -> bool:
    """这条消息是否**不参与合并**（结构类条目要保住自己的形状）。"""
    return (is_list_start(text) or is_heading(text) or is_hr(text)
            or is_table_msg(text) or bool(PH_RE.fullmatch(text.strip())))


class _Node:
    """合并用的双向链表节点。

    旧实现每轮遍历全部相邻对选最小、合并后重建标记，长文本因此 m^2；
    这里用优先队列 + 惰性失效，每合并一次只重算左右两个邻居。
    """

    __slots__ = ("text", "bid", "prev", "next", "seq",
                 "blocked", "length", "tilde")

    def __init__(self, text: str, bid: int, seq: int, blocks: Blocks) -> None:
        self.text = text
        self.bid = bid
        self.seq = seq
        self.prev: "Optional[_Node]" = None
        self.next: "Optional[_Node]" = None
        self.refresh(blocks)

    def refresh(self, blocks: Blocks) -> None:
        self.blocked = _merge_blocked(self.text)
        self.length = visible_len(self.text, blocks)
        self.tilde = ends_with_tilde(self.text)


def _pack_sequence(msgs: List[_Msg], limit: int,
                   blocks: Blocks) -> List[_Msg]:
    """按原顺序从左到右装箱：能并就并，直到每条接近 ``limit``。

    只在"段内合并怎么也压不到 max_messages"时才走这条路——此时跨段落合并
    本来就是必须的，逐条贪心（先挑最小的合并）反而会把段落两两翻倍、
    最后剩一堆中等大小的消息合不动。
    """
    nodes = [_Node(m.text, m.bid, i, blocks) for i, m in enumerate(msgs)]
    out: List[_Node] = []
    for nd in nodes:
        if out:
            prev = out[-1]
            if not prev.blocked and not nd.blocked and not prev.tilde:
                cross = prev.bid != nd.bid
                total = prev.length + nd.length + (2 if cross else 0)
                if total <= limit:
                    if cross:
                        prev.text = (prev.text.rstrip()
                                     + '\n\n' + nd.text.lstrip())
                    else:
                        prev.text = smart_merge(prev.text, nd.text)
                    prev.refresh(blocks)
                    continue
        out.append(nd)
    return [_Msg(n.text, n.bid) for n in out]


def enforce_max_messages(msgs: List[_Msg], cfg: Config,
                         blocks: Blocks) -> List[_Msg]:
    """尽力把条数压到 max_messages 以内。

    第一段只在同一段落内合并（与历史行为一致，输出逐字节不变）；段内怎么
    合都到不了上限时，才允许跨段落合并（用空行连接）。旧实现只合并同一
    段号，于是每个段落至少一条，多段落文本的条数上限必然失效（QK-04）。

    条数存在物理下限：``merge_max_chars``（且不超过 ``max_chars``）是合并后
    单条上限，所以上限低于 ``ceil(可见字数 / 上限)`` 时不可能达到；结构类
    条目（列表、标题、表格、代码块）也不参与合并。
    """
    if cfg.max_messages <= 0 or not msgs:
        return msgs
    merge_limit = min(cfg.merge_max_chars, cfg.max_chars)

    nodes = [_Node(m.text, m.bid, i, blocks) for i, m in enumerate(msgs)]
    for a, b in zip(nodes, nodes[1:]):
        a.next = b
        b.prev = a

    def pair_key(a: _Node, b: _Node) -> Tuple[int, int, int]:
        # 同段落优先（0），其次合并后长度，再其次左节点原始顺序——与旧实现
        # "先同段、取最小总长、并列取最早" 的选择顺序一致。
        same = 0 if a.bid == b.bid else 1
        total = a.length + b.length + (0 if same == 0 else 2)
        return (same, total, a.seq)

    heap: List[Tuple[Tuple[int, int, int], _Node, _Node]] = []
    for a, b in zip(nodes, nodes[1:]):
        heapq.heappush(heap, (pair_key(a, b), a, b))

    count = len(nodes)
    while count > cfg.max_messages and heap:
        key, a, b = heapq.heappop(heap)
        if a.bid != b.bid:
            continue                    # 跨段落留到第二阶段
        if b.prev is not a or a.blocked or b.blocked or a.tilde:
            continue
        total = a.length + b.length
        if total > merge_limit:
            continue
        if key[1] != total:
            # 邻居合并后长度变大了：这条记录已过期，按真实长度重新入队，
            # 保证每轮总是挑当前最小的同段相邻对（与旧实现顺序一致）。
            heapq.heappush(heap, (pair_key(a, b), a, b))
            continue

        a.text = smart_merge(a.text, b.text)
        a.next = b.next
        if b.next is not None:
            b.next.prev = a
        b.prev = None
        b.next = None
        a.refresh(blocks)
        count -= 1

        if a.prev is not None:
            heapq.heappush(heap, (pair_key(a.prev, a), a.prev, a))
        if a.next is not None:
            heapq.heappush(heap, (pair_key(a, a.next), a, a.next))

    if count > cfg.max_messages:
        return _pack_sequence(msgs, merge_limit, blocks)

    out: List[_Msg] = []
    node: "Optional[_Node]" = nodes[0]
    while node is not None:
        out.append(_Msg(node.text, node.bid))
        node = node.next
    return out


# ============================================================
# 主入口
# ============================================================

def split(text: str, config: Optional[Config] = None,
          on_overflow: Optional[Callable[[str, int], None]] = None) -> List[str]:
    """把一段文本切成若干条短消息。

    Args:
        text: 待切分的文本。
        config: 可选配置，不会被修改。显式设定 ``max_chars`` 时不再按
            文本总长自动放大（见 ``Config.scaled_for_length``）。
        on_overflow: 可选回调。某条消息无法再切而超过 ``max_chars`` 时，
            以 ``(消息文本, max_chars)`` 调用一次。默认不通知，与原行为一致。

    Returns:
        消息列表；输入为空或纯空白时返回空列表。

    空白约定：输入首尾空白会被去掉；消息**边界**处的空白（含制表符）
    不保留；消息内部的空白原样保留。

    ::

        for message in split(reply):
            send(message)
    """
    kaomoji.ensure_loaded()
    cfg = Config() if config is None else config

    text = text.strip()
    if not text:
        return []

    protected, special_blocks = protect_special(text)
    total = visible_len(protected, special_blocks)
    cfg = cfg.scaled_for_length(total)

    units = build_units(protected, special_blocks)
    msgs = pack_units(units, cfg, special_blocks)
    msgs = enforce_max_messages(msgs, cfg, special_blocks)

    out = [postprocess_message(restore_special(m.text, special_blocks))
           for m in msgs]

    if on_overflow is not None:
        for m in out:
            if len(m) > cfg.max_chars:
                on_overflow(m, cfg.max_chars)
    return out

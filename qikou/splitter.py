# -*- coding: utf-8 -*-
"""气口 v2.0 核心切分逻辑。"""

import copy
import re

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
    is_before_list_item, is_list_start, is_heading, is_hr,
    is_table_msg,
)
from .protect import (
    protect_special, restore_special, visible_len, index_at_len,
)
from .postprocess import postprocess_message


# ============================================================
# 成对符号状态
#
# 判断 pos 是否落在"未闭合的标记内"时，除了看 pos 之前是否欠一个闭合，
# 还要求 pos 之后确实还有机会闭合。否则一个漏打的左括号或一个孤立的
# 星号会否决其后的每一个候选切点，把整段回复挤成一条——这与产品目标
# 正好相反（见 tests/test.txt 用例 121、122）。真实的括注与强调总是
# 配得上对的，配不上的就是笔误。
# ============================================================

def _has_partner(text, pos, token):
    """pos 之后是否还会出现 token，即当前未闭合的标记还有没有机会配对。"""
    return text.find(token, pos) >= 0


def _has_any(text, pos, chars):
    """pos 之后是否出现 chars 中的任一字符。"""
    tail = text[pos:]
    return any(c in tail for c in chars)


def in_md_span(text, pos):
    before = text[:pos]
    for token in ('**', '__', '~~', '`'):
        if before.count(token) % 2 == 1 and _has_partner(text, pos, token):
            return True
    stripped = before.replace('**', '').replace('__', '').replace('~~', '')
    if stripped.count('*') % 2 == 1 and _has_partner(text, pos, '*'):
        return True
    if stripped.count('_') % 2 == 1 and _has_partner(text, pos, '_'):
        return True
    return False


def in_unclosed_bracket(text, pos):
    before = text[:pos]
    depth = 0
    for c in before:
        if c in OPEN_BRACKETS:
            depth += 1
        elif c in CLOSE_BRACKETS:
            if depth > 0:
                depth -= 1
    if depth > 0 and _has_any(text, pos, CLOSE_BRACKETS):
        return True
    for op, cl in (('“', '”'), ('「', '」'), ('『', '』')):
        if before.count(op) > before.count(cl) and cl in text[pos:]:
            return True
    return False


# ============================================================
# 词与字符判定
# ============================================================

def _prev_word(text, dot_pos):
    i = dot_pos - 1
    while i >= 0 and (text[i].isalnum() or text[i] in ".\'"):
        i -= 1
    return text[i + 1:dot_pos].lower()


def _prev_word_raw(text, dot_pos):
    i = dot_pos - 1
    while i >= 0 and (text[i].isalnum() or text[i] in ".\'"):
        i -= 1
    return text[i + 1:dot_pos]


def _is_abbrev(text, dot_pos):
    prev = _prev_word(text, dot_pos)
    if prev in EN_ABBREV:
        return True
    m = re.search(r'\b[A-Z](?:\.[A-Z])+\.$', text[:dot_pos + 1])
    if m:
        return True
    return False


def _is_single_upper_letter(text, dot_pos):
    w = _prev_word_raw(text, dot_pos)
    return len(w) == 1 and w.isupper()


def _is_cjk(ch):
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

def merge_leading_punct(parts):
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


def _split_by_br(line):
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


def _split_sentences_core(line):
    result = []
    buf = []
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
            if in_md_span(line, i) or in_unclosed_bracket(line, i):
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


def split_sentences(line):
    parts = []
    for seg in _split_by_br(line):
        parts.extend(_split_sentences_core(seg))
    return parts


def build_units(text):
    units = []
    blocks = re.split(r'\n\s*\n', text)
    bid = 0
    for block in blocks:
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
                table_text = '\n'.join(table_lines)
                units.append((table_text, bid, 'table'))
                i = j
            elif LIST_RE.match(line):
                units.append((line, bid, 'list'))
                i += 1
            else:
                for s in split_sentences(line):
                    units.append((s, bid, 'text'))
                i += 1
    return units


# ============================================================
# 拼接
# ============================================================

def join_text(a, b):
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


def smart_merge(a, b):
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

def score_cut(text, pos, base, cfg, blocks):
    s = base
    left = text[:pos].rstrip()
    right = text[pos:].lstrip()

    m = re.search(r'([A-Za-z][A-Za-z.]*)\.\s*$', text[:pos])
    if m and m.group(1).lower() in EN_ABBREV:
        s -= 100

    for w in ZH_TAIL_BAD:
        if left.endswith(w):
            s -= 50
            break

    for w in ZH_HEAD_BAD:
        if right.startswith(w):
            s -= 50
            break

    m = re.search(r'([A-Za-z]+)\s*$', left)
    if m and m.group(1).lower() in EN_TAIL_BAD:
        s -= 50

    m = re.match(r'\s*([A-Za-z]+)', right)
    if m and m.group(1).lower() in EN_HEAD_BAD:
        s -= 50

    if in_md_span(text, pos):
        s -= 100
    if in_unclosed_bracket(text, pos):
        s -= 80

    if is_before_list_item(right):
        s += 30

    vis = visible_len(text[:pos], blocks)
    if cfg.target_chars <= vis <= cfg.max_chars:
        span = cfg.max_chars - cfg.target_chars
        if span > 0:
            s += int(20 * min((vis - cfg.target_chars) / span, 1.0))

    vis_total = visible_len(text, blocks)
    right_len = vis_total - vis
    if right_len < MIN_RIGHT_LEN:
        s -= 30

    return s


def find_cut(text, cfg, blocks):
    hard = index_at_len(text, cfg.max_chars, blocks)
    if hard <= 0:
        m = PH_RE.match(text, 0)
        return m.end() if m else 1

    candidates = {}
    for sep in SEPS:
        base = SEP_BASE_SCORE[sep]
        idx = 0
        while True:
            p = text.find(sep, idx, hard)
            if p < 0:
                break
            end = p + len(sep)
            if end not in candidates or candidates[end] < base:
                candidates[end] = base
            idx = p + 1

    if not candidates:
        if in_md_span(text, hard) or in_unclosed_bracket(text, hard):
            return len(text)
        vis_before = visible_len(text[:hard], blocks)
        vis_total = visible_len(text, blocks)
        if vis_total - vis_before < cfg.target_chars // 2:
            return len(text)
        return hard

    best_pos = hard
    best_score = -1e9
    for pos, base in candidates.items():
        sc = score_cut(text, pos, base, cfg, blocks)
        if sc > best_score:
            best_score = sc
            best_pos = pos

    if best_score < 0:
        return len(text)

    return best_pos


def split_long(text, cfg, blocks):
    if visible_len(text, blocks) <= cfg.max_chars:
        return [text]

    parts = []
    rest = text
    guard = 0
    while visible_len(rest, blocks) > cfg.max_chars and guard < 200:
        guard += 1
        cut = find_cut(rest, cfg, blocks)
        if cut <= 0 or cut >= len(rest):
            parts.append(rest.strip())
            rest = ''
            break
        parts.append(rest[:cut].strip())
        rest = rest[cut:].strip()

    if rest:
        parts.append(rest)

    return [p for p in parts if p]


# ============================================================
# 打包
# ============================================================

def is_fragment(text):
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


def ends_with_tilde(text):
    t = text.rstrip()
    return bool(t) and t[-1] in TILDE_CHARS


def pack_units(units, cfg, blocks):
    msgs = []
    for text, bid, kind in units:
        if kind in ('table', 'heading', 'hr'):
            msgs.append([text, bid])
            continue

        for part in split_long(text, cfg, blocks):
            if msgs:
                prev_text, prev_bid = msgs[-1]
                plen = visible_len(prev_text, blocks)
                clen = visible_len(part, blocks)

                if is_fragment(part):
                    msgs[-1][0] = join_text(prev_text, part)
                    continue

                if kind == 'list':
                    msgs.append([part, bid])
                    continue

                if is_heading(prev_text) or is_hr(prev_text):
                    msgs.append([part, bid])
                    continue

                if PH_RE.fullmatch(part):
                    if (clen > cfg.max_chars
                            and plen <= cfg.atomic_merge_prefix
                            and prev_bid == bid):
                        msgs[-1][0] = join_text(prev_text, part)
                        continue
                    msgs.append([part, bid])
                    continue

                if prev_bid == bid and ends_with_tilde(prev_text):
                    msgs.append([part, bid])
                    continue

                if (prev_bid == bid
                        and plen < cfg.min_chars
                        and plen + clen <= cfg.max_chars):
                    msgs[-1][0] = join_text(prev_text, part)
                    continue
            msgs.append([part, bid])
    return msgs


def enforce_max_messages(msgs, cfg, blocks):
    if cfg.max_messages <= 0:
        return msgs
    merge_limit = cfg.merge_max_chars
    guard = 0
    while len(msgs) > cfg.max_messages and guard < 500:
        guard += 1
        best_i = -1
        best_len = None
        for i in range(len(msgs) - 1):
            a_text, a_bid = msgs[i]
            b_text, b_bid = msgs[i + 1]

            if a_bid != b_bid:
                continue
            if is_list_start(a_text) or is_list_start(b_text):
                continue
            if is_heading(a_text) or is_heading(b_text):
                continue
            if is_hr(a_text) or is_hr(b_text):
                continue
            if is_table_msg(a_text) or is_table_msg(b_text):
                continue
            if PH_RE.fullmatch(a_text.strip()) or \
               PH_RE.fullmatch(b_text.strip()):
                continue
            if ends_with_tilde(a_text):
                continue

            a = visible_len(a_text, blocks)
            b = visible_len(b_text, blocks)
            if a + b > merge_limit:
                continue
            if best_len is None or a + b < best_len:
                best_len = a + b
                best_i = i
        if best_i < 0:
            break
        msgs[best_i][0] = smart_merge(msgs[best_i][0], msgs[best_i + 1][0])
        del msgs[best_i + 1]
    return msgs


# ============================================================
# 主入口
# ============================================================

def split_reply(text, cfg=None):
    # 不原地改写调用方传入的 Config：长度自适应会放大 max_chars /
    # target_chars / max_messages，若直接改这个对象，同一个 Config 复用
    # 多次时会单调放宽，且与"无副作用"的约定冲突。
    cfg = Config() if cfg is None else copy.copy(cfg)

    text = text.strip()
    if not text:
        return [], cfg

    protected, special_blocks = protect_special(text)
    total = visible_len(protected, special_blocks)
    cfg.scale_for_length(total)

    units = build_units(protected)
    msgs = pack_units(units, cfg, special_blocks)
    msgs = enforce_max_messages(msgs, cfg, special_blocks)

    out = [restore_special(m[0], special_blocks) for m in msgs]
    out = [postprocess_message(m) for m in out]
    return out, cfg

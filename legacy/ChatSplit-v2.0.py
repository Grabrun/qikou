#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agent 回复 → 社交媒体聊天气泡 切分器
"""

import os
import re
import sys
import time
import random


# ============================================================
# 颜文字表：Trie + Set
# ============================================================

_HERE = os.path.dirname(os.path.abspath(__file__))
KAOMOJI_FILE = os.path.join(_HERE, 'Kaomoji', 'kaomojis.txt')
TEST_FILE = os.path.join(_HERE, 'test.txt')

_TRIE = {}
_END = '\x00'
_KAOMOJI_COUNT = 0
KAOMOJI_SET = set()


def load_kaomojis(path=KAOMOJI_FILE):
    global _TRIE, _KAOMOJI_COUNT, KAOMOJI_SET
    _TRIE = {}
    _KAOMOJI_COUNT = 0
    KAOMOJI_SET = set()
    if not os.path.isfile(path):
        print("[警告] 未找到颜文字文件：%s" % path)
        return 0
    t0 = time.time()
    with open(path, 'r', encoding='utf-8-sig') as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith('#'):
                continue
            KAOMOJI_SET.add(s)
            node = _TRIE
            for c in s:
                nxt = node.get(c)
                if nxt is None:
                    nxt = {}
                    node[c] = nxt
                node = nxt
            if _END not in node:
                _KAOMOJI_COUNT += 1
            node[_END] = True
    print("[信息] 已加载 %d 个颜文字（Trie），耗时 %.0f ms"
          % (_KAOMOJI_COUNT, (time.time() - t0) * 1000.0))
    return _KAOMOJI_COUNT


def _kaomoji_len(s, i):
    if i >= len(s):
        return 0
    node = _TRIE
    j = i
    n = len(s)
    best = 0
    while j < n:
        nxt = node.get(s[j])
        if nxt is None:
            break
        node = nxt
        j += 1
        if _END in node:
            best = j - i
    return best


# ============================================================
# 词表
# ============================================================

EN_ABBREV = {
    'mr', 'mrs', 'ms', 'dr', 'prof', 'st', 'ave', 'blvd',
    'jr', 'sr', 'vs', 'etc', 'eg', 'ie', 'am', 'pm',
    'us', 'uk', 'no', 'vol', 'pp', 'fig', 'al', 'inc', 'ltd',
    'jan', 'feb', 'mar', 'apr', 'jun', 'jul', 'aug', 'sep',
    'oct', 'nov', 'dec', 'mon', 'tue', 'wed', 'thu', 'fri',
    'sat', 'sun', 'dept', 'univ', 'approx', 'est',
    'e.g', 'i.e', 'u.s', 'u.k', 'a.m', 'p.m', 'u.n', 'e.u',
    'ph.d', 'b.a', 'm.a', 'b.s', 'm.s',
}

ZH_TAIL_BAD = (
    '虽然', '尽管', '即使', '哪怕',
    '因为', '由于',
    '如果', '假如', '要是', '万一',
    '不但', '不仅', '不光',
    '与其', '宁可', '宁愿',
    '之所以', '既然',
)

ZH_HEAD_BAD = (
    '但是', '但', '不过', '然而', '可是', '只是', '偏偏',
    '所以', '因此', '因而', '从而', '于是',
    '而且', '并且', '况且', '何况', '甚至', '更有甚者',
    '然后', '接着', '随后', '之后', '最后', '紧接着',
    '或者', '还是', '要么',
    '的话', '的时候', '以后', '之前', '以来',
    '也就是说', '换言之', '换句话说',
    '总的来说', '总之',
)

EN_TAIL_BAD = {
    'because', 'although', 'though', 'if', 'when', 'while',
    'since', 'as', 'than', 'however', 'therefore', 'yet', 'nor',
}
EN_HEAD_BAD = {
    'however', 'therefore', 'thus', 'meanwhile', 'moreover',
    'furthermore', 'nonetheless', 'nevertheless',
}


# ============================================================
# 标点基础分
# ============================================================

SEP_BASE_SCORE = {
    '\n\n': 100,
    '\n': 80,
    '。': 60, '！': 60, '？': 60, '!': 60, '?': 60, '…': 60,
    '；': 40, ';': 40,
    '：': 35, ':': 35,
    '，': 20, ',': 20, '、': 20,
    ' ': 10,
}

SEPS = list(SEP_BASE_SCORE.keys())
MIN_RIGHT_LEN = 30


# ============================================================
# 成对符号
# ============================================================

OPEN_BRACKETS = '([{（【「『'
CLOSE_BRACKETS = ')]}）】」』'


def in_md_span(text, pos):
    before = text[:pos]
    if before.count('**') % 2 == 1:
        return True
    if before.count('__') % 2 == 1:
        return True
    if before.count('~~') % 2 == 1:
        return True
    if before.count('`') % 2 == 1:
        return True
    stripped = before.replace('**', '').replace('__', '').replace('~~', '')
    if stripped.count('*') % 2 == 1:
        return True
    if stripped.count('_') % 2 == 1:
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
    if depth > 0:
        return True
    if before.count('“') > before.count('”'):
        return True
    if before.count('「') > before.count('」'):
        return True
    if before.count('『') > before.count('』'):
        return True
    return False


LIST_RE = re.compile(r'^\s*(?:[-*+•]|\d+[.、)])\s+')
TABLE_SEP_RE = re.compile(r'^\s*\|[\s\-:|]+\|\s*$')
TABLE_ROW_RE = re.compile(r'^\s*\|.*\|\s*$')
HEADING_RE = re.compile(r'^\s*#{1,6}\s+')
HR_RE = re.compile(r'^\s*(?:-{3,}|\*{3,}|_{3,})\s*$')
HTML_BR_RE = re.compile(r'<br\s*/?>', re.IGNORECASE)


def is_before_list_item(right):
    return bool(LIST_RE.match(right))


def is_list_start(text):
    return bool(LIST_RE.match(text.lstrip()))


def is_heading(text):
    return bool(HEADING_RE.match(text.lstrip()))


def is_hr(text):
    return bool(HR_RE.match(text))


def is_table_msg(msg):
    lines = [l for l in msg.split('\n') if l.strip()]
    if len(lines) < 2:
        return False
    return all(l.lstrip().startswith('|') for l in lines)


# ============================================================
# 配置
# ============================================================

class Config:
    def __init__(self):
        self.max_chars = 60
        self.target_chars = 20
        self.min_chars = 4
        self.max_messages = 6
        self.atomic_merge_prefix = 20
        self.merge_max_chars = 60

        self.base_ms = 500
        self.per_char_ms = 30
        self.jitter_ms = 200
        self.min_ms = 300
        self.max_ms = 1800

    def scale_for_length(self, total):
        if total <= 150:
            pass
        elif total <= 400:
            self.max_chars = max(self.max_chars, 90)
            self.target_chars = max(self.target_chars, 30)
        elif total <= 800:
            self.max_chars = max(self.max_chars, 120)
            self.target_chars = max(self.target_chars, 45)
            self.max_messages = max(self.max_messages, 8)
        else:
            self.max_chars = max(self.max_chars, 160)
            self.target_chars = max(self.target_chars, 60)
            self.max_messages = max(self.max_messages, 10)

    def delay_for(self, msg):
        d = self.base_ms + len(msg) * self.per_char_ms \
            + random.randint(0, self.jitter_ms)
        d = max(self.min_ms, min(d, self.max_ms))
        return d / 1000.0


# ============================================================
# 特殊片段保护
# ============================================================

CODE_RE = re.compile(r'```[\s\S]*?```|~~~[\s\S]*?~~~')
URL_RE = re.compile(
    r'https?://[^\s\u4e00-\u9fff\u3000-\u303f\uff01-\uff5e]+'
)
PH_RE = re.compile(r'\x00(\d+)\x00')


def protect_special(text):
    blocks = []

    def repl(m):
        blocks.append(m.group(0))
        return '\x00%d\x00' % (len(blocks) - 1)

    text = CODE_RE.sub(repl, text)
    text = URL_RE.sub(repl, text)
    return text, blocks


def restore_special(text, blocks):
    if not blocks:
        return text
    return PH_RE.sub(lambda m: blocks[int(m.group(1))], text)


def visible_len(text, blocks):
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


def index_at_len(text, limit, blocks):
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


# ============================================================
# 分句
# ============================================================

CLOSE_CHARS = ")]）】」』\"'`”’"
REAL_CHAR_RE = re.compile(r'[^\W_]')
TILDE_CHARS = '~～〜˜˷∼∽⁓'
LEADING_MOVE_CHARS = '，。！？；：、）】」』”’'


def _prev_word(text, dot_pos):
    i = dot_pos - 1
    while i >= 0 and (text[i].isalnum() or text[i] in '.\''):
        i -= 1
    return text[i + 1:dot_pos].lower()


def _prev_word_raw(text, dot_pos):
    i = dot_pos - 1
    while i >= 0 and (text[i].isalnum() or text[i] in '.\''):
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

        is_end = ch in '。！？!?…'
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
                k = _kaomoji_len(line, j)
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

ASCII_PUNCT_END = set('.!?,;:')


def join_text(a, b):
    if not a:
        return b
    if not b:
        return a
    if a[-1].isspace() or b[0].isspace():
        return a + b
    if re.match(r'[A-Za-z0-9]', a[-1]) and re.match(r'[A-Za-z0-9]', b[0]):
        return a + ' ' + b
    if a[-1] in ASCII_PUNCT_END and re.match(r'[A-Za-z0-9\u4e00-\u9fff]', b[0]):
        return a + ' ' + b
    if a[-1] in TILDE_CHARS and re.match(r'[A-Za-z0-9\u4e00-\u9fff]', b[0]):
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
# 后处理
# ============================================================

def fix_unbalanced_md(msg):
    if not msg:
        return msg
    # 水平线独立处理，不补 ** / __
    if HR_RE.match(msg.strip()):
        return msg
    for marker in ('**', '__'):
        if msg.count(marker) % 2 == 1:
            msg = msg.rstrip() + marker
    return msg


def fix_unbalanced_quote(msg):
    if not msg:
        return msg
    pairs = [('“', '”'), ('「', '」'), ('『', '』')]
    for op, cl in pairs:
        if msg.count(op) > msg.count(cl):
            msg = msg.rstrip() + cl
    return msg


def postprocess_message(msg):
    msg = fix_unbalanced_md(msg)
    msg = fix_unbalanced_quote(msg)
    return msg


# ============================================================
# 打包
# ============================================================

def is_fragment(text):
    t = text.strip()
    if not t:
        return True
    if t in KAOMOJI_SET:
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
            if PH_RE.fullmatch(a_text.strip()) or PH_RE.fullmatch(b_text.strip()):
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
    if cfg is None:
        cfg = Config()

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


# ============================================================
# 输出 / 终端 / 测试
# ============================================================

BANNER = "=" * 52


def print_detailed(msgs, cfg):
    print()
    print(BANNER)
    print(" 切分结果：%d 条" % len(msgs))
    print(" 参数：max=%d  target=%d  min=%d  max_messages=%d"
          % (cfg.max_chars, cfg.target_chars,
             cfg.min_chars, cfg.max_messages))
    print(BANNER)
    for i, m in enumerate(msgs, 1):
        print()
        print("─── [%d/%d]  %d 字 ───" % (i, len(msgs), len(m)))
        print(m)
    print()
    print("-" * 52)
    print("模拟发送时间轴：")
    t = 0.0
    for i, m in enumerate(msgs, 1):
        d = cfg.delay_for(m)
        print("  t=%5.2fs  第 %d 条（%d 字，等待 %.2fs）"
              % (t, i, len(m), d))
        t += d
    print("  t=%5.2fs  发送完毕" % t)


def write_case_report(f, idx, total, name, text, msgs):
    f.write("\n")
    f.write("-" * 52 + "\n")
    f.write("用例 %d/%d：%s\n" % (idx, total, name))
    f.write("-" * 52 + "\n")
    f.write("输入：\n")
    for line in text.split('\n'):
        f.write("  | " + line + "\n")
    f.write("\n")
    f.write("结果（%d 条）：\n" % len(msgs))
    for i, m in enumerate(msgs, 1):
        preview = m.replace('\n', ' ⏎ ')
        f.write("  [%d] %s\n" % (i, preview))


CASE_MARK = re.compile(r'^\s*\[CASE\]\s*(.*?)\s*$', re.MULTILINE)


def load_test_cases(path):
    with open(path, 'r', encoding='utf-8-sig') as f:
        content = f.read()
    if '[CASE]' not in content:
        text = content.strip()
        return [("整个文件", text)] if text else []
    parts = CASE_MARK.split(content)
    cases = []
    for i in range(1, len(parts), 2):
        name = parts[i].strip() or ("用例 %d" % ((i + 1) // 2))
        raw = parts[i + 1] if i + 1 < len(parts) else ''
        if raw.strip():
            body = raw.strip()
        else:
            body = raw.strip('\n')
        cases.append((name, body))
    return cases


def run_auto_test(path, out_path=None):
    if not os.path.isfile(path):
        print("[错误] 找不到测试文件：%s" % path)
        return None, 0.0
    cases = load_test_cases(path)
    if not cases:
        print("[信息] 测试文件里没有用例。")
        return None, 0.0
    if out_path is None:
        ts = time.strftime("%Y%m%d_%H%M%S")
        out_path = os.path.join(_HERE, "test_result_%s.txt" % ts)
    start_time = time.time()
    total_msgs = 0
    max_name_len = max((len(name) for name, _ in cases), default=0)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(BANNER + "\n")
        f.write(" Agent 回复 → 社交媒体聊天气泡 切分器\n")
        f.write(" 自动测试报告\n")
        f.write(BANNER + "\n")
        f.write(" 测试文件：%s\n" % os.path.abspath(path))
        f.write(" 运行时间：%s\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
        f.write(" 颜文字表：%d 条\n" % _KAOMOJI_COUNT)
        f.write(" 用例数  ：%d\n" % len(cases))
        f.write(BANNER + "\n")
        for idx, (name, text) in enumerate(cases, 1):
            msgs, cfg = split_reply(text)
            total_msgs += len(msgs)
            write_case_report(f, idx, len(cases), name, text, msgs)
            print("  [%2d/%2d] %s  →  %d 条" %
                  (idx, len(cases), name.ljust(max_name_len), len(msgs)))
        f.write("\n")
        f.write(BANNER + "\n")
        f.write(" 测试完成：%d 个用例，共 %d 条气泡\n"
                % (len(cases), total_msgs))
        f.write(BANNER + "\n")
    return out_path, time.time() - start_time


def read_multiline():
    print("请输入 Agent 回复（可多行）。")
    print("  结束输入：单独一行输入 EOF，或 Ctrl-D（Windows: Ctrl-Z 后回车）")
    print("  取消    ：Ctrl-C")
    print("-" * 52)
    lines = []
    while True:
        prompt = "> " if not lines else "  "
        try:
            line = input(prompt)
        except EOFError:
            print()
            break
        if line.strip().upper() == 'EOF':
            break
        lines.append(line)
    return '\n'.join(lines)


def manual_mode():
    while True:
        try:
            text = read_multiline()
        except KeyboardInterrupt:
            print("\n\n已取消。")
            return
        if not text.strip():
            print("（没有输入内容）")
        else:
            msgs, cfg = split_reply(text)
            print_detailed(msgs, cfg)
        print()
        try:
            again = input("继续输入？(y/N) ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if again != 'y':
            return


def print_help():
    print("用法：")
    print("  python chat_split.py              # 交互菜单")
    print("  python chat_split.py --test       # 跑 test.txt")
    print("  python chat_split.py --test FILE  # 跑指定文件")
    print("  python chat_split.py --help       # 帮助")


def menu_mode():
    print(BANNER)
    print("  Agent 回复 → 社交媒体聊天气泡 切分器")
    print(BANNER)
    load_kaomojis()
    has_test = os.path.isfile(TEST_FILE)
    print()
    print("请选择模式：")
    print("  [1] 手动输入（结果直接显示在终端）")
    if has_test:
        print("  [2] 自动测试（读取 %s，结果写入文件）"
              % os.path.basename(TEST_FILE))
    else:
        print("  [2] （同目录未找到 %s）" % os.path.basename(TEST_FILE))
    print("  [q] 退出")
    print()
    try:
        choice = input("> ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return
    if choice in ('q', 'quit', 'exit'):
        return
    if choice == '2':
        if not has_test:
            print("[提示] 同目录没有 %s。" % os.path.basename(TEST_FILE))
            return
        print()
        print("开始自动测试：%s" % os.path.abspath(TEST_FILE))
        print("-" * 52)
        out_path, elapsed = run_auto_test(TEST_FILE)
        if out_path is None:
            return
        print("-" * 52)
        print("用时：%.2f 秒" % elapsed)
        print("结果已保存到：")
        print("  %s" % os.path.abspath(out_path))
        return
    manual_mode()


def main():
    args = sys.argv[1:]
    if '--help' in args or '-h' in args:
        print_help()
        return
    if '--test' in args or '-t' in args:
        idx = None
        for flag in ('--test', '-t'):
            if flag in args:
                idx = args.index(flag)
                break
        path = None
        if idx is not None and idx + 1 < len(args):
            nxt = args[idx + 1]
            if not nxt.startswith('-'):
                path = nxt
        if path is None:
            path = TEST_FILE
        load_kaomojis()
        print()
        print("开始自动测试：%s" % os.path.abspath(path))
        print("-" * 52)
        out_path, elapsed = run_auto_test(path)
        if out_path is None:
            return
        print("-" * 52)
        print("用时：%.2f 秒" % elapsed)
        print("结果已保存到：")
        print("  %s" % os.path.abspath(out_path))
        return
    menu_mode()


if __name__ == '__main__':
    main()
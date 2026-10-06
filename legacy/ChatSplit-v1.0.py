#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agent 回复 → 社交媒体聊天气泡 切分器

用法：
    python3 chat_split.py                # 交互菜单：手动输入 / 自动测试
    python3 chat_split.py --test         # 直接跑 test.txt，结果写入文件
    python3 chat_split.py --test a.txt   # 跑指定文件
    python3 chat_split.py --help         # 帮助

手动输入结束：单独一行 EOF，或 Ctrl-D（Windows: Ctrl-Z 后回车）

颜文字表：
    Kaomoji/kaomojis.txt（相对脚本目录，每行一个颜文字）
    用 Trie 索引，支持 5 万+ 条目，查询 O(匹配长度)。

测试文件格式：
    每个用例以一行 [CASE] 名字 开头，接下来到下一个 [CASE] 前为该用例内容。
    如果整个文件没有任何 [CASE] 标记，则整个文件作为一个用例。
"""

import os
import re
import sys
import time
import random


# ============================================================
# 颜文字表：Trie
# ============================================================

_HERE = os.path.dirname(os.path.abspath(__file__))
KAOMOJI_FILE = os.path.join(_HERE, 'Kaomoji', 'kaomojis.txt')
TEST_FILE = os.path.join(_HERE, 'test.txt')

_TRIE = {}
_END = '\x00'
_KAOMOJI_COUNT = 0


def load_kaomojis(path=KAOMOJI_FILE):
    global _TRIE, _KAOMOJI_COUNT
    _TRIE = {}
    _KAOMOJI_COUNT = 0

    if not os.path.isfile(path):
        print("[警告] 未找到颜文字文件：%s" % path)
        print("       颜文字将不会被识别。")
        return 0

    t0 = time.time()
    with open(path, 'r', encoding='utf-8-sig') as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith('#'):
                continue
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

    elapsed = (time.time() - t0) * 1000.0
    print("[信息] 已加载 %d 个颜文字（Trie），耗时 %.0f ms"
          % (_KAOMOJI_COUNT, elapsed))
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
# 配置
# ============================================================

class Config:
    def __init__(self):
        self.max_chars = 60
        self.target_chars = 20
        self.min_chars = 4
        self.max_messages = 6

        self.atomic_merge_prefix = 20

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
# 特殊片段保护（代码块 + URL）
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
# 分句 / 分单元
# ============================================================

LIST_RE = re.compile(r'^\s*(?:[-*+•]|\d+[.、)])\s+')
CLOSE_CHARS = ")]）】」』\"'`”’"
REAL_CHAR_RE = re.compile(r'[A-Za-z0-9_\u4e00-\u9fff]')
TILDE_CHARS = '~～〜'


def split_sentences(line):
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
            if i >= n or line[i].isspace():
                is_end = True
        if ch in TILDE_CHARS:
            if (i - 2 >= 0
                    and REAL_CHAR_RE.match(line[i - 2])
                    and (i >= n or line[i] not in TILDE_CHARS)):
                is_end = True

        if is_end:
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
    return [s for s in result if s]


def build_units(text):
    units = []
    blocks = re.split(r'\n\s*\n', text)
    bid = 0
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        bid += 1
        for raw in block.split('\n'):
            line = raw.strip()
            if not line:
                continue
            if LIST_RE.match(line):
                units.append((line, bid, 'list'))
            else:
                for s in split_sentences(line):
                    units.append((s, bid, 'text'))
    return units


# ============================================================
# 拼接 / 切点查找 / 超长拆分
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
    return a + b


SEPS = ['\n\n', '\n', '。', '！', '？', '!', '?', '…',
        '；', ';', '，', ',', '、', ' ']


def find_cut(text, cfg, blocks):
    hard = index_at_len(text, cfg.max_chars, blocks)
    if hard <= 0:
        m = PH_RE.match(text, 0)
        return m.end() if m else 1

    segment = text[:hard]
    candidates = set()
    for sep in SEPS:
        start = 0
        while True:
            p = segment.find(sep, start)
            if p < 0:
                break
            candidates.add(p + len(sep))
            start = p + 1

    if not candidates:
        return hard

    ideal = index_at_len(text, cfg.target_chars, blocks)

    good = sorted(c for c in candidates if ideal <= c <= hard)
    if good:
        return good[-1]

    below = sorted(c for c in candidates if c < ideal)
    if below:
        last = below[-1]
        if visible_len(text[:last], blocks) >= cfg.max_chars * 0.5:
            return last

    return hard


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
# 打包 / 条数控制
# ============================================================

def is_fragment(text):
    return not REAL_CHAR_RE.search(text)


def ends_with_tilde(text):
    t = text.rstrip()
    return bool(t) and t[-1] in TILDE_CHARS


def pack_units(units, cfg, blocks):
    msgs = []
    for text, bid, kind in units:
        for part in split_long(text, cfg, blocks):
            if msgs:
                prev_text, prev_bid = msgs[-1]
                plen = visible_len(prev_text, blocks)
                clen = visible_len(part, blocks)

                # 1) 纯标点碎片，无条件并入上一条
                if is_fragment(part):
                    msgs[-1][0] = join_text(prev_text, part)
                    continue

                # 2) 当前块是不可拆的原子片段（URL / 代码块）且本身超限，
                #    前一条又很短 → 直接合并，允许整条超 max_chars
                if (clen > cfg.max_chars
                        and plen <= cfg.atomic_merge_prefix
                        and prev_bid == bid):
                    msgs[-1][0] = join_text(prev_text, part)
                    continue

                # 3) 前一条以波浪号结尾：不合并，保持软句末的断开效果
                if (prev_bid == bid
                        and ends_with_tilde(prev_text)):
                    msgs.append([part, bid])
                    continue

                # 4) 前一条很短、同段，且合并后不超限 → 合并
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
    guard = 0
    while len(msgs) > cfg.max_messages and guard < 500:
        guard += 1
        best_i = -1
        best_len = None
        for i in range(len(msgs) - 1):
            a = visible_len(msgs[i][0], blocks)
            b = visible_len(msgs[i + 1][0], blocks)
            if a + b > cfg.max_chars * 3:
                continue
            if best_len is None or a + b < best_len:
                best_len = a + b
                best_i = i
        if best_i < 0:
            break
        msgs[best_i][0] = join_text(msgs[best_i][0], msgs[best_i + 1][0])
        del msgs[best_i + 1]
    return msgs


# ============================================================
# 对外主入口
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
    return out, cfg


# ============================================================
# 输出：详细模式（手动）
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


# ============================================================
# 测试用例加载
# ============================================================

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
        body = parts[i + 1].strip() if i + 1 < len(parts) else ''
        if body:
            cases.append((name, body))
    return cases


def run_auto_test(path, out_path=None):
    """跑自动测试。终端只显示进度；完整结果写入文件。
    返回 (输出文件路径, 用时秒数) 或 (None, 0)。"""
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

            name_padded = name.ljust(max_name_len)
            print("  [%2d/%2d] %s  →  %d 条" %
                  (idx, len(cases), name_padded, len(msgs)))

        f.write("\n")
        f.write(BANNER + "\n")
        f.write(" 测试完成：%d 个用例，共 %d 条气泡\n"
                % (len(cases), total_msgs))
        f.write(BANNER + "\n")

    elapsed = time.time() - start_time
    return out_path, elapsed


# ============================================================
# 手动输入
# ============================================================

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


# ============================================================
# 主菜单 / 入口
# ============================================================

def print_help():
    print("用法：")
    print("  python chat_split.py              # 交互菜单")
    print("  python chat_split.py --test       # 跑 test.txt，结果写入文件")
    print("  python chat_split.py --test FILE  # 跑指定文件")
    print("  python chat_split.py --help       # 显示帮助")
    print()
    print("测试文件格式：")
    print("  [CASE] 用例名")
    print("  用例内容（多行，直到下一个 [CASE]）")
    print()
    print("  [CASE] 另一个用例")
    print("  ...")


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
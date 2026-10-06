# -*- coding: utf-8 -*-
"""命令行接口。"""

import os
import re
import sys
import time

from . import kaomoji
from .splitter import split_reply


BANNER = "=" * 52

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
TEST_FILE = os.path.join(_ROOT, 'tests', 'test.txt')
RESULT_DIR = os.path.join(_ROOT, 'tests', 'results')


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
        print("─── [%d/%d]  %d 字 ───"
              % (i, len(msgs), len(m)))
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


CASE_MARK_RE = re.compile(r'^\s*\[CASE\]\s*(.*?)\s*$', re.MULTILINE)


def load_test_cases(path):
    with open(path, 'r', encoding='utf-8-sig') as f:
        content = f.read()
    if '[CASE]' not in content:
        text = content.strip()
        return [("整个文件", text)] if text else []
    parts = CASE_MARK_RE.split(content)
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
        os.makedirs(RESULT_DIR, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        out_path = os.path.join(RESULT_DIR, "test_result_%s.txt" % ts)
    start_time = time.time()
    total_msgs = 0
    max_name_len = max((len(name) for name, _ in cases), default=0)
    with open(out_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(BANNER + "\n")
        f.write(" 气口 —— AI 回复分句器\n")
        f.write(" 自动测试报告\n")
        f.write(BANNER + "\n")
        f.write(" 测试文件：%s\n" % os.path.abspath(path))
        f.write(" 运行时间：%s\n"
                % time.strftime("%Y-%m-%d %H:%M:%S"))
        f.write(" 颜文字表：%d 条\n" % kaomoji.kaomoji_count())
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
    print("  结束输入：单独一行输入 EOF，或 Ctrl-D")
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
    print("  python -m qikou              # 交互菜单")
    print("  python -m qikou --test       # 跑 tests/test.txt")
    print("  python -m qikou --test FILE  # 跑指定文件")
    print("  python -m qikou --help       # 显示帮助")


def menu_mode():
    print(BANNER)
    print(" 气口 —— AI 回复分句器")
    print(BANNER)
    kaomoji.load_kaomojis()
    has_test = os.path.isfile(TEST_FILE)
    print()
    print("请选择模式：")
    print("  [1] 手动输入")
    if has_test:
        print("  [2] 自动测试（读取 %s）"
              % os.path.basename(TEST_FILE))
    else:
        print("  [2] （未找到 %s）" % os.path.basename(TEST_FILE))
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
            print("[提示] 未找到 %s。" % os.path.basename(TEST_FILE))
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
        kaomoji.load_kaomojis()
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

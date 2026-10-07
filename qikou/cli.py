# -*- coding: utf-8 -*-
"""命令行接口。

子命令形态::

    qikou split [文件]    切分（默认从标准输入读取）
    qikou test  [文件]    跑测试用例
    qikou menu            交互菜单
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from typing import Any, List, Optional, Sequence

from . import __version__, kaomoji
from .config import Config
from .message import Message
from .splitter import split, split_with_delays

__all__ = ["build_parser", "main"]

PROG = "qikou"
BANNER = "=" * 52

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)

# 用例文件与报告目录属于源码仓库，不随 wheel 分发。装成包之后这两个变量
# 为 None：test 仍可跑指定文件，但报告写到当前工作目录，绝不写进
# site-packages。
_REPO = _ROOT if os.path.isdir(os.path.join(_ROOT, 'tests')) else None
TEST_FILE = os.path.join(_REPO, 'tests', 'test.txt') if _REPO else None
RESULT_DIR = os.path.join(_REPO, 'tests', 'results') if _REPO else None


# ============================================================
# 终端
# ============================================================

def _setup_streams() -> None:
    """尽量把 stdout/stderr 切到 UTF-8。

    否则在非 UTF-8 控制台（或 PYTHONIOENCODING=ascii）下打印中文与边框
    会直接抛 UnicodeEncodeError。切不过就跳过，不影响功能。
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass


def _isatty(stream: Any = None) -> bool:
    try:
        return bool((stream or sys.stdout).isatty())
    except (AttributeError, ValueError):
        return False


# ============================================================
# 输入
# ============================================================

def _read_input(path: Optional[str]) -> str:
    """读入待切分文本；path 为 None 或 '-' 时读标准输入。"""
    if path is None or path == '-':
        return sys.stdin.read()
    with open(path, 'r', encoding='utf-8-sig') as f:
        return f.read()


# ============================================================
# 输出
# ============================================================

def effective_config(text: str, config: Optional[Config] = None) -> Config:
    """返回这段文本实际生效的配置（与 split 内部一致）。"""
    return (config or Config()).scaled_for_length(len(text.strip()))


def print_messages(messages: List[Message], cfg: Config) -> None:
    """带装饰地逐条打印，并给出模拟发送时间轴。"""
    print()
    print(BANNER)
    print(" 切分结果：%d 条" % len(messages))
    print(" 参数：max=%d  target=%d  min=%d  max_messages=%d"
          % (cfg.max_chars, cfg.target_chars,
             cfg.min_chars, cfg.max_messages))
    print(BANNER)
    for i, m in enumerate(messages, 1):
        print()
        print("─── [%d/%d]  %d 字 ───"
              % (i, len(messages), len(m.text)))
        print(m.text)
    print()
    print("-" * 52)
    print("模拟发送时间轴：")
    t = 0.0
    for i, m in enumerate(messages, 1):
        print("  t=%5.2fs  第 %d 条（%d 字，等待 %.2fs）"
              % (t, i, len(m.text), m.delay))
        t += m.delay
    print("  t=%5.2fs  发送完毕" % t)


def print_plain(messages: List[Message]) -> None:
    """只输出消息正文，空行分隔，便于管道消费。"""
    sys.stdout.write("\n\n".join(m.text for m in messages))
    if messages:
        sys.stdout.write("\n")


def print_json(messages: List[Message]) -> None:
    payload = [{"text": m.text, "delay": round(m.delay, 3)} for m in messages]
    print(json.dumps(payload, ensure_ascii=False, indent=2))


# ============================================================
# 测试报告
# ============================================================

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
    """跑完所有用例并写报告，返回 (报告路径, 用时)。"""
    if not os.path.isfile(path):
        print("[错误] 找不到测试文件：%s" % path)
        return None, 0.0
    cases = load_test_cases(path)
    if not cases:
        print("[信息] 测试文件里没有用例。")
        return None, 0.0
    if out_path is None:
        ts = time.strftime("%Y%m%d_%H%M%S")
        if RESULT_DIR is not None:
            os.makedirs(RESULT_DIR, exist_ok=True)
            out_path = os.path.join(RESULT_DIR, "test_result_%s.txt" % ts)
        else:
            # 非源码仓库运行：报告写到当前工作目录
            out_path = os.path.abspath("test_result_%s.txt" % ts)
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
            msgs = split(text)
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


def load_kaomojis_checked():
    """加载颜文字语料；加载为空时明确报错。

    语料缺失时切分仍能跑，只是颜文字不再被识别——结果悄悄变差。
    这里把它变成一个看得见的失败。
    """
    n = kaomoji.load_kaomojis()
    if n <= 0:
        print()
        print("[错误] 颜文字语料为空（0 条），切分结果会明显变差。")
        print("       预期语料文件：%s" % kaomoji.default_path())
        return False
    print("[信息] 已加载 %d 条颜文字" % n)
    return True


# ============================================================
# 子命令
# ============================================================

def cmd_split(args: argparse.Namespace) -> int:
    path = args.file

    if path is None and not sys.stdin.isatty():
        path = '-'                      # 管道接进来的，按过滤器处理
    elif path is None:
        print("从标准输入读取，结束输入：Ctrl-Z 回车（Windows）/ Ctrl-D",
              file=sys.stderr)

    try:
        text = _read_input(path)
    except FileNotFoundError:
        print("%s: 找不到文件：%s" % (PROG, path), file=sys.stderr)
        return 1
    except IsADirectoryError:
        print("%s: 这是一个目录：%s" % (PROG, path), file=sys.stderr)
        return 1
    except UnicodeDecodeError as exc:
        print("%s: 无法以 UTF-8 解码 %s（%s）" % (PROG, path, exc),
              file=sys.stderr)
        return 1
    except OSError as exc:
        print("%s: 读取失败：%s" % (PROG, exc), file=sys.stderr)
        return 1

    config = Config()
    if args.max_chars is not None:
        config.max_chars = args.max_chars
    if args.target_chars is not None:
        config.target_chars = args.target_chars
    if args.max_messages is not None:
        config.max_messages = args.max_messages

    messages = split_with_delays(text, config=config)

    if args.json:
        print_json(messages)
    elif args.quiet or not _isatty():
        print_plain(messages)
    else:
        print_messages(messages, effective_config(text, config))
    return 0


def cmd_test(args: argparse.Namespace) -> int:
    path = args.file
    if path is None:
        path = TEST_FILE
    if path is None:
        print("%s: 未找到内置用例文件（当前不是从源码仓库运行）。" % PROG,
              file=sys.stderr)
        print("       可指定文件：%s test path/to/cases.txt" % PROG,
              file=sys.stderr)
        return 1

    if not load_kaomojis_checked():
        return 1

    print()
    print("开始自动测试：%s" % os.path.abspath(path))
    print("-" * 52)
    out_path, elapsed = run_auto_test(path)
    if out_path is None:
        return 1
    print("-" * 52)
    print("用时：%.2f 秒" % elapsed)
    print("结果已保存到：")
    print("  %s" % os.path.abspath(out_path))
    return 0


def cmd_menu(args: argparse.Namespace) -> int:
    print(BANNER)
    print(" 气口 —— AI 回复分句器")
    print(BANNER)
    if not load_kaomojis_checked():
        return 1

    test_file = TEST_FILE
    has_test = test_file is not None and os.path.isfile(test_file)
    print()
    print("请选择模式：")
    print("  [1] 手动输入")
    if has_test and test_file is not None:
        print("  [2] 自动测试（读取 %s）" % os.path.basename(test_file))
    elif test_file is None:
        print("  [2] （当前不是从源码仓库运行，内置用例不可用）")
    else:
        print("  [2] （未找到 %s）" % os.path.basename(test_file))
    print("  [q] 退出")
    print()
    try:
        choice = input("> ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return 0
    if choice in ('q', 'quit', 'exit'):
        return 0
    if choice == '2':
        if not has_test or test_file is None:
            if test_file is None:
                print("[提示] 当前不是从源码仓库运行，内置用例不可用。")
                print("      可用 test 子命令指定用例文件。")
            else:
                print("[提示] 未找到 %s。" % os.path.basename(test_file))
            return 0
        print()
        print("开始自动测试：%s" % os.path.abspath(test_file))
        print("-" * 52)
        out_path, elapsed = run_auto_test(test_file)
        if out_path is None:
            return 1
        print("-" * 52)
        print("用时：%.2f 秒" % elapsed)
        print("结果已保存到：")
        print("  %s" % os.path.abspath(out_path))
        return 0
    return _manual_mode()


def _read_multiline() -> str:
    print("请输入 AI 回复（可多行）。")
    print("  结束输入：单独一行输入 EOF，或 Ctrl-D")
    print("  取消    ：Ctrl-C")
    print("-" * 52)
    lines: List[str] = []
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


def _manual_mode() -> int:
    while True:
        try:
            text = _read_multiline()
        except KeyboardInterrupt:
            print("\n\n已取消。")
            return 0
        if not text.strip():
            print("（没有输入内容）")
        else:
            messages = split_with_delays(text)
            print_messages(messages, effective_config(text))
        print()
        try:
            again = input("继续输入？(y/N) ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if again != 'y':
            return 0


# ============================================================
# 入口
# ============================================================

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="气口 / Cadence —— 把 AI 的长回复切成读起来像真人发出的短消息。",
        epilog="不带子命令时显示本帮助。示例：echo \"长文本\" | qikou split",
    )
    parser.add_argument(
        "--version", action="version", version="%(prog)s " + __version__,
    )
    sub = parser.add_subparsers(dest="command", metavar="命令")

    p_split = sub.add_parser(
        "split", help="切分文本（默认从标准输入读取）",
        description="把一段文本切成若干条短消息。",
    )
    p_split.add_argument(
        "file", nargs="?", metavar="文件",
        help="要切分的文本文件；'-' 或省略表示标准输入",
    )
    p_split.add_argument("-j", "--json", action="store_true",
                         help="以 JSON 输出（含每条的建议延迟）")
    p_split.add_argument("-q", "--quiet", action="store_true",
                         help="只输出消息正文，空行分隔")
    p_split.add_argument("-c", "--max-chars", type=int, metavar="N",
                         help="单条硬上限，调小更碎")
    p_split.add_argument("-T", "--target-chars", type=int, metavar="N",
                         help="理想长度")
    p_split.add_argument("-m", "--max-messages", type=int, metavar="N",
                         help="条数上限（软）")
    p_split.set_defaults(handler=cmd_split)

    p_test = sub.add_parser(
        "test", help="跑测试用例并输出报告（仅源码仓库可用）",
        description="跑一份 [CASE] 格式的用例文件，报告写入 tests/results/。",
    )
    p_test.add_argument(
        "file", nargs="?", metavar="文件",
        help="用例文件，默认 tests/test.txt",
    )
    p_test.set_defaults(handler=cmd_test)

    p_menu = sub.add_parser("menu", help="交互菜单")
    p_menu.set_defaults(handler=cmd_menu)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    _setup_streams()
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "command", None) is None:
        parser.print_help()
        return 0
    return args.handler(args)

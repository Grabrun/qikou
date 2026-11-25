# -*- coding: utf-8 -*-
"""后处理：补全未闭合的 Markdown 与引号。"""

from typing import List

from .patterns import HR_RE

__all__ = ["postprocess_message"]


def fix_unbalanced_md(msg: str) -> str:
    """补 ** 与 __。水平线和反引号不处理。"""
    if not msg:
        return msg
    if HR_RE.match(msg.strip()):
        return msg
    for marker in ('**', '__'):
        if msg.count(marker) % 2 == 1:
            msg = msg.rstrip() + marker
    return msg


def fix_unbalanced_quote(msg: str) -> str:
    """补中文引号 / 日式引号。括号不补。"""
    if not msg:
        return msg
    pairs = [('“', '”'), ('「', '」'), ('『', '』')]
    for op, cl in pairs:
        if msg.count(op) > msg.count(cl):
            msg = msg.rstrip() + cl
    return msg


def fix_unbalanced_structure(msg: str, max_close: int = 3) -> str:
    """补全未闭合的代码围栏与括号（仅用于 DP 兜底消息）。

    只在出现未闭合结构时追加最少字符；``max_close`` 防止病态输入
    （例如几万个反引号）被补成更大的字符串。
    """
    if not msg:
        return msg
    if HR_RE.match(msg.strip()):
        return msg

    for fence in ('```', '~~~'):
        count = msg.count(fence)
        if count % 2 == 1 and count <= max_close:
            msg = msg.rstrip() + '\n' + fence

    pairs = {'(': ')', '[': ']', '{': '}', '（': '）', '【': '】'}
    closers = {v: k for k, v in pairs.items()}
    stack: List[str] = []
    for ch in msg:
        if ch in pairs:
            stack.append(ch)
        elif ch in closers and stack and pairs[stack[-1]] == ch:
            stack.pop()
    if stack:
        msg = msg.rstrip() + ''.join(pairs[ch] for ch in reversed(stack))
    return msg


def postprocess_message(msg: str, repair_structure: bool = False) -> str:
    msg = fix_unbalanced_md(msg)
    msg = fix_unbalanced_quote(msg)
    if repair_structure:
        msg = fix_unbalanced_structure(msg)
    return msg

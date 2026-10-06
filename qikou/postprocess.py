# -*- coding: utf-8 -*-
"""后处理：补全未闭合的 Markdown 与引号。"""

from .patterns import HR_RE


def fix_unbalanced_md(msg):
    """补 ** 与 __。水平线和反引号不处理。"""
    if not msg:
        return msg
    if HR_RE.match(msg.strip()):
        return msg
    for marker in ('**', '__'):
        if msg.count(marker) % 2 == 1:
            msg = msg.rstrip() + marker
    return msg


def fix_unbalanced_quote(msg):
    """补中文引号 / 日式引号。括号不补。"""
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

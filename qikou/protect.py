# -*- coding: utf-8 -*-
"""特殊片段保护：代码块 + URL。"""

from .patterns import CODE_RE, URL_RE, PH_RE


def protect_special(text):
    """把代码块和 URL 替换成占位符，返回 (替换后文本, 片段列表)。"""
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
    """真实字符长度（占位符按原片段长度计）。"""
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
    """返回索引 i，使 visible_len(text[:i]) <= limit 且尽量大。"""
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

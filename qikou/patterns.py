# -*- coding: utf-8 -*-
"""所有编译好的正则表达式及配套判定函数。"""

import re

OPEN_BRACKETS = '([{（【「『'
CLOSE_BRACKETS = ')]}）】」』'
CLOSE_CHARS = ")]）】」』\"'`”’"
TILDE_CHARS = '~～〜˜˷∼∽⁓'
LEADING_MOVE_CHARS = '，。！？；：、）】」』”’'

REAL_CHAR_RE = re.compile(r'[^\W_]')

# 占位符字符空间：私有使用区，而不是 NUL。
#
# 2026-11 审计 QK-06：原占位符形如 "\x00N\x00"，与输入文本的字符空间重叠——
# 输入自身带 NUL 片段时会被当成占位符替换，表现为代码块被复制、字面片段消失。
# 现在占位符用 U+E000/U+E001 包围；输入里出现的 U+E000/U+E001/U+E002 先用
# U+E002 转义（见 protect.py 的 _escape/_unescape），还原后再转回，往返无损。
PH_OPEN = '\ue000'
PH_CLOSE = '\ue001'
PH_ESCAPE = '\ue002'

PH_RE = re.compile(PH_OPEN + r'(\d+)' + PH_CLOSE)


LIST_RE = re.compile(r'^\s*(?:[-*+•]|\d+[.、)])\s+')
TABLE_SEP_RE = re.compile(r'^\s*\|[\s\-:|]+\|\s*$')
TABLE_ROW_RE = re.compile(r'^\s*\|.*\|\s*$')
HEADING_RE = re.compile(r'^\s*#{1,6}\s+')
HR_RE = re.compile(r'^\s*(?:-{3,}|\*{3,}|_{3,})\s*$')
HTML_BR_RE = re.compile(r'<br\s*/?>', re.IGNORECASE)


CODE_RE = re.compile(r'```[\s\S]*?```|~~~[\s\S]*?~~~')
# 字符类里排除占位符起始符：若允许它参与匹配，"URL 紧贴代码块"（如
# https://a.com/a```code```）时 URL 会一口吞掉前一个占位符，形成嵌套占位符，
# 还原时漏展开——表现为代码块内容丢失。URL 本身也不该含私有区字符。
URL_RE = re.compile(
    r'https?://[^\s' + PH_OPEN + PH_CLOSE + r'\u4e00-\u9fff\u3000-\u303f'
    r'\uff01-\uff5e]+'
)


def is_list_start(text: str) -> bool:
    return bool(LIST_RE.match(text.lstrip()))


def is_heading(text: str) -> bool:
    return bool(HEADING_RE.match(text.lstrip()))


def is_hr(text: str) -> bool:
    return bool(HR_RE.match(text))


def is_table_msg(msg: str) -> bool:
    lines = [l for l in msg.split('\n') if l.strip()]
    if len(lines) < 2:
        return False
    return all(l.lstrip().startswith('|') for l in lines)

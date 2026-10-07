# -*- coding: utf-8 -*-
"""所有编译好的正则表达式及配套判定函数。"""

import re


OPEN_BRACKETS = '([{（【「『'
CLOSE_BRACKETS = ')]}）】」』'
CLOSE_CHARS = ")]）】」』\"'`”’"
TILDE_CHARS = '~～〜˜˷∼∽⁓'
LEADING_MOVE_CHARS = '，。！？；：、）】」』”’'

REAL_CHAR_RE = re.compile(r'[^\W_]')


LIST_RE = re.compile(r'^\s*(?:[-*+•]|\d+[.、)])\s+')
TABLE_SEP_RE = re.compile(r'^\s*\|[\s\-:|]+\|\s*$')
TABLE_ROW_RE = re.compile(r'^\s*\|.*\|\s*$')
HEADING_RE = re.compile(r'^\s*#{1,6}\s+')
HR_RE = re.compile(r'^\s*(?:-{3,}|\*{3,}|_{3,})\s*$')
HTML_BR_RE = re.compile(r'<br\s*/?>', re.IGNORECASE)


CODE_RE = re.compile(r'```[\s\S]*?```|~~~[\s\S]*?~~~')
URL_RE = re.compile(
    r'https?://[^\s\u4e00-\u9fff\u3000-\u303f\uff01-\uff5e]+'
)
PH_RE = re.compile(r'\x00(\d+)\x00')


def is_before_list_item(right: str) -> bool:
    return bool(LIST_RE.match(right))


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

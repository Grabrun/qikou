# -*- coding: utf-8 -*-
"""词表与切点基础分。"""

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
    '但是', '但', '不过', '然而',
    '可是', '只是', '偏偏',
    '所以', '因此', '因而',
    '从而', '于是',
    '而且', '并且', '况且',
    '何况', '甚至', '更有甚者',
    '然后', '接着', '随后',
    '之后', '最后', '紧接着',
    '或者', '还是', '要么',
    '的话', '的时候', '以后',
    '之前', '以来',
    '也就是说', '换言之',
    '换句话说',
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

SEP_BASE_SCORE = {
    '\n\n': 100,
    '\n': 80,
    '。': 60, '！': 60, '？': 60,
    '!': 60, '?': 60, '…': 60,
    '；': 40, ';': 40,
    '：': 35, ':': 35,
    '，': 20, ',': 20, '、': 20,
    ' ': 10,
}

SEPS = list(SEP_BASE_SCORE.keys())
MIN_RIGHT_LEN = 30
ASCII_PUNCT_END = set('.!?,;:')

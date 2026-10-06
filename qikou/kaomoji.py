# -*- coding: utf-8 -*-
"""颜文字表：Trie 索引。"""

import os
import time


_END = '\x00'

_state = {
    'trie': {},
    'count': 0,
}


def load_kaomojis(path=None):
    """从文件加载颜文字到 Trie。返回去重后的条目数。"""
    if path is None:
        here = os.path.dirname(os.path.abspath(__file__))
        root = os.path.dirname(here)
        path = os.path.join(root, 'kaomoji', 'kaomojis.txt')

    trie = {}
    count = 0

    if not os.path.isfile(path):
        print("[警告] 未找到颜文字文件：%s" % path)
        _state['trie'] = trie
        _state['count'] = 0
        return 0

    t0 = time.time()
    with open(path, 'r', encoding='utf-8-sig') as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith('#'):
                continue
            node = trie
            for c in s:
                nxt = node.get(c)
                if nxt is None:
                    nxt = {}
                    node[c] = nxt
                node = nxt
            if _END not in node:
                count += 1
            node[_END] = True

    _state['trie'] = trie
    _state['count'] = count

    print("[信息] 已加载 %d 个颜文字（Trie），耗时 %.0f ms"
          % (count, (time.time() - t0) * 1000.0))
    return count


def kaomoji_count():
    return _state['count']


def kaomoji_len(s, i):
    """从 s[i] 起匹配颜文字，返回最长匹配长度。无匹配返回 0。"""
    trie = _state['trie']
    if not trie or i >= len(s):
        return 0
    node = trie
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


def is_kaomoji(text):
    """判断整段文本是否精确命中颜文字表。"""
    t = text.strip()
    if not t:
        return False
    trie = _state['trie']
    node = trie
    for c in t:
        nxt = node.get(c)
        if nxt is None:
            return False
        node = nxt
    return _END in node

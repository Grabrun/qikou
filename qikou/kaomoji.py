# -*- coding: utf-8 -*-
"""颜文字语料：Trie 索引。

语料随包分发，直接放在包目录下，构建 wheel 时由 pyproject.toml 的
package-data 一并打包。

历史教训：早期代码指向仓库根目录的 'kaomoji'（小写、且在包外），
在 Windows 上被大小写不敏感的文件系统掩盖，Linux/macOS 上会静默加载
0 条；而包外目录在 pip 安装后根本不存在。
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Dict, Optional, Union

__all__ = ["default_path", "ensure_loaded", "is_kaomoji", "kaomoji_count",
           "kaomoji_len", "load_kaomojis"]

logger = logging.getLogger(__name__)

_PATH = Union[str, "os.PathLike[str]"]

_END = "\x00"
KAOMOJI_FILE = "kaomojis.txt"

_state: Dict[str, Any] = {
    "trie": {},
    "count": 0,
    "loaded": False,
}

# 语料是进程级共享状态。用可重入锁保护"检查-加载"的竞态：多个线程同时
# 首次调用 split() 时，只会真正加载一次。
_lock = threading.RLock()


def default_path() -> str:
    """返回包内语料文件的绝对路径。"""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, KAOMOJI_FILE)


def load_kaomojis(path: Optional[_PATH] = None) -> int:
    """把颜文字语料加载进 Trie，返回去重后的条目数。

    Args:
        path: 语料文件路径；默认用包内自带的那份。

    Returns:
        去重后的条目数；文件不存在时返回 0。

    成功时不向 stdout 输出任何内容（信息走 :mod:`logging`）。语料缺失只
    记录一条 warning，切分仍可继续进行，只是不再识别颜文字。
    """
    target = default_path() if path is None else os.fspath(path)

    trie: Dict[str, Any] = {}
    count = 0

    if not os.path.isfile(target):
        logger.warning("未找到颜文字语料：%s", target)
        with _lock:
            _state["trie"] = trie
            _state["count"] = 0
            _state["loaded"] = True
        return 0

    t0 = time.perf_counter()
    with open(target, "r", encoding="utf-8-sig") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
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

    with _lock:
        _state["trie"] = trie
        _state["count"] = count
        _state["loaded"] = True

    logger.debug("已加载 %d 个颜文字，耗时 %.0f ms",
                 count, (time.perf_counter() - t0) * 1000.0)
    return count


def ensure_loaded() -> None:
    """首次使用时自动加载默认语料；已加载或已尝试过则直接返回。

    调用 :func:`load_kaomojis` 显式指定过语料后，这里不会再覆盖它。
    多线程并发首次调用只会真正加载一次。
    """
    if not _state["loaded"]:
        with _lock:
            if not _state["loaded"]:
                load_kaomojis()


def kaomoji_count() -> int:
    """返回当前已加载的颜文字条数。"""
    return int(_state["count"])


def kaomoji_len(s: str, i: int) -> int:
    """从 ``s[i]`` 起匹配颜文字，返回最长匹配长度；无匹配返回 0。"""
    trie = _state["trie"]
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


def is_kaomoji(text: str) -> bool:
    """判断整段文本是否精确命中颜文字表。"""
    t = text.strip()
    if not t:
        return False
    node = _state["trie"]
    for c in t:
        nxt = node.get(c)
        if nxt is None:
            return False
        node = nxt
    return _END in node

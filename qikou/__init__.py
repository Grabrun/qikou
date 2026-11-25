# -*- coding: utf-8 -*-
"""气口 / Cadence —— 让 AI 回复会呼吸。

把一段长文本切成若干条短消息，读起来像真人一条条发出来的聊天内容。

::

    from qikou import split

    for message in split(reply):
        send(message)
"""

from .config import Config
from .kaomoji import kaomoji_count, load_kaomojis
from .splitter import SplitResult, split, split_with_report

__version__ = "3.0.0"

__all__ = [
    "Config",
    "SplitResult",
    "kaomoji_count",
    "load_kaomojis",
    "split",
    "split_with_report",
]

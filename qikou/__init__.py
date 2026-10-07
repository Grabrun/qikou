# -*- coding: utf-8 -*-
"""气口 / Cadence —— 让 AI 回复会呼吸。

把一段长文本切成若干条短消息，读起来像真人一条条发出来的聊天内容。

::

    from qikou import split

    for text in split("好的，我来帮你规划。首先确定目标。然后每天练习。"):
        send(text)

需要发送延迟时用 :func:`split_with_delays`::

    from qikou import split_with_delays

    for m in split_with_delays(long_reply):
        send(m.text)
        time.sleep(m.delay)
"""

from .config import Config
from .kaomoji import kaomoji_count, load_kaomojis
from .message import Message
from .splitter import split, split_with_delays

__version__ = "2.1.0"

__all__ = [
    "Config",
    "Message",
    "kaomoji_count",
    "load_kaomojis",
    "split",
    "split_with_delays",
]

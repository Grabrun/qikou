# -*- coding: utf-8 -*-
"""切分结果类型。"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Message"]


@dataclass(frozen=True)
class Message:
    """一条切分后的消息。

    ::

        from qikou import split_with_delays

        for m in split_with_delays(text):
            send(m.text)
            time.sleep(m.delay)
    """

    #: 消息正文。
    text: str
    #: 建议发送延迟（秒）。
    delay: float

    def __str__(self) -> str:
        return self.text

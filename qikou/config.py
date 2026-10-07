# -*- coding: utf-8 -*-
"""切分配置。"""

from __future__ import annotations

from dataclasses import dataclass, replace

__all__ = ["Config"]


@dataclass
class Config:
    """切分参数，所有字段都有默认值，按需覆盖即可。

    ::

        from qikou import Config, split

        split(text, config=Config(max_chars=80, max_messages=10))

    传入 :func:`~qikou.split` 的实例不会被修改——长度自适应由
    :meth:`scaled_for_length` 返回一个新实例来完成。
    """

    #: 单条硬上限，超过触发切分。
    max_chars: int = 60
    #: 理想长度，切点优选位置。
    target_chars: int = 20
    #: 低于此长度尝试与相邻条目合并。
    min_chars: int = 4
    #: 条数上限（软）。结构类条目不参与合并，因此可能超过。
    max_messages: int = 6
    #: 短前缀 + 超长原子片段合并的阈值。
    atomic_merge_prefix: int = 20
    #: 合并后单条上限。
    merge_max_chars: int = 60

    def scaled_for_length(self, total: int) -> "Config":
        """返回按文本总长放宽后的新配置，**不改动 self**。

        长文本放宽单条上限可以避免碎成一地；合并上限同步放大，否则
        长文本的相邻对全都超过它，条数上限永远够不到。
        """
        if total <= 150:
            return replace(self)
        if total <= 400:
            max_chars, target_chars, max_messages = 90, 30, self.max_messages
        elif total <= 800:
            max_chars, target_chars, max_messages = 120, 45, 8
        else:
            max_chars, target_chars, max_messages = 160, 60, 10

        new_max = max(self.max_chars, max_chars)
        return replace(
            self,
            max_chars=new_max,
            target_chars=max(self.target_chars, target_chars),
            max_messages=max(self.max_messages, max_messages),
            merge_max_chars=max(self.merge_max_chars, new_max),
        )

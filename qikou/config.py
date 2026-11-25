# -*- coding: utf-8 -*-
"""切分配置。"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

__all__ = ["Config"]

# 默认值。长度自适应只放大**默认值**，显式设定过的字段原样保留——否则
# 用户传 max_chars=30 会被分层逻辑悄悄改回 120（见 2026-11 审计 QK-01）。
DEFAULT_MAX_CHARS = 60
DEFAULT_TARGET_CHARS = 20
DEFAULT_MIN_CHARS = 4
DEFAULT_MAX_MESSAGES = 6
DEFAULT_ATOMIC_MERGE_PREFIX = 20
DEFAULT_MERGE_MAX_CHARS = 60

_INT_FIELDS = (
    "max_chars",
    "target_chars",
    "min_chars",
    "max_messages",
    "atomic_merge_prefix",
    "merge_max_chars",
)

# max_chars 的内部哨兵：构造后即被换成默认值，对外不可见（repr 里是 60）。
_UNSET_MAX_CHARS = -1


@dataclass
class Config:
    """切分参数，所有字段都有默认值，按需覆盖即可。

    ::

        from qikou import Config, split

        split(text, config=Config(max_chars=80, max_messages=10))

    传入 :func:`~qikou.split` 的实例不会被修改——长度自适应由
    :meth:`scaled_for_length` 返回一个新实例来完成。

    构造时会校验取值：非整数抛 :class:`TypeError`，越界抛
    :class:`ValueError`。默认值之外的字段**不会**被长度自适应改写；
    要强制保持默认行为（例如 CLI 传了 ``-c 60``）可置 ``auto_scale=False``。
    """

    #: 单条硬上限，超过触发切分。默认 60；显式传入的值不会被长度自适应
    #: 放大（内部用 -1 作哨兵区分"没传"与"传了 60"）。
    max_chars: int = _UNSET_MAX_CHARS
    #: 理想长度，切点优选位置。
    target_chars: int = DEFAULT_TARGET_CHARS
    #: 低于此长度尝试与相邻条目合并。
    min_chars: int = DEFAULT_MIN_CHARS
    #: 条数上限（软）。结构类条目不参与合并；且受 ``merge_max_chars``
    #: 约束，条文数不可能少于 ``ceil(可见字数 / merge_max_chars)``。
    #: ``<= 0`` 表示不限条数。
    max_messages: int = DEFAULT_MAX_MESSAGES
    #: 短前缀 + 超长原子片段合并的阈值。
    atomic_merge_prefix: int = DEFAULT_ATOMIC_MERGE_PREFIX
    #: 合并后单条上限。
    merge_max_chars: int = DEFAULT_MERGE_MAX_CHARS
    #: 是否允许按文本总长自动放大**默认**配置。
    auto_scale: bool = True
    #: 是否显式给过 max_chars（内部记账，不参与比较与打印）。
    explicit_max_chars: bool = field(default=False, init=False,
                                     repr=False, compare=False)

    def __post_init__(self) -> None:
        self.explicit_max_chars = self.max_chars != _UNSET_MAX_CHARS
        if not self.explicit_max_chars:
            self.max_chars = DEFAULT_MAX_CHARS
        for name in _INT_FIELDS:
            value: Any = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(
                    "%s 必须是 int，收到 %r（%s）"
                    % (name, value, type(value).__name__))
        if self.max_chars <= 0:
            raise ValueError("max_chars 必须为正整数，收到 %r" % (self.max_chars,))
        if self.merge_max_chars <= 0:
            raise ValueError(
                "merge_max_chars 必须为正整数，收到 %r" % (self.merge_max_chars,))
        if self.target_chars < 0:
            raise ValueError(
                "target_chars 不能为负，收到 %r" % (self.target_chars,))
        # target_chars 允许大于 max_chars：此时打分里的长度奖励自然失效，
        # 但 max_chars 仍然是硬上限，不构成错误（CLI 的 -c 6 就是这种情形）。
        if self.min_chars < 0:
            raise ValueError("min_chars 不能为负，收到 %r" % (self.min_chars,))
        if self.atomic_merge_prefix < 0:
            raise ValueError(
                "atomic_merge_prefix 不能为负，收到 %r"
                % (self.atomic_merge_prefix,))

    def scaled_for_length(self, total: int) -> "Config":
        """返回按文本总长放宽后的新配置，**不改动 self**。

        长文本放宽单条上限可以避免碎成一地；合并上限同步放大，否则
        长文本的相邻对全都超过它，条数上限永远够不到。

        只放大仍处于默认值的字段。显式设定过 ``max_chars``（或
        ``auto_scale=False``）时原样返回，避免覆盖调用方的意图。
        """
        explicit = not self.auto_scale or self.explicit_max_chars
        if explicit or total <= 150:
            return replace(self)

        if total <= 400:
            tier_max, tier_target, tier_messages = 90, 30, DEFAULT_MAX_MESSAGES
        elif total <= 800:
            tier_max, tier_target, tier_messages = 120, 45, 8
        else:
            tier_max, tier_target, tier_messages = 160, 60, 10

        return replace(
            self,
            max_chars=tier_max,
            target_chars=(tier_target
                          if self.target_chars == DEFAULT_TARGET_CHARS
                          else self.target_chars),
            max_messages=(tier_messages
                          if self.max_messages == DEFAULT_MAX_MESSAGES
                          else self.max_messages),
            merge_max_chars=(tier_max
                             if self.merge_max_chars == DEFAULT_MERGE_MAX_CHARS
                             else self.merge_max_chars),
        )

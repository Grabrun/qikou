# -*- coding: utf-8 -*-
"""切分配置。"""

import random


class Config:
    def __init__(self):
        self.max_chars = 60
        self.target_chars = 20
        self.min_chars = 4
        self.max_messages = 6
        self.atomic_merge_prefix = 20
        self.merge_max_chars = 60

        self.base_ms = 500
        self.per_char_ms = 30
        self.jitter_ms = 200
        self.min_ms = 300
        self.max_ms = 1800

    def scale_for_length(self, total):
        if total <= 150:
            pass
        elif total <= 400:
            self.max_chars = max(self.max_chars, 90)
            self.target_chars = max(self.target_chars, 30)
        elif total <= 800:
            self.max_chars = max(self.max_chars, 120)
            self.target_chars = max(self.target_chars, 45)
            self.max_messages = max(self.max_messages, 8)
        else:
            self.max_chars = max(self.max_chars, 160)
            self.target_chars = max(self.target_chars, 60)
            self.max_messages = max(self.max_messages, 10)

    def delay_for(self, msg):
        d = self.base_ms + len(msg) * self.per_char_ms \
            + random.randint(0, self.jitter_ms)
        d = max(self.min_ms, min(d, self.max_ms))
        return d / 1000.0

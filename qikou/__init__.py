# -*- coding: utf-8 -*-
"""气口 —— 让 AI 回复会呼吸。"""

from .config import Config
from .kaomoji import load_kaomojis, kaomoji_count
from .splitter import split_reply

__version__ = '2.0.0'
__all__ = ['Config', 'split_reply', 'load_kaomojis', 'kaomoji_count']

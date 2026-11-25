# -*- coding: utf-8 -*-
"""v3.0 候选切点的行为契约。"""

from __future__ import annotations

import pytest

from qikou import Config
from qikou.candidates import (
    CANDIDATE_CAP_PER_100,
    candidate_positions,
    prune_candidates,
    visible_prefix,
)
from qikou.protect import protect_special


def _cands(text: str, max_chars: int = 60):
    protected, blocks = protect_special(text)
    return candidate_positions(protected, blocks, max_chars), protected, blocks


def test_punctuation_candidates_are_after_the_separator():
    cands, text, _ = _cands("第一句。第二句！第三句？")
    assert any(text[p - 1:p] == "。" for p in cands)
    assert any(text[p - 1:p] == "！" for p in cands)


def test_cjk_ascii_boundary_candidate():
    cands, text, _ = _cands("今天meeting讨论API设计。")
    assert text.index("m") in cands
    assert text.index("m") + len("meeting") in cands


def test_placeholder_inner_positions_are_removed():
    text = "看这个：https://example.com/a/b 说明。"
    protected, blocks = protect_special(text)
    cands = candidate_positions(protected, blocks, 60)
    start = protected.index("\ue000")
    end = protected.index("\ue001", start) + 1
    assert start in cands and end in cands
    assert all(not (start < p < end) for p in cands)


def test_zero_candidates_for_short_prose():
    cands, _, _ = _cands("你好")
    assert cands == []


def test_density_cap_12_per_100():
    text = "字" * 1000
    cands, protected, blocks = _cands(text, max_chars=20)
    total = visible_prefix(protected, blocks)[-1]
    assert len(cands) <= 12 * total // 100 + 3


def test_prune_keeps_coverage_skeleton():
    text = "字" * 500
    cands, protected, blocks = _cands(text, max_chars=60)
    pruned = prune_candidates(protected, blocks, cands, 500, 60, 12)
    assert pruned
    # 每个 60 字窗口至少有一个保留候选
    vis = visible_prefix(protected, blocks)
    start = 0
    while start + 60 < 500:
        end = min(500, start + 60)
        assert any(start < vis[p] <= end for p in pruned)
        start = end


def test_prune_respects_density_limit():
    text = "，".join(["字"] * 200)
    cands, protected, blocks = _cands(text, max_chars=60)
    pruned = prune_candidates(protected, blocks, cands, 200, 60, 12)
    assert len(pruned) <= 24 + 3


def test_config_validation_for_v3_fields():
    assert Config().use_dp is False
    assert Config().dp_cut_cost == pytest.approx(1.20)
    assert Config().candidate_cap_per_100 == CANDIDATE_CAP_PER_100
    with pytest.raises(ValueError):
        Config(candidate_cap_per_100=0)
    with pytest.raises(ValueError):
        Config(dp_cut_cost=0)
    with pytest.raises(TypeError):
        Config(use_dp="yes")          # type: ignore[arg-type]

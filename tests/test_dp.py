# -*- coding: utf-8 -*-
"""v3.0 段级 DP 的结构不变量与确定性。"""

from __future__ import annotations

import hashlib
import time

from qikou import Config, split, split_with_report
from qikou.candidates import candidate_positions, prune_candidates
from qikou.dp import dp_cut
from qikou.protect import protect_special, visible_len
from qikou.splitter import _State


def _parts(text: str, config: Config):
    return split_with_report(text, config=config)


def test_dp_cut_cost_prevents_cut_every_sentence():
    text = ("这是第%d句，内容还行，再补一点字数。" % 1) * 44
    cheap = _parts(text, Config(max_chars=120, use_dp=True,
                                dp_cut_cost=0.01))
    normal = _parts(text, Config(max_chars=120, use_dp=True,
                                 dp_cut_cost=1.20))
    assert len(cheap.messages) > len(normal.messages)
    assert len(normal.messages) <= 8


def test_atomic_oversize_is_reported_not_broken():
    url = "https://example.com/" + "very-long-path/" * 3
    result = _parts(url, Config(max_chars=30, use_dp=True))
    assert result.fallback_count == 1
    assert result.over_max_chars == 1
    assert result.messages == [url]


def test_structural_fallback_is_marked_and_repaired():
    text = "**" + "很长的一段话。" * 10 + "**"
    result = _parts(text, Config(max_chars=40, use_dp=True))
    assert result.fallback_count >= 1
    assert result.over_max_chars == 1
    assert result.messages


def test_dp_is_deterministic():
    text = "".join("第%d句内容，补充一些字数让它长一点。" % i
                   for i in range(1, 31))
    cfg = Config(max_chars=80, use_dp=True)
    first = split(text, config=cfg)
    second = split(text, config=cfg)
    assert first == second
    digest = hashlib.sha256("\x1e".join(first).encode()).hexdigest()
    assert digest == hashlib.sha256("\x1e".join(second).encode()).hexdigest()


def test_no_short_message_except_single_text():
    text = "".join("第%d句内容，补充一些字数让它长一点。" % i
                   for i in range(1, 31))
    result = _parts(text, Config(max_chars=60, use_dp=True))
    assert len(result.messages) > 1
    assert all(len(m) >= 4 for m in result.messages)


def test_report_counts_match_independent_check():
    text = "\n\n".join("第%d段内容，写得不算长但也要占一些字数。" % i
                       for i in range(1, 21))
    cfg = Config(max_chars=60, max_messages=2, use_dp=True)
    result = _parts(text, cfg)
    assert result.over_max_chars == sum(
        1 for m in result.messages if len(m) > cfg.max_chars)
    assert result.over_max_messages == max(
        0, len(result.messages) - cfg.max_messages)


def test_long_text_is_chunked_and_bounded():
    text = ("这是第%d句，内容还行，再补一点字数让句子长一些。" % 1) * 420
    cfg = Config(max_chars=160, use_dp=True)
    result = _parts(text, cfg)
    assert result.over_max_chars == 0
    assert max(len(m) for m in result.messages) <= 160
    assert result.fallback_count == 0


def test_dp_cli_switch(tmp_path, capsys):
    from qikou.cli import main
    f = tmp_path / "in.txt"
    f.write_text("这是第1句，内容还行。" * 12, encoding="utf-8")
    assert main(["split", "--dp", str(f)]) == 0
    assert capsys.readouterr().out.strip()


def test_dp_cut_handles_no_candidates():
    text = "https://example.com/" + "x" * 40
    protected, blocks = protect_special(text)
    state = _State(protected, blocks)
    result = dp_cut(protected, state, Config(max_chars=30, use_dp=True), [])
    assert result.cuts == ()
    assert result.fallback is True


def test_candidate_pruning_does_not_drop_all_cut_points():
    text = ("这是第%d句，内容还行，再补一点字数。" % 1) * 44
    cfg = Config(max_chars=120, use_dp=True)
    protected, blocks = protect_special(text)
    cands = candidate_positions(protected, blocks, 120)
    pruned = prune_candidates(protected, blocks, cands,
                              visible_len(protected, blocks), 120, 12)
    assert pruned
    assert len(pruned) <= len(cands)


def test_dp_performance_budget_for_500_chars():
    text = ("这是第%d句，内容还行，再补一点字数让句子长一些。" % 1) * 18
    split_with_report(text, Config(max_chars=120, use_dp=True))
    start = time.perf_counter()
    split_with_report(text, Config(max_chars=120, use_dp=True))
    assert time.perf_counter() - start < 0.05


def test_content_is_not_lost_on_dp_path():
    text = ("好的，我来帮你规划。首先确定目标。\n\n"
            "- 官方文档\n- 练手项目\n\n加油！")
    out = "".join(split(text, config=Config(use_dp=True)))
    assert out.replace("\n", "") == text.replace("\n", "")
    assert all(out.count(ch) >= text.count(ch)
               for ch in set(text) if not ch.isspace())

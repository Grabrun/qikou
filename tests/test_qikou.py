# -*- coding: utf-8 -*-
"""qikou 的自动化测试。

跑法::

    pytest

`tests/test.txt` 是给人看的用例语料（只有输入、没有预期输出，靠
``qikou test`` 生成报告人工复核）；本文件是真正的断言测试，覆盖公开
API 的行为契约与曾经修过的缺陷。
"""

from __future__ import annotations

import dataclasses
import json
import os

import pytest

import qikou
from qikou import Config, kaomoji_count, load_kaomojis, split
from qikou.cli import main


# ============================================================
# 公开 API 契约
# ============================================================

def test_version():
    # 发布流程：改版本号时同步 pyproject 的动态版本、CHANGELOG 与本用例
    assert qikou.__version__ == "2.2.2"


def test_public_api_surface():
    assert set(qikou.__all__) == {"Config", "kaomoji_count", "load_kaomojis", "split"}


def test_split_returns_list_of_str():
    messages = split("你好。今天不错。")
    assert isinstance(messages, list)
    assert all(isinstance(m, str) for m in messages)


def test_removed_delay_feature_is_gone():
    """延迟功能已移除，不应留下任何入口。"""
    assert not hasattr(Config(), "delay_for")
    assert not hasattr(Config(), "base_ms")
    assert not hasattr(qikou, "split_with_delays")
    assert not hasattr(qikou, "Message")


# ============================================================
# 切分行为
# ============================================================

def test_empty_and_whitespace_return_empty():
    assert split("") == []
    assert split("   ") == []
    assert split("\n\n\t ") == []


def test_basic_chinese_sentences():
    assert split("第一句话写得足够长。第二句话也写得足够长。第三句同样足够长。") == [
        "第一句话写得足够长。", "第二句话也写得足够长。", "第三句同样足够长。",
    ]


def test_short_first_sentence_merges_into_the_next():
    """首句短于 min_chars 时按设计并入下一句，而不是单独成条。"""
    assert split("你好。今天不错。再见。") == ["你好。今天不错。", "再见。"]


def test_english_sentences():
    assert split("Hello. How are you?") == ["Hello.", "How are you?"]


def test_mixed_chinese_english():
    messages = split("今天 meeting 讨论 API 设计。明天继续。")
    assert len(messages) == 2
    assert messages[1] == "明天继续。"


def test_english_abbreviation_not_split():
    """Mr. / i.e. 之后不应断句。"""
    assert split("Mr. Smith went home. He was tired.") == [
        "Mr. Smith went home.", "He was tired.",
    ]


def test_code_block_kept_whole():
    text = "看这个：\n```python\nprint('a. b')\n```\n就这样。"
    messages = split(text)
    assert any("```python" in m and "print" in m for m in messages)
    assert "就这样。" in messages


def test_url_not_broken():
    url = "https://example.com/a.b/c?d=e"
    messages = split("参见 %s 说明。" % url)
    assert any(url in m for m in messages)


def test_list_items_stand_alone():
    messages = split("- 苹果\n- 香蕉\n- 橘子")
    assert messages == ["- 苹果", "- 香蕉", "- 橘子"]


def test_heading_and_hr_stand_alone():
    messages = split("第一段\n---\n# 标题\n第二段")
    assert "---" in messages
    assert "# 标题" in messages


def test_kaomoji_stays_with_its_sentence():
    messages = split("今天真开心 (≧ω≦) 明天见。")
    assert len(messages) == 1
    assert "(≧ω≦)" in messages[0]


def test_content_preserved():
    """切分不得丢字。"""
    text = ("好的，我来帮你规划。首先你要确定目标，比如三个月内写个小工具。"
            "然后每天练 30 分钟。\n\n- 官方文档\n- 一个练手项目\n\n加油！")
    joined = "".join(split(text))
    assert joined.replace("\n", "") == text.replace("\n", "")


# ---- 三个曾经修过的缺陷（P0-1）：未配对标记不得否决其后的切点 ----

def test_unclosed_bracket_does_not_block_splitting():
    text = "（参见图 1 第一句。第二句。第三句。第四句。"
    assert len(split(text)) >= 4


def test_stray_asterisk_does_not_block_splitting():
    text = "计算 3 * 4 得出结果。然后继续下一步。最后做一次复查。"
    assert len(split(text)) == 3


def test_unclosed_quote_does_not_block_splitting():
    text = "他说“第一句。第二句。第三句。"
    assert len(split(text)) >= 3


def test_balanced_brackets_still_protected():
    """修 P0-1 不能把合法括注的保护一起弄丢。"""
    assert split("他（今天很忙。明天也是。）然后走了。") == [
        "他（今天很忙。明天也是。）然后走了。",
    ]


# ============================================================
# Config
# ============================================================

def test_config_defaults():
    cfg = Config()
    assert (cfg.max_chars, cfg.target_chars, cfg.min_chars) == (60, 20, 4)
    assert cfg.max_messages == 6


def test_config_is_dataclass():
    assert Config() == Config()
    assert "max_chars=60" in repr(Config())
    assert dataclasses.replace(Config(), max_chars=200).max_chars == 200


def test_split_does_not_mutate_callers_config():
    cfg = Config(max_chars=80)
    before = dataclasses.asdict(cfg)
    split("这是一段很长的文本。" * 60, config=cfg)
    assert dataclasses.asdict(cfg) == before


@pytest.mark.parametrize("total,expected_max,expected_messages", [
    (150, 60, 6),
    (400, 90, 6),
    (800, 120, 8),
    (2000, 160, 10),
])
def test_scaled_for_length_tiers(total, expected_max, expected_messages):
    scaled = Config().scaled_for_length(total)
    assert scaled.max_chars == expected_max
    assert scaled.max_messages == expected_messages
    # 合并上限必须同步放大，否则长文本的条数上限永远够不到
    assert scaled.merge_max_chars == expected_max


def test_scaled_for_length_does_not_mutate():
    cfg = Config()
    cfg.scaled_for_length(2000)
    assert cfg.max_chars == 60


def test_max_messages_is_reachable_for_long_prose():
    text = "".join("第%d句内容，用来撑长度。" % i for i in range(1, 41))
    config = Config()
    assert len(split(text, config=config)) <= 10


# ============================================================
# 颜文字语料
# ============================================================

def test_corpus_loads():
    assert load_kaomojis() > 50000
    assert kaomoji_count() > 50000


def test_load_kaomojis_is_silent(capsys):
    """库不该往 stdout 写东西。"""
    load_kaomojis()
    assert capsys.readouterr().out == ""


def test_missing_corpus_degrades_without_raising(tmp_path):
    n = load_kaomojis(str(tmp_path / "nope.txt"))
    assert n == 0
    assert kaomoji_count() == 0
    try:
        # 语料缺失时切分仍应可用，只是不再识别颜文字
        assert "".join(split("你好。再见。")) == "你好。再见。"
    finally:
        load_kaomojis()          # 恢复，避免污染后续测试


def test_load_custom_corpus(tmp_path):
    p = tmp_path / "my.txt"
    p.write_text("(^_^)\n(T_T)\n", encoding="utf-8")
    try:
        assert load_kaomojis(str(p)) == 2
    finally:
        load_kaomojis()


# ============================================================
# 命令行
# ============================================================

def test_cli_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert qikou.__version__ in capsys.readouterr().out


def test_cli_help(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for cmd in ("split", "test", "menu"):
        assert cmd in out


def test_cli_no_subcommand_prints_help(capsys):
    assert main([]) == 0
    assert "split" in capsys.readouterr().out


def test_cli_unknown_subcommand_exits_2():
    with pytest.raises(SystemExit) as exc:
        main(["splt"])
    assert exc.value.code == 2


def test_cli_unknown_option_exits_2():
    with pytest.raises(SystemExit) as exc:
        main(["--tst"])
    assert exc.value.code == 2


def test_cli_split_missing_file_returns_1(capsys):
    assert main(["split", "definitely_missing_file.txt"]) == 1
    assert "找不到文件" in capsys.readouterr().err


def test_cli_split_file_prints_messages(tmp_path, capsys):
    f = tmp_path / "in.txt"
    f.write_text("你好。今天不错。再见。", encoding="utf-8")
    assert main(["split", str(f)]) == 0
    out = capsys.readouterr().out
    assert "你好。" in out and "再见。" in out
    # 非 TTY 时只输出正文，不带装饰
    assert "切分结果" not in out


def test_cli_split_json(tmp_path, capsys):
    f = tmp_path / "in.txt"
    f.write_text("你好。再见。", encoding="utf-8")
    assert main(["split", "--json", str(f)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == ["你好。再见。"]


def test_cli_split_respects_max_chars(tmp_path, capsys):
    f = tmp_path / "in.txt"
    f.write_text("你好。今天不错。再见。", encoding="utf-8")
    assert main(["split", "-c", "6", str(f)]) == 0
    lines = [ln for ln in capsys.readouterr().out.splitlines() if ln]
    assert lines == ["你好。", "今天不错。", "再见。"]


def test_cli_test_missing_casefile_returns_1(capsys):
    assert main(["test", "definitely_missing_cases.txt"]) == 1


# ============================================================
# 终端的编码健壮性
# ============================================================

def test_setup_streams_is_safe():
    from qikou.cli import _setup_streams
    _setup_streams()          # 不该抛异常，也不该改变正常流的行为
    assert True


# ============================================================
# 规则与打分系统审计（2026-10）发现的缺陷
# ============================================================

def test_kaomoji_immediately_before_url_does_not_crash():
    """颜文字紧贴 URL/代码块曾抛 TypeError。

    根因：kaomoji trie 用字符 "\\x00" 当终止标记，而 \\x00 正是
    protect_special 的占位符分隔符——node.get("\\x00") 会取到终止标记
    True，下一轮 `_END in True` 直接崩。
    """
    assert split("你好。 (T_T)https://a.com/x") == ["你好。 (T_T)", "https://a.com/x"]
    assert split("你好。 (T_T)```code```") == ["你好。 (T_T)", "```code```"]
    assert split("太好了！ (*´ω`*)https://a.com/x") == [
        "太好了！ (*´ω`*)", "https://a.com/x"]


def test_url_immediately_before_code_block_keeps_both():
    """URL 紧贴代码块时，URL 匹配曾一口吞掉占位符。

    后果是代码块整段消失、输出里留下字面的 \\x00N\\x00。
    """
    text = "https://example.com/a```code```"
    assert "".join(split(text)) == text
    assert "\x00" not in "".join(split(text))


def test_protect_restore_roundtrip():
    """保护/还原必须无损，包括 URL 与代码块相邻这种边界。"""
    from qikou.protect import protect_special, restore_special
    for text in ("普通文本。",
                 "https://example.com/a```code```",
                 "```py\ncode```",
                 "看 https://a.b/c 和 `x`",
                 "a```b```c https://d.e/f"):
        prot, blocks = protect_special(text)
        assert restore_special(prot, blocks) == text


def test_literal_nul_in_input_does_not_crash():
    """输入自带 \\x00N\\x00（越界占位符）曾抛 IndexError。

    只要求不崩溃；往返无损不在承诺范围内（见 protect_special 的已知限制）。
    """
    assert split("https://a.com/x \x009\x00")
    assert split("\x000\x00")


def test_no_character_loss_on_adversarial_input():
    """乱码输入不得丢字（只允许补全未闭合标记）。"""
    from collections import Counter
    markers = set('*_"’”’「」』『')
    samples = [
        "(]`~Ac([chttps://a.b/ca**(、**\n}2[ba；：。，)”\t～b2…「",
        '`[；bhttps://a.b/c～`“(T_T)https://a.b/c”_\n#**）C}',
        "```\n" + "x。" * 40 + "\n```",
        "**" + "很长。" * 50 + "**",
    ]
    for text in samples:
        out = "".join(split(text))
        ci, co = Counter(text), Counter(out)
        for ch, n in ci.items():
            if not ch.isspace():
                assert co.get(ch, 0) >= n, (
                    "%r 中的 %r 从 %d 个变成 %d 个" % (text[:30], ch, n, co.get(ch, 0)))
        added = {c: co.get(c, 0) - ci.get(c, 0) for c in set(co) | set(ci)
                 if co.get(c, 0) > ci.get(c, 0)}
        illegal = {c: v for c, v in added.items()
                   if c not in markers and not c.isspace()}
        assert not illegal, "凭空多出 %r" % (illegal,)


# ============================================================
# 2026-11 深度审计（QK-01…QK-17）的回归用例
#
# 每一条对应审计报告里的一个编号；改动相关代码时先看这里。
# ============================================================

def _long_body(times=44):
    """约 480 字的单段落中文回复。"""
    return ("这是第%d句，内容还行，再补一点字数。" % 1) * times


def test_explicit_max_chars_is_respected():
    """QK-01：显式 max_chars 不得被长度分层悄悄放大。"""
    text = _long_body()
    assert len(text) > 400
    for mc in (30, 45, 60):
        ms = split(text, config=Config(max_chars=mc))
        longest = max(len(m) for m in ms)
        assert longest <= mc + 6, (mc, longest)


def test_default_config_still_scales_for_long_text():
    """QK-01 的修复不能把"默认值自动放宽"一起弄丢。"""
    text = _long_body()
    ms = split(text)
    assert max(len(m) for m in ms) > 60


def test_scaled_for_length_only_enlarges_defaults():
    cfg = Config(max_messages=3)
    scaled = cfg.scaled_for_length(2000)
    assert scaled.max_chars == 160      # 默认值，照常放大
    assert scaled.max_messages == 3     # 显式值，不被放大
    assert Config(max_chars=30).scaled_for_length(2000).max_chars == 30


def test_cli_max_chars_applies_to_long_text(tmp_path, capsys):
    f = tmp_path / "long.txt"
    f.write_text(_long_body(), encoding="utf-8")
    assert main(["split", "-c", "30", str(f)]) == 0
    lines = [ln for ln in capsys.readouterr().out.splitlines() if ln]
    assert lines
    assert max(len(ln) for ln in lines) <= 36


def test_list_marker_stays_with_content():
    """QK-05：列表标记不能单独成条。"""
    for text, prefix in (("- " + "很长" * 80, "- "),
                         ("1. " + "步骤说明" * 60, "1. ")):
        ms = split(text, config=Config(max_chars=40))
        assert ms[0].startswith(prefix)
        assert len(ms[0]) > len(prefix) + 2


def test_many_paragraphs_do_not_defeat_message_cap():
    """QK-04：多段落文本的条数上限不再随段落数线性失效。"""
    text = "\n\n".join("第%d段内容，写得不算长但也要占一些字数。" % i
                       for i in range(50))
    assert len(split(text)) <= 10


def test_placeholder_sentinels_roundtrip():
    """QK-06：输入自带的占位符形状 / 私有区字符不得被误替换。"""
    from qikou.protect import protect_special, restore_special
    samples = [
        "```code``` 以及 \x000\x00 字面",
        "https://a.com/x \x009\x00",
        "\ue0007\ue001 与 \ue002",
    ]
    for text in samples:
        assert restore_special(*protect_special(text)) == text
        assert "".join(split(text)) == text


def test_overflow_callback_reports_oversize():
    """QK-09：无法再切的超长消息要有可见信号。"""
    seen = []
    text = "**" + "很长的一段话" * 200 + "**"
    split(text, config=Config(max_chars=60),
          on_overflow=lambda msg, cap: seen.append((msg, cap)))
    assert seen
    assert all(cap == 60 for _, cap in seen)
    assert all(len(msg) > 60 for msg, _ in seen)


def test_split_without_callback_stays_silent():
    text = "**" + "很长的一段话" * 200 + "**"
    assert len(split(text, config=Config(max_chars=60))) == 1


def test_ascii_double_quote_is_protected():
    """QK-15：半角双引号与全角引号同等保护；半角单引号不配对。"""
    text = 'He said "one. two. three." Then left.'
    assert split(text) == [text]
    assert split("他说“第一句。第二句。”然后走了。") == ["他说“第一句。第二句。”然后走了。"]


def test_whitespace_contract():
    """QK-10：段内空白保留，消息边界的空白丢弃（已在文档写明）。"""
    assert split("甲\t乙。") == ["甲\t乙。"]
    assert split("第一句话写得足够长。\t第二句话也写得足够长。") == [
        "第一句话写得足够长。", "第二句话也写得足够长。"]


def test_config_validation():
    """QK-13：非法配置给出明确错误，而不是产出无意义的结果。"""
    with pytest.raises(ValueError):
        Config(max_chars=0)
    with pytest.raises(ValueError):
        Config(max_chars=-5)
    with pytest.raises(ValueError):
        Config(merge_max_chars=0)
    with pytest.raises(TypeError):
        Config(max_chars="60")          # type: ignore[arg-type]
    assert Config(max_messages=0).max_messages == 0


def test_repo_root_resolution_is_explicit(monkeypatch, tmp_path):
    """QK-12：源码仓库的判定用环境变量/真实用例文件，而不是猜目录。"""
    from qikou import cli
    monkeypatch.setenv("QIKOU_REPO", str(tmp_path))
    assert cli._resolve_repo_root() == str(tmp_path)
    monkeypatch.setenv("QIKOU_REPO", str(tmp_path / "missing"))
    assert cli._resolve_repo_root() is None


def test_performance_budget_for_long_text():
    """QK-02：长文本不得再平方退化（阈值放宽到 CI 也能过）。"""
    import time
    text = ("这是第%d句，内容还行，再补一点字数让句子长一些。" % 1) * 700
    split(text)                          # 预热，排除语料加载
    t0 = time.perf_counter()
    split(text)
    assert time.perf_counter() - t0 < 1.2      # 约 20k 字


def test_performance_budget_for_unclosed_fence():
    """QK-03：未闭合围栏输入不得拖住进程。"""
    import time
    fence = "`" * 40000
    split(fence)
    t0 = time.perf_counter()
    assert split(fence)
    assert time.perf_counter() - t0 < 2.5


def test_case_corpus_matches_golden():
    """205 条用例的输出金标。预期改动请跑 `python tests/golden.py --write`。"""
    import sys as _sys
    _sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import golden
    assert golden.compute() == golden.read_baseline(), (
        "用例输出变了。确认差异符合预期后运行 python tests/golden.py --write 更新基线。")

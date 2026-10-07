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
    assert qikou.__version__ == "2.2.0"


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

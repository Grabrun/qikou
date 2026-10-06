# Cadence (气口)

**English** | [中文](README.md)

> Let AI replies breathe.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**气口 (qìkǒu)** is a term from Chinese opera and storytelling. It is the breath point — the spot where a performer pauses mid-passage to take a new breath. A good qikou makes the words land naturally, with rhythm, never running out of air. A bad one leaves the audience behind and gasping. The English name, **Cadence**, comes from music: the close of a phrase, the rhythm of speech.

That is exactly what this project does for AI replies: **find the breath points in a long reply** — split one long response into several short messages so they read like a real person sending them one after another.

---

## Table of Contents

- [Why This Exists](#why-this-exists)
- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Using It as a Library](#using-it-as-a-library)
- [Configuration](#configuration)
- [Test Case Format](#test-case-format)
- [Project Structure](#project-structure)
- [Design Tradeoffs](#design-tradeoffs)
- [Version History](#version-history)
- [Roadmap](#roadmap)
- [Naming](#naming)
- [License](#license)

---

## Why This Exists

Agent replies tend to be long. Sent as-is to a social platform, they read like an essay. On WeChat, QQ, Discord, or Telegram, real people send messages like this:

- one idea per message, 10–40 characters
- a break after punctuation, with tone particles standing on their own
- lists, code blocks, and URLs kept intact
- a human-like delay instead of an instant wall of text

Chopping by character count breaks Markdown, URLs, and code blocks, and reads like a machine. Cadence does **semantics-aware soft splitting**.

---

## Features

### Core

- **Chinese/English mixed sentence splitting**: breaks after `。！？!?…`, and after `. ` when followed by whitespace or CJK
- **English abbreviation protection**: 40+ entries such as `Mr.` `Dr.` `e.g.` `i.e.` `U.S.` `U.S.A.` are never mis-split
- **Conjunction protection**: Chinese correlatives (`虽然…但是`, `因为…所以`) and English connectives (`because`, `although`, `however`)
- **Tilde as a soft sentence end**: 8 variants (`~` `～` `〜` and more), only after a real character; the operator `~=`, the range `18~25`, and the sub/superscript `H~2~O` are recognised and never treated as ends

### Structure Awareness

- **Markdown**: never splits inside `**` `__` `~~` `` ` `` `*` `_`
- **Quotes and brackets**: never splits inside `“”` `「」` `『』` `()` `（）`
- **Code blocks**: triple-backtick and `~~~` fences are protected as a whole
- **URLs**: `http(s)://` is protected as a whole, and a short prefix is merged automatically
- **Lists**: unordered, ordered, task, and nested lists become their own messages
- **Tables**: a Markdown table stays one message
- **Headings**: `#` through `######` stand alone
- **Horizontal rules**: `---` `***` `___` stand alone
- **HTML breaks**: `<br>` `<br/>` `<br />` count as cut points

### Kaomoji

- **55,000+ kaomoji** in a trie index, exact match
- kaomoji at the end, the start, or the middle of a sentence are attached to the right message
- multiple upstream corpora can be merged

### Post-processing

- **Unclosed Markdown**: `**` and `__` are paired up at the end
- **Unclosed quotes**: `“”` `「」` `『』` are paired up at the end
- **Half-width brackets are never auto-closed**: avoids misfiring inside kaomoji, formulas, and code

### Output

- **Human-like delay**: every message carries a suggested send delay (by length plus jitter)
- **Adaptive length**: long text relaxes the per-message cap so it does not shatter into pieces
- **Message-count control**: over the cap, the shortest adjacent pair is merged — but list items, headings, tables, and tilde endings are skipped

---

## Installation

**Requirements**: Python 3.8+. Zero third-party dependencies.

```bash
git clone https://github.com/Grabrun/qikou.git
cd qikou
```

---

## Quick Start

### Interactive menu

```bash
python -m qikou
```

```
====================================================
 气口 —— AI 回复分句器
====================================================
[信息] 已加载 <N> 个颜文字（Trie），耗时 <T> ms

请选择模式：
  [1] 手动输入
  [2] 自动测试（读取 test.txt）
  [q] 退出
```

The command-line interface is currently Chinese-only; the menu labels above are quoted verbatim from the program.

### Manual input

Choose `[1]`, paste your text, and finish with a line containing `EOF` or with Ctrl-D:

```
> 好的，我来帮你规划。首先你需要确定目标，比如你想在三个月内学会 Python。然后每天安排 30 分钟练习基础语法。接着做一个小项目，比如爬虫或自动化脚本。最后定期复习并调整计划。
  EOF

─── [1/5]  11 字 ───
好的，我来帮你规划。

─── [2/5]  27 字 ───
首先你需要确定目标，比如你想在三个月内学会 Python。

─── [3/5]  18 字 ───
然后每天安排 30 分钟练习基础语法。

─── [4/5]  21 字 ───
接着做一个小项目，比如爬虫或自动化脚本。

─── [5/5]  12 字 ───
最后定期复习并调整计划。

模拟发送时间轴：
  t= 0.00s  第 1 条（11 字，等待 0.93s）
  t= 0.93s  第 2 条（27 字，等待 1.40s）
  ...
```

The header of each block is `[index/total]  <character count> 字`; the timeline is `t=<elapsed>s  message <n> (<count> chars, waiting <delay>s)`.

### Automated test

```bash
python -m qikou --test
```

Reads `tests/test.txt`, runs every case, and writes the report to `tests/results/test_result_<timestamp>.txt`.

```
开始自动测试：.../tests/test.txt
----------------------------------------------------
  [  1/N] 001 中文句号后紧跟英文      →  2 条
  [  2/N] 002 中文问号后无空格       →  3 条
  ...
----------------------------------------------------
用时：<T> 秒
结果已保存到：
  .../tests/results/test_result_<时间戳>.txt
```

### Running a specific file

```bash
python -m qikou --test path/to/your_cases.txt
```

### Help

```bash
python -m qikou --help
```

---

## Using It as a Library

```python
from qikou import split_reply, load_kaomojis, Config

# 1. Load the kaomoji table (once, at program start)
load_kaomojis()

# 2. Split
text = "好的，我来帮你规划。首先你需要确定目标。然后每天练习。最后定期复习。"
msgs, cfg = split_reply(text)

# 3. Use the result
for i, m in enumerate(msgs, 1):
    delay = cfg.delay_for(m)
    print(f"[{i}] {m}  (waiting {delay:.2f}s)")
```

### Custom configuration

```python
from qikou import split_reply, Config

cfg = Config()
cfg.max_chars = 80       # hard cap per message
cfg.target_chars = 30    # ideal length
cfg.min_chars = 5        # below this, try to merge
cfg.max_messages = 8     # cap on the number of messages

msgs, cfg = split_reply(text, cfg=cfg)
```

### It also runs without the kaomoji table

```python
from qikou import split_reply

# Works without load_kaomojis(); kaomoji simply are not recognised.
msgs, cfg = split_reply("hello world. how are you?")
```

---

## Configuration

Every parameter of the `Config` class:

| Parameter | Default | Meaning |
|---|---|---|
| `max_chars` | 60 | Hard cap per message. Exceeding it triggers a split |
| `target_chars` | 20 | Ideal length. The preferred region for a cut |
| `min_chars` | 4 | Below this, try to merge with a neighbour |
| `max_messages` | 6 | Soft cap on the message count. Over it, the shortest adjacent pair is merged |
| `atomic_merge_prefix` | 20 | Threshold for merging a short prefix with a long atomic fragment |
| `merge_max_chars` | 60 | Cap after a merge (not scaled up) |
| `base_ms` | 500 | Base value of the human-like delay |
| `per_char_ms` | 30 | Delay added per character |
| `jitter_ms` | 200 | Random jitter |
| `min_ms` | 300 | Minimum delay |
| `max_ms` | 1800 | Maximum delay |

**Adaptive length**: `split_reply()` relaxes `max_chars` according to the total length:

| Total length | max_chars | target_chars | max_messages |
|---|---|---|---|
| ≤ 150 | 60 | 20 | 6 |
| ≤ 400 | 90 | 30 | 6 |
| ≤ 800 | 120 | 45 | 8 |
| > 800 | 160 | 60 | 10 |

To shift the overall feel (choppier or longer), change `max_chars` and `target_chars`.

Note that `split_reply()` scales the `Config` instance it is given, in place. Pass a copy if you need to reuse the same object across calls.

---

## Test Case Format

The format of `tests/test.txt`:

```
[CASE] 001 Chinese full stop
你好。今天不错。再见。

[CASE] 002 English period
Hello. How are you?

[CASE] 003 Tilde
好耶~ 就这么定了！
```

- every case starts with `[CASE] <number> <short description>`
- the body runs until the next `[CASE]` or the end of the file
- whitespace-only cases are kept (0 messages) for boundary testing

To add a case, just edit the file.

Cases hold **inputs only** — there are no expected outputs. `--test` is therefore a deterministic report generator rather than an assertion suite: it fails only if a case raises. Read the reports, or diff them, to catch behaviour changes.

---

## Project Structure

```
qikou/
├── qikou/                      # core package
│   ├── __init__.py             # public exports
│   ├── __main__.py             # python -m qikou entry point
│   ├── cli.py                  # CLI / menu / auto test
│   ├── config.py               # Config class
│   ├── patterns.py             # regexes and structural checks
│   ├── lexicon.py              # abbreviation list, conjunction list, base scores
│   ├── kaomoji.py              # kaomoji trie
│   ├── protect.py              # code block / URL placeholder protection
│   ├── postprocess.py          # closing unclosed markers
│   └── splitter.py             # core splitting logic
├── Kaomoji/
│   └── kaomojis.txt            # kaomoji corpus, 55,213 entries
├── tests/
│   ├── test.txt                # 120 test cases
│   └── results/                # generated reports (not tracked)
├── legacy/                     # archived single-file versions
│   ├── ChatSplit-v1.0.py
│   └── ChatSplit-v2.0.py
├── HANDOVER.md                 # handover notes (Chinese)
├── Prompt.txt                  # prompt used to generate the test cases (Chinese)
├── README.md                   # Chinese README
├── README_en-US.md             # this file
└── LICENSE                     # MIT
```

`Kaomoji/` additionally holds four upstream exports (`kaomojis-gboard.txt`, `kaomojis-googlejp.txt`, `kaomojis-msime.txt`, `kaomojis-ios.plist`, about 13.7 MB). No code reads them; they are kept on disk and excluded from version control.

### Module responsibilities

| Module | Responsibility |
|---|---|
| `patterns.py` | all regexes, character sets, and structural predicates |
| `lexicon.py` | abbreviation list, conjunction list, base punctuation scores |
| `config.py` | configuration parameters, adaptive length, human-like delay |
| `kaomoji.py` | loading and matching the kaomoji trie |
| `protect.py` | protecting and restoring code block / URL placeholders |
| `postprocess.py` | closing unclosed Markdown and quotes |
| `splitter.py` | sentence splitting, packing, scoring, cut search, main entry point |
| `cli.py` | argument parsing, manual input, automated test |

---

## Design Tradeoffs

Every decision in the splitter is a tradeoff between **semantic completeness** and **length tidiness**. The following are deliberate choices, not bugs:

| Scenario | Behaviour | Reason |
|---|---|---|
| Long run with no punctuation | kept whole, allowed to exceed the cap | an arbitrary hard cut would be meaningless |
| Over-long code block / table | stays one message | splitting it would break the structure |
| A sentence after `etc.` | not split | abbreviation ambiguity has no clean answer; stay conservative |
| Unclosed half-width bracket | not auto-closed | too risky inside kaomoji, formulas, and code |
| A single message slightly over `max_chars` | allowed | semantics first; better long than shattered |
| Very long text cut after a preposition | unsolved | the ceiling of the rule approach; v3.0 addresses it |
| Kaomoji next to a tilde | each becomes its own message | `~` is a soft sentence end and stands semantically alone |

---

## Version History

### v2.0 (current)

**Cadence**. Rules plus scoring.

- split into the `qikou` package
- modularised: patterns / lexicon / config / kaomoji / protect / postprocess / splitter / cli
- 120 test cases covering a broad range of edge cases, all running without error
- command: `python -m qikou`
- `ChatSplit-v1.0.py` / `ChatSplit-v2.0.py` archived under `legacy/`

### v1.0

**ChatSplit**. Single-file rule-based version.

- basic sentence splitting: `。！？!?…`
- 8 tilde variants as soft sentence ends
- kaomoji trie
- code block and URL protection
- list, table, and quote detection
- unclosed Markdown / quote completion
- human-like delay timeline
- interactive menu plus automated test

---

## Roadmap

### v3.0 Prosody (planned)

**Model-based splitting**. Binary classification of candidate cut points, with LightGBM.

- data: LLM synthesis + rule-based weak supervision + user feedback
- features: local characters + position and length + semantic lexicon + structural state + rule scores
- model: LightGBM (40 features, ~5 minutes to train, under 10 ms to infer)
- fusion: rules generate candidates, the model decides the cuts, greedy packing, post-processing to finish
- hardware: **an ordinary 4-core CPU and 8 GB of RAM is enough** — no GPU needed

It addresses the ceiling of the rule approach:

- semantic boundary ≠ punctuation boundary (e.g. `我觉得吧，这个方案，可能还需要再想想`)
- long-text cut optimisation (e.g. after `to` rather than after `and`)
- tone versus information (e.g. is `好吧。那就这样。` one message or two?)

### v4.0 Breathing (long term)

**Small Transformer**. Reconsider once there are more than 50,000 samples. Training needs a GPU; inference runs on CPU. Learns candidate generation, cut selection, and packing end to end.

---

## Naming

**气口 (qìkǒu)** — a term from Chinese opera and storytelling: the spot where a performer breathes and pauses. A good qikou makes a passage land naturally, with rhythm, never out of air; a bad one leaves the listener gasping.

The English name is **Cadence** (the close of a musical phrase; the rhythm of speech), and the package name is `qikou`.

Version names:

| Version | Name | Kernel |
|---|---|---|
| v1 | 吐字 (Articulation) | hard rules |
| v2 | 气口 (Cadence) | rules + scoring |
| v3 | 韵律 (Prosody) | LightGBM |
| v4 | 呼吸 (Breathing) | Transformer |

Each version is another step towards learning how to breathe.

---

## License

[MIT](LICENSE) © 2026 Grabrun

### Note on the kaomoji data

The kaomoji corpus in `Kaomoji/kaomojis.txt` comes from exported data of publicly available input methods.

Each kaomoji is a combination of symbols and belongs to the public domain as a form of expression; it is not a copyrightable original work. The collection, merging, and de-duplication of the corpus was done by this project.

If an upstream data provider objects to the redistribution of the corpus, please reach out through a GitHub Issue and we will adjust promptly.

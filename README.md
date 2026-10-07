# 气口 (Cadence)

**中文** | [English](README_en-US.md)

> 让 AI 回复会呼吸。

[![PyPI](https://img.shields.io/pypi/v/qikou.svg)](https://pypi.org/project/qikou/)
[![Python](https://img.shields.io/pypi/pyversions/qikou.svg)](https://pypi.org/project/qikou/)
[![CI](https://github.com/Grabrun/qikou/actions/workflows/ci.yml/badge.svg)](https://github.com/Grabrun/qikou/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**气口** —— 戏曲和评书里的术语。演员说唱时换气、停顿的那个位置，叫"气口"。好的气口让一段话说得自然、有节奏、不憋气；坏的气口让听众跟不上、喘不过气。

这个项目在做的事，就是**给 AI 的回复找气口** —— 把一段长回复切成若干条短消息，让它们读起来像真人一条条发出来的聊天。

---

## 目录

- [为什么做这个](#为什么做这个)
- [特性](#特性)
- [安装](#安装)
- [快速上手](#快速上手)
- [作为库使用](#作为库使用)
- [配置](#配置)
- [测试用例格式](#测试用例格式)
- [项目结构](#项目结构)
- [设计权衡](#设计权衡)
- [版本历史](#版本历史)
- [路线图](#路线图)
- [命名](#命名)
- [许可证](#许可证)

---

## 为什么做这个

AI 生成的回复通常较长，直接发送到社交媒体上像"小作文"。在微信、QQ、Discord、Telegram 这类聊天平台里，真人发消息的习惯是：

- 一条一个意思单元，10–40 字
- 标点后断开，语气词独立
- 列表、代码块、URL 保持完整

直接按字符数硬切会破坏 Markdown、URL、代码块，读起来像机器。气口做的是**语义感知的软切分**。

---

## 特性

### 核心

- **中英混排断句**：`。！？!?…` 断句，`. ` 后接空白或 CJK 也断
- **英文缩写保护**：`Mr.` `Dr.` `e.g.` `i.e.` `U.S.` `U.S.A.` 等 40+ 条不错断
- **连词保护**：`虽然…但是` `因为…所以` 等中文关联词；`because` `although` `however` 等英文连词
- **波浪号软句末**：`~` `～` `〜` 等 8 种变体，前有实义字符才切；运算符 `~=`、数值范围 `18~25`、上下标 `H~2~O` 自动识别

### 结构感知

- **Markdown**：`**` `__` `~~` `` ` `` `*` `_` 内不切
- **引号括号**：`“”` `「」` `『』` `()` `（）` 内不切
- **代码块**：` ``` ` 和 `~~~` 围栏整体保护
- **URL**：`http(s)://` 整体保护，短前缀自动合并
- **列表**：无序、有序、任务列表、嵌套结构独立成条
- **表格**：Markdown 表格整体成条
- **标题**：`#` 到 `######` 独立成条
- **水平线**：`---` `***` `___` 独立成条
- **HTML 换行**：`<br>` `<br/>` `<br />` 当切点

### 颜文字

- **万级颜文字** Trie 索引，精确匹配
- 句末、句首、句中的颜文字正确归属
- 支持多来源语料合并

### 后处理

- **未闭合 Markdown**：`**` `__` 在末尾自动补配对
- **未闭合引号**：`“”` `「」` `『』` 自动补配对
- **半角括号不补**：避免颜文字、公式、代码误判

### 输出

- **自适应长度**：长文本自动放宽单条上限，避免碎成一地
- **条数控制**：超过上限时合并最短相邻对，但跳过列表 / 标题 / 表格 / 波浪号结尾

---

## 安装

**要求**：Python 3.9+。零第三方依赖。颜文字语料随包分发，装完即可用。

```bash
git clone https://github.com/Grabrun/qikou.git
cd qikou
pip install .
```

安装后提供 `qikou` 命令，也可继续用 `python -m qikou`。不安装也能在仓库根目录直接运行。

---

## 快速上手

### 命令行

```bash
qikou split 文件.txt          # 切分文件
echo "长文本" | qikou split    # 或从标准输入读
qikou test                    # 跑测试用例（源码仓库）
qikou menu                    # 交互菜单
qikou --version
qikou --help
```

`python -m qikou` 与 `qikou` 等价；不带子命令时显示帮助。

### 切分

输出到终端时带装饰：

```
$ qikou split 回复.txt

====================================================
 切分结果：5 条
 参数：max=60  target=20  min=4  max_messages=6
====================================================

─── [1/5]  11 字 ───
好的，我来帮你规划。

─── [2/5]  27 字 ───
首先你需要确定目标，比如你想在三个月内学会 Python。
...
```

被管道接走时自动只输出消息正文（空行分隔），方便 `grep` / `wc`：

```bash
$ echo "你好。今天不错。再见。" | qikou split
你好。今天不错。

再见。
```

需要机器可读就用 `--json`：

```bash
$ qikou split --json 回复.txt
[
  "好的，我来帮你规划。",
  "首先你需要确定目标，比如你想在三个月内学会 Python。"
]
```

| 选项 | 作用 |
|---|---|
| `-j`, `--json` | JSON 输出（字符串数组） |
| `-q`, `--quiet` | 只输出消息正文 |
| `-c N`, `--max-chars N` | 单条硬上限，调小更碎 |
| `-T N`, `--target-chars N` | 理想长度 |
| `-m N`, `--max-messages N` | 条数上限（软） |

### 交互菜单

```bash
qikou menu
```

```
====================================================
 气口 —— AI 回复分句器
====================================================
[信息] 已加载 55213 条颜文字

请选择模式：
  [1] 手动输入
  [2] 自动测试（读取 test.txt）
  [q] 退出
```

### 手动输入

选择 `[1]`，粘贴文本，单独一行输入 `EOF` 或按 `Ctrl-D` 结束：

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

----------------------------------------------------
合计 89 字（最长 27 字）
```

### 跑测试用例

```bash
qikou test                       # 跑 tests/test.txt
qikou test path/to/cases.txt     # 跑指定文件
```

会读取用例文件，跑全部用例，结果写入 `tests/results/test_result_<时间戳>.txt`。报告正文是确定性的——不含时间戳——同一份用例每次输出完全一致，需要时可以对两份报告直接做 diff。

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

### 帮助

```bash
qikou --help
```

---

## 作为库使用

```python
from qikou import split

text = "好的，我来帮你规划。首先你需要确定目标。然后每天练习。最后定期复习。"

for message in split(text):
    print(message)
```

`split()` 返回 `list[str]`。颜文字语料在首次调用时**自动加载**（约 0.1 秒），通常不需要手动处理。

### 自定义配置

```python
from qikou import Config, split

config = Config(
    max_chars=80,      # 单条硬上限
    target_chars=30,   # 理想长度
    min_chars=5,       # 低于此长度尝试合并
    max_messages=8,    # 条数上限（软）
)
messages = split(text, config=config)   # config 不会被修改
```

`Config` 是 dataclass，也可以用 `dataclasses.replace()` 派生新配置：

```python
import dataclasses
from qikou import Config

loose = dataclasses.replace(Config(), max_chars=200, target_chars=80)
```

### 预先加载或替换语料

```python
from qikou import load_kaomojis, kaomoji_count

load_kaomojis()                    # 预加载包内语料，返回条数
load_kaomojis("my-kaomojis.txt")   # 换成自己的语料
print(kaomoji_count())             # 当前已加载的条数
```

语料缺失只在日志里记一条 warning，切分继续，只是不再识别颜文字。

---

## 配置

`Config` 类的所有参数：

| 参数 | 默认 | 说明 |
|---|---|---|
| `max_chars` | 60 | 单条硬上限。超过触发切分 |
| `target_chars` | 20 | 理想长度。切点优选位置 |
| `min_chars` | 4 | 低于此长度尝试与相邻合并 |
| `max_messages` | 6 | 条数上限（**软**）。超限合并最短相邻对 |
| `atomic_merge_prefix` | 20 | 短前缀 + 超长原子片段合并的阈值 |
| `merge_max_chars` | 60 | 合并后单条上限（随档位放大到该档的 `max_chars`） |

**`max_messages` 是软上限**：超限时合并最短相邻对，但列表项、标题、表格、水平线、独立代码块 / URL、以波浪号结尾的条目都不参与合并——所以结构多的回复，最终条数可能超过这个值。纯文本回复则能压缩到上限以内：合并后的单条不超过 `merge_max_chars`，而它随档位一并放大（见下表）。

**长度自适应**：`split()` 会根据总长自动放宽单条上限与条数上限：

| 总长 | max_chars | target_chars | max_messages | merge_max_chars |
|---|---|---|---|---|
| ≤ 150 | 60 | 20 | 6 | 60 |
| ≤ 400 | 90 | 30 | 6 | 90 |
| ≤ 800 | 120 | 45 | 8 | 120 |
| > 800 | 160 | 60 | 10 | 160 |

想调节整体风格（更碎 / 更长），改 `max_chars` 和 `target_chars` 即可。

---

## 测试用例格式

`tests/test.txt` 的格式：

```
[CASE] 001 中文句号
你好。今天不错。再见。

[CASE] 002 英文句点
Hello. How are you?

[CASE] 003 波浪号
好耶~ 就这么定了！
```

- 每个用例以 `[CASE] 编号 简短描述` 开头
- 内容直到下一个 `[CASE]` 或文件末尾
- 纯空白用例会被保留（结果 0 条），用于测试边界

想加新用例，直接编辑文件即可。

---

## 项目结构

```
qikou/
├── qikou/                      # 核心包
│   ├── __init__.py             # 对外导出
│   ├── __main__.py             # python -m qikou 入口
│   ├── cli.py                  # 命令行 / 菜单
│   ├── config.py               # 配置类
│   ├── patterns.py             # 正则与结构判定
│   ├── lexicon.py              # 词表与标点分
│   ├── kaomoji.py              # 颜文字 Trie
│   ├── protect.py              # 特殊片段保护
│   ├── postprocess.py          # 后处理
│   ├── splitter.py             # 核心切分逻辑
│   ├── kaomojis.txt            # 颜文字语料（随 wheel 分发）
│   └── py.typed                # PEP 561 类型标记
├── tests/
│   ├── test.txt                # 测试用例
│   └── results/                # 测试报告（自动生成）
├── legacy/                     # 旧版存档
│   ├── ChatSplit-v1.0.py
│   └── ChatSplit-v2.0.py
├── pyproject.toml              # 打包配置（PEP 621）
├── MANIFEST.in                 # sdist 内容清单
├── README.md                   # 中文文档
└── README_en-US.md             # 英文文档
```

### 各模块职责

| 模块 | 职责 |
|---|---|
| `patterns.py` | 所有正则、字符集、结构判定函数 |
| `lexicon.py` | 缩写表、连词表、标点基础分 |
| `config.py` | 配置参数、长度自适应 |
| `kaomoji.py` | 颜文字 Trie 加载与匹配 |
| `protect.py` | 代码块 / URL 占位符保护与还原 |
| `postprocess.py` | 未闭合 Markdown 与引号的补全 |
| `splitter.py` | 分句、打包、打分、切点查找、主入口 |
| `cli.py` | 命令行解析、手动输入、自动测试 |

---

## 设计权衡

切分器的每一次决策都是**语义完整 vs 长度整齐**之间的取舍。以下几处是刻意的选择，不是 bug：

| 场景 | 行为 | 理由 |
|---|---|---|
| 无标点长串 | 整段保留，允许超限 | 硬切位置无意义，宁可长 |
| 超长代码块 / 表格 | 整体成条 | 分行破坏结构 |
| `etc.` 后接句 | 不切 | 缩写歧义无解，保守处理 |
| 未闭合半角括号 | 不自动补 | 颜文字 / 公式误补风险大 |
| 单条允许轻微超 `max_chars` | 语义优先 | 宁长不碎，聊天更自然 |
| 超长文本切在介词后 | 无解 | 规则方案天花板，v3.0 模型解决 |
| 颜文字 + 波浪号 | 各自成条 | `~` 是软句末，语义独立 |

---

## 版本历史

### v2.1（当前）

- 打包标准化：`pyproject.toml`（PEP 621）、`py.typed`（PEP 561）、控制台入口 `qikou`
- API 规范化：`split(text, config=None) -> list[str]`，`Config` 改为 dataclass
- 命令行改为子命令：`qikou split` / `qikou test` / `qikou menu`，支持标准输入与 `--json`
- 颜文字语料随包分发，首次调用自动加载
- **去掉拟人延迟**，专注切分质量

### v2.0

**气口**。规则 + 打分方案。

- 拆成 `qikou` 包结构
- 模块化：patterns / lexicon / config / kaomoji / protect / postprocess / splitter / cli
- 上百个测试用例，覆盖各类边界，全部通过
- 命令：`python -m qikou`
- 遗留 `ChatSplit-v1.0.py` / `ChatSplit-v2.0.py` 归档到 `legacy/`
- 拟人延迟时间轴（已在 v2.1 移除）

### v1.0

**ChatSplit**。单文件规则方案。

- 基础断句：`。！？!?…`
- 波浪号 8 种变体软句末
- 颜文字 Trie
- 代码块、URL 保护
- 列表、表格、引用识别
- 未闭合 Markdown / 引号补全
- 拟人延迟时间轴
- 交互菜单 + 自动测试

---

## 路线图

### v3.0 韵律（规划中）

**用模型自动分句**。候选点二分类 + LightGBM。

- 数据来源：LLM 合成 + 规则弱监督 + 真实日志（脱敏）+ 在线反馈
- 特征：局部字符 + 位置长度 + 语义词表 + 结构状态 + 候选上下文 + 规则分数（约 55–65 维）
- 模型：LightGBM。**训练用 LightGBM，推理用随包模型 + 纯 Python 评估器——运行时依旧零依赖**（已实测：纯 Python 推理与 LightGBM 输出逐样本一致）
- 打包：动态规划全局最优，替代局部贪心
- 硬件：**普通 4 核 CPU + 8GB 内存即可**，无需 GPU

解决规则方案的天花板问题：

- 语义边界 ≠ 标点边界（如 `我觉得吧，这个方案，可能还需要再想想`）
- 超长文本切点优化（如切在 `to` 还是 `and` 后）
- 语气 vs 信息（如 `好吧。那就这样。` 一句还是两句）

完整方案（含实测预研数据、数据与合规、特征清单、评估体系、分阶段落地、成本估算）见 [docs/v3-design.md](docs/v3-design.md)。

### v4.0 呼吸（远期）

**小型 Transformer**。数据量 > 5 万后再考虑。训练需 GPU，推理 CPU 可跑。端到端学习候选生成 + 切点 + 打包。

---

## 命名

**气口** —— 戏曲和评书里的术语。演员说唱时换气、停顿的那个位置。好的气口让一段话说得自然、有节奏、不憋气；坏的气口让听众跟不上、喘不过气。

英文名 **Cadence**（音乐里的终止式，说话里的韵律），包名 `qikou`。

版本命名：

| 版本 | 名字 | 内核 |
|---|---|---|
| v1 | 吐字 | 硬规则 |
| v2 | 气口 | 规则 + 打分 |
| v3 | 韵律 | LightGBM |
| v4 | 呼吸 | Transformer |

每个版本是一次"学会呼吸"的进阶。

---

## 许可证

[MIT](LICENSE) © 2026 Grabrun

### 颜文字数据来源说明

`qikou/kaomojis.txt` 中的颜文字语料来自 **https://kaomojis.jp**。

颜文字本身是符号组合，通常不构成受版权保护的原创作品；但各来源站点的使用条款不尽相同，本项目不对语料的再分发作法律保证。

若权利人认为语料的收录或再分发不妥，请通过 GitHub Issue 联系，我们会及时调整或移除。
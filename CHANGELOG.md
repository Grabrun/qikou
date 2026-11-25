# Changelog

本文件记录 qikou 的显著变更。格式参考
[Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循[语义化版本](https://semver.org/lang/zh-CN/)。

## [2.2.2] — 2026-11-25

2026-11 深度审计（17 项发现）的修复版本。205 条用例输出与 2.2.1 逐字节
相同；改动集中在对外契约与规模表现。

### Fixed

- 显式 `max_chars` 被长度分层静默放大：`Config(max_chars=30)` 在 484 字
  文本上实际按 120 切，CLI `-c 30` 同样失效。现在分层只放大仍处于默认
  值的字段，显式值原样保留（`auto_scale=False` 可完全固定）。
- 长文本耗时平方增长：分句判定与切点打分每个候选都重扫一遍前缀。
  改为每段预计算一次前缀状态（可见长度、括号深度、标记位置），
  118.9k 字 135.9 s → 187 ms，37.3k 字 20.2 s → 66 ms。
- 超长文本的切分循环固定 200 次上限，超出后把剩余整段并成一条。
  上限改为按可见长度估算。
- 列表项标记与内容被切开（出现只有 `-` 或 `1.` 的气泡）。切分时先从
  标记后取内容，再把标记粘回第一段。
- 多段落文本的条数上限失效（50 段 5226 字产 50 条）。段内压不到上限时
  改为按顺序跨段落装箱（空行连接），并写明物理下限
  `⌈可见字数 / 合并上限⌉`。
- 合并后单条上限可能超过 `max_chars`（`-c 30` 仍产出 60 字消息），
  现在取 `min(merge_max_chars, max_chars)`。
- 占位符与输入字符空间重叠：输入自带 `\x00N\x00` 时内容被复制、字面片段
  消失。占位符改用私有使用区（`U+E000`/`U+E001`），冲突字符用 `U+E002`
  转义，往返无损。
- 半角双引号不参与未闭合保护：`"a. b."` 会被切开。现在与全角引号同等
  处理；半角单引号因与英文撇号无法区分，明确不配对。
- `Config` 构造不校验：`max_chars=0` 产出 6 条 3 字消息。现在类型错误抛
  `TypeError`、越界抛 `ValueError`；`max_messages <= 0` 明确表示不限。
- `cli._REPO` 靠"兄弟目录有 tests"猜测运行环境。改为 `QIKOU_REPO` 环境
  变量或真实存在的 `tests/test.txt`；报告目录可用 `QIKOU_REPORT_DIR`。

### Added

- `split(text, config=None, on_overflow=None)`：超长不可切消息的回调通知。
- `tests/golden.py`：205 条用例输出的金标哈希，CI 用 `--check` 校验。
- 21 条新增回归用例，覆盖 QK-01…QK-17；测试总数 49 → 65。
- CI 增加 Windows 矩阵（3.9 / 3.13）。

### Changed

- 内部打包结构由 `List[Any]` 改为 `_Msg` dataclass；合并改为优先队列，
  避免 O(m²) 的空转。
- 文档补齐：`Config` 参数表、`max_messages` 物理下限、空白约定、
  设计权衡新增三行、版本历史补 2.2.0 / 2.2.1 / 2.2.2。

## [2.2.1] — 2026-10-08

### Fixed

- **`requires-python` 由 `>=3.8` 上调为 `>=3.9`。** 构建后端
  `setuptools>=77`（PEP 639 许可元数据所需）自身要求 Python ≥ 3.9，
  所以 3.8 上无法从源码构建——原声明是错的，CI 在 3.8 上的安装步骤也
  因此失败。运行时本身仍兼容 3.8（测试通过），但发布元数据必须按**构建
  能力**声明，故上调下限。CI 矩阵与 classifiers 同步去掉 3.8。

## [2.2.0] — 2026-10-08

首个公开发布版本。

### Added

- 自动化测试套件 `tests/test_qikou.py`（pytest，44 项），覆盖公开 API 契约、
  切分行为、`Config` 语义、语料加载与命令行。
- GitHub Actions CI：Python 3.9–3.13 跑测试、`mypy --strict` 类型检查、
  构建并校验 wheel 元数据。
- `CHANGELOG.md`、`SECURITY.md`、`CONTRIBUTING.md`。
- `pyproject.toml`：`[project.optional-dependencies]` 的 `dev` 组、
  `[tool.pytest.ini_options]`、`[tool.mypy]`（strict）。

### Changed

- **全量类型注解**：补齐 40 个内部函数的签名，`mypy --strict` 现在零报错。
- 语料的懒加载改为线程安全（可重入锁 + 双检锁）：多线程并发首次调用
  `split()` 只会真正加载一次。
- `Development Status` 分类器由 `5 - Production/Stable` 调整为 `4 - Beta`
  ——这是第一次公开发布，尚无外部使用者反馈。
- `splitter` / `protect` / `postprocess` 补上模块级 `__all__`，明确内部
  辅助函数不属于公开接口。

### Fixed

- 修复在非 UTF-8 输出环境（如 `PYTHONIOENCODING=ascii`）下打印中文与边框
  直接抛 `UnicodeEncodeError` 的问题；现在启动时会把 stdout/stderr 切到
  UTF-8，切不过则安全跳过。

## [2.1.0] — 2026-10-08

**未公开发布**，仅上传 TestPyPI 演练。

### Changed

- API 规范化：`split_reply()` → `split(text, config=None) -> list[str]`，
  配置不再兼作返回值通道；`Config` 改为 dataclass。
- 命令行改为子命令：`qikou split` / `qikou test` / `qikou menu`，
  支持标准输入、`--json`、`--version`，退出码规范为 0/1/2。
- 颜文字语料随 wheel 分发，首次调用自动加载（此前必须手动加载，
  忘记加载会静默降级）。

### Removed

- 拟人延迟功能：`Config` 的 `base_ms` / `per_char_ms` / `jitter_ms` /
  `min_ms` / `max_ms` 与 `delay_for()`、`split_with_delays()`、
  `Message` 类型全部移除。项目专注切分本身。

## [2.0.0] — 2026-10-07

**未公开发布**。

### Added

- 拆分为 `qikou` 包：`patterns` / `lexicon` / `config` / `kaomoji` /
  `protect` / `postprocess` / `splitter` / `cli`。
- `pyproject.toml`（PEP 621）、`MANIFEST.in`、`LICENSE`。
- 结构化测试用例 `tests/test.txt` 与确定性报告生成（`qikou test`）。

### Security

- 修复 `Kaomoji/` 目录大小写与实际代码不一致的问题：在大小写敏感的文件
  系统上会导致语料静默加载 0 条。现在语料位于 `qikou/kaomojis.txt`，
  且加载失败会明确报错。

[2.2.2]: https://github.com/Grabrun/qikou/releases/tag/v2.2.2
[2.2.1]: https://github.com/Grabrun/qikou/releases/tag/v2.2.1
[2.2.0]: https://github.com/Grabrun/qikou/releases/tag/v2.2.0
[2.1.0]: https://test.pypi.org/project/qikou/2.1.0/

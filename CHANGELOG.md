# Changelog

本文件记录 qikou 的显著变更。格式参考
[Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循[语义化版本](https://semver.org/lang/zh-CN/)。

## [2.2.0] — 2026-10-08

首个公开发布版本。

### Added

- 自动化测试套件 `tests/test_qikou.py`（pytest，44 项），覆盖公开 API 契约、
  切分行为、`Config` 语义、语料加载与命令行。
- GitHub Actions CI：Python 3.8–3.13 跑测试、`mypy --strict` 类型检查、
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

[2.2.0]: https://github.com/Grabrun/qikou/releases/tag/v2.2.0
[2.1.0]: https://test.pypi.org/project/qikou/2.1.0/

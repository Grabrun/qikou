# 项目目录约定

一句话：**仓库里只放「能构建、能测试、能分发」的东西；本机私有物进 `local/`；
能被重新生成的东西随手清掉。**

---

## 1. 目录树（现行）

```
ChatSplit/
├── qikou/                      # 核心包，随 wheel 分发
├── tests/
│   ├── test.txt                # 205 条人工复核用例
│   ├── test_qikou.py           # pytest 断言测试
│   └── results/                # qikou test 输出（自动生成，不入库）
├── docs/
│   ├── README.md               # 文档索引
│   ├── project-layout.md       # 本文件
│   ├── audit/                  # 审计报告与配图
│   └── design/
│       ├── v3.0-design.md      # v3.0 方案（现行）
│       └── v3.0-design-draft-1.md  # v3.0 早期草案（已归档）
├── legacy/                     # v1.0 / v2.0 单文件存档
│   └── README.md               # 存档说明（含失效的语料路径）
├── local/                      # 本机私有，整体不入库
│   ├── README.md
│   ├── kaomoji-sources/        # 4 个上游导出（≈14.4 MB）
│   ├── test-reports/           # 历史测试报告（≈1.7 MB）
│   ├── handover/               # 交接文档快照
│   └── prompt/                 # 个人提示词 + 其独立仓库
├── dist/                       # 构建产物（.whl / .tar.gz，不入库）
├── .venv-build/                # 构建与检查用虚拟环境（Python 3.14，不入库）
└── 根级文件：pyproject.toml / MANIFEST.in / .gitattributes / .gitignore /
   README.md / README_en-US.md / CHANGELOG.md / CONTRIBUTING.md / SECURITY.md / LICENSE
```

## 2. 目录职责

| 目录 | 职责 | 进 Git | 可删 |
|---|---|---|---|
| `qikou/` | 源码与语料，唯一参与打包的目录 | 是 | 否 |
| `tests/` | 断言测试与人工复核用例 | 是（`results/` 除外） | 否 |
| `tests/results/` | `qikou test` 的当次输出，带时间戳 | 否 | 是 |
| `docs/` | 设计文档、目录约定 | 是 | 否（归档文档除外） |
| `legacy/` | 旧版单文件实现，历史参考 | 是 | 视作历史，别删 |
| `local/` | 本机私有资产（数据存档、历史报告、个人资料） | 否 | `test-reports/` 可删 |
| `dist/` | 构建产物 | 否 | 是 |
| `.venv-build/` | 构建/类型检查环境 | 否 | 是（重建见第 5 节） |
| `.git/`、`.github/` | 版本库与 CI | — | 否 |

## 3. 命名约定

- **设计文档**：`<版本>-<主题>.md`，版本写全（`v3.0` 而不是 `v3`）；
  草案追加 `-draft-<序号>`。同一目录内按版本号自然排序，`draft` 永远排在
  正式稿前面。
- **测试报告**：`test_result_<YYYYMMDD>_<HHMMSS>.txt`，由 CLI 生成，**不要手工改名**。
- **发布产物**：`qikou-<版本>-py3-none-any.whl` / `qikou-<版本>.tar.gz`，
  版本号取自 `qikou/__init__.py` 的 `__version__`，两者必须一致。
- **目录名**：小写，单数或类别名（`docs/` `tests/` `legacy/`），不建"杂项""其他"这类筐。

## 4. 维护规则

1. **不进库的东西只放两个地方**：纯生成物放原位并确保在 `.gitignore`（`tests/results/`、`dist/`、
   各类缓存）；需要长期保留的本机资产一律进 `local/`，不要散在根目录。
2. **清缓存不用犹豫**：`.pytest_cache/`、`.mypy_cache/`、`__pycache__/`、`*.egg-info/` 全是可再生的。
3. **测试报告定期清**：报告正文是确定性的，堆多了直接删，或挪进 `local/test-reports/`
   留个对照。不会因此丢信息。
4. **新增文档**：设计类放 `docs/design/`，命名按第 3 节，并同步 `docs/README.md` 索引。
5. **交接文档**（`HANDOVER.md` 一类）只放 `local/handover/`，只在交接时读；
   它的目录树与版本号会过时，**不作为现状依据**，也不拿来判定缺陷。
6. **发布**：`python -m build` 出 `dist/`，`twine check dist/*` 过校验，
   再按版本登记 `CHANGELOG.md`；旧版本产物不要覆盖同名文件。

## 5. 常用命令

```bash
# 环境（本机已有 .venv-build，缺了就重建）
python -m venv .venv-build
.venv-build/Scripts/python.exe -m pip install -e ".[dev]"

# 断言测试 / 类型检查
.venv-build/Scripts/python.exe -m pytest -q          # 49 passed
.venv-build/Scripts/python.exe -m mypy              # strict，零报错

# 人工复核报告（写入 tests/results/）
.venv-build/Scripts/python.exe -m qikou test

# 构建
.venv-build/Scripts/python.exe -m build
```

## 6. 整理记录

### 2026-11-25 深度整理

起始基线：5519 个文件 / 151.67 MB。整理后：5471 个文件 / 146.52 MB
（其中 `.venv-build` 127.22 MB、`.git` 0.80 MB，属于不可删项）。

| 动作 | 对象 | 处置 |
|---|---|---|
| 删除 | `.mypy_cache`（4.85 MB）、`.pytest_cache`、`qikou.egg-info`、`tests/__pycache__` | 可再生缓存 |
| 归位 | `Kaomoji/` 4 个上游导出（14.36 MB） | → `local/kaomoji-sources/` |
| 归位 | `HANDOVER.md` | → `local/handover/` |
| 归位 | `.prompt/`（含其独立 git 仓库） | → `local/prompt/` |
| 归位 | `tests/results/` 29 份历史报告（1.70 MB） | → `local/test-reports/` |
| 改名 | `docs/v3-design.md` | → `docs/design/v3.0-design.md` |
| 改名 | `docs/v3.0-design-1.md` | → `docs/design/v3.0-design-draft-1.md`，并加归档标注 |
| 新增 | `docs/README.md`、`docs/project-layout.md`、`local/README.md`、`legacy/README.md` | — |
| 同步 | 中英文 README 的目录树与 v3 文档链接、`.gitignore` 的 `local/` 规则 | — |

验证：`pytest` 49 项通过，`mypy --strict` 零报错，`qikou split` 与 `qikou test`
输出正常（报告仍写入 `tests/results/`）。

**未改动**：`qikou/` 源码与语料、`tests/` 用例、`legacy/` 两个旧脚本、`dist/`
现有 2.2.1 产物、`.venv-build`（重建成本高，且已被忽略）。

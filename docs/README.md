# docs —— 文档索引

仓库内 `docs/` 只保留**工程约定**，不存放审计报告、设计方案、需求草稿这类长文档。
原因：它们面向维护者本人而非使用者，且会随版本迅速过时；需要留档的放本机
`local/archive/docs/`（`.gitignore` 整体忽略，不进 GitHub）。

| 文档 | 内容 | 状态 |
|---|---|---|
| [project-layout.md](project-layout.md) | 目录职责、入库规则、命名与维护约定 | 现行 |

面向使用的入门文档、API 说明在仓库根目录：

- [README.md](../README.md)（中文）
- [README_en-US.md](../README_en-US.md)（English）
- [CHANGELOG.md](../CHANGELOG.md) 版本变更
- [CONTRIBUTING.md](../CONTRIBUTING.md) 开发约定
- [SECURITY.md](../SECURITY.md) 安全问题上报

新增文档时先问一句：**这是给使用者/贡献者的，还是维护者自己的？** 前者才进
`docs/`，命名遵循 [project-layout.md](project-layout.md) 的约定，并在本表补一行。

# docs —— 文档索引

| 文档 | 内容 | 状态 |
|---|---|---|
| [project-layout.md](project-layout.md) | 目录职责、入库规则、命名与维护约定 | 现行 |
| [design/v3.0-design.md](design/v3.0-design.md) | v3.0「韵律」方案：宽召回候选 + 模型打分 + 概率校准 + DP 打包 | 设计完成，待评审 |
| [design/v3.0-design-draft-1.md](design/v3.0-design-draft-1.md) | v3.0 早期草案（纯规则 + 二分类），已并入合并稿 | 归档 |
| [audit/2026-11-25-qikou-deep-audit.md](audit/2026-11-25-qikou-deep-audit.md) | qikou 2.2.1 深度审计：17 项分级风险、六视角评审、过度开发专项、修复路线 | 现行（2026-11-25） |

面向使用的入门文档、API 说明在仓库根目录：

- [README.md](../README.md)（中文）
- [README_en-US.md](../README_en-US.md)（English）
- [CHANGELOG.md](../CHANGELOG.md) 版本变更
- [CONTRIBUTING.md](../CONTRIBUTING.md) 开发约定
- [SECURITY.md](../SECURITY.md) 安全问题上报

新增文档时：放进对应的子目录（设计类进 `design/`），命名遵循
[project-layout.md](project-layout.md) 的版本前缀约定，并在本表补一行。

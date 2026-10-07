# 贡献指南

感谢有兴趣改进 qikou。这个项目很小，规则也很简单，请先读完这一页。

## 环境准备

```bash
git clone https://github.com/Grabrun/qikou.git
cd qikou
python -m venv .venv
.venv/Scripts/activate          # Windows；Linux/macOS 用 source .venv/bin/activate
pip install -e ".[dev]"         # 只有开发期依赖，运行时依旧是零依赖
```

## 跑测试

```bash
pytest              # 断言测试，44 项
mypy                # 类型检查（strict，配置在 pyproject.toml）
```

另外有一套**给人看的**用例语料：

```bash
qikou test                     # 跑 tests/test.txt，报告写入 tests/results/
qikou test 你的用例.txt         # 跑指定文件
```

`tests/test.txt` 只有输入、没有预期输出，报告正文是确定性的，可以直接
diff 两份报告来观察改动带来的差异。它适合人工复核，不是断言测试。

## 硬性约束

1. **运行时零第三方依赖。** 只能用标准库。新增运行时依赖的 PR 不会合并。
   开发期依赖（测试、类型检查、构建）随意。
2. **先加用例，再改代码。** 修 bug 时请在 `tests/test.txt` 补一条能复现
   的最小输入，并在 `tests/test_qikou.py` 里补断言。
3. **行尾统一 LF。** 仓库有 `.gitattributes` 保证，请不要改它。
4. **改动算法后必须说明对既有用例的影响。** 跑一遍 `qikou test`，在 PR
   描述里贴出条数变化的清单。

## 代码风格

- 类型注解是必需的：`mypy --strict` 必须通过。
- 公开 API 要有 docstring；内部辅助函数可以有简短注释。
- 面向用户的文本（CLI、异常信息、README）用中文；代码标识符用英文。
- 不要为了通过检查而写 `# type: ignore`——先问为什么这里需要它。

## 提交 PR

- 一个 PR 只做一件事。重构与行为变更请分开。
- 说明**为什么**，不只是做了什么。
- 如果改变了切分结果，请给出具体例子（输入 → 之前几条 / 现在几条）。
- CI 必须全绿。

## 报告问题

功能不符合预期请开 [issue](https://github.com/Grabrun/qikou/issues)，
附上输入文本与 `qikou split` 的实际输出。安全相关问题请见
[SECURITY.md](SECURITY.md)。

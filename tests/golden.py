# -*- coding: utf-8 -*-
"""205 条用例输出的金标哈希。

``tests/test.txt`` 只有输入、没有预期输出，人工复核靠 diff 报告；这里把
"当前认可的切分结果"压成一个哈希，任何无意的行为漂移都会让 CI 失败。

用法::

    python tests/golden.py --check     # 只校验（CI 用）
    python tests/golden.py --write     # 预期改动后重建基线
    python tests/golden.py             # 打印当前哈希

预期改动请把条数变化的清单贴进 PR 描述（见 CONTRIBUTING）。
"""

from __future__ import annotations

import hashlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE = os.path.join(ROOT, "tests", "baseline", "cases.sha256")
BASELINE_DP = os.path.join(ROOT, "tests", "baseline", "cases-dp.sha256")


def _baseline_path(profile: str) -> str:
    return BASELINE_DP if profile == "dp" else BASELINE


def compute(profile: str = "default") -> str:
    sys.path.insert(0, ROOT)
    from qikou import Config, split                 # noqa: WPS433 (延迟导入)
    from qikou.cli import load_test_cases

    config = Config(use_dp=True) if profile == "dp" else None
    cases = load_test_cases(os.path.join(ROOT, "tests", "test.txt"))
    digest = hashlib.sha256()
    for name, text in cases:
        digest.update(name.encode("utf-8"))
        digest.update(b"\x1f")
        parts = split(text) if config is None else split(text, config=config)
        digest.update("\x1e".join(parts).encode("utf-8"))
        digest.update(b"\x1d")
    return digest.hexdigest().upper()


def read_baseline(profile: str = "default") -> str:
    with open(_baseline_path(profile), "r", encoding="utf-8") as f:
        for line in f:
            value = line.strip()
            if value and not value.startswith("#"):
                return value
    return ""


def write_baseline(value: str, profile: str = "default") -> None:
    path = _baseline_path(profile)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("# qikou 用例金标：python tests/golden.py --write%s 生成\n"
                % (" --profile dp" if profile == "dp" else ""))
        f.write("# 覆盖 tests/test.txt 全部用例的切分结果（含用例名）\n")
        f.write(value + "\n")


def _utf8_streams() -> None:
    """Windows 控制台默认 cp1252，打印中文会抛 UnicodeEncodeError。

    CI 日志、`cmd.exe`、PowerShell 都可能是这种编码；能在运行时切换的流
    一律切到 UTF-8，切不了的（被重定向到不支持的对象）就保持原样。
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8")
            except (OSError, ValueError):
                pass


def _parse_profile(argv: "list[str]") -> str:
    if "--profile" not in argv:
        return "default"
    i = argv.index("--profile")
    if i + 1 >= len(argv) or argv[i + 1] not in ("default", "dp"):
        raise SystemExit("--profile 只支持 default 或 dp")
    return argv[i + 1]


def main(argv: "list[str]") -> int:
    _utf8_streams()
    profile = _parse_profile(argv)
    current = compute(profile)
    baseline_path = _baseline_path(profile)
    if "--write" in argv:
        write_baseline(current, profile)
        print("已写入基线（%s）：%s" % (profile, current))
        return 0
    baseline = read_baseline(profile)
    if "--check" in argv:
        if not baseline:
            print("缺少基线文件：%s（先运行 --write --profile %s）"
                  % (baseline_path, profile))
            return 1
        if current != baseline:
            print("用例输出与基线不一致（%s）：" % profile)
            print("  基线 %s" % baseline)
            print("  当前 %s" % current)
            print("确认差异符合预期后运行：python tests/golden.py --write "
                  "--profile %s" % profile)
            return 1
        print("金标一致（%s）：%s" % (profile, current))
        return 0
    print(current)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

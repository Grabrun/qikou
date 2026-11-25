# -*- coding: utf-8 -*-
"""v3.0 段级 DP 的轻量性能基准。

用法::

    python tests/bench.py            # 打印 500 / 2000 字的中位与 P95
    python tests/bench.py --smoke    # CI 冒烟：500 字 P95 必须 <= 20 ms
"""

from __future__ import annotations

import argparse
import os
import platform
import statistics
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from qikou import Config, split_with_report  # noqa: E402

TEXT_500 = (("这是第%d句，内容还行，再补一点字数让句子长一些。" % 1) * 16)[:500]
TEXT_2000 = (TEXT_500 * 4)[:2000]


def _p95(values: "list[float]") -> float:
    return sorted(values)[min(len(values) - 1, int(len(values) * 0.95))]


def run(text: str, runs: int = 5) -> "tuple[float, float]":
    cfg = Config(use_dp=True)
    split_with_report(text, config=cfg)          # 预热
    times = []
    for _ in range(runs):
        start = time.perf_counter()
        split_with_report(text, config=cfg)
        times.append((time.perf_counter() - start) * 1000)
    return statistics.median(times), _p95(times)


def main(argv: "list[str]") -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args(argv)

    print("Python %s / %s" % (platform.python_version(), platform.platform()))
    for label, text in (("500", TEXT_500), ("2000", TEXT_2000)):
        median, p95 = run(text)
        print("%s 字：中位 %.2f ms，P95 %.2f ms" % (label, median, p95))
        if args.smoke and label == "500" and p95 > 20.0:
            print("性能冒烟失败：500 字 P95 %.2f ms > 20 ms" % p95,
                  file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

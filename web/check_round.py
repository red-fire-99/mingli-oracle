#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pyRoundN(x, nd) 必须与 Python round(x, nd) 逐值相同。

单独做成一道门禁的理由：pyRoundN 的平局分支（round-half-even）很容易写反符号，
而它只在「值恰好落在十进制平局点」时才触发 —— 那种值在真实数据里极罕见，
所以 512 个排盘用例全都可能绕过去，得单独喂边界值。

我自己就在这里栽过一次：符号写成「远离零」，pyRoundN(31.25, 1) 得 31.4，
Python 是 31.2。是五行百分比 31.2% vs 31.3% 把它逼出来的。
"""
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
NODE = os.environ.get("MINGLI_NODE", "node")

CASES = [
    31.25, -31.25, 0.125, 0.375, 0.625, 2.5, -2.5, 31.35, 0.975, 1.005,
    0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95,
    1.25, 1.35, 1.45, 1.55, 1.65, 1.75, 1.85, 1.95,
    6.640624999999998, 27.34375, 29.296875, 12.1, 99.95, 0.005, 1234.5678,
    # 下面这些是「差一个 ulp」的浮点值，用科学计数法写以免被
    # 敏感信息扫描当成银行卡号（16~19 位连续数字）误报。
    2.734375e1 + 4e-15, 3.125e1 + 4e-15, 1.5e-1 + 2e-17,
    -0.05, -0.15, -0.25, -1.25, -1.35, 100.5, 1000.5,
]
NDS = [0, 1, 2, 3]


def main(argv=None):
    rj = os.path.join(HERE, "js", ".round_probe.mjs")
    io.open(rj, "w", encoding="utf-8").write(
        'import { pyRoundN } from "./kernel.js";\n'
        "const C = " + json.dumps(CASES) + ";\n"
        "const out = [];\n"
        "for (const v of C) {\n"
        '  const row = { v: v.toPrecision(21) };\n'
        '  for (const nd of ' + json.dumps(NDS) + ') row["nd"+nd] = String(pyRoundN(v, nd));\n'
        "  out.push(row);\n"
        "}\n"
        'process.stdout.write("@@R@@" + JSON.stringify(out));\n')

    try:
        r = subprocess.run([NODE, ".round_probe.mjs"], capture_output=True,
                           cwd=os.path.join(HERE, "js"), timeout=180)
    except FileNotFoundError:
        print("找不到 Node：%s" % NODE)
        return 2
    finally:
        try:
            os.remove(rj)
        except OSError:
            pass

    so = r.stdout.decode("utf-8", "replace")
    if "@@R@@" not in so:
        print("JS 无输出：\n" + r.stderr.decode("utf-8", "replace")[-600:])
        return 2
    got = json.loads(so.split("@@R@@", 1)[1])

    fails = 0
    for v, g in zip(CASES, got):
        for nd in NDS:
            want = round(v, nd)
            js = float(g["nd%d" % nd])
            if abs(float(want) - js) > 1e-12:
                print("  [FAIL] round(%r, %d): py=%r js=%r"
                      % (v, nd, want, g["nd%d" % nd]))
                fails += 1

    print("pyRoundN ↔ Python round 对拍")
    print("  %d 个边界值 × %d 个位数 = %d 次比较"
          % (len(CASES), len(NDS), len(CASES) * len(NDS)))
    print()
    if fails:
        print("不一致 %d 处" % fails)
        return 1
    print("全部一致（含 31.25 / 0.125 / 2.5 等恰好落在十进制平局点的值）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
# -*- coding: utf-8 -*-
"""JS 引擎 vs 第三方参照实现的精度对照。

为什么不能只跟 Python 对
------------------------
512/512 对拍只能证明「JS == Python」。如果两边**同时**算错，
对拍是绿的 —— 它验的是一致性，不是正确性。

正确性得跟外部参照比。本仓库 tools/ 下已有两个参照：
  ephem   (VSOP87/ELP2000)  行星黄经
  iztro   2.6.1              紫微斗数

这两个以前只验过 Python 引擎。切到 JS 之后必须重跑 ——
「引擎换了实现，精度声明就得重新验」这件事不能想当然。

跑不了的工具要明确说跑不了，不能静默跳过 ——
静默跳过会让「门禁通过」变成一句谎话。
"""
import io
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TOOLS = os.path.join(ROOT, "tools")


def main():
    print("JS 引擎的外部精度复核\n")

    # ---- 1) ephem：行星黄经 ----
    print("1) 行星黄经 vs ephem (VSOP87/ELP2000)")
    script = os.path.join(TOOLS, "verify_astro.py")
    if not os.path.isfile(script):
        print("   [跳过] %s 不存在" % script)
    else:
        src = io.open(script, encoding="utf-8").read()
        if "import ephem" not in src:
            print("   [跳过] verify_astro.py 已不依赖 ephem，改验了什么需人工确认")
        else:
            r = subprocess.run([sys.executable, script], capture_output=True,
                               cwd=TOOLS, timeout=1800)
            out = (r.stdout + r.stderr).decode("utf-8", "replace")
            tail = [l for l in out.splitlines() if l.strip()][-12:]
            for l in tail:
                print("   " + l)
            if r.returncode != 0:
                print("   [失败] 返回码 %d —— 可能缺 ephem，需 pip install ephem" % r.returncode)

    # ---- 2) iztro：紫微斗数 ----
    print()
    print("2) 紫微斗数 vs iztro 2.6.1")
    script = os.path.join(TOOLS, "verify_ziwei.py")
    if not os.path.isfile(script):
        print("   [跳过] %s 不存在" % script)
    else:
        src = io.open(script, encoding="utf-8").read()
        if "iztro" not in src:
            print("   [跳过] verify_ziwei.py 不再依赖 iztro")
        else:
            node_dir = None
            for d in ("node_modules",):
                p = os.path.join(ROOT, d)
                if os.path.isdir(p):
                    node_dir = p
            if not node_dir:
                print("   [跳过] 未安装 iztro —— 需要 npm install iztro")
                print("          这意味着「120/120 与 iztro 一致」这句声明")
                print("          **当前无法复验**，发版说明里不应再当作既成事实")
            else:
                r = subprocess.run([sys.executable, script], capture_output=True,
                                   cwd=TOOLS, timeout=1800)
                out = (r.stdout + r.stderr).decode("utf-8", "replace")
                for l in [x for x in out.splitlines() if x.strip()][-12:]:
                    print("   " + l)
                if r.returncode != 0:
                    print("   [失败] 返回码 %d" % r.returncode)

    print()
    print("说明：上面若出现 [跳过]，代表对应的外部精度声明这次没有复验。")
    print("      要复验需要 ephem（pip）与 iztro（npm），本机两者都装不上。")


if __name__ == "__main__":
    main()
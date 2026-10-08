#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把产物里的内联 script 交给 node 做真正的语法解析。

为什么 verify_dist 不够
----------------------
`verify_dist.py` 剥掉字符串与注释后只数括号，能抓「少一个 }」，
抓不到这些：

    var a = [1, 2   // 少一个逗号
    if (x            // if 后面漏了括号
    return 1          // return 写在了函数体外
    foo()             // 上一行少了分号（自动插入能救，但下面这种救不了）

它们括号是**配平的**，所以 verify_dist 全绿；
但浏览器一执行就抛 SyntaxError，整个 script 块不执行 ——
而产物只有一个 script 块（出生地数据 + 引擎 + 页面代码），
一抛错就是**整页空白**，现象是「打开就什么都没有」。

所以：数括号 ≠ 语法正确。这条门禁让 node 的解析器真的过一遍。

用法
----
    python web/check_syntax.py
    python web/check_syntax.py --node /path/to/node
"""
import argparse
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(HERE, "dist", "index.html")


def find_node():
    """找 node。找不到就报错退出 —— 不静默跳过。

    静默跳过等于「这条门禁其实没跑」，而报告里会显示它通过了。
    这正是历史上踩过的坑：验证的是别的东西，却当成这条过了。
    """
    return shutil.which("node")


def main(argv=None):
    p = argparse.ArgumentParser(description="校验产物内联 JS 的语法")
    p.add_argument("--node", default=None, help="node 可执行文件路径")
    p.add_argument("--dist", default=DIST)
    a = p.parse_args(argv)

    node = a.node or find_node()
    if not node:
        print("[FAIL] 找不到 node，无法校验 JS 语法。\n"
              "       这条门禁不能跳过 —— 括号配平不等于语法正确，"
              "而产物只有一个 script 块，语法错就是整页空白。\n"
              "       本地可显式指定：--node /path/to/node", file=sys.stderr)
        return 2

    if not os.path.isfile(a.dist):
        print("[FAIL] 找不到产物 %s，请先运行 build_web.py" % a.dist,
              file=sys.stderr)
        return 2

    html = io.open(a.dist, encoding="utf-8").read()
    # 有 src 的是外链；产物本该零外链（verify_dist 负责查），这里一并跳过
    blocks = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, re.S)

    print("校验 %s 内联 JS 语法" % a.dist)
    print("node: %s" % node)
    print("内联 script %d 段\n" % len(blocks))
    if not blocks:
        print("[FAIL] 产物里没有内联 script —— 引擎不该外链，"
              "这说明构建产物不对", file=sys.stderr)
        return 1

    tmp = tempfile.mkdtemp(prefix="check_syntax_")
    bad = 0
    try:
        for i, code in enumerate(blocks, 1):
            if not code.strip():
                continue
            path = os.path.join(tmp, "block_%02d.js" % i)
            io.open(path, "w", encoding="utf-8", newline="\n").write(code)
            kb = len(code.encode("utf-8")) / 1024.0
            r = subprocess.run([node, "--check", path], capture_output=True)
            if r.returncode == 0:
                print("  [OK]   第 %d 段 %.1f KB 语法正确" % (i, kb))
            else:
                bad += 1
                print("  [FAIL] 第 %d 段 %.1f KB 语法错误" % (i, kb))
                err = r.stderr.decode("utf-8", "replace")
                # node --check 报的是临时文件的行列，转成块内行号才好定位
                print("    " + err.strip()[:900].replace("\n", "\n    "))
    finally:
        for f in os.listdir(tmp):
            os.remove(os.path.join(tmp, f))
        os.rmdir(tmp)

    print()
    if bad:
        print("语法校验失败 %d 段 —— 产物会在浏览器里直接抛 SyntaxError" % bad)
        return 1
    print("语法校验通过：%d 段全部可解析" % len(blocks))
    return 0


if __name__ == "__main__":
    sys.exit(main())
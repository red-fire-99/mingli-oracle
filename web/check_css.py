# -*- coding: utf-8 -*-
"""加第 18 道门禁：HTML 用到的 class 必须在 CSS 里有定义。

为什么需要这道门禁
----------------
这次用户反馈「折叠起来的字顶格、太窄、颜色浅」，根因是
**34 个 class、300 多处使用，CSS 里一个都没定义**。
浏览器只能按 <p>/<div> 默认值渲染，于是顶格、无限宽、颜色失控。

这类问题前面已经犯过一次（.ssx CSS 未定义），
靠我手动扫才扫出来。既然会复发，就该固化。
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P_ORACLE = os.path.join(ROOT, "scripts", "oracle.py")
P_RENDER = os.path.join(ROOT, "web", "js", "render.js")


def css_text():
    t = io.open(P_ORACLE, encoding="utf-8").read()
    s = t.index('CSS = """') + len('CSS = """')
    e = t.index('"""', s)
    return t[s:e]


def used_classes():
    used = {}
    for p in (P_ORACLE, P_RENDER):
        t = io.open(p, encoding="utf-8").read()
        for m in re.finditer(r'class=\\?"([a-zA-Z0-9 -]+)\\?"', t):
            for c in m.group(1).split():
                if re.fullmatch(r"[a-zA-Z][a-zA-Z0-9-]*", c):
                    used[c] = used.get(c, 0) + 1
    return used


def main():
    css = css_text()
    defined = set(re.findall(r"\.([a-zA-Z][a-zA-Z0-9-]*)", css))
    used = used_classes()
    missing = {k: v for k, v in used.items() if k not in defined}

    print("CSS 定义了 %d 个 class，HTML 用到 %d 个" % (len(defined), len(used)))
    if not missing:
        print("全部都有样式。")
        return 0
    print("")
    print("!! 用到但没定义样式的 class 共 %d 个：" % len(missing))
    for k in sorted(missing, key=lambda x: -missing[x]):
        print("   .%-14s 用了 %d 次" % (k, missing[k]))
    print("")
    print("未定义的 class 会让浏览器按默认值渲染 —— 顶格、宽度失控、")
    print("颜色不可控。请在 oracle.py 的 CSS 里补上，或用别的 class。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
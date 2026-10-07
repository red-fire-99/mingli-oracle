#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验 web/dist/index.html 是否自洽 —— CI 用，零第三方依赖。

这些断言刻意做成「静态可判定」：不启动浏览器、不联网。
目的是在部署前把明显的构建错误挡住，而不是替浏览器做端到端测试。

检查项
------
1. 构建占位符已全部替换（否则页面会拿到字面量 /*__...__*/）
2. 7 个引擎模块都在，且内联内容是合法 JSON 字符串、Python 语法真实配平
3. JS 结构配平（剥掉字符串与注释后计数）
4. JS 引用的 DOM id 都真实存在，避免运行时报「null」
5. 页面自身不含本机痕迹或凭据
"""
import io
import json
import os
import re
import sys
import tokenize
import io as _io

HERE = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(HERE, "dist", "index.html")

EXPECT_MODULES = ["almanac", "plain", "bazi", "ziwei", "astro", "divination", "oracle"]
PLACEHOLDERS = ["/*__MINGLI_MODULES__*/", "/*__PYODIDE_INDEX__*/", "/*__ENGINE_VERSION__*/"]

# 本机痕迹与凭据：进 CI 就等于进公网，必须拦住
FORBIDDEN = ["cuiyuxin", "C:/Users", "C:\\Users", ".workbuddy-ai",
             "ghp_", "github_pat_", "BEGIN RSA PRIVATE KEY", "BEGIN OPENSSH PRIVATE KEY"]

fails = []


def ck(name, ok, extra=""):
    print("  [%s] %s%s" % ("OK" if ok else "FAIL", name, (" " + extra) if extra else ""))
    if not ok:
        fails.append(name)


def strip_js(s):
    """剥掉 JS 的字符串、行注释、块注释，只留结构字符。"""
    out = []
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c in "\"'":
            q = c
            i += 1
            while i < n:
                if s[i] == "\\":
                    i += 2
                    continue
                if s[i] == q:
                    i += 1
                    break
                i += 1
            continue
        if c == "/" and i + 1 < n and s[i + 1] == "/":
            while i < n and s[i] != "\n":
                i += 1
            continue
        if c == "/" and i + 1 < n and s[i + 1] == "*":
            i += 2
            while i + 1 < n and not (s[i] == "*" and s[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def balanced_python(src):
    """Python 源码的括号是否在语法层配平（剥字符串与注释后再数）。

    不能直接对原文字符计数：中文 docstring 里常有字面括号，
    例如 almanac.py 的「归一到 (−180, 180]」，会让朴素计数误报。
    """
    cnt = {"(": 0, ")": 0, "[": 0, "]": 0, "{": 0, "}": 0}
    try:
        for t in tokenize.generate_tokens(_io.StringIO(src).readline):
            if t.type == tokenize.OP and t.string in cnt:
                cnt[t.string] += 1
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return False, "语法错误"
    ok = (cnt["("] == cnt[")"] and cnt["["] == cnt["]"] and cnt["{"] == cnt["}"])
    detail = "( %d/%d  [ %d/%d  { %d/%d" % (cnt["("], cnt[")"], cnt["["], cnt["]"],
                                            cnt["{"], cnt["}"])
    return ok, detail


def main():
    if not os.path.isfile(DIST):
        print("找不到产物 %s，请先运行 build_web.py" % DIST)
        return 1
    html = io.open(DIST, encoding="utf-8").read()
    print("校验 %s（%.1f KB）\n" % (DIST, len(html.encode("utf-8")) / 1024.0))

    print("1) 构建占位符")
    for ph in PLACEHOLDERS:
        ck("已替换 %s" % ph, ph not in html)

    print("\n2) 内联的引擎模块")
    found = re.findall(r'window\.MINGLI_SRC\["([^"]+)"\]', html)
    ck("模块数量 = %d" % len(EXPECT_MODULES), len(found) == len(EXPECT_MODULES),
       "-> " + ",".join(found))
    for m in EXPECT_MODULES:
        ck("含模块 " + m, m in found)
    for name, lit in re.findall(r'window\.MINGLI_SRC\["([^"]+)"\] = (".*?");\n', html, re.S):
        try:
            src = json.loads(lit)
        except Exception as e:
            ck("模块 %s 是合法 JSON" % name, False, str(e))
            continue
        ok, detail = balanced_python(src)
        ck("模块 %s Python 语法配平" % name, ok, detail)

    print("\n3) JS 结构")
    m = re.search(r"<script>(.*)</script>", html, re.S)
    if not m:
        ck("找到内联 script", False)
        return 1
    code = strip_js(m.group(1))
    for a, b, nm in [("(", ")", "圆"), ("{", "}", "花"), ("[", "]", "方")]:
        ck("JS %s括号配平" % nm, code.count(a) == code.count(b),
           "%d/%d" % (code.count(a), code.count(b)))
    depth = 0
    for ch in code:
        depth += (ch == "{") - (ch == "}")
    ck("JS 花括号深度归零", depth == 0, "depth=%d" % depth)

    print("\n4) DOM 引用")
    ids = set(re.findall(r'id="([^"]+)"', html))
    used = set(re.findall(r'\$\("#([A-Za-z0-9_-]+)"\)', html))
    missing = sorted(used - ids)
    ck("JS 引用的 id 全部存在", not missing, "缺失=%s" % (missing or "无"))
    for want in ("form", "city", "lon", "lat", "solarDate", "birthTime", "status",
                 "submitBtn", "resetBtn", "demoBtn", "saveBtn", "editBtn",
                 "panel-plain", "panel-pro", "headline", "result"):
        ck("含 #" + want, want in ids)
    ck("切页按钮按 .tabs [data-tab] 定位",
       'querySelectorAll(".tabs [data-tab]")' in html and "dataset.tab" in html)
    ck("分段控件按 data-cal / data-sex 定位",
       'data-cal="solar"' in html and 'data-sex="男"' in html
       and 'getAttribute("data-cal")' in html)

    print("\n5) 敏感信息")
    for needle in FORBIDDEN:
        ck("不含 %s" % needle, needle not in html)
    ck("无外部 script 标签（Pyodide 由 JS 动态注入）",
       not re.findall(r'<script[^>]+src="[^"]+"', html))
    ck("Pyodide 版本已锁定", 'var PYODIDE_VERSION = "0.26.4"' in html)
    # 两类文件分别配源：npmmirror 的 python_stdlib.zip 是 451，必须换源
    ck("wasm 配了多个候选源", "var WASM_SOURCES = [" in html
       and html.count('url: "https://') >= 4)
    ck("stdlib 配了多个候选源", "var INDEX_SOURCES = [" in html)
    # 顺序判断必须在数组内部，避免注释里先出现某源名导致误判
    warr = html[html.index("var WASM_SOURCES = ["):html.index("];", html.index("var WASM_SOURCES = ["))]
    ck("wasm 源 npmmirror 优先", warr.index("npmmirror") < warr.index("gcore.jsdelivr"))
    ck("indexURL 未硬编码单源（改成逐个试）",
       "indexURL: idxSrc.url" in html and "var INDEX_URL" not in html)
    # 两层回退：wasm 源失败换源，indexURL 失败也换源
    ck("两层回退已实现", "trySource(wi, ii)" in html
       and "trySource(wi, ii + 1)" in html and "trySource(wi + 1, ii)" in html)
    ck("回退入口带双索引", "trySource(0, 0)" in html)
    ck("wasm 源耗尽后转下一个 indexURL",
       "if (ii + 1 < INDEX_SOURCES.length) return trySource(0, ii + 1);" in html)
    ck("全部源失败时给出可操作提示",
       "所有镜像源都没能加载成功" in html and "scripts/server.py" in html)
    # 超时兜底：单源卡死必须能换下一个，否则永久白屏
    ck("下载超时已设死", "LOAD_TIMEOUT_MS = 20000" in html)
    ck("启动超时已设死", "BOOT_TIMEOUT_MS = 45000" in html)
    ck("超时会清理定时器", html.count("clearTimeout(bootTimer)") >= 2)
    ck("已加载的 pyodide.js 不重复挂载",
       'typeof loadPyodide !== "function"' in html)
    ck("加载完成显示来源与耗时", "运行时来源：" in html)
    ck("声明生辰不上传", "不上传" in html)

    print("\n" + "=" * 56)
    if fails:
        print("失败 %d 项：%s" % (len(fails), fails))
        return 1
    print("产物校验全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
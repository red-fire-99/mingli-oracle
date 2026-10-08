#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成网页版：把纯 JS 排盘引擎内联进一个自包含的 HTML 文件。

设计要点
--------
1. **打开即用**：引擎（web/js/*.js）在构建时由 web/bundle.py 拼成一个
   IIFE 直接内联进 HTML。页面加载后**不发起任何网络请求**，
   也不需要 HTTP 服务 —— file:// 双击打开就能排盘。
2. **结果一致**：JS 引擎是 Python 引擎的移植，两份实现由
   web/diff_py_js.py 逐案对拍保证一致（CI 门禁，不过不部署）。
3. **数据不出浏览器**：纯前端计算，没有后端。生辰只在本机内存里。
4. **零构建依赖**：只用标准库，不需要 npm / 打包器。

与上一版的区别
--------------
上一版把 scripts/ 的 Python 源码内联、靠 Pyodide（WASM 版 CPython）
在浏览器里执行。首次打开需下载约 5MB 运行时，且必须走 HTTP。
现在改成纯 JS 移植，代价是仓库里有两份实现 —— 这个代价由对拍工具消化。

用法
----
    python web/build_web.py            # 输出到 web/dist/index.html
    python web/build_web.py --out 目录
"""
import argparse
import io
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TEMPLATE = os.path.join(HERE, "app.html")

PLACEHOLDER_ENGINE = "/*__MINGLI_ENGINE__*/"
PLACEHOLDER_CSS = "/*__ORACLE_CSS__*/"
PLACEHOLDER_REGIONS = "/*__MINGLI_REGIONS__*/"
PLACEHOLDER_PY = "/*__MINGLI_PY__*/"

# 引擎版本号的占位符。刻意**不带引号**：注入的是 json.dumps(ver) 的结果，
# 自带引号；模板里若写成 "/*__...__*/" 就会变成 ""1.0.0"" 这种坏代码。
# 同一个字符串在 app.html（JS 表达式）与 engine.js（JS 字符串字面量）里
# 各用一次形式不同，所以要同时接受两种写法。
VERSION_TOKENS = ["/*__ENGINE_VERSION__*/", '"__ENGINE_VERSION__"',
                  "__ENGINE_VERSION__"]

# 需要内联的渲染层 CSS：命盘 HTML 靠它成型（scripts/oracle.py 里的 CSS 常量）
CSS_FROM = os.path.join(ROOT, "scripts", "oracle.py")


def read(path):
    with io.open(path, encoding="utf-8") as f:
        return f.read()


def engine_version():
    """从 CHANGELOG 头一行取版本号，用于页面上的运行时标识。"""
    head = read(os.path.join(ROOT, "CHANGELOG.md")).splitlines()
    for line in head:
        s = line.strip()
        if not s.startswith("## ["):
            continue
        # s 形如 "## [1.0.0] — 2026-10-07"，从 '[' 之后取到 ']'
        name = s[s.index("[") + 1:s.index("]")].strip()
        # 「[Unreleased]」是占位标题，不是版本号，往后找第一个真实版本
        if name and name.lower() != "unreleased":
            return name
    return "dev"


def oracle_css():
    """从 oracle.py 里抠出 CSS 常量。

    渲染层 HTML 与它的样式是一套的，CSS 也归 Python 管（CLI 导出的命盘
    网页要用同一份）。这里用「找常量起止」而不是手抄一份 CSS 文件 ——
    手抄必然漂移，且漂移了没有任何检查能发现。
    """
    src = read(CSS_FROM)
    start = src.index('CSS = """')
    body_start = src.index("\n", start) + 1
    end = src.index('"""', body_start)
    return src[body_start:end]


def bundle_js():
    """调 bundle.py 生成引擎 IIFE。"""
    out = os.path.join(HERE, ".engine_bundle.js")
    try:
        r = subprocess.run(
            [sys.executable, os.path.join(HERE, "bundle.py"), "--out", out],
            capture_output=True)
        if r.returncode != 0:
            sys.stderr.write(r.stderr.decode("utf-8", "replace"))
            raise SystemExit("引擎打包失败")
        sys.stdout.write(r.stdout.decode("utf-8", "replace"))
        with io.open(out, encoding="utf-8") as f:
            return f.read()
    finally:
        try:
            os.remove(out)
        except OSError:
            pass


def main(argv=None):
    p = argparse.ArgumentParser(description="生成网页版单文件 HTML（零构建依赖）")
    p.add_argument("--out", default=os.path.join(HERE, "dist"), help="输出目录")
    a = p.parse_args(argv)

    if not os.path.isfile(TEMPLATE):
        print("缺少模板: %s" % TEMPLATE, file=sys.stderr)
        return 1
    html = read(TEMPLATE)
    if PLACEHOLDER_ENGINE not in html:
        print("模板缺少占位符 %s（引擎 IIFE）" % PLACEHOLDER_ENGINE, file=sys.stderr)
        return 1
    if not any(t in html for t in VERSION_TOKENS):
        print("模板缺少版本号占位符", file=sys.stderr)
        return 1
    if PLACEHOLDER_CSS not in html:
        print("模板缺少占位符 %s（命盘样式）" % PLACEHOLDER_CSS, file=sys.stderr)
        return 1
    if PLACEHOLDER_REGIONS not in html:
        print("模板缺少占位符 %s（行政区划经纬度）" % PLACEHOLDER_REGIONS,
              file=sys.stderr)
        return 1
    if PLACEHOLDER_PY not in html:
        print("模板缺少占位符 %s（拼音表）" % PLACEHOLDER_PY, file=sys.stderr)
        return 1

    engine = bundle_js()
    ver = engine_version()
    quoted = json.dumps(ver)          # "1.0.0"

    # 引擎 IIFE 里的版本占位符先替掉，再整体塞进 HTML。
    # 顺序敏感：必须「长 token 在前」，否则 "__ENGINE_VERSION__" 会把
    # '"__ENGINE_VERSION__"' 里的引号留成孤儿。
    for tok in sorted(VERSION_TOKENS, key=len, reverse=True):
        engine = engine.replace(tok, quoted)

    # 关键：占位符在 app.html 里出现两次 —— 一处在顶部说明文字里
    #（「内联进下方 /*__MINGLI_ENGINE__*/ 处」），一处在真正该插代码的位置。
    # str.replace 默认全替换，会把 136KB 引擎塞两遍，产物直接翻倍。
    # 所以只认「独占一行」的那处。
    needle = "\n" + PLACEHOLDER_ENGINE + "\n"
    if html.count(needle) != 1:
        raise SystemExit("模板里独占一行的 %s 出现 %d 次（应 1 次）"
                         % (PLACEHOLDER_ENGINE, html.count(needle)))
    html = html.replace(needle, "\n" + engine + "\n")
    for tok in sorted(VERSION_TOKENS, key=len, reverse=True):
        html = html.replace(tok, quoted)
    html = html.replace(PLACEHOLDER_CSS, oracle_css())

    # 行政区划数据：整体内联成 window.MINGLI_REGIONS。
    # 用 JSON.parse 而不是直接贴字面量 —— 40 万字符的对象字面量
    # 在浏览器里逐个 token 解析明显比一次性 parse 慢。
    regions = read(os.path.join(HERE, "js", "regions.json"))
    if len(regions) < 10000:
        print("regions.json 异常小（%d 字节），出生地三级选择会是空的" % len(regions),
              file=sys.stderr)
        return 1
    html = html.replace(PLACEHOLDER_REGIONS,
                        "window.MINGLI_REGIONS = JSON.parse(%s);"
                        % json.dumps(regions, ensure_ascii=False))

    # 拼音表与行政区划同源（同一个 regions.json 里），单独注入成两个变量。
    # 不用 JSON.parse 是因为这两张表小（~20KB），直接贴字面量解析更快；
    # 而且贴字面量能在产物里一眼看出「拼音表有没有真的进来」。
    reg = json.loads(regions)
    py_map = reg.get("py") or {}
    poly_map = reg.get("poly") or {}
    if len(py_map) < 1000:
        print("regions.json 里没有拼音表（%d 字），拼音搜索会失效。"
              "请运行 python web/gen_regions.py 重新生成" % len(py_map),
              file=sys.stderr)
        return 1
    html = html.replace(PLACEHOLDER_PY,
                        "window.MINGLI_PY = %s;\nwindow.MINGLI_POLY = %s;"
                        % (json.dumps(py_map, ensure_ascii=False),
                           json.dumps(poly_map, ensure_ascii=False)))

    os.makedirs(a.out, exist_ok=True)
    dest = os.path.join(a.out, "index.html")
    with io.open(dest, "w", encoding="utf-8") as f:
        f.write(html)

    # Pages 站点 favicon：没有就复用截图，免得 404
    shot = os.path.join(ROOT, "assets", "screenshot.png")
    if os.path.isfile(shot):
        shutil.copyfile(shot, os.path.join(a.out, "favicon.png"))

    kb = os.path.getsize(dest) / 1024.0
    print("已生成 %s (%.1f KB)" % (dest, kb))
    print("引擎: 纯 JS 内联 v%s，零外部依赖" % ver)
    print("提示: 直接用浏览器打开即可（file:// 也能跑），无需起 HTTP 服务")
    return 0


if __name__ == "__main__":
    sys.exit(main())
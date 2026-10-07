#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成网页版：把整个排盘引擎内联进一个自包含的 HTML 文件。

设计要点
--------
1. **不重写引擎**：网页版跑的就是 scripts/ 里同一份 Python 源码，
   通过 Pyodide（CPython 的 WASM 构建）在浏览器里执行。
   因此网页版和本地 CLI 的排盘结果逐字一致，不存在「两份实现」。
2. **数据不出浏览器**：Pyodide 是纯前端运行时，没有后端。
   生辰只在本机内存里计算，不发往任何服务器。
3. **零构建依赖**：只用标准库，不需要 npm / 打包器。
   产物是单个 HTML + 一份 LICENSE 说明，扔进任意静态托管都能跑。

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
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPTS = os.path.join(ROOT, "scripts")
TEMPLATE = os.path.join(HERE, "app.html")

# 需要内联的模块：almanac 是底座，其余按依赖顺序
MODULES = [
    "almanac.py",
    "plain.py",
    "bazi.py",
    "ziwei.py",
    "astro.py",
    "divination.py",
    "oracle.py",
]

# Pyodide 版本（锁死，避免上游变更导致行为漂移）
# 页面里配了多镜像源，npmmirror 国内优先；这个版本只用于占位符替换与提示文案。
PYODIDE_VERSION = "0.26.4"

PLACEHOLDER_MODULES = "/*__MINGLI_MODULES__*/"
PLACEHOLDER_PYODIDE = "/*__PYODIDE_VERSION__*/"


def read(path):
    with io.open(path, encoding="utf-8") as f:
        return f.read()


def build_modules():
    """把每个 .py 模块包成 JS 字符串常量，拼成一段可注入的 JS。"""
    out = ["// 由 web/build_web.py 自动生成，请勿手改。", "// 引擎源码逐字内联，保证与本地 CLI 结果一致。", ""]
    for name in MODULES:
        src = read(os.path.join(SCRIPTS, name))
        module = name[:-3]  # 去掉 .py
        # 用 JSON 字符串字面量承载源码，转义交给 json.dumps，不手拼
        out.append("window.MINGLI_SRC[%s] = %s;"
                   % (json.dumps(module), json.dumps(src, ensure_ascii=False)))
    return "\n".join(out)


def main(argv=None):
    p = argparse.ArgumentParser(description="生成网页版单文件 HTML（零构建依赖）")
    p.add_argument("--out", default=os.path.join(HERE, "dist"), help="输出目录")
    a = p.parse_args(argv)

    for name in MODULES:
        if not os.path.isfile(os.path.join(SCRIPTS, name)):
            print("缺少模块: %s" % name, file=sys.stderr)
            return 1
    if not os.path.isfile(TEMPLATE):
        print("缺少模板: %s" % TEMPLATE, file=sys.stderr)
        return 1

    html = read(TEMPLATE)
    if PLACEHOLDER_MODULES not in html or PLACEHOLDER_PYODIDE not in html:
        print("模板缺少占位符: %s / %s" % (PLACEHOLDER_MODULES, PLACEHOLDER_PYODIDE), file=sys.stderr)
        return 1

    html = html.replace(PLACEHOLDER_MODULES, build_modules())
    html = html.replace(PLACEHOLDER_PYODIDE, json.dumps(PYODIDE_VERSION))
    # 顺带把引擎版本写进页面，便于线上排查
    html = html.replace("/*__ENGINE_VERSION__*/",
                        json.dumps(read(os.path.join(ROOT, "CHANGELOG.md")).splitlines()[2].strip("[] ")))

    os.makedirs(a.out, exist_ok=True)
    dest = os.path.join(a.out, "index.html")
    with io.open(dest, "w", encoding="utf-8") as f:
        f.write(html)

    # Pages 站点 favicon：没有就复用截图，免得 404
    shot = os.path.join(ROOT, "assets", "screenshot.png")
    if os.path.isfile(shot):
        shutil.copyfile(shot, os.path.join(a.out, "favicon.png"))

    kb = os.path.getsize(dest) / 1024.0
    print("已生成 %s (%.1f KB, 内联 %d 个模块)" % (dest, kb, len(MODULES)))
    print("Pyodide: v%s（页面内置多镜像源回退，npmmirror 优先）" % PYODIDE_VERSION)
    print("提示: 本地预览用  python -m http.server -d web/dist 8000"
          "（需 http:// 而非 file://，否则浏览器不让加载 WASM）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
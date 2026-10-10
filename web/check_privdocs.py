#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""门禁：文档里不该出现隐私叙述。

为什么单独一道门禁
------------------
`check_secrets.py` 查的是「有没有泄露」—— 凭据、路径、token。
它**不查**「有没有把内部审查报告发到公网」。

而后者我已经犯过一次：把「哪个文件曾硬编码了什么」「远端历史被重写过」
「本机还留着备份分支」「逐条隐私审查结论」写进了 CHANGELOG 和发行说明。
每一条单看都不是凭据，扫描器全绿 —— 但那些是**内部审查的结论**，
只该跟开发者说，不该挂在公开仓库里。

规矩是定过的：**隐私审查照做，但公开文档不声明**。
所以要有门禁守着，否则下次整理发布说明时又会顺手写进去。

扫什么
------
只扫文档类文件（.md / .txt）。代码里的模式清单（FORBIDDEN 里写着
token 前缀）是规则本身，不是隐私叙述，不能扫。

判据用完整短语，不用单字 —— 用「性」去扫会命中「确定性」，
报出来的全是误报，方向完全错。
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (正则, 为什么这条不该出现在公开文档里)
NARRATIVE = [
    (r"曾硬编码", "叙述了曾硬编码路径"),
    (r"已(在)?远端历史中移除", "叙述了远端历史被重写过"),
    (r"备份分支|pre-rewrite-history", "提到了重写前的备份分支"),
    (r"隐私现状|审查结论|隐私审查结论", "写出了隐私审查结论"),
    (r"远端全部\s*\d+\s*个\s*commit", "叙述了远端 commit 状态"),
    (r"工作区扫描会全绿", "叙述了扫描器的历史缺陷"),
    (r"泄露.{0,12}(发生|进过|留在)", "叙述了泄露事件"),
    (r"误推就出去了", "叙述了误推风险"),
    (r"本机仍留着", "叙述了本机残留"),
    (r"真实用户名", "提到了真实用户名"),
    (r"工具链安装目录", "提到了工具链安装目录"),
]

# 本机痕迹 —— 已有门禁覆盖，这里在文档类文件上再兜一次
FINGER = [("cuiyuxin", "本机用户名"),
          (".workbuddy-ai", "本机应用名")]

DOC_EXT = (".md", ".txt", ".rst")
SKIP_DIR = {".git", "node_modules", "__pycache__", ".venv", "web/dist"}
# 只扫给用户看的文档；源码目录里的说明性 md 也扫（它们同样会进仓库）
SKIP_FILES = set()


def scan():
    hits = []
    nfile = 0
    for root, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIR]
        for f in files:
            if not f.endswith(DOC_EXT):
                continue
            p = os.path.join(root, f)
            rel = os.path.relpath(p, ROOT).replace("\\", "/")
            if rel in SKIP_FILES:
                continue
            try:
                t = io.open(p, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            nfile += 1
            for pat, label in NARRATIVE:
                for m in re.finditer(pat, t):
                    s = max(0, m.start() - 40)
                    hits.append((label, rel,
                                 t[s:m.end() + 40].replace("\n", " ").strip()))
            for lit, label in FINGER:
                n = t.count(lit)
                if n:
                    i = t.index(lit)
                    hits.append(("%s x%d" % (label, n), rel,
                                 t[max(0, i - 40):i + 50].replace("\n", " ").strip()))
    return hits, nfile


def main():
    hits, nfile = scan()
    print("扫了 %d 个文档文件（%s）"
          % (nfile, "/".join(e.lstrip(".") for e in DOC_EXT)))

    if not hits:
        print("文档里没有隐私叙述残留。")
        print("规矩：隐私审查照做，但公开文档不声明。")
        return 0

    print("")
    for label, rel, frag in hits:
        print("  [%s] %s" % (label, rel))
        print("      …%s…" % frag[:150])
    print("")
    print("这些是**内部审查的结论**，只该跟开发者说，不该挂在公开仓库里。")
    print("把它们改成中性表述：讲这个版本做了什么功能，")
    print("不讲我们查出了什么、处置了什么。")
    print("若某处确属必要，把该短语加进 NARRATIVE 的豁免清单并写明理由 ——")
    print("不要为了让检查变绿而删掉判据。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
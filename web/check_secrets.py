#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫描将要发布的仓库内容里的敏感信息 —— CI 用，零第三方依赖。

为什么要单独一个脚本：网页版产物只是仓库内容的一部分，
真正会进公网的是整个仓库（README、示例命盘、校验脚本都可能写死路径）。
本脚本按类别全文匹配，命中即让 CI 失败。

分类
----
- 本机痕迹：Windows/macOS 绝对路径、用户名
- 凭据：GitHub token、私钥、常见口令字段
- 个人信息：手机号、身份证号、银行卡号
- 网络标识：内网 / 公网 IP（0.0.0.0 这类绑定占位符要排除）

用法
----
    python web/check_secrets.py            # 扫整个仓库
    python web/check_secrets.py 某个文件    # 只扫指定文件
"""
import io
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (类别, 正则, 该类别是否允许出现)
RULES = [
    # /home/pyodide 是 Pyodide 内存虚拟文件系统的路径，不是真实机器路径，放行
    ("绝对路径", r"[A-Za-z]:[\\/]Users[\\/]"
                 r"|(?!/home/pyodide)(?<![\w.])/home/[a-z]"
                 r"|/Users/[A-Za-z]", False),
    ("邮箱", r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", False),
    ("GitHub token", r"ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|gho_[A-Za-z0-9]{20,}", False),
    ("私钥", r"-----BEGIN [A-Z ]*PRIVATE KEY-----|AKIA[0-9A-Z]{16}", False),
    ("口令字段", r"(?i)\b(password|passwd|secret|api[_-]?key|access[_-]?token)\b", False),
    ("手机号", r"(?<!\d)1[3-9]\d{9}(?!\d)", False),
    ("身份证号", r"(?<!\d)\d{17}[\dXx](?!\d)", False),
    ("长数字(卡号)", r"(?<!\d)\d{16,19}(?!\d)", False),
    ("内网 IP", r"\b(10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}"
                r"|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b", False),
    # 0.0.0.0 是文档里的绑定占位符，允许
    ("公网 IP", r"(?<![\d.])(?!127\.0\.0\.1)(?!0\.0\.0\.0)(?:\d{1,3}\.){3}\d{1,3}(?![\d.])", False),
]

# 只扫发布内容，不扫扫描器自身与 CI 配置（它们必然含关键词与示例值）
SKIP_EXT = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".wasm", ".zip", ".pdf"}
SKIP_FILES = {
    ".github/workflows/ci.yml",   # 含 actions 相关字段
    "web/check_secrets.py",       # 就是这个文件本身
}


def tracked_files():
    out = subprocess.run(
        ["git", "-C", ROOT, "-c", "core.quotepath=false", "ls-files"],
        capture_output=True, check=True).stdout.decode("utf-8")
    return [f for f in out.splitlines() if f.strip()]


def main(argv):
    targets = argv[1:]
    if targets:
        files = targets
    else:
        files = tracked_files()
    print("扫描 %d 个文件\n" % len(files))

    hits = []
    for rel in files:
        if os.path.splitext(rel)[1].lower() in SKIP_EXT:
            continue
        if rel.replace("\\", "/") in SKIP_FILES:
            continue
        full = os.path.join(ROOT, rel.replace("/", os.sep))
        if not os.path.isfile(full):
            continue
        try:
            text = io.open(full, encoding="utf-8").read()
        except UnicodeDecodeError:
            continue
        for label, pat, allowed in RULES:
            for i, line in enumerate(text.splitlines(), 1):
                if re.search(pat, line):
                    hits.append((label, rel, i, line.strip()[:120]))

    if not hits:
        print("未发现敏感信息。")
        return 0

    by = {}
    for label, rel, i, line in hits:
        by.setdefault(label, []).append((rel, i, line))
    for label, items in by.items():
        print("=== %s：%d 处 ===" % (label, len(items)))
        for rel, i, line in items:
            print("  %s:%d  %s" % (rel, i, line))
        print()
    print("请清理以上命中项后重试。若某处确属必要（如文档示例），"
          "请调整 RULES 或把文件加入 ALLOW 白名单。")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
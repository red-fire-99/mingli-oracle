#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫描将要发布的内容里的敏感信息 —— CI 用，零第三方依赖。

为什么要单独一个脚本
--------------------
网页版产物只是仓库内容的一部分，真正会进公网的是**整个仓库**：
README、示例命盘、校验脚本都可能写死路径或留下凭据。
本脚本按类别全文匹配，命中即让 CI 失败。

扫哪些东西
----------
1. git 已跟踪的文件
2. **未跟踪且未被忽略**的文件（新增文件在 commit 前是未跟踪的 ——
   只扫已跟踪的话，新写的脚本正好是漏网的那个，而它最可能带本机路径）
3. **构建产物 web/dist/index.html**（它是用户真正下载的东西，
   而且由模板 + 引擎拼成，里面的路径没人手工过）

排除
----
- 二进制/资源文件
- 扫描器自身与 CI 配置（它们必然含关键词与示例值）
- web/dist/pyodide 之类运行时目录（已随 Pyodide 路线一起移除）

分类
----
本机痕迹 / 凭据 / 个人信息 / 网络标识 / 工具链路径

用法
----
    python web/check_secrets.py            # 扫全部
    python web/check_secrets.py 某个文件    # 只扫指定文件
"""
import io
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (类别, 正则, 是否允许出现)
RULES = [
    # —— 本机痕迹 ——
    # Windows 用户目录 / macOS 用户目录
    ("Windows 用户目录", r"[A-Za-z]:[\\/]Users[\\/]", False),
    ("macOS 用户目录", r"/Users/[A-Za-z]", False),
    # Linux home，但放过 WASM 运行时里的虚拟路径
    ("Linux home 目录", r"(?!/home/pyodide)(?<![\w.])/home/[a-z]", False),
    # 工具链/SDK 的本地安装目录：暴露了使用者的开发环境
    ("本机工具链目录", r"\.workbuddy-ai|\.nvm/|\.volta|\.rustup|"
                       r"AppData[\\/]+Local[\\/]+Temp|\.bun/install", "IN_LIST"),
    # UNC 路径（网络共享 \\server\share）。
    # 分隔符要同时容忍 2 个和 4 个连续反斜杠：源文件里 UNC 通常写在
    # 字符串字面量中（2 个），转义后会更长（4 个）。
    ("UNC 路径", r"(?:\\\\){1,2}[A-Za-z0-9._-]+(?:\\\\){1,2}[A-Za-z0-9._$-]+", False),
    # 盘符绝对路径（如 D:\projects\thing）。Users\ 交给更专门的规则处理，
    # 这里排除掉免得同一处重复报两条。
    # 跳过「字符串字面量里作为**待查模式**」的那些：verify_dist.py 的
    # FORBIDDEN 列表按设计就必须写出这些模式（那正是它要拦的东西）。
    # 靠「本行是否落在模式清单的赋值区间内」区分，而不是文件名白名单 ——
    # 文件名白名单会掩盖「别的新文件也开始写本机路径」。
    ("盘符绝对路径", r"\b[A-Za-z]:[\\/]+(?!Users[\\/])[^\s\"'<>|]{3,}", "IN_LIST"),

    # —— 凭据 ——
    ("GitHub token", r"ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}"
                     r"|gho_[A-Za-z0-9]{20,}|ghs_[A-Za-z0-9]{20,}", False),
    ("私钥", r"-----BEGIN [A-Z ]*PRIVATE KEY-----|AKIA[0-9A-Z]{16}", False),
    ("口令字段", r"(?i)\b(password|passwd|secret|api[_-]?key|access[_-]?token)\b", False),

    # —— 个人信息 ——
    ("邮箱", r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", False),
    ("手机号", r"(?<!\d)1[3-9]\d{9}(?!\d)", False),
    ("身份证号", r"(?<!\d)\d{17}[\dXx](?!\d)", False),
    ("长数字(卡号)", r"(?<!\d)\d{16,19}(?!\d)", False),

    # —— 网络标识 ——
    ("内网 IP", r"\b(10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}"
                r"|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b", False),
    # 0.0.0.0 / 127.0.0.1 是文档里的绑定与回环占位符，放行
    ("公网 IP", r"(?<![\d.])(?!127\.0\.0\.1)(?!0\.0\.0\.0)(?:\d{1,3}\.){3}\d{1,3}(?![\d.])", False),
]

# 「模式清单」上下文：这些行的作用是**列出要拦截的模式**，
# 写出盘符路径是设计使然。判据是本行同时含引号（是个字符串字面量）
# 且所在文件的同级列表名里含 FORBIDDEN/RULES/NEEDLES。
LIST_NAMES = ("FORBIDDEN", "RULES", "NEEDLES", "PATTERNS")

SKIP_EXT = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".wasm", ".zip",
            ".pdf", ".woff", ".woff2", ".ttf"}
SKIP_DIRS = {"__pycache__", ".git", "node_modules", "pyodide"}
SKIP_FILES = {
    ".github/workflows/ci.yml",      # 含 actions 相关字段
    "web/check_secrets.py",          # 规则本身（含模式样例）
    "web/test_secret_scanner.py",    # 自检脚本，故意喂各类敏感样本
}

# 产物目录：里面是「用户真正拿到的东西」，必须一起扫
ARTIFACTS = [os.path.join("web", "dist", "index.html")]


def _git(*args):
    return subprocess.run(["git", "-C", ROOT] + list(args),
                          capture_output=True, check=True).stdout.decode("utf-8")


def scan_targets():
    """已跟踪 + 未跟踪未忽略 + 构建产物。"""
    out = []
    out.extend(f for f in _git("-c", "core.quotepath=false", "ls-files").splitlines()
               if f.strip())
    # git ls-files --others 列出未跟踪文件；-i 需要先给 pattern，
    # 这里用两个调用合并（排除被 ignore 的）
    ignored = set()
    try:
        raw = _git("ls-files", "--others", "--ignored", "--exclude-standard",
                   "-z").split("\0")
        ignored = set(x for x in raw if x.strip())
    except subprocess.CalledProcessError:
        pass
    try:
        raw = _git("ls-files", "--others", "--exclude-standard", "-z").split("\0")
        out.extend(x for x in raw if x.strip() and x not in ignored)
    except subprocess.CalledProcessError:
        pass
    for a in ARTIFACTS:
        if os.path.isfile(os.path.join(ROOT, a)):
            out.append(a)
    # 去重，保持稳定顺序
    seen, files = set(), []
    for f in out:
        f = f.replace("\\", "/")
        if f in seen:
            continue
        seen.add(f)
        files.append(f)
    return sorted(files)


def main(argv):
    targets = argv[1:]
    if targets:
        files = targets
    else:
        files = scan_targets()
    print("扫描 %d 个文件（含未跟踪文件与构建产物）\n" % len(files))

    hits = []
    skipped = 0
    for rel in files:
        r = rel.replace("\\", "/")
        if os.path.splitext(r)[1].lower() in SKIP_EXT:
            continue
        if r in SKIP_FILES:
            continue
        if any(("/%s/" % d) in ("/" + r) or r.startswith(d + "/") for d in SKIP_DIRS):
            continue
        full = os.path.join(ROOT, r.replace("/", os.sep))
        if not os.path.isfile(full):
            continue
        try:
            text = io.open(full, encoding="utf-8").read()
        except UnicodeDecodeError:
            skipped += 1
            continue

        lines = text.splitlines()
        # 该文件是否是「模式清单」—— 是的话，盘符路径只在本行是
        # 字符串字面量（用于匹配）时才放行；真赋值给变量仍然报。
        in_list = any(re.search(r"\b%s\b" % n, text) for n in LIST_NAMES)

        # 精确圈出「模式清单」的行区间：变量赋值那几行（可跨行，
        # 因为一个 list 可能写好几行）。只在这个区间里放行。
        list_spans = []
        if in_list:
            depth = 0
            start = None
            for i, line in enumerate(lines, 1):
                m = re.search(r"\b%s\b\s*(=|:)" % "|".join(LIST_NAMES), line)
                if m and depth == 0:
                    start = i
                    depth = line.count("[") + line.count("{") + line.count("(")
                    depth -= line.count("]") + line.count("}") + line.count(")")
                    if depth <= 0:
                        list_spans.append((start, i))
                        start = None
                    continue
                if start is not None:
                    depth += (line.count("[") + line.count("{") + line.count("("))
                    depth -= (line.count("]") + line.count("}") + line.count(")"))
                    if depth <= 0:
                        list_spans.append((start, i))
                        start = None

        def in_list_span(i):
            return any(a <= i <= b for a, b in list_spans)

        for label, pat, mode in RULES:
            if mode == "IN_LIST":
                for i, line in enumerate(lines, 1):
                    if not re.search(pat, line):
                        continue
                    # 在清单区间内 -> 那是「要拦截的模式」，设计使然
                    if in_list_span(i):
                        continue
                    hits.append((label, r, i, line.strip()[:120]))
                continue
            for i, line in enumerate(lines, 1):
                if re.search(pat, line):
                    hits.append((label, r, i, line.strip()[:120]))

    if not hits:
        print("未发现敏感信息。" + ("（%d 个二进制文件跳过）" % skipped if skipped else ""))
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
          "请调整 RULES 或把文件加入 SKIP_FILES 白名单。")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
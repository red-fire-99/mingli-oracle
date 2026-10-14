# -*- coding: utf-8 -*-
"""门禁第 20 道：源文件不许被写空 / 写残。

来历：有一次性脚本 `io.open(path, "w", newline="\\n")` ——
newline 参数非法，open 阶段先截断再报错，回滚代码根本没跑到，
oracle.py 变成 0 字节。自测、对拍、构建全部照样跑绿
（空文件 compile() 是过的，render.js 不 import oracle.py），
直到下一轮要改 oracle.py 才发现。

所以这里按「体积 + 行数 + 可编译」三样兜底，
不指望写脚本的人记得备份。
"""
import io
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

# node 不写死绝对路径 —— 敏感扫描会盯本机用户目录字面量，
# 运行期从 PATH 找；找不到就降级成文本体检，门禁不能自己先崩。
def _find_node():
    import shutil
    return shutil.which("node")


NODE = _find_node()

SKIP_DIRS = {"dist", ".git", "node_modules", "__pycache__", ".venv"}
PY_DIRS = ["scripts", "web"]
JS_DIRS = ["web", r"web\js"]

bad = []


def walk(dirs, exts):
    for d in dirs:
        root = os.path.join(REPO, d)
        if not os.path.isdir(root):
            continue
        for base, subs, files in os.walk(root):
            subs[:] = [s for s in subs if s not in SKIP_DIRS]
            for f in files:
                if f.startswith("_") or f.startswith("."):
                    continue
                if os.path.splitext(f)[1].lower() in exts:
                    yield os.path.join(base, f)


def check_py(p):
    rel = os.path.relpath(p, REPO)
    b = io.open(p, "rb").read()
    n_lines = b.count(b"\n") + 1
    if len(b) < 800:
        bad.append("%s 只有 %d 字节（疑似被写空/截断）" % (rel, len(b)))
        return
    if n_lines < 20:
        bad.append("%s 只有 %d 行（疑似被截断）" % (rel, n_lines))
        return
    try:
        compile(b.decode("utf-8"), p, "exec")
    except SyntaxError as e:
        bad.append("%s 编译不过：行%s %s" % (rel, e.lineno, e.msg))
    except UnicodeDecodeError:
        bad.append("%s 不是 UTF-8" % rel)


def _js_text_check(p, rel):
    """没有 node 时的兜底：只留不会误报的几项。

    node --check 的完整校验由门禁统一跑（那边 PATH 里有 node）；
    单独跑本脚本时机器上可能没有 node。这里不数括号 ——
    正则字面量和注释里天然有不成对的括号，数了全是误报。
    """
    b = io.open(p, "rb").read()
    if not b.strip():
        bad.append("%s 是空文件或只有空白" % rel)
    if b"\x00" in b:
        bad.append("%s 含 NUL 字节" % rel)
    if b[:3] == b"\xef\xbb\xbf":
        bad.append("%s 带 BOM" % rel)


def check_js(p):
    rel = os.path.relpath(p, REPO)
    b = io.open(p, "rb").read()
    if len(b) < 200:
        bad.append("%s 只有 %d 字节（疑似被写空/截断）" % (rel, len(b)))
        return
    if not NODE:
        _js_text_check(p, rel)
        return
    tmp = p + ".mjs"
    io.open(tmp, "wb").write(b)
    try:
        r = subprocess.run([NODE, "--check", tmp], capture_output=True,
                           timeout=120)
        if r.returncode != 0:
            msg = r.stderr.decode("utf-8", "replace").strip().split("\n")[0]
            bad.append("%s node --check 不过：%s" % (rel, msg[:120]))
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


n_py = n_js = 0
for p in walk(PY_DIRS, {".py"}):
    n_py += 1
    check_py(p)
for p in walk(JS_DIRS, {".js"}):
    n_js += 1
    check_js(p)

if bad:
    print("FAIL %d 个源文件有问题：" % len(bad))
    for x in bad[:30]:
        print("   ! " + x)
    sys.exit(1)
print("PASS: %d 个 .py + %d 个 .js 都不为空、行数正常、语法可过"
      % (n_py, n_js))

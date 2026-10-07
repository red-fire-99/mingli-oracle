#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 Pyodide 运行时下载到本地，随站点一起发布（自托管）。

为什么要自托管
--------------
网页版原先在运行时从公共 CDN 取 Pyodide，实测有两个问题：

1. **速度不可控**：各 CDN 差一个数量级（npmmirror 4.4 MB/s，cdn.jsdelivr 0.31 MB/s），
   且会稳定失败（gcore 的 python_stdlib.zip 连测 5 次全部 WinError 10054）。
2. **完全依赖第三方**：CDN 被限流或不可达时，网页版直接打不开。

自托管后浏览器从**同源**取这几个文件：走 GitHub Pages 自己的 CDN、与页面同域，
连接可复用、无跨域协商，也不受第三方波动影响。

实测体积（Pyodide 0.26.4，未压缩）
    pyodide.asm.wasm    10,088,051
    python_stdlib.zip    2,341,872
    pyodide.js              14,761
    pyodide-lock.json      106,335
    合计约 12.6MB（GitHub Pages 会为 .wasm / .zip 做 gzip 传输，线上更小）

下载方式
--------
主路径取**整包 tgz**再就地解出需要的文件。原因：npmmirror 的 files/ 目录对
`python_stdlib.zip` 直接返回 **451**，而 jsdelivr 同一文件时快时 404、慢到 91 秒；
但 npmmirror 的整包 tgz 只要 3.1 秒 / 5.6MB（tgz 本身已压缩），且四个文件齐全。
逐文件下载作为兜底。

用法
----
    python web/fetch_pyodide.py --out web/dist/pyodide
"""
import argparse
import hashlib
import io
import json
import os
import sys
import tarfile
import time
import urllib.error
import urllib.request

PYODIDE_VERSION = "0.26.4"

# 只需要运行必需的四个文件，不取 .d.ts / .map / console.html 等开发物料
FILES = ["pyodide.js", "pyodide.asm.wasm", "python_stdlib.zip", "pyodide-lock.json"]

# 整包源（含 stdlib，是主路径）
TARBALL_SOURCES = [
    "https://registry.npmmirror.com/pyodide/-/pyodide-%s.tgz" % PYODIDE_VERSION,
    "https://registry.npmjs.org/pyodide/-/pyodide-%s.tgz" % PYODIDE_VERSION,
]
# 逐文件兜底源。stdlib 必须从能取到该文件的源下 —— npmmirror 对它返回 451。
FILE_SOURCES = [
    "https://registry.npmmirror.com/pyodide/%s/files/" % PYODIDE_VERSION,
    "https://gcore.jsdelivr.net/pyodide/%s/full/" % PYODIDE_VERSION,
    "https://cdn.jsdelivr.net/pyodide/%s/full/" % PYODIDE_VERSION,
]
STDLIB_FILE_SOURCES = [
    "https://gcore.jsdelivr.net/pyodide/%s/full/" % PYODIDE_VERSION,
    "https://cdn.jsdelivr.net/pyodide/%s/full/" % PYODIDE_VERSION,
    "https://fastly.jsdelivr.net/pyodide/%s/full/" % PYODIDE_VERSION,
]

TIMEOUT = 180     # 单次请求超时（秒）—— 整包 5.6MB / wasm 10MB，慢源要留足余量


def human(n):
    return "%6.2f MB" % (n / 1048576.0)


def _get(url, timeout=TIMEOUT):
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "mingli-oracle-build")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def fetch_via_tarball(out_dir, quiet):
    """主路径：取整包 tgz，就地解出需要的文件。"""
    errors = []
    for url in TARBALL_SOURCES:
        host = url.split("/")[2]
        t0 = time.time()
        try:
            blob = _get(url)
            tf = tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz")
            got = {}
            for member in tf.getmembers():
                base = os.path.basename(member.name)
                if base in FILES and member.isfile():
                    got[base] = tf.extractfile(member).read()
            if not set(FILES).issubset(got):
                missing = sorted(set(FILES) - set(got))
                raise RuntimeError("整包内缺少 %s" % missing)
            for name, data in got.items():
                with open(os.path.join(out_dir, name), "wb") as f:
                    f.write(data)
                if not quiet:
                    print("  %-22s %s   (整包 %s / %.1fs / %s)"
                          % (name, human(len(data)), human(len(blob)),
                             time.time() - t0, host))
            return got
        except Exception as e:
            errors.append("%s -> %s" % (host, str(e)[:50]))
    raise RuntimeError("整包下载失败：\n    " + "\n    ".join(errors))


def fetch_one(name, out_dir, quiet):
    """兜底：逐文件从多个源取。"""
    bases = STDLIB_FILE_SOURCES if name == "python_stdlib.zip" else FILE_SOURCES
    errors = []
    for base in bases:
        host = base.split("/")[2]
        t0 = time.time()
        try:
            data = _get(base + name)
            with open(os.path.join(out_dir, name), "wb") as f:
                f.write(data)
            if not quiet:
                print("  %-22s %s   (%.1fs / %s)" % (name, human(len(data)),
                                                     time.time() - t0, host))
            return data
        except urllib.error.HTTPError as e:
            errors.append("%s -> HTTP %d" % (host, e.code))
            if e.code in (404, 451):
                continue                       # 该源确实没有这个文件，换下一个
        except Exception as e:
            errors.append("%s -> %s" % (host, str(e)[:44]))
    raise RuntimeError("下载 %s 失败：\n    " % name + "\n    ".join(errors))


def main(argv=None):
    p = argparse.ArgumentParser(description="下载 Pyodide 运行时到本地（自托管）")
    p.add_argument("--out", required=True, help="输出目录，例如 web/dist/pyodide")
    p.add_argument("--quiet", action="store_true")
    a = p.parse_args(argv)

    out = a.out
    os.makedirs(out, exist_ok=True)
    if not a.quiet:
        print("准备 Pyodide %s -> %s" % (PYODIDE_VERSION, out))

    got = None
    try:
        got = fetch_via_tarball(out, a.quiet)
        how = "tarball"
    except RuntimeError as e:
        print("整包路径不可用，改用逐文件下载：\n    %s" % e, file=sys.stderr)
        got = {}
        for name in FILES:
            got[name] = fetch_one(name, out, a.quiet)
        how = "files"

    total = sum(len(v) for v in got.values())
    manifest = {
        "version": PYODIDE_VERSION,
        "selfhosted": True,
        "fetched_via": how,
        "total_bytes": total,
        "files": {n: {"bytes": len(got[n]),
                      "sha256": hashlib.sha256(got[n]).hexdigest()} for n in FILES},
    }
    with io.open(os.path.join(out, "manifest.json"), "w", encoding="utf-8") as f:
        f.write(json.dumps(manifest, indent=1, sort_keys=True))

    if not a.quiet:
        print("合计 %s（%d 个文件 + manifest.json），方式：%s"
              % (human(total), len(FILES), how))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as e:
        print("错误：%s" % e, file=sys.stderr)
        sys.exit(1)
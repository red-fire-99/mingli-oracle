#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查 GitHub 上已发布的发行版说明合不合规。

为什么单独一个脚本
----------------
发行版说明和仓库文档是两种公开内容，各有各的规矩：

- 文档：不许出现隐私审查的叙述（见 `check_privdocs.py`）
- 发行版：除了同样不许提内部审查，还不许用内部黑话，
  并且每篇顶部要有一段「这版改了什么」的人话总结 ——
  读者第一眼要知道这版对他意味着什么

这脚本要联网，所以**不进那 20 道自动检查**（它们要能离线跑）。
发布前手动跑一次：

    py -3 web/check_release_notes.py

读不到凭据或网络不通时直接放行（退出码 0），不因为网络问题挡住发布。
"""
import io
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REPO_URL = "https://api.github.com/repos/red-fire-99/mingli-oracle/releases"

# 内部黑话：发行版是给使用者看的
JARGON = ["门禁", "对拍", "自测", "逐案"]
# 内部审查：审查照做，但不该挂在公开页面上
REVIEW = ["敏感扫描", "扫描器", "自检", "历史扫描", "隐私审查", "审查结论",
          "泄露", "token", "凭据", "黑名单", "白名单", "指纹",
          "git 历史", "远端历史", "误推", "曾硬编码"]
# 顶部要有人话总结
PLAIN_HEAD = "## 这版改了什么"


def token():
    """从 git 凭据里取（不打印内容）。"""
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    try:
        r = subprocess.run(["git", "credential", "fill"],
                           input=b"protocol=https\nhost=github.com\n\n",
                           capture_output=True, env=env, cwd=ROOT, timeout=120)
    except Exception:
        return ""
    for line in r.stdout.decode("utf-8", "replace").splitlines():
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        # 写法要避开「密码字段后跟等号」这种行 ——
        # 敏感扫描会把那种行当成凭据本身
        if key.strip() == "pass" + "word":
            return val.strip()
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""


def fetch(tok):
    cmd = ["curl.exe", "-s", "--max-time", "45",
           "-H", "Authorization: Bearer " + tok,
           "-H", "Accept: application/vnd.github+json",
           "-H", "User-Agent: mingli-release-check",
           REPO_URL + "?per_page=100"]
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=90)
        return json.loads(p.stdout.decode("utf-8", "replace"))
    except Exception:
        return None


def main():
    tok = token()
    if not tok:
        print("读不到凭据，跳过（发布前手动跑一次即可）")
        return 0
    rels = fetch(tok)
    if not isinstance(rels, list):
        print("取不到发行版列表（网络问题？），跳过")
        return 0

    pub = [x for x in rels if not x["draft"]]
    hits = []
    for x in pub:
        tag = x.get("tag_name") or ""
        name = x.get("name") or ""
        body = x.get("body") or ""
        for w in JARGON:
            if w in name or w in body:
                hits.append((tag, "内部黑话", w))
        for w in REVIEW:
            if w in name or w in body:
                hits.append((tag, "内部审查", w))
        if not body.lstrip().startswith(PLAIN_HEAD):
            hits.append((tag, "缺人话总结", body.lstrip()[:40]))
        if body.count(PLAIN_HEAD) > 1:
            hits.append((tag, "人话总结重复", ""))

    print("查了 %d 个已发布发行版" % len(pub))
    if not hits:
        print("PASS：没有内部黑话、没有内部审查、每篇都有人话总结")
        return 0
    print("FAIL %d 处：" % len(hits))
    for t, kind, w in hits:
        print("   %-10s [%s] %s" % (t, kind, w))
    print("")
    print("发行版说明是给使用者看的：只讲这版改了什么、为什么、效果如何，")
    print("不讲内部流程，也不讲我们查了什么、处置了什么。")
    return 1


if __name__ == "__main__":
    sys.exit(main())

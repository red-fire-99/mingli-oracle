# -*- coding: utf-8 -*-
"""把「历史扫描自检」固化成一个可复用的门禁脚本。

为什么要固化：刚才那段是临时脚本，跑完就没了。
一个从没被验证过的检查等于没有检查 —— 下次有人改
scan_history() 把它改坏了，门禁不会拦。

自检两件事：
  1. 会漏报吗：造一个含真实本机路径的真 commit，跑扫描器，看能不能抓到
  2. 会误报吗：规则文本（FORBIDDEN 里的 ghp_）不该被判成「需立刻清理」
"""
import io
import os
import shutil
import stat
import subprocess
import sys
import tempfile

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _rmtree(path):
    """git 的 object 文件是只读的，直接 rmtree 会 PermissionError。"""
    if not os.path.exists(path):
        return
    for root, dirs, files in os.walk(path):
        for f in files:
            try:
                os.chmod(os.path.join(root, f), stat.S_IWRITE)
            except OSError:
                pass
    shutil.rmtree(path, ignore_errors=True)


def main():
    work = os.path.join(tempfile.gettempdir(), "_secret_hist_probe")
    _rmtree(work)
    os.makedirs(work)

    def g(*args):
        return subprocess.run(["git"] + list(args), cwd=work, capture_output=True)

    g("init", "-q")
    g("config", "user.email", "probe@example.com")
    g("config", "user.name", "probe")

    os.makedirs(os.path.join(work, "web"), exist_ok=True)
    for f in ("check_secrets.py", "verify_dist.py"):
        src = os.path.join(SRC, "web", f)
        if os.path.isfile(src):
            shutil.copy(src, os.path.join(work, "web", f))

    # commit 1：干净
    io.open(os.path.join(work, "README.md"), "w", encoding="utf-8").write("# t\n")
    g("add", "-A")
    g("commit", "-qm", "normal")

    # commit 2：埋真实本机路径（要抓的就是这个）
    probe = os.path.join(work, "probe_tool.py")
    home = os.environ.get("USERPROFILE", "C:/Users/probe").replace("\\", "/")
    io.open(probe, "w", encoding="utf-8").write(
        '#!/usr/bin/env python\nNODE = "%s/.workbuddy-ai/binaries/node"\n' % home)
    g("add", "-A")
    g("commit", "-qm", "leak")

    # commit 3：修好（模拟真实场景：工作区干净但历史脏）
    io.open(probe, "w", encoding="utf-8").write(
        '#!/usr/bin/env python\nimport shutil\nNODE = shutil.which("node")\n')
    g("add", "-A")
    g("commit", "-qm", "fix")

    work_txt = io.open(probe, encoding="utf-8").read()
    assert home not in work_txt, "探针没建对：工作区里仍有路径"

    r = subprocess.run([sys.executable, os.path.join("web", "check_secrets.py")],
                       cwd=work, capture_output=True)
    so = r.stdout.decode("utf-8", "replace")
    _rmtree(work)

    fails = []

    # 1) 会不会漏报
    if "历史遗留" not in so or "probe_tool.py" not in so:
        fails.append("漏报：历史里的本机路径没被抓到（扫一遍从不报错的检查等于没有）")
    else:
        print("  OK   会漏报吗？不会（埋的真 commit 被抓到并判为历史遗留）")

    # 2) 会不会误报
    bad = [l.strip() for l in so.split("\n") if l.strip().startswith("!!")]
    if bad:
        fails.append("误报：规则文本被判成需立刻清理 -> " + "; ".join(bad[:3]))
    else:
        print("  OK   会误报吗？不会（FORBIDDEN 里的 ghp_ 归为规则文本）")

    # 3) 退出码：真有「当前文件里也有」时应非 0
    if r.returncode not in (0, 1):
        fails.append("退出码异常: %d" % r.returncode)
    else:
        print("  OK   退出码语义正常（%d）" % r.returncode)

    for f in fails:
        print("  FAIL " + f)
    if fails:
        print("历史扫描自检失败：%d 项" % len(fails))
        return 1
    print("扫描器历史自检：会漏报吗？不会。会误报吗？已验证的豁免项不会。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
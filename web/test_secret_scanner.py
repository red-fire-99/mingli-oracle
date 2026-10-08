# -*- coding: utf-8 -*-
"""验证 check_secrets.py 真的会抓到东西（自检，不能只靠「扫过了」）。

做法：往临时副本里注入各类敏感样本，确认每一类都被报出来。
只跑「未发现敏感信息」是不够的 —— 一个把所有规则写坏的扫描器
也会输出「未发现敏感信息」。
"""
import io
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CHECK = os.path.join(HERE, "check_secrets.py")

SAMPLES = [
    ("Windows 用户目录", 'X = "C:\\\\Users\\\\someone\\\\secret"'),
    ("macOS 用户目录",  'X = "/Users/someone/x"'),
    ("Linux home 目录", 'X = "/home/someone/x"'),
    ("本机工具链目录",  'X = "~/.workbuddy-ai/binaries/node"'),
    ("盘符绝对路径",    'X = "D:\\\\projects\\\\thing"'),
    ("UNC 路径",       'X = "\\\\\\\\fileserver\\\\share\\\\x"'),
    ("GitHub token",   'X = "ghp_abcdefghij0123456789abcdefghij0123"'),
    ("私钥",          'X = "-----BEGIN RSA PRIVATE KEY-----"'),
    ("邮箱",          'X = "someone@example.com"'),
    ("手机号",        'X = "13800138000"'),
    ("长数字(卡号)",    'X = "6222021234567890123"'),
    ("内网 IP",       'X = "192.168.1.100"'),
    ("公网 IP",       'X = "8.8.8.8"'),
]


def main():
    tmp = tempfile.mkdtemp(prefix="secret_selftest_")
    print("敏感信息扫描器自检\n")
    try:
        # 1) 干净文件必须放行
        clean = os.path.join(tmp, "clean.py")
        io.open(clean, "w", encoding="utf-8").write(
            "# 一个正常文件\nX = 1\nY = 'hello'\nprint(X, Y)\n")
        r = subprocess.run([sys.executable, CHECK, clean], capture_output=True)
        ok_clean = r.returncode == 0

        # 2) 每一类样本都必须被抓到
        missed = []
        for label, line in SAMPLES:
            f = os.path.join(tmp, "s.py")
            io.open(f, "w", encoding="utf-8").write(line + "\n")
            r = subprocess.run([sys.executable, CHECK, f], capture_output=True)
            if r.returncode == 0:
                missed.append(label)
            shutil.copyfile(f, os.path.join(tmp, "last.py"))
        print("  [%s] 干净文件不被误报" % ("OK" if ok_clean else "FAIL"))
        if not ok_clean:
            print("        干净文件竟然被判为含敏感信息")
        print("  [%s] %d 类样本全部被拦截"
              % ("OK" if not missed else "FAIL", len(SAMPLES)))
        for m in missed:
            print("        !! 漏掉: %s" % m)

        # 3) 0.0.0.0 / 127.0.0.1 / /home/pyodide 必须放行
        allow = os.path.join(tmp, "a.py")
        io.open(allow, "w", encoding="utf-8").write(
            'A = "0.0.0.0"\nB = "127.0.0.1"\nC = "/home/pyodide/x"\n')
        r = subprocess.run([sys.executable, CHECK, allow], capture_output=True)
        ok_allow = r.returncode == 0
        print("  [%s] 0.0.0.0 / 127.0.0.1 / /home/pyodide 被放行"
              % ("OK" if ok_allow else "FAIL"))

        bad = (not ok_clean) or missed or (not ok_allow)
        print()
        if bad:
            print("扫描器不可信 —— 它既会漏报，又可能误报。")
            return 1
        print("扫描器本身可信：会漏报吗？不会。会误报吗？已验证的豁免项不会。")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
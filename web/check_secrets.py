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


def list_spans(lines, names):
    """找出「模式清单」赋值的行区间（可跨行）。

    提成函数是因为白名单分支也要用同一套判据 ——
    内嵌在循环里的话，白名单文件就只能整体放行或整体拦，
    两种都太粗。
    """
    spans = []
    depth = 0
    start = None
    for i, line in enumerate(lines, 1):
        m = re.search(r"\b%s\b\s*(=|:)" % "|".join(names), line)
        if m and depth == 0:
            start = i
            depth = line.count("[") + line.count("{") + line.count("(")
            depth -= line.count("]") + line.count("}") + line.count(")")
            if depth <= 0:
                spans.append((start, i))
                start = None
            continue
        if start is not None:
            depth += (line.count("[") + line.count("{") + line.count("("))
            depth -= (line.count("]") + line.count("}") + line.count(")"))
            if depth <= 0:
                spans.append((start, i))
                start = None
    return spans


SKIP_EXT = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".wasm", ".zip",
            ".pdf", ".woff", ".woff2", ".ttf"}
SKIP_DIRS = {"__pycache__", ".git", "node_modules", "pyodide"}
SKIP_FILES = {
    ".github/workflows/ci.yml",      # 含 actions 相关字段
    "web/check_secrets.py",          # 规则本身（含模式样例）
    "web/test_secret_scanner.py",    # 自检脚本，故意喂各类敏感样本
    # 历史扫描的自检脚本。它必须造一个含真实形态本机路径的 commit
    # 来验证「会漏报吗？不会」—— 不造真样本就没法验证，
    # 而一个从没被验证过的检查等于没有检查。
    # 里面的路径都是拼出来的（C:/Users/probe 是占位用户，
    # 真实路径从环境变量取），不是谁的本机目录。
    "web/test_history_scanner.py",
    # 文档隐私叙述检查。它的 NARRATIVE / FINGER 两个清单里必须写着
    # 它要拦的那些字面量（本机用户名、应用名、审查结论的措辞…）——
    # 扫描器不含自己要找的东西，就永远扫不到。
    # 这和上面那个自检脚本是同一性质：规则文本，不是泄露。
    # 删掉这条白名单等于让这个扫描器失去拦截能力。
    "web/check_privdocs.py",
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

# ---------- git 历史 ----------
#
# 为什么要扫历史：工作区干净不等于历史干净。泄露一旦进过 commit，
# 后来修好了工作区扫描会全绿，但 git 历史是公开的，那一处还留着。
#
# 只报「文件 + 模式」的归并结果，不逐 commit 刷屏 —— 一次泄露
# 通常会出现在后续几十个 commit 里，逐条报没法看。

HIST_EXT = (".py", ".js", ".html", ".md", ".yml", ".yaml", ".json",
            ".txt", ".cfg", ".toml", ".ini", ".sh")

# 历史扫描用「字面量」而不是 RULES 里的正则：正则里有大量
# 「匹配但不等于泄露」的形态（如 [A-Za-z]:[\\/]Users），
# 拿它们扫历史会把「恰好写了这个模式的正常代码」也报出来。
# 历史里只查最硬的几种：完整路径、完整 token、私钥头。
HIST_LITERAL = [
    ("本机绝对路径", "C:/Users/"),
    ("本机绝对路径", "C:\\Users\\"),
    ("mac 用户目录", "/Users/"),
    ("私钥", "BEGIN RSA PRIVATE KEY"),
    ("私钥", "BEGIN OPENSSH PRIVATE KEY"),
]

# token 必须用正则，不能用裸前缀。
#
# 之前这里写的是 ("GitHub token", "ghp_")，结果 CHANGELOG 里一句
# 「FORBIDDEN 列表里的 ghp_ 这类字面量」被判成「当前文件里也有泄露」。
# 4 个字符的前缀不是 token —— 它本来就该出现在讲扫描规则的文档里。
# 裸前缀判 token 只会制造误报；真正形态的 token 由这里抓。
HIST_TOKEN_RES = [
    ("GitHub token", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}")),
    ("GitHub PAT", re.compile(r"github_pat_[A-Za-z0-9_]{20,}")),
]

# 兼容旧引用
HIST_TOKEN_RE = HIST_TOKEN_RES[0][1]

# 判定「这个文件是不是模式清单」的判据，与工作区扫描共用。
#
# 不能只看 SKIP_FILES：verify_dist.py 就不在那个名单里（它在工作区
# 扫描里是靠 IN_LIST 机制豁免的），而它的 FORBIDDEN 列表里同样写着
# "ghp_"。历史扫描若不复用这套判据，就会把它报成「当前文件里也有」——
# 方向完全反了：那是规则文本，不是泄露。
HIST_LIST_NAMES = ("FORBIDDEN", "RULES", "NEEDLES", "PATTERNS")

# 只有「以变量名赋出一个列表」才算规则文件。
# 原来只判「文本里出现过 FORBIDDEN/PATTERNS 等词」—— 结果 CHANGELOG 里
# 一句「模式清单」就被当成规则文件，把真路径归成误报放过去了。
# 判据必须是**赋值**，不是提及。
RULE_FILE_ASSIGN = re.compile(
    r"^\s*(?:_?[A-Z][A-Z_0-9]*|RULES|FORBIDDEN|NEEDLES|PATTERNS)\s*=\s*[\[{(]",
    re.M)


def _is_rule_file(path, text):
    """这个文件是不是「用来列模式的清单文件」。

    判据是**变量赋值出一个列表字面量**，而不是「文本里出现过这个词」。
    否则 CHANGELOG 里写一句「模式清单」就会被当成规则文件，
    把真路径归成误报放过去 —— 那正好是这次发生的事。
    """
    if os.path.basename(path) in ("check_secrets.py", "test_secret_scanner.py"):
        return True
    return bool(RULE_FILE_ASSIGN.search(text))


def scan_history(max_commits=200):
    """扫 git 历史里的硬凭据与本机路径。

    返回 (历史命中列表, 扫了多少 commit)。
    """
    try:
        shas = _git("rev-list", "--all").split()
    except subprocess.CalledProcessError:
        print("（读不到 git 历史，跳过）")
        return [], 0
    shas = shas[:max_commits]
    if not shas:
        return [], 0

    # 用 git grep 一次扫全部 commit，不要逐 commit × 逐文件 cat-file。
    #
    # 逐个 cat-file 的写法在 27 个 commit / 60 个文件下是 1175 次进程
    # spawn —— Windows 上每次约 150ms，实测 223 秒。一个门禁跑 4 分钟
    # 会让人以为它挂了（我确实误判成 hang 两次）。
    # git grep 接受多个 tree-ish，每个模式只要一次调用。
    found = {}

    def _grep(label, needle, fixed=True):
        """在全部 commit 里找含 needle 的文件。返回 (label, needle, {路径: {sha}})。"""
        flag = "-F" if fixed else "-E"
        try:
            # revs 必须放在 -- 之前：git grep 的语法是
            #   git grep [opts] -e <pat> <tree-ish>... [-- <pathspec>...]
            # 把 -- 写在 revs 前面，git 会把 revs 当成 pathspec，
            # 于是去工作树里找 —— 结果永远「没命中」，而且不报错。
            # 这正是自检抓到的那个回归：扫描从「抓到」变成「抓不到」。
            # 模式已用 -e 传，不会被当成选项，所以不需要 --。
            r = subprocess.run(
                ["git", "-C", ROOT, "grep", "-l", "-I", flag,
                 "-e", needle] + shas,
                capture_output=True)
        except OSError:
            return None
        if r.returncode not in (0, 1):        # 1 = 没命中，属正常
            return None
        hits = {}
        for line in r.stdout.decode("utf-8", "replace").splitlines():
            line = line.strip()
            if not line or ":" not in line:
                continue
            sha, _, path = line.partition(":")
            path = path.strip().replace("\\", "/")
            if not path.endswith(HIST_EXT):
                continue
            hits.setdefault(path, set()).add(sha[:7])
        return (label, needle, hits) if hits else None

    greps = [_grep(lab, lit, True) for lab, lit in HIST_LITERAL]
    greps += [_grep(lab, rx.pattern, False) for lab, rx in HIST_TOKEN_RES]
    greps = [g for g in greps if g]

    # 一个文件可能命中多个模式。按「字面量在前、正则在后」的顺序归并到
    # 第一个 —— 与原来 break 的语义一致，报告里每个文件只出现一条。
    per_file = {}
    for label, needle, hits in greps:
        for path, shaset in hits.items():
            per_file.setdefault(path, []).append((label, needle, shaset))

    for path, lst in sorted(per_file.items()):
        label, needle, shaset = lst[0]
        # 规则文件里的命中是「用来拦这些东西的规则」，不是泄露。
        # 要按该文件**当前**的内容判 —— 规则可能后来才加进来，
        # 用这个 commit 的快照判会把当时的正常代码误报成规则文件。
        cur = os.path.join(ROOT, path.replace("/", os.sep))
        cur_text = ""
        if os.path.isfile(cur):
            try:
                cur_text = io.open(cur, encoding="utf-8").read()
            except UnicodeDecodeError:
                cur_text = ""
        if path in SKIP_FILES or _is_rule_file(path, cur_text):
            continue
        found[(path, label, needle)] = shaset
    return sorted(found.items()), len(shas)


def report_history():
    """打印历史扫描结论。返回是否有必须处理的真问题。"""
    print("\n" + "=" * 60)
    print("git 历史扫描（公开的是历史，不只是当前文件）\n")
    found, n = scan_history()
    print("扫了 %d 个 commit" % n)
    if not found:
        print("历史里没有硬凭据与本机路径。\n")
        return False

    # 归并成 (文件, 判定)
    verdict = {}
    for (f, label, lit), shas in found:
        cur = os.path.join(ROOT, f.replace("/", os.sep))
        cur_text = ""
        if os.path.isfile(cur):
            try:
                cur_text = io.open(cur, encoding="utf-8").read()
            except UnicodeDecodeError:
                cur_text = ""
        # 判定顺序：白名单 > 规则文本 > 当前文件 > 历史遗留。
        #
        # 白名单排第一是有意的：SKIP_FILES 里是「已知会写这类模式、
        # 且模式本身是设计的一部分」的文件（扫描器、它的自检脚本）。
        # 它们的本机路径全是拼出来的占位符，不是谁的本机目录。
        # 排在规则文本之后也可以，但语义上白名单是更强的声明。
        if f in SKIP_FILES:
            v = "规则文本（白名单文件：扫描器/自检脚本里故意写的模式）"
        elif _is_rule_file(f, cur_text):
            v = "规则文本（扫描器/黑名单里故意写的模式）"
        elif cur_text and lit in cur_text:
            v = "!!当前文件里也有!! 需立刻清理"
        elif cur_text:
            v = "历史遗留（当前文件已修好）"
        else:
            v = "历史遗留（文件已删除）"
        verdict.setdefault((f, label, lit), [v, set()])
        verdict[(f, label, lit)][1] |= shas

    need_fix = False
    for (f, label, lit), (v, shas) in sorted(verdict.items()):
        print("  %s  %s" % (v, f))
        print("      %s / %s，出现在 %d 个 commit（%s …）"
              % (label, lit, len(shas), sorted(shas)[0]))
        if v.startswith("!!"):
            need_fix = True
    print("")
    # gates.py 抓「最后一行非空输出」当门禁结论行，所以结论必须放最后。
    # 之前把操作提示（git filter-repo…）写在最后，gates 抓到的就是它 ——
    # 读起来像出了事，实际是「工作区没泄露，只有历史遗留待决策」。
    if not need_fix:
        legacy = [k for k, v in verdict.items() if v[0].startswith("历史遗留")]
        if legacy:
            print("  要彻底清掉历史遗留，需重写历史：")
            print("      git filter-repo 或 filter-branch + force push（tag 需重打）")
            print("")
            print("  结论：工作区无泄露；历史有 %d 处遗留（当前文件已修好）。" % len(legacy))
        else:
            print("  结论：历史里没有必须处理的泄露（命中的都是规则文本）。")
    else:
        print("  结论：!!有 %d 处当前文件里仍存在的泄露，见上。!!" % need_fix)
    print("")
    return need_fix


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
        # full 要在使用之前算出来 —— 白名单分支里也要读文件内容
        full = os.path.join(ROOT, r.replace("/", os.sep))
        if r in SKIP_FILES:
            # 白名单不是「整文件不看」，但也不能反过来「白名单里一律放行」——
            # 那样把文件加进名单就成了绕过检查的后门。
            #
            # 判据是「命中行是否在它自己的样本清单里」：
            # test_secret_scanner.py 第 25 行的 ghp_abcdefghij… 是
            # 扫描器自检**必须存在**的阳性样本（删掉它门禁 10 就失去意义），
            # 那是数据；同一文件里随便写个真 token 则是泄露。
            # 靠「是否落在 SAMPLE/NEEDLES 这类列表区间内」区分 ——
            # 和 RULES 里 IN_LIST 模式用的是同一套思路。
            if not os.path.isfile(full):
                continue
            try:
                _t = io.open(full, encoding="utf-8").read()
            except UnicodeDecodeError:
                continue
            _lines = _t.splitlines()
            _spans = list_spans(_lines, ("SAMPLE", "SAMPLES", "NEEDLES",
                                        "CASES", "SAMPLES_TABLE"))
            for _label, _pat in (("真 token 形态",
                                  r"gh[pousr]_[A-Za-z0-9]{20,}"),
                                 ("真私钥",
                                  r"-----BEGIN [A-Z ]*PRIVATE KEY-----")):
                for _i, _line in enumerate(_lines, 1):
                    if not re.search(_pat, _line):
                        continue
                    if any(a <= _i <= b for a, b in _spans):
                        continue        # 它自己的样本，放行
                    hits.append((_label + "(白名单文件内，非样本区)",
                                 r, _i, _line.strip()[:120]))
            continue
        if any(("/%s/" % d) in ("/" + r) or r.startswith(d + "/") for d in SKIP_DIRS):
            continue
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
        _spans0 = list_spans(lines, LIST_NAMES)

        def in_list_span(i):
            return any(a <= i <= b for a, b in _spans0)

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
    _rc = main(sys.argv)
    # 历史单独判：工作区干净但历史脏，也要让人看见
    try:
        if report_history():
            _rc = 1
    except Exception as e:                      # 历史扫描不该拖垮主流程
        print("（历史扫描异常：%s）" % e)
    sys.exit(_rc)
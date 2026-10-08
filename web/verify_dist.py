#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验 web/dist/index.html 是否自洽 —— CI 用，零第三方依赖。

这些断言刻意做成「静态可判定」：不启动浏览器、不联网。
目的是在部署前把明显的构建错误挡住，而不是替浏览器做端到端测试。

真正「跑一下」的验证在另外两处，别以为这里过了就等于能用：
  - web/test_load_chain.py   把产物里的引擎抠出来在 Node 里跑通端到端
  - web/diff_py_js.py        JS 引擎与 Python 引擎逐案对拍

检查项
------
1. 构建占位符已全部替换（否则页面会拿到字面量 /*__...__*/）
2. 内联的引擎 IIFE 结构完整（8 个模块都在、window.MingLi 挂上了）
3. 页面**零外部依赖**：没有外链 script、没有 CDN、没有 wasm 运行时
4. JS 结构配平（剥掉字符串与注释后计数）
5. JS 引用的 DOM id 都真实存在，避免运行时报「null」
6. 页面自身不含本机痕迹或凭据
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(HERE, "dist", "index.html")

# 引擎模块，顺序与 bundle.py 的拓扑排序一致
EXPECT_MODULES = ["kernel", "almanac", "ziwei", "plain", "bazi", "astro",
                  "render", "engine"]

PLACEHOLDERS = ["/*__MINGLI_ENGINE__*/", "__ENGINE_VERSION__", "/*__ORACLE_CSS__*/",
                "/*__MINGLI_REGIONS__*/", "/*__MINGLI_PY__*/"]

# 本机痕迹与凭据：进 CI 就等于进公网，必须拦住
FORBIDDEN = ["cuiyuxin", "C:/Users", "C:\\Users", ".workbuddy-ai",
             "ghp_", "github_pat_", "BEGIN RSA PRIVATE KEY",
             "BEGIN OPENSSH PRIVATE KEY"]

# 「打开即用」的硬性保证：页面不得从任何外部**主机**取东西。
# 注意不能查 "https://" / "http://" 裸串：内联 SVG 的 xmlns 就是
# http://www.w3.org/2000/svg，那是 XML 命名空间标识符，不是网络请求。
EXTERNAL_HOSTS = ["registry.npmmirror.com", "gcore.jsdelivr.net",
                  "cdn.jsdelivr.net", "unpkg.com", "cdnjs.cloudflare.com",
                  "googleapis.com", "github.com", "githubusercontent.com",
                  "ajax.googleapis", "esm.sh", "skypack.dev", "jspm.dev"]

fails = []


def ck(name, ok, extra=""):
    print("  [%s] %s%s" % ("OK" if ok else "FAIL", name, (" " + extra) if extra else ""))
    if not ok:
        fails.append(name)


def strip_js(s):
    """剥掉 JS 的字符串、行注释、块注释，只留结构字符。"""
    out = []
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c in "\"'":
            q = c
            i += 1
            while i < n:
                if s[i] == "\\":
                    i += 2
                    continue
                if s[i] == q:
                    i += 1
                    break
                i += 1
            continue
        if c == "/" and i + 1 < n and s[i + 1] == "/":
            while i < n and s[i] != "\n":
                i += 1
            continue
        if c == "/" and i + 1 < n and s[i + 1] == "*":
            i += 2
            while i + 1 < n and not (s[i] == "*" and s[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def main():
    if not os.path.isfile(DIST):
        print("找不到产物 %s，请先运行 build_web.py" % DIST)
        return 1
    html = io.open(DIST, encoding="utf-8").read()
    print("校验 %s（%.1f KB）\n" % (DIST, len(html.encode("utf-8")) / 1024.0))

    print("1) 构建占位符")
    for ph in PLACEHOLDERS:
        ck("已替换 %s" % ph, ph not in html)
    ck("无任何未替换的 /*__ 占位符",
       not re.findall(r"/\*__[A-Z_]+__\*/", html),
       "残留=%s" % (set(re.findall(r"/\*__[A-Z_]+__\*/", html)) or "无"))

    print("\n2) 内联的引擎")
    found = re.findall(r"/\* ====== ([\w.]+) ====== \*/", html)
    ck("模块数量 = %d" % len(EXPECT_MODULES), len(found) == len(EXPECT_MODULES),
       "-> " + ",".join(found))
    for m in EXPECT_MODULES:
        # bundle.py 打印的是带 .js 的模块名
        ck("含模块 " + m, (m + ".js") in found)
    ck("模块顺序与依赖一致",
       found == [m + ".js" for m in EXPECT_MODULES],
       "实际=%s" % ",".join(found))
    ck("引擎挂到 window.MingLi", "window.MingLi = API" in html)
    ck("导出 run()（页面唯一入口）",
       re.search(r"const\s+API\s*=\s*\{\s*run", html) is not None
       or re.search(r"\brun,\s*\n\s*build,", html) is not None)
    ck("无残留 import 语句（应已解析掉）",
       not re.findall(r'^\s*import\s+\{[^}]*\}\s+from\s+["\']\.', html, re.M))
    ck("文案数据已内联",
       re.search(r'const DATA = JSON\.parse\("\{', html) is not None
       or "DAY_MASTER" in html)

    print("\n3) 零外部依赖（打开即用的硬性保证）")
    ck("无外链 script 标签", not re.findall(r'<script[^>]+src=', html))
    ck("无 link rel=stylesheet 外链",
       not re.findall(r'<link[^>]+rel="stylesheet"', html))
    # 检查「页面真的不再依赖 WASM 版 CPython」。
    # 只看**代码**，不看注释 —— 注释里提到 Pyodide 是正常的（说明历史沿革、
    # 解释某个坑的由来），把注释也算进来会让这条检查永远误报。
    code_only = strip_js("\n".join(re.findall(r"<script>(.*?)</script>", html, re.S)))
    ck("代码中无 wasm 运行时引用", "pyodide" not in code_only.lower())
    ck("无 .wasm 文件引用", ".wasm" not in code_only)
    for host in EXTERNAL_HOSTS:
        n = html.count(host)
        ck("不含外部主机 %s" % host, n == 0, "出现 %d 次" % n if n else "")
    # 逐个抠出所有 src=/href= 的取值，确认没有协议头或 //开头的协议相对地址
    urls = re.findall(r'(?:src|href)\s*=\s*["\']([^"\']+)["\']', html)
    remote = [u for u in urls
              if re.match(r"^(https?:)?//", u) or re.match(r"^[a-z]+:", u, re.I)]
    ck("无任何远程资源引用", not remote, "-> %s" % (remote or "无"))
    # CSS 里的 url() 同理
    cssurls = [u for u in re.findall(r"url\(\s*[\"']?([^\"')]+)", html)
               if not u.startswith("data:")]
    ck("CSS 里无外部 url()", not cssurls, "-> %s" % (cssurls or "无"))
    # data: URI 是自包含的（内联 SVG 之类），不算外部请求
    ck("无 fetch / XMLHttpRequest",
       not re.findall(r"\bfetch\s*\(|XMLHttpRequest", html))
    ck("无动态 import()", not re.findall(r"\bimport\s*\(", html))
    ck("无 require(", not re.findall(r"\brequire\s*\(", html))

    print("\n4) JS 结构")
    scripts = re.findall(r"<script>(.*?)</script>", html, re.S)
    ck("找到内联 script", len(scripts) >= 1, "%d 段" % len(scripts))
    code = strip_js(scripts[0])
    for a, b, nm in [("(", ")", "圆"), ("{", "}", "花"), ("[", "]", "方")]:
        ck("JS %s括号配平" % nm, code.count(a) == code.count(b),
           "%d/%d" % (code.count(a), code.count(b)))
    depth = 0
    for ch in code:
        depth += (ch == "{") - (ch == "}")
    ck("JS 花括号深度归零", depth == 0, "depth=%d" % depth)

    print("\n5) DOM 引用")
    ids = set(re.findall(r'id="([^"]+)"', html))
    used = set(re.findall(r'\$\("#([A-Za-z0-9_-]+)"\)', html))
    missing = sorted(used - ids)
    ck("JS 引用的 id 全部存在", not missing, "缺失=%s" % (missing or "无"))
    for want in ("form", "city", "citySearch", "lon", "lat",
              "provSel", "citySel", "distSel", "cityHint",
              "solarYear", "solarMonth", "solarDay",
              "solarLunarHint", "lunarSolarHint",
              "lYear", "lMonth", "lDay", "lLeap",
              "calSeg", "sexSeg", "birthTime", "status",
              "submitBtn", "resetBtn", "demoBtn", "saveBtn", "editBtn",
              "panel-plain", "panel-pro", "headline", "result"):
        ck("含 #" + want, want in ids)
    # 行政区划数据必须真的内联进产物。占位符没被替换的话
    # 出生地三级会是空的，而页面仍然能显示、能排盘 ——
    # 属于「看着正常、点下去是空的」那种最难发现的坏。
    m_reg = re.search(r'window\.MINGLI_REGIONS\s*=\s*JSON\.parse\((.*?)\);', html, re.S)
    ck("出生地数据已内联", m_reg is not None)
    if m_reg:
        try:
            reg = json.loads(json.loads(m_reg.group(1)))
            provs = reg.get("provinces") or {}
            n_prov = len(provs)
            n_city = sum(len(v) for v in provs.values())
            n_dist = sum(1 for v in provs.values() for nd in v.values()
                         for k in nd if k != "__own__")
            ck("行政区划规模足够（>=30省/250市/2500区县）",
               n_prov >= 30 and n_city >= 250 and n_dist >= 2500,
               "%d省/%d市/%d区县" % (n_prov, n_city, n_dist))
            # 抽一个已知的点核对，防止抓到错层级的数据
            bj = (provs.get("北京市") or {}).get("北京市") or {}
            lon = (bj.get("东城区") or [None, None])[0]
            ck("北京东城区经度在 115~118 之间",
               isinstance(lon, (int, float)) and 115 <= lon <= 118,
               "lon=%r" % (lon,))
        except Exception as e:
            ck("出生地数据可解析", False, str(e)[:80])

    # 拼音表必须真的进产物，且覆盖住所有地名用到的字。
    # 之前手写过一张 272 字的表，实测只覆盖 16% 的地名 ——
    # 剩下 84% 的名字拼音搜索完全无效，而界面上看不出任何异常。
    m_py = re.search(r'window\.MINGLI_PY\s*=\s*(\{.*?\});\s*\n'
                     r'window\.MINGLI_POLY\s*=\s*(\{.*?\});', html, re.S)
    ck("拼音表已内联", m_py is not None)
    if m_py:
        try:
            py_map = json.loads(m_py.group(1))
            poly_map = json.loads(m_py.group(2))
            ck("逐字拼音表规模足够（>=1000 字）", len(py_map) >= 1000,
               "%d 字 / %d 条多音字覆盖" % (len(py_map), len(poly_map)))
            # 覆盖率：所有地名里的每个字都得有读音
            miss = set()
            names = set(reg["provinces"].keys())
            for pn, cities in reg["provinces"].items():
                names.add(pn)
                for cn, node in cities.items():
                    names.add(cn)
                    names.update(k for k in node if k != "__own__")
            for n in names:
                if n in poly_map:
                    continue
                for c in n:
                    if c not in py_map:
                        miss.add(c)
            ck("地名用到的字全部有拼音", not miss,
               "缺 %d 个字: %s" % (len(miss), "".join(sorted(miss)[:20])))
            # 抽查多音字：重庆/厦门/六安 逐字查都是错的
            for name, right in [("重庆市", "chongqing"), ("厦门市", "xiamen"),
                                ("六安市", "luan"), ("蚌埠市", "bengbu"),
                                ("漯河市", "luohe")]:
                if name in names:
                    got = (poly_map.get(name) or "").replace(" ", "")
                    concat = "".join(py_map.get(c, "?") for c in name)
                    # 只比读音部分：「六安市」的六安读 luan，「市」是 shi
                    if got.startswith(right):
                        ck("多音字「%s」读音正确" % name, True,
                           "%s（逐字拼会是 %s）" % (got, concat))
                    else:
                        ck("多音字「%s」读音正确" % name, False,
                           "词组=%r 期望前缀=%r（逐字拼会是 %r）"
                           % (got, right, concat))

            # 音节必须用空格隔开：页面靠它切音节算首字母缩写。
            # 连写（beijingshi）里没有音节边界，首字母会退化成单字 "b"，
            # 症状是搜「bj」「xa」全部 0 条而界面上毫无异常。
            no_space = [n for n, v in poly_map.items() if " " not in v and len(v) > 4]
            ck("多音字表音节以空格分隔", not no_space,
               "有 %d 条没分隔: %s" % (len(no_space), no_space[:3]))
        except Exception as e:
            ck("拼音表可解析", False, str(e)[:80])
    ck("切页按钮按 .tabs [data-tab] 定位",
       'querySelectorAll(".tabs [data-tab]")' in html and "dataset.tab" in html)
    ck("分段控件按 data-cal / data-sex 定位",
       'data-cal="solar"' in html and 'data-sex="男"' in html
       and 'getAttribute("data-cal")' in html)

    print("\n6) 敏感信息")
    for needle in FORBIDDEN:
        ck("不含 %s" % needle, needle not in html)

    print("\n7) 文案与隐私")
    ck("声明生辰不上传", "不上传" in html)
    ck("引擎标识已写进页面", "纯 JS 引擎" in html)

    # ---- 产物目录不应再有运行时文件：留着只会让人以为还需要下载 ----
    ddir = os.path.dirname(DIST)
    ck("dist/pyodide 已移除", not os.path.isdir(os.path.join(ddir, "pyodide")))

    print("\n" + "=" * 56)
    if fails:
        print("失败 %d 项：%s" % (len(fails), fails))
        return 1
    print("产物校验全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
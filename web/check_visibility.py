#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验「JS 显示元素」与「CSS 可见规则」对得上 —— CI 门禁，零第三方依赖。

为什么需要这道门禁
------------------
有一类 bug 的形状很固定：

    CSS:  .status { display: none }   .status.show { display: flex }
    JS:   el.className = "status " + type        <- 忘了 show

结果：元素永远不可见。用户看到的是「点了没反应」，控制台也不报错，
因为 innerHTML 确实被写进去了 —— 只是没人看得见。

这不是假设，是我实际踩的：`setStatus()` 从来不加 `show`，
于是「请先选择阳历生日」「请选择出生时间」这类提示全都隐形。
用户点排盘没反应，以为按钮坏了，我却在排查引擎。

所以纯逻辑测试不够（它只验 innerHTML 有没有内容），
必须拿「JS 最终设的 class」×「CSS 规则」做交叉比对。

用法
----
    python web/check_visibility.py
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(HERE, "dist", "index.html")

# setStatus 的 type 取值 —— 它的 class 是拼接出来的，正则抓不到
STATUS_TYPES = ("loading", "error", "ok")

# 这些元素上 JS 的语义是「**隐藏**」，判定方向要反过来
HIDE_TARGETS = {"form": "collapsed"}


def parse_css(css):
    """-> [(选择器, {prop: val})]。刻意支持复合选择器（.summary.show）。"""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    out = []
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        props = {}
        for d in m.group(2).split(";"):
            if ":" in d:
                k, v = d.split(":", 1)
                props[k.strip()] = v.strip()
        for s in " ".join(m.group(1).split()).split(","):
            out.append((s.strip(), props))
    return out


def sel_parts(sel):
    """把选择器拆成 (tag, #id, [.class...])。只处理单元素选择器，够用。"""
    parts = re.split(r"([.#])", sel.strip())
    tag, eid, kls = None, None, []
    i = 1
    while i < len(parts):
        kind = parts[i]
        name = parts[i + 1] if i + 1 < len(parts) else ""
        if kind == ".":
            kls.append(name)
        elif kind == "#":
            eid = name
        else:
            tag = name
        i += 2
    return tag, eid, kls


def main():
    if not os.path.isfile(DIST):
        print("找不到产物 %s，请先运行 build_web.py" % DIST)
        return 1

    h = io.open(DIST, encoding="utf-8").read()
    body = h[:h.index("<script>")]
    script = "\n".join(re.findall(r"<script>(.*?)</script>", h, re.S))
    rules = parse_css("\n".join(re.findall(r"<style[^>]*>(.*?)</style>", h, re.S)))

    ids_in_page = set(re.findall(r'id="([^"]+)"', body))

    def html_classes(eid):
        m = re.search(r'<[^>]*\bid="%s"[^>]*>' % re.escape(eid), body)
        if not m:
            return None
        cm = re.search(r'class="([^"]*)"', m.group(0))
        return cm.group(1).split() if cm else []

    def display_for(eid, classes):
        """该元素在这些 class 下的最终 display（后出现的规则覆盖先出现的）。"""
        val = None
        for s, props in rules:
            if "display" not in props:
                continue
            _, sid, kls = sel_parts(s)
            if sid is not None and sid != eid:
                continue
            if not all(c in classes for c in kls):
                continue
            val = props["display"]
        return val

    # ---- 收集 JS 里所有「改 class 从而影响显隐」的写法 ----
    targets = {}
    for m in re.finditer(
            r'\$\("#([\w-]+)"\)\s*\.\s*classList\.(?:add|toggle)\(\s*"([\w-]+)"', script):
        targets.setdefault(m.group(1), set()).update(m.group(2).split())
    for m in re.finditer(r'\$\("#([\w-]+)"\)\s*\.\s*className\s*=\s*([^;]+);', script):
        got = set()
        for lit in re.findall(r'"([^"]*)"', m.group(2)):
            got.update(lit.split())
        if "(type" in m.group(2):
            got.update(STATUS_TYPES)
        targets.setdefault(m.group(1), set()).update(got)

    fails = []
    print("校验 %s\n" % DIST)
    print("=== JS 操作显隐的元素 × CSS 规则 ===")
    for eid in sorted(targets):
        base = html_classes(eid)
        if base is None:
            print("  [FAIL] #%-13s 在 HTML 里不存在" % eid)
            fails.append("#%s 不存在" % eid)
            continue
        classes = set(base) | targets[eid]
        d = display_for(eid, classes)
        if eid in HIDE_TARGETS:
            ok, want = (d == "none"), "none"
        else:
            ok, want = (d is not None and d != "none"), "非 none"
        print("  [%s] #%-13s class=%-24s display=%-6s (期望 %s)"
              % ("OK" if ok else "FAIL", eid,
                 ",".join(sorted(classes))[:24], d, want))
        if not ok:
            fails.append("#%s（class=%s）display=%s，期望 %s"
                         % (eid, ",".join(sorted(classes)), d, want))
            print("         相关 CSS:")
            for s, props in rules:
                _, sid, kls = sel_parts(s)
                if "display" not in props:
                    continue
                if (sid == eid) or (sid is None and
                                    any(c in kls for c in set(base) | targets[eid])):
                    print("           %-30s display:%s" % (s, props["display"]))

    # ---- 兜底：靠 show 才可见的元素，CSS 里必须有对应的 show 规则 ----
    # 注意 #result 是 **id** 不是 class：#result{display:none} / #result.show{display:block}。
    # 早先只按 .class 找，于是把这条正常写法误报成缺失 —— 门禁自己先失准，
    # 那它报的其他结果就不能信了。所以 id 与 class 都要认。
    print("\n=== 依赖 show 才可见的元素 ===")
    for name in ("status", "summary", "panel", "result"):
        def has_show_rule(nm):
            for s, props in rules:
                _, sid, kls = sel_parts(s)
                if props.get("display") in (None, "none"):
                    continue
                if "show" not in kls:
                    continue
                if sid == nm or nm in kls:      # #result.show 或 .status.show
                    return True
            return False

        ok = has_show_rule(name)
        print("  [%s] %s 有 show 可见规则" % ("OK" if ok else "FAIL", name))
        if not ok:
            fails.append("%s 依赖 show 才可见，但 CSS 里没有对应的 show 规则" % name)

    # ---- setStatus 必须加 show ----
    # 单独拎出来断言：这是踩过的坑，值得一条专门的检查
    print("\n=== setStatus 的可见性契约 ===")
    m = re.search(r"function setStatus\([^)]*\)\s*\{(.*?)\n  \}", script, re.S)
    if not m:
        print("  [FAIL] 找不到 setStatus")
        fails.append("找不到 setStatus")
    else:
        fn = m.group(1)
        has_show = re.search(r'className\s*=\s*"[^"]*\bshow\b', fn) \
            or re.search(r'classList\s*\.\s*add\(\s*"show"', fn)
        if has_show:
            print("  [OK] setStatus 会加 show 类")
        else:
            print("  [FAIL] setStatus 没有加 show —— 状态条永远不可见，"
                  "所有错误提示都会静默失败")
            fails.append("setStatus 未加 show（状态条永久隐形）")

    print("\n" + "=" * 56)
    if fails:
        print("失败 %d 项：" % len(fails))
        for f in fails:
            print("  - " + f)
        return 1
    print("可见性契约全部成立")
    return 0


if __name__ == "__main__":
    sys.exit(main())
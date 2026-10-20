# -*- coding: utf-8 -*-
"""对比度检查：全量扫描版（v1.11.0 重写）。

## 为什么重写

上一版是**人工维护的 CHECKS 名单**：只验名单里列过的选择器。
结果真实浏览器审计（Lighthouse）发现一堆不在名单里的
不合格字 ——

  .dy-seg i   十神名   #9a8f7e/#efe9dd = 2.63:1   FAIL
  .dy-seg u   年份     #b3a693/#efe9dd = 1.97:1   FAIL
  .ln-seg i   年份     #b3a693/#f6f0e4 = 2.10:1   FAIL
  .ln-seg.now i 当前年 rgba(255,255,255,.7)/#a8322d = 4.05 FAIL
  .pill.ji    神煞     #3f7a52/#e8f2ea = 4.44:1   FAIL

名单没列到 = 自动检查永远绿 = 「修哪验哪」的历史根源。

## 这一版怎么扫

1. 解析 oracle.py CSS 的每一条规则
2. 对**每条设置了 color 的规则**（不再凭名单）：
   - 跳过 ::before/::after（三角、圆点等装饰符号，非正文）
   - **真实落点**：沿祖先链从最具体到最泛走，
     第一层设置了 background 的祖先就是这片字实际躺的底
     （层叠里更远的底都被它盖住了）；没有则落在页面底色上
   - 渐变展开为全部色标；rgba 按 alpha 与**所在底**合成
     （白字 .7 躺红底 = 白红混合色对红底算，不是对奶油底算）
   - 取最差对比度，要求 >= 4.5（WCAG AA 小字标准）
3. --selftest：把历史不合格色喂进去，必须全部抓到（防扫描器
   本身失效变摆设）；正常颜色的用例必须通过
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P_ORACLE = os.path.join(ROOT, "scripts", "oracle.py")

NEED = 4.5          # WCAG AA：正文与 12px 级小字


def lum(h):
    h = h.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda c: c / 12.92 if c <= .03928 else ((c + .055) / 1.055) ** 2.4
    return .2126 * f(r) + .7152 * f(g) + .0722 * f(b)


def ratio(a, b):
    la, lb = lum(a), lum(b)
    return (max(la, lb) + .05) / (min(la, lb) + .05)


def parse_hexa(s):
    """#rrggbb(#aa) -> (hex 无 #, alpha)，否则 (None, None)"""
    s = s.strip()
    m = re.match(r"#([0-9a-fA-F]{6})([0-9a-fA-F]{2})?$", s)
    if m:
        a = int(m.group(2), 16) / 255.0 if m.group(2) else 1.0
        return m.group(1).lower(), a
    return None, None


def hex_color(s):
    """任意 hex 形态 -> (6位hex 无 #, alpha)；#abc 展开为 6 位。"""
    s = s.strip()
    m = re.match(r"#([0-9a-fA-F]{3})$", s)
    if m:
        d = m.group(1).lower()
        return "".join(ch * 2 for ch in d), 1.0
    return parse_hexa(s)


def parse_rgba(s):
    """rgba(255,255,255,.7) -> (ffffff, 0.7)；解析不了 (None, 0)"""
    m = re.match(
        r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+))?\s*\)",
        s.strip())
    if not m:
        return None, None
    a = float(m.group(4)) if m.group(4) is not None else 1.0
    return "%02x%02x%02x" % tuple(int(m.group(i)) for i in (1, 2, 3)), a


def over(fg, a, bg):
    """alpha 混合：fg 以透明度 a 躺在 bg 上的实际颜色。"""
    f = [int(fg[i:i + 2], 16) for i in (0, 2, 4)]
    b = [int(bg[i:i + 2], 16) for i in (0, 2, 4)]
    return "%02x%02x%02x" % tuple(int(round(f[i] * a + b[i] * (1 - a)))
                                  for i in range(3))


def css_text(text):
    s = text.index('CSS = """') + 9
    return text[s:text.index('"""', s)]


def flatten(css):
    """把 var(--x) 替换成 :root 里的定义。"""
    vars_ = dict(re.findall(r"--([a-z0-9-]+)\s*:\s*([^;}]+)", css))
    base = vars_.get("bg", "#f7f4ee").strip()
    for _ in range(4):                       # 变量套变量
        changed = False
        for k, v in list(vars_.items()):
            m = re.search(r"var\(--([a-z0-9-]+)\)", v)
            if m and m.group(1) in vars_ and "var(--" + m.group(1) + ")" in v:
                nv = v.replace("var(--%s)" % m.group(1),
                               vars_[m.group(1)].strip())
                if nv != v:
                    vars_[k] = nv
                    changed = True
        if not changed:
            break
    return re.sub(r"var\(--([a-z0-9-]+)\)",
                  lambda m: vars_.get(m.group(1), m.group(0)).strip(), css), base


def rules(css):
    """(selector, body)，跳过 @media print 的规则。"""
    out = []
    in_print = False
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        sel = m.group(1).strip().split("\n")[-1].strip()
        if sel.startswith("/*") or not sel:
            continue
        if "@media print" in m.group(1):
            in_print = True
            continue
        if in_print:
            if "@media" in m.group(1):
                in_print = False
            else:
                continue
        out.append((sel, m.group(2)))
    return out


def body_bgs(body, page_bg):
    """规则体里的底色候选：纯色 + 渐变全部色标 + rgba/#hexaa 合成。"""
    cols = []
    m = re.search(r"(?<!-)background\s*:\s*([^;]+)", body)
    if not m:
        return cols
    decl = m.group(1)
    for c in re.findall(r"#([0-9a-fA-F]{6})\b", decl):
        cols.append(c.lower())
    for c, a in [hex_color(x) for x in re.findall(r"#[0-9a-fA-F]{8}\b", decl)]:
        if c:
            cols.append(over(c, a, page_bg))
    for c, a in [parse_rgba(x) for x in re.findall(r"rgba?\([^)]+\)", decl)]:
        if c:
            cols.append(over(c, a, page_bg))
    return sorted(set(cols))


def norm_sel(sel):
    """> 两侧去空格、多空格合一，便于父级匹配。"""
    s = re.sub(r"\s*>\s*", ">", sel)
    return re.sub(r"\s+", " ", s).strip()


def variant_key(sel):
    """selector 的状态归一键：去掉 [] 状态符后重组。

    details.fold[open]>summary == details.fold>summary
    """
    core = re.sub(r"\[[^\]]*\]", "", sel)
    return re.sub(r"\s+", " ", core).strip()


def scan(css_text_all):
    """返回 (fail 列表, 检查条数)。"""
    css, page_bg = flatten(css_text_all)
    page_bg = parse_hexa(page_bg)[0] or "f7f4ee"
    rs = rules(css)

    # 底色源（归一选择器 -> [底色]），同元素状态变体也归拢
    bg_of = {}
    bg_variants = {}
    for sel, body in rs:
        b = body_bgs(body, page_bg)
        if not b:
            continue
        ns = norm_sel(sel)
        bg_of[ns] = bg_of.get(ns, []) + b
        k = variant_key(ns)
        bg_variants[k] = bg_variants.get(k, []) + b

    fails = []
    n_checked = 0
    for sel, body in rs:
        m = re.search(r"(?<![-\w])color\s*:\s*([^;}]+)", body)
        if not m:
            continue
        col = m.group(1).strip().split()[0]
        if col.startswith(("transparent", "inherit", "currentColor")):
            continue
        if "::before" in sel or "::after" in sel:
            continue          # 装饰符号（三角/圆点），不是正文
        fx, fa = hex_color(col)
        if not fx:
            fx, fa = parse_rgba(col)
        if not fx:
            continue          # 未知色值形态（理论上不会出现）

        ns = norm_sel(sel)
        parts = ns.split(" ")

        # 真实落点：自身底 > 逐级祖先（从最具体向外）第一层有底者；
        # 全都没有 → 页面底。
        cand = []
        own = body_bgs(body, page_bg)
        if own:
            cand.extend(own)
        for i in range(len(parts) - 1, 0, -1):
            p = " ".join(parts[:i])
            b = bg_of.get(p, []) + bg_variants.get(
                variant_key(p), [])
            if b:
                cand.extend(sorted(set(b)))
                break          # 这一层的底盖住更远的底，停止向外走
        if not cand:
            cand = [page_bg]

        worst = 99.0
        for bg in cand:
            if not re.match(r"^[0-9a-fA-F]{6}$", bg):
                continue
            real = over(fx, fa, bg) if (fa is not None and fa < 1.0) else fx
            worst = min(worst, ratio("#" + real, "#" + bg))
        n_checked += 1
        if worst < NEED:
            fail_fg = ("#" + over(fx, fa, page_bg)
                       if fa is not None and fa < 1.0 else "#" + fx)
            fails.append((sel, fail_fg, worst))
    return fails, n_checked


# ---- SVG 文字色（fill= 属性，CSS 扫描看不见，但浏览器审计看得见） ----
# 五行环 / 占星盘的数字与标签都是 <text fill="...">，它们躺在页面底色上。
# 之前 .a-num 用 #b3a693 只有 1.97:1 —— CSS 自动检查全过，真页面几乎看不见。
SVG_TEXT_RE = re.compile(r'class="([a-zA-Z0-9_\- ]+)"\s+fill="#([0-9a-fA-F]{6})"')
SVG_BGS = ["f7f4ee", "fffdf8", "fbf8f1"]   # 页面底 / 卡片底 / 折叠块底


def scan_svg_text(paths):
    """返回 [(来源, class, 色, 最差对比度)]。"""
    out = []
    for p in paths:
        if not os.path.isfile(p):
            continue
        src = io.open(p, encoding="utf-8").read()
        for m in SVG_TEXT_RE.finditer(src):
            cls = m.group(1)
            col = m.group(2).lower()
            worst = min(ratio(col, bg) for bg in SVG_BGS)
            out.append((os.path.basename(p), cls, col, worst))
    return out


# ---- 设计令牌同步：网页版与 CLI 必须用同一套色 ----
# app.html 自己有一份 :root，它在文档里排在 oracle CSS 之后，
# 同名令牌会覆盖 oracle 那份。两边一旦不同步，网页版就会悄悄
# 用另一套颜色 —— --green 停在旧值就是这样漏到网页版的。
def root_tokens(text):
    i = text.find(":root{")
    if i < 0:
        return {}
    j = text.find("}", i)
    if j < 0:
        return {}
    body = text[i + 6:j]
    return dict(re.findall(r"--([a-z0-9-]+)\s*:\s*([^;}]+)", body))


def check_tokens():
    """返回不一致的令牌 [(名, CLI 值, 网页版值)]。"""
    t = io.open(P_ORACLE, encoding="utf-8").read()
    css = css_text(t)
    app_path = os.path.join(ROOT, "web", "app.html")
    if not os.path.isfile(app_path):
        return []
    app = io.open(app_path, encoding="utf-8").read()
    a = root_tokens(css)
    b = root_tokens(app)
    bad = []
    for k in sorted(set(a) & set(b)):
        if a[k].strip() != b[k].strip():
            bad.append((k, a[k].strip(), b[k].strip()))
    return bad


def selftest():
    """历史不合格色必须全部抓到；正常用例必须通过。"""
    bad_css = """
    :root{ --bad:#b3a693; }
    body{ background:#f7f4ee; color:#2b2621 }
    .dy-seg{ background:#efe9dd }
    .dy-seg i{ color:var(--bad); font-size:11px }
    .ln-seg.now{ background:#a8322d }
    .ln-seg.now i{ color:rgba(255,255,255,.7) }
    .fine{ color:#2b2621 }
    .low-contrast{ color:#777 }      /* 3 位缩写也要能解析 */
    .red-on-red{ color:#e5c2c0 }
    .pill{ background:#a8322d; color:#ffffff }
    """
    fails, n = scan(bad_css)
    got = {s for s, _, _ in fails}
    want = {".dy-seg i", ".ln-seg.now i", ".low-contrast", ".red-on-red"}
    if not want <= got:
        print("FAIL 自检漏了 %s（只抓到 %s）"
              % (sorted(want - got), sorted(got)))
        return 1
    if got != want:
        print("FAIL 自检多抓了 %s" % sorted(got - want))
        return 1
    print("自检通过：4 个坏用例全抓到，3 个好用例全放过")
    return 0


def main():
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    t = io.open(P_ORACLE, encoding="utf-8").read()
    css = css_text(t)
    fails, n = scan(css)
    print("全量扫描 %d 条文字色规则" % n)

    svg_files = [os.path.join(ROOT, "scripts", "plain.py"),
                 os.path.join(ROOT, "web", "js", "plain.js")]
    svg = scan_svg_text(svg_files)
    bad = check_tokens()
    print("设计令牌：CLI 与网页版共有 %d 个同名令牌"
          % len(set(root_tokens(css_text(io.open(P_ORACLE, encoding="utf-8").read())))
                 & set(root_tokens(io.open(os.path.join(ROOT, "web", "app.html"),
                                          encoding="utf-8").read()))))
    for k, v1, v2 in bad:
        print("   ! 令牌 %s 两端不一致：CLI %s / 网页版 %s" % (k, v1, v2))
    if bad:
        fails.extend([("token " + k, v1, 0.0) for k, v1, _v2 in bad])

    svg_fail = [x for x in svg if x[3] < NEED]
    print("SVG 文字色 %d 处（%d 个文件）" % (len(svg), len(svg_files)))
    for src, cls, col, r in svg_fail:
        print("   ! SVG %s .%s %s %.2f:1" % (src, cls, col, r))
    fails.extend([("SVG .%s" % c, "#" + col, r)
                  for _s, c, col, r in svg_fail])
    if fails:
        print("FAIL %d 条不合格（<%.1f:1）：" % (len(fails), NEED))
        for sel, fg, r in sorted(fails, key=lambda x: x[2])[:40]:
            print("   ! %-46s %-9s %.2f:1" % (sel[:46], fg, r))
        return 1
    print("PASS 全部 >= %.1f:1" % NEED)
    return 0


if __name__ == "__main__":
    sys.exit(main())

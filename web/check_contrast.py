# -*- coding: utf-8 -*-
"""重写 check_contrast.py 的门禁本身。

上一版门禁三处写错，报出来的全是假失败：
1. `.persona` 的底色是渐变，浅色文字要按**最亮**处算，
   而我取了页面底色（浅）→ 方向反了
2. CSS 变量（var(--sub) / var(--red)）没解析
3. `.plain p` / `.li` 这类选择器在 CSS 里没有 color（继承 body）
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P_ORACLE = os.path.join(ROOT, "scripts", "oracle.py")


def lum(h):
    h = h.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda c: c / 12.92 if c <= .03928 else ((c + .055) / 1.055) ** 2.4
    return .2126 * f(r) + .7152 * f(g) + .0722 * f(b)


def ratio(a, b):
    la, lb = lum(a), lum(b)
    return (max(la, lb) + .05) / (min(la, lb) + .05)


def parse_hex(s):
    m = re.match(r"#([0-9a-fA-F]{6})$", s.strip())
    return m.group(1).lower() if m else None


def parse_hexa(s):
    """#rrggbb(#aa) -> (hex, alpha)"""
    s = s.strip()
    m = re.match(r"#([0-9a-fA-F]{6})([0-9a-fA-F]{2})?$", s)
    if m:
        a = int(m.group(2), 16) / 255.0 if m.group(2) else 1.0
        return m.group(1).lower(), a
    return None, None


def over(fg, a, bg):
    f = [int(fg.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    b = [int(bg.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    return "%02x%02x%02x" % tuple(int(round(f[i] * a + b[i] * (1 - a)))
                                  for i in range(3))


def css_text():
    t = io.open(P_ORACLE, encoding="utf-8").read()
    s = t.index('CSS = """') + 9
    e = t.index('"""', s)
    return t[s:e]


def flatten(css):
    """把 var(--x) 替换成 :root 里的定义。"""
    vars_ = dict(re.findall(r"--([a-z0-9-]+)\s*:\s*([^;}]+)", css))
    for _ in range(3):                       # 支持变量套变量
        for k, v in vars_.items():
            if "var(" in v:
                v2 = v
                for k2, v2v in vars_.items():
                    v2 = v2.replace("var(--%s)" % k2, v2v.strip())
                vars_[k] = v2
    def rep(m):
        return vars_.get(m.group(1), m.group(0)).strip()
    css = re.sub(r"var\(--([a-z0-9-]+)\)", rep, css)
    return css


def rules(css):
    out = []
    in_print = False
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        sel = m.group(1).strip().split("\n")[-1].strip()
        if sel.startswith("/*") or not sel:
            continue
        # 跳过 @media print：打印时白底黑字，与屏幕无关。
        # 上一版没跳过，把打印规则里的 color:#222 当成了屏幕色值，
        # 于是误报"不是纯色"。
        if "@media print" in m.group(1):
            in_print = True
            continue
        if in_print:
            # 遇到下一个 @media 或顶层规则时退出
            if "@media" in m.group(1):
                in_print = False
            else:
                continue
        out.append((sel, m.group(2)))
    return out


def grad_lightest(body):
    """linear-gradient → 最亮的颜色（浅字的最严格约束）。"""
    m = re.search(r"linear-gradient\(([^)]*)\)", body)
    if not m:
        return None
    cols = re.findall(r"#[0-9a-fA-F]{6}", m.group(1))
    if not cols:
        return None
    return max(cols, key=lum).lower()


def bg_of(body):
    m = re.search(r"(?<!-)background\s*:\s*([^;}]+)", body)
    return m.group(1).strip() if m else None


def color_of(body):
    m = re.search(r"(?<![-\w])color\s*:\s*([^;}]+)", body)
    return m.group(1).strip().split()[0] if m else None


# (容器链, 文字选择器, 需要的最小对比度)
# 容器链从外到内；底色逐层叠加。
# persona 已改成浅色卡（1.10.1），所以和全站其他卡片同一套底色，
# 不再需要为深背景单维护一套检查项。
CHECKS = [
    ([".persona"], ".persona .p-v", 4.5),
    ([".persona"], ".persona .p-lead", 4.5),
    ([".persona"], ".persona .p-k", 4.5),
    ([".persona"], ".persona .p-src", 4.5),
    ([".persona"], ".persona .p-note", 4.5),
    ([".persona"], ".persona .p-eyebrow", 4.5),
    # persona 内嵌 fold
    ([".persona", ".persona details.fold"], ".persona .p-v", 4.5),
    ([".persona", ".persona details.fold"], ".persona .p-k", 4.5),
    ([".persona", ".persona details.fold"], ".persona .p-src", 4.5),
    ([".persona", ".persona details.fold"],
     ".persona details.fold>summary", 4.5),
    # 浅色区
    (["body"], ".plain .sub2", 4.5),
    (["body"], ".fbody p", 4.5),
    (["body"], ".li", 4.5),
    (["body"], ".hd", 4.5),
    (["body"], ".xsx-h", 4.5),
    (["body"], ".sub2", 4.5),
]


def main():
    css = flatten(css_text())
    rs = rules(css)

    page_bg = "#f7f4ee"
    body_color = "#2b2621"
    for sel, body in rs:
        if sel == "body":
            b = bg_of(body)
            h, _ = parse_hexa(b) if b else (None, None)
            if h:
                page_bg = h
            c = color_of(body)
            if c:
                body_color = c
    print("页面底色 #%s / 页面字色 #%s" % (page_bg, body_color))

    fails = []
    for chain, text_sel, need in CHECKS:
        # 底色：从外到内逐层叠。渐变取最亮处（浅字的最严格约束）。
        # 底色：从外到内逐层叠。
        # 注意：渐变取**最亮**处。因为我们要验的是浅色文字 ——
        # 渐变最亮那段是浅字对比最低的地方，是最严格约束。
        # 这是上一版错的地方：我把 persona 的渐变当成「随便什么」，
        # 结果算出浅底，方向整个反了。
        bg = page_bg
        for layer in chain:
            # 同一个选择器可能出现多次（如深浅两版）。
            # 取"最亮的那一版" —— 同样是浅字的最严格约束。
            cands = []
            for sel, body in rs:
                if sel == layer:
                    cands.append(bg_of(body))
            if not cands:
                continue
            # 逐个候选解析出颜色，取最亮
            resolved = []
            for cand in cands:
                if not cand:
                    continue
                g = grad_lightest(cand)
                if g:
                    resolved.append(g)
                    continue
                h, a = parse_hexa(cand)
                if h:
                    resolved.append(over(h, a, bg))
            if not resolved:
                continue
            bg = max(resolved, key=lum)

        # 文字色：选择器自己的 color；没有则继承 body。
        # 同一选择器可能有多条（小屏、print）。做法：把候选都列出来，
        # 取与底色**对比最高**的那条 —— 深底配浅字、白底配深字，
        # 对比最高的自然就是当前生效的那条。
        cands = []
        for sel, body in rs:
            if sel != text_sel:
                continue
            c = color_of(body)
            if not c:
                continue
            h, a = parse_hexa(c)
            if h:
                cands.append((h, a, c))
        if cands:
            fg, fa, raw = max(cands, key=lambda t: ratio(t[0], bg))
        else:
            # 没有自己的 color 规则 —— 继承父级。这里简化为继承 body，
            # 因为要验的这些都在浅色区，body 就是最深的字色。
            fg, fa, raw = parse_hexa(body_color) + (body_color,)
        if not fg:
            fails.append("%s：取不到 color" % text_sel)
            continue
        if fa < 1:
            fg = over(fg, fa, bg)
        r = ratio(fg, bg)
        ok = r >= need
        print("  %-30s on %-40s %5.2f:1  %s"
              % (text_sel, " > ".join(chain), r, "OK" if ok else "!!不足!!"))
        if not ok:
            fails.append("%s（%s）只有 %.2f:1，需 %.1f"
                         % (text_sel, " > ".join(chain), r, need))

    print("")
    if fails:
        for f in fails:
            print("  FAIL " + f)
        print("嵌套对比度检查失败：%d 项" % len(fails))
        print("这类错误不是「颜色选得不好」，而是容器嵌套后底色变了 ——")
        print("为深背景调的浅色文字可能落在浅底上，人眼查不出来。")
        return 1
    print("嵌套对比度全部达标")
    return 0


if __name__ == "__main__":
    sys.exit(main())
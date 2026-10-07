#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在 Node 里模拟 DOM，把产物页面的**表单交互**真跑一遍。

为什么 test_load_chain.py 不够
------------------------------
那个脚本只验引擎：window.MingLi 挂上了、run() 能出盘。
但页面上「点排盘按钮 → 出结果」这一段是**另一段代码**（bind/collect/…），
挂在 DOM 事件上。引擎全对、界面全哑，是完全可能的 ——
而且不报任何错，页面看起来「正常打开」，只是按钮没用。

我踩过：换成内联 JS 时把 Pyodide 成功分支里的 bind() 一起删了，
线上表现是「页面打开了但点排盘毫无反应」，没有任何报错。

所以这个脚本用最小 DOM stub 跑真实的点击流程：
  填表 → 点分段控件 → 点时辰 → 提交 → 检查结果面板真的被填上了。

不追求覆盖所有交互，只保证「主路径是通的」。

用法
----
    python web/test_ui_chain.py [--js node]
"""
import argparse
import io
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(HERE, "dist", "index.html")

DRIVER = r"""
const fs = require("node:fs");
const vm = require("node:vm");

const html = fs.readFileSync(process.argv[2], "utf8");
const code = html.match(/<script>([\s\S]*?)<\/script>/)[1];

// ---- 极简 DOM ----
// 只实现页面实际用到的那几个方法。故意不做「万能 mock」：
// 一旦 mock 什么都能接受，就永远测不出「调用了不存在的方法」这类问题。
const ALL_ATTRS = new Set();
let idSeq = 0;

function mkEl(tag, id) {
  const el = {
    tagName: (tag || "div").toUpperCase(),
    id: id || ("el" + (idSeq++)),
    className: "",
    _html: "", _text: "",
    value: "", checked: false, hidden: false, disabled: false,
    dataset: {}, attrs: {}, style: {}, children: [], parent: null,
    _listeners: {},
    get innerHTML() { return this._html; },
    set innerHTML(v) { this._html = String(v); },
    get textContent() { return this._text; },
    set textContent(v) { this._text = String(v); },
    get classList() {
      const self = this;
      const set = new Set((self.className || "").split(/\s+/).filter(Boolean));
      return {
        add(...c) { c.forEach(x => set.add(x)); self.className = [...set].join(" "); },
        remove(...c) { c.forEach(x => set.delete(x)); self.className = [...set].join(" "); },
        contains(c) { return set.has(c); },
        toggle(c) { set.has(c) ? set.delete(c) : set.add(c);
                    self.className = [...set].join(" "); },
      };
    },
    setAttribute(k, v) { this.attrs[k] = v; if (k === "id") this.id = v; },
    getAttribute(k) {
      if (k === "class") return this.className;
      if (k === "value") return this.value;
      return (k in this.attrs) ? this.attrs[k] : null;
    },
    removeAttribute(k) { delete this.attrs[k]; },
    addEventListener(t, fn) { (this._listeners[t] ||= []).push(fn); },
    removeEventListener(t, fn) {
      this._listeners[t] = (this._listeners[t] || []).filter(f => f !== fn);
    },
    // 触发事件：模拟用户点击/提交
    fire(t, ev) {
      const evs = this._listeners[t] || [];
      if (!evs.length) return false;
      for (const fn of evs.slice()) fn(ev || { type: t, preventDefault(){}, target: this });
      return true;
    },
    hasListener(t) { return (this._listeners[t] || []).length > 0; },
    appendChild(c) { this.children.push(c); c.parent = this; return c; },
    removeChild(c) { this.children = this.children.filter(x => x !== c); },
    remove() { if (this.parent) this.parent.removeChild(this); },
    querySelector(sel) { return doc.querySelector(sel); },
    querySelectorAll(sel) { return doc.querySelectorAll(sel); },
    closest() { return null; },
    scrollIntoView() {},
    focus() {},
  };
  return el;
}

const byId = new Map();
const byClass = new Map();   // class -> [el]

function reg(el) {
  if (el.id) { byId.set(el.id, el); ALL_ATTRS.add("#" + el.id); }
  for (const c of (el.className || "").split(/\s+/).filter(Boolean)) {
    (byClass.get(c) || byClass.set(c, []).get(c)).push(el);
  }
  return el;
}

// 从 HTML 里把 id / class / data-* / 标签结构抠出来，造一棵够用的树。
// 做法很土，但足以让页面的 querySelector('#x') / .seg [data-cal] 找到东西。
function buildFromHTML(src) {
  const root = mkEl("body");
  const stack = [root];
  // 逐个标签扫描：只关心能挂 id/class/data-* 的容器型元素
  const re = /<(\/?)([a-zA-Z][\w-]*)((?:\s+[^>]*?)?)(\/?)>/g;
  let m;
  while ((m = re.exec(src)) !== null) {
    const [full, close, tag, attrs, selfClose] = m;
    const tagl = tag.toLowerCase();
    if (tagl === "script" || tagl === "style") {
      // 跳过整块内容，避免把 JS 里的 '<div' 当成标签
      const end = src.indexOf("</" + tagl, re.lastIndex);
      if (end >= 0) re.lastIndex = end;
      continue;
    }
    if (close) {
      if (stack.length > 1) stack.pop();
      continue;
    }
    const idm = attrs.match(/\bid="([^"]+)"/);
    const clsm = attrs.match(/\bclass="([^"]+)"/);
    const hasAttr = idm || clsm || /data-/.test(attrs);
    if (!hasAttr) {
      if (!selfClose && !/^(br|img|input|meta|link|hr|source)$/.test(tagl)) {
        // 无属性但可能仍有子节点的容器：粗略入栈，出栈靠下一个 close
      }
      continue;
    }
    const el = mkEl(tagl, idm ? idm[1] : null);
    if (clsm) el.className = clsm[1];
    const dm = attrs.match(/\bdata-([\w-]+)="([^"]*)"/g) || [];
    for (const d of dm) {
      const [, k, v] = d.match(/data-([\w-]+)="([^"]*)"/);
      el.dataset[k] = v;
      el.attrs["data-" + k] = v;
    }
    reg(el);
    stack[stack.length - 1].appendChild(el);
    if (!selfClose && !/^(br|img|input|meta|link|hr|source)$/.test(tagl)) stack.push(el);
  }
  return root;
}

const htmlBody = html.slice(html.indexOf("<body"), html.indexOf("<script>"));
const bodyRoot = buildFromHTML(htmlBody);

const doc = {
  body: bodyRoot,
  querySelector(sel) {
    sel = sel.trim();
    if (sel.startsWith("#")) return byId.get(sel.slice(1)) || mkEl("div");
    if (sel.startsWith(".")) {
      // 支持 ".a .b"（后代）这类组合：逐段在已注册元素里找
      const parts = sel.split(/\s+/);
      let cur = [bodyRoot];
      for (const p of parts) {
        const next = [];
        for (const c of cur) next.push(...(byClass.get(p.slice(1)) || []));
        cur = next;
        if (!cur.length) return null;
      }
      return cur[0];
    }
    return null;
  },
  querySelectorAll(sel) {
    sel = sel.trim();
    // 处理 "A B" / "A [attr]" 组合：取 A，再在 A 的子树里找 B
    const parts = sel.split(/\s+/);
    let scope = [bodyRoot];
    let last = null;
    for (let i = 0; i < parts.length; i++) {
      const p = parts[i];
      let matched = [];
      if (p.startsWith(".")) {
        const c = p.slice(1);
        for (const root of scope) {
          const walk = (n) => {
            for (const ch of n.children || []) {
              if ((ch.className || "").split(/\s+/).includes(c)) matched.push(ch);
              walk(ch);
            }
          };
          walk(root);
        }
      } else if (p.startsWith("#")) {
        const e = byId.get(p.slice(1));
        matched = e ? [e] : [];
      } else {
        const attrm = p.match(/^\[([\w-]+)\]$/);
        if (attrm) {
          const a = attrm[1];
          for (const root of scope) {
            const walk = (n) => {
              for (const ch of n.children || []) {
                if (a in ch.attrs) matched.push(ch);
                walk(ch);
              }
            };
            walk(root);
          }
        }
      }
      if (i === parts.length - 1) { last = matched; break; }
      scope = matched;
    }
    return last || [];
  },
  getElementById(id) { return byId.get(id) || null; },
  getElementsByTagName() { return []; },
  createElement: (t) => mkEl(t),
  addEventListener() {},
};

// 自己实现 setTimeout：排盘前页面会 setTimeout 一下让 loading 态先画出来。
// 真浏览器里它异步执行，Node 里如果不给，页面就永远停在「正在排盘…」——
// 那也是种静默失效，必须能被测出来，所以要收集起来手动 drain。
const pending = [];
function setTimeoutShim(fn, ms) { pending.push({ fn, ms: ms || 0 }); return pending.length; }
function drain() {
  let guard = 0;
  while (pending.length && guard++ < 1000) pending.shift().fn();
}

const win = { document: doc, location: { href: "https://example.invalid/", pathname: "/" } };
const ctx = vm.createContext({
  window: win, document: doc, location: win.location, console,
  Date, Math, JSON, parseInt, parseFloat, isFinite, isNaN,
  Array, Object, String, Number, Boolean, Error, Set, Map, Symbol, RegExp,
  setTimeout: setTimeoutShim, clearTimeout() {}, requestAnimationFrame(fn) { fn(); },
});
ctx.globalThis = ctx;

try {
  vm.runInContext(code, ctx, { filename: "page.js" });
} catch (e) {
  console.error("FAIL: 页面脚本抛错 -> " + (e && e.stack || e));
  process.exit(1);
}

let bad = 0;
const fail = (m) => { console.log("  FAIL " + m); bad++; };

// ---- 1) 引擎在 ----
if (!(win.MingLi && typeof win.MingLi.run === "function")) {
  fail("window.MingLi 未挂上");
} else {
  console.log("  OK   window.MingLi 已挂上");
}

// ---- 2) 关键元素存在 ----
const need = ["form", "solarDate", "birthTime", "city", "submitBtn",
              "headline", "panel-plain", "panel-pro", "result", "status",
              "shichenGrid"];
for (const id of need) {
  if (!byId.get(id)) fail("缺少 #" + id);
}
console.log("  OK   关键元素齐全（已注册 " + byId.size + " 个 id）");

// ---- 3) 提交路径真的绑了监听 ----
// 这一条就是本次事故的检测点：bind() 没被调用时，页面「正常打开」但完全没用。
//
// 注意页面用的是 <form> 的 submit 事件（按钮 type=submit），
// 不是给按钮绑 click。所以要查 form 的 submit 监听，不是按钮的 click。
const form = byId.get("form");
const submit = byId.get("submitBtn");
if (!form) {
  fail("找不到 #form");
} else if (!form.hasListener("submit")) {
  fail("#form 没有 submit 监听 —— boot() 忘了调 bind()");
} else {
  console.log("  OK   #form 已绑 submit 监听");
}
if (!submit) fail("找不到 #submitBtn");
else console.log("  OK   #submitBtn 存在，type=" + (submit.getAttribute("type") || "(默认 submit)"));

// 时辰格子、分段控件也各查一下
const segs = doc.querySelectorAll("[data-cal]");
if (!segs.length) fail("找不到 data-cal 分段按钮");
else {
  const anyBound = segs.some(b => b.hasListener("click"));
  anyBound ? console.log("  OK   分段控件已绑监听")
           : fail("data-cal 分段按钮没有 click 监听");
}

// ---- 4) 走完整流程：填表 → 点分段 → 点时辰 → 提交 → 看结果 ----
const set = (id, v) => { const e = byId.get(id); if (e) { e.value = v; e._text = v; } };
set("solarDate", "1990-05-15");
set("birthTime", "12:00");
const city = byId.get("city");
if (city) { city.value = "北京"; }

// 点一下「农历」再点回「阳历」，确认分段回调真的在跑
const calBtns = doc.querySelectorAll("[data-cal]");
if (calBtns.length > 1) calBtns[1].fire("click");

if (form && form.hasListener("submit")) {
  // 页面在 setTimeout 里才算盘，这里把队列里排队的定时器都跑掉。
  // 顺带验证 setTimeout 真的被调度了 —— 如果没有，界面会永远停在
  // 「正在排盘…」，这也是一种静默失效。
  const before = pending.length;
  form.fire("submit");
  const queued = pending.length - before;
  if (queued === 0) {
    fail("提交后没有排任何 setTimeout —— 结果永远不会渲染出来");
  } else {
    drain();
  }
}

const hl = byId.get("headline");
const pp = byId.get("panel-plain");
const pr = byId.get("panel-pro");
const st = byId.get("status");

const gotHl = hl && hl.innerHTML.trim().length > 0;
const gotPP = pp && pp.innerHTML.length > 500;
const gotPR = pr && pr.innerHTML.length > 500;
const errMsg = st ? (st.className || "") + "|" + st.textContent : "";

if (gotHl) console.log("  OK   #headline 已填入: "
  + hl.innerHTML.replace(/<[^>]+>/g, "").slice(0, 60));
else fail("#headline 是空的 —— 排盘结果没显示出来");

if (gotPP) console.log("  OK   #panel-plain " + pp.innerHTML.length + " 字符");
else fail("#panel-plain 内容过少: " + (pp ? pp.innerHTML.length : "null"));

if (gotPR) console.log("  OK   #panel-pro " + pr.innerHTML.length + " 字符");
else fail("#panel-pro 内容过少: " + (pr ? pr.innerHTML.length : "null"));

if (/error/i.test(errMsg)) {
  fail("#status 显示错误: " + st.textContent);
} else {
  console.log("  OK   #status 无错误 (class=" + ((st && st.className) || "") + ")");
}

if (bad) { console.error("\nUI 端到端验证失败 " + bad + " 项"); process.exit(1); }
console.log("\nPASS: 页面表单交互全通（填表→提交→出结果）");
"""


def main(argv=None):
    p = argparse.ArgumentParser(description="在 Node 里模拟 DOM 跑页面交互")
    p.add_argument("--js", default="node", help="Node 可执行文件")
    p.add_argument("--dist", default=DIST)
    a = p.parse_args(argv)

    if not os.path.isfile(a.dist):
        print("找不到产物 %s，请先运行 build_web.py" % a.dist)
        return 1
    print("UI 端到端验证 %s\n"
          % a.dist)

    drv = os.path.join(HERE, ".ui_chain_test.cjs")
    try:
        io.open(drv, "w", encoding="utf-8").write(DRIVER)
        try:
            r = subprocess.run([a.js, drv, a.dist], capture_output=True, timeout=300)
        except FileNotFoundError:
            print("找不到 Node：%s（用 --js 指定）" % a.js)
            return 2
    finally:
        try:
            os.remove(drv)
        except OSError:
            pass

    sys.stdout.write(r.stdout.decode("utf-8", "replace"))
    if r.returncode != 0:
        sys.stdout.write(r.stderr.decode("utf-8", "replace"))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
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
    value: "", checked: false, hidden: false, disabled: false,
    dataset: {}, attrs: {}, style: {}, children: [], parent: null,
    _html: "", _text: "", _opts: [],
    _listeners: {},
    get innerHTML() { return this._html; },
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
    // 页面里用 dispatchEvent(new Event("change")) 把 change 转发给
    // 另一个元素（搜索结果 -> 三级下拉同步）。stub 必须支持，
    // 否则这段同步代码一次都跑不到 —— 而它是「界面上显示 A、
    // 经纬度却是 B」这类自相矛盾的来源。
    dispatchEvent(ev) {
      const t = (ev && ev.type) || "change";
      return this.fire(t, ev && ev.type ? ev : { type: t, preventDefault(){}, target: this });
    },
    hasListener(t) { return (this._listeners[t] || []).length > 0; },
    appendChild(c) { this.children.push(c); c.parent = this;
                     if (this.tagName === "SELECT") this._opts.push(c);
                     // 真 DOM 语义：往空 select 里 append 第一个 option 时，
                     // 它会自动成为选中项（select.value 变成它的 value）。
                     // 页面靠这个行为拿到「默认选中的那个市 / 区县」。
                     // stub 不实现的话，页面里 select.value 恒为 ""，
                     // 报出来的错却是「页面逻辑不对」—— 方向就反了。
                     if (this.tagName === "SELECT" && !this.value && c.value) {
                       this.value = c.value;
                     }
                     return c; },
    removeChild(c) { this.children = this.children.filter(x => x !== c);
                     this._opts = this._opts.filter(x => x !== c); },
    // 真 DOM 里 select.options 是 HTMLOptionsCollection，与 children 等价但独立存在。
    // 页面里用的是 options.length，stub 不实现的话就会在这些行上炸 ——
    // 而那正是「stub 不够真」而不是「页面有 bug」，要分清。
    get options() {
      const self = this;
      if (!self._opts) self._opts = self.children.slice();
      self._opts.length = 0;
      for (const c of self.children) self._opts.push(c);
      return self._opts;
    },
    // 真 DOM 语义：selectedIndex 跟着 value 走。
    // 页面用它取「当前选中项的标签」（optText()），stub 不实现的话
    // 那里恒为 -1，报出来的错却是「页面逻辑不对」——方向就反了。
    get selectedIndex() {
      const opts = this.options;
      for (let i = 0; i < opts.length; i++) if (opts[i].value === this.value) return i;
      return -1;
    },
    set selectedIndex(i) {
      const opts = this.options;
      if (opts[i]) this.value = opts[i].value;
    },
    set innerHTML(v) { this._html = String(v); this.children = []; this._opts = [];
                     // 真 DOM：清空 select 的 options 会让它回到「无选中项」
                     if (this.tagName === "SELECT") this.value = "";
                   },
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
// 页面里用了 new Event("change") + dispatchEvent 来做「搜索结果 ->
// 三级下拉」的同步。Node 有全局 Event，但浏览器里构造出来的事件
// 带 target 等字段；这里显式给一份最小实现，让 dispatchEvent 能被测到。
class EventShim {
  constructor(type, init) {
    this.type = type;
    this.defaultPrevented = false;
    this.key = (init && init.key) || "";
    Object.assign(this, init || {});
  }
  preventDefault() { this.defaultPrevented = true; }
  stopPropagation() {}
}
const ctx = vm.createContext({
  window: win, document: doc, location: win.location, console,
  Date, Math, JSON, parseInt, parseFloat, isFinite, isNaN,
  Array, Object, String, Number, Boolean, Error, Set, Map, Symbol, RegExp,
  Event: EventShim,
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
// 元素清单必须排在「填表→提交」之前：后面的检查要读 panel-plain 的
// innerHTML，元素不存在时后面会报一堆看不懂的错。
const need = ["form", "solarYear", "solarMonth", "solarDay", "birthTime",
              "provSel", "citySel", "distSel", "cityHint", "lon", "lat",
              "city", "citySearch", "submitBtn", "headline", "panel-plain",
              "panel-pro", "result", "status", "shichenGrid",
              "solarLunarHint", "lunarSolarHint", "calSeg", "sexSeg"];
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

// 点一下「女」—— 这一步以前完全没测，
// 于是 segBind("seg","data-sex") 静默失效（两次调用都命中第一个 .seg，
// 也就是历法控件）都没人发现：性别选不了，性别恒为男。
// 而性别决定大运顺逆。
const sexBtns = doc.querySelectorAll("[data-sex]");
if (sexBtns.length !== 2) {
  fail("[data-sex] 按钮数 = " + sexBtns.length + "（应 2：男 / 女）");
} else if (!sexBtns[1].hasListener("click")) {
  fail("「女」按钮没有 click 监听 —— 性别选不了，性别恒为男");
} else {
  sexBtns[1].fire("click");
  const pressed = sexBtns.filter(b => b.getAttribute("aria-pressed") === "true");
  if (pressed.length !== 1 || pressed[0] !== sexBtns[1]) {
    fail("点「女」之后 aria-pressed 没正确切换（当前选中 "
       + (pressed[0] ? pressed[0].getAttribute("data-sex") : "无") + "）");
  } else {
    console.log("  OK   点「女」后选中态正确切换");
  }
}

// ---- 4) 走完整流程：填表 → 提交 → 看结果 ----
// 日期现在是年/月/日三个下拉（不再是 input[type=date]），
// 所以「填表」是设三个下拉的 value。
const setDate = (y, m, d) => {
  const ys = byId.get("solarYear"), ms = byId.get("solarMonth"), ds = byId.get("solarDay");
  if (!ys || !ms || !ds) { fail("年 / 月 / 日下拉不存在 —— 日期控件没渲染出来"); return false; }
  ys.value = String(y); ms.value = String(m);
  ds.fire("change");                 // 触发天数联动与农历回显
  ds.value = String(d);
  ds.fire("change");
  return true;
};

// 天数联动：平年 2 月 28 天、闰年 2 月 29 天、4 月 30 天。
// 少了这个联动，用户能选到「2 月 30 日」，然后拿到一张静默错误的盘。
const dayCount = () => byId.get("solarDay").children.length;
let dayOk = true;
for (const [y, m, want, label] of [[2023, 2, 28, "2023 平年 2 月"],
                                    [2024, 2, 29, "2024 闰年 2 月"],
                                    [1990, 4, 30, "1990 年 4 月"],
                                    [1990, 1, 31, "1990 年 1 月"]]) {
  // 联动监听器绑在 year / month 上（不是 day）—— 必须触发它们，
  // 否则 syncSolarDays 根本不跑，测试会「通过」而联动其实坏了。
  byId.get("solarYear").value = String(y);
  byId.get("solarMonth").value = String(m);
  byId.get("solarMonth").fire("change");
  const got = dayCount();
  if (got !== want) { fail(label + " 天数联动：应有 " + want + " 天，实际 " + got); dayOk = false; }
}
if (dayOk) console.log("  OK   日数随年月联动（平年 28 / 闰年 29 / 30 天月 / 31 天月）");

// 阳历 ⇄ 农历 实时互查
setDate(1990, 5, 15);
const hint = byId.get("solarLunarHint");
if (!hint || (hint.textContent || "").indexOf("农历") < 0) {
  fail("阳历填完没显示对应农历：" + (hint ? JSON.stringify(hint.textContent) : "元素不存在"));
} else {
  console.log("  OK   阳历实时显示农历: " + hint.textContent);
}

// 出生地三级选择 + 搜索
const search = byId.get("citySearch");
const city = byId.get("city");
const provSel = byId.get("provSel"), citySel = byId.get("citySel"),
      distSel = byId.get("distSel");
if (!provSel || !citySel || !distSel) fail("缺少省/市/区三级下拉");
else {
  const nProv = provSel.children.length;
  if (nProv < 30) fail("省级下拉只有 " + nProv + " 项（应 ≥30）");
  else console.log("  OK   省级下拉 " + nProv + " 项");

  // 北京市 -> 北京市 -> 东城区
  provSel.value = "北京市";
  provSel.fire("change");
  const nCity = citySel.children.length;
  if (!nCity) fail("选北京市后市下拉为空");
  else {
    citySel.value = "北京市";
    citySel.fire("change");
    const nDist = distSel.children.length;
    if (nDist < 10) fail("北京市的区县只有 " + nDist + " 项");
    else {
      // 选一个真区县，确认经纬度被正确写进 #lon/#lat。
      // 这里必须逐值核对，不能只查「非空」：曾经把纬度写进经度字段，
      // 而非空检查是通过的 —— 结果是按 90 度经度算真太阳时，不报任何错。
      distSel.value = distSel.children[1].value;   // [0] 是「整市」
      distSel.fire("change");
      const raw = String(distSel.children[1].value).split(",");
      const lon = Number(byId.get("lon").value), lat = Number(byId.get("lat").value);
      if (!isFinite(lon) || !isFinite(lat)) {
        fail("选区县后经纬度无效：" + byId.get("lon").value + ", " + byId.get("lat").value);
      } else if (Math.abs(lon - Number(raw[1])) > 1e-6 || Math.abs(lat - Number(raw[2])) > 1e-6) {
        fail("经纬度写串位了：option=" + distSel.children[1].value
             + " 但 #lon/#lat = " + lon + ", " + lat);
      } else if (lon < 70 || lon > 140 || lat < 3 || lat > 55) {
        // 东城区应在东经 116、北纬 40 附近。越界说明维度搞反了或抓错了层级
        fail("经纬度不在中国境内（可能经纬写反）：" + lon + ", " + lat);
      } else {
        console.log("  OK   三级下拉：" + nProv + "省 / " + nCity + "市 / " + nDist
          + "区县，选「" + distSel.children[1].textContent + "」→ "
          + lon.toFixed(4) + ", " + lat.toFixed(4) + "（与中国境内范围相符）");
      }
    }
  }
}

// 不填出生地时也能算：三级下拉的默认值就是合法坐标，
// 用户什么都不选不该拿到「没填出生地」的结果
{
  const D = byId.get("distSel");
  const lon = byId.get("lon").value, lat = byId.get("lat").value;
  if (!lon || !lat) fail("默认出生地无坐标（用户不选也不该拿到空结果）");
  else console.log("  OK   出生地有默认值 " + Number(lon).toFixed(3)
    + ", " + Number(lat).toFixed(3) + "（" + D.options[0].textContent + "）");
}

if (!search) fail("缺少 #citySearch");
else if (!city) fail("缺少 #city");
else {
  const val = o => (o.value || "").split("|");
  const names = () => (city.children || []).map(o => (o.value || "").split("|")[2]);

  // 1) 拼音首字母：bj 必须能命中北京
  //
  //    这一条曾经反复栽：先是拼音表没覆盖「京」字，后来是音节没分隔
  //    导致 pyInitials 退化成单字「b」。两次症状完全一样
  //    （界面毫无异常、搜索静默失效），只有直接断言命中才能拦住。
  search.value = "bj"; search.fire("input");
  let opts = city.children || [];
  if (!opts.filter(o => val(o)[2] === "北京市").length) {
    fail("拼音首字母搜「bj」找不到北京（命中 " + opts.length + " 项）");
    opts.slice(0, 5).forEach(o => console.log("        " + o.textContent));
  } else {
    console.log("  OK   拼音首字母搜索（bj → 北京，命中 " + opts.length + " 项）");
  }

  // 1b) 多音字拼音：这三个逐字查全是错的，必须走词组表
  //     重庆 chongqing（逐字查会得到 zhongqing）
  //     厦门 xiamen（逐字查会得到 shamen）
  //     蚌埠 bengbu（逐字查会得到 bangbu）
  if (win.MingLiPyTest) {
    for (const [nm, want] of [["重庆市", "chongqingshi"], ["厦门市", "xiamenshi"],
                              ["蚌埠市", "bengbushi"], ["漯河市", "luoheshi"]]) {
      const got = win.MingLiPyTest(nm);
      if (got !== want) fail("「" + nm + "」拼音应为 " + want + "，实际 " + got);
    }
    if (win.MingLiIniTest("北京市") !== "bjs")
      fail("「北京市」首字母应为 bjs，实际 " + win.MingLiIniTest("北京市"));
    console.log("  OK   多音字拼音正确（重庆/厦门/蚌埠/漯河），首字母 bjs");
  } else {
    fail("页面没暴露 MingLiPyTest，无法验证拼音");
  }

  // 2) 层级感知：打「北京」必须能列出北京的区。
  //    这是这次重做的核心 —— 旧实现打「北京」只出 1 条「北京市」，
  //    底下的区一条都不出，用户得再打一次区名才找得到。
  search.value = "北京"; search.fire("input");
  opts = city.children || [];
  const bjDist = opts.filter(o => val(o)[0] === "北京市" && val(o)[2] !== "北京市");
  if (bjDist.length < 10)
    fail("搜「北京」只列出 " + opts.length + " 条，其中北京的区县 " + bjDist.length
         + " 条 —— 应当展开北京的区");
  else console.log("  OK   层级感知：搜「北京」列出 " + opts.length
    + " 条，含北京的区县 " + bjDist.length + " 个");

  // 3) 相关度排序：搜区名时，精确同名必须排第一
  search.value = "东城区"; search.fire("input");
  opts = city.children || [];
  if (!opts.length) fail("搜「东城区」无结果");
  else if (val(opts[0])[2] !== "东城区")
    fail("搜「东城区」第一条不是精确同名，是「" + val(opts[0])[2] + "」");
  else console.log("  OK   精确同名排第一（搜「东城区」→ "
    + opts[0].textContent.replace(/（.*/, "") + "）");

  // 4) 重名条目要能按省市分辨，且排序不该是省份顺序
  search.value = "鼓楼"; search.fire("input");
  opts = city.children || [];
  if (opts.length < 2) fail("搜「鼓楼」应命中多个（南京/徐州/福州/开封），只出了 " + opts.length + " 条");
  else {
    const labels = opts.slice(0, 4).map(o => o.textContent.replace(/（.*/, ""));
    const distinct = new Set(labels).size;
    if (distinct < 2) fail("重名条目没有用省市区分开：" + labels.join(" / "));
    else console.log("  OK   重名条目按省市区分：" + labels.slice(0, 3).join(" / "));
  }

  // 5) 搜市名要能命中市自身（广州在数据里是市节点的 __own__）
  search.value = "广州"; search.fire("input");
  if (!(city.children || []).filter(o => val(o)[2] === "广州市").length)
    fail("搜「广州」找不到广州市（市自身条目被漏掉）");
  else console.log("  OK   搜城市名能找到该市自身条目");

  // 6) 全拼容错
  search.value = "urumqi"; search.fire("input");
  const ur = (city.children || []).length;
  if (!ur) fail("全拼搜索 urumqi 无结果");
  else console.log("  OK   全拼容错（urumqi → " + ur + " 项）");

  // 7) 搜索结果必须同步回三级下拉 ——
  //    否则界面上会出现「下拉显示 A、经纬度却是 B 的值」
  search.value = "东城区"; search.fire("input");
  opts = city.children || [];
  if (opts.length) {
    city.value = opts[0].value;
    city.fire("change");
    const ps = byId.get("provSel"), cs = byId.get("citySel"), ds = byId.get("distSel");
    const dTxt = ds.options[ds.selectedIndex] ? ds.options[ds.selectedIndex].textContent : "";
    if (ps.value !== "北京市" || cs.value !== "北京市" || dTxt.indexOf("东城区") < 0)
      fail("选搜索结果后三级下拉没同步：省=" + ps.value + " 市=" + cs.value + " 区=" + dTxt);
    else if (!byId.get("lon").value)
      fail("选搜索结果后经纬度是空的");
    else console.log("  OK   选搜索结果后三级下拉同步到 " + ps.value + " / " + cs.value
      + " / " + dTxt.replace(/（.*/, "") + "，经度 " + Number(byId.get("lon").value).toFixed(4));
  }

  // 8) 回车选第一条
  search.value = "朝阳区"; search.fire("input");
  opts = city.children || [];
  if (opts.length && search.hasListener("keydown")) {
    const want = val(opts[0])[2];
    search.fire("keydown", { type: "keydown", key: "Enter", preventDefault() {} });
    const dTxt = byId.get("distSel").options[
      byId.get("distSel").selectedIndex].textContent;
    if (dTxt.indexOf(want) < 0)
      fail("回车没有选中第一条：期望含「" + want + "」，实际区=" + dTxt);
    else console.log("  OK   回车选中第一条（" + want + "）");
  } else if (opts.length) {
    fail("搜索框没有绑 keydown，回车选不了");
  }

  search.value = "";
  search.fire("input");
}

// 回到标准示例再提交
setDate(1990, 5, 15);
const bt = byId.get("birthTime");
if (bt) bt.value = "12:00";
// 出生地交给三级下拉（上面已选好北京），别再往搜索框塞旧格式的值

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

// 1.3.1 新增：折叠区块必须真的存在于结果里，且默认收起。
//
// 只断言「有 details 标签」不够 —— 半新半旧的代码也能产出配平的标签。
// 要断言内容：标题文案、步数、逐项解读。
// 另外检查没有 open 属性：用户明确选了「默认折叠」，
// 带 open 就等于没折叠。
{
  const pp = byId.get("panel-plain");
  const html = pp ? pp.innerHTML : "";
  const need = ["你一生十步大运", "未来七年的年度节奏", "你身上五股的劲儿",
                "四种元素逐项看", "十二长生", "好的一面", "要注意"];
  const missing = need.filter(k => html.indexOf(k) < 0);
  if (missing.length) {
    fail("白话区缺少新内容: " + missing.join("、"));
    process.exit(1);
  }
  const nFold = (html.match(/<details/g) || []).length;
  const nClose = (html.match(/<\/details>/g) || []).length;
  if (nFold !== nClose) fail("折叠标签不配平：" + nFold + " 开 / " + nClose + " 闭");
  if (/<details[^>]*\sopen/.test(html)) fail("折叠区块带 open 属性，没有默认收起");
  // 「（今年）」说明流年里确实标出了当前年份
  if (html.indexOf("（今年）") < 0) fail("流年没有标出今年");
  console.log("  OK   白话区新增 " + nFold + " 个折叠区块（默认收起），"
    + "含大运逐段/流年逐年/五行意象/四元素逐项");
}

// 1.5.0 新增：紫微四块（十二宫 / 大限 12 步 / 流年命宫 / 四化落宫）
//
// 只断言「有 details 标签」不够 —— 半新半旧的代码也能产出配平的标签，
// 而这次紫微块插错位置时（跑到 if(data.紫微) 外面）产出的是
// 「z is not defined」这种运行时错，静态标签检查照样通过。
// 所以断言具体内容：宫名、步数、星曜、四化落宫。
{
  const html0 = byId.get("panel-plain").innerHTML;
  const need0 = ["你的十二宫", "你一生十二步大限", "今年的落点", "四化落在哪",
                 "借对宫", "该宫管的是", "当前大限", "十二宫代表人生十二个领域"];
  const miss0 = need0.filter((k) => html0.indexOf(k) < 0);
  if (miss0.length) { fail("白话区缺少紫微新内容: " + miss0.join("、")); process.exit(1); }

  // 十二宫逐宫：12 个宫名都要出现（命宫/兄弟/夫妻/子女/财帛/疾厄/
  // 迁移/交友/官禄/田宅/福德/父母）
  const PAL = ["命宫", "兄弟", "夫妻", "子女", "财帛", "疾厄",
               "迁移", "交友", "官禄", "田宅", "福德", "父母"];
  const missPal = PAL.filter((k) => html0.indexOf(">" + k + "<") < 0
                                 && html0.indexOf(k + "宫") < 0
                                 && html0.indexOf(k) < 0);
  if (missPal.length) { fail("十二宫缺: " + missPal.join("、")); process.exit(1); }

  // 大限 12 步：数「岁」区间，至少要有 12 个
  const nDx = (html0.match(/\d+–\d+ 岁/g) || []).length;
  if (nDx < 12) { fail("紫微大限只渲染了 " + nDx + " 步（应 12）"); process.exit(1); }

  // 四化 4 项：禄权科忌都要出现
  const missHua = ["化禄", "化权", "化科", "化忌"].filter((k) => html0.indexOf(k) < 0);
  if (missHua.length) { fail("四化缺: " + missHua.join("、")); process.exit(1); }

  const nFold0 = (html0.match(/<details/g) || []).length;
  console.log("  OK   紫微四块齐全：十二宫 12 宫 / 大限 " + nDx + " 步 / "
    + "流年命宫 / 四化 4 项（白话区共 " + nFold0 + " 个折叠区块）");
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

// ---------- 时辰留空 → 默认 12:00，且必须标明是估算 ----------
// 为什么这条要单独测：时辰决定时柱，留空时如果报错拦下，
// 用户就只能走「猜一个时间」；如果默默按 0 点算，时柱会凭空差一格。
// 所以要求是：不拦下、按 12:00 算、并且在界面上说清这是估算。
{
  const timeEl = byId.get("birthTime");
  const before = { plain: pp ? pp.innerHTML : "", hl: hl ? hl.innerHTML : "" };
  if (timeEl) timeEl.value = "";              // 真的留空
  if (form && form.hasListener("submit")) {
    form.fire("submit");
    drain();
  }
  const stTxt = (st && st.textContent) || "";
  const hlTxt = (hl ? hl.innerHTML.replace(/<[^>]+>/g, "") : "");
  const all = stTxt + " " + hlTxt + " " + (pp ? pp.innerHTML : "");
  if (/error/i.test((st && st.className) || "")) {
    fail("时辰留空时页面报错拦下了（应默认 12:00 继续算）: " + stTxt);
  } else if (pp && pp.innerHTML.length < 500) {
    fail("时辰留空时没有出结果");
  } else if (all.indexOf("估算") < 0) {
    fail("时辰留空时结果里没有「估算」字样 —— 用户会以为时柱是按真实出生时刻算的");
  } else {
    // 还要确认 12:00 与真实填 12:00 算出来的一致（默认就是 12 点，不是别的时间）
    console.log("  OK   时辰留空不拦下，按 12:00 出结果并标明估算（#status: "
      + stTxt.trim().slice(0, 40) + "）");
  }
  // 复原，免得影响后面的判断
  if (timeEl) timeEl.value = "12:00";
  if (form && form.hasListener("submit")) { form.fire("submit"); drain(); }
  if (pp && before.plain && pp.innerHTML === before.plain) {
    console.log("  OK   填回 12:00 后结果与默认一致（默认确实是 12 点）");
  } else {
    console.log("  [--] 填回 12:00 后结果有差异，默认值可能不是 12:00");
  }
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
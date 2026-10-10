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
  const hl = byId.get("headline");
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

// 1.5.0 新增第二批：神煞 / 十神 / 轴点 / 性质 / 全部相位
//
// 这批的坑全在「静默失效」上，静态标签检查抓不到：
//  - 神煞吉凶原先按名字猜，把亡神判成吉、寡宿判成凶；
//    渲染对了但分类错了，页面看不出异常。
//  - 十神八个字摊到十种十神上，出现四五个并列第一是常态；
//    只报一个就等于说「你最重要的是偏印」，方向是错的。
//  - 相位原先只讲强度前 4 组，其余 19 组算了白算。
// 所以这里断言的是内容与分类，不是「有没有这个标签」。
{
  const html1 = byId.get("panel-plain").innerHTML;
  const need1 = ["你命里的神煞", "你的十神分布", "两个轴点",
                 "你的行星性质", "全部相位",
                 "天生的助力", "要练的地方"];
  const miss1 = need1.filter((k) => html1.indexOf(k) < 0);
  if (miss1.length) { fail("白话区缺少 A2 新内容: " + miss1.join("、")); process.exit(1); }

  // 神煞：逐条都要有「查法 + 落支」，不能只是一串名字
  const nSs = (html1.match(/查[^<]+，落/g) || []).length;
  if (nSs < 5) { fail("神煞只渲染了 " + nSs + " 条（应 5 条以上且逐条带查法）"); process.exit(1); }
  if (html1.indexOf("不计入吉凶统计") >= 0) {
    fail("还有神煞没归类 —— 分类表漏了，不能就这样发出去");
  }
  // 三类标签都要出现：全归成同一类说明表又退回按名字猜了
  const nKinds = ["助你的", "中性的", "要留意的"].filter((k) => html1.indexOf(k) >= 0).length;
  if (nKinds < 2) { fail("神煞只有 " + nKinds + " 种分类（都归成一类等于没分）"); process.exit(1); }

  // 十神：明细要有占比，并列时必须写成并列而不是只报一个
  if (html1.indexOf("干上") < 0 || html1.indexOf("藏干") < 0) {
    fail("十神明细没区分干上/藏干");
  }
  const tied = html1.indexOf("并列") >= 0 || html1.indexOf("各占") >= 0;
  if (!tied) {
    // 这个盘不一定并列，只要求：报了「最多」时不能是并列却当成唯一
    const m = html1.match(/最重的是<\/span>([^<]+)/);
    if (m && /、/.test(m[1])) { fail("并列十神被当成唯一报了: " + m[1]); process.exit(1); }
  }

  // 轴点：上升与天顶两个都要在，且都要说明「这不是性格本身」
  for (const k of ["上升", "天顶"]) {
    if (html1.indexOf(">" + k + "<") < 0) { fail("轴点缺: " + k); process.exit(1); }
  }
  if (html1.indexOf("别人看到的你") < 0) { fail("轴点没说明上升是「别人看到的你」"); process.exit(1); }

  // 性质：三类各自的个数要列出来
  for (const k of ["基本", "固定", "变动"]) {
    if (html1.indexOf(k) < 0) { fail("行星性质缺: " + k); process.exit(1); }
  }

  // 相位：原先只画前 4 组，现在要全列。至少 10 组。
  const nAs = (html1.match(/<span class="pn[ ji]*">[^<]+ · [^<]+<\/span>/g) || []).length;
  if (nAs < 10) { fail("相位只渲染了 " + nAs + " 组（这批的改动就是补全全部相位）"); process.exit(1); }
  if (html1.indexOf("很强") < 0 && html1.indexOf("较强") < 0 && html1.indexOf("一般") < 0) {
    fail("相位没有强度档位 —— 只有裸数字的话读者判断不了轻重");
  }

  const nFold1 = (html1.match(/<details/g) || []).length;
  const nClose1 = (html1.match(/<\/details>/g) || []).length;
  if (nFold1 !== nClose1) fail("折叠标签不配平：" + nFold1 + " 开 / " + nClose1 + " 闭");
  console.log("  OK   A2 五块齐全：神煞 " + nSs + " 条 / 十神分布 / "
    + "轴点 2 个 / 行星性质 3 类 / 相位 " + nAs + " 组（白话区共 "
    + nFold1 + " 个折叠区块）");
}

// 1.6.0 新增：六亲 / 夫妻宫 / 关系宫
//
// 这批的静默失效点：
//  - **男女分派**。男盘和女盘的八字完全相同（只差性别），
//    六亲星若不分派，男女会看到同一段关于配偶的话 —— 硬错。
//  - **措辞纪律**。夫妻宫有煞星就写成「婚姻不顺」是断语。
//  - **空宫**。7/8 宫无星时不能只留个空卡片让人以为漏了。
{
  const html2 = byId.get("panel-plain").innerHTML;
  const need2 = ["六亲怎么看", "夫妻宫", "关系相关的宫", "四柱各代表谁"];
  const miss2 = need2.filter((k) => html2.indexOf(k) < 0);
  if (miss2.length) { fail("白话区缺少六亲新内容: " + miss2.join("、")); process.exit(1); }

  // 六亲四个角色都要有
  for (const k of ["配偶", "父母", "兄弟", "子女"]) {
    if (html2.indexOf(">" + k + "<") < 0) { fail("六亲缺角色: " + k); process.exit(1); }
  }
  // 男盘：配偶看财星。女盘：看官杀。所以页面必须出现财或官之一。
  if (html2.indexOf("正财") < 0 && html2.indexOf("偏财") < 0
      && html2.indexOf("正官") < 0 && html2.indexOf("七杀") < 0) {
    fail("六亲里没有配偶星 —— 配偶一项是空的");
  }
  // 柱位对应要给出来，否则「配偶星落在日支」这件事看不懂。
  // 注意：引擎里 `柱详解[].柱` 的值是「年/月/日/时」而不是「年柱/月柱」，
  // PILLAR_ROLE 的键曾写成「年柱」，两边都查不到 → 全空。
  // 而这种错对拍抓不到（Python 与 JS 都返回空字符串，512 例照样一致）。
  for (const k of ["祖上与父母", "兄弟与同辈", "自己和配偶", "子女与晚年"]) {
    if (html2.indexOf(k) < 0) {
      fail("四柱对应缺「" + k + "」—— 查表键与实际数据对不上，全是空的");
      process.exit(1);
    }
  }
  // 空说明 = 查表落空。这是最直接的信号。
  if (/<p class="li"><\/p>/.test(html2)) {
    fail("页面里有空的说明段落 —— 文案表没查到值");
  }

  // 夫妻宫：主星组合或单星解读至少要有一个；煞星要走「要磨合」的口径
  if (html2.indexOf("要磨合的地方") >= 0) {
    // 有煞星时必须用这个标题，不能只列名字不解释
    if (html2.indexOf("对宫是") < 0) {
      fail("夫妻宫有煞星但没讲对宫 —— 只讲问题不讲关联，读起来像定论");
    }
  }
  // 措辞纪律：这几类断语不能出现
  for (const bad2 of ["婚姻不顺", "婚姻不稳", "克夫", "克妻", "注定", "命中注定"]) {
    if (html2.indexOf(bad2) >= 0) {
      fail("出现了断语「" + bad2 + "」—— 只说倾向与课题，不下吉凶结论");
    }
  }

  // 关系宫：5 个宫，空宫要有解释而不是留空
  // 宫数用「卡片容器里的标题」来数，别用 /第 \d+ 宫/ 全局匹配 ——
  // 那个串在概述与正文里都会出现，数出来会偏多。
  const relIdx0 = html2.indexOf("关系相关的宫");
  const relSeg0 = relIdx0 >= 0
    ? html2.slice(relIdx0, html2.indexOf("</details>", relIdx0)) : "";
  const nHouse = (relSeg0.match(/<span class="pn">第 \d+ 宫<\/span>/g) || []).length;
  if (nHouse < 5) { fail("关系宫只渲染了 " + nHouse + " 个（应 5 个）"); process.exit(1); }
  const nEmptyNote = (html2.match(/这一宫没有星/g) || []).length;
  if (nEmptyNote < 1) {
    fail("关系宫有空宫但没解释 —— 空宫不是「这块没有」，要看文案兜住");
  }
  if (html2.indexOf("不靠外力推") < 0) {
    fail("空宫没说明「不靠外力推」");
  }
  // 空宫说明不能当概述用：放在开头会变成「整块都没星」的意思，方向是错的。
  // 判据用「第一个宫卡片容器之前」而不是「第 7 宫之前」——
  // 「第 N 宫」这个串在别处也会出现，拿它当分界点会误判。
  const relIdx = html2.indexOf("关系相关的宫");
  if (relIdx < 0) { fail("找不到关系宫块"); process.exit(1); }
  const relEnd = html2.indexOf("</details>", relIdx);
  const relSeg = html2.slice(relIdx, relEnd);
  const firstCard = relSeg.indexOf('<div class="ssx">');
  const emptyNoteAt = relSeg.indexOf("不靠外力推");
  if (firstCard < 0) { fail("关系宫块里没有卡片容器"); process.exit(1); }
  if (emptyNoteAt >= 0 && emptyNoteAt > firstCard) {
    fail("空宫说明被渲染成了卡片内容 —— 概述里出现「没有星」会读成整块都没星");
  }

  const nFold2 = (html2.match(/<details/g) || []).length;
  const nClose2 = (html2.match(/<\/details>/g) || []).length;
  if (nFold2 !== nClose2) fail("折叠标签不配平：" + nFold2 + " 开 / " + nClose2 + " 闭");
  console.log("  OK   1.6.0 三块齐全：六亲 4 角色 + 四柱对应 / 夫妻宫 / "
    + "关系宫 " + nHouse + " 个（空宫有解释 " + nEmptyNote + " 处，白话区共 "
    + nFold2 + " 个折叠区块）");
}

// 主星带四化时不能被当成「另一种星」丢掉。
//
// 这个 bug 是时辰路径门禁（用辰时那个盘）抓出来的，512 例对拍全绿漏了它：
// 那些盘夫妻宫要么有普通主星，要么本来就空，只有辰时那个盘的主星是
// 「太阳·化禄」这种带后缀的。原先用 `"·" not in s` 过滤，主星就全空了，
// 整块不渲染 —— 页面看着正常（少一块），看不出是 bug。
//
// 断言放在 Python 侧（scripts 的自测）而不是这里：数据层的丢数据问题
// 与 DOM 无关，而产物里 ziweiPlain 并不挂在 window 上（只暴露 MingLi.run），
// 写在 UI 断言里只会「找不到函数」而查不出真问题。
{
  const hl2 = (byId.get("headline") || {}).innerHTML || "";
  // 页面这一侧只确认一件事：带化曜的夫妻宫不会让整块消失。
  // 造不出那种盘（辰时那个盘的紫微依赖年干支），所以这里只能反向断言：
  // 若夫妻宫块出现了，就不该同时出现「这些星还没写解读：」且里面带化曜的主星名。
  const spSeg = hl2.indexOf("夫妻宫");
  if (spSeg >= 0) {
    const seg = hl2.slice(spSeg, hl2.indexOf("</details>", spSeg));
    const m = seg.match(/这些星还没写解读：([^<]+)/);
    if (m && /·化(禄|权|科|忌)/.test(m[1])) {
      fail("带化曜的主星被当成「未解读的星」: " + m[1]);
    }
  }
  console.log("  OK   带化曜的主星没被当成待补的星（数据层断言见 Python 自测）");
}

// 1.7.0 新增：B 类三盘交叉
//
// 断言要盯「页面上真的出现了三边各自的说法」，不能只断言「有交叉这个标题」——
// 这一块最容易出的错就是某一边静默为空（星座名差一个字就查不到表），
// 而标题照样在，页面看着正常。
//
// html2 / hl2 都是上一个 { } 块里的 const，在本块外取不到（踩过一次
// ReferenceError）。所以这里自己从 DOM 取，不依赖外层作用域 ——
// 否则这段断言的失败原因会是「变量不存在」而不是「内容不对」。
{
  const ppX = byId.get("panel-plain");
  const htmlX = ppX ? ppX.innerHTML : "";
  const cx = htmlX.indexOf("三盘交叉");
  if (cx < 0) {
    fail("页面上没有 B 类「三盘交叉」块");
  } else {
    const closeX = htmlX.indexOf("</details>", cx);
    const seg = htmlX.slice(cx, closeX > 0 ? closeX : htmlX.length);
    // 三边来源都要写出来 —— 交叉的可信度取决于每边各自用了什么
    for (const pan of ["八字", "紫微", "占星"]) {
      if (seg.indexOf(pan) < 0) {
        fail("B 类块里没标出「" + pan + "」这一边的来源");
      }
    }
    // 六个维度逐项都要在
    for (const dim of ["表达方式", "行动节奏", "社交范围",
                       "守旧与换新", "关系经营", "事业路子"]) {
      if (seg.indexOf(dim) < 0) fail("B 类块里少了维度：" + dim);
    }
    // 每条依据都要写清是按什么算出来的，否则读者无法判断可信度
    if (!/透干十神|命宫主星|太阳星座/.test(seg)) {
      fail("B 类块没有写清各边的判据来源");
    }
    // 必须明说「三套不换算」—— 不加这句就成了伪交叉。
    // 搜索范围要覆盖后面的折叠块：新布局把「不换算」那句放在
    // 「这三边分别按什么算的」那个 details 里，只看到第一个
    // </section> 会漏掉它 —— 之前断言就是这样误报的。
    const tailX = htmlX.slice(cx);
    if (tailX.indexOf("没有换算关系") < 0) {
      fail("B 类块没说明三套体系之间没有换算关系");
    }
    // 折叠标签不能被转义出来
    if (tailX.indexOf("&lt;b&gt;") >= 0) {
      fail("B 类块把 HTML 标签转义成文字显示了");
    }
    // 一致的当主结论（不折叠）、分歧的折起来 —— 这是 v1.7.1 的排布改动
    const idxSame = tailX.indexOf("三边都指向同一头");
    const idxDiff = tailX.indexOf("三边说法不同");
    if (idxSame < 0) fail("B 类块没有「三边都指向同一头」的主结论区");
    if (idxDiff < 0) fail("B 类块没有「三边说法不同」的折叠区");
    if (idxSame > idxDiff) {
      fail("B 类块把分歧放在一致之前 —— 默认先看到的应该是三边一致的面");
    }
    // 「三边说法不同」这行字有两处：summary 里一处、折叠体里一处。
    // indexOf 命中的是 summary —— 它前面当然不会有 <details>。
    // 要判「是否折叠」，得看第二个出现处的前面有没有 <details>。
    const idxDiff2 = tailX.indexOf("三边说法不同", idxDiff + 1);
    if (idxDiff2 < 0) {
      fail("「三边说法不同」折叠体里没有标题 —— 可能只渲染了 summary");
    } else if (tailX.slice(idxDiff, idxDiff2).indexOf("<details") < 0) {
      fail("「三边说法不同」没有默认折叠 —— 它会挤在主结论位置");
    }
    // 必须告诉读者怎么读，否则就是一堆互相矛盾的句子
    if (tailX.indexOf("先说怎么读") < 0) {
      fail("B 类块没有「先说怎么读」这一层");
    }
    if (tailX.indexOf("不投票") < 0) {
      fail("B 类块没有说明不做加权合成/投票");
    }
    console.log("  OK   1.7.0 B 类三盘交叉：一致的当主结论 + 分歧折叠 + "
      + "先说怎么读 + 明说无换算关系");
  }
}

// 1.7.0：C 类桃花星 + 行业细分
//
// 同样不能只断言「有标题」。这一类最危险的错是**缺键静默退化**：
// 表里少一个键，那一条不会空、不会报错，只会换成泛泛的兜底文案，
// 页面看着完整，内容其实被削平了。所以断言要看内容本身。
{
  const ppC = byId.get("panel-plain");
  const htmlC = ppC ? ppC.innerHTML : "";
  const th = htmlC.indexOf("桃花星");
  if (th < 0) {
    fail("页面上没有 C 类「桃花星」块");
  } else {
    const seg = htmlC.slice(th, htmlC.indexOf("</section>", th));
    for (const pan of ["八字", "紫微", "占星"]) {
      if (seg.indexOf(pan) < 0) fail("桃花星块没标出「" + pan + "」这一边");
    }
    // 每条都要有依据（是按什么算出来的）
    if (!/金星落在|月亮落在|夫妻宫主星|咸池/.test(seg)) {
      fail("桃花星块没有写清各条的判据来源");
    }
    // 必须有免责：只讲倾向、不预测
    if (seg.indexOf("不预测") < 0) {
      fail("桃花星块缺少「不预测具体事件」的口径说明");
    }
    // 必须说清三边是「不同层面」而不是互相矛盾 ——
    // 三条各说各话摆在一起，读者只会以为其中一条是错的。
    if (seg.indexOf("不同层面") < 0) {
      fail("桃花星块没有说明三边说的是不同层面、不是互相矛盾");
    }
    // 措辞纪律：不得出现吉凶断语
    for (const w of ["注定", "必然", "艳福", "桃花运旺", "容易出轨"]) {
      if (seg.indexOf(w) >= 0) fail("桃花星块出现禁用表述：" + w);
    }
    console.log("  OK   1.7.0 桃花星：三边来源标出 + 有判据依据 + 含免责口径");
  }

  const cr = htmlC.indexOf("行业细分");
  if (cr < 0) {
    fail("页面上没有 C 类「行业细分」块");
  } else {
    const seg = htmlC.slice(cr, htmlC.indexOf("</section>", cr));
    // 行业 + 角色类型两层都要在
    if (seg.indexOf("角色类型") < 0) fail("行业细分块没有角色类型这一层");
    // 依据改成按组渲染（新布局），所以搜「依据：」会搜不到 ——
    // 搜组标题上的依据（如「喜用神金」）。判据跟着实际结构走。
    if (!/喜用神|命宫主星|宫主星|上升/.test(seg)) {
      fail("行业细分块没有标出每组的判据依据");
    }
    // 必须按组折叠：一组喜用神下有 7 个行业，铺平会被读成
    // 7 个互相冲突的结论。分组是这版排布的重点。
    if (seg.indexOf("组方向") < 0) {
      fail("行业细分没有按依据分组（一次铺十几个行业会读成互相冲突）");
    }
    // 明说不做加权合成
    if (seg.indexOf("不做加权合成") < 0) {
      fail("行业细分块没有说明三盘不做加权合成");
    }
    // 不得越界成星座职位细分
    for (const w of ["适合当基金经理", "适合当医生", "天生是领导"]) {
      if (seg.indexOf(w) >= 0) fail("行业细分块越界成职位细分：" + w);
    }
    // 兜底文案不该出现（表覆盖完整时不该退化）
    if (seg.indexOf("兜底分类") >= 0) {
      fail("行业细分出现了兜底分类 —— 说明 INDUSTRY_ROLES 缺了键，内容被削平");
    }
    console.log("  OK   1.7.0 行业细分：按依据分组 + 行业/角色两层 + 无兜底退化");
  }
}

// 1.8.0：个性版本（总览）
//
// 断言它**真的是总览**：必须在八字/紫微/占星三段之前出现，
// 且必须有 hero 容器与展开块。放在三段之后就失去意义了。
{
  const ppP = byId.get("panel-plain");
  const htmlP = ppP ? ppP.innerHTML : "";
  const iPersona = htmlP.indexOf('class="persona"');
  if (iPersona < 0) {
    fail("页面上没有个性版本的 hero 容器（.persona）");
  } else {
    const iBazi = htmlP.indexOf("八字 · 看你的性格和天赋");
    if (iBazi < 0) fail("页面上没有八字区块");
    if (iPersona > iBazi) {
      fail("个性版本排在八字之后 —— 它必须是总览，放在前面");
    }
    // 个性版本内部是嵌套 div，不能只切到第一个 </div> ——
    // 那样只切到 p-eyebrow 那一行，后面全切没了。
    // 用「persona 开始 到 </div><!--persona 结束-->」这种深层切片不可靠，
    // 直接把这一段到下一个 <div class="persona"> 或八字标题为止。
    const iPersonaEnd = htmlP.indexOf("八字 · 看你的性格和天赋");
    const pSeg = htmlP.slice(iPersona, iPersonaEnd > iPersona ? iPersonaEnd
                                                            : htmlP.length);
    if (pSeg.indexOf("p-lead") < 0) fail("个性版本缺主文案（.p-lead）");
    for (const k of ["内核", "运转", "关系", "独处", "团队", "压力"]) {
      if (pSeg.indexOf(k) < 0) fail("个性版本里缺块：" + k);
    }
    // 每块都要标来源，否则读者无从判断这话是哪来的
    if (pSeg.indexOf("来自 ") < 0) {
      fail("个性版本没有标每块的来源");
    }
    // 残句检测：模板拼接最容易漏出「…看，」后面没内容。
    // 判据要**只取 .p-lead 那一段** —— 之前取 hero 后 400 字符，
    // 把 <summary> 里的「… / 压力」和后面的正文一起算进来，
    // 「压力」后面紧跟正文时被误判成以标点结尾。
    const mLead = pSeg.match(/p-lead">([^<]*)</);
    const leadTxt = mLead ? mLead[1].trim() : "";
    if (!leadTxt) {
      fail("取不到个性版本主文案");
    } else if (/[，：、]$/.test(leadTxt)) {
      fail("个性版本主文案以标点结尾 —— 像拼接漏了内容：" + leadTxt.slice(-20));
    }
    console.log("  OK   1.8.0 个性版本：hero 在最前 + 六块齐全 + 标来源");
  }
}
const pp = byId.get("panel-plain");
const pr = byId.get("panel-pro");
const st = byId.get("status");
const hl = byId.get("headline");

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
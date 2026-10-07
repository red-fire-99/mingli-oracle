#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从构建产物里把引擎抠出来，在 Node 里端到端跑一遍。

为什么需要它
------------
verify_dist.py 只做静态检查（占位符替换、括号配平、无外链）。
但「静态看起来对、实际跑不起来」是这类内联产物的典型翻车方式 ——
上一次的线上事故就是这个形态：文件都在、SHA 都对，
但 pyodide.js 里那句 `import(pyodide.asm.js)` 指向一个没下载的文件，
页面表现为「所有源都试过了」，极具误导性。

所以必须**真的把产物里的引擎执行一遍**，验证：
  1. 内联的 IIFE 语法合法、能跑完
  2. window.MingLi 真的挂上了，且 run 是函数
  3. 拿真实生辰能排出盘，产出的 HTML 非空、不含 undefined/NaN
  4. HTML 是自包含的（没有外链引用）

用法
----
    python web/test_load_chain.py [--js node] [--dist web/dist/index.html]
"""
import argparse
import io
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(HERE, "dist", "index.html")

# 在 Node 里跑的驱动器。刻意写成 CommonJS（.cjs）：
# 本项目要支持 Node 18~22，用 .mjs 的话 require 不可用，得全改 import，
# 而这只是一次性测试脚本，不值得为它引入模块类型上的前提。
DRIVER = r"""
const fs = require("node:fs");
const vm = require("node:vm");

const html = fs.readFileSync(process.argv[2], "utf8");

// 只取第一段 <script>：引擎 IIFE 就躺在那里。
const m = html.match(/<script>([\s\S]*?)<\/script>/);
if (!m) { console.error("FAIL: 找不到内联 script"); process.exit(1); }
const code = m[1];

// 最小 DOM stub。存在的理由：产物里引擎与 UI 写在**同一个** <script> 里，
// 只测引擎就得先把 UI 那半边也执行一遍（否则会撞上 document is not defined）。
//
// 这不是为了替代真浏览器 —— 而是为了让「引擎 + UI 装配」这段代码真的跑一遍：
// 如果引擎没挂上 window.MingLi，boot() 会走错误分支，
// 那个分支我们自己写的断言抓不到，但真浏览器里会白屏。
function mkEl(tag) {
  const el = {
    tagName: (tag || "div").toUpperCase(),
    className: "", innerHTML: "", textContent: "", value: "",
    style: {}, dataset: {}, hidden: false, disabled: false,
    checked: false, classList: { add(){}, remove(){}, contains(){ return false; } },
    children: [],
    setAttribute(){}, getAttribute(){ return null; }, removeAttribute(){},
    appendChild(c){ this.children.push(c); return c; },
    addEventListener(){}, removeEventListener(){},
    querySelector(){ return mkEl("div"); },
    querySelectorAll(){ return []; },
    closest(){ return null; },
    remove(){}, scrollIntoView(){},
    getAttribute(){ return null; },
  };
  return el;
}
const doc = {
  querySelector(){ return mkEl("div"); },
  querySelectorAll(){ return []; },
  getElementById(){ return mkEl("div"); },
  createElement: mkEl,
  addEventListener(){},
};

const win = { document: doc, location: { href: "https://example.invalid/" } };
const ctx = vm.createContext({
  window: win, document: doc, console,
  location: win.location,
  // 引擎真正用到的全局。多给任何一个，都可能让
  // 「浏览器里其实会报错」的代码在这里蒙混过关。
  Date, Math, JSON, parseInt, parseFloat, isFinite, isNaN,
  Array, Object, String, Number, Boolean, Error, Set, Map, Symbol,
});
ctx.globalThis = ctx;

try {
  vm.runInContext(code, ctx, { filename: "inline-engine.js" });
} catch (e) {
  console.error("FAIL: 引擎+UI 执行抛错 -> " + (e && e.stack || e));
  process.exit(1);
}

const ML = win.MingLi;
if (!ML) { console.error("FAIL: window.MingLi 未挂上"); process.exit(1); }

const need = ["run", "build", "renderBazi", "renderZiwei", "renderAstro",
              "renderPlain", "renderGlossary", "headline"];
for (const k of need) {
  if (typeof ML[k] !== "function") {
    console.error("FAIL: 缺导出 " + k); process.exit(1);
  }
}

// 覆盖：正常、跨立春、晚子时、闰月、无时刻无经纬（最容易崩的组合）
const cases = [
  { tag: "常规", solar: [1990, 5, 15], hour: "12:00", sex: "男",
    place: "北京", lon: 116.41, lat: 39.90 },
  { tag: "跨立春晚子时", solar: [2024, 2, 4], hour: "23:00", sex: "女",
    place: "拉萨", lon: 91.11, lat: 29.97 },
  { tag: "边界年", solar: [1900, 1, 1], hour: "00:30", sex: "男",
    place: "上海", lon: 121.47, lat: 31.23 },
  { tag: "闰五月", lunar: [1990, 5, 15], leap: true, hour: "12:00", sex: "男",
    place: "北京", lon: 116.41, lat: 39.90 },
  { tag: "无时刻无经纬", solar: [1990, 5, 15], sex: "男" },
];

let bad = 0;
for (const c of cases) {
  const inp = Object.assign({}, c); delete inp.tag;
  let r;
  try {
    r = ML.run(inp);
  } catch (e) {
    console.error("  FAIL " + c.tag + ": 抛错 " + (e && e.message));
    bad++; continue;
  }
  const htmlOut = r.plain_html + r.pro_html;
  if (!r.headline || !r.plain_html.length || !r.pro_html.length) {
    console.error("  FAIL " + c.tag + ": 输出为空");
    bad++; continue;
  }
  // undefined / NaN 混进 HTML 是移植最常见的漏网之鱼
  const mm = htmlOut.match(/.{0,50}(undefined|NaN|\[object Object\]).{0,50}/);
  if (mm) {
    console.error("  FAIL " + c.tag + ": HTML 含 " + mm[0]);
    bad++; continue;
  }
  // 自包含：产物里不能出现远程引用
  const remote = htmlOut.match(/(?:src|href)\s*=\s*["'](?!#)([^"']+)/g);
  if (remote) {
    console.error("  FAIL " + c.tag + ": 排盘 HTML 含外部引用 " + remote[0]);
    bad++; continue;
  }
  console.log("  OK   " + c.tag + "  headline: " + r.headline);
  console.log("       plain " + r.plain_html.length
              + " 字符 / pro " + r.pro_html.length + " 字符");
}

if (bad) { console.error("端到端验证失败 " + bad + " 例"); process.exit(1); }
console.log("PASS: 产物内联引擎端到端可用");
"""


def main(argv=None):
    p = argparse.ArgumentParser(description="把产物里的引擎抠出来端到端跑")
    p.add_argument("--js", default="node", help="Node 可执行文件")
    p.add_argument("--dist", default=DIST, help="待验产物")
    a = p.parse_args(argv)

    if not os.path.isfile(a.dist):
        print("找不到产物 %s，请先运行 build_web.py" % a.dist)
        return 1

    html = io.open(a.dist, encoding="utf-8").read()
    print("端到端验证 %s（%.1f KB）\n"
          % (a.dist, len(html.encode("utf-8")) / 1024.0))

    drv = os.path.join(HERE, ".load_chain_test.cjs")
    try:
        io.open(drv, "w", encoding="utf-8").write(DRIVER)
        try:
            r = subprocess.run([a.js, drv, a.dist], capture_output=True, timeout=300)
        except FileNotFoundError:
            print("找不到 Node：%s（用 --js 指定，或在 CI 里装 Node）" % a.js)
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
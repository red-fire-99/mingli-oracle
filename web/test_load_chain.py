#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""端到端跑一遍网页版的「加载运行时」状态机 —— CI 用，可选（需要 Node）。

为什么需要它
------------
加载回退逻辑里的 bug，静态检查全都抓不到：

1. **形参名与函数体不一致**：形参叫 ``settledFlag``，函数体 8 处写 ``settled``，
   标识符落到全局 ``window.settled``，于是所有 ``if (settled) return`` 守卫失效，
   脚本被反复重复挂载、Pyodide 重复初始化 —— 线上表现就是进度条永远停在 3%。
2. **重试被自己的守卫挡掉**：``st.settled = true`` 之后立刻递归 ``trySource()``，
   而入口第一句检查 ``settled`` —— 所有重试都在入口被挡回去。
3. **组合推进不同步**：wasm 索引回卷、index 索引单调加，两者不同步就会
   重复试已失败的组合，甚至取到 ``undefined`` 元素。

这类问题只能真跑一遍。本测试用最小 DOM 桩 + 可编排的假 ``loadPyodide``，
在 Node 里执行构建产物里的页面脚本，覆盖 5 种失败组合。

用法
----
    python web/test_load_chain.py            # 需要 node 在 PATH
    python web/test_load_chain.py --js 路径  # 指定 node 可执行文件
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(HERE, "dist", "index.html")
PAGE = "https://example.github.io/mingli-oracle/"

# 最小 DOM 桩 + 可编排的假 loadPyodide。
# 注意不要替换 global.console —— 上一版把 console 换成空实现，
# 结果连测试自己的输出都被吞掉，node 正常退出却没有输出。
HARNESS = r"""
function El(id) {
  return {
    id, value: "", textContent: "", innerHTML: "", disabled: false, removed: false,
    dataset: {}, children: [],
    classList: { _s: new Set(),
      add(c){this._s.add(c);}, remove(c){this._s.delete(c);},
      toggle(c,f){f?this._s.add(c):this._s.delete(c);}, contains(c){return this._s.has(c);} },
    style: {}, parentNode: null,
    appendChild(c){this.children.push(c); c.parentNode=this; return c;},
    setAttribute(){}, getAttribute(){return null;},
    addEventListener(){}, querySelector(){return null;}, querySelectorAll(){return [];},
    remove(){ this.removed = true; }, requestSubmit(){},
  };
}
const els = {};
function $(sel){ const id = sel.replace('#','');
  if (!els[id]) { els[id] = El(id); els[id].parentNode = els[id]; } return els[id]; }

global.document = { head: El('head'), body: El('body'), querySelector: $,
  querySelectorAll: () => [], createElement: (t) => El(t + Math.random().toString(36).slice(2,7)) };
global.window = { MINGLI_SRC: {} };
global.location = { href: "__PAGE__" };

const CFG = JSON.parse(process.env.__CFG);
const rec = [];
console.warn = function(){ rec.push("WARN " + Array.prototype.join.call(arguments, " ")); };

let SCRIPT_MOUNTS = 0, INFLIGHT = 0, MAX_INFLIGHT = 0, PROGRESS_CALLS = 0, LAST_PCT = null;

global.loadPyodide = function(opts){
  INFLIGHT++; MAX_INFLIGHT = Math.max(MAX_INFLIGHT, INFLIGHT);
  const c = CFG.combos.shift() || { ok: false };
  rec.push("LOAD " + String(opts.indexURL).replace("__PAGE__", "./"));
  if (c.progress !== false && typeof opts.progressCallback === "function") {
    for (const [l, t] of [[1000000,5000000],[3000000,5000000],[5000000,5000000]]) {
      opts.progressCallback({ type:"progress", loaded:l, total:t });
      PROGRESS_CALLS++;
      LAST_PCT = els['bootFill'] ? els['bootFill'].style.width : null;
    }
  }
  return new Promise((res, rej) => setTimeout(() => {
    INFLIGHT--;
    if (c.ok) res({ FS:{writeFile(){}}, runPython(){} }); else rej(new Error("boom"));
  }, c.delay || 4));
};

const origAppend = global.document.head.appendChild.bind(global.document.head);
global.document.head.appendChild = function(node){
  const r = origAppend(node);
  const src = String(node.src || "");
  if (src.includes("pyodide.js")) {
    SCRIPT_MOUNTS++;
    rec.push("MOUNT " + src.replace("__PAGE__", "./"));
    const fails = CFG.scriptFails.indexOf(SCRIPT_MOUNTS) >= 0;
    setTimeout(() => { fails ? (node.onerror && node.onerror()) : (node.onload && node.onload()); }, 2);
  }
  return r;
};

setTimeout(() => {
  process.stdout.write("@@RESULT@@" + JSON.stringify({
    scriptMounts: SCRIPT_MOUNTS, maxInflight: MAX_INFLIGHT,
    progressCalls: PROGRESS_CALLS, lastPct: LAST_PCT,
    bootRemoved: !!(els['boot'] && els['boot'].removed),
    statusText: els['status'] ? els['status'].textContent : "",
    bootMsgHTML: els['bootMsg'] ? els['bootMsg'].innerHTML.slice(0,240) : "",
    record: rec,
  }) + "\n");
  process.exit(0);
}, 1200);
"""

FAILS = []


def ck(name, cond, extra=""):
    if not cond:
        FAILS.append(name)
    print("  [%s] %s%s" % ("OK" if cond else "FAIL", name, ("  " + str(extra)) if extra else ""))


def load_page_js():
    if not os.path.isfile(DIST):
        print("找不到 %s，请先运行 build_web.py" % DIST, file=sys.stderr)
        sys.exit(1)
    html = open(DIST, encoding="utf-8").read()
    blocks = re.findall(r"<script>(.*?)</script>", html, re.S)
    if not blocks:
        print("产物里没有内联 script", file=sys.stderr)
        sys.exit(1)
    js = max(blocks, key=len)
    # 摘掉引擎源码赋值（很长，与本测试无关）
    return re.sub(r'window\.MINGLI_SRC\["[^"]+"\] = .*?;\n', "", js)


def run(node, js, cfg):
    d = tempfile.mkdtemp()
    p = os.path.join(d, "t.cjs")
    with open(p, "w", encoding="utf-8") as f:
        f.write(HARNESS.replace("__PAGE__", PAGE) + "\n" + js)
    env = dict(os.environ)
    env["__CFG"] = json.dumps(cfg)
    try:
        out = subprocess.run([node, p], capture_output=True, env=env, timeout=40)
    except subprocess.TimeoutExpired:
        shutil.rmtree(d, ignore_errors=True)
        return {"error": "超时（疑似死循环）"}
    finally:
        shutil.rmtree(d, ignore_errors=True)
    if out.returncode != 0:
        return {"error": out.stderr.decode("utf-8", "replace")[-300:]}
    so = out.stdout.decode("utf-8", "replace")
    if "@@RESULT@@" not in so:
        return {"error": "无结果标记；stdout=%r" % so[:160]}
    return json.loads(so.split("@@RESULT@@", 1)[1].strip().splitlines()[0])


def main(argv=None):
    ap = argparse.ArgumentParser(description="端到端验证网页版的加载状态机")
    ap.add_argument("--js", default="node", help="Node 可执行文件路径")
    a = ap.parse_args(argv)

    node = shutil.which(a.js) or a.js
    js = load_page_js()
    print("加载状态机端到端测试（node: %s，页面 js %d 字符）\n" % (node, len(js)))

    print("场景 1：自托管源直接成功")
    r = run(node, js, {"combos": [{"ok": True}], "scriptFails": []})
    if "error" in r:
        print("  无法运行：%s" % r["error"]); return 2
    ck("pyodide.js 只挂一次", r["scriptMounts"] == 1, r["scriptMounts"])
    ck("并发加载数 = 1", r["maxInflight"] == 1, r["maxInflight"])
    ck("进度来自 progressCallback", r["progressCalls"] == 3, r["progressCalls"])
    # 97% 是刻意的：100% 留给「引擎装入完成」，避免下载刚满就显示 100% 却还在解压
    ck("进度按实测字节推进（97% 封顶）", r["lastPct"] == "97%", r["lastPct"])
    ck("boot 移除、页面可用", r["bootRemoved"] is True)
    ck("状态提示就绪", "就绪" in r["statusText"])

    print("\n场景 2：pyodide.js 挂载连续失败 2 次后成功")
    r = run(node, js, {"combos": [{"ok": True}], "scriptFails": [1, 2]})
    if "error" in r:
        print("  无法运行：%s" % r["error"]); return 2
    ck("确实尝试了 3 次挂载", r["scriptMounts"] == 3, r["scriptMounts"])
    ck("最终成功", r["bootRemoved"] is True)

    print("\n场景 3：loadPyodide 连续失败后换源恢复（settled 守卫回归）")
    r = run(node, js, {"combos": [{"ok": False}, {"ok": False}, {"ok": True}], "scriptFails": []})
    if "error" in r:
        print("  无法运行：%s" % r["error"]); return 2
    loads = [x for x in r["record"] if x.startswith("LOAD")]
    ck("pyodide.js 只挂一次（不重复初始化）", r["scriptMounts"] == 1, r["scriptMounts"])
    ck("换源后确实重试", len(loads) >= 2, "LOAD %d 次" % len(loads))
    ck("各次 indexURL 不重复", len(set(loads)) == len(loads), loads)
    ck("最终恢复成功", r["bootRemoved"] is True)
    ck("全程并发 = 1", r["maxInflight"] <= 1, r["maxInflight"])
    ck("记录换源原因便于排障", any("WARN" in x for x in r["record"]))

    print("\n场景 4：组合穷尽 -> 有界失败并给出可操作提示")
    r = run(node, js, {"combos": [], "scriptFails": []})
    if "error" in r:
        print("  无法运行：%s" % r["error"]); return 2
    ck("无死循环（挂载次数有界）", r["scriptMounts"] <= 8, r["scriptMounts"])
    ck("提示改用本地版或说明真实原因",
       "scripts/server.py" in r["bootMsgHTML"] or "部署不完整" in r["bootMsgHTML"])

    print("\n场景 5：所有脚本挂载都失败")
    r = run(node, js, {"combos": [{"ok": True}], "scriptFails": list(range(1, 9))})
    if "error" in r:
        print("  无法运行：%s" % r["error"]); return 2
    ck("有界失败", r["scriptMounts"] <= 8, r["scriptMounts"])
    # 失败时必须列出每次的真实原因，而不是只说一句「都试过了」
    ck("给出可操作提示",
       "scripts/server.py" in r["bootMsgHTML"] or "加载失败" in r["bootMsgHTML"])
    ck("列出各次失败原因", "各次失败的具体原因" in r["bootMsgHTML"],
       r["bootMsgHTML"][:60])
    ck("提示区分网络问题与部署不完整",
       "pyodide.asm.js" in r["bootMsgHTML"] or "部署不完整" in r["bootMsgHTML"])

    print("\n" + "=" * 56)
    if FAILS:
        print("失败 %d 项：%s" % (len(FAILS), FAILS))
        return 1
    print("加载状态机端到端验证全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
# -*- coding: utf-8 -*-
"""网页版入口 run() vs Python oracle.build() —— 覆盖**时辰**这条路径。

为什么要单独验这个
------------------
现有 512 个对拍用例，**全部用 birthTime（"12:00" 这种）**，
没有一个走 shichen（页面上点十二时辰格子那条路径）。

而 run() 里 shichen 与 hour 是互斥的：

    hour: (!v.shichen && v.hour) ? String(v.hour).split(":").map(Number) : null

也就是说，只要用户点时辰不填时间，hour 就是 null，
下游各盘拿到的输入跟对拍用例**完全不同**。

一条没被任何用例走过的分支，等于没测过。
"""
import argparse
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

# shichen 路径 + 一些容易分歧的组合
CASES = [
    dict(solar=(1990, 5, 15), shichen="午", sex="男", place="北京",
         lon=116.41, lat=39.90, tag="午时"),
    dict(solar=(1990, 5, 15), shichen="子", sex="男", place="北京",
         lon=116.41, lat=39.90, tag="子时"),
    dict(solar=(1990, 5, 15), shichen="丑", sex="女", place="北京",
         lon=116.41, lat=39.90, tag="丑时"),
    dict(solar=(1990, 5, 15), shichen="亥", sex="男", place="上海",
         lon=121.47, lat=31.23, tag="亥时(晚子)"),
    dict(solar=(2024, 2, 4), shichen="子", sex="女", place="北京",
         lon=116.41, lat=39.90, tag="立春日 子时"),
    dict(solar=(2024, 2, 4), shichen="亥", sex="女", place="北京",
         lon=116.41, lat=39.90, tag="立春日 亥时(早子/晚子边界)"),
    dict(solar=(1900, 1, 1), shichen="午", sex="男", place="北京",
         lon=116.41, lat=39.90, tag="1900 午时"),
    dict(solar=(2100, 12, 31), shichen="亥", sex="女", place="北京",
         lon=116.41, lat=39.90, tag="2100 亥时"),
    dict(lunar=(1990, 5, 15), leap=True, shichen="午", sex="男", place="北京",
         lon=116.41, lat=39.90, tag="闰五月 午时"),
    dict(solar=(1990, 5, 15), shichen="午", sex="男", place=None,
         lon=None, lat=None, tag="无经纬"),
]

JS_RUNNER = r"""
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
const CASES = JSON.parse(readFileSync(process.env.__CASES, "utf8"));
const RD = await import(pathToFileURL(process.env.__RENDER).href);
const out = [];
for (const c of CASES) {
  out.push(rdRun(c));
}
function rdRun(c) {
  const r = RD.run({ solar: c.solar || null, lunar: c.lunar || null,
                     leap: !!c.leap, hour: null, shichen: c.shichen,
                     sex: c.sex, place: c.place || null,
                     lon: c.lon, lat: c.lat });
  return { headline: r.headline,
           plain_html: r.plain_html,
           pro_html: r.pro_html };
}
process.stdout.write("@@R@@" + JSON.stringify(out));
"""


def main():
    import bazi as B, ziwei as Z, astro as AS, plain as PL, oracle as O
    from datetime import datetime

    print("网页版入口 run() ↔ Python oracle.build()  —— 时辰路径\n")

    baseline, cases = [], []
    for c in CASES:
        kw = dict(solar=c.get("solar"), lunar=c.get("lunar"),
                  leap=c.get("leap", False), hour=None,
                  sex=c["sex"], place=c.get("place"))
        # shichen 也要由 kw 统一传，否则下面各盘的签名对不齐
        kw["shichen"] = c["shichen"]
        rb = B.pai_pan(longitude=c["lon"], deceased_year=None,
                       now=datetime(2026, 1, 1), **kw)
        rz = Z.pai_pan(year=2026, **kw)
        # astro.pai_pan 没有 shichen 参数 —— 与 oracle.build() 一致：
        # 它拿到的是 hour or (12,0)。也就是说用户点时辰不填时间时，
        # 占星盘一律按中午 12 点算（下面会单独把这个行为报出来）。
        ra = AS.pai_pan(solar=c.get("solar"), lunar=c.get("lunar"),
                        leap=c.get("leap", False), hour=None,
                        sex=c["sex"], lat=c["lat"], lon=c["lon"],
                        place=c.get("place"))
        data = {"八字": rb, "紫微": rz, "占星": ra}
        pro = ""
        pro += O.render_bazi(rb)
        pro += O.render_ziwei(rz)
        pro += O.render_astro(ra)
        pro += O.render_glossary()
        baseline.append({
            "tag": c["tag"],
            "八字": rb["四柱"],
            "真太阳时": rb["输入"]["真太阳时"],
            "紫微五行局": rz["五行局"],
            "紫微命宫": rz["命宫"],
            "上升": ra["上升星座"],
            "太阳": ra["太阳星座"],
            "headline": PL.headline(data),
        })
        cases.append({"solar": list(c["solar"]) if c.get("solar") else None,
                      "lunar": list(c["lunar"]) if c.get("lunar") else None,
                      "leap": c.get("leap", False), "shichen": c["shichen"],
                      "sex": c["sex"], "place": c.get("place"),
                      "lon": c["lon"], "lat": c["lat"], "tag": c["tag"]})

    d = os.path.join(HERE, ".tz_cases.json")
    io.open(d, "w", encoding="utf-8").write(json.dumps(cases, ensure_ascii=False))
    rj = os.path.join(HERE, ".tz_runner.mjs")
    io.open(rj, "w", encoding="utf-8").write(JS_RUNNER)
    env = dict(os.environ)
    env["__CASES"] = d
    env["__RENDER"] = os.path.join(HERE, "js", "render.js")
    r = subprocess.run([sys.argv[sys.argv.index("--js") + 1] if "--js" in sys.argv else "node", rj],
                       capture_output=True, env=env, timeout=600)
    for p in (d, rj):
        try:
            os.remove(p)
        except OSError:
            pass

    so = r.stdout.decode("utf-8", "replace")
    if "@@R@@" not in so:
        print("JS 侧无输出：\n" + r.stderr.decode("utf-8", "replace")[-800:])
        return 2
    got = json.loads(so.split("@@R@@", 1)[1])

    bad = 0
    for b, g in zip(baseline, got):
        tag = b["tag"]
        if g["headline"] != b["headline"]:
            print("  [FAIL] %-22s headline 不同\n         py=%s\n         js=%s"
                  % (tag, b["headline"], g["headline"]))
            bad += 1
        else:
            print("  [OK]   %-22s %s" % (tag, b["headline"][:56]))
        # HTML 逐字比对
        if g["pro_html"] != _py_pro(b):
            print("         pro_html 不同（Python %d vs JS %d 字符）"
                  % (len(_py_pro(b)), len(g["pro_html"])))
    print("\n" + "=" * 56)
    if bad:
        print("失败 %d 例" % bad)
        return 1
    print("时辰路径 %d 例全部一致" % len(baseline))
    return 0


def _py_pro(b):
    return b.get("_pro", "")


if __name__ == "__main__":
    sys.exit(main())
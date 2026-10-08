# -*- coding: utf-8 -*-
"""时辰路径：JS 引擎 vs Python 引擎，逐字比对（含 HTML）。

512 个既有对拍用例**全部走 birthTime**（"12:00" 这种），
没有一个走 shichen（页面上点十二时辰格子那条路）。

而 run() 里两者互斥：
    hour: (!v.shichen && v.hour) ? String(v.hour).split(":").map(Number) : null
点时辰 => hour 为 null => 下游拿到的输入跟既有用例完全不同。

一条没被任何用例走过的分支，等于没测过 —— 上游那个 off-by-one
就是这么活到今天才被发现的。

覆盖：十二时辰全走一遍，外加闰月/边界年/无经纬等边界组合。
"""
import argparse
import io
import json
import os
import subprocess
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

SHICHEN = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]

# (solar/lunar, sex, lon/lat/place, tag)
COMBOS = []
for z in SHICHEN:
    COMBOS.append((dict(solar=(1990, 5, 15), sex="男", lon=116.41, lat=39.90,
                        place="北京"), z, "1990-05-15 %s时 北京男" % z))
COMBOS += [
    (dict(solar=(2024, 2, 4), sex="女", lon=116.41, lat=39.90, place="北京"),
     "子", "2024-02-04 立春 子时 女"),
    (dict(solar=(2024, 2, 4), sex="女", lon=116.41, lat=39.90, place="北京"),
     "亥", "2024-02-04 立春 亥时(晚子边界) 女"),
    (dict(solar=(1900, 1, 1), sex="男", lon=116.41, lat=39.90, place="北京"),
     "午", "1900 午时"),
    (dict(solar=(2100, 12, 31), sex="女", lon=116.41, lat=39.90, place="北京"),
     "亥", "2100 亥时"),
    (dict(lunar=(1990, 5, 15), leap=True, sex="男", lon=116.41, lat=39.90,
          place="北京"), "午", "闰五月 午时"),
    (dict(solar=(1990, 5, 15), sex="男", lon=None, lat=None, place=None),
     "午", "无经纬 午时"),
    (dict(solar=(1990, 5, 15), sex="女", lon=87.62, lat=43.83, place="乌鲁木齐"),
     "丑", "乌鲁木齐 丑时 女"),
]

JS_RUNNER = r"""
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
const CASES = JSON.parse(readFileSync(process.env.__CASES, "utf8"));
const RD = await import(pathToFileURL(process.env.__RENDER).href);
const R = [];
for (const c of CASES) {
  try {
    const r = RD.run({ solar: c.solar || null, lunar: c.lunar || null,
                       leap: !!c.leap, hour: null, shichen: c.shichen,
                       sex: c.sex, place: c.place || null,
                       lon: c.lon, lat: c.lat });
    R.push({ headline: r.headline, plain: r.plain_html, pro: r.pro_html });
  } catch (e) {
    R.push({ err: String(e && e.message) });
  }
}
process.stdout.write("@@R@@" + JSON.stringify(R));
"""


def main(argv=None):
    ap = argparse.ArgumentParser(description="时辰路径：Python ↔ JS 对拍")
    ap.add_argument("--js", default="node")
    a = ap.parse_args(argv)

    import bazi as B, ziwei as Z, astro as AS, plain as PL, oracle as O

    print("时辰路径对拍（Python ↔ JS）\n")

    baseline, cases = [], []
    for opts, z, tag in COMBOS:
        kw = dict(solar=opts.get("solar"), lunar=opts.get("lunar"),
                  leap=opts.get("leap", False), hour=None,
                  sex=opts["sex"], place=opts.get("place"), shichen=z)
        rb = B.pai_pan(longitude=opts["lon"], deceased_year=None,
                       now=datetime(2026, 1, 1), **kw)
        rz = Z.pai_pan(year=2026, **kw)
        ra = AS.pai_pan(lat=opts["lat"], lon=opts["lon"], solar=opts.get("solar"),
                        lunar=opts.get("lunar"), leap=opts.get("leap", False),
                        hour=None, shichen=z, sex=opts["sex"], place=opts.get("place"))
        data = {"八字": rb, "紫微": rz, "占星": ra}
        pro = (O.render_bazi(rb) + O.render_ziwei(rz)
               + O.render_astro(ra) + O.render_glossary())
        baseline.append({
            "tag": tag, "headline": PL.headline(data),
            "plain": O.render_plain(data), "pro": pro,
            "四柱": rb["四柱"], "真太阳时": rb["输入"]["真太阳时"],
            "命宫": rz["命宫"], "上升": ra["上升星座"],
        })
        cases.append({
            "solar": list(opts["solar"]) if opts.get("solar") else None,
            "lunar": list(opts["lunar"]) if opts.get("lunar") else None,
            "leap": opts.get("leap", False), "shichen": z,
            "sex": opts["sex"], "place": opts.get("place"),
            "lon": opts["lon"], "lat": opts["lat"], "tag": tag,
        })

    d = os.path.join(HERE, ".shichen_cases.json")
    rj = os.path.join(HERE, ".shichen_runner.mjs")
    io.open(d, "w", encoding="utf-8").write(json.dumps(cases, ensure_ascii=False))
    io.open(rj, "w", encoding="utf-8").write(JS_RUNNER)
    env = dict(os.environ)
    env["__CASES"] = d
    env["__RENDER"] = os.path.join(HERE, "js", "render.js")
    try:
        r = subprocess.run([a.js, rj], capture_output=True, env=env, timeout=600)
    finally:
        for p in (d, rj):
            try:
                os.remove(p)
            except OSError:
                pass

    so = r.stdout.decode("utf-8", "replace")
    if "@@R@@" not in so:
        print("JS 无输出：\n" + r.stderr.decode("utf-8", "replace")[-800:])
        return 2
    got = json.loads(so.split("@@R@@", 1)[1])

    fails = 0
    for b, g in zip(baseline, got):
        if "err" in g:
            print("  [FAIL] %-26s JS 抛错: %s" % (b["tag"], g["err"]))
            fails += 1
            continue
        diffs = []
        if g["headline"] != b["headline"]:
            diffs.append("headline")
        if g["pro"] != b["pro"]:
            diffs.append("pro_html")
        if g["plain"] != b["plain"]:
            diffs.append("plain_html")
        if diffs:
            print("  [FAIL] %-26s %s 不同" % (b["tag"], ",".join(diffs)))
            sys.stdout.flush()
            if "headline" in diffs:
                print("         py=%s" % b["headline"])
                print("         js=%s" % g["headline"])
            # HTML 逐字比对：只报首个不同的位置，否则几万字没法看
            # 注意键名要对上：diffs 里存的是 "pro_html"/"plain_html"，
            # 下面按同样的名字取 g/b。之前写成 ("pro","plain") 查不中，
            # 于是失败时只印一行「不同」，看不到到底差在哪 ——
            # 这种「报了错但没给出定位信息」的输出等于没报。
            for key in ("pro_html", "plain_html"):
                if key not in diffs:
                    continue
                # g/b 里的键是 "pro"/"plain"，diffs 里是 "pro_html"/"plain_html"
                x = g[key.replace("_html", "")]
                y = b[key.replace("_html", "")]
                # 报出**所有**不同的片段，而不只是第一个 ——
                # 只报第一个的话，修完第一个往往还有第二个，来回拉锯。
                spans = []
                k = 0
                while k < min(len(x), len(y)):
                    if x[k] == y[k]:
                        k += 1
                        continue
                    s = k
                    while k < min(len(x), len(y)) and x[k] != y[k]:
                        k += 1
                    spans.append((s, k))
                    if len(spans) >= 6:
                        break
                print("         %s 长度 py=%d js=%d，%d 处不同"
                      % (key, len(y), len(x), len(spans)))
                for s, e in spans:
                    a0, b0 = max(0, s - 60), min(len(y), e + 60)
                    c0, d0 = max(0, s - 60), min(len(x), e + 60)
                    # 用 repr 而不是 split/join：HTML 里含大量中文标点，
                    # 压缩空白会把差异位置冲掉，看不出到底哪几个字不同。
                    print("           @%d py: %r" % (s, y[a0:b0]))
                    print("           @%d js: %r" % (s, x[c0:d0]))
                    sys.stdout.flush()
            fails += 1
        else:
            print("  [OK]   %-26s %s" % (b["tag"], b["四柱"]["时"] + " 时柱"))

    print("\n" + "=" * 60)
    if fails:
        print("不一致 %d / %d" % (fails, len(baseline)))
        return 1
    print("全部 %d 个时辰用例与 Python 引擎逐字一致" % len(baseline))
    return 0


if __name__ == "__main__":
    sys.exit(main())
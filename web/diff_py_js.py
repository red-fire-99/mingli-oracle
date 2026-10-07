#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Python 引擎 ↔ JS 移植的逐案对拍。

为什么必须有这个
--------------
引入 JS 移植后，仓库里就有**两份实现**（Python 与 JS）。两份必然漂移，
光靠「各跑各的自测」只能保证各自自洽，保证不了**一致**。

本工具的做法：用 Python 引擎（唯一事实来源）跑一批用例生成基准，
再让 JS 版跑同一批用例，逐项比对。任何不一致都算 bug 并让 CI 失败。

覆盖面刻意挑在「容易因语言语义差异而出错」的地方：
  - Python 的 % / // / round() 与 JS 语义不同（子丑宫、朔序号都会用到）
  - 定朔 / 置闰（.date() 判定而非时刻判定）
  - 节气时刻（牛顿迭代 + ΔT）
  - 行星黄经（开普勒方程 + 光行时 + 岁差）
  - 时辰与真太阳时

用法
----
    python web/diff_py_js.py --layer almanac
    python web/diff_py_js.py --layer all --node <node 路径>
"""
import argparse
import io
import json
import os
import subprocess
import sys
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import almanac as A  # noqa: E402

# 浮点比较容差：两个实现都是 IEEE754 双精度，但运算次序可能不同
TOL = 1e-9


# ---------------------------------------------------------------------------
# 基准生成
# ---------------------------------------------------------------------------

def cases_almanac():
    """产出 (op, 标签, 输入描述, Python 基准) 四元组。

    op 显式给出，不从标签里切 —— 切出来的名字容易和 JS 分支对不上。
    """
    out = []
    add = lambda op, label, inp, want: out.append((op, label, inp, want))

    # 取模 / 整除 / round 的语义陷阱：子丑宫 (zhi_i-2) 为负
    for (y, mo, d, H) in [(1990, 5, 15, 12), (1984, 2, 4, 23), (2000, 1, 1, 0),
                          (1991, 8, 15, 1), (2020, 6, 21, 23), (2014, 12, 22, 12),
                          (1900, 1, 1, 12), (2100, 12, 31, 23), (1999, 2, 28, 23),
                          (2004, 5, 1, 0)]:
        dt = A.beijing(y, mo, d, H)
        mg = A.month_gz(dt)
        add("month_gz", "month_gz(%d-%02d-%02d %02d)" % (y, mo, d, H),
            {"y": y, "m": mo, "d": d, "H": H}, {"gz": mg[0], "zhi": mg[1], "jie": mg[2]})
        yg = A.year_gz(dt)
        add("year_gz", "year_gz(%d-%02d-%02d)" % (y, mo, d),
            {"y": y, "m": mo, "d": d, "H": H}, {"gz": yg[0], "year": yg[1]})
        add("day_gz", "day_gz(%d-%02d-%02d)" % (y, mo, d),
            {"y": y, "m": mo, "d": d}, {"gz": A.day_gz(y, mo, d)})

    # 时辰跨日：23:00 起为早子时
    for (h, mi) in [(23, 30), (0, 30), (1, 0), (11, 59), (12, 0), (13, 0), (22, 59), (23, 0)]:
        s = A.shichen_of(h, mi)
        add("shichen_of", "shichen_of(%d:%02d)" % (h, mi),
            {"hour": h, "minute": mi}, {"zhi": s[0], "idx": s[1]})

    # 节气时刻
    for y in (1900, 1949, 1984, 1990, 2000, 2020, 2024, 2100):
        for lon in (315, 270, 90):
            dt = A.solar_term_beijing(y, lon)
            add("solar_term", "solar_term(%d,%d)" % (y, lon), {"year": y, "lon": lon},
                {"y": dt.year, "m": dt.month, "d": dt.day,
                 "H": dt.hour, "Mi": dt.minute, "S": dt.second})

    # 定气定朔与农历（含闰月年、朔与中气同日年）
    for (y, mo, d) in [(1990, 5, 15), (1990, 8, 15), (2020, 6, 21), (2014, 12, 22),
                       (1984, 2, 4), (2000, 1, 1), (2024, 2, 10), (1900, 1, 1),
                       (2100, 12, 31), (2017, 6, 24), (2014, 9, 24), (2009, 6, 23),
                       (2012, 5, 21), (2025, 7, 25)]:
        sl = A.solar_to_lunar(y, mo, d)
        add("solar_to_lunar", "solar_to_lunar(%d-%02d-%02d)" % (y, mo, d),
            {"y": y, "m": mo, "d": d},
            {"ly": sl[0], "lm": sl[1], "ld": sl[2], "leap": sl[3]})

    # 农历月序列（闰月位置最容易错）
    for y in (1989, 1990, 2014, 2017, 2020, 2023, 2025, 2001, 2012, 2004, 2009):
        seg = A.lunar_months_between_dongzhi(y)
        add("lunar_months", "lunar_months_between_dongzhi(%d)" % y, {"year": y},
            {"months": [[m["year"], m["month"], m["leap"],
                         m["start"].toordinal(), m["days"]] for m in seg]})

    # 朔序号（round() 银行家舍入）
    for y in (1900, 1984, 1990, 2000, 2020, 2024, 2100, 2017, 2014):
        for lon in (270, 315):
            jd = A.solar_term_jd(y, lon)
            add("last_new_moon_k", "last_new_moon_k(%d,%d)" % (y, lon),
                {"year": y, "lon": lon},
                {"k": A.last_new_moon_k_on_or_before(jd), "jd": jd})

    # 行星黄经
    for (y, mo, d, H) in [(1990, 5, 15, 12), (2000, 1, 1, 0), (2024, 6, 1, 6),
                          (1900, 3, 1, 0), (2100, 9, 9, 18), (2026, 10, 7, 22)]:
        jd = A.jd_from_datetime(A.beijing(y, mo, d, H))
        for name in A.PLANETS:
            add("planet_lon", "planet_lon(%s,%d-%02d-%02d)" % (name, y, mo, d),
                {"name": name, "jd": jd},
                {"lon": A.planet_geocentric_longitude(name, jd)})
        add("sun_lon", "sun_lon(%d-%02d-%02d)" % (y, mo, d), {"jd": jd},
            {"lon": A.sun_apparent_longitude(jd)})
        add("moon_lon", "moon_lon(%d-%02d-%02d)" % (y, mo, d), {"jd": jd},
            {"lon": A.planet_geocentric_longitude("月亮", jd)})

    # 均时差与真太阳时
    for (y, mo, d, H, lon) in [(1990, 5, 15, 12, 116.4), (2000, 1, 1, 0, 121.5),
                               (2024, 7, 4, 18, 87.6), (1900, 6, 15, 6, 113.3),
                               (1991, 8, 15, 1, 121.5), (2020, 12, 21, 23, 91.1)]:
        dt = A.beijing(y, mo, d, H)
        jd = A.jd_from_datetime(dt)
        add("eot", "eot(%d-%02d-%02d)" % (y, mo, d), {"jd": jd},
            {"eot": A.equation_of_time_minutes(jd)})
        tst, off, eot = A.true_solar_time(dt, lon)
        add("true_solar", "true_solar(%d-%02d-%02d,%.1f)" % (y, mo, d, lon),
            {"y": y, "m": mo, "d": d, "H": H, "lon": lon},
            {"offset_min": off, "eot": eot, "y2": tst.year, "m2": tst.month,
             "d2": tst.day, "H2": tst.hour, "Mi2": tst.minute})

    # 干支基础
    for idx in (0, 1, 59, 60, 61, 1990, -1, 120):
        add("gz_from_index", "gz_from_index(%d)" % idx, {"idx": idx},
            {"gz": A.gz_from_index(idx)})
    for y in (1984, 2000, 1900, 2100, 2026):
        add("year_gz_index", "year_gz_index(%d)" % y, {"year": y}, {"idx": A.year_gz_index(y)})
        add("day_gz", "day_gz(%d-01-01)" % y, {"y": y, "m": 1, "d": 1},
            {"gz": A.day_gz(y, 1, 1)})
    for g in A.GAN:
        for i in range(12):
            if (i % 2) == (A.GAN.index(g) % 2):     # 只取阴阳相配的合法时柱
                add("hour_gz", "hour_gz(%s,%d)" % (g, i), {"gan": g, "zhi_i": i},
                    {"gz": A.hour_gz(g, i)})
    for i in range(60):
        gz = A.gz_from_index(i)
        add("nayin", "nayin(%s)" % gz, {"gan": gz[0], "zhi": gz[1]},
            {"nayin": A.nayin_of(gz[0], gz[1]), "wx": A.nayin_wuxing(gz[0], gz[1])})
    return out


LAYERS = {"almanac": cases_almanac}


def gen_baseline(layer):
    return LAYERS[layer]()


# ---------------------------------------------------------------------------
# JS 侧比对
# ---------------------------------------------------------------------------

JS_RUNNER = r"""
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const CASES = JSON.parse(readFileSync(process.env.__CASES, 'utf8'));
const mod  = await import(pathToFileURL(process.env.__ALMANAC).href);
const K    = await import(pathToFileURL(process.env.__KERNEL).href);

const R = [];
for (const c of CASES) {
  const i = c.in;
  let got = null;
  try {
    switch (c.op) {
      case "month_gz": {
        const r = mod.monthGz(K.bjUnix(i.y,i.m,i.d,i.H,0,0), i.y);
        got = { gz: r.gz, zhi: r.zhi, jie: r.name };   // JS 的 name -> Python 的 jie
        break;
      }
      case "year_gz": {
        const r = mod.yearGz(K.bjUnix(i.y,i.m,i.d,i.H,0,0), i.y);
        got = { gz: r.gz, year: r.year }; break;
      }
      case "day_gz":   got = { gz: mod.dayGz(i.y, i.m, i.d) }; break;
      case "shichen_of": got = mod.shichenOf(i.hour, i.minute); break;
      case "solar_term": { const d = mod.solarTermBeijing(i.year, i.lon);
                           got = { y:d.y, m:d.m, d:d.d, H:d.H, Mi:d.Mi, S:d.S }; break; }
      case "solar_to_lunar": { const r = mod.solarToLunarTuple(i.y,i.m,i.d);
                               got = { ly:r[0], lm:r[1], ld:r[2], leap:r[3] }; break; }
      case "lunar_months": { const s = mod.lunarMonthsBetweenDongzhi(i.year);
                             got = { months: s.map(m => [m.year, m.month, m.leap,
                                     // JS 内部用 JDN，Python 侧用 date.toordinal()，
                                     // 两者零点不同，必须换算到同一纪日再比。
                                     K.jdnToOrdinal(m.startJdn), m.days]) }; break; }
      case "last_new_moon_k": { const jd = mod.solarTermJd(i.year, i.lon);
                               got = { k: mod.lastNewMoonKOnOrBefore(jd), jd }; break; }
      case "planet_lon": got = { lon: mod.planetGeocentricLongitude(i.name, i.jd) }; break;
      case "sun_lon":    got = { lon: mod.sunApparentLongitude(i.jd) }; break;
      case "moon_lon":   got = { lon: mod.planetGeocentricLongitude("月亮", i.jd) }; break;
      case "eot":        got = { eot: mod.equationOfTimeMinutes(i.jd) }; break;
      case "true_solar": {
        const t0 = K.bjUnix(i.y, i.m, i.d, i.H, 0, 0);
        const r  = mod.trueSolarTime(t0, i.lon);
        const c  = K.bjCivilFromUnix(r.t);
        got = { offset_min: r.offsetMin, eot: r.eot,
                y2: c.y, m2: c.m, d2: c.d, H2: c.H, Mi2: c.Mi };
        break;
      }
      case "gz_from_index": got = { gz: mod.gzFromIndex(i.idx) }; break;
      case "year_gz_index": got = { idx: mod.yearGzIndex(i.year) }; break;
      case "hour_gz":       got = { gz: mod.hourGz(i.gan, i.zhi_i) }; break;
      case "nayin":         got = { nayin: mod.nayinOf(i.gan, i.zhi),
                                    wx: mod.nayinWuxing(i.gan, i.zhi) }; break;
      default: got = { __unknown_op: c.op };
    }
  } catch (e) {
    got = { __error: String(e && e.message) };
  }
  R.push({ label: c.label, got });
}
process.stdout.write("@@R@@" + JSON.stringify(R));
"""


def main(argv=None):
    ap = argparse.ArgumentParser(description="Python 引擎与 JS 移植逐案对拍")
    ap.add_argument("--layer", default="almanac", choices=sorted(LAYERS))
    ap.add_argument("--js", default="node", help="Node 可执行文件")
    ap.add_argument("--tol", type=float, default=TOL)
    a = ap.parse_args(argv)

    cases = []
    for op, label, inp, want in gen_baseline(a.layer):
        cases.append({"op": op, "label": label, "in": inp, "want": want})

    # JSON 往返会把整数变成浮点，先把该当整数的字段钉回去，
    # 避免「类型不同」被误判成数值不一致。
    def pin_ints(o):
        if isinstance(o, dict):
            return {k: (int(v) if isinstance(v, float) and v.is_integer()
                        and k not in ("jd", "lon", "eot", "offset_min", "offsetMin")
                        else pin_ints(v)) for k, v in o.items()}
        if isinstance(o, list):
            return [pin_ints(v) for v in o]
        if isinstance(o, float) and o.is_integer() and abs(o) < 1e15:
            return o
        return o

    for c in cases:
        c["want"] = pin_ints(c["want"])

    d = os.path.join(HERE, ".diff_cases.json")
    with io.open(d, "w", encoding="utf-8") as f:
        json.dump(cases, f, ensure_ascii=False)
    print("生成 %d 个基准用例 -> %s\n" % (len(cases), d))

    runner = os.path.join(HERE, ".diff_runner.mjs")
    with io.open(runner, "w", encoding="utf-8") as f:
        f.write(JS_RUNNER)

    env = dict(os.environ)
    env["__CASES"] = d
    env["__ALMANAC"] = os.path.join(HERE, "js", "almanac.js")
    env["__KERNEL"] = os.path.join(HERE, "js", "kernel.js")
    try:
        r = subprocess.run([a.js, runner], capture_output=True, env=env, timeout=600)
    finally:
        for p in (d, runner):
            try:
                os.remove(p)
            except OSError:
                pass

    so = r.stdout.decode("utf-8", "replace")
    if "@@R@@" not in so:
        print("JS 侧没有输出结果；stderr:\n%s" % r.stderr.decode("utf-8", "replace")[-1500:])
        return 2
    results = json.loads(so.split("@@R@@", 1)[1])

    def cmp(got, want, path=""):
        """递归比对（got=JS 结果，want=Python 基准），返回首个不一致描述。"""
        if isinstance(got, dict) and isinstance(want, dict):
            for k in sorted(set(got) | set(want)):
                if k not in got:
                    return "JS 缺少字段 %s%s" % (path, k)
                if k not in want:
                    return "Python 缺少字段 %s%s" % (path, k)
                m = cmp(got[k], want[k], path + k + ".")
                if m:
                    return m
            return None
        if isinstance(got, list) and isinstance(want, list):
            if len(got) != len(want):
                return "长度不同 %s: py=%d js=%d" % (path, len(want), len(got))
            for i, (g, w) in enumerate(zip(got, want)):
                m = cmp(g, w, "%s[%d]." % (path, i))
                if m:
                    return m
            return None
        if isinstance(got, bool) or isinstance(want, bool):
            return None if got == want else "%spy=%r js=%r" % (path, want, got)
        if isinstance(got, (int, float)) and isinstance(want, (int, float)):
            if abs(got - want) <= a.tol + max(abs(got), abs(want)) * 1e-15:
                return None
            return "%spy=%r js=%r (差 %.3g)" % (path, want, got, abs(got - want))
        return None if got == want else "%spy=%r js=%r" % (path, want, got)

    fails = []
    for c, res in zip(cases, results):
        err = cmp(res["got"], c["want"])
        if err:
            fails.append("%s\n     %s" % (c["label"], err))

    print("=" * 60)
    if fails:
        print("不一致 %d / %d：" % (len(fails), len(cases)))
        for f in fails[:25]:
            print("  ! " + f)
        if len(fails) > 25:
            print("  ... 其余 %d 条省略" % (len(fails) - 25))
        return 1
    print("全部 %d 个用例与 Python 引擎一致" % len(cases))
    return 0


if __name__ == "__main__":
    sys.exit(main())
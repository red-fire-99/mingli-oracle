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

# 钉死的「当前年」：Python 与 JS 必须用同一年，否则流年必然对不上。
PINNED_YEAR = 2026


def cases_bazi():
    """产出 (op, 标签, 输入, Python 基准)。"""
    import bazi as B
    from datetime import datetime
    out = []
    add = lambda op, label, inp, want: out.append((op, label, inp, want))

    # 覆盖面：平胎 / 早子 / 晚子(23点) / 跨时辰 / 边界年 / 闰月 / 无时刻
    combos = [
        dict(solar=(1990, 5, 15), hour=(12, 0), sex="男", place="北京",
             longitude=116.4, label="1990-05-15 午 北京 男"),
        dict(solar=(1990, 5, 15), hour=(12, 0), sex="女", place="北京",
             longitude=116.4, label="1990-05-15 午 北京 女"),
        dict(solar=(1991, 8, 15), hour=(1, 0), sex="男", place="上海",
             longitude=121.5, label="1991-08-15 丑 上海 男"),
        dict(solar=(1991, 8, 15), hour=(23, 30), sex="男", place="上海",
             longitude=121.5, label="1991-08-15 晚子 上海"),
        dict(solar=(2000, 1, 1), hour=(0, 30), sex="女", label="2000-01-01 子 女"),
        dict(solar=(1984, 2, 4), hour=(23, 0), sex="男", label="1984-02-04 晚子"),
        dict(solar=(2020, 6, 21), hour=(12, 0), sex="男", place="乌鲁木齐",
             longitude=87.62, label="2020-06-21 夏至日 乌鲁木齐"),
        dict(solar=(2014, 12, 22), hour=(12, 0), sex="男", label="2014-12-22 冬至日"),
        dict(solar=(2024, 2, 4), hour=(12, 0), sex="女", label="2024-02-04 立春"),
        dict(solar=(1900, 1, 1), hour=(12, 0), sex="男", label="1900 边界"),
        dict(solar=(2100, 12, 31), hour=(23, 59), sex="女", label="2100 边界"),
        dict(solar=(1990, 5, 15), hour=None, sex="男", label="无时刻"),
        dict(lunar=(1990, 5, 15), leap=True, hour=(12, 0), sex="男", label="闰五月"),
        dict(lunar=(2020, 4, 1), leap=True, hour=(12, 0), sex="女", label="闰四月"),
        dict(solar=(2026, 10, 7), hour=(22, 0), sex="男", place="北京",
             longitude=116.4, label="今天附近"),
    ]

    for c in combos:
        label = c["label"]
        kw = dict(solar=c.get("solar"), lunar=c.get("lunar"), leap=c.get("leap", False),
                  hour=c.get("hour"), shichen=None, sex=c.get("sex", "男"),
                  place=c.get("place"), longitude=c.get("longitude"),
                  deceased_year=None,
                  now=datetime(PINNED_YEAR, 1, 1))
        r = B.pai_pan(**kw)
        want = {
            "四柱": r["四柱"],
            "输入": {k: v for k, v in r["输入"].items() if k != "真太阳时"},
            "真太阳时": r["输入"]["真太阳时"],
            "日主": r["日主"],
            "柱详解": r["柱详解"],
            "五行统计": r["五行统计"],
            "日主强弱": r["日主强弱"],
            "格局": r["格局"],
            "旬空": r["旬空"],
            "神煞": [[s["神煞"], s["落支"], s["位置"]] for s in r["神煞"]],
            "大运": {"顺逆": r["大运"]["顺逆"], "起运": r["大运"]["起运"],
                     "起运虚岁": r["大运"]["起运虚岁"],
                     "列表": [[d["序"], d["干支"], d["十神"], d["起始虚岁"],
                                d["结束虚岁"], d["起始公历"]] for d in r["大运"]["列表"]]},
            "流年": [[x["年"], x["干支"], x["十神"], x["虚岁"], x["大运"]]
                     for x in r["流年"]],
            "警告": r["警告"],
            "当前时间": r["当前时间"],
        }
        inp = {"solar": c.get("solar"), "lunar": c.get("lunar"),
               "leap": c.get("leap", False), "hour": c.get("hour"),
               "sex": c.get("sex", "男"), "place": c.get("place"),
               "longitude": c.get("longitude"), "nowYear": PINNED_YEAR}
        add("pai_pan", "pai_pan(%s)" % label, inp, want)

    # 十神：日干 × 其他天干全覆盖
    for dg in "甲乙丙丁戊己庚辛壬癸":
        row = [B.shishen(dg, og) for og in "甲乙丙丁戊己庚辛壬癸"]
        add("shishen_row", "shishen_row(%s)" % dg, {"dayGan": dg}, {"row": row})

    # 旬空：六十甲子全覆盖
    for i in range(60):
        gz = __import__("almanac").gz_from_index(i)
        add("kongwang", "kongwang(%s)" % gz,
            {"idx": __import__("almanac").day_gz_index(1984, 1, 1) + i},
            {"kw": B.kongwang(__import__("almanac").day_gz_index(1984, 1, 1) + i)})
    return out


LAYERS["bazi"] = cases_bazi

def cases_astro():
    """占星层对拍：十天体黄经、星座度数、上升天顶、相位、元素分布、整宫制。"""
    import astro as AS
    out = []
    add = lambda op, label, inp, want: out.append((op, label, inp, want))

    combos = [
        dict(solar=(1990, 5, 15), hour=(12, 0), lat=39.9, lon=116.4, sex="男", place="北京"),
        dict(solar=(1990, 5, 15), hour=(12, 0), lat=39.9, lon=116.4, sex="女", place="北京"),
        dict(solar=(2000, 1, 1), hour=(0, 0), lat=31.2, lon=121.5, sex="男", place="上海"),
        dict(solar=(2024, 6, 1), hour=(6, 0), lat=87.6, lon=113.3, sex="女", place="拉萨"),
        dict(solar=(1900, 3, 1), hour=(18, 0), lat=40.0, lon=-74.0, sex="男", place="纽约"),
        dict(solar=(2100, 9, 9), hour=(18, 0), lat=-33.9, lon=151.2, sex="女", place="悉尼"),
        dict(solar=(2020, 6, 21), hour=(12, 0), lat=None, lon=None, sex="男"),
        dict(lunar=(1990, 5, 15), leap=True, hour=(12, 0), lat=39.9, lon=116.4, sex="男"),
    ]
    for c in combos:
        r = AS.pai_pan(solar=c.get("solar"), lunar=c.get("lunar"), leap=c.get("leap", False),
                        hour=c.get("hour"), sex=c.get("sex", "男"),
                        lat=c.get("lat"), lon=c.get("lon"), place=c.get("place"))
        want = {
            "输入": r["输入"],
            "天体": [[p["天体"], p["黄经"], p["星座"], p["度数"], p["星座内度"],
                       p["元素"], p["性质"]] for p in r["天体"]],
            "轴点": {k: [v["黄经"], v["星座"], v["度数"], v["星座内度"]]
                     for k, v in r["轴点"].items()},
            "相位": [[a["天体1"], a["天体2"], a["相位"], a["标准角"], a["偏差"], a["强度"]]
                     for a in sorted(r["相位"], key=lambda x: -x["强度"])[:14]],
            "元素分布": r["元素分布"],
            "性质分布": r["性质分布"],
            "宫位": [[h["宫"], h["星座"], h["内行星"]] for h in r["宫位"]],
            "太阳星座": r["太阳星座"], "月亮星座": r["月亮星座"],
            "上升星座": r["上升星座"],
        }
        add("astro_pai_pan", "astro_pai_pan(%s)" % str(c.get("solar") or c.get("lunar")),
            {"solar": c.get("solar"), "lunar": c.get("lunar"),
             "leap": c.get("leap", False), "hour": c.get("hour"),
             "lat": c.get("lat"), "lon": c.get("lon"),
             "sex": c.get("sex", "男"), "place": c.get("place")}, want)
    return out


LAYERS["astro"] = cases_astro


def cases_ziwei():
    """紫微层对拍：命身宫、五行局、安星、十二宫、大限、流年。

    ziwei.py 的「流年」默认取 datetime.now().year，必须用 year= 钉死，
    否则 Python 与 JS 跑在跨年边界时会得出不同结果。
    """
    import ziwei as Z
    out = []
    add = lambda op, label, inp, want: out.append((op, label, inp, want))

    combos = [
        dict(solar=(1990, 5, 15), hour=(12, 0), sex="男", place="北京"),
        dict(solar=(1990, 5, 15), hour=(12, 0), sex="女", place="北京"),
        dict(solar=(2000, 1, 1), hour=(0, 0), sex="男", place="上海"),
        dict(solar=(2024, 2, 4), hour=(23, 0), sex="女"),
        dict(solar=(1984, 2, 4), hour=(1, 0), sex="男"),
        dict(solar=(1900, 1, 1), hour=(12, 0), sex="女"),
        dict(solar=(2100, 12, 31), hour=(12, 0), sex="男"),
        dict(solar=(1990, 5, 15), hour=None, sex="男"),
        dict(solar=(2020, 6, 21), hour=(13, 0), sex="女"),
        dict(lunar=(1990, 5, 15), leap=True, hour=(12, 0), sex="男"),
    ]
    for c in combos:
        kw = dict(solar=c.get("solar"), lunar=c.get("lunar"),
                  leap=c.get("leap", False), hour=c.get("hour"), shichen=None,
                  sex=c["sex"], place=c.get("place"), year=PINNED_YEAR)
        r = Z.pai_pan(**kw)
        want = {
            "输入": r["输入"], "命宫": r["命宫"], "身宫": r["身宫"],
            "五行局": r["五行局"], "紫微星": r["紫微星"], "天府星": r["天府星"],
            "十二宫": [[p["宫名"], p["地支"], p["天干"], p["星曜"], p["主星"],
                        p["是否命宫"], p["是否身宫"]] for p in r["十二宫"]],
            "四化": r["四化"],
            "大限": {"顺逆": r["大限"]["顺逆"], "起运虚岁": r["大限"]["起运虚岁"],
                     "列表": [[d["宫位"], d["地支"], d["天干"], d["虚岁起"],
                                d["虚岁止"], d["星曜"]] for d in r["大限"]["列表"]]},
            "流年": r["流年"],
            "警告": r["警告"],
        }
        add("ziwei_pai_pan", "ziwei(%s %s %s)"
            % (c.get("solar") or c.get("lunar"), c["sex"], c.get("hour")),
            {"solar": c.get("solar"), "lunar": c.get("lunar"),
             "leap": c.get("leap", False), "hour": c.get("hour"),
             "sex": c["sex"], "place": c.get("place"), "year": PINNED_YEAR}, want)

    # 安紫微：五行局 × 农历日 全覆盖（1..30），这是紫微最核心的查表
    for ju in (2, 3, 4, 5, 6):
        row = [Z.an_ziwei(ju, d) for d in range(1, 31)]
        add("an_ziwei", "an_ziwei(ju=%d, 1..30)" % ju, {"ju": ju}, {"row": row})
    return out


LAYERS["ziwei"] = cases_ziwei


def cases_plain():
    """白话解读层对拍：6 个函数在真实排盘结果上的输出。

    plain.py 的输入是 bazi/ziwei/astro 的**完整排盘结果**，所以这一层
    同时验证「移植后的 plain.js 能吃 JS 引擎自己产出的结构」——
    这是纯 JS 站点能否独立跑通的关键一环。
    """
    import bazi as B, ziwei as Z, astro as AS, plain as PL
    from datetime import datetime
    out = []
    add = lambda op, label, inp, want: out.append((op, label, inp, want))

    combos = [
        dict(solar=(1990, 5, 15), hour=(12, 0), sex="男", place="北京",
             lon=116.4, lat=39.9),
        dict(solar=(1990, 5, 15), hour=(12, 0), sex="女", place="北京",
             lon=116.4, lat=39.9),
        dict(solar=(2000, 1, 1), hour=(0, 0), sex="男", place="上海",
             lon=121.5, lat=31.2),
        dict(solar=(2024, 2, 4), hour=(23, 0), sex="女", place="拉萨",
             lon=91.1, lat=29.7),
        dict(solar=(1984, 2, 4), hour=(1, 0), sex="男", place="广州",
             lon=113.3, lat=23.1),
        dict(solar=(2020, 6, 21), hour=(12, 0), sex="女", place="乌鲁木齐",
             lon=87.6, lat=43.8),
        dict(solar=(1990, 5, 15), hour=None, sex="男", place="北京",
             lon=116.4, lat=39.9),
    ]
    for c in combos:
        common = dict(solar=c["solar"], hour=c["hour"], sex=c["sex"],
                      place=c["place"])
        rb = B.pai_pan(longitude=c["lon"], shichen=None, lunar=None, leap=False,
                       deceased_year=None, now=datetime(PINNED_YEAR, 1, 1), **common)
        rz = Z.pai_pan(lunar=None, leap=False, shichen=None, year=PINNED_YEAR, **common)
        ra = AS.pai_pan(lunar=None, leap=False, lat=c["lat"], lon=c["lon"], **common)

        tag = "%s %s %s" % (c["solar"], c["sex"], c["hour"])
        add("plain_bazi", "bazi_plain(%s)" % tag, dict(common, lon=c["lon"]),
            PL.bazi_plain(rb))
        add("plain_ziwei", "ziwei_plain(%s)" % tag, dict(common),
            PL.ziwei_plain(rz))
        add("plain_astro", "astro_plain(%s)" % tag,
            dict(common, lat=c["lat"], lon=c["lon"]),
            PL.astro_plain(ra))
        add("plain_headline", "headline(%s)" % tag,
            dict(common, lat=c["lat"], lon=c["lon"]),
            PL.headline({"八字": rb, "紫微": rz, "占星": ra}))

    # 词汇表
    add("glossary", "glossary_html()", {}, {"g": PL.glossary_html()})
    return out


LAYERS["plain"] = cases_plain


def cases_render():
    """渲染层端到端对拍：同一生辰，Python 与 JS 必须输出逐字相同的 HTML。"""
    import bazi as B, ziwei as Z, astro as AS, plain as PL, oracle as O
    from datetime import datetime
    out = []
    add = lambda op, label, inp, want: out.append((op, label, inp, want))

    combos = [
        dict(solar=(1990, 5, 15), hour="12:00", sex="男", place="北京",
             lon=116.4, lat=39.9),
        dict(solar=(1990, 5, 15), hour="12:00", sex="女", place="北京",
             lon=116.4, lat=39.9),
        dict(solar=(2000, 1, 1), hour="00:00", sex="男", place="上海",
             lon=121.5, lat=31.2),
        dict(solar=(2024, 2, 4), hour="23:00", sex="女", place="拉萨",
             lon=91.1, lat=29.7),
        dict(solar=(1984, 2, 4), hour="01:00", sex="男", place="广州",
             lon=113.3, lat=23.1),
        dict(solar=(2020, 6, 21), hour="12:00", sex="女", place="乌鲁木齐",
             lon=87.6, lat=43.8),
        dict(solar=(1990, 5, 15), hour=None, sex="男", place=None,
             lon=None, lat=None),
        dict(lunar=(1990, 5, 15), leap=True, hour="12:00", sex="男",
             place="北京", lon=116.4, lat=39.9),
    ]
    for c in combos:
        # hour 统一用 "H:MM" 字符串跨语言传递（网页表单就是这个格式），
        # 两侧各自解析成本地表示 —— 与 render.js 的 run() 保持同一约定。
        hh = (tuple(int(x) for x in c["hour"].split(":")) if c.get("hour") else None)
        kw = dict(solar=c.get("solar"), lunar=c.get("lunar"),
                  leap=c.get("leap", False), hour=hh,
                  sex=c["sex"], place=c.get("place"))
        rb = B.pai_pan(longitude=c["lon"], shichen=None,
                       deceased_year=None,
                       now=datetime(PINNED_YEAR, 1, 1), **kw)
        rz = Z.pai_pan(shichen=None, year=PINNED_YEAR, **kw)
        ra = AS.pai_pan(lat=c["lat"], lon=c["lon"], **kw)
        data = {"八字": rb, "紫微": rz, "占星": ra}

        tag = "%s %s %s" % (c.get("solar") or c.get("lunar"), c["sex"], c.get("hour"))
        # 逐字比对 HTML：HTML 里含有大量中文与标点，只报首个不同的字符位置
        add("render_bazi", "render_bazi(%s)" % tag, dict(c),
            {"html": O.render_bazi(rb)})
        add("render_ziwei", "render_ziwei(%s)" % tag, dict(c),
            {"html": O.render_ziwei(rz)})
        add("render_astro", "render_astro(%s)" % tag, dict(c),
            {"html": O.render_astro(ra)})
        add("render_plain", "render_plain(%s)" % tag, dict(c),
            {"html": O.render_plain(data)})
        add("render_glossary", "render_glossary()", {}, {"html": O.render_glossary()})
        add("run", "run(%s)" % tag, dict(c), O_run_js_equiv(c, O, PL, data))
    return out


def O_run_js_equiv(c, O, PL, data):
    """Python 侧模拟 render.js 的 run()：拼出网页版真正消费的三个字段。"""
    pro = ""
    if "八字" in data: pro += O.render_bazi(data["八字"])
    if "紫微" in data: pro += O.render_ziwei(data["紫微"])
    if "占星" in data: pro += O.render_astro(data["占星"])
    pro += O.render_glossary()
    return {"headline": PL.headline(data),
            "plain_html": O.render_plain(data),
            "pro_html": pro}


LAYERS["render"] = cases_render




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
const B    = await import(pathToFileURL(process.env.__BAZI).href);
const A    = await import(pathToFileURL(process.env.__ASTRO).href);
const ZW   = await import(pathToFileURL(process.env.__ZIWEI).href);
const P    = await import(pathToFileURL(process.env.__PLAIN).href);
const RD   = await import(pathToFileURL(process.env.__RENDER).href);

// 渲染层辅助：按 Python 侧同样的参数造盘。year 钉死，流年才可比。
function mk(i, which) {
  const common = { solar: i.solar || null, lunar: i.lunar || null,
                   leap: !!i.leap,
                   hour: i.hour ? String(i.hour).split(":").map(Number) : null,
                   shichen: null, sex: i.sex, place: i.place || null };
  if (which === "bazi") return B.paiPan({ ...common, longitude: i.lon,
                                          nowYear: 2026 });
  if (which === "ziwei") return ZW.paiPan({ ...common, year: 2026 });
  return A.paiPan({ ...common, lat: i.lat, lon: i.lon });
}


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
      case "pai_pan": {
        const r = B.paiPan({ solar: i.solar || null, lunar: i.lunar || null,
                             leap: !!i.leap, hour: i.hour || null, shichen: null,
                             sex: i.sex, place: i.place || null,
                             longitude: (i.longitude === null || i.longitude === undefined)
                                        ? null : i.longitude,
                             nowYear: i.nowYear });
        got = {
          四柱: r.四柱,
          输入: (({ 真太阳时, ...rest }) => rest)(r.输入),
          真太阳时: r.输入.真太阳时,
          日主: r.日主, 柱详解: r.柱详解, 五行统计: r.五行统计,
          日主强弱: r.日主强弱, 格局: r.格局, 旬空: r.旬空,
          神煞: r.神煞.map(s => [s.神煞, s.落支, s.位置]),
          大运: { 顺逆: r.大运.顺逆, 起运: r.大运.起运,
                  起运虚岁: r.大运.起运虚岁,
                  列表: r.大运.列表.map(d => [d.序, d.干支, d.十神,
                                            d.起始虚岁, d.结束虚岁, d.起始公历]) },
          流年: r.流年.map(x => [x.年, x.干支, x.十神, x.虚岁, x.大运]),
          警告: r.警告, 当前时间: r.当前时间,
        };
        break;
      }
      case "shishen_row": {
        got = { row: "甲乙丙丁戊己庚辛壬癸".split("").map(g => B.shishen(i.dayGan, g)) };
        break;
      }
      case "kongwang": got = { kw: B.kongwang(i.idx) }; break;
      case "astro_pai_pan": {
        const r = A.paiPan({ solar: i.solar || null, lunar: i.lunar || null,
                             leap: !!i.leap, hour: i.hour || null, sex: i.sex,
                             lat: i.lat, lon: i.lon, place: i.place || null });
        got = {
          输入: r.输入,
          天体: r.天体.map(p => [p.天体, p.黄经, p.星座, p.度数, p.星座内度,
                                  p.元素, p.性质]),
          轴点: Object.fromEntries(Object.entries(r.轴点).map(
                    ([k, v]) => [k, [v.黄经, v.星座, v.度数, v.星座内度]])),
          相位: r.相位.slice().sort((a, b) => b.强度 - a.强度).slice(0, 14)
                  .map(a => [a.天体1, a.天体2, a.相位, a.标准角, a.偏差, a.强度]),
          元素分布: r.元素分布, 性质分布: r.性质分布,
          宫位: r.宫位.map(h => [h.宫, h.星座, h.内行星]),
          太阳星座: r.太阳星座, 月亮星座: r.月亮星座, 上升星座: r.上升星座,
        };
        break;
      }
      case "ziwei_pai_pan": {
        const r = ZW.paiPan({ solar: i.solar || null, lunar: i.lunar || null,
                              leap: !!i.leap, hour: i.hour || null, shichen: null,
                              sex: i.sex, place: i.place || null, year: i.year });
        got = {
          输入: r.输入, 命宫: r.命宫, 身宫: r.身宫, 五行局: r.五行局,
          紫微星: r.紫微星, 天府星: r.天府星,
          十二宫: r.十二宫.map(p => [p.宫名, p.地支, p.天干, p.星曜, p.主星,
                                     p.是否命宫, p.是否身宫]),
          四化: r.四化,
          大限: { 顺逆: r.大限.顺逆, 起运虚岁: r.大限.起运虚岁,
                  列表: r.大限.列表.map(d => [d.宫位, d.地支, d.天干,
                                              d.虚岁起, d.虚岁止, d.星曜]) },
          流年: r.流年, 警告: r.警告,
        };
        break;
      }
      case "an_ziwei": {
        got = { row: Array.from({length: 30}, (_, k) => ZW.anZiwei(i.ju, k + 1)) };
        break;
      }
      case "plain_bazi": {
        const r = B.paiPan({ solar: i.solar || null, hour: i.hour || null,
                             shichen: null, sex: i.sex, place: i.place || null,
                             longitude: i.lon, leap: false, nowYear: 2026 });
        got = P.baziPlain(r);
        break;
      }
      case "plain_ziwei": {
        const r = ZW.paiPan({ solar: i.solar || null, hour: i.hour || null,
                              shichen: null, sex: i.sex, place: i.place || null,
                              leap: false, year: 2026 });
        got = P.ziweiPlain(r);
        break;
      }
      case "plain_astro": {
        const r = A.paiPan({ solar: i.solar || null, hour: i.hour || null,
                             shichen: null, sex: i.sex, place: i.place || null,
                             lat: i.lat, lon: i.lon, leap: false });
        got = P.astroPlain(r);
        break;
      }
      case "plain_headline": {
        const c = i;
        const rb = B.paiPan({ solar: c.solar || null, hour: c.hour || null,
                              shichen: null, sex: c.sex, place: c.place || null,
                              longitude: c.lon, leap: false, nowYear: 2026 });
        const rz = ZW.paiPan({ solar: c.solar || null, hour: c.hour || null,
                               shichen: null, sex: c.sex, place: c.place || null,
                               leap: false, year: 2026 });
        const ra = A.paiPan({ solar: c.solar || null, hour: c.hour || null,
                              shichen: null, sex: c.sex, place: c.place || null,
                              lat: c.lat, lon: c.lon, leap: false });
        got = P.headline({ 八字: rb, 紫微: rz, 占星: ra });
        break;
      }
      case "glossary": got = { g: P.glossaryHtml() }; break;
      case "render_bazi": {
        const rb = mk(i, "bazi");
        got = { html: RD.renderBazi(rb) };
        break;
      }
      case "render_ziwei": {
        got = { html: RD.renderZiwei(mk(i, "ziwei")) };
        break;
      }
      case "render_astro": {
        got = { html: RD.renderAstro(mk(i, "astro")) };
        break;
      }
      case "render_plain": {
        got = { html: RD.renderPlain({ 八字: mk(i, "bazi"), 紫微: mk(i, "ziwei"),
                                       占星: mk(i, "astro") }) };
        break;
      }
      case "render_glossary": got = { html: RD.renderGlossary() }; break;
      case "run": {
        got = RD.run({ solar: i.solar || null, lunar: i.lunar || null,
                       leap: !!i.leap, hour: i.hour || null,
                       sex: i.sex, place: i.place || null,
                       lon: i.lon, lat: i.lat });
        break;
      }
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
    ap.add_argument("--layer", default="all", choices=sorted(LAYERS) + ["all"])
    ap.add_argument("--js", default="node", help="Node 可执行文件")
    ap.add_argument("--tol", type=float, default=TOL)
    a = ap.parse_args(argv)

    layers = sorted(LAYERS) if a.layer == "all" else [a.layer]
    cases = []
    for _layer in layers:
      for op, label, inp, want in gen_baseline(_layer):
        cases.append({"op": op, "label": label, "in": inp, "want": want})

    # JSON 往返会把整数变成浮点，先把该当整数的字段钉回去，
    # 避免「类型不同」被误判成数值不一致。
    def pin_ints(o):
        # Python 的 tuple 经 JSON 往返会变成 JS 侧的 array，比对前统一成 list，
        # 否则「术语」这类 [(k, v), ...] 会永远报不一致。
        if isinstance(o, tuple):
            return [pin_ints(v) for v in o]
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
    env["__BAZI"] = os.path.join(HERE, "js", "bazi.js")
    env["__ASTRO"] = os.path.join(HERE, "js", "astro.js")
    env["__ZIWEI"] = os.path.join(HERE, "js", "ziwei.js")
    env["__PLAIN"] = os.path.join(HERE, "js", "plain.js")
    env["__RENDER"] = os.path.join(HERE, "js", "render.js")
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
        if isinstance(got, str) and isinstance(want, str):
            if got == want:
                return None
            # HTML 逐字比对：只报首个不同的位置，否则几万字的差异没法看
            k = 0
            lim = min(len(got), len(want))
            while k < lim and got[k] == want[k]:
                k += 1
            ctx = lambda s: repr(s[max(0, k - 40):k + 40])
            return ("HTML 在第 %d 字符不同\n       py: %s\n       js: %s"
                    "（长度 py=%d js=%d）" % (k, ctx(want), ctx(got), len(want), len(got)))
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
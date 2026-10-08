# -*- coding: utf-8 -*-
"""验证：时辰 → 钟点的映射必须与「直接给该时辰内的真实钟点」等价。

这是刚修的 off-by-one 的回归锁。原代码

    hh = 2 * (ZHI.index(shichen) - 1) % 24     # 子 -> 22
    if shichen == "子": hh = 0                 # 只把子时兜回来

导致除子时外**每个时辰都偏前一格**：丑时报成子时、午时报成巳时。
「知道大概时辰、不确定几点」是最常见的用法，所以影响面很大。

修法是 hh = 2 * ZHI.index(shichen) % 24（子=0、丑=2、寅=4……），
这样交给统一的 hour_idx 公式后自然落进正确的区间。

本检查同时验证八字/紫微/占星三盘拿到的出生时刻是同一个。
"""
import io
import os
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import almanac as A
import bazi as B
import ziwei as Z
import astro as AS

ZHI = A.ZHI
# 每个时辰覆盖的钟点区间（取区间内的代表点做对照）
REPRESENTATIVE = {}
for i, z in enumerate(ZHI):
    lo = (i * 2 - 1) % 24          # 23:00-01:00 -> lo=23
    REPRESENTATIVE[z] = (lo + 1) % 24   # 取区间起点+1，避开跨日边界

fails = []
print("时辰映射回归检查\n")
print("  时辰  代表钟点   经时辰推算      经真实钟点     时柱      紫微命宫   占星太阳")
print("  " + "-" * 82)

SOLAR = (1990, 5, 15)
LON, LAT = 116.41, 39.90

for z in ZHI:
    hh_rep = REPRESENTATIVE[z]

    # 路径 A：只给 shichen
    rb_a = B.pai_pan(solar=SOLAR, lunar=None, leap=False, hour=None, shichen=z,
                     sex="男", place="北京", longitude=LON, deceased_year=None,
                     now=datetime(2026, 1, 1))
    rz_a = Z.pai_pan(solar=SOLAR, lunar=None, leap=False, hour=None, shichen=z,
                     sex="男", place="北京", year=2026)
    ra_a = AS.pai_pan(solar=SOLAR, lunar=None, leap=False, hour=None, shichen=z,
                      sex="男", lat=LAT, lon=LON, place="北京")

    # 路径 B：给该时辰内的真实钟点
    rb_b = B.pai_pan(solar=SOLAR, lunar=None, leap=False, hour=(hh_rep, 0),
                     shichen=None, sex="男", place="北京", longitude=LON,
                     deceased_year=None, now=datetime(2026, 1, 1))
    rz_b = Z.pai_pan(solar=SOLAR, lunar=None, leap=False, hour=(hh_rep, 0),
                     shichen=None, sex="男", place="北京", year=2026)
    ra_b = AS.pai_pan(solar=SOLAR, lunar=None, leap=False, hour=(hh_rep, 0),
                      shichen=None, sex="男", lat=LAT, lon=LON, place="北京")

    ok = (rb_a["四柱"] == rb_b["四柱"]
          and rz_a["命宫"] == rz_b["命宫"]
          and ra_a["太阳星座"] == ra_b["太阳星座"]
          and ra_a["天体"][0]["黄经"] == ra_b["天体"][0]["黄经"])

    ok_bz = rb_a["四柱"] == rb_b["四柱"]
    ok_zw = rz_a["命宫"] == rz_b["命宫"]
    ok_as = (ra_a["太阳星座"] == ra_b["太阳星座"]
             and ra_a["天体"][0]["黄经"] == ra_b["天体"][0]["黄经"])
    got_z = A.shichen_of(hh_rep, 0)[0]
    print("  %-4s  %02d:00   时柱 %s/%s %s  命宫 %s/%s %s  太阳 %s %s"
          % (z, hh_rep,
             rb_a["四柱"]["时"], rb_b["四柱"]["时"], "OK" if ok_bz else "!!",
             rz_a["命宫"]["天干"] + rz_a["命宫"]["地支"],
             rz_b["命宫"]["天干"] + rz_b["命宫"]["地支"], "OK" if ok_zw else "!!",
             ra_a["太阳星座"], "OK" if ok_as else "!!"))
    print("       实际落在 %s 时" % got_z)
    if got_z != z:
        fails.append("%s 时辰的代表钟点 %02d:00 实际落在 %s 时" % (z, hh_rep, got_z))
    if not ok:
        fails.append("%s 时辰：时辰路径与真实钟点路径结果不一致" % z)

print()
if fails:
    print("失败 %d 项：" % len(fails))
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("全部 12 个时辰：时辰路径 == 该时辰内真实钟点路径")
print("（即「只知道大概时辰」与「知道准确钟点」得到同一张盘）")
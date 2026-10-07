#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""临时脚本：农历 / 闰月 / 朔望 / 干支连续性 综合复盘。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import almanac as A

PASS = FAIL = 0


def ck(label, got, want):
    global PASS, FAIL
    if got == want:
        PASS += 1
    else:
        FAIL += 1
        print("  [FAIL] %s => %s (期望 %s)" % (label, got, want))


print("== 1. 历年春节（正月初一）对照 ==")
SPRING = [(2025, 1, 29), (2024, 2, 10), (2023, 1, 22), (2022, 2, 1), (2021, 2, 12),
          (2020, 1, 25), (2019, 2, 5), (2018, 2, 16), (2015, 2, 19), (2010, 2, 14),
          (2000, 2, 5), (1990, 1, 27), (1980, 2, 16), (1970, 2, 6), (1960, 1, 28)]
bad = 0
for (y, m, d) in SPRING:
    ly, lm, ld, leap = A.solar_to_lunar(y, m, d)
    if not (ly == y and lm == 1 and ld == 1 and not leap):
        bad += 1
        print("  [FAIL] %04d-%02d-%02d => 农历%d年%s月%s" % (y, m, d, ly, lm, ld))
ck("15 个春节全部命中", bad, 0)

print("== 2. 闰月对照 ==")
LEAP = {2023: 2, 2020: 4, 2017: 6, 2014: 9, 2012: 4, 2009: 5, 2006: 7, 2004: 2, 1990: 5}
bad = 0
for y, lm in sorted(LEAP.items()):
    seg = list(A.lunar_months_between_dongzhi(y - 1)) + list(A.lunar_months_between_dongzhi(y))
    if not any(x["leap"] and x["year"] == y and x["month"] == lm for x in seg):
        bad += 1
        print("  [FAIL] %d 年应有闰 %d 月" % (y, lm))
ck("9 个闰月全部命中", bad, 0)

print("== 3. 朔望自洽（新月时月亮黄经应≈太阳黄经）==")
worst = 0.0
for k in range(-60, 61):
    jde = A.new_moon_jde(k)
    diff = abs((A._moon_position(jde) - A.sun_apparent_longitude(jde) + 180) % 360 - 180)
    worst = max(worst, diff)
print("    新月时刻日月黄经最大偏差：%.3f°" % worst)
ck("朔望自洽 < 1°", worst < 1.0, True)

print("== 4. 日柱干支连续性（连续 400 天必须逐日 +1）==")
from datetime import date, timedelta
start = date(1990, 1, 1)
bad = 0
for i in range(400):
    d1 = start + timedelta(days=i)
    d2 = start + timedelta(days=i + 1)
    i1 = A.day_gz_index(d1.year, d1.month, d1.day)
    i2 = A.day_gz_index(d2.year, d2.month, d2.day)
    if (i1 + 1) % 60 != i2:
        bad += 1
ck("400 天日柱连续", bad, 0)

print("== 5. 年柱以立春为界（抽查 20 年）==")
bad = 0
for y in range(1985, 2005):
    lc = A.solar_term_beijing(y, 315)
    before = A.year_gz(A.beijing(y, 1, 15, 12))[0]
    after = A.year_gz(A.beijing(y, 6, 15, 12))[0]
    if before == after:
        bad += 1
        print("  [FAIL] %d 年立春前后年柱相同" % y)
    if A.year_gz(A.beijing(y, 12, 31, 12))[0] != after:
        bad += 1
ck("20 年立春分界正确", bad, 0)

print("== 6. 节气间隔合理性（相邻中气间隔 29-32 天）==")
bad = 0
for y in (1950, 2000, 2050):
    terms = [A.solar_term_beijing(y, lon) for lon in sorted(A.ZHONGQI_LONGS)]
    terms.sort()
    for i in range(len(terms) - 1):
        gap = (terms[i + 1] - terms[i]).days
        if not (29 <= gap <= 32):
            bad += 1
ck("中气间隔正常", bad, 0)

print("== 7. 农历反算往返一致（抽查 300 天）==")
bad = 0
for i in range(0, 300, 7):
    d = date(1995, 1, 1) + timedelta(days=i)
    ly, lm, ld, leap = A.solar_to_lunar(d.year, d.month, d.day)
    back = A.lunar_to_solar(ly, lm, ld, leap)
    if back != d:
        bad += 1
        print("  [FAIL] %s → 农历 → %s" % (d, back))
ck("往返一致", bad, 0)

print("=" * 52)
print("  复盘通过 %d 项，失败 %d 项" % (PASS, FAIL))
print("=" * 52)
sys.exit(0 if FAIL == 0 else 1)

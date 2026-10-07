#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""临时脚本：用 ephem（VSOP87/ELP2000）交叉验证占星引擎的行星黄经精度。"""
import math
import os
import sys
from datetime import datetime, timezone

import ephem

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import almanac as A

BODIES = [("太阳", "Sun"), ("月亮", "Moon"), ("水星", "Mercury"), ("金星", "Venus"),
          ("火星", "Mars"), ("木星", "Jupiter"), ("土星", "Saturn"),
          ("天王星", "Uranus"), ("海王星", "Neptune"), ("冥王星", "Pluto")]

CASES = [(1900, 1, 1, 0), (1930, 6, 15, 12), (1950, 3, 20, 6), (1970, 11, 8, 18),
         (1990, 5, 15, 4), (2000, 1, 1, 12), (2010, 8, 1, 0), (2020, 6, 21, 12),
         (2035, 9, 9, 3), (2060, 2, 29, 9), (2099, 12, 31, 18)]


def ephem_lon(ename, dt_utc):
    d = ephem.Date(dt_utc)
    body = getattr(ephem, ename)(d)
    ecl = ephem.Ecliptic(body, epoch=d)
    return math.degrees(float(ecl.lon)) % 360.0


def main():
    print("=" * 78)
    print("  占星引擎 vs ephem(VSOP87/ELP2000)  黄经误差对照（单位：度）")
    print("=" * 78)
    header = "  日期(UTC)      " + "".join("%8s" % n for n, _ in BODIES)
    print(header)
    print("  " + "-" * 74)
    worst = {}
    for (y, m, d, h) in CASES:
        dt = datetime(y, m, d, h, 0, tzinfo=timezone.utc)
        jd = A.jd_from_datetime(dt)
        row = "  %04d-%02d-%02d %02d:00 " % (y, m, d, h)
        for cn, en in BODIES:
            mine = A.planet_geocentric_longitude(cn, jd)
            ref = ephem_lon(en, dt)
            diff = (mine - ref + 180) % 360 - 180
            row += "%8.2f" % diff
            worst[cn] = max(worst.get(cn, 0), abs(diff))
        print(row)
    print("  " + "-" * 74)
    print("  最大误差：")
    for cn, _ in BODIES:
        w = worst[cn]
        flag = "OK " if w < 1.0 else ("注意" if w < 3.0 else "偏大")
        print("    %-4s %6.2f°  %s" % (cn, w, flag))
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())

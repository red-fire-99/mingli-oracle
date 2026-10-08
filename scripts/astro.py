#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""西洋占星本命盘引擎（零第三方依赖，仅标准库）。

能力：日月与八大行星地心黄经、星座、上升（ASC）、天顶（MC）、整宫制十二宫、
主要相位（合/六分/刑/三分/对分）、元素与性质分布、月亮相位。

星历由 almanac 提供（低精度解析式，占星用途足够，1900–2100）。

用法
----
python astro.py --solar 1990-05-15 --hour 12:00 --lat 39.9 --lon 116.4 --sex 男
"""

import argparse
import json
import math
import sys

from almanac import (PLANETS, planet_geocentric_longitude, jd_from_datetime, J2000,
                     beijing, solar_to_lunar, format_lunar, setup_console, ZHI)

SIGNS = ("白羊", "金牛", "双子", "巨蟹", "狮子", "处女",
         "天秤", "天蝎", "射手", "摩羯", "水瓶", "双鱼")
SIGN_EN = ("Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
           "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces")
ELEMENT = ("火", "土", "风", "水") * 3
MODALITY = ("基本", "固定", "变动") * 4
# 星座序号 0-11 → 元素/性质
SIGN_ELEMENT = ("火", "土", "风", "水", "火", "土", "风", "水", "火", "土", "风", "水")
SIGN_MODALITY = ("基本", "固定", "变动", "基本", "固定", "变动",
                 "基本", "固定", "变动", "基本", "固定", "变动")

GLYPH = {"太阳": "☉", "月亮": "☽", "水星": "☿", "金星": "♀", "火星": "♂",
         "木星": "♃", "土星": "♄", "天王星": "♅", "海王星": "♆", "冥王星": "♇",
         "上升": "ASC", "天顶": "MC"}

ASPECTS = (("合相", 0, 8), ("六分相", 60, 5), ("刑相", 90, 6),
           ("三分相", 120, 6), ("对分相", 180, 8))


def norm360(x):
    return x % 360.0


def sign_of(lon):
    """黄经 → (星座名, 星座内度数)。"""
    i = int(lon // 30) % 12
    return SIGNS[i], round(lon - i * 30, 2), i


def gmst_deg(jd_ut):
    """格林尼治平恒星时（度）。"""
    T = (jd_ut - J2000) / 36525.0
    return norm360(280.46061837 + 360.98564736629 * (jd_ut - J2000)
                   + 0.000387933 * T * T - T * T * T / 38710000.0)


def asc_mc(jd_ut, lat, lon):
    """上升点与天顶的黄经（度）。"""
    eps = math.radians(23.439291 - 0.0130042 * (jd_ut - J2000) / 36525.0)
    ramc = math.radians(norm360(gmst_deg(jd_ut) + lon))
    lat_r = math.radians(lat)
    # 天顶 MC
    mc = math.atan2(math.sin(ramc), math.cos(ramc) * math.cos(eps))
    mc = math.degrees(mc) % 360.0
    # 上升 ASC
    asc = math.atan2(-math.cos(ramc),
                     math.sin(ramc) * math.cos(eps) + math.tan(lat_r) * math.sin(eps))
    asc = math.degrees(asc) % 360.0
    return asc, mc


def aspects_between(lon1, lon2):
    """两黄经的相位（若有）。返回 (名称, 精确角度, 容许偏差) 或 None。"""
    diff = abs((lon1 - lon2 + 180) % 360 - 180)
    for name, ang, orb in ASPECTS:
        if abs(diff - ang) <= orb:
            return name, ang, round(diff - ang, 2)
    return None


def pai_pan(solar=None, lunar=None, leap=False, hour=None, shichen=None, sex="男",
            lat=None, lon=None, place=None):
    if solar:
        y, m, d = solar
        lunar_info = solar_to_lunar(y, m, d)
    elif lunar:
        ly, lm, ld = lunar
        from almanac import lunar_to_solar
        dt = lunar_to_solar(ly, lm, ld, leap)
        y, m, d = dt.year, dt.month, dt.day
        lunar_info = (ly, lm, ld, leap)
    else:
        raise ValueError("必须提供 --solar 或 --lunar")

    # 出生时刻：hour 优先；只给 shichen 时按时辰的起始钟点（子=0、丑=2……）。
    # 原先这里没有 shichen 参数，oracle.build() 传的是 hour or (12, 0) ——
    # 于是「只点时辰、不填时间」的用户，占星盘一律按中午 12 点算，
    # 与八字/紫微拿到的出生时刻对不上。同一个盘里三套时间，结论自然矛盾。
    hh = 12
    mm = 0
    if hour is not None:
        hh, mm = (hour, 0) if isinstance(hour, int) else hour
    elif shichen is not None:
        hh, mm = 2 * ZHI.index(shichen) % 24, 0
    dt = beijing(y, m, d, hh, mm)
    jd_ut = jd_from_datetime(dt)

    planets = []
    for name in PLANETS:
        lo = planet_geocentric_longitude(name, jd_ut)
        sign, deg, si = sign_of(lo)
        planets.append({
            "天体": name, "符号": GLYPH[name], "黄经": round(lo, 3),
            "星座": sign, "度数": deg, "星座内度": "%d°%02d'" % (int(deg), int(deg % 1 * 60)),
            "元素": SIGN_ELEMENT[si], "性质": SIGN_MODALITY[si],
        })

    angles = {}
    if lat is not None and lon is not None:
        asc, mc = asc_mc(jd_ut, float(lat), float(lon))
        for nm, val in (("上升", asc), ("天顶", mc)):
            sign, deg, si = sign_of(val)
            angles[nm] = {"黄经": round(val, 3), "星座": sign, "度数": deg,
                          "星座内度": "%d°%02d'" % (int(deg), int(deg % 1 * 60)),
                          "符号": GLYPH[nm]}

    # 相位
    bodies = [(p["天体"], p["黄经"]) for p in planets]
    if "上升" in angles:
        bodies.append(("上升", angles["上升"]["黄经"]))
        bodies.append(("天顶", angles["天顶"]["黄经"]))
    asp = []
    for i in range(len(bodies)):
        for j in range(i + 1, len(bodies)):
            r = aspects_between(bodies[i][1], bodies[j][1])
            if r:
                asp.append({"天体1": bodies[i][0], "天体2": bodies[j][0],
                            "相位": r[0], "标准角": r[1], "偏差": r[2],
                            "强度": round(1 - abs(r[2]) / 8, 2)})

    # 元素 / 性质分布（十大天体）
    elem_cnt = {e: 0 for e in ("火", "土", "风", "水")}
    mod_cnt = {k: 0 for k in ("基本", "固定", "变动")}
    for p in planets:
        elem_cnt[p["元素"]] += 1
        mod_cnt[p["性质"]] += 1

    # 整宫制宫位（以 ASC 所在星座为第一宫）
    houses = []
    if "上升" in angles:
        asc_si = int(angles["上升"]["黄经"] // 30)
        for k in range(12):
            si = (asc_si + k) % 12
            members = [p["天体"] for p in planets if int(p["黄经"] // 30) == si]
            houses.append({"宫": k + 1, "星座": SIGNS[si], "内行星": members})

    return {
        "输入": {"公历": "%04d-%02d-%02d" % (y, m, d), "农历": format_lunar(*lunar_info),
                 "时刻": "%02d:%02d" % (hh, mm), "性别": sex,
                 "出生地": place or "未提供",
                 "经纬度": ("%s, %s" % (lat, lon)) if lat is not None else "未提供（无法定上升/宫位）"},
        "天体": planets,
        "轴点": angles,
        "相位": asp,
        "元素分布": elem_cnt,
        "性质分布": mod_cnt,
        "宫位": houses,
        "太阳星座": next(p["星座"] for p in planets if p["天体"] == "太阳"),
        "月亮星座": next(p["星座"] for p in planets if p["天体"] == "月亮"),
        "上升星座": angles.get("上升", {}).get("星座", "未知"),
    }


def format_report(r):
    L = []
    L.append("=" * 52)
    L.append("  西洋占星本命盘")
    L.append("=" * 52)
    i = r["输入"]
    L.append("公历：%s  农历：%s  时刻：%s" % (i["公历"], i["农历"], i["时刻"]))
    L.append("出生地：%s  经纬度：%s" % (i["出生地"], i["经纬度"]))
    L.append("太阳星座：%s   月亮星座：%s   上升星座：%s" % (r["太阳星座"], r["月亮星座"], r["上升星座"]))
    L.append("")
    L.append("【天体位置】")
    for p in r["天体"]:
        L.append("  %s %-4s %-3s %-6s %s" % (p["符号"], p["天体"], p["星座"], p["星座内度"], p["元素"] + "·" + p["性质"]))
    if r["轴点"]:
        L.append("")
        L.append("【轴点】")
        for nm, v in r["轴点"].items():
            L.append("  %-4s %-3s %s" % (nm, v["星座"], v["星座内度"]))
    L.append("")
    L.append("【主要相位】")
    for a in sorted(r["相位"], key=lambda x: -x["强度"]):
        L.append("  %s — %s  %s（偏差 %.2f°，强度 %.2f）" % (a["天体1"], a["天体2"], a["相位"], a["偏差"], a["强度"]))
    L.append("")
    L.append("【元素分布】" + "  ".join("%s%d" % (k, v) for k, v in r["元素分布"].items()))
    L.append("【性质分布】" + "  ".join("%s%d" % (k, v) for k, v in r["性质分布"].items()))
    if r["宫位"]:
        L.append("")
        L.append("【宫位（整宫制）】")
        for h in r["宫位"]:
            L.append("  第%2d宫 %-3s  %s" % (h["宫"], h["星座"], " ".join(h["内行星"]) if h["内行星"] else ""))
    L.append("")
    L.append("提示：占星分析仅供文化研究与娱乐参考，人生在于自身的努力和选择。")
    return "\n".join(L)


def parse_date(text):
    parts = text.strip().replace("/", "-").replace(".", "-").split("-")
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("日期请按 1990-05-15 这样的格式填写（年-月-日）")
    return tuple(int(x) for x in parts)


def parse_hour(text):
    text = text.strip().replace("：", ":")
    if ":" in text:
        h, m = text.split(":")
        return int(h), int(m)
    return int(text), 0


def main(argv=None):
    setup_console()
    p = argparse.ArgumentParser(description="西洋占星本命盘 —— 输入生日，排出星盘")
    p.add_argument("--solar", type=parse_date)
    p.add_argument("--lunar", type=parse_date)
    p.add_argument("--leap", action="store_true")
    p.add_argument("--hour", type=parse_hour, default=(12, 0))
    p.add_argument("--sex", default="男")
    p.add_argument("--lat", type=float, default=None, help="出生地纬度")
    p.add_argument("--lon", type=float, default=None, help="出生地经度")
    p.add_argument("--place", default=None)
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    if not a.solar and not a.lunar:
        p.error("请至少填一个生日：阳历用 --solar，农历用 --lunar")
    r = pai_pan(solar=a.solar, lunar=a.lunar, leap=a.leap, hour=a.hour, sex=a.sex,
                lat=a.lat, lon=a.lon, place=a.place)
    print(json.dumps(r, ensure_ascii=False, indent=2) if a.json else format_report(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())

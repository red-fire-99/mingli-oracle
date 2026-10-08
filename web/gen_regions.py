#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抓取全国行政区划经纬度，生成 web/js/regions.json。

为什么必须要外部数据
------------------
经度不是装饰。同一���「中午 12 点」：

    北京   真太阳时 11:49  时柱 壬午
    乌鲁木齐 真太阳时 09:54  时柱 辛巳

差 2 小时，时柱直接差一格。坐标填错 = 时柱错，**且没有任何提示**。
手写 2900 个区县的坐标不可能可靠。

数据源：DataV.GeoAtlas（阿里，基于国家统计局行政区划）
    https://geo.datav.aliyun.com/areas_v3/bound/{adcode}_full.json
下钻规则：请求某级的 adcode，拿回的是它的**下一级**要素。
    100000 -> 34 个省
    110000 -> 北京的 16 个区
    440100 -> 广州的 11 个区

坐标口径：用 `center`（政府驻点/行政中心）而不是 `centroid`（多边形几何中心）。
真太阳时校正要用的是「当地实际用的钟表时」，行政中心更接近用户认知的那个点；
几何中心在形状狭长的行政区（如甘肃、内蒙古）会偏出十几公里。

用法
----
    python web/gen_regions.py               # 抓取并生成
    python web/gen_regions.py --out xxx.json
"""
import argparse
import io
import json
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "js", "regions.json")
CACHE = os.path.join(HERE, ".regions_cache")

BASE = "https://geo.datav.aliyun.com/areas_v3/bound/"
UA = {"User-Agent": "mingli-oracle/1.2 (regions fetcher)"}

# 只抓到这一级。区县往下的「街道/乡镇」对真太阳时没有额外价值，
# 而数据量会翻十几倍。
MAX_LEVEL = 3          # province / city / district

LEVEL_CN = {1: "省", 2: "市", 3: "区"}


def fetch(adcode, cache=True):
    """取某个 adcode 的下一级要素。带磁盘缓存 —— 抓一次要几百个请求，
    失败重来时不必再打一次源站。"""
    os.makedirs(CACHE, exist_ok=True)
    cf = os.path.join(CACHE, "%s.json" % adcode)
    if cache and os.path.isfile(cf):
        try:
            return json.loads(io.open(cf, encoding="utf-8").read())
        except Exception:
            pass
    url = BASE + "%s_full.json" % adcode
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=40) as r:
                raw = r.read().decode("utf-8")
            j = json.loads(raw)
            io.open(cf, "w", encoding="utf-8").write(raw)
            time.sleep(0.25)          # 别把源站打挂
            return j
        except Exception as e:
            if attempt == 3:
                print("   !! 取 %s 失败: %s" % (adcode, e), file=sys.stderr)
                return None
            time.sleep(1.5 * (attempt + 1))
    return None


def walk(adcode, level, province, city, out, stats):
    """递归下钻，把结果摊平成 {省: {市: {区县: [lon, lat]}}}。

    为什么必须看 features 里的 `level` 而不能靠「数第几层」
    --------------------------------------------------
    直辖市（北京/上海/天津/重庆）和「省直辖县级行政区」
    没有地级市这一层：110000 的下一级直接就是东城区、西城区。
    海南的济源市、新疆的县级市也是同理。

    所以「第一级=市」这个假设是错的，会把区县错记成市。
    正确做法是读数据自带的 level 字段。
    """
    j = fetch(adcode)
    if j is None:
        return
    feats = j.get("features") or []
    stats["requests"] = stats.get("requests", 0) + 1

    for f in feats:
        p = f.get("properties") or {}
        name = p.get("name")
        code = p.get("adcode")
        c = p.get("center") or p.get("centroid")
        lvl = p.get("level")
        if not name or code is None or not c:
            continue
        lon, lat = round(c[0], 4), round(c[1], 4)

        if lvl == "province":
            # 省级自成一格；市级挂到上一级传入的 province 名下
            prov = name
            cty = name
            out.setdefault(prov, {}).setdefault(cty, {"__own__": [lon, lat]})
        elif lvl == "city":
            prov = province or name
            cty = name
            out.setdefault(prov, {}).setdefault(cty, {"__own__": [lon, lat]})
            # 地级市要继续下钻到区县
            walk(code, level + 1, prov, cty, out, stats)
        elif lvl == "district":
            prov = province or "?"
            cty = city or prov
            out.setdefault(prov, {}).setdefault(cty, {})[name] = [lon, lat]
            stats["district"] = stats.get("district", 0) + 1
        else:
            continue

        if lvl in ("province", "city"):
            stats[lvl] = stats.get(lvl, 0) + 1


def main(argv=None):
    p = argparse.ArgumentParser(description="抓取全国行政区划经纬度")
    p.add_argument("--out", default=OUT)
    p.add_argument("--no-cache", action="store_true")
    a = p.parse_args(argv)

    print("抓取行政区划经纬度（DataV.GeoAtlas）\n")

    out = {}
    stats = {}
    root = fetch("100000", cache=not a.no_cache)
    if root is None:
        print("无法连接数据源，退出", file=sys.stderr)
        return 2

    feats = root.get("features") or []
    provinces = []
    for f in feats:
        p = f.get("properties") or {}
        if p.get("level") != "province":
            continue
        c = p.get("center") or p.get("centroid")
        provinces.append((p["adcode"], p["name"], c))
    print("省级 %d 个\n" % len(provinces))

    for i, (code, name, center) in enumerate(provinces, 1):
        # 省级自身的坐标要先落进去。直辖市（北京/上海/天津/重庆）与港澳
        # 下钻后直接就是区县，中间没有「市」这一层，
        # 所以它们的 __own__ 不会由 walk() 填出来 —— 少填的话
        # 「只填到省级」的用户就拿不到坐标。
        if center:
            out.setdefault(name, {}).setdefault(name, {})["__own__"] = [
                round(center[0], 4), round(center[1], 4)]
            stats["province"] = stats.get("province", 0) + 1
        print("  [%2d/%d] %s ..." % (i, len(provinces), name), end="", flush=True)
        n0 = stats.get("district", 0)
        walk(code, 1, name, name, out, stats)
        print(" %d 个区县" % (stats.get("district", 0) - n0))

    payload = {"source": "DataV.GeoAtlas（国家统计局行政区划）",
               "coord": "center = 行政中心，非几何质心",
               "provinces": out}

    io.open(a.out, "w", encoding="utf-8").write(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")))

    n_prov = len(out)
    n_city = sum(len(v) for v in out.values())
    n_dist = sum(len(d) - (1 if "__own__" in d else 0)
                 for v in out.values() for d in v.values())
    kb = os.path.getsize(a.out) / 1024.0
    print()
    print("已生成 %s（%.1f KB）" % (a.out, kb))
    print("  省 %d / 市 %d / 区县 %d" % (n_prov, n_city, n_dist))
    print("  HTTP 请求 %d 次" % stats.get("requests", 0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验 web/js/regions.json 的坐标是否可信。

为什么必须校验
--------------
经度直接改时柱：同一个「中午 12 点」，北京真太阳时 11:49、乌鲁木齐 09:54，
时柱差一格。**坐标错了不会有任何报错，只会算出一张 quietly 错的盘。**

所以这份数据进仓库之前必须过一遍：
  - 坐标落在国境内（越界说明抓串了层级）
  - 经度不东倒西歪（个别行政区质心会飘到境外）
  - 与原先那份手工核过的 41 城市表交叉比对 —— 那是唯一已知的参照
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(HERE, "js", "regions.json")

# 之前手工核对过的城市坐标（app.html 里那张表），作为参照基准
KNOWN = {
    "北京": (116.41, 39.90), "上海": (121.47, 31.23), "广州": (113.26, 23.13),
    "深圳": (114.06, 22.55), "成都": (104.07, 30.57), "杭州": (120.15, 30.28),
    "武汉": (114.30, 30.59), "西安": (108.94, 34.34), "南京": (118.78, 32.06),
    "重庆": (106.55, 29.56), "天津": (117.20, 39.13), "沈阳": (123.43, 41.80),
    "哈尔滨": (126.53, 45.80), "昆明": (102.83, 24.88), "南宁": (108.32, 22.82),
    "兰州": (103.83, 36.06), "乌鲁木齐": (87.62, 43.83),
    # 拉萨原先写的是 (91.11, 29.97)，被这次交叉比对判为偏 0.31°。
    # 查证：拉萨实际在北纬 29.65 度（29.66~29.70 之间），
    # 29.97 是错的 —— 是**旧的手工表错了**，数据源是对的。
    # 这正是加这道交叉比对的意义：手工表的错本来会一直错下去。
    "拉萨": (91.14, 29.65),
    "海口": (110.20, 20.04), "长春": (125.32, 43.82), "大连": (121.62, 38.92),
    "香港": (114.17, 22.32), "澳门": (113.55, 22.20),
}

# 中国大致经纬范围（含领海，略微放宽以便发现抓错层级）
LON_RANGE = (72.0, 136.0)
LAT_RANGE = (2.0, 54.5)

# 省级坐标自检的容差。0.5° ≈ 55km 纬度 / 44km 经度。
# 省界是曲线，本省包围盒比省界大，贴边的（甘肃、内蒙古）
# 省级行政中心可能被排除在外，所以要给容差。
PROV_TOL = 0.5
# 超出这个量级一定是放错省了 —— 相邻省界最远也就这个尺度
PROV_HARD = 4.0


def norm(name):
    """把「广州市」「内蒙古自治区」归一化成「广州」「内蒙古」。

    数据源带行政通名后缀，而参照表用简称。不归一化的话
    交叉比对会「一个都没命中」，而那看上去像是数据全错 ——
    实际上只是名字对不上。分不清这两种情况的检查没有意义。
    """
    for suf in ("特别行政区", "回族自治州", "维吾尔自治区", "壮族自治区",
                "回族自治区", "自治区", "自治州", "地区", "省", "市"):
        if name.endswith(suf):
            return name[: -len(suf)]
    return name


def main():
    if not os.path.isfile(P):
        print("找不到 %s，请先运行 gen_regions.py" % P)
        return 2
    d = json.loads(io.open(P, encoding="utf-8").read())
    provs = d["provinces"]
    print("校验 %s（%.1f KB）\n" % (P, os.path.getsize(P) / 1024.0))
    print("数据源: %s" % d.get("source"))
    print("坐标口径: %s\n" % d.get("coord"))

    fails = []
    n_city = n_dist = 0
    oob = []

    for pname, cities in provs.items():
        for cname, node in cities.items():
            n_city += 1
            own = node.get("__own__")
            if own:
                lon, lat = own
                if not (LON_RANGE[0] <= lon <= LON_RANGE[1]
                        and LAT_RANGE[0] <= lat <= LAT_RANGE[1]):
                    oob.append(("%s/%s" % (pname, cname), lon, lat))
            for dname, coord in node.items():
                if dname == "__own__":
                    continue
                n_dist += 1
                lon, lat = coord
                if not (LON_RANGE[0] <= lon <= LON_RANGE[1]
                        and LAT_RANGE[0] <= lat <= LAT_RANGE[1]):
                    oob.append(("%s/%s/%s" % (pname, cname, dname), lon, lat))

    print("规模：省 %d / 市 %d / 区县 %d" % (len(provs), n_city, n_dist))
    print()
    print("1) 坐标是否都在国境内")
    if oob:
        print("   [FAIL] %d 条越界：" % len(oob))
        for name, lon, lat in oob[:15]:
            print("      %-40s lon=%.3f lat=%.3f" % (name, lon, lat))
        fails.append("%d 条坐标越界" % len(oob))
    else:
        print("   [OK] 全部 %d 条在 lon[%.0f,%.0f] × lat[%.0f,%.0f] 内"
              % (n_city + n_dist, LON_RANGE[0], LON_RANGE[1],
                 LAT_RANGE[0], LAT_RANGE[1]))

    # ---- 交叉比对：与手工核过的 41 城市表 ----
    print()
    print("2) 与手工核对过的城市坐标交叉比对")
    # 建索引（名字归一化）：名字 -> [(lon, lat, 来源路径)]
    idx = {}
    for pname, cities in provs.items():
        for cname, node in cities.items():
            if node.get("__own__"):
                idx.setdefault(norm(cname), []).append(
                    (node["__own__"][0], node["__own__"][1], "%s/%s" % (pname, cname)))
            for dname, coord in node.items():
                if dname == "__own__":
                    continue
                idx.setdefault(norm(dname), []).append(
                    (coord[0], coord[1], "%s/%s/%s" % (pname, cname, dname)))

    compared = 0
    big_diff = []
    for name, (k_lon, k_lat) in KNOWN.items():
        hits = idx.get(norm(name))
        if not hits:
            print("   [--] %-8s 未在新数据里找到（可能已改名或并入他市）" % name)
            continue
        # 取最接近手工值的一条
        best = min(hits, key=lambda h: (h[0] - k_lon) ** 2 + (h[1] - k_lat) ** 2)
        dlon, dlat = best[0] - k_lon, best[1] - k_lat
        # 0.3° ≈ 30km。真太阳时 4 分钟/度，0.3° 就是 1.2 分钟 —— 可接受
        d = (dlon ** 2 + dlat ** 2) ** 0.5
        compared += 1
        if d > 0.3:
            big_diff.append((name, best[2], d, dlon, dlat))
            print("   [FAIL] %-8s 差 %.3f°  新(%s)=%.3f,%.3f  旧=%.3f,%.3f"
                  % (name, d, best[2], best[0], best[1], k_lon, k_lat))
        else:
            print("   [OK]   %-8s 差 %.3f°  (%s)" % (name, d, best[2]))
    if big_diff:
        fails.append("%d 个城市与手工表差 >0.3°" % len(big_diff))
    else:
        print("   -> 交叉比对的 %d 个城市全部在 0.3°（约 30km）以内" % compared)

    # ---- 结构完整性 ----
    print()
    print("3) 结构完整性")
    empty_city = [c for pn, cs in provs.items() for c, nd in cs.items()
                  if not [k for k in nd if k != "__own__"] and not nd.get("__own__")]
    if empty_city:
        print("   [FAIL] %d 个市既无自身坐标也无区县：" % len(empty_city))
        fails.append("有空的市节点")
    else:
        print("   [OK] 没有空的市节点")

    # 台湾等无下级的省级单位
    only_self = [p for p, cs in provs.items()
                 for c, nd in cs.items() if list(nd.keys()) == ["__own__"]]
    if only_self:
        print("   [--] %d 个市/省只有自身坐标、无下级：" % len(only_self))
        print("        例: %s" % ", ".join(only_self[:6]))

    missing_prov = [x for x in ("台湾省", "香港特别行政区", "澳门特别行政区",
                               "西藏自治区", "新疆维吾尔自治区")
                    if x not in provs]
    if missing_prov:
        # 数据源本身没有台湾的下级要素（710000_full.json 返回 404），
        # 不是抓取逻辑漏了。记为已知缺口而不是失败 ——
        # 但要显式说出来，不能让它悄悄变成「查不到台湾」。
        print("   [--] 缺少省级单位: %s" % ", ".join(missing_prov))
        print("        数据源未提供该区下级要素（非抓取遗漏），")
        print("        该省只能用「手填经纬度」路径。")
    else:
        print("   [OK] 含台湾/香港/澳门/西藏/新疆")

    # ---- 省级坐标有没有放错省 ----
    # 前两条检查都抓不到这一类：坐标只要还在国境内就放行，
    # 而「河北省的坐标其实是内蒙的」正是这样溜过去的。
    # 判据不依赖手工表 —— 用本省所有区县的包围盒反推：
    # 省会级行政中心必然在本省范围内，超出 4° 就是抓错省了。
    print()
    print("4) 省级坐标是否落在本省包围盒内")
    print("   容差 ±%.1f°（约 55km），硬上限 %.1f°" % (PROV_TOL, PROV_HARD))
    prov_bad, prov_warn, prov_ok = [], [], 0
    for pn, cities in provs.items():
        pts = []
        for cn, node in cities.items():
            if node.get("__own__"):
                pts.append(node["__own__"])
            for k, v in node.items():
                if k != "__own__":
                    pts.append(v)
        own = (cities.get(pn) or {}).get("__own__")
        if not pts or not own:
            prov_bad.append((pn, "缺坐标或缺下级，无法自检"))
            continue
        lons = [p[0] for p in pts]
        lats = [p[1] for p in pts]
        lo0, lo1, la0, la1 = min(lons), max(lons), min(lats), max(lats)
        over = max(lo0 - own[0], own[0] - lo1, la0 - own[1], own[1] - la1, 0)
        if over <= PROV_TOL:
            prov_ok += 1
        elif over <= PROV_HARD:
            prov_warn.append((pn, own, over, (lo0, lo1, la0, la1)))
        else:
            prov_bad.append((pn, own, over, (lo0, lo1, la0, la1)))
    print("   [OK]   %d 个省的自身坐标落在本省范围内" % prov_ok)
    for pn, own, over, bb in prov_warn:
        print("   [--]   %-14s (%.3f, %.3f) 超出包围盒 %.2f°，请人工确认"
              % (pn, own[0], own[1], over))
    if prov_bad:
        print("   [FAIL] %d 个省坐标明显不在本省：" % len(prov_bad))
        for item in prov_bad:
            if len(item) >= 4:
                pn, own, over, bb = item
                print("      %-14s (%.3f, %.3f)  本省 lon[%.2f,%.2f] lat[%.2f,%.2f]  超出 %.2f°"
                      % (pn, own[0], own[1], bb[0], bb[1], bb[2], bb[3], over))
            else:
                print("      %-14s %s" % (item[0], item[-1]))
        fails.append("%d 个省的坐标不在本省范围内" % len(prov_bad))
    else:
        print("   -> 未发现省级坐标放错省的情况（这条不依赖手工对照表）")

    print()
    print("=" * 60)
    if fails:
        print("校验失败 %d 项：" % len(fails))
        for f in fails:
            print("  - " + f)
        return 1
    print("坐标数据可信：在境内、与手工表交叉一致、省级坐标未放错省")
    return 0


if __name__ == "__main__":
    sys.exit(main())
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""命理神机 · 回归自测。

运行：python self_test.py
用途：验证历法、八字、紫微、占星、六爻五大引擎的算法锚点未被改坏。
所有断言均来自权威来源（Meeus 天文算法、iztro 官方文档示例、命理通行规则）。
"""

import sys

import almanac as A
import bazi as B
import ziwei as Z
import astro as S
import divination as D
import plain as PL
import oracle as O

PASS = 0
FAIL = 0


def ck(label, got, want):
    global PASS, FAIL
    if got == want:
        PASS += 1
        print("  [OK]   %s => %s" % (label, got))
    else:
        FAIL += 1
        print("  [FAIL] %s => %s  (期望 %s)" % (label, got, want))


def test_almanac():
    print("== 历法引擎 ==")
    ck("1990-05-15 日柱", A.day_gz(1990, 5, 15), "庚辰")
    ck("2000-01-01 日柱", A.day_gz(2000, 1, 1), "戊午")
    ck("1984 年干支", A.gz_from_index(A.year_gz_index(1984)), "甲子")
    ck("1990-05-15 月柱", A.month_gz(A.beijing(1990, 5, 15, 12))[0], "辛巳")
    ck("1990-02-03 年柱（未过立春）", A.year_gz(A.beijing(1990, 2, 3, 10))[0], "己巳")
    ck("庚日午时时柱", A.hour_gz("庚", 6), "壬午")
    ck("1990-05-15 农历", A.solar_to_lunar(1990, 5, 15), (1990, 4, 21, False))
    ck("农历反算", A.lunar_to_solar(1990, 4, 21).isoformat(), "1990-05-15")
    ck("纳音 甲子", A.nayin_of("甲", "子"), "海中金")
    ck("纳音 庚辰", A.nayin_of("庚", "辰"), "白蜡金")
    ck("1990 立春在 2/4", (A.solar_term_beijing(1990, 315).month, A.solar_term_beijing(1990, 315).day), (2, 4))
    ck("2024 冬至在 12/21", (A.solar_term_beijing(2024, 270).month, A.solar_term_beijing(2024, 270).day), (12, 21))
    ck("太阳黄经 2000-01-01 ≈ 280°", round(A.sun_apparent_longitude(2451545.0)), 280)


def test_bazi():
    print("== 八字引擎 ==")
    r = B.pai_pan(solar=(1990, 5, 15), hour=(12, 0), sex="男")
    ck("四柱", (r["四柱"]["年"], r["四柱"]["月"], r["四柱"]["日"], r["四柱"]["时"]),
       ("庚午", "辛巳", "庚辰", "壬午"))
    ck("日主", (r["日主"]["干"], r["日主"]["五行"], r["日主"]["阴阳"]), ("庚", "金", "阳"))
    ck("年柱十神（庚见庚=比肩）", r["柱详解"][0]["干十神"], "比肩")
    ck("月柱十神（庚见辛=劫财）", r["柱详解"][1]["干十神"], "劫财")
    ck("时柱十神（庚见壬=食神）", r["柱详解"][3]["干十神"], "食神")
    ck("日支辰藏干", [c["干"] for c in r["柱详解"][2]["支藏干"]], ["戊", "乙", "癸"])
    ck("月支巳藏干十神", [c["十神"] for c in r["柱详解"][1]["支藏干"]], ["七杀", "比肩", "偏印"])
    ck("格局（月令丙火克庚金·同阳=七杀格）", r["格局"]["名"], "七杀格")
    ck("大运顺逆（庚阳年男顺排）", r["大运"]["顺逆"], "顺排")
    ck("旬空（庚辰日属甲戌旬）", r["旬空"], "申酉")
    # 十神函数交叉校验
    ck("十神 甲见丙=食神", B.shishen("甲", "丙"), "食神")
    ck("十神 甲见丁=伤官", B.shishen("甲", "丁"), "伤官")
    ck("十神 甲见戊=偏财", B.shishen("甲", "戊"), "偏财")
    ck("十神 甲见己=正财", B.shishen("甲", "己"), "正财")
    ck("十神 甲见庚=七杀", B.shishen("甲", "庚"), "七杀")
    ck("十神 甲见辛=正官", B.shishen("甲", "辛"), "正官")
    ck("十神 甲见壬=偏印", B.shishen("甲", "壬"), "偏印")
    ck("十神 甲见癸=正印", B.shishen("甲", "癸"), "正印")


def test_ziwei():
    print("== 紫微引擎（对照 iztro 官方算法）==")

    def iztro_ziwei(ju, day):
        off = -1
        while True:
            off += 1
            if (day + off) % ju == 0:
                break
        q = ((day + off) // ju) % 12
        zi = q - 1
        zi += off if off % 2 == 0 else -off
        return zi % 12  # 寅为 0

    bad = 0
    for ju in (2, 3, 4, 5, 6):
        for d in range(1, 31):
            if Z.an_ziwei(ju, d) != (iztro_ziwei(ju, d) + 2) % 12:
                bad += 1
    ck("紫微定位 5局×30日 与 iztro 全等", bad, 0)
    # iztro 文档三个官方示例
    ck("例一 木三局廿七 → 戌", A.ZHI[Z.an_ziwei(3, 27)], "戌")
    ck("例二 火六局十三 → 亥", A.ZHI[Z.an_ziwei(6, 13)], "亥")
    ck("例三 土五局初六 → 未", A.ZHI[Z.an_ziwei(5, 6)], "未")

    r = Z.pai_pan(solar=(1991, 8, 15), hour=1, sex="男")
    ck("命宫（七月丑时）", r["命宫"]["地支"], "未")
    ck("身宫（七月丑时）", r["身宫"]["地支"], "酉")
    ck("年干支 1991", r["输入"]["年干支"], "辛未")
    ck("五行局（乙未纳音沙中金）", r["五行局"], "金四局")
    ck("紫微星", r["紫微星"], "巳宫")
    ck("天府星", r["天府星"], "亥宫")
    ck("四化辛干化忌=文昌", r["四化"]["化忌"], "文昌")
    ck("大限逆行（辛阴年男）", r["大限"]["顺逆"], "逆行")
    ck("起运虚岁=局数4", r["大限"]["起运虚岁"], 4)
    # 星曜落宫抽样（星曜名可能带「·化X」后缀）
    pal = {p["地支"]: [s.split("·")[0] for s in p["星曜"]] for p in r["十二宫"]}
    ck("紫微在巳", "紫微" in pal["巳"], True)
    ck("天机在辰", "天机" in pal["辰"], True)
    ck("太阳在寅", "太阳" in pal["寅"], True)
    ck("天府在亥", "天府" in pal["亥"], True)
    ck("破军在酉", "破军" in pal["酉"], True)
    ck("命宫空宫（对宫武贪）", pal["未"], [])


def test_astro():
    print("== 占星引擎 ==")
    r = S.pai_pan(solar=(1990, 5, 15), hour=(12, 0), lat=39.9, lon=116.4)
    ck("太阳星座（5/15=金牛）", r["太阳星座"], "金牛")
    ck("月亮星座（1990-05-15 月亮在摩羯）", r["月亮星座"], "摩羯")
    ck("土星在摩羯（1988-1996）", next(p["星座"] for p in r["天体"] if p["天体"] == "土星"), "摩羯")
    ck("冥王星在天蝎（1983-1995）", next(p["星座"] for p in r["天体"] if p["天体"] == "冥王星"), "天蝎")
    ck("上升星座存在", r["上升星座"] in S.SIGNS, True)
    # 正午太阳应接近天顶（MC）
    sun = next(p["黄经"] for p in r["天体"] if p["天体"] == "太阳")
    mc = r["轴点"]["天顶"]["黄经"]
    ck("正午 MC 与太阳相差 <6°", abs((sun - mc + 180) % 360 - 180) < 6, True)


def test_divination():
    print("== 六爻引擎 ==")
    r = D.divinate(method="time", solar=(1990, 5, 15), hour=(12, 0))
    ck("时间起卦 1990-05-15 午时 → 地山谦", r["本卦"]["卦名"], "地山谦")
    ck("谦卦属兑宫", r["本卦"]["宫"], "兑")
    ck("谦卦世5应2", (r["本卦"]["世爻"], r["本卦"]["应爻"]), (5, 2))
    ck("动爻第3爻", r["动爻"], [3])
    ck("变卦 坤为地", r["变卦"]["卦名"], "坤为地")
    ck("谦卦初爻纳甲 丙辰", r["本卦"]["爻"][0]["纳甲"], "丙辰")
    ck("谦卦初爻六亲 父母（辰土生兑金）", r["本卦"]["爻"][0]["六亲"], "父母")
    ck("谦卦二爻六亲 官鬼（午火克金）", r["本卦"]["爻"][1]["六亲"], "官鬼")
    ck("庚日起初爻白虎", r["本卦"]["爻"][0]["六神"], "白虎")
    # 卦名表完整性：64 卦全覆盖
    ck("六十四卦表条目数", len(D.GUA64), 64)
    ck("八宫卦序覆盖 64 卦", sum(len(v) for v in D.GONG_ORDER.values()), 64)


def test_plain():
    print("== 白话解读引擎 ==")
    ck("日主文案覆盖 10 天干", len(PL.DAY_MASTER), 10)
    ck("十神文案覆盖 10 神", len(PL.SHISHEN), 10)
    ck("紫微主星文案覆盖 14 星", len(PL.ZIWEI_STAR), 14)
    ck("每颗主星含 核心/事业/财运/感情 四维",
       all(all(k in v for k in ("核心", "事业", "财运", "感情")) for v in PL.ZIWEI_STAR.values()), True)
    ck("神煞文案非空", len(PL.SHENSHA) > 15, True)
    ck("术语表非空", len(PL.GLOSSARY) > 15, True)
    ck("星座白话覆盖 12 星座", len(PL.SIGN_PLAIN), 12)
    # 实用对应表
    ck("五行开运表覆盖 5 行", len(PL.WUXING_LUCK), 5)
    ck("每行开运含 颜色/方位/数字/行业/饰品/日常",
       all(all(k in v for k in ("颜色", "方位", "数字", "行业", "饰品", "日常"))
           for v in PL.WUXING_LUCK.values()), True)
    ck("星座实用档案覆盖 12 座", len(PL.SIGN_PROFILE), 12)
    ck("每座档案含 8 个字段",
       all(len(v) == 8 for v in PL.SIGN_PROFILE.values()), True)
    ck("生肖表覆盖 12 生肖", len(PL.SHENGXIAO), 12)
    ck("地支转生肖覆盖 12 支", len(PL.ZHI_TO_SX), 12)

    d = O.build(solar=(1990, 5, 15), hour=(12, 0), sex="男", lat=39.9, lon=116.4)
    hl = PL.headline(d)
    ck("一句话总览含三盘关键词", ("庚" in hl and "紫微" in hl and "金牛" in hl), True)

    b = PL.bazi_plain(d["八字"])
    ck("八字白话-性格底色有内容", len(b["性格底色"]["要点"]) > 8, True)
    ck("八字白话-做事方式有内容", len(b["做事方式"]["要点"]) > 8, True)
    # 当前大运十神必须来自大运而非流年
    dy = next(x for x in d["八字"]["大运"]["列表"] if x["干支"] == b["当前阶段"]["干支"])
    ck("当前大运十神与大运表一致", b["当前阶段"]["十神"], dy["十神"])
    # 生肖与开运指南
    ck("八字-生肖为马（1990 庚午年）", b["生肖"]["生肖"], "马")
    ck("八字-开运指南五行=喜用神",
       b["开运指南"]["五行"], "、".join(d["八字"]["日主强弱"]["喜用神"]))
    ck("八字-开运指南含幸运色", len(b["开运指南"]["颜色"]) > 4, True)
    ck("八字-开运指南含适合行业", len(b["开运指南"]["行业"]) > 6, True)

    z = PL.ziwei_plain(d["紫微"])
    ck("紫微白话-命宫主星", z["主星"], "天梁")
    ck("紫微-开运指南含五行局", z["开运指南"]["局"], "土五局")
    ck("紫微-开运指南含幸运色", len(z["开运指南"]["颜色"]) > 4, True)
    # 分维度文案不得串味：夫妻宫天机的解读应落在感情维度
    ck("感情模式用「感情」维度文案", "感情" in z["感情模式"]["要点"], True)
    ck("财运模式用「财运」维度文案", "财" in z["财运模式"]["要点"], True)

    a = PL.astro_plain(d["占星"])
    ck("太阳星座文案覆盖 12 座", len(PL.SUN_SIGN), 12)
    ck("月亮星座文案覆盖 12 座", len(PL.MOON_SIGN), 12)
    ck("上升星座文案覆盖 12 座", len(PL.ASC_SIGN), 12)
    ck("水星/金星/火星文案各 12 条",
       (len(PL.MERCURY_SIGN), len(PL.VENUS_SIGN), len(PL.MARS_SIGN)), (12, 12, 12))
    ck("宫位含义 12 条", len(PL.HOUSE_MEANING), 12)
    ck("上升守护星 12 座全覆盖", len(PL.RULER), 12)
    ck("相位性质 5 类", len(PL.ASPECT_TRAIT), 5)
    ck("占星-三支柱含太阳月亮上升", len(a["三支柱"]["列表"]), 3)
    ck("占星-第一支柱是太阳金牛", a["三支柱"]["列表"][0]["座"], "金牛")
    ck("占星-性格拼图 3 项", len(a["性格拼图"]["列表"]), 3)
    ck("占星-人生重心有宫位解读", len(a["人生重心"]["列表"]) > 0, True)
    ck("占星-关键线索非空", bool(a["关键线索"]), True)
    ck("占星-关系张力非空", len(a["关系张力"]["列表"]) > 0, True)
    ck("占星-能量配比含四元素明细",
       set(a["元素配比"]["明细"]) == {"火", "土", "风", "水"}, True)
    ck("占星-实用档案 3 项（日/月/升）", len(a["实用档案"]["列表"]), 3)
    ck("占星-档案含守护星/幸运色/宝石/职业",
       all(all(k in x["档案"] for k in ("守护星", "幸运色", "宝石", "职业"))
           for x in a["实用档案"]["列表"]), True)
    # 没填出生地时要优雅降级，不能崩
    d3 = O.build(solar=(1985, 11, 20), hour=(20, 0), sex="男")
    a3 = PL.astro_plain(d3["占星"])
    ck("占星-无出生地时支柱只有 2 项", len(a3["三支柱"]["列表"]), 2)
    ck("占星-无出生地时无宫位解读", len(a3["人生重心"]["列表"]), 0)
    ck("占星-无出生地时给出提示", "出生地" in a3["一句话"], True)
    ck("占星-无出生地时关键线索为空", a3["关键线索"], None)

    # 空宫借星路径
    d2 = O.build(solar=(1991, 8, 15), hour=(1, 0), sex="男", lat=31.2, lon=121.5)
    z2 = PL.ziwei_plain(d2["紫微"])
    ck("空宫借对宫主星（武曲）", z2["主星"], "武曲")
    ck("空宫说明含「借」字", "借" in z2["一句话"], True)


def test_server():
    print("== 本地服务与交互界面 ==")
    import server as SV
    page = SV.build_page()
    ck("页面能生成", len(page) > 5000, True)
    ck("样式已注入（无残留占位符）", "/*__ORACLE_CSS__*/" not in page, True)
    ck("样式表带 id 供导出复用", 'id="oracle-css"' in page, True)
    ck("页面含表单与提交按钮", ('id="form"' in page and 'id="submitBtn"' in page), True)
    ck("页面含状态提示区", 'aria-live="polite"' in page, True)
    ck("页面含移动端适配", "viewport" in page and "@media(max-width:480px)" in page, True)
    ck("表单收起逻辑存在", "collapsed" in page, True)
    # 前端脚本不能出现会被 HTML 解析器误伤的裸 </head>
    import re
    js = re.findall(r"<script>(.*?)</script>", page, re.S)[-1]
    ck("前端脚本无裸 </head> 字面量", "</head>" not in js, True)
    ck("前端脚本无裸 </body> 字面量", "</body>" not in js, True)

    # 接口：正常
    r = SV.do_paipan({"solar": [1990, 5, 15], "hour": [12, 0], "sex": "男",
                      "lon": 116.4, "lat": 39.9, "place": "北京"})
    ck("接口排盘成功", r["ok"], True)
    ck("接口返回一句话总览", len(r["headline"]) > 8, True)
    ck("接口返回白话区", "先说人话" in r["plain_html"], True)
    ck("接口返回专业区", "四柱八字" in r["pro_html"], True)
    # 接口：各类错误提示都要是人话
    ck("缺生日", SV.do_paipan({"sex": "男"})["error"], "请先填出生日期。")
    ck("年份越界", SV.do_paipan({"solar": [1850, 1, 1], "sex": "男"})["ok"], False)
    ck("时间非法", SV.do_paipan({"solar": [1990, 5, 15], "hour": [99, 0], "sex": "男"})["ok"], False)
    ck("性别非法", SV.do_paipan({"solar": [1990, 5, 15], "sex": "外星人"})["ok"], False)
    ck("农历越界给白话提示",
       "天" in SV.do_paipan({"lunar": [1990, 4, 31], "sex": "男"})["error"], True)
    # 农历路径
    r2 = SV.do_paipan({"lunar": [1990, 4, 21], "shichen": "午", "sex": "男"})
    ck("农历接口可用", r2["ok"], True)


def test_regression():
    """固化历次复盘发现并修复的 bug，防止回归。

    这几条每一条都对应一个真实踩过的坑：
    - 行星黄经曾整体偏 1.4°/百年（坐标系混用 J2000 与 of-date）
    - 地球日心坐标曾少加 180°，导致行星位置全错
    - 置闰与冬至月曾按「精确时刻」判定，导致闰月/春节错位一个月
    - 五虎遁宫干在子、丑两宫曾因负数取模算错
    """
    print("== 回归锚点（复盘修复项）==")
    from datetime import datetime, timezone
    dt = datetime(1990, 5, 15, 12, 0, tzinfo=timezone.utc)
    jd = A.jd_from_datetime(dt)
    # 行星黄经快照（已用 ephem/VSOP87 交叉验证，误差 < 0.25°）
    SNAP = {"太阳": 54.40, "月亮": 297.14, "水星": 38.02, "金星": 12.82,
            "火星": 348.33, "木星": 99.58, "土星": 295.18, "天王星": 279.19,
            "海王星": 284.35, "冥王星": 226.16}
    for name, want in SNAP.items():
        got = A.planet_geocentric_longitude(name, jd)
        # 容差 0.05°：远小于占星需要的 1°，但足以抓住坐标系类错误
        ck("行星黄经 %s（容差0.05°）" % name, abs(got - want) < 0.05, True)

    # 农历：春节与闰月
    for (y, m, d) in [(2024, 2, 10), (2020, 1, 25), (2015, 2, 19), (2000, 2, 5)]:
        ck("春节 %04d-%02d-%02d" % (y, m, d), A.solar_to_lunar(y, m, d)[:3], (y, 1, 1))
    for y, lm in [(2020, 4), (2014, 9), (2023, 2), (2017, 6), (1990, 5)]:
        seg = list(A.lunar_months_between_dongzhi(y - 1)) + list(A.lunar_months_between_dongzhi(y))
        ck("%d 年闰 %d 月" % (y, lm),
            any(x["leap"] and x["year"] == y and x["month"] == lm for x in seg), True)

    # 八字：子月、丑月的月柱天干（五虎遁负数取模）
    for (d, want) in [((1990, 12, 15), "戊子"), ((1991, 1, 20), "己丑"), ((2020, 1, 15), "丁丑")]:
        r = B.pai_pan(solar=d, hour=(12, 0), sex="男")
        ck("月柱 %s" % str(d), r["四柱"]["月"], want)

    # 紫微：子、丑宫的宫干（同一处公式）
    z = Z.pai_pan(solar=(1990, 5, 15), hour=9, sex="男")   # 命宫落在子
    ming = next(p for p in z["十二宫"] if p["是否命宫"])
    ck("命宫落子时宫干为戊", ming["天干"] + ming["地支"], "戊子")


def main():
    A.setup_console()
    print("=" * 52)
    print("  命理神机 · 回归自测")
    print("=" * 52)
    test_almanac()
    test_bazi()
    test_ziwei()
    test_astro()
    test_divination()
    test_plain()
    test_server()
    test_regression()
    print("=" * 52)
    print("  通过 %d 项，失败 %d 项" % (PASS, FAIL))
    print("=" * 52)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

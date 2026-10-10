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


def _astro_sun_names():
    """跑引擎，取它**真实产出**的太阳星座名集合。

    不能硬编码 12 个星座名去比对 —— 那样断言的是「我以为引擎会返回什么」，
    而真正要防的是「表里的键和引擎的输出对不上」。
    之前就踩过：ASTRO_CROSS 的键写成「双子座」，引擎给的是「双子」，
    查表全部落空、占星那一整边静默消失，对拍还全绿。
    """
    import astro as AS
    seen = set()
    for mm in range(1, 13):
        for dd, hh in ((3, 2), (11, 9), (19, 17), (27, 22)):
            try:
                r = AS.pai_pan(solar=(1995, mm, dd), hour=(hh, 20),
                               sex="男", lat=39.9, lon=116.4)
            except Exception:
                continue
            n = r.get("太阳星座")
            if n:
                seen.add(n)
    return seen


def _astro_venus_names():
    """引擎真实产出的金星落座名。"""
    import astro as AS
    seen = set()
    for mm in range(1, 13):
        for dd, hh in ((3, 2), (11, 9), (19, 17), (27, 22)):
            try:
                r = AS.pai_pan(solar=(1995, mm, dd), hour=(hh, 20),
                               sex="男", lat=39.9, lon=116.4)
            except Exception:
                continue
            for p in (r.get("天体") or []):
                if p.get("天体") == "金星" and p.get("星座"):
                    seen.add(p["星座"])
    return seen


def _astro_phase_names():
    """引擎真实产出的相位名集合。"""
    import astro as AS
    seen = set()
    for mm in (1, 4, 7, 10):
        for dd in (5, 20):
            try:
                r = AS.pai_pan(solar=(1995, mm, dd), hour=(12, 0),
                               sex="男", lat=39.9, lon=116.4)
            except Exception:
                continue
            for a in (r.get("相位") or []):
                if a.get("相位"):
                    seen.add(a["相位"])
    return seen


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

    # ---- 1.6.0：查表键必须真能查到值 ----
    #
    # 这类错对拍抓不到：Python 与 JS 两边都返回空字符串，
    # 512 例全部一致，页面只是少讲了一段，看着正常。
    # PILLAR_ROLE 的键就曾写成「年柱」而数据是「年」，
    # 四柱对应整块全空。所以这里逐条查「有没有查到值」。
    kin = PL.bazi_plain(d["八字"])["六亲详批"]
    ck("六亲 柱位全部查到代表含义",
       all(x["代表"] for x in kin["柱位"]), True)
    # 注意：ck() 会把两边都排序后比，所以「年/月/日/时」写成什么顺序都过。
    # 想要真正的顺序断言，得先看 ck 的实现再决定用什么形式。
    ck("四柱对应覆盖 年月日时",
       set(x["柱"] for x in kin["柱位"]), set(["年", "月", "日", "时"]))
    ck("六亲 四个角色说明都非空",
       all(x["说明"] for x in kin["列表"]), True)
    # KIN_STARS 里存的是元组，所以「星」是元组不是列表。
    # 断言要跟着实际类型写，否则每次都比不过。
    ck("六亲 男女分派：男看财星",
       list(kin["列表"][0]["星"]), ["正财", "偏财"])
    dn = PL.bazi_plain(O.build(solar=(1990, 5, 15), hour=(12, 0), sex="女",
                               lat=39.9, lon=116.4)["八字"])["六亲详批"]
    ck("六亲 男女分派：女看官杀（同盘只差性别）",
       list(dn["列表"][0]["星"]), ["正官", "七杀"])
    ck("六亲 男女说明也不同（不是同一段话）",
       dn["列表"][0]["说明"] != kin["列表"][0]["说明"], True)

    sp = PL.ziwei_plain(d["紫微"])["夫妻详批"]
    ck("夫妻宫 主星非空", len(sp["主星"]) > 0, True)
    ck("夫妻宫 有组合或单星解读", bool(sp["组合"]), True)
    ck("夫妻宫 所有煞星都有解读",
       all(x["说明"] for x in sp["煞星"]), True)
    ck("夫妻宫 查不到解读的星为空", sp["未解读"], [])
    ck("夫妻宫 有大限年龄与说明",
       bool(sp["大限年龄"]) and bool(sp["大限说明"]), True)
    ck("夫妻宫 对宫非空", bool(sp["对宫"]), True)

    # 主星带四化后缀（"太阳·化禄"）时不能被丢。
    # 这个 bug 是时辰路径门禁抓出来的，512 例对拍全绿漏了它：
    # 那些盘夫妻宫要么有普通主星、要么本来就空。
    # 只调 _spouse_list，不走 ziwei_plain —— 后者要 12 宫齐全
    # （会去找「是否命宫」那一宫），造个残盘会 KeyError。
    def _zw(主星, 星曜):
        return PL._spouse_list({"十二宫": [{"宫名": "夫妻", "地支": "酉",
                                              "天干": "乙", "星曜": 星曜,
                                              "主星": 主星}],
                                "大限": {"列表": []}})

    sp2 = _zw(["太阳·化禄"], ["太阳·化禄", "擎羊"])
    ck("主星带化曜不被丢弃（太阳·化禄）", sp2["主星"], ["太阳·化禄"])
    ck("主星上的四化单列", len(sp2["四化"]), 1)
    ck("带化曜的主星不算「未解读」",
       "太阳·化禄" in sp2["未解读"], False)
    ck("带化曜时仍能查到解读", bool(sp2["组合"]), True)
    # 空数组：Python falsy / JS truthy，行为最容易分叉的地方
    sp3 = _zw([], [])
    ck("空主星返回空数组（不是 None）", sp3["主星"], [])

    hr = PL.astro_plain(d["占星"])["关系宫详批"]
    ck("关系宫 5 个", len(hr["列表"]), 5)
    ck("关系宫 顺序固定 7/8/4/10/11",
       [x["宫"] for x in hr["列表"]], [7, 8, 4, 10, 11])
    ck("关系宫 每宫都有名称与说明",
       all(x["名"] and x["管什么"] for x in hr["列表"]), True)
    ck("关系宫 每颗星都有解读",
       all(y["说明"] for x in hr["列表"] for y in x["星"]), True)
    ck("空宫有兜底说明", bool(hr["空宫说明"]), True)

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

    # ---- 1.7.0：B 类三盘交叉 ----
    #
    # 这一块的对拍完全抓不到三类问题，必须在这里断言：
    #   1. 查表键与引擎输出不一致（星座名差一个「座」字就静默失效）
    #   2. 只有一盘参与的维度整行消失（两边都空，一致）
    #   3. 某一盘无论换什么盘落点都不变（常量假输出）
    x = PL.cross_plain(d["八字"], d["紫微"], d["占星"])
    ck("交叉-六个维度全部有结论",
       len(x["一致"]) + len(x["分歧"]) + len(x["单盘"]), len(PL.CROSS_AXES))
    ck("交叉-三边都参与了（无单盘项）", len(x["单盘"]), 0)
    ck("交叉-每一维至少两家有信号",
       all(len(r["各家"]) >= 2 for r in x["一致"] + x["分歧"]), True)
    # 一致必须按**端点**算，不是按盘数算
    ck("交叉-一致项两端确实相同",
       all(len(set(g["端"] for g in r["各家"])) == 1 for r in x["一致"]), True)
    ck("交叉-分歧项两端确实不同",
       all(len(set(g["端"] for g in r["各家"])) > 1 for r in x["分歧"]), True)
    ck("交叉-每条依据都写清来源盘",
       all(g["盘"] in ("八字", "紫微", "占星") and g["依据"]
           for r in x["一致"] + x["分歧"] for g in r["各家"]), True)
    ck("交叉-明说三套不换算", "没有换算关系" in x["提醒"], True)
    # 查表键：引擎能产出的每个星座/主星都必须查得到
    ck("交叉-ASTRO_CROSS 覆盖引擎的 12 个星座名",
       sorted(PL.ASTRO_CROSS), sorted(_astro_sun_names()))
    ck("交叉-ZW_CROSS 覆盖全部 14 主星",
       sorted(set(PL.ZIWEI_STAR) - set(PL.ZW_CROSS)), [])
    # 维度不能有死条目：某一维若在某表整列是 None，那一边永远没信号
    ck("交叉-无死维度（紫微/占星每维都有落点）",
       all(any(row.get(s) is not None for row in PL.ZW_CROSS.values())
           and any(row.get(s) is not None for row in PL.ASTRO_CROSS.values())
           for s in PL.CROSS_SHORT), True)
    # 缺盘：单盘必须进「单盘」桶，不许静默消失
    only_b = PL.cross_plain(d["八字"], None, None)
    ck("交叉-只给八字时不丢维度",
       len(only_b["一致"]) + len(only_b["分歧"]) + len(only_b["单盘"]),
       len(PL.CROSS_AXES))
    ck("交叉-只给八字时全进单盘桶", len(only_b["单盘"]), len(PL.CROSS_AXES))
    empty = PL.cross_plain(None, None, None)
    ck("交叉-三盘全空不报错且为空",
       (len(empty["一致"]), len(empty["分歧"]), len(empty["单盘"])), (0, 0, 0))
    # 落点必须随盘变化：同一套八字换 12 个生辰，两端都要出现过
    seen = set()
    for mm, dd in ((1, 15), (3, 10), (5, 20), (7, 5), (9, 25),
                   (11, 8), (2, 28), (4, 3), (6, 30), (8, 18),
                   (10, 12), (12, 22)):
        dd2 = PL.cross_plain(
            O.build(solar=(1985, mm, dd), hour=(12, 0), sex="男",
                    lat=39.9, lon=116.4)["八字"], None, None)
        for r in dd2["单盘"]:
            seen.add(r["同向"])
    ck("交叉-八字落点两端都出现过（不是常量）", len(seen) > 1, True)

    # 渲染层：B 类块必须在、必须在 </section> 内、缺盘也要说话
    h = O.render_plain(d)
    ck("交叉-渲染出 B 类块", "三盘交叉" in h, True)
    ck("交叉-渲染块在 </section> 之前",
       h.find("三盘交叉") < h.rfind("</section>"), True)
    ck("交叉-渲染块默认折叠", '<details class="ssx">' in h, True)
    ck("交叉-渲染块标出三边来源",
       all(s["盘"] in h for s in x["依据"]), True)
    ck("交叉-渲染没把 HTML 标签转义出来", "&lt;b&gt;" in h, False)
    h_only_b = O.render_plain({"八字": d["八字"]})
    ck("交叉-缺盘时渲染块仍在", "三盘交叉" in h_only_b, True)
    ck("交叉-缺盘时说清只有一盘给了信号",
       "只有一盘给了信号" in h_only_b, True)
    ck("交叉-三盘全空时不渲染 B 类块",
       "三盘交叉" in O.render_plain({}), False)

    # ---- 1.7.0：C 类桃花星 + 行业细分 ----
    #
    # 这一类最危险的错是「缺键静默退化」：表里少一个键，
    # 那一条不会报错、不会空，只会换成泛泛的兜底文案，
    # 页面看着完整，内容其实被削平了。所以断言全部是
    # 「表里的键必须覆盖数据里出现的值」，不是「有内容」。
    _inds = set()
    for _row in PL.WUXING_LUCK.values():
        for _s in _row.get("行业", "").split("、"):
            if _s:
                _inds.add(_s)
    ck("行业细分-INDUSTRY_ROLES 覆盖 WUXING_LUCK 全部行业词",
       sorted(_inds - set(PL.INDUSTRY_ROLES)), [])
    ck("行业细分-每个行业都有角色类型且非空",
       all(v and all(isinstance(x, str) and x for x in v)
           for v in PL.INDUSTRY_ROLES.values()), True)
    # 角色必须是「行业内的通用分类」而不是具体职位名。
    # 判据用数量：通用分类每个行业 3~4 个且互不相同；
    # 若有人写成「适合当基金经理」这种，角色表就会退化成职位清单。
    ck("行业细分-每行业 3~4 个角色",
       all(3 <= len(v) <= 4 for v in PL.INDUSTRY_ROLES.values()), True)
    ck("行业细分-同一行业内角色不重复",
       all(len(set(v)) == len(v) for v in PL.INDUSTRY_ROLES.values()), True)

    th = PL.taohua_plain(d["八字"], d["紫微"], d["占星"])
    ck("桃花-三盘都给了线索",
       sorted(set(r["盘"] for r in th["列表"])), ["八字", "占星", "紫微"])
    ck("桃花-每条都有依据", all(r["依据"] for r in th["列表"]), True)
    ck("桃花-每条都有说明", all(r["说明"] for r in th["列表"]), True)
    ck("桃花-明说只讲倾向不预测", "不预测" in th["提醒"], True)
    ck("桃花-占星金星落座覆盖 12 星座",
       sorted(set(PL.VENUS_ATTRACT) - set(_astro_venus_names())), [])
    ck("桃花-相位表覆盖引擎的 6 类相位",
       sorted(set(_astro_phase_names()) - set(PL.VENUS_MOON_ASPECT)), [])
    ck("桃花-只给一盘时不崩也不空",
       all(len(PL.taohua_plain(*a)["列表"]) > 0
           for a in ((d["八字"], None, None), (None, d["紫微"], None),
                     (None, None, d["占星"]))), True)
    ck("桃花-三盘全空时为空不报错", PL.taohua_plain(None, None, None)["列表"], [])

    cr = PL.career_plain(d["八字"], d["紫微"], d["占星"])
    ck("行业-三盘都给了线索",
       sorted(set(r["盘"] for r in cr["列表"])), ["八字", "占星", "紫微"])
    ck("行业-每条都有依据", all(r["依据"] for r in cr["列表"]), True)
    ck("行业-每条都标明角色来源", all(r["角色来源"] for r in cr["列表"]), True)
    ck("行业-不用兜底分类（表覆盖完整）",
       [r["行业"] for r in cr["列表"] if r["角色来源"] == "兜底分类"], [])
    ck("行业-只到两层（不给具体职位名）",
       any(x in ("基金经理", "公务员", "医生", "律师", "教师")
           for r in cr["列表"] for x in r["角色"]), False)
    ck("行业-紫微/占星只用六类通用角色（不细分职位）",
       sorted(set(x for r in cr["列表"] if r["盘"] in ("紫微", "占星")
                  for x in r["角色"]) - set(PL.ROLE_FALLBACK)), [])
    ck("行业-八字用的是行业内细分角色（不是那六类）",
       all(x not in PL.ROLE_FALLBACK for r in cr["列表"]
           if r["盘"] == "八字" for x in r["角色"]), True)
    ck("行业-兜底六类都有说明",
       all(PL.ROLE_FALLBACK.get(k) for k in PL.ROLE_FALLBACK), True)
    ck("行业-明说不做加权合成", "不做加权合成" in cr["提醒"], True)
    ck("行业-三盘全空时为空不报错",
       PL.career_plain(None, None, None)["列表"], [])


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

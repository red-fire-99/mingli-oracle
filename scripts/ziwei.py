#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""紫微斗数排盘引擎（零第三方依赖，仅标准库）。

安星法遵循《紫微斗数全书》通行体系（三合派）：
  定命身宫 → 起五行局 → 安紫微（局数+生日）→ 安十四主星 → 安辅星 → 四化 → 大限流年。

铁律：星曜位置一律以本模块计算结果为准，语言模型不得凭记忆安星。

用法
----
python ziwei.py --solar 1991-08-15 --hour 1 --sex 男
python ziwei.py --lunar 1991-07-06 --shichen 丑 --sex 男 --json
"""

import argparse
import json
import sys

from almanac import (GAN, ZHI, solar_to_lunar,
                     lunar_to_solar, YUE_GAN_YIN, nayin_wuxing, GAN_YINYANG, format_lunar,
                     setup_console)

GONG_NAMES = ["命宫", "兄弟", "夫妻", "子女", "财帛", "疾厄",
              "迁移", "交友", "官禄", "田宅", "福德", "父母"]

# 五行局
JU_TABLE = {"水": 2, "木": 3, "金": 4, "土": 5, "火": 6}
JU_NAME = {2: "水二局", 3: "木三局", 4: "金四局", 5: "土五局", 6: "火六局"}

# 十四主星
ZIWEI_SERIES = [("紫微", 0), ("天机", -1), ("太阳", -3), ("武曲", -4), ("天同", -5), ("廉贞", -8)]
TIANFU_SERIES = [("天府", 0), ("太阴", 1), ("贪狼", 2), ("巨门", 3),
                 ("天相", 4), ("天梁", 5), ("七杀", 6), ("破军", 10)]

# 四化（年干）
SIHUA = {
    "甲": ("廉贞", "破军", "武曲", "太阳"),
    "乙": ("天机", "天梁", "紫微", "太阴"),
    "丙": ("天同", "天机", "文昌", "廉贞"),
    "丁": ("太阴", "天同", "天机", "巨门"),
    "戊": ("贪狼", "太阴", "右弼", "天机"),
    "己": ("武曲", "贪狼", "天梁", "文曲"),
    "庚": ("太阳", "武曲", "太阴", "天同"),
    "辛": ("巨门", "太阳", "文曲", "文昌"),
    "壬": ("天梁", "紫微", "左辅", "武曲"),
    "癸": ("破军", "巨门", "太阴", "贪狼"),
}

TIANKUI = {"甲": ("丑", "未"), "戊": ("丑", "未"), "庚": ("丑", "未"),
           "乙": ("子", "申"), "己": ("子", "申"),
           "丙": ("亥", "酉"), "丁": ("亥", "酉"),
           "壬": ("卯", "巳"), "癸": ("卯", "巳"), "辛": ("午", "寅")}

LUCUN = {"甲": "寅", "乙": "卯", "丙": "巳", "丁": "午", "戊": "巳",
         "己": "午", "庚": "申", "辛": "酉", "壬": "亥", "癸": "子"}

HUOXING_START = {"申": "寅", "子": "寅", "辰": "寅", "寅": "丑", "午": "丑", "戌": "丑",
                 "巳": "卯", "酉": "卯", "丑": "卯", "亥": "酉", "卯": "酉", "未": "酉"}
LINGXING_START = {"申": "戌", "子": "戌", "辰": "戌", "寅": "卯", "午": "卯", "戌": "卯",
                  "巳": "戌", "酉": "戌", "丑": "戌", "亥": "戌", "卯": "戌", "未": "戌"}
TIANMA = {"水": "寅", "火": "申", "金": "亥", "木": "巳"}
SANHE_JU = {"申": "水", "子": "水", "辰": "水", "寅": "火", "午": "火", "戌": "火",
            "巳": "金", "酉": "金", "丑": "金", "亥": "木", "卯": "木", "未": "木"}

# 主星特质（用于解读提示，不含吉凶断语）
STAR_BRIEF = {
    "紫微": "帝王之星，尊贵统御，喜居高位",
    "天机": "智慧谋略，机变善思，多动少静",
    "太阳": "光明博爱，施予奉献，利男性长辈",
    "武曲": "财星刚毅，执行力强，重原则",
    "天同": "福星温和，知足随和，喜安逸",
    "廉贞": "次桃花，囚星，才情与规矩的张力",
    "天府": "库星稳健，包容持重，善守成",
    "太阴": "月亮柔情，细腻内敛，利女性长辈",
    "贪狼": "正桃花，多才多欲，交际力强",
    "巨门": "暗星口舌，善辩研究，宜专业立身",
    "天相": "印星辅佐，忠厚公正，重体面",
    "天梁": "荫星长辈，慈悲正直，善解厄",
    "七杀": "将星开创，果决肃杀，起伏大",
    "破军": "耗星变革，破旧立新，敢冲敢闯",
}


def _zhi_i(z):
    return ZHI.index(z)


def an_ziwei(ju, day):
    """由五行局数与农历生日定紫微星地支索引。"""
    if day % ju == 0:
        n = day // ju
        return (2 + n - 1) % 12
    n = day // ju + 1
    rem = n * ju - day
    if rem % 2 == 0:
        return (2 + n - 1 + rem) % 12
    return (2 + n - 1 - rem) % 12


def pai_pan(solar=None, lunar=None, leap=False, hour=None, shichen=None, sex="男",
            place=None, year=None):
    """返回紫微斗数命盘 dict。"""
    warnings = []
    if solar:
        y, m, d = solar
        ly, lm, ld, leap = solar_to_lunar(y, m, d)
    elif lunar:
        ly, lm, ld = lunar
        dt = lunar_to_solar(ly, lm, ld, leap)
        y, m, d = dt.year, dt.month, dt.day
    else:
        raise ValueError("必须提供 --solar 或 --lunar")

    if hour is not None:
        hh = hour if isinstance(hour, int) else hour[0]
    elif shichen is not None:
        # 时辰 → 该时辰的起始钟点（子=0、丑=2、寅=4……）
        # 原先写成 2 * (index - 1) % 24，子时算出 22 点又被单独兜回 0，
        # 其余时辰一律偏前一格。详见 bazi.py 同一处的说明。
        hh = 2 * ZHI.index(shichen) % 24
    else:
        hh = None
        warnings.append("未提供出生时刻，按子时（0点）排盘，结果可能偏差，请补全时辰。")

    hour_idx = 0 if hh is None else ((hh + 1) // 2) % 12
    if leap:
        warnings.append("生于闰月：本盘按「闰月归本月」处理（另有归下月流派），如需可注明。")

    # 1. 命宫 / 身宫（寅起正月，顺数至生月；再起子时逆数至生时）
    month = lm
    ming_idx = (2 + (month - 1) - hour_idx) % 12
    shen_idx = (2 + (month - 1) + hour_idx) % 12

    # 2. 年干支（紫微用农历年，正月初一分界）
    year_gan = GAN[(ly - 4) % 10]
    year_zhi = ZHI[(ly - 4) % 12]

    # 3. 宫位天干（五虎遁）
    yg = GAN.index(year_gan)
    def gong_gan(zhi_i):
        # 同 almanac.month_gz：地支偏移用 %12，避免子/丑宫因负数取模出错
        return GAN[(YUE_GAN_YIN[yg] + (zhi_i - 2) % 12) % 10]

    ming_gan = gong_gan(ming_idx)
    # 4. 五行局（命宫纳音）
    ju_wx = nayin_wuxing(ming_gan, ZHI[ming_idx])
    ju = JU_TABLE[ju_wx]

    # 5. 安紫微
    ziwei_idx = an_ziwei(ju, ld)
    tianfu_idx = (4 - ziwei_idx) % 12

    stars = {i: [] for i in range(12)}  # 地支索引 → [星名]
    def put_star(name, idx):
        stars[idx % 12].append(name)

    for name, off in ZIWEI_SERIES:
        put_star(name, ziwei_idx + off)
    for name, off in TIANFU_SERIES:
        put_star(name, tianfu_idx + off)

    # 6. 辅星
    put_star("左辅", 4 + (month - 1))
    put_star("右弼", 10 - (month - 1))
    put_star("文昌", 10 - hour_idx)
    put_star("文曲", 4 + hour_idx)
    kui, yue = TIANKUI[year_gan]
    put_star("天魁", _zhi_i(kui))
    put_star("天钺", _zhi_i(yue))
    lu_i = _zhi_i(LUCUN[year_gan])
    put_star("禄存", lu_i)
    put_star("擎羊", lu_i + 1)
    put_star("陀罗", lu_i - 1)
    hx = _zhi_i(HUOXING_START[year_zhi])
    put_star("火星", hx + hour_idx)
    lx = _zhi_i(LINGXING_START[year_zhi])
    put_star("铃星", lx + hour_idx)
    put_star("地空", 11 - hour_idx)
    put_star("地劫", 11 + hour_idx)
    put_star("天马", _zhi_i(TIANMA[SANHE_JU[year_zhi]]))

    # 7. 四化
    hua = SIHUA[year_gan]
    hua_map = {}
    for star, kind in zip(hua, ("禄", "权", "科", "忌")):
        hua_map[star] = kind
        for i in range(12):
            if star in stars[i]:
                stars[i] = [s if s != star else s + "·化" + kind for s in stars[i]]

    # 8. 十二宫（从命宫起逆排）
    palaces = []
    for k in range(12):
        idx = (ming_idx - k) % 12
        palaces.append({
            "宫名": GONG_NAMES[k],
            "地支": ZHI[idx],
            "天干": gong_gan(idx),
            "星曜": sorted(stars[idx]),
            "主星": [s for s in stars[idx] if s.split("·")[0] in STAR_BRIEF],
            "是否命宫": k == 0,
            "是否身宫": idx == shen_idx,
        })

    # 9. 大限（起运=局数；阳男阴女顺行，阴男阳女逆行）
    yang_year = GAN_YINYANG[GAN.index(year_gan)] == "阳"
    forward = (yang_year and sex == "男") or ((not yang_year) and sex == "女")
    dayun = []
    for k in range(12):
        idx = (ming_idx + k) % 12 if forward else (ming_idx - k) % 12
        start_age = ju + k * 10
        dayun.append({
            "宫位": GONG_NAMES[0] if idx == ming_idx else palaces[(ming_idx - idx) % 12]["宫名"],
            "地支": ZHI[idx], "天干": gong_gan(idx),
            "虚岁起": start_age, "虚岁止": start_age + 9,
            "星曜": sorted(stars[idx]),
        })

    # 10. 流年（指定年或当前年）
    import datetime as _dt
    cur_year = int(year) if year else _dt.datetime.now().year
    ln_zhi_i = (cur_year - 4) % 12
    ln_gan = GAN[(cur_year - 4) % 10]
    ln_palaces = []
    for k in range(12):
        idx = (ln_zhi_i - k) % 12
        ln_palaces.append({
            "宫名": GONG_NAMES[k], "地支": ZHI[idx],
            "星曜": sorted(stars[idx]),
            "是否流年命宫": k == 0,
        })
    cur_age = cur_year - ly + 1
    cur_dayun = next((x for x in dayun if x["虚岁起"] <= cur_age <= x["虚岁止"]), None)

    return {
        "输入": {
            "公历": "%04d-%02d-%02d" % (y, m, d),
            "农历": format_lunar(ly, lm, ld, leap),
            "时辰": ZHI[hour_idx] + "时" if hh is not None else "子时(默认)",
            "性别": sex, "出生地": place or "未提供",
            "年干支": year_gan + year_zhi,
        },
        "命宫": {"地支": ZHI[ming_idx], "天干": ming_gan},
        "身宫": {"地支": ZHI[shen_idx], "天干": gong_gan(shen_idx)},
        "五行局": JU_NAME[ju],
        "紫微星": ZHI[ziwei_idx] + "宫",
        "天府星": ZHI[tianfu_idx] + "宫",
        "十二宫": palaces,
        "四化": {"年干": year_gan,
                 "化禄": hua[0], "化权": hua[1], "化科": hua[2], "化忌": hua[3]},
        "大限": {"顺逆": "顺行" if forward else "逆行", "起运虚岁": ju, "列表": dayun},
        "流年": {"年": cur_year, "干支": ln_gan + ZHI[ln_zhi_i], "虚岁": cur_age,
                 "流年命宫": ZHI[ln_zhi_i] + "宫",
                 "当前大限": (cur_dayun["宫位"] + "·" + cur_dayun["地支"] if cur_dayun else "")},
        "警告": warnings,
    }


def format_report(r):
    L = []
    L.append("=" * 52)
    L.append("  紫微斗数命盘")
    L.append("=" * 52)
    i = r["输入"]
    L.append("公历：%s  农历：%s" % (i["公历"], i["农历"]))
    L.append("时辰：%s  性别：%s  出生地：%s  年干支：%s"
             % (i["时辰"], i["性别"], i["出生地"], i["年干支"]))
    L.append("命宫：%s%s   身宫：%s%s   五行局：%s"
             % (r["命宫"]["天干"], r["命宫"]["地支"], r["身宫"]["天干"], r["身宫"]["地支"], r["五行局"]))
    L.append("紫微星：%s   天府星：%s" % (r["紫微星"], r["天府星"]))
    h = r["四化"]
    L.append("四化（%s干）：禄=%s 权=%s 科=%s 忌=%s" % (h["年干"], h["化禄"], h["化权"], h["化科"], h["化忌"]))
    L.append("")
    L.append("【十二宫】")
    for p in r["十二宫"]:
        tag = []
        if p["是否命宫"]:
            tag.append("命")
        if p["是否身宫"]:
            tag.append("身")
        star_s = " ".join(p["星曜"]) if p["星曜"] else "（空宫）"
        L.append("  %s%s%s %-4s %s" % (p["宫名"], ("[" + "/".join(tag) + "]") if tag else "",
                                       "", p["天干"] + p["地支"], star_s))
    L.append("")
    d = r["大限"]
    L.append("【大限】%s，起运虚岁 %d" % (d["顺逆"], d["起运虚岁"]))
    for x in d["列表"]:
        L.append("  虚岁%2d-%2d  %s%s  %s  %s"
                 % (x["虚岁起"], x["虚岁止"], x["天干"], x["地支"], x["宫位"], " ".join(x["星曜"])))
    ln = r["流年"]
    L.append("")
    L.append("【流年】%d %s 虚岁%d 流年命宫%s 当前大限%s"
             % (ln["年"], ln["干支"], ln["虚岁"], ln["流年命宫"], ln["当前大限"]))
    if r["警告"]:
        L.append("")
        for w in r["警告"]:
            L.append("  ⚠ " + w)
    L.append("")
    L.append("提示：命理分析仅供文化研究与娱乐参考，人生在于自身的努力和选择。")
    return "\n".join(L)


def parse_date(text):
    parts = text.strip().replace("/", "-").replace(".", "-").split("-")
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("日期请按 1990-05-15 这样的格式填写（年-月-日）")
    return tuple(int(x) for x in parts)


def main(argv=None):
    setup_console()
    p = argparse.ArgumentParser(description="紫微斗数排盘 —— 输入生日，排出紫微命盘")
    p.add_argument("--solar", type=parse_date)
    p.add_argument("--lunar", type=parse_date)
    p.add_argument("--leap", action="store_true")
    p.add_argument("--hour", type=int, help="出生是几点（0-23），例如 12")
    p.add_argument("--shichen", choices=list(ZHI))
    p.add_argument("--sex", required=True, choices=("男", "女"))
    p.add_argument("--place", default=None)
    p.add_argument("--year", type=int, default=None, help="想看哪一年的运势，例如 2027")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    if not a.solar and not a.lunar:
        p.error("请至少填一个生日：阳历用 --solar，农历用 --lunar")
    r = pai_pan(solar=a.solar, lunar=a.lunar, leap=a.leap, hour=a.hour,
                shichen=a.shichen, sex=a.sex, place=a.place, year=a.year)
    print(json.dumps(r, ensure_ascii=False, indent=2) if a.json else format_report(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())

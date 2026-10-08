#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""四柱八字排盘引擎（零第三方依赖，仅标准库）。

铁律：四柱 / 大运 / 流年 / 神煞一律以本模块计算结果为准，
语言模型不得口算、不得凭记忆中的万年历改写。

用法
----
python bazi.py --solar 1990-05-15 --hour 12:00 --sex 男 [--place 北京] [--lon 116.4]
python bazi.py --lunar 1990-04-21 --shichen 午 --sex 男
python bazi.py --solar 1990-05-15 --hour 12:00 --sex 男 --json
"""

import argparse
import json
import sys
from datetime import timedelta

from almanac import (
    GAN, ZHI, GAN_WUXING, ZHI_WUXING, GAN_YINYANG, ZHI_CANGGAN,
    beijing, day_gz_index, month_gz, year_gz, year_gz_index, hour_gz, shichen_of,
    gz_from_index, ganzhi_hour_label, jie_events_around, solar_to_lunar,
    lunar_to_solar, format_lunar, true_solar_time, nayin_of, setup_console, fsum,
)

WUXING = "木火土金水"

# 六十甲子纳音（每两个干支一组，共 30 组）
NAYIN = [
    "海中金", "炉中火", "大林木", "路旁土", "剑锋金", "山头火",
    "涧下水", "城头土", "白蜡金", "杨柳木", "泉中水", "屋上土",
    "霹雳火", "松柏木", "长流水", "沙中金", "山下火", "平地木",
    "壁上土", "金箔金", "覆灯火", "天河水", "大驿土", "钗钏金",
    "桑柘木", "大溪水", "沙中土", "天上火", "石榴木", "大海水",
]

# 地支藏干力量权重（本气 / 中气 / 余气）
CANG_WEIGHT = (1.0, 0.4, 0.2)
# 地支位置权重：月支最重，日支次之
ZHI_POS_WEIGHT = {"年": 1.0, "月": 1.8, "日": 1.4, "时": 1.0}
GAN_POS_WEIGHT = {"年": 1.0, "月": 1.2, "日": 0.0, "时": 1.0}  # 日干是「我」，不计入同异党

# 神煞基础表
TIANYI = {  # 天乙贵人（日干或年干查地支）
    "甲": "丑未", "戊": "丑未", "庚": "丑未", "乙": "子申", "己": "子申",
    "丙": "亥酉", "丁": "亥酉", "壬": "卯巳", "癸": "卯巳", "辛": "午寅",
}
WENCHANG = {"甲": "巳", "乙": "午", "丙": "申", "丁": "酉", "戊": "申",
            "己": "酉", "庚": "亥", "辛": "子", "壬": "寅", "癸": "卯"}
XUETANG = {"甲": "亥", "乙": "午", "丙": "寅", "丁": "酉", "戊": "寅",
           "己": "酉", "庚": "巳", "辛": "子", "壬": "申", "癸": "卯"}
LUSHEN = {"甲": "寅", "乙": "卯", "丙": "巳", "丁": "午", "戊": "巳",
          "己": "午", "庚": "申", "辛": "酉", "壬": "亥", "癸": "子"}
YANGREN = {"甲": "卯", "乙": "寅", "丙": "午", "丁": "巳", "戊": "午",
           "己": "巳", "庚": "酉", "辛": "子", "壬": "子", "癸": "亥"}
GUOYIN = {"甲": "戌", "乙": "亥", "丙": "丑", "丁": "寅", "戊": "丑",
          "己": "寅", "庚": "辰", "辛": "巳", "壬": "未", "癸": "申"}
JINYU = {"甲": "辰", "乙": "巳", "丙": "未", "丁": "申", "戊": "未",
         "己": "申", "庚": "戌", "辛": "亥", "壬": "丑", "癸": "寅"}
HONGYAN = {"甲": "午", "乙": "午", "丙": "寅", "丁": "未", "戊": "辰",
           "己": "辰", "庚": "戌", "辛": "酉", "壬": "子", "癸": "申"}
TIANYI_MED = {"甲": "卯", "乙": "亥", "丙": "子", "丁": "酉", "戊": "午",
              "己": "酉", "庚": "亥", "辛": "巳", "壬": "寅", "癸": "亥"}

TIANDE = {"寅": ("干", "丁"), "卯": ("支", "申"), "辰": ("干", "壬"), "巳": ("干", "辛"),
          "午": ("支", "亥"), "未": ("干", "甲"), "申": ("干", "癸"), "酉": ("支", "寅"),
          "戌": ("干", "丙"), "亥": ("干", "乙"), "子": ("干", "己"), "丑": ("干", "庚")}
YUEDE = {"寅": "丙", "午": "丙", "戌": "丙", "申": "壬", "子": "壬", "辰": "壬",
         "亥": "甲", "卯": "甲", "未": "甲", "巳": "庚", "酉": "庚", "丑": "庚"}

# 三合局：年支 → 局
SANHE = {"申": "水", "子": "水", "辰": "水", "寅": "火", "午": "火", "戌": "火",
         "巳": "金", "酉": "金", "丑": "金", "亥": "木", "卯": "木", "未": "木"}
YIMA = {"水": "寅", "火": "申", "金": "亥", "木": "巳"}
TAOHUA = {"水": "酉", "火": "卯", "金": "午", "木": "子"}
HUAGAI = {"水": "辰", "火": "戌", "金": "丑", "木": "未"}
JIANGXING = {"水": "子", "火": "午", "金": "酉", "木": "卯"}
JIESHA = {"水": "巳", "火": "亥", "金": "寅", "木": "申"}
WANGSHEN = {"水": "亥", "火": "巳", "金": "申", "木": "寅"}
ZAISHA = {"水": "午", "火": "子", "金": "卯", "木": "酉"}
WANGSHEN_X = {"水": "亥", "火": "巳", "金": "申", "木": "寅"}
GUCHEN = {"亥": "寅", "子": "寅", "丑": "寅", "寅": "巳", "卯": "巳", "辰": "巳",
          "巳": "申", "午": "申", "未": "申", "申": "亥", "酉": "亥", "戌": "亥"}
GUASU = {"亥": "戌", "子": "戌", "丑": "戌", "寅": "丑", "卯": "丑", "辰": "丑",
         "巳": "辰", "午": "辰", "未": "辰", "申": "未", "酉": "未", "戌": "未"}
TIANYI_ZHUSHI = {"子": "亥", "丑": "亥", "寅": "丑", "卯": "寅", "辰": "卯", "巳": "辰",
                 "午": "巳", "未": "午", "申": "未", "酉": "申", "戌": "酉", "亥": "戌"}


# ---------------------------------------------------------------------------
# 五行 / 十神
# ---------------------------------------------------------------------------

def wuxing_of_gan(gan):
    return GAN_WUXING[GAN.index(gan)]


def wuxing_of_zhi(zhi):
    return ZHI_WUXING[ZHI.index(zhi)]


def shishen(day_gan, other_gan):
    """以日干为「我」，求 other_gan 的十神。"""
    me = WUXING.index(wuxing_of_gan(day_gan))
    me_yy = GAN_YINYANG[GAN.index(day_gan)] == "阳"
    oth = WUXING.index(wuxing_of_gan(other_gan))
    oth_yy = GAN_YINYANG[GAN.index(other_gan)] == "阳"
    same = (me_yy == oth_yy)
    rel = (oth - me) % 5
    if rel == 0:
        return "比肩" if same else "劫财"
    if rel == 1:  # 我生
        return "食神" if same else "伤官"
    if rel == 2:  # 我克
        return "偏财" if same else "正财"
    if rel == 3:  # 克我
        return "七杀" if same else "正官"
    return "偏印" if same else "正印"  # 生我


def kongwang(day_gan_zhi_idx):
    """旬空（以日柱查）。"""
    xun = day_gan_zhi_idx // 10
    return ZHI[(10 - xun * 2) % 12] + ZHI[(11 - xun * 2) % 12]


def nayin(gan, zhi):
    """纳音名，如 庚辰 → 白蜡金（委托 almanac 统一实现）。"""
    return nayin_of(gan, zhi)


# ---------------------------------------------------------------------------
# 排盘主流程
# ---------------------------------------------------------------------------

def pai_pan(solar=None, lunar=None, leap=False, hour=None, shichen=None, sex="男",
            place=None, longitude=None, deceased_year=None, now=None):
    """返回完整八字排盘 dict。

    solar: (y, m, d) 阳历；lunar: (y, m, d, leap) 农历；hour: (h, min) 或 None；
    shichen: 地支字 或 None；sex: '男'/'女'。
    """
    warnings = []
    # 1. 定公历日期
    if solar:
        y, m, d = solar
        birth_date = beijing(y, m, d)
        lunar_info = solar_to_lunar(y, m, d)
    elif lunar:
        ly, lm, ld = lunar
        dt = lunar_to_solar(ly, lm, ld, leap)
        birth_date = beijing(dt.year, dt.month, dt.day)
        lunar_info = (ly, lm, ld, leap)
        y, m, d = dt.year, dt.month, dt.day
    else:
        raise ValueError("必须提供 --solar 或 --lunar")

    # 2. 定时辰
    if hour is not None:
        hh, mm = hour
    elif shichen is not None:
        # 时辰 → 该时辰的**起始钟点**：子=0点、丑=2点、寅=4点……
        #
        # 这里原先写的是 2 * (ZHI.index(shichen) - 1) % 24，那是错的：
        # 子时 index=0，算出 (0-1)*2 % 24 = 22 点，于是除被单独兜回 0 的子时外，
        # **每个时辰都被算成了前一个时辰**（丑时报子时、午时报巳时……）。
        # 结果是「知道大概时辰、不确定几点」这种最常见的用法整体偏一格，
        # 时柱、命宫、主星全错，而页面上完全看不出来。
        hh, mm = 2 * ZHI.index(shichen) % 24, 0
    else:
        hh = mm = None

    # 3. 真太阳时校正
    tst_note = None
    if hh is not None and longitude is not None:
        clock = beijing(y, m, d, hh, mm)
        tst, offset_min, eot = true_solar_time(clock, float(longitude))
        tst_note = {"钟表时": clock.strftime("%H:%M"), "真太阳时": tst.strftime("%H:%M"),
                    "校正分钟": round(offset_min, 1), "均时差分钟": round(eot, 1)}
        # 真太阳时跨时辰则提示
        z1, _ = shichen_of(hh, mm)
        z2, _ = shichen_of(tst.hour, tst.minute)
        if z1 != z2:
            warnings.append("真太阳时校正后由「%s时」跨到「%s时」，请以真太阳时为准并确认出生地经度。" % (z1, z2))
        hh, mm = tst.hour, tst.minute

    birth_dt = beijing(y, m, d, hh if hh is not None else 12, mm if mm is not None else 0)

    # 4. 四柱
    year_pillar, solar_year = year_gz(birth_dt)
    month_pillar, month_zhi, jie_name, jie_start = month_gz(birth_dt)
    if hh is None:
        day_idx = day_gz_index(y, m, d)
        day_pillar = gz_from_index(day_idx)
        hour_pillar = None
        warnings.append("未提供出生时刻，时柱未知，仅作六字（年月日）分析。")
    else:
        # 早晚子时：23:00 起用次日日柱
        if hh >= 23:
            nd = birth_date.date() + timedelta(days=1)
            day_idx = day_gz_index(nd.year, nd.month, nd.day)
            warnings.append("出生时刻在 23:00 之后，按「晚子时」用次日日柱。")
        else:
            day_idx = day_gz_index(y, m, d)
        day_pillar = gz_from_index(day_idx)
        zhi, zhi_i = shichen_of(hh, mm)
        hour_pillar = hour_gz(day_pillar[0], zhi_i)

    # 节气交界提示
    secs_to_jie = abs((birth_dt - jie_start).total_seconds())
    if secs_to_jie <= 6 * 3600:
        warnings.append("出生时刻距「%s」仅 %.1f 小时，处于节气交界，月柱对时刻高度敏感，请核对出生时间。" % (jie_name, secs_to_jie / 3600.0))
    lichun = jie_events_around(y)
    for ev in lichun:
        if ev[1] == "立春" and abs((birth_dt - ev[0]).total_seconds()) <= 6 * 3600:
            warnings.append("出生时刻距「立春」仅 %.1f 小时，年柱归属临界，请核对出生时间。" % (abs((birth_dt - ev[0]).total_seconds()) / 3600.0))

    pillars = [("年", year_pillar), ("月", month_pillar), ("日", day_pillar)]
    if hour_pillar:
        pillars.append(("时", hour_pillar))

    day_gan = day_pillar[0]

    # 5. 十神 / 藏干 / 纳音
    detail = []
    for pos, gz in pillars:
        g, z = gz[0], gz[1]
        cang = ZHI_CANGGAN[z]
        detail.append({
            "柱": pos,
            "干": g, "支": z,
            "干十神": "日主" if pos == "日" else shishen(day_gan, g),
            "支藏干": [{"干": c, "十神": shishen(day_gan, c)} for c in cang],
            "纳音": nayin(g, z),
            "五行": wuxing_of_gan(g) + wuxing_of_zhi(z),
        })

    # 6. 五行力量统计
    score = {w: 0.0 for w in WUXING}
    for pos, gz in pillars:
        g, z = gz[0], gz[1]
        score[wuxing_of_gan(g)] += GAN_POS_WEIGHT[pos]
        for i, c in enumerate(ZHI_CANGGAN[z]):
            w = CANG_WEIGHT[i] * ZHI_POS_WEIGHT[pos]
            score[wuxing_of_gan(c)] += w
    total = fsum(score.values()) or 1.0
    wuxing_pct = {w: round(v / total * 100, 1) for w, v in score.items()}

    # 7. 日主强弱（同党=印+比劫；异党=食伤+财+官杀）
    me_wx = wuxing_of_gan(day_gan)
    me_i = WUXING.index(me_wx)
    sheng_me = WUXING[(me_i + 4) % 5]   # 生我者（印）
    tongdang = score[me_wx] + score[sheng_me]
    ratio = tongdang / total
    if ratio >= 0.62:
        strength = "身强"
    elif ratio >= 0.55:
        strength = "偏强"
    elif ratio >= 0.45:
        strength = "中和"
    elif ratio >= 0.38:
        strength = "偏弱"
    else:
        strength = "身弱"
    # 喜忌（简化：身强喜克泄耗，身弱喜生扶）
    if ratio >= 0.5:
        xiyong = [WUXING[(me_i + 1) % 5], WUXING[(me_i + 2) % 5], WUXING[(me_i + 3) % 5]]
    else:
        xiyong = [me_wx, sheng_me]

    # 8. 格局（以月支本气十神取格）
    month_main = ZHI_CANGGAN[month_zhi][0]
    geju_ss = shishen(day_gan, month_main)
    geju = geju_ss + "格" if geju_ss not in ("比肩", "劫财") else "建禄/月劫格"
    # 透干检查
    tou = [p[1][0] for p in pillars if p[0] != "日"]
    geju_tou = shishen(day_gan, month_main) in [shishen(day_gan, t) for t in tou]

    # 9. 神煞
    year_zhi = pillars[0][1][1]
    ju = SANHE[year_zhi]
    all_zhi = [p[1][1] for p in pillars]
    shensha = []

    def hit(name, target, basis, note=""):
        found = [pos for pos, gz in pillars if gz[1] == target]
        if found:
            shensha.append({"神煞": name, "查法": basis, "落支": target, "位置": "、".join(found) + "柱", "说明": note})

    for g in (day_gan, pillars[0][1][0]):
        for z in TIANYI[g]:
            hit("天乙贵人", z, "日/年干" + g, "贵人助力、逢凶化吉")
    for z in WENCHANG[day_gan]:
        hit("文昌贵人", z, "日干" + day_gan, "聪颖好学、利文书考试")
    for z in XUETANG[day_gan]:
        hit("学堂", z, "日干" + day_gan, "学业有成、宜求学")
    for z in LUSHEN[day_gan]:
        hit("禄神", z, "日干" + day_gan, "衣食丰足、有独立之财")
    for z in YANGREN[day_gan]:
        hit("羊刃", z, "日干" + day_gan, "刚烈果决，宜防冲动")
    for z in GUOYIN[day_gan]:
        hit("国印贵人", z, "日干" + day_gan, "掌权柄、利公职")
    for z in JINYU[day_gan]:
        hit("金舆", z, "日干" + day_gan, "配偶贤、有车马之福")
    for z in HONGYAN[day_gan]:
        hit("红艳煞", z, "日干" + day_gan, "多情浪漫、异性缘旺")
    hit("驿马", YIMA[ju], "年支三合" + ju + "局", "奔波变动、宜外出发展")
    hit("桃花（咸池）", TAOHUA[ju], "年支三合" + ju + "局", "异性缘、人缘魅力")
    hit("华盖", HUAGAI[ju], "年支三合" + ju + "局", "孤高清雅、有宗教艺术缘")
    hit("将星", JIANGXING[ju], "年支三合" + ju + "局", "领导统御、掌权")
    hit("劫煞", JIESHA[ju], "年支三合" + ju + "局", "宜防破耗、竞争")
    hit("亡神", WANGSHEN[ju], "年支三合" + ju + "局", "心思深沉、宜防口舌")
    hit("灾煞", ZAISHA[ju], "年支三合" + ju + "局", "宜防意外")
    hit("孤辰", GUCHEN[year_zhi], "年支" + year_zhi, "性喜独处")
    hit("寡宿", GUASU[year_zhi], "年支" + year_zhi, "情感上易孤独")
    # 天德月德
    td = TIANDE[month_zhi]
    if td[0] == "干" and td[1] in [p[1][0] for p in pillars]:
        shensha.append({"神煞": "天德贵人", "查法": "月支" + month_zhi, "落支": td[1], "位置": "天干", "说明": "福德深厚、遇难成祥"})
    elif td[0] == "支" and td[1] in all_zhi:
        shensha.append({"神煞": "天德贵人", "查法": "月支" + month_zhi, "落支": td[1], "位置": "地支", "说明": "福德深厚、遇难成祥"})
    yd = YUEDE[month_zhi]
    if yd in [p[1][0] for p in pillars]:
        shensha.append({"神煞": "月德贵人", "查法": "月支" + month_zhi, "落支": yd, "位置": "天干", "说明": "慈祥厚德、贵人相扶"})

    kw = kongwang(day_idx)

    # 10. 大运
    y_gan = year_pillar[0]
    yang_year = GAN_YINYANG[GAN.index(y_gan)] == "阳"
    forward = (yang_year and sex == "男") or ((not yang_year) and sex == "女")
    # 起运：到最近节的天数 / 3
    events = list(jie_events_around(birth_dt.year))
    if forward:
        nxt = next((e for e in events if e[0] > birth_dt), events[-1])
        delta_days = (nxt[0] - birth_dt).total_seconds() / 86400.0
    else:
        prv = None
        for e in events:
            if e[0] <= birth_dt:
                prv = e
            else:
                break
        prv = prv or events[0]
        delta_days = (birth_dt - prv[0]).total_seconds() / 86400.0
    qiyun_years_f = delta_days / 3.0
    qy = int(qiyun_years_f)
    qm = int(round((qiyun_years_f - qy) * 12))
    if qm >= 12:
        qy += 1
        qm -= 12
    # 月柱序号
    m_idx = None
    for n in range(60):
        if GAN[n % 10] == month_pillar[0] and ZHI[n % 12] == month_pillar[1]:
            m_idx = n
            break
    dayun = []
    start_age = qiyun_years_f
    for step in range(1, 11):
        idx = (m_idx + step) % 60 if forward else (m_idx - step) % 60
        gz = gz_from_index(idx)
        a0 = start_age + (step - 1) * 10
        a1 = a0 + 10
        dayun.append({
            "序": step, "干支": gz,
            "十神": shishen(day_gan, gz[0]),
            "起始虚岁": round(a0, 1), "结束虚岁": round(a1, 1),
            "起始公历": y + int(a0),
        })

    # 11. 流年（当前年 ±3，或到去世年）
    # `now` 参数原本被下面无条件取系统年份覆盖掉，是个形同虚设的参数：
    # 传什么都不起作用，也没法做可复现的测试（JS 侧对拍需要钉住年份）。
    # 现在显式尊重 now，只在未传时才取系统年份。
    if now is not None:
        cur_year = now.year
    else:
        try:
            from datetime import datetime as _dt
            cur_year = _dt.now().year
        except Exception:
            cur_year = 2026
    if deceased_year:
        cur_year = min(cur_year, int(deceased_year))
    liunian = []
    for yy in range(cur_year - 3, cur_year + 4):
        if deceased_year and yy > int(deceased_year):
            break
        gz = gz_from_index(year_gz_index(yy))
        age = yy - solar_year + 1
        liunian.append({"年": yy, "干支": gz, "十神": shishen(day_gan, gz[0]),
                        "虚岁": age,
                        "大运": next((d["干支"] for d in dayun if d["起始虚岁"] <= age - 1 < d["结束虚岁"]), "")})

    return {
        "输入": {
            "公历": "%04d-%02d-%02d" % (y, m, d),
            "农历": format_lunar(*lunar_info),
            "时辰": (hour_pillar[1] + "时(" + ganzhi_hour_label(hour_pillar[1]) + ")") if hour_pillar else "未知",
            "性别": sex,
            "出生地": place or "未提供",
            "真太阳时": tst_note,
        },
        "四柱": {"年": year_pillar, "月": month_pillar, "日": day_pillar, "时": hour_pillar or "未知"},
        "日主": {"干": day_gan, "五行": me_wx, "阴阳": GAN_YINYANG[GAN.index(day_gan)]},
        "柱详解": detail,
        "五行统计": wuxing_pct,
        "日主强弱": {"判定": strength, "同党占比": round(ratio * 100, 1), "喜用神": xiyong,
                     "说明": "同党=比劫+印星，占比越高日主越强"},
        "格局": {"名": geju, "月令本气": month_main, "是否透干": geju_tou},
        "旬空": kw,
        "神煞": shensha,
        "大运": {"顺逆": "顺排" if forward else "逆排", "起运": "%d年%d个月" % (qy, qm),
                 "起运虚岁": round(qiyun_years_f, 2), "列表": dayun},
        "流年": liunian,
        "警告": warnings,
        "当前时间": "%04d" % cur_year,
    }


def format_report(r):
    L = []
    L.append("=" * 46)
    L.append("  四柱八字排盘")
    L.append("=" * 46)
    i = r["输入"]
    L.append("公历：%s   农历：%s" % (i["公历"], i["农历"]))
    L.append("时辰：%s   性别：%s   出生地：%s" % (i["时辰"], i["性别"], i["出生地"]))
    if i["真太阳时"]:
        t = i["真太阳时"]
        L.append("真太阳时：%s（钟表 %s，校正 %s 分钟，均时差 %s 分钟）"
                 % (t["真太阳时"], t["钟表时"], t["校正分钟"], t["均时差分钟"]))
    L.append("")
    L.append("【四柱】")
    for pos, gz in [("年", r["四柱"]["年"]), ("月", r["四柱"]["月"]), ("日", r["四柱"]["日"]), ("时", r["四柱"]["时"])]:
        if gz == "未知":
            L.append("  %s柱：未知" % pos)
            continue
        d = next(x for x in r["柱详解"] if x["柱"] == pos)
        cang = " ".join("%s(%s)" % (c["干"], c["十神"]) for c in d["支藏干"])
        L.append("  %s柱：%s  %s  %s  [%s]  藏干：%s"
                 % (pos, gz, d["干十神"], d["纳音"], d["五行"], cang))
    L.append("")
    L.append("【日主】%s（%s，%s）" % (r["日主"]["干"], r["日主"]["五行"], r["日主"]["阴阳"]))
    s = r["日主强弱"]
    L.append("【强弱】%s（同党 %.1f%%，喜用神：%s）" % (s["判定"], s["同党占比"], "、".join(s["喜用神"])))
    L.append("【格局】%s%s" % (r["格局"]["名"], "（透干）" if r["格局"]["是否透干"] else ""))
    L.append("【旬空】%s" % r["旬空"])
    L.append("")
    L.append("【五行统计】")
    for w, p in r["五行统计"].items():
        bar = "█" * int(p / 4)
        L.append("  %s %5.1f%%  %s" % (w, p, bar))
    L.append("")
    L.append("【神煞】")
    if r["神煞"]:
        for x in r["神煞"]:
            L.append("  %s（%s，落%s，%s）：%s" % (x["神煞"], x["查法"], x["位置"], x["落支"], x["说明"]))
    else:
        L.append("  （无）")
    L.append("")
    d = r["大运"]
    L.append("【大运】%s，起运 %s（虚岁 %.1f）" % (d["顺逆"], d["起运"], d["起运虚岁"]))
    for x in d["列表"]:
        L.append("  %2d运 %s  %s  虚岁 %.0f-%.0f" % (x["序"], x["干支"], x["十神"], x["起始虚岁"], x["结束虚岁"]))
    L.append("")
    L.append("【流年】")
    for x in r["流年"]:
        L.append("  %d %s %s 虚岁%d %s" % (x["年"], x["干支"], x["十神"], x["虚岁"], ("运:" + x["大运"]) if x["大运"] else ""))
    if r["警告"]:
        L.append("")
        L.append("【警告】")
        for w in r["警告"]:
            L.append("  ⚠ " + w)
    L.append("")
    L.append("提示：命理分析仅供文化研究与娱乐参考，人生在于自身的努力和选择。")
    return "\n".join(L)


def parse_date(text):
    text = text.strip().replace("/", "-").replace(".", "-")
    parts = text.split("-")
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
    p = argparse.ArgumentParser(description="四柱八字排盘 —— 输入生日，算出你的八字命盘")
    p.add_argument("--solar", type=parse_date, help="阳历生日，例如 1990-05-15")
    p.add_argument("--lunar", type=parse_date, help="农历生日，例如 1990-04-21")
    p.add_argument("--leap", action="store_true", help="如果生日在闰月，加上这个开关")
    p.add_argument("--hour", type=parse_hour, help="出生时间，例如 12:00")
    p.add_argument("--shichen", choices=list(ZHI), help="出生时辰：子、丑、寅…（不知道几点就用这个）")
    p.add_argument("--sex", required=True, choices=("男", "女"))
    p.add_argument("--place", default=None, help="出生地，例如 北京")
    p.add_argument("--lon", type=float, default=None, help="出生地经度，例如 116.4（填了会自动做真太阳时校正）")
    p.add_argument("--deceased-year", type=int, default=None, help="如果人已过世，填去世年份，运势只算到那一年")
    p.add_argument("--json", action="store_true", help="输出给程序看的原始数据")
    a = p.parse_args(argv)
    if not a.solar and not a.lunar:
        p.error("请至少填一个生日：阳历用 --solar，农历用 --lunar")
    r = pai_pan(solar=a.solar, lunar=a.lunar, leap=a.leap, hour=a.hour, shichen=a.shichen,
                sex=a.sex, place=a.place, longitude=a.lon, deceased_year=a.deceased_year)
    print(json.dumps(r, ensure_ascii=False, indent=2) if a.json else format_report(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())

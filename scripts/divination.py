#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""六爻 / 梅花易数 起卦与装卦引擎（零第三方依赖，仅标准库）。

支持三种起卦法：
  1. 时间起卦（梅花易数，以农历年月日时数取卦）
  2. 数字起卦（报数）
  3. 摇卦（三枚铜钱六次，随机或指定）

装卦：八宫归属、纳甲地支、六亲、世应、六神、动爻变卦。
铁律：卦象与装卦一律以本模块为准，语言模型不得自行起卦。

用法
----
python divination.py --time --solar 1990-05-15 --hour 12:00
python divination.py --numbers 7 15
python divination.py --toss
"""

import argparse
import json
import random
import sys

from almanac import GAN, ZHI, ZHI_WUXING, solar_to_lunar, format_lunar

# 摇卦用系统 CSPRNG（random.SystemRandom 自 Python 2.6 起可用，不依赖 3.6+ 的 secrets）
_RNG = random.SystemRandom()

# 八卦：先天数 1-8 → (名, 自然, 五行, 三爻(初,二,三) 阳=1)
BAGUA = {
    1: ("乾", "天", "金", (1, 1, 1)),
    2: ("兑", "泽", "金", (1, 1, 0)),
    3: ("离", "火", "火", (1, 0, 1)),
    4: ("震", "雷", "木", (1, 0, 0)),
    5: ("巽", "风", "木", (0, 1, 1)),
    6: ("坎", "水", "水", (0, 1, 0)),
    7: ("艮", "山", "土", (0, 0, 1)),
    8: ("坤", "地", "土", (0, 0, 0)),
}
NAME2NUM = {v[0]: k for k, v in BAGUA.items()}

# 64 卦名表：[(上卦, 下卦)] → 卦名
GUA64 = {
    ("乾", "乾"): "乾为天", ("乾", "兑"): "天泽履", ("乾", "离"): "天火同人", ("乾", "震"): "天雷无妄",
    ("乾", "巽"): "天风姤", ("乾", "坎"): "天水讼", ("乾", "艮"): "天山遁", ("乾", "坤"): "天地否",
    ("兑", "乾"): "泽天夬", ("兑", "兑"): "兑为泽", ("兑", "离"): "泽火革", ("兑", "震"): "泽雷随",
    ("兑", "巽"): "泽风大过", ("兑", "坎"): "泽水困", ("兑", "艮"): "泽山咸", ("兑", "坤"): "泽地萃",
    ("离", "乾"): "火天大有", ("离", "兑"): "火泽睽", ("离", "离"): "离为火", ("离", "震"): "火雷噬嗑",
    ("离", "巽"): "火风鼎", ("离", "坎"): "火水未济", ("离", "艮"): "火山旅", ("离", "坤"): "火地晋",
    ("震", "乾"): "雷天大壮", ("震", "兑"): "雷泽归妹", ("震", "离"): "雷火丰", ("震", "震"): "震为雷",
    ("震", "巽"): "雷风恒", ("震", "坎"): "雷水解", ("震", "艮"): "雷山小过", ("震", "坤"): "雷地豫",
    ("巽", "乾"): "风天小畜", ("巽", "兑"): "风泽中孚", ("巽", "离"): "风火家人", ("巽", "震"): "风雷益",
    ("巽", "巽"): "巽为风", ("巽", "坎"): "风水涣", ("巽", "艮"): "风山渐", ("巽", "坤"): "风地观",
    ("坎", "乾"): "水天需", ("坎", "兑"): "水泽节", ("坎", "离"): "水火既济", ("坎", "震"): "水雷屯",
    ("坎", "巽"): "水风井", ("坎", "坎"): "坎为水", ("坎", "艮"): "水山蹇", ("坎", "坤"): "水地比",
    ("艮", "乾"): "山天大畜", ("艮", "兑"): "山泽损", ("艮", "离"): "山火贲", ("艮", "震"): "山雷颐",
    ("艮", "巽"): "山风蛊", ("艮", "坎"): "山水蒙", ("艮", "艮"): "艮为山", ("艮", "坤"): "山地剥",
    ("坤", "乾"): "地天泰", ("坤", "兑"): "地泽临", ("坤", "离"): "地火明夷", ("坤", "震"): "地雷复",
    ("坤", "巽"): "地风升", ("坤", "坎"): "地水师", ("坤", "艮"): "地山谦", ("坤", "坤"): "坤为地",
}

# 八宫卦序（用于定宫、世应）
GONG_ORDER = {
    "乾": ["乾为天", "天风姤", "天山遁", "天地否", "风地观", "山地剥", "火地晋", "火天大有"],
    "坎": ["坎为水", "水泽节", "水雷屯", "水火既济", "泽火革", "雷火丰", "地火明夷", "地水师"],
    "艮": ["艮为山", "山火贲", "山天大畜", "山泽损", "火泽睽", "天泽履", "风泽中孚", "风山渐"],
    "震": ["震为雷", "雷地豫", "雷水解", "雷风恒", "地风升", "水风井", "泽风大过", "泽雷随"],
    "巽": ["巽为风", "风天小畜", "风火家人", "风雷益", "天雷无妄", "火雷噬嗑", "山雷颐", "山风蛊"],
    "离": ["离为火", "火山旅", "火风鼎", "火水未济", "山水蒙", "风水涣", "天水讼", "天火同人"],
    "坤": ["坤为地", "地雷复", "地泽临", "地天泰", "雷天大壮", "泽天夬", "水天需", "水地比"],
    "兑": ["兑为泽", "泽水困", "泽地萃", "泽山咸", "水山蹇", "地山谦", "雷山小过", "雷泽归妹"],
}
# 八宫各卦的世爻位置（1-6）
SHI_POS = [6, 1, 2, 3, 4, 5, 4, 3]
GONG_WUXING = {"乾": "金", "兑": "金", "离": "火", "震": "木",
               "巽": "木", "坎": "水", "艮": "土", "坤": "土"}

# 纳甲：卦 → (内卦天干, 内卦地支[初,二,三], 外卦天干, 外卦地支[四,五,六])
NAJIA = {
    "乾": ("甲", ("子", "寅", "辰"), "壬", ("午", "申", "戌")),
    "坎": ("戊", ("寅", "辰", "午"), "戊", ("申", "戌", "子")),
    "艮": ("丙", ("辰", "午", "申"), "丙", ("戌", "子", "寅")),
    "震": ("庚", ("子", "寅", "辰"), "庚", ("午", "申", "戌")),
    "巽": ("辛", ("丑", "亥", "酉"), "辛", ("未", "巳", "卯")),
    "离": ("己", ("卯", "丑", "亥"), "己", ("酉", "未", "巳")),
    "坤": ("乙", ("未", "巳", "卯"), "癸", ("丑", "亥", "酉")),
    "兑": ("丁", ("巳", "卯", "丑"), "丁", ("亥", "酉", "未")),
}

LIUSHEN = ("青龙", "朱雀", "勾陈", "腾蛇", "白虎", "玄武")
# 日干 → 初爻六神：甲乙青龙、丙丁朱雀、戊勾陈、己腾蛇、庚辛白虎、壬癸玄武
LIUSHEN_START = {0: 0, 1: 0, 2: 1, 3: 1, 4: 2, 5: 3, 6: 4, 7: 4, 8: 5, 9: 5}

WUXING_SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
WUXING_KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}

YAO_SYMBOL = {1: "▅▅▅▅▅", 0: "▅▅  ▅▅"}


def yao_to_bagua(yaos):
    """三爻(初,二,三) → 八卦数。"""
    v = 4 * yaos[0] + 2 * yaos[1] + 1 * yaos[2]
    return {7: 1, 6: 2, 5: 3, 4: 4, 3: 5, 2: 6, 1: 7, 0: 8}[v]


def liuqin(gong_wx, yao_wx):
    if gong_wx == yao_wx:
        return "兄弟"
    if WUXING_SHENG[gong_wx] == yao_wx:
        return "子孙"
    if WUXING_SHENG[yao_wx] == gong_wx:
        return "父母"
    if WUXING_KE[gong_wx] == yao_wx:
        return "妻财"
    return "官鬼"


def gua_info(yaos):
    """六爻列表(初→上) → 卦信息 dict。"""
    lower = yao_to_bagua(yaos[0:3])
    upper = yao_to_bagua(yaos[3:6])
    ln, un = BAGUA[lower][0], BAGUA[upper][0]
    name = GUA64[(un, ln)]
    gong, shi = None, None
    for g, lst in GONG_ORDER.items():
        if name in lst:
            gong = g
            shi = SHI_POS[lst.index(name)]
            break
    ying = ((shi + 2) % 6) + 1  # 世爻对面（相隔三位）
    gong_wx = GONG_WUXING[gong]

    # 纳甲装爻
    nlb = NAJIA[ln]
    nu = NAJIA[un]
    yao_detail = []
    for i in range(6):
        if i < 3:
            gan, zhi = nlb[0], nlb[1][i]
        else:
            gan, zhi = nu[2], nu[3][i - 3]
        wx = ZHI_WUXING[ZHI.index(zhi)]
        yao_detail.append({
            "爻位": i + 1,
            "爻名": ("初", "二", "三", "四", "五", "上")[i],
            "阴阳": "阳" if yaos[i] else "阴",
            "符号": YAO_SYMBOL[yaos[i]],
            "纳甲": gan + zhi,
            "地支": zhi,
            "五行": wx,
            "六亲": liuqin(gong_wx, wx),
            "世应": "世" if i + 1 == shi else ("应" if i + 1 == ying else ""),
        })
    return {
        "卦名": name, "上卦": un, "下卦": ln, "宫": gong, "宫五行": gong_wx,
        "世爻": shi, "应爻": ying, "爻": yao_detail,
        "六十四卦序": None,
    }


def hexagram_lines(info):
    """六爻文本图（上爻在上）。"""
    out = []
    for y in reversed(info["爻"]):
        mark = ("【" + y["世应"] + "】") if y["世应"] else "    "
        out.append("  %s%s %-2s %s %-3s %-2s %s"
                   % (y["符号"], "", y["爻名"], y["纳甲"], y["六亲"], mark, y["地支"] + y["五行"]))
    return out


def cast_by_numbers(n1, n2, n3=None):
    """数字起卦：n1 上卦，n2 下卦，n3（或 n1+n2）动爻。返回本卦六爻与动爻。"""
    up = n1 % 8 or 8
    low = n2 % 8 or 8
    mov = ((n3 if n3 is not None else n1 + n2) % 6) or 6
    yaos = [0] * 6
    yaos[0:3] = list(BAGUA[low][3])
    yaos[3:6] = list(BAGUA[up][3])
    return yaos, mov


def cast_by_time(year_zhi_idx, month, day, hour_zhi_idx):
    """时间起卦（梅花易数）：以农历年支序数、月、日、时支序数。返回本卦六爻与动爻。"""
    s = year_zhi_idx + month + day
    up = s % 8 or 8
    s2 = s + hour_zhi_idx
    low = s2 % 8 or 8
    mov = s2 % 6 or 6
    yaos = [0] * 6
    yaos[0:3] = list(BAGUA[low][3])
    yaos[3:6] = list(BAGUA[up][3])
    return yaos, mov


def cast_by_toss():
    """摇卦：三枚铜钱六次。返回六爻(初→上) 与动爻列表。"""
    yaos = []
    mov = []
    for i in range(6):
        coins = [_RNG.randint(0, 1) for _ in range(3)]  # 1=字(阳), 0=背(阴)
        n = sum(coins)
        if n == 3:      # 三字：老阳（动）
            yaos.append(1)
            mov.append(i + 1)
        elif n == 0:    # 三背：老阴（动）
            yaos.append(0)
            mov.append(i + 1)
        elif n == 2:    # 两字一背：少阴
            yaos.append(0)
        else:           # 一字两背：少阳
            yaos.append(1)
    return yaos, mov


def divinate(method="time", solar=None, lunar=None, leap=False, hour=None, numbers=None,
             sex="男", question=None):
    warnings = []
    if method == "time":
        if solar:
            y, m, d = solar
            ly, lm, ld, leap = solar_to_lunar(y, m, d)
        elif lunar:
            ly, lm, ld = lunar
            from almanac import lunar_to_solar
            dt = lunar_to_solar(ly, lm, ld, leap)
            y, m, d = dt.year, dt.month, dt.day
        else:
            raise ValueError("时间起卦需提供 --solar 或 --lunar")
        hh = hour if isinstance(hour, int) else (hour[0] if hour else 12)
        year_zhi_idx = ((ly - 4) % 12) + 1      # 子=1
        hour_zhi_idx = ((hh + 1) // 2) % 12 + 1
        yaos, mov = cast_by_time(year_zhi_idx, lm, ld, hour_zhi_idx)
        from almanac import day_gz
        day_gan = day_gz(y, m, d)[0]
        basis = {"方式": "时间起卦（梅花易数）", "农历": format_lunar(ly, lm, ld, leap),
                 "年支序": year_zhi_idx, "月": lm, "日": ld, "时支序": hour_zhi_idx}
    elif method == "numbers":
        n = list(numbers or [])
        if len(n) < 2:
            raise ValueError("数字起卦至少需要两个数")
        yaos, mov = cast_by_numbers(n[0], n[1], n[2] if len(n) > 2 else None)
        from almanac import day_gz
        import datetime as _dt
        t = _dt.date.today()
        day_gan = day_gz(t.year, t.month, t.day)[0]
        basis = {"方式": "数字起卦", "数字": n}
    else:  # toss
        yaos, mov = cast_by_toss()
        from almanac import day_gz
        import datetime as _dt
        t = _dt.date.today()
        day_gan = day_gz(t.year, t.month, t.day)[0]
        basis = {"方式": "摇卦（三枚铜钱六次）"}

    ben = gua_info(yaos)
    mov_list = mov if isinstance(mov, list) else [mov]
    bian_yaos = list(yaos)
    for p in mov_list:
        bian_yaos[p - 1] ^= 1
    bian = gua_info(bian_yaos) if mov_list else None

    # 六神（按日干起初爻）
    ls0 = LIUSHEN_START[GAN.index(day_gan)]
    for i, y in enumerate(ben["爻"]):
        y["六神"] = LIUSHEN[(ls0 + i) % 6]

    return {
        "起卦": basis,
        "本卦": ben,
        "变卦": bian,
        "动爻": mov_list,
        "日干": day_gan,
        "提示": "卦象与装卦由脚本确定性生成；吉凶断语须结合所问之事（用神）分析。",
        "警告": warnings,
    }


def format_report(r):
    L = []
    L.append("=" * 46)
    L.append("  六爻占卜")
    L.append("=" * 46)
    b = r["起卦"]
    L.append("起卦方式：%s" % b["方式"])
    if "农历" in b:
        L.append("农历：%s  年支序%d 月%d 日%d 时支序%d"
                 % (b["农历"], b["年支序"], b["月"], b["日"], b["时支序"]))
    if "数字" in b:
        L.append("数字：%s" % b["数字"])
    L.append("日干：%s（定六神）" % r["日干"])
    L.append("")
    ben = r["本卦"]
    L.append("【本卦】%s（%s宫，世%d爻应%d爻）" % (ben["卦名"], ben["宫"], ben["世爻"], ben["应爻"]))
    for line in hexagram_lines(ben):
        L.append(line)
    L.append("  爻位:  %s" % "  ".join("%s" % y["爻名"] for y in ben["爻"]))
    L.append("  六神:  %s" % "  ".join("%s" % y["六神"] for y in ben["爻"]))
    if r["动爻"]:
        L.append("")
        L.append("【动爻】第 %s 爻" % "、".join(str(x) for x in r["动爻"]))
        bian = r["变卦"]
        L.append("【变卦】%s（%s宫）" % (bian["卦名"], bian["宫"]))
        for line in hexagram_lines(bian):
            L.append(line)
    L.append("")
    L.append(r["提示"])
    L.append("提示：占卜仅供文化研究与娱乐参考，重大决策请依据理性判断。")
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
    p = argparse.ArgumentParser(description="六爻占卜 —— 起一卦，看看所问之事的吉凶")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--time", action="store_true", help="按当前时间起卦（最常用）")
    g.add_argument("--numbers", type=int, nargs="+", help="心里想两个数字，填进来起卦")
    g.add_argument("--toss", action="store_true", help="模拟掷三枚硬币六次")
    p.add_argument("--solar", type=parse_date)
    p.add_argument("--lunar", type=parse_date)
    p.add_argument("--leap", action="store_true")
    p.add_argument("--hour", type=parse_hour)
    p.add_argument("--sex", default="男")
    p.add_argument("--question", default=None)
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    method = "time" if a.time else ("numbers" if a.numbers else "toss")
    r = divinate(method=method, solar=a.solar, lunar=a.lunar, leap=a.leap, hour=a.hour,
                 numbers=a.numbers, sex=a.sex, question=a.question)
    print(json.dumps(r, ensure_ascii=False, indent=2) if a.json else format_report(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())

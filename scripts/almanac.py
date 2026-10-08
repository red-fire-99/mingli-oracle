#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""天文历法引擎 —— 所有命理术数的公共底座（零第三方依赖，仅标准库）。

设计原则
--------
1. **确定性**：同样的输入永远得到同样的输出。所有术数排盘都必须建立在本模块之上，
   禁止让语言模型凭记忆推算四柱 / 农历 / 星历。
2. **零依赖**：只用 Python 标准库，可离线运行，不联网、不写盘、不读环境变量。
3. **天文精度**：节气用太阳视黄经「定气」，朔望用 Meeus 定朔，覆盖 1900–2100，
   时刻精度到分钟级，足以判定任何立春 / 节气交界 / 闰月边界。
4. **时区**：命理一律以北京时间 UTC+8 为基准钟表时（华人生辰传统），
   不随运行机器的本地时区漂移。

能力清单
--------
- 儒略日 / ΔT / 北京时间互转
- 太阳视黄经 → 二十四节气（含立春、十二「节」、十二「中气」）
- 月亮与行星地心视黄经（占星用，Schlyter 低精度轨道 + 摄动主项）
- 定朔 → 农历（冬至所在月为十一月、无中气置闰，即「定气定朔」）
- 干支纪日 / 年 / 月 / 时（五虎遁、五鼠遁）
- 真太阳时（均时差 EOT + 经度修正）
- 二十八宿、星期、节气所属月建

算法锚点（供自测断言）
----------------------
- 1990-05-15 日柱 = 庚辰；月柱 = 辛巳（立夏后、芒种前）
- 1990-02-03 10:00 年柱 = 己巳（未过立春）
- 2000-01-01 日柱 = 戊午
- 1990 年有闰五月；1990 农历四月廿一 = 1990-05-15
- 1984 = 甲子年
"""

import math
import os
import sys
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache


def fsum(values):
    """浮点补偿求和（Neumaier 算法）。

    为什么不能直接用内置 ``sum()``
    ------------------------------
    CPython 3.12 给 ``sum()`` 对 float 加了 Neumaier 补偿，3.8/3.11 仍是朴素循环。
    两者结果会差 1 ulp，而下游会把它放大：

        五行力量 = score / total * 100
        朴素循环 total = 10.239999999999998  ->  水 = 31.250000000000007  ->  显示 31.3%
        补偿求和 total = 10.24               ->  水 = 31.25              ->  显示 31.2%

    两个后果：
      1. 同一份代码在 3.8 与 3.12 上算出不同的五行百分比
      2. JS 移植无法对上 —— JS 只有朴素循环，除非也实现补偿

    所以这里显式实现，把行为固定下来、与 Python 版本无关。
    JS 侧 kernel.js 有一份逐行对应的实现，对拍保证两者一致。
    """
    s = 0.0
    c = 0.0
    for x in values:
        t = s + x
        if abs(s) >= abs(x):
            c += (s - t) + x
        else:
            c += (x - t) + s
        s = t
    return s + c


def setup_console():
    """把 stdout/stderr 统一成 UTF-8，避免中文输出乱码。

    Windows 中文系统默认控制台代码页是 936（GBK），Python 的
    ``sys.stdout.encoding`` 会变成 ``gbk``。直接跑在终端里通常正常，
    但一旦输出走管道、重定向到文件、或被 IDE / CI 捕获，GBK 字节会被
    按 UTF-8 解码，中文立刻变成乱码。这里把控制台代码页切到 65001
    并把两个流重配为 UTF-8，让「终端 / 管道 / 文件」三处输出一致。
    """
    if os.name != "nt":
        return
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

BJ = timezone(timedelta(hours=8))
J2000 = 2451545.0
UNIX_JD = 2440587.5

GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"
GAN_WUXING = "木木火火土土金金水水"
ZHI_WUXING = "水土木木土火火土金金土水"
GAN_YINYANG = "阳阴阳阴阳阴阳阴阳阴"
ZHI_YINYANG = "阳阴阳阴阳阴阳阴阳阴阳阴"

# 地支藏干（本气、中气、余气）
ZHI_CANGGAN = {
    "子": ("癸",),
    "丑": ("己", "癸", "辛"),
    "寅": ("甲", "丙", "戊"),
    "卯": ("乙",),
    "辰": ("戊", "乙", "癸"),
    "巳": ("丙", "庚", "戊"),
    "午": ("丁", "己"),
    "未": ("己", "丁", "乙"),
    "申": ("庚", "壬", "戊"),
    "酉": ("辛",),
    "戌": ("戊", "辛", "丁"),
    "亥": ("壬", "甲"),
}

# 十二「节」（非中气）：决定月柱换月
JIE_DEFS = (
    (315, "立春", 2),
    (345, "惊蛰", 3),
    (15, "清明", 4),
    (45, "立夏", 5),
    (75, "芒种", 6),
    (105, "小暑", 7),
    (135, "立秋", 8),
    (165, "白露", 9),
    (195, "寒露", 10),
    (225, "立冬", 11),
    (255, "大雪", 0),
    (285, "小寒", 1),
)
JIE_LONGS = tuple(x[0] for x in JIE_DEFS)
ZHONGQI_LONGS = (0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330)

SOLAR_TERM_ALL = {
    315: "立春", 330: "雨水", 345: "惊蛰", 0: "春分",
    15: "清明", 30: "谷雨", 45: "立夏", 60: "小满",
    75: "芒种", 90: "夏至", 105: "小暑", 120: "大暑",
    135: "立秋", 150: "处暑", 165: "白露", 180: "秋分",
    195: "寒露", 210: "霜降", 225: "立冬", 240: "小雪",
    255: "大雪", 270: "冬至", 285: "小寒", 300: "大寒",
}

# 年上起月（五虎遁）：年干序号 → 寅月天干序号
YUE_GAN_YIN = {0: 2, 5: 2, 1: 4, 6: 4, 2: 6, 7: 6, 3: 8, 8: 8, 4: 0, 9: 0}
# 五鼠遁元：日干序号 → 子时天干序号
ZI_SHI_GAN = {0: 0, 5: 0, 1: 2, 6: 2, 2: 4, 7: 4, 3: 6, 8: 6, 4: 8, 9: 8}

XIU28 = (
    "角", "亢", "氐", "房", "心", "尾", "箕",
    "斗", "牛", "女", "虚", "危", "室", "壁",
    "奎", "娄", "胃", "昴", "毕", "觜", "参",
    "井", "鬼", "柳", "星", "张", "翼", "轸",
)

# 六十甲子纳音（每两个干支一组，共 30 组）
NAYIN_30 = (
    "海中金", "炉中火", "大林木", "路旁土", "剑锋金", "山头火",
    "涧下水", "城头土", "白蜡金", "杨柳木", "泉中水", "屋上土",
    "霹雳火", "松柏木", "长流水", "沙中金", "山下火", "平地木",
    "壁上土", "金箔金", "覆灯火", "天河水", "大驿土", "钗钏金",
    "桑柘木", "大溪水", "沙中土", "天上火", "石榴木", "大海水",
)
NAYIN_WUXING = {
    "海中金": "金", "炉中火": "火", "大林木": "木", "路旁土": "土", "剑锋金": "金",
    "山头火": "火", "涧下水": "水", "城头土": "土", "白蜡金": "金", "杨柳木": "木",
    "泉中水": "水", "屋上土": "土", "霹雳火": "火", "松柏木": "木", "长流水": "水",
    "沙中金": "金", "山下火": "火", "平地木": "木", "壁上土": "土", "金箔金": "金",
    "覆灯火": "火", "天河水": "水", "大驿土": "土", "钗钏金": "金", "桑柘木": "木",
    "大溪水": "水", "沙中土": "土", "天上火": "火", "石榴木": "木", "大海水": "水",
}


def ganzhi_index(gan, zhi):
    """干支组合 → 六十甲子序号（0-59）。"""
    g, z = GAN.index(gan), ZHI.index(zhi)
    for n in range(60):
        if n % 10 == g and n % 12 == z:
            return n
    raise ValueError("非法干支组合：%s%s" % (gan, zhi))


def nayin_of(gan, zhi):
    """纳音名，如 甲子 → 海中金。"""
    return NAYIN_30[ganzhi_index(gan, zhi) // 2]


def nayin_wuxing(gan, zhi):
    """纳音五行（木火土金水）。"""
    return NAYIN_WUXING[nayin_of(gan, zhi)]


SHICHEN_MID = {
    "子": (0, 0), "丑": (2, 0), "寅": (4, 0), "卯": (6, 0),
    "辰": (8, 0), "巳": (10, 0), "午": (12, 0), "未": (14, 0),
    "申": (16, 0), "酉": (18, 0), "戌": (20, 0), "亥": (22, 0),
}

LUNAR_MONTH_NAMES = {1: "正", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六",
                     7: "七", 8: "八", 9: "九", 10: "十", 11: "冬", 12: "腊"}
LUNAR_DAY_NAMES = {
    1: "初一", 2: "初二", 3: "初三", 4: "初四", 5: "初五", 6: "初六",
    7: "初七", 8: "初八", 9: "初九", 10: "初十", 11: "十一", 12: "十二",
    13: "十三", 14: "十四", 15: "十五", 16: "十六", 17: "十七", 18: "十八",
    19: "十九", 20: "二十", 21: "廿一", 22: "廿二", 23: "廿三", 24: "廿四",
    25: "廿五", 26: "廿六", 27: "廿七", 28: "廿八", 29: "廿九", 30: "三十",
}


# ---------------------------------------------------------------------------
# 时间 / 儒略日
# ---------------------------------------------------------------------------

def delta_t_seconds(year):
    """TT − UTC 近似秒（Espenak/Meeus 分段多项式），1900–2100 分钟级。"""
    y = float(year)
    t = y - 2000.0
    if y < 1920:
        t1 = y - 1900.0
        return -2.79 + 1.494119 * t1 - 0.0598939 * t1 ** 2 + 0.0061966 * t1 ** 3 - 0.000197 * t1 ** 4
    if y < 1941:
        t1 = y - 1920.0
        return 21.20 + 0.84493 * t1 - 0.076100 * t1 ** 2 + 0.0020936 * t1 ** 3
    if y < 1961:
        t1 = y - 1950.0
        return 29.07 + 0.407 * t1 - t1 ** 2 / 233.0 + t1 ** 3 / 2547.0
    if y < 1986:
        t1 = y - 1975.0
        return 45.45 + 1.067 * t1 - t1 ** 2 / 260.0 - t1 ** 3 / 718.0
    if y < 2005:
        t1 = y - 2000.0
        return (63.86 + 0.3345 * t1 - 0.060374 * t1 ** 2 + 0.0017275 * t1 ** 3
                + 0.000651814 * t1 ** 4 + 0.00002373599 * t1 ** 5)
    if y < 2050:
        return 62.92 + 0.32217 * t + 0.005589 * t * t
    return -20.0 + 32.0 * ((y - 1820.0) / 100.0) ** 2 - 0.5628 * (2150.0 - y)


def jd_from_datetime(dt):
    """带时区 datetime → 儒略日（同一瞬时）。"""
    utc = dt.astimezone(timezone.utc)
    unix = (utc - datetime(1970, 1, 1, tzinfo=timezone.utc)).total_seconds()
    return UNIX_JD + unix / 86400.0


def datetime_from_jd_utc(jd):
    return datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=(jd - UNIX_JD) * 86400.0)


def jd_tt_to_beijing(jd_tt):
    """力学时（TT）儒略日 → 北京时间 datetime。"""
    year = 2000.0 + (jd_tt - J2000) / 365.242189
    utc_jd = jd_tt - delta_t_seconds(year) / 86400.0
    return datetime_from_jd_utc(utc_jd).astimezone(BJ)


def beijing(year, month, day, hour=0, minute=0, second=0):
    return datetime(year, month, day, hour, minute, second, tzinfo=BJ)


def jdn(year, month, day):
    """格里历儒略日数（整数，中午基准）。"""
    a = (14 - month) // 12
    y = year + 4800 - a
    m = month + 12 * a - 3
    return day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045


def jd_to_weekday(jd):
    """儒略日 → 星期（0=周日 … 6=周六）。"""
    return int(math.floor(jd + 1.5)) % 7


# ---------------------------------------------------------------------------
# 太阳视黄经与二十四节气
# ---------------------------------------------------------------------------

def sun_apparent_longitude(jd_tt):
    """太阳视黄经（度）。Meeus《天文算法》第 25 章简式，1900–2100 误差约 0.01°。"""
    T = (jd_tt - J2000) / 36525.0
    L0 = 280.46646 + 36000.76983 * T + 0.0003032 * T * T
    M = 357.52911 + 35999.05029 * T - 0.0001537 * T * T
    mr = math.radians(M)
    C = ((1.914602 - 0.004817 * T - 0.000014 * T * T) * math.sin(mr)
         + (0.019993 - 0.000101 * T) * math.sin(2.0 * mr)
         + 0.000289 * math.sin(3.0 * mr))
    omega = 125.04 - 1934.136 * T
    return (L0 + C - 0.00569 - 0.00478 * math.sin(math.radians(omega))) % 360.0


def _lon_delta(actual, target):
    """actual − target，归一到 (−180, 180]。"""
    return (actual - target + 180.0) % 360.0 - 180.0


@lru_cache(maxsize=8192)
def solar_term_jd(year, longitude):
    """某公历年达到目标视黄经的定气 TT 儒略日（牛顿迭代，收敛快且稳）。"""
    year = int(year)
    longitude = float(longitude) % 360.0
    # 初值：当年 1 月 1 日太阳黄经约 280.47°，日行约 0.9856°
    delta_lon = (longitude - 280.46646) % 360.0
    jd = J2000 + (year - 2000) * 365.242189 + delta_lon / 0.98564736
    for _ in range(24):
        diff = _lon_delta(sun_apparent_longitude(jd), longitude)
        if abs(diff) < 1e-8:
            break
        jd -= diff / 0.9856
    return jd


def solar_term_beijing(year, longitude):
    return jd_tt_to_beijing(solar_term_jd(year, longitude))


@lru_cache(maxsize=512)
def solar_terms_of_year(year):
    """该公历年 24 节气（按时间排序）→ tuple[(datetime, 名称, 黄经)]。"""
    out = []
    for lon, name in SOLAR_TERM_ALL.items():
        out.append((solar_term_beijing(year, lon), name, lon))
    out.sort(key=lambda x: x[0])
    return tuple(out)


@lru_cache(maxsize=512)
def jie_events_around(year):
    """year-1 … year+1 的十二「节」，按时间排序。每项 (dt, 名称, 月支下标)。"""
    events = []
    for y in (year - 1, year, year + 1):
        for lon, name, zhi_i in JIE_DEFS:
            events.append((solar_term_beijing(y, lon), name, zhi_i))
    events.sort(key=lambda x: x[0])
    return tuple(events)


def current_jie(dt):
    """给定时刻所处的「节」（月建）。返回 (节名, 月支下标, 该节起始时间)。"""
    events = jie_events_around(dt.year)
    cur = None
    for e in events:
        if e[0] <= dt:
            cur = e
        else:
            break
    if cur is None:
        cur = events[0]
    return cur[1], cur[2], cur[0]


# ---------------------------------------------------------------------------
# 月亮与行星地心黄经（占星用）
# ---------------------------------------------------------------------------

def _norm360(x):
    return x % 360.0


def _solve_kepler(M_deg, e):
    """解开普勒方程，返回偏近点角（弧度）。"""
    M = math.radians(M_deg % 360.0)
    E = M + e * math.sin(M)
    for _ in range(12):
        dE = (E - e * math.sin(E) - M) / (1.0 - e * math.cos(E))
        E -= dE
        if abs(dE) < 1e-10:
            break
    return E


# 行星轨道根数（J2000 历元 + 每世纪变化率）—— 低精度解析式，占星足够
_PLANET_ELEMENTS = {
    # name: (a0, a1, e0, e1, i0, i1, L0, L1, wbar0, wbar1, Omega0, Omega1)
    "水星": (0.38709927, 0.00000037, 0.20563593, 0.00001906, 7.00497902, -0.00594749,
             252.25032350, 149472.67411175, 77.45779628, 0.16047689, 48.33076593, -0.12534081),
    "金星": (0.72333566, 0.00000390, 0.00677672, -0.00004107, 3.39467605, -0.00078890,
             181.97909950, 58517.81538729, 131.60246718, 0.00268329, 76.67984255, -0.27769418),
    "火星": (1.52371034, 0.00001847, 0.09339410, 0.00007882, 1.84969142, -0.00813131,
             -4.55343205, 19140.30268499, -23.94362959, 0.44441088, 49.55953891, -0.29257343),
    "木星": (5.20288700, -0.00011607, 0.04838624, -0.00013253, 1.30439695, -0.00183714,
             34.39644051, 3034.74612775, 14.72847983, 0.21252668, 100.47390909, 0.20469106),
    "土星": (9.53667594, -0.00125060, 0.05386179, -0.00050991, 2.48599187, 0.00193609,
             49.95424423, 1222.49362201, 92.59887831, -0.41897216, 113.66242448, -0.28867794),
    "天王星": (19.18916464, -0.00196176, 0.04725744, -0.00004397, 0.77263783, -0.00242939,
               313.23810451, 428.48202785, 170.95427630, 0.40805281, 74.01692503, 0.04240589),
    "海王星": (30.06992276, 0.00026291, 0.00859048, 0.00005105, 1.77004347, 0.00035372,
               -55.12002969, 218.45945325, 44.96476227, -0.32241464, 131.78422574, -0.00508664),
    "冥王星": (39.48211675, -0.00031596, 0.24882730, 0.00005170, 17.14001206, 0.00004818,
               238.92903833, 145.20780515, 224.06891629, -0.04062942, 110.30393684, -0.01183482),
    # 地球（J2000 黄道系，与上面行星同一套根数，保证坐标系一致）
    "地球": (1.00000261, 0.00000562, 0.01671123, -0.00004392, -0.00001531, -0.01294668,
             100.46457166, 35999.37244981, 102.93768193, 0.32327364, 0.0, -0.01294668),
}


def _heliocentric_xyz(name, T):
    """行星日心黄道直角坐标（AU），T 为 J2000 起算世纪数。"""
    a0, a1, e0, e1, i0, i1, L0, L1, w0, w1, O0, O1 = _PLANET_ELEMENTS[name]
    a = a0 + a1 * T
    e = e0 + e1 * T
    i = math.radians(i0 + i1 * T)
    L = L0 + L1 * T
    wbar = w0 + w1 * T
    Om = math.radians(O0 + O1 * T)
    w = math.radians(wbar) - Om
    M = L - wbar
    E = _solve_kepler(M, e)
    xp = a * (math.cos(E) - e)
    yp = a * math.sqrt(1.0 - e * e) * math.sin(E)
    # 轨道面 → 黄道面
    cw, sw = math.cos(w), math.sin(w)
    cO, sO = math.cos(Om), math.sin(Om)
    ci, si = math.cos(i), math.sin(i)
    x = (cw * cO - sw * sO * ci) * xp + (-sw * cO - cw * sO * ci) * yp
    y = (cw * sO + sw * cO * ci) * xp + (-sw * sO + cw * cO * ci) * yp
    z = (sw * si) * xp + (cw * si) * yp
    return x, y, z


def _earth_heliocentric(T):
    """地球日心黄道直角坐标（AU，J2000 黄道系）。

    必须与行星使用**同一套 J2000 轨道根数**。曾因混用「of-date 太阳公式」与
    「J2000 行星根数」两个坐标系，导致行星黄经整体偏 1.4°/百年（恰好等于
    岁差量）——已用 ephem 交叉验证锁定并修正。
    """
    return _heliocentric_xyz("地球", T)


def _precession_arcsec(T):
    """J2000 → 目标历元的黄经岁差（角秒），Meeus 21.5 式。"""
    return 5029.0966 * T + 1.11113 * T * T - 0.000006 * T * T * T


def _moon_position(jd_tt):
    """月亮地心黄经（度）—— Meeus 第 47 章主项，精度约 0.1°。"""
    T = (jd_tt - J2000) / 36525.0
    Lp = 218.3164477 + 481267.88123421 * T - 0.0015786 * T * T
    D = 297.8501921 + 445267.1114034 * T - 0.0018819 * T * T
    M = 357.5291092 + 35999.0502909 * T
    Mp = 134.9633964 + 477198.8675055 * T + 0.0087414 * T * T
    F = 93.2720950 + 483202.0175233 * T - 0.0036539 * T * T
    d, m, mp, f = (math.radians(x) for x in (D, M, Mp, F))
    # 主要摄动项（黄经）
    lon = Lp + (
        6.288774 * math.sin(mp)
        + 1.274027 * math.sin(2 * d - mp)
        + 0.658314 * math.sin(2 * d)
        + 0.213618 * math.sin(2 * mp)
        - 0.185116 * math.sin(m)
        - 0.114332 * math.sin(2 * f)
        + 0.058793 * math.sin(2 * d - 2 * mp)
        + 0.057066 * math.sin(2 * d - m - mp)
        + 0.053322 * math.sin(2 * d + mp)
        + 0.045758 * math.sin(2 * d - m)
        - 0.040923 * math.sin(m - mp)
        - 0.034720 * math.sin(d)
        - 0.030383 * math.sin(m + mp)
        + 0.015327 * math.sin(2 * d - 2 * f)
        - 0.012528 * math.sin(mp + 2 * f)
        + 0.010980 * math.sin(mp - 2 * f)
    )
    return _norm360(lon)


def planet_geocentric_longitude(name, jd_tt):
    """行星（或太阳 / 月亮）地心**视黄经**（度，当日春分点 / of-date）。

    占星的黄道十二宫以当日春分点为起点，因此行星要先算 J2000 地心黄经，
    再加岁差转成 of-date，才能与太阳、月亮的 of-date 黄经放在同一张盘上。
    """
    if name == "太阳":
        return sun_apparent_longitude(jd_tt)
    if name == "月亮":
        return _moon_position(jd_tt)
    T = (jd_tt - J2000) / 36525.0
    ex, ey, _ = _earth_heliocentric(T)
    px, py, _ = _heliocentric_xyz(name, T)
    # 光行时修正：用行星在 (t − 光行时) 时刻的位置
    dist = math.sqrt((px - ex) ** 2 + (py - ey) ** 2)
    jd2 = jd_tt - dist * 0.0057755183
    T2 = (jd2 - J2000) / 36525.0
    ex2, ey2, _ = _earth_heliocentric(T2)
    px2, py2, _ = _heliocentric_xyz(name, T2)
    lon_j2000 = math.degrees(math.atan2(py2 - ey2, px2 - ex2))
    return _norm360(lon_j2000 + _precession_arcsec(T) / 3600.0)


PLANETS = ("太阳", "月亮", "水星", "金星", "火星", "木星", "土星", "天王星", "海王星", "冥王星")


# ---------------------------------------------------------------------------
# 定朔与农历（定气定朔：冬至所在月为十一月，无中气置闰）
# ---------------------------------------------------------------------------

def new_moon_jde(k):
    """第 k 次新月力学时 JDE（Meeus 第 49 章）。k=0 ≈ 2000-01-06 朔。"""
    T = k / 1236.85
    jde = (2451550.09766 + 29.530588861 * k + 0.00015437 * T * T
           - 0.000000150 * T ** 3 + 0.00000000073 * T ** 4)
    E = 1.0 - 0.002516 * T - 0.0000074 * T * T
    M = math.radians(2.5534 + 29.10535670 * k - 0.0000014 * T * T - 0.00000011 * T ** 3)
    Mp = math.radians(201.5643 + 385.81693528 * k + 0.0107582 * T * T
                      + 0.00001238 * T ** 3 - 0.000000058 * T ** 4)
    F = math.radians(160.7108 + 390.67050284 * k - 0.0016118 * T * T
                     - 0.00000227 * T ** 3 + 0.000000011 * T ** 4)
    omega = math.radians(124.7746 - 1.56375588 * k + 0.0020672 * T * T + 0.00000215 * T ** 3)
    args = (Mp, M, 2 * Mp, 2 * F, Mp - M, Mp + M, 2 * M, Mp - 2 * F, Mp + 2 * F,
            2 * Mp + M, 3 * Mp, M + 2 * F, M - 2 * F, 2 * Mp - M, omega,
            Mp + 2 * M, 2 * Mp - 2 * F, 3 * M, Mp + M - 2 * F, 2 * Mp + 2 * F,
            Mp + M + 2 * F, Mp - M + 2 * F, Mp - M - 2 * F, 3 * Mp + M, 4 * Mp)
    coef = (-0.40720, 0.17241 * E, 0.01608, 0.01039, 0.00739 * E, -0.00514 * E,
            0.00208 * E * E, -0.00111, -0.00057, 0.00056 * E, -0.00042, 0.00042 * E,
            0.00038 * E, -0.00024 * E, -0.00017, -0.00007, 0.00004, 0.00004,
            0.00003, 0.00003, -0.00003, 0.00003, -0.00002, -0.00002, 0.00002)
    jde += sum(c * math.sin(a) for c, a in zip(coef, args))
    A = (299.77 + 0.107408 * k - 0.009173 * T * T, 251.88 + 0.016321 * k,
         251.83 + 26.651886 * k, 349.42 + 36.412478 * k, 84.66 + 18.206239 * k,
         141.74 + 53.303771 * k, 207.14 + 2.453732 * k, 154.84 + 7.306860 * k,
         34.52 + 27.261239 * k, 207.19 + 0.121824 * k, 291.34 + 1.844379 * k,
         161.72 + 24.198154 * k, 239.56 + 25.513099 * k, 331.55 + 3.592518 * k)
    Ac = (325, 165, 164, 126, 110, 62, 60, 56, 47, 42, 40, 37, 35, 23)
    jde += sum(c * 1e-6 * math.sin(math.radians(a)) for c, a in zip(Ac, A))
    return jde


def _k_near(jd):
    return int(round((jd - 2451550.09766) / 29.530588861))


def last_new_moon_k_on_or_before(jd_tt):
    """**含该时刻所在农历月首**的朔序号（按北京时间的「日期」判定）。

    必须按日期而不是精确时刻：国标 GB/T 33661 以「含朔的那一天」为月首。
    当冬至与朔恰好同一天时（如 2014-12-22、2020-06-21），按时刻比较会把整个
    农历月序列错位一个月，进而让置闰判断也跟着错。
    """
    d = jd_tt_to_beijing(jd_tt).date()
    k = _k_near(jd_tt)
    while jd_tt_to_beijing(new_moon_jde(k)).date() > d:
        k -= 1
    while jd_tt_to_beijing(new_moon_jde(k + 1)).date() <= d:
        k += 1
    return k


@lru_cache(maxsize=512)
def lunar_months_between_dongzhi(dongzhi_year):
    """自「该年冬至所在十一月」起，到下一年冬至月之前的农历月序列。

    每项 dict: year, month, leap, start(date), days, shuo_jd
    """
    y = int(dongzhi_year)
    dz0 = solar_term_jd(y, 270)
    dz1 = solar_term_jd(y + 1, 270)
    k0 = last_new_moon_k_on_or_before(dz0)
    k1 = last_new_moon_k_on_or_before(dz1)
    moons = [new_moon_jde(k) for k in range(k0, k1 + 1)]
    n = len(moons) - 1
    zhong = [solar_term_jd(yy, lon) for yy in (y - 1, y, y + 1) for lon in ZHONGQI_LONGS]
    leap_index = None
    if n == 13:
        for i in range(n):
            # 关键：中气归属必须按「北京时间日期」判断，而非精确时刻。
            # 国标 GB/T 33661 规定农历月首为「含朔时刻的那一天」。
            # 当朔与中气恰好同一天时（如 2020-06-21 夏至与朔同日），
            # 按时刻比较会把中气算进前一个月，导致闰月整体滞后一个月。
            start_d = jd_tt_to_beijing(moons[i]).date()
            end_d = jd_tt_to_beijing(moons[i + 1]).date()
            has = False
            for z in zhong:
                if start_d <= jd_tt_to_beijing(z).date() < end_d:
                    has = True
                    break
            if not has:
                leap_index = i
                break
    months = []
    month_num = 11
    lunar_year = y
    for i in range(n):
        is_leap = leap_index is not None and i == leap_index
        if i > 0 and not is_leap:
            month_num += 1
            if month_num == 13:
                month_num = 1
                lunar_year = y + 1
        start_d = jd_tt_to_beijing(moons[i]).date()
        next_d = jd_tt_to_beijing(moons[i + 1]).date()
        months.append({
            "year": lunar_year, "month": month_num, "leap": is_leap,
            "start": start_d, "days": (next_d - start_d).days, "shuo_jd": moons[i],
        })
    return tuple(months)


def _lunar_months_covering(solar_year):
    seen, out = set(), []
    for seg in (lunar_months_between_dongzhi(solar_year - 2),
                lunar_months_between_dongzhi(solar_year - 1),
                lunar_months_between_dongzhi(solar_year)):
        for m in seg:
            key = (m["start"], m["year"], m["month"], m["leap"])
            if key not in seen:
                seen.add(key)
                out.append(m)
    out.sort(key=lambda x: x["start"])
    return out


def solar_to_lunar(y, m, d):
    """公历日 → (农历年, 月, 日, 是否闰月)。"""
    target = date(y, m, d)
    for info in _lunar_months_covering(y):
        start = info["start"]
        if start <= target < start + timedelta(days=info["days"]):
            return info["year"], info["month"], (target - start).days + 1, info["leap"]
    raise ValueError("无法换算农历：%04d-%02d-%02d 超出推算范围" % (y, m, d))


def lunar_to_solar(ly, lm, ld, leap=False):
    """农历日 → 公历 date。"""
    months = list(lunar_months_between_dongzhi(ly - 1)) + list(lunar_months_between_dongzhi(ly))
    found = None
    for info in months:
        if info["year"] == ly and info["month"] == lm and bool(info["leap"]) == bool(leap):
            found = info
            break
    if found is None:
        raise ValueError("找不到农历 %d年%s%s" % (ly, "闰" if leap else "", LUNAR_MONTH_NAMES.get(lm, str(lm) + "月")))
    if not 1 <= ld <= found["days"]:
        raise ValueError("农历 %d年%s%s只有 %d 天" % (ly, "闰" if leap else "", LUNAR_MONTH_NAMES.get(lm, str(lm) + "月"), found["days"]))
    return found["start"] + timedelta(days=ld - 1)


def format_lunar(ly, lm, ld, leap):
    return "%d年%s%s月%s" % (ly, "闰" if leap else "", LUNAR_MONTH_NAMES.get(lm, str(lm)),
                            LUNAR_DAY_NAMES.get(ld, str(ld)))


def lunar_month_days(ly, lm, leap=False):
    for info in list(lunar_months_between_dongzhi(ly - 1)) + list(lunar_months_between_dongzhi(ly)):
        if info["year"] == ly and info["month"] == lm and bool(info["leap"]) == bool(leap):
            return info["days"]
    return 30


# ---------------------------------------------------------------------------
# 干支
# ---------------------------------------------------------------------------

def gz_from_index(idx):
    idx = int(idx) % 60
    return GAN[idx % 10] + ZHI[idx % 12]


def year_gz_index(year):
    """立春之后的年干支序号（1984 = 甲子 = 0）。"""
    return (int(year) - 4) % 60


def year_gz(birth_dt):
    """按立春精确时刻定年柱干支。"""
    y = birth_dt.year
    lichun = solar_term_beijing(y, 315)
    if birth_dt < lichun:
        y -= 1
    return gz_from_index(year_gz_index(y)), y


def day_gz_index(y, m, d):
    """日柱序号（1990-05-15 = 庚辰 = 16）。"""
    return (jdn(y, m, d) + 49) % 60


def day_gz(y, m, d):
    return gz_from_index(day_gz_index(y, m, d))


def month_gz(birth_dt):
    """按月建「节」定月柱。返回 (干支, 月支, 节名, 节起始)。"""
    name, zhi_i, jie_start = current_jie(birth_dt)
    # 年干用节气年（月柱随节气年）
    yg, _ = year_gz(birth_dt)
    yg_idx = GAN.index(yg[0])
    # 五虎遁：寅宫起 YUE_GAN_YIN[年干]，按地支顺序（寅卯辰…子丑）顺推。
    # 地支偏移必须用 %12（子=0、丑=1 时 (zhi_i-2) 为负，%10 会得到错误结果）。
    gan_i = (YUE_GAN_YIN[yg_idx] + (zhi_i - 2) % 12) % 10
    return GAN[gan_i] + ZHI[zhi_i], ZHI[zhi_i], name, jie_start


def shichen_of(hour, minute=0):
    """钟表时间 → 时辰地支（子时跨日：23:00 起为次日早子时）。"""
    idx = ((hour + 1) // 2) % 12
    return ZHI[idx], idx


def hour_gz(day_gan, zhi_i):
    """时柱干支：五鼠遁元。"""
    return GAN[(ZI_SHI_GAN[GAN.index(day_gan)] + zhi_i) % 10] + ZHI[zhi_i]


def ganzhi_hour_label(zhi):
    return {
        "子": "23:00-01:00", "丑": "01:00-03:00", "寅": "03:00-05:00", "卯": "05:00-07:00",
        "辰": "07:00-09:00", "巳": "09:00-11:00", "午": "11:00-13:00", "未": "13:00-15:00",
        "申": "15:00-17:00", "酉": "17:00-19:00", "戌": "19:00-21:00", "亥": "21:00-23:00",
    }.get(zhi, "")


# ---------------------------------------------------------------------------
# 真太阳时
# ---------------------------------------------------------------------------

def equation_of_time_minutes(jd_tt):
    """均时差（分钟）= 真太阳时 − 平太阳时。"""
    T = (jd_tt - J2000) / 36525.0
    L0 = 280.46646 + 36000.76983 * T + 0.0003032 * T * T
    M = math.radians(357.52911 + 35999.05029 * T - 0.0001537 * T * T)
    # 太阳平黄经与真黄经之差 + 黄赤交角修正
    C = ((1.914602 - 0.004817 * T - 0.000014 * T * T) * math.sin(M)
         + (0.019993 - 0.000101 * T) * math.sin(2 * M)
         + 0.000289 * math.sin(3 * M))
    eps = math.radians(23.439291 - 0.0130042 * T)
    lam = math.radians(L0 + C)
    alpha = math.degrees(math.atan2(math.cos(eps) * math.sin(lam), math.cos(lam)))
    eot = (L0 - 0.0057183 - alpha) % 360.0
    if eot > 180:
        eot -= 360
    return eot * 4.0


def true_solar_time(dt, longitude):
    """钟表时间（北京 UTC+8）→ 真太阳时 datetime。

    真太阳时 = 北京时间 + (当地经度 − 120°) × 4 分钟 + 均时差
    """
    eot = equation_of_time_minutes(jd_from_datetime(dt))
    offset_min = (longitude - 120.0) * 4.0 + eot
    return dt + timedelta(minutes=offset_min), offset_min, eot


def xiu28_of(jd):
    """二十八宿（按日序近似轮值）。"""
    return XIU28[int(math.floor(jd - 2451545.0 + 0.5)) % 28]


# ---------------------------------------------------------------------------
# 自测
# ---------------------------------------------------------------------------

def _self_test():
    ok = True

    def check(label, got, want):
        nonlocal ok
        good = got == want
        ok = ok and good
        print(("  [OK] " if good else "  [FAIL] ") + label + " => " + str(got) + ("" if good else "  (期望 " + str(want) + ")"))

    print("== 历法引擎自测 ==")
    check("1990-05-15 日柱", day_gz(1990, 5, 15), "庚辰")
    check("2000-01-01 日柱", day_gz(2000, 1, 1), "戊午")
    check("1984 年干支", gz_from_index(year_gz_index(1984)), "甲子")
    check("1990-05-15 月柱", month_gz(beijing(1990, 5, 15, 12))[0], "辛巳")
    check("1990-02-03 10:00 年柱", year_gz(beijing(1990, 2, 3, 10))[0], "己巳")
    check("1990-05-15 12:00 时柱", hour_gz("庚", 6), "壬午")
    ly, lm, ld, leap = solar_to_lunar(1990, 5, 15)
    check("1990-05-15 农历", (ly, lm, ld, leap), (1990, 4, 21, False))
    check("农历反算", lunar_to_solar(1990, 4, 21), date(1990, 5, 15))
    check("1990 闰月存在", any(m["leap"] and m["year"] == 1990 and m["month"] == 5
                              for m in lunar_months_between_dongzhi(1989)), True)
    # 立春时刻量级检查：1990 立春应在 2 月 4 日
    lc = solar_term_beijing(1990, 315)
    check("1990 立春日期", (lc.month, lc.day), (2, 4))
    # 冬至应在 12 月 21-23
    dz = solar_term_beijing(2024, 270)
    check("2024 冬至日期", (dz.month, dz.day), (12, 21))
    print("== 自测" + ("全部通过" if ok else "存在失败") + " ==")
    return ok


if __name__ == "__main__":
    import sys
    sys.exit(0 if _self_test() else 1)

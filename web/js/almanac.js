/* ===================================================================
   almanac.js —— almanac.py 的 JS 移植（天文历法底座）
   ===================================================================
   逐函数对照 Python 版移植，函数名与结构尽量保持一致，便于逐行核对。
   所有 Python/JS 语义差异都走 kernel.js 里的 pyMod / pyFloorDiv / pyRound。

   与 Python 版的关系：Python 是唯一事实来源，本文件是它的第二实现。
   两者的一致性由 tools/diff_py_js.py 逐案对拍保证，任何不一致都算 bug。
   =================================================================== */

import {
  J2000, pyMod, pyFloorDiv, pyRound, norm360, memo,
  jdn, civilFromJdn, bjUnix, bjCivilFromUnix, jdFromBjUnix, bjUnixFromJd,
} from "./kernel.js";

/* ---------------- 常量 ---------------- */

export const GAN = "甲乙丙丁戊己庚辛壬癸";
export const ZHI = "子丑寅卯辰巳午未申酉戌亥";
export const GAN_WUXING = "木木火火土土金金水水";
export const ZHI_WUXING = "水土木木土火火土金金土水";
export const GAN_YINYANG = "阳阴阳阴阳阴阳阴阳阴";
export const ZHI_YINYANG = "阳阴阳阴阳阴阳阴阳阴阳阴";

export const ZHI_CANGGAN = {
  子: ["癸"], 丑: ["己", "癸", "辛"], 寅: ["甲", "丙", "戊"], 卯: ["乙"],
  辰: ["戊", "乙", "癸"], 巳: ["丙", "庚", "戊"], 午: ["丁", "己"],
  未: ["己", "丁", "乙"], 申: ["庚", "壬", "戊"], 酉: ["辛"],
  戌: ["戊", "辛", "丁"], 亥: ["壬", "甲"],
};

// 十二「节」：定月柱
export const JIE_DEFS = [
  [315, "立春", 2], [345, "惊蛰", 3], [15, "清明", 4], [45, "立夏", 5],
  [75, "芒种", 6], [105, "小暑", 7], [135, "立秋", 8], [165, "白露", 9],
  [195, "寒露", 10], [225, "立冬", 11], [255, "大雪", 0], [285, "小寒", 1],
];
export const ZHONGQI_LONGS = [0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330];

export const SOLAR_TERM_ALL = {
  315: "立春", 330: "雨水", 345: "惊蛰", 0: "春分",
  15: "清明", 30: "谷雨", 45: "立夏", 60: "小满",
  75: "芒种", 90: "夏至", 105: "小暑", 120: "大暑",
  135: "立秋", 150: "处暑", 165: "白露", 180: "秋分",
  195: "寒露", 210: "霜降", 225: "立冬", 240: "小雪",
  255: "大雪", 270: "冬至", 285: "小寒", 300: "大寒",
};

export const YUE_GAN_YIN = { 0: 2, 5: 2, 1: 4, 6: 4, 2: 6, 7: 6, 3: 8, 8: 8, 4: 0, 9: 0 };
export const ZI_SHI_GAN = { 0: 0, 5: 0, 1: 2, 6: 2, 2: 4, 7: 4, 3: 6, 8: 6, 4: 8, 9: 8 };

export const XIU28 = ["角", "亢", "氐", "房", "心", "尾", "箕",
  "斗", "牛", "女", "虚", "危", "室", "壁",
  "奎", "娄", "胃", "昴", "毕", "觜", "参",
  "井", "鬼", "柳", "星", "张", "翼", "轸"];

export const NAYIN_30 = ["海中金", "炉中火", "大林木", "路旁土", "剑锋金", "山头火",
  "涧下水", "城头土", "白蜡金", "杨柳木", "泉中水", "屋上土",
  "霹雳火", "松柏木", "长流水", "沙中金", "山下火", "平地木",
  "壁上土", "金箔金", "覆灯火", "天河水", "大驿土", "钗钏金",
  "桑柘木", "大溪水", "沙中土", "天上火", "石榴木", "大海水"];

export const NAYIN_WUXING = {
  "海中金": "金", "炉中火": "火", "大林木": "木", "路旁土": "土", "剑锋金": "金",
  "山头火": "火", "涧下水": "水", "城头土": "土", "白蜡金": "金", "杨柳木": "木",
  "泉中水": "水", "屋上土": "土", "霹雳火": "火", "松柏木": "木", "长流水": "水",
  "沙中金": "金", "山下火": "火", "平地木": "木", "壁上土": "土", "金箔金": "金",
  "覆灯火": "火", "天河水": "水", "大驿土": "土", "钗钏金": "金", "桑柘木": "木",
  "大溪水": "水", "沙中土": "土", "天上火": "火", "石榴木": "木", "大海水": "水",
};

export const LUNAR_MONTH_NAMES = { 1: "正", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六",
  7: "七", 8: "八", 9: "九", 10: "十", 11: "冬", 12: "腊" };

export const LUNAR_DAY_NAMES = {
  1: "初一", 2: "初二", 3: "初三", 4: "初四", 5: "初五", 6: "初六",
  7: "初七", 8: "初八", 9: "初九", 10: "初十", 11: "十一", 12: "十二",
  13: "十三", 14: "十四", 15: "十五", 16: "十六", 17: "十七", 18: "十八",
  19: "十九", 20: "二十", 21: "廿一", 22: "廿二", 23: "廿三", 24: "廿四",
  25: "廿五", 26: "廿六", 27: "廿七", 28: "廿八", 29: "廿九", 30: "三十",
};

export const SHICHEN_HOUR_RANGE = {
  子: "23:00-01:00", 丑: "01:00-03:00", 寅: "03:00-05:00", 卯: "05:00-07:00",
  辰: "07:00-09:00", 巳: "09:00-11:00", 午: "11:00-13:00", 未: "13:00-15:00",
  申: "15:00-17:00", 酉: "17:00-19:00", 戌: "19:00-21:00", 亥: "21:00-23:00",
};

/* ---------------- 干支 ---------------- */

export function ganzhiIndex(gan, zhi) {
  const g = GAN.indexOf(gan), z = ZHI.indexOf(zhi);
  for (let n = 0; n < 60; n++) if (n % 10 === g && n % 12 === z) return n;
  throw new Error("非法干支组合：" + gan + zhi);
}

export function nayinOf(gan, zhi) { return NAYIN_30[Math.floor(ganzhiIndex(gan, zhi) / 2)]; }
export function nayinWuxing(gan, zhi) { return NAYIN_WUXING[nayinOf(gan, zhi)]; }

export function gzFromIndex(idx) {
  const i = pyMod(Math.trunc(idx), 60);
  return GAN[pyMod(i, 10)] + ZHI[pyMod(i, 12)];
}

/* ---------------- ΔT / 儒略日 ---------------- */

export function deltaTSeconds(year) {
  const y = Number(year);
  const t = y - 2000.0;
  if (y < 1920) {
    const t1 = y - 1900.0;
    return -2.79 + 1.494119 * t1 - 0.0598939 * t1 ** 2 + 0.0061966 * t1 ** 3 - 0.000197 * t1 ** 4;
  }
  if (y < 1941) {
    const t1 = y - 1920.0;
    return 21.20 + 0.84493 * t1 - 0.076100 * t1 ** 2 + 0.0020936 * t1 ** 3;
  }
  if (y < 1961) {
    const t1 = y - 1950.0;
    return 29.07 + 0.407 * t1 - t1 ** 2 / 233.0 + t1 ** 3 / 2547.0;
  }
  if (y < 1986) {
    const t1 = y - 1975.0;
    return 45.45 + 1.067 * t1 - t1 ** 2 / 260.0 - t1 ** 3 / 718.0;
  }
  if (y < 2005) {
    const t1 = y - 2000.0;
    return 63.86 + 0.3345 * t1 - 0.060374 * t1 ** 2 + 0.0017275 * t1 ** 3
      + 0.000651814 * t1 ** 4 + 0.00002373599 * t1 ** 5;
  }
  if (y < 2050) return 62.92 + 0.32217 * t + 0.005589 * t * t;
  return -20.0 + 32.0 * ((y - 1820.0) / 100.0) ** 2 - 0.5628 * (2150.0 - y);
}

/** 力学时（TT）儒略日 → 北京墙钟的 unix 秒。 */
export function ttToBjUnix(jdTt) {
  const year = 2000.0 + (jdTt - J2000) / 365.242189;
  const utcJd = jdTt - deltaTSeconds(year) / 86400.0;
  return bjUnixFromJd(utcJd);
}

/** 力学时儒略日 → 北京墙钟字段。 */
export function ttToBeijing(jdTt) { return bjCivilFromUnix(ttToBjUnix(jdTt)); }

/** 北京墙钟 unix 秒 → 该时刻的儒略日。 */
export function jdFromBj(t) { return jdFromBjUnix(t); }

/** 北京墙钟 unix 秒 → 该时刻的儒略日序（整数 JDN，取北京日期）。 */
export function bjDateJdn(t) {
  const c = bjCivilFromUnix(t);
  return jdn(c.y, c.m, c.d);
}

export function jdToWeekday(jd) {
  return pyMod(Math.floor(jd + 1.5), 7);
}

/* ---------------- 太阳视黄经与节气 ---------------- */

export function sunApparentLongitude(jdTt) {
  const T = (jdTt - J2000) / 36525.0;
  const L0 = 280.46646 + 36000.76983 * T + 0.0003032 * T * T;
  const M = 357.52911 + 35999.05029 * T - 0.0001537 * T * T;
  const mr = M * Math.PI / 180;
  const C = (1.914602 - 0.004817 * T - 0.000014 * T * T) * Math.sin(mr)
    + (0.019993 - 0.000101 * T) * Math.sin(2.0 * mr)
    + 0.000289 * Math.sin(3.0 * mr);
  const omega = 125.04 - 1934.136 * T;
  return pyMod(L0 + C - 0.00569 - 0.00478 * Math.sin(omega * Math.PI / 180), 360.0);
}

/** actual − target，归一到 (−180, 180]。 */
function lonDelta(actual, target) {
  return pyMod(actual - target + 180.0, 360.0) - 180.0;
}

const solarTermJdInner = memo(function (year, longitude) {
  const y = Math.trunc(year);
  const lon = norm360(Number(longitude));
  const deltaLon = pyMod(lon - 280.46646, 360.0);
  let jd = J2000 + (y - 2000) * 365.242189 + deltaLon / 0.98564736;
  for (let i = 0; i < 24; i++) {
    const diff = lonDelta(sunApparentLongitude(jd), lon);
    if (Math.abs(diff) < 1e-8) break;
    jd -= diff / 0.9856;
  }
  return jd;
});

export function solarTermJd(year, longitude) { return solarTermJdInner(year, longitude); }

/** 节气时刻 → 北京墙钟 unix 秒。 */
export function solarTermBjUnix(year, longitude) {
  return ttToBjUnix(solarTermJd(year, longitude));
}

export function solarTermBeijing(year, longitude) {
  return bjCivilFromUnix(solarTermBjUnix(year, longitude));
}

/** 该公历年 24 节气，按时间排序 → [{t, name, lon}]。 */
export const solarTermsOfYear = memo(function (year) {
  const out = [];
  for (const lon of Object.keys(SOLAR_TERM_ALL)) {
    const L = Number(lon);
    out.push({ t: solarTermBjUnix(year, L), name: SOLAR_TERM_ALL[L], lon: L });
  }
  out.sort((a, b) => a.t - b.t);
  return out;
});

/** year-1…year+1 的十二「节」，按时间排序 → [{t, name, zhi_i}]。 */
export const jieEventsAround = memo(function (year) {
  const events = [];
  for (const y of [year - 1, year, year + 1]) {
    for (const [lon, name, zhiI] of JIE_DEFS) {
      events.push({ t: solarTermBjUnix(y, lon), name, zhi_i: zhiI });
    }
  }
  events.sort((a, b) => a.t - b.t);
  return events;
});

/** 给定时刻所处的「节」。返回 {name, zhi_i, start}。 */
export function currentJie(t, yearOfT) {
  const events = jieEventsAround(yearOfT);
  let cur = null;
  for (const e of events) {
    if (e.t <= t) cur = e; else break;
  }
  if (!cur) cur = events[0];
  return { name: cur.name, zhi_i: cur.zhi_i, start: cur.t };
}

/* ---------------- 行星 / 月亮 ---------------- */

function solveKepler(MDeg, e) {
  const M = (norm360(MDeg)) * Math.PI / 180;
  let E = M + e * Math.sin(M);
  for (let i = 0; i < 12; i++) {
    const dE = (E - e * Math.sin(E) - M) / (1.0 - e * Math.cos(E));
    E -= dE;
    if (Math.abs(dE) < 1e-10) break;
  }
  return E;
}

// name: [a0,a1,e0,e1,i0,i1,L0,L1,wbar0,wbar1,O0,O1]
const PLANET_ELEMENTS = {
  水星: [0.38709927, 0.00000037, 0.20563593, 0.00001906, 7.00497902, -0.00594749,
    252.25032350, 149472.67411175, 77.45779628, 0.16047689, 48.33076593, -0.12534081],
  金星: [0.72333566, 0.00000390, 0.00677672, -0.00004107, 3.39467605, -0.00078890,
    181.97909950, 58517.81538729, 131.60246718, 0.00268329, 76.67984255, -0.27769418],
  火星: [1.52371034, 0.00001847, 0.09339410, 0.00007882, 1.84969142, -0.00813131,
    -4.55343205, 19140.30268499, -23.94362959, 0.44441088, 49.55953891, -0.29257343],
  木星: [5.20288700, -0.00011607, 0.04838624, -0.00013253, 1.30439695, -0.00183714,
    34.39644051, 3034.74612775, 14.72847983, 0.21252668, 100.47390909, 0.20469106],
  土星: [9.53667594, -0.00125060, 0.05386179, -0.00050991, 2.48599187, 0.00193609,
    49.95424423, 1222.49362201, 92.59887831, -0.41897216, 113.66242448, -0.28867794],
  天王星: [19.18916464, -0.00196176, 0.04725744, -0.00004397, 0.77263783, -0.00242939,
    313.23810451, 428.48202785, 170.95427630, 0.40805281, 74.01692503, 0.04240589],
  海王星: [30.06992276, 0.00026291, 0.00859048, 0.00005105, 1.77004347, 0.00035372,
    -55.12002969, 218.45945325, 44.96476227, -0.32241464, 131.78422574, -0.00508664],
  冥王星: [39.48211675, -0.00031596, 0.24882730, 0.00005170, 17.14001206, 0.00004818,
    238.92903833, 145.20780515, 224.06891629, -0.04062942, 110.30393684, -0.01183482],
  地球: [1.00000261, 0.00000562, 0.01671123, -0.00004392, -0.00001531, -0.01294668,
    100.46457166, 35999.37244981, 102.93768193, 0.32327364, 0.0, -0.01294668],
};

function heliocentricXYZ(name, T) {
  const [a0, a1, e0, e1, i0, i1, L0, L1, w0, w1, O0, O1] = PLANET_ELEMENTS[name];
  const a = a0 + a1 * T;
  const e = e0 + e1 * T;
  const i = (i0 + i1 * T) * Math.PI / 180;
  const L = L0 + L1 * T;
  const wbar = w0 + w1 * T;
  const Om = (O0 + O1 * T) * Math.PI / 180;
  const w = wbar * Math.PI / 180 - Om;
  const M = L - wbar;
  const E = solveKepler(M, e);
  const xp = a * (Math.cos(E) - e);
  const yp = a * Math.sqrt(1.0 - e * e) * Math.sin(E);
  const cw = Math.cos(w), sw = Math.sin(w);
  const cO = Math.cos(Om), sO = Math.sin(Om);
  const ci = Math.cos(i), si = Math.sin(i);
  const x = (cw * cO - sw * sO * ci) * xp + (-sw * cO - cw * sO * ci) * yp;
  const y = (cw * sO + sw * cO * ci) * xp + (-sw * sO + cw * cO * ci) * yp;
  const z = (sw * si) * xp + (cw * si) * yp;
  return [x, y, z];
}

const earthHelio = (T) => heliocentricXYZ("地球", T);

function precessionArcsec(T) {
  return 5029.0966 * T + 1.11113 * T * T - 0.000006 * T * T * T;
}

function moonPosition(jdTt) {
  const T = (jdTt - J2000) / 36525.0;
  const Lp = 218.3164477 + 481267.88123421 * T - 0.0015786 * T * T;
  const D = 297.8501921 + 445267.1114034 * T - 0.0018819 * T * T;
  const M = 357.5291092 + 35999.0502909 * T;
  const Mp = 134.9633964 + 477198.8675055 * T + 0.0087414 * T * T;
  const F = 93.2720950 + 483202.0175233 * T - 0.0036539 * T * T;
  const d = D * Math.PI / 180, m = M * Math.PI / 180, mp = Mp * Math.PI / 180, f = F * Math.PI / 180;
  const lon = Lp + (
    6.288774 * Math.sin(mp)
    + 1.274027 * Math.sin(2 * d - mp)
    + 0.658314 * Math.sin(2 * d)
    + 0.213618 * Math.sin(2 * mp)
    - 0.185116 * Math.sin(m)
    - 0.114332 * Math.sin(2 * f)
    + 0.058793 * Math.sin(2 * d - 2 * mp)
    + 0.057066 * Math.sin(2 * d - m - mp)
    + 0.053322 * Math.sin(2 * d + mp)
    + 0.045758 * Math.sin(2 * d - m)
    - 0.040923 * Math.sin(m - mp)
    - 0.034720 * Math.sin(d)
    - 0.030383 * Math.sin(m + mp)
    + 0.015327 * Math.sin(2 * d - 2 * f)
    - 0.012528 * Math.sin(mp + 2 * f)
    + 0.010980 * Math.sin(mp - 2 * f)
  );
  return norm360(lon);
}

/** 行星（或太阳/月亮）地心视黄经（度，of-date）。 */
export function planetGeocentricLongitude(name, jdTt) {
  if (name === "太阳") return sunApparentLongitude(jdTt);
  if (name === "月亮") return moonPosition(jdTt);
  const T = (jdTt - J2000) / 36525.0;
  const [ex, ey] = earthHelio(T);
  const [px, py] = heliocentricXYZ(name, T);
  const dist = Math.sqrt((px - ex) ** 2 + (py - ey) ** 2);
  const jd2 = jdTt - dist * 0.0057755183;
  const T2 = (jd2 - J2000) / 36525.0;
  const [ex2, ey2] = earthHelio(T2);
  const [px2, py2] = heliocentricXYZ(name, T2);
  const lonJ2000 = Math.atan2(py2 - ey2, px2 - ex2) * 180 / Math.PI;
  return norm360(lonJ2000 + precessionArcsec(T) / 3600.0);
}

export const PLANETS = ["太阳", "月亮", "水星", "金星", "火星", "木星", "土星",
  "天王星", "海王星", "冥王星"];

/* ---------------- 定朔与农历 ---------------- */

export function newMoonJde(k) {
  const T = k / 1236.85;
  let jde = 2451550.09766 + 29.530588861 * k + 0.00015437 * T * T
    - 0.000000150 * T ** 3 + 0.00000000073 * T ** 4;
  const E = 1.0 - 0.002516 * T - 0.0000074 * T * T;
  const M = (2.5534 + 29.10535670 * k - 0.0000014 * T * T - 0.00000011 * T ** 3) * Math.PI / 180;
  const Mp = (201.5643 + 385.81693528 * k + 0.0107582 * T * T
    + 0.00001238 * T ** 3 - 0.000000058 * T ** 4) * Math.PI / 180;
  const F = (160.7108 + 390.67050284 * k - 0.0016118 * T * T
    - 0.00000227 * T ** 3 + 0.000000011 * T ** 4) * Math.PI / 180;
  const omega = (124.7746 - 1.56375588 * k + 0.0020672 * T * T + 0.00000215 * T ** 3) * Math.PI / 180;
  const args = [Mp, M, 2 * Mp, 2 * F, Mp - M, Mp + M, 2 * M, Mp - 2 * F, Mp + 2 * F,
    2 * Mp + M, 3 * Mp, M + 2 * F, M - 2 * F, 2 * Mp - M, omega,
    Mp + 2 * M, 2 * Mp - 2 * F, 3 * M, Mp + M - 2 * F, 2 * Mp + 2 * F,
    Mp + M + 2 * F, Mp - M + 2 * F, Mp - M - 2 * F, 3 * Mp + M, 4 * Mp];
  const coef = [-0.40720, 0.17241 * E, 0.01608, 0.01039, 0.00739 * E, -0.00514 * E,
    0.00208 * E * E, -0.00111, -0.00057, 0.00056 * E, -0.00042, 0.00042 * E,
    0.00038 * E, -0.00024 * E, -0.00017, -0.00007, 0.00004, 0.00004,
    0.00003, 0.00003, -0.00003, 0.00003, -0.00002, -0.00002, 0.00002];
  let sum = 0;
  for (let i = 0; i < args.length; i++) sum += coef[i] * Math.sin(args[i]);
  jde += sum;
  const A = [299.77 + 0.107408 * k - 0.009173 * T * T, 251.88 + 0.016321 * k,
    251.83 + 26.651886 * k, 349.42 + 36.412478 * k, 84.66 + 18.206239 * k,
    141.74 + 53.303771 * k, 207.14 + 2.453732 * k, 154.84 + 7.306860 * k,
    34.52 + 27.261239 * k, 207.19 + 0.121824 * k, 291.34 + 1.844379 * k,
    161.72 + 24.198154 * k, 239.56 + 25.513099 * k, 331.55 + 3.592518 * k];
  const Ac = [325, 165, 164, 126, 110, 62, 60, 56, 47, 42, 40, 37, 35, 23];
  for (let i = 0; i < Ac.length; i++) jde += Ac[i] * 1e-6 * Math.sin(A[i] * Math.PI / 180);
  return jde;
}

function kNear(jd) {
  // Python: int(round(x))，round 是银行家舍入 —— 必须用 pyRound
  return pyRound((jd - 2451550.09766) / 29.530588861);
}

/**
 * 含该时刻所在农历月首的朔序号（按北京时间的「日期」判定）。
 * 必须按日期而非精确时刻 —— GB/T 33661 以「含朔的那一天」为月首。
 */
export function lastNewMoonKOnOrBefore(jdTt) {
  const d = bjDateJdn(ttToBjUnix(jdTt));
  let k = kNear(jdTt);
  while (bjDateJdn(ttToBjUnix(newMoonJde(k))) > d) k -= 1;
  while (bjDateJdn(ttToBjUnix(newMoonJde(k + 1))) <= d) k += 1;
  return k;
}

const lunarMonthsBetweenDongzhiInner = memo(function (dongzhiYear) {
  const y = Math.trunc(dongzhiYear);
  const dz0 = solarTermJd(y, 270);
  const dz1 = solarTermJd(y + 1, 270);
  const k0 = lastNewMoonKOnOrBefore(dz0);
  const k1 = lastNewMoonKOnOrBefore(dz1);
  const moons = [];
  for (let k = k0; k <= k1; k++) moons.push(newMoonJde(k));
  const n = moons.length - 1;
  const zhong = [];
  for (const yy of [y - 1, y, y + 1]) for (const lon of ZHONGQI_LONGS) zhong.push(solarTermJd(yy, lon));
  let leapIndex = null;
  if (n === 13) {
    for (let i = 0; i < n; i++) {
      // 中气归属必须按「北京时间日期」判断，而非精确时刻
      const startD = bjDateJdn(ttToBjUnix(moons[i]));
      const endD = bjDateJdn(ttToBjUnix(moons[i + 1]));
      let has = false;
      for (const z of zhong) {
        const zd = bjDateJdn(ttToBjUnix(z));
        if (zd >= startD && zd < endD) { has = true; break; }
      }
      if (!has) { leapIndex = i; break; }
    }
  }
  const months = [];
  let monthNum = 11;
  let lunarYear = y;
  for (let i = 0; i < n; i++) {
    const isLeap = leapIndex !== null && i === leapIndex;
    if (i > 0 && !isLeap) {
      monthNum += 1;
      if (monthNum === 13) { monthNum = 1; lunarYear = y + 1; }
    }
    const startD = bjDateJdn(ttToBjUnix(moons[i]));
    const nextD = bjDateJdn(ttToBjUnix(moons[i + 1]));
    months.push({
      year: lunarYear, month: monthNum, leap: isLeap,
      startJdn: startD, days: nextD - startD, shuoJd: moons[i],
    });
  }
  return months;
});

export function lunarMonthsBetweenDongzhi(dzYear) {
  return lunarMonthsBetweenDongzhiInner(dzYear);
}

const lunarMonthsCoveringInner = memo(function (solarYear) {
  const seen = new Set();
  const out = [];
  for (const seg of [lunarMonthsBetweenDongzhi(solarYear - 2),
                      lunarMonthsBetweenDongzhi(solarYear - 1),
                      lunarMonthsBetweenDongzhi(solarYear)]) {
    for (const m of seg) {
      const key = [m.startJdn, m.year, m.month, m.leap].join("|");
      if (!seen.has(key)) { seen.add(key); out.push(m); }
    }
  }
  out.sort((a, b) => a.startJdn - b.startJdn);
  return out;
});

function lunarMonthsCovering(y) { return lunarMonthsCoveringInner(y); }

/** 公历日 → {y, m, d} */
export function solarToLunar(y, m, d) {
  const target = jdn(y, m, d);
  const months = lunarMonthsCovering(y);
  for (const info of months) {
    if (target >= info.startJdn && target < info.startJdn + info.days) {
      return { year: info.year, month: info.month, day: target - info.startJdn + 1, leap: info.leap };
    }
  }
  throw new Error("无法换算农历：" + y + "-" + m + "-" + d + " 超出推算范围");
}

export function solarToLunarTuple(y, m, d) {
  const r = solarToLunar(y, m, d);
  return [r.year, r.month, r.day, r.leap];
}

/** 农历日 → 公历 {y, m, d} */
export function lunarToSolar(ly, lm, ld, leap) {
  const months = [...lunarMonthsBetweenDongzhi(ly - 1), ...lunarMonthsBetweenDongzhi(ly)];
  let found = null;
  for (const info of months) {
    if (info.year === ly && info.month === lm && Boolean(info.leap) === Boolean(leap)) {
      found = info; break;
    }
  }
  if (!found) throw new Error("找不到农历 " + ly + "年" + (leap ? "闰" : ""));
  if (!(ld >= 1 && ld <= found.days)) {
    throw new Error("农历 " + ly + "年" + (leap ? "闰" : "") + "只有 " + found.days + " 天");
  }
  return civilFromJdn(found.startJdn + ld - 1);
}

export function formatLunar(ly, lm, ld, leap) {
  const mn = LUNAR_MONTH_NAMES[lm] || (lm + "月");
  const dn = LUNAR_DAY_NAMES[ld] || String(ld);
  return ly + "年" + (leap ? "闰" : "") + mn + "月" + dn;
}

export function lunarMonthDays(ly, lm, leap) {
  const months = [...lunarMonthsBetweenDongzhi(ly - 1), ...lunarMonthsBetweenDongzhi(ly)];
  for (const info of months) {
    if (info.year === ly && info.month === lm && Boolean(info.leap) === Boolean(leap)) return info.days;
  }
  return 30;
}

/* ---------------- 干支（四柱） ---------------- */

export function yearGzIndex(year) { return pyMod(Math.trunc(year) - 4, 60); }

/** 按立春精确时刻定年柱。t 为北京墙钟 unix 秒。 */
export function yearGz(t, yearOfT) {
  let y = yearOfT;
  const lichun = solarTermBjUnix(y, 315);
  if (t < lichun) y -= 1;
  return { gz: gzFromIndex(yearGzIndex(y)), year: y };
}

export function dayGzIndex(y, m, d) { return pyMod(jdn(y, m, d) + 49, 60); }
export function dayGz(y, m, d) { return gzFromIndex(dayGzIndex(y, m, d)); }

/** 按月建「节」定月柱。 */
export function monthGz(t, yearOfT) {
  const { name, zhi_i, start } = currentJie(t, yearOfT);
  const yg = yearGz(t, yearOfT).gz;
  const ygIdx = GAN.indexOf(yg[0]);
  // 五虎遁：地支偏移必须用 %12（子=0、丑=1 时 (zhi_i-2) 为负，%10 会错）
  const ganI = pyMod(YUE_GAN_YIN[ygIdx] + pyMod(zhi_i - 2, 12), 10);
  return { gz: GAN[ganI] + ZHI[zhi_i], zhi: ZHI[zhi_i], name, start };
}

/** 钟表时间 → 时辰地支（子时跨日：23:00 起为早子时）。 */
export function shichenOf(hour, minute) {
  const idx = pyMod(pyFloorDiv(hour + 1, 2), 12);
  return { zhi: ZHI[idx], idx };
}

export function hourGz(dayGan, zhiI) {
  return GAN[pyMod(ZI_SHI_GAN[GAN.indexOf(dayGan)] + zhiI, 10)] + ZHI[zhiI];
}

export function ganzhiHourLabel(zhi) { return SHICHEN_HOUR_RANGE[zhi] || ""; }

/* ---------------- 真太阳时 ---------------- */

export function equationOfTimeMinutes(jdTt) {
  const T = (jdTt - J2000) / 36525.0;
  const L0 = 280.46646 + 36000.76983 * T + 0.0003032 * T * T;
  const M = (357.52911 + 35999.05029 * T - 0.0001537 * T * T) * Math.PI / 180;
  const C = (1.914602 - 0.004817 * T - 0.000014 * T * T) * Math.sin(M)
    + (0.019993 - 0.000101 * T) * Math.sin(2 * M)
    + 0.000289 * Math.sin(3 * M);
  const eps = (23.439291 - 0.0130042 * T) * Math.PI / 180;
  const lam = (L0 + C) * Math.PI / 180;
  const alpha = Math.atan2(Math.cos(eps) * Math.sin(lam), Math.cos(lam)) * 180 / Math.PI;
  let eot = pyMod(L0 - 0.0057183 - alpha, 360.0);
  if (eot > 180) eot -= 360;
  return eot * 4.0;
}

/** 真太阳时 = 北京时间 + (经度 − 120°) × 4 分钟 + 均时差。 */
export function trueSolarTime(t, longitude) {
  const eot = equationOfTimeMinutes(jdFromBjUnix(t));
  const offsetMin = (longitude - 120.0) * 4.0 + eot;
  return { t: t + offsetMin * 60, offsetMin, eot };
}

export function xiu28Of(jd) {
  return XIU28[pyMod(Math.floor(jd - 2451545.0 + 0.5), 28)];
}
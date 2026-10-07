/* ===================================================================
   astro.js —— astro.py 的 JS 移植（西洋占星本命盘）
   ===================================================================
   与 Python 版逐段对照。Python 是唯一事实来源，一致性由 diff_py_js 保证。
   =================================================================== */

import {
  PLANETS, planetGeocentricLongitude,
  solarToLunarTuple, lunarToSolar, formatLunar,
} from "./almanac.js";
import { pyMod, pyRound, J2000, bjUnix, jdFromBjUnix, pyRoundN } from "./kernel.js";

// SIGNS / 元素 / 性质 本来就定义在 astro.py，不在 almanac.py —— 别从 almanac 导
export const SIGNS = ["白羊", "金牛", "双子", "巨蟹", "狮子", "处女",
  "天秤", "天蝎", "射手", "摩羯", "水瓶", "双鱼"];

const SIGN_ELEMENT = ["火", "土", "风", "水", "火", "土", "风", "水", "火", "土", "风", "水"];
const SIGN_MODALITY = ["基本", "固定", "变动", "基本", "固定", "变动",
  "基本", "固定", "变动", "基本", "固定", "变动"];

const GLYPH = { 太阳: "☉", 月亮: "☽", 水星: "☿", 金星: "♀", 火星: "♂",
  木星: "♃", 土星: "♄", 天王星: "♅", 海王星: "♆", 冥王星: "♇",
  上升: "ASC", 天顶: "MC" };

const ASPECTS = [["合相", 0, 8], ["六分相", 60, 5], ["刑相", 90, 6],
  ["三分相", 120, 6], ["对分相", 180, 8]];

// SIGNS 已在上方 export；这里只补导出尚未导出的三个
export { SIGN_ELEMENT, SIGN_MODALITY, GLYPH };

/** 黄经 → [星座名, 星座内度数, 星座序号]。 */
export function signOf(lon) {
  const i = pyMod(Math.floor(lon / 30), 12);
  return [SIGNS[i], pyRoundN((lon - i * 30), 2), i];
}

/** 格林尼治平恒星时（度）。 */
export function gmstDeg(jdUt) {
  const T = (jdUt - J2000) / 36525.0;
  return pyMod(280.46061837 + 360.98564736629 * (jdUt - J2000)
    + 0.000387933 * T * T - T * T * T / 38710000.0, 360.0);
}

/** 上升点与天顶的黄经（度）。 */
export function ascMc(jdUt, lat, lon) {
  const eps = (23.439291 - 0.0130042 * (jdUt - J2000) / 36525.0) * Math.PI / 180;
  const ramc = pyMod(gmstDeg(jdUt) + lon, 360.0) * Math.PI / 180;
  const latR = lat * Math.PI / 180;
  let mc = Math.atan2(Math.sin(ramc), Math.cos(ramc) * Math.cos(eps));
  mc = pyMod(mc * 180 / Math.PI, 360.0);
  let asc = Math.atan2(-Math.cos(ramc),
    Math.sin(ramc) * Math.cos(eps) + Math.tan(latR) * Math.sin(eps));
  asc = pyMod(asc * 180 / Math.PI, 360.0);
  return [asc, mc];
}

/** 两黄经的相位：{名称, 标准角, 偏差} 或 null。 */
export function aspectsBetween(lon1, lon2) {
  const diff = Math.abs(pyMod(lon1 - lon2 + 180, 360) - 180);
  for (const [name, ang, orb] of ASPECTS) {
    if (Math.abs(diff - ang) <= orb) {
      return { 名称: name, 标准角: ang, 偏差: pyRoundN((diff - ang), 2) };
    }
  }
  return null;
}

function degText(deg) {
  // Python: "%d°%02d'" % (int(deg), int(deg % 1 * 60))
  return Math.trunc(deg) + "°" + String(Math.trunc(deg % 1 * 60)).padStart(2, "0") + "'";
}

/**
 * Python float 的字符串化：整数值也带 ".0"（repr(40.0) == '40.0'）。
 * JS 的 number 分不清 40 与 40.0，直接拼接会得到 '40'，与 Python 不一致。
 */
function pyFloatStr(v) {
  const n = Number(v);
  return Number.isInteger(n) ? n.toFixed(1) : String(n);
}

export function paiPan(opt) {
  let y, m, d, lunarInfo;
  if (opt.solar) {
    [y, m, d] = opt.solar;
    lunarInfo = solarToLunarTuple(y, m, d);
  } else if (opt.lunar) {
    const [ly, lm, ld] = opt.lunar;
    const dt = lunarToSolar(ly, lm, ld, opt.leap);
    y = dt.y; m = dt.m; d = dt.d;
    lunarInfo = [ly, lm, ld, Boolean(opt.leap)];
  } else {
    throw new Error("必须提供 solar 或 lunar");
  }

  let hh = 12, mm = 0;
  if (opt.hour != null) {
    if (typeof opt.hour === "number") { hh = opt.hour; mm = 0; }
    else { hh = opt.hour[0]; mm = opt.hour[1]; }
  }
  const jdUt = jdFromBjUnix(bjUnix(y, m, d, hh, mm, 0));

  const planets = PLANETS.map((name) => {
    const lo = planetGeocentricLongitude(name, jdUt);
    const [sign, deg, si] = signOf(lo);
    return {
      天体: name, 符号: GLYPH[name], 黄经: pyRoundN(lo, 3),
      星座: sign, 度数: deg, 星座内度: degText(deg),
      元素: SIGN_ELEMENT[si], 性质: SIGN_MODALITY[si],
    };
  });

  const angles = {};
  if (opt.lat != null && opt.lon != null) {
    const [asc, mc] = ascMc(jdUt, Number(opt.lat), Number(opt.lon));
    for (const [nm, val] of [["上升", asc], ["天顶", mc]]) {
      const [sign, deg, si] = signOf(val);
      angles[nm] = { 黄经: pyRoundN(val, 3), 星座: sign, 度数: deg,
                      星座内度: degText(deg), 符号: GLYPH[nm] };
    }
  }

  // 相位
  const bodies = planets.map((p) => [p.天体, p.黄经]);
  if (angles["上升"]) {
    bodies.push(["上升", angles["上升"].黄经]);
    bodies.push(["天顶", angles["天顶"].黄经]);
  }
  const asp = [];
  for (let i = 0; i < bodies.length; i++) {
    for (let j = i + 1; j < bodies.length; j++) {
      const r = aspectsBetween(bodies[i][1], bodies[j][1]);
      if (r) {
        asp.push({ 天体1: bodies[i][0], 天体2: bodies[j][0], 相位: r.名称,
                   标准角: r.标准角, 偏差: r.偏差,
                   强度: pyRoundN(1 - Math.abs(r.偏差) / 8, 2) });
      }
    }
  }

  // 元素 / 性质分布
  const elemCnt = { 火: 0, 土: 0, 风: 0, 水: 0 };
  const modCnt = { 基本: 0, 固定: 0, 变动: 0 };
  for (const p of planets) { elemCnt[p.元素] += 1; modCnt[p.性质] += 1; }

  // 整宫制宫位
  const houses = [];
  if (angles["上升"]) {
    const ascSi = Math.floor(angles["上升"].黄经 / 30);
    for (let k = 0; k < 12; k++) {
      const si = pyMod(ascSi + k, 12);
      const members = planets.filter((p) => Math.floor(p.黄经 / 30) === si).map((p) => p.天体);
      houses.push({ 宫: k + 1, 星座: SIGNS[si], 内行星: members });
    }
  }

  const pad2 = (n) => String(n).padStart(2, "0");
  return {
    输入: {
      公历: String(y).padStart(4, "0") + "-" + pad2(m) + "-" + pad2(d),
      农历: formatLunar(lunarInfo[0], lunarInfo[1], lunarInfo[2], lunarInfo[3]),
      时刻: pad2(hh) + ":" + pad2(mm),
      性别: opt.sex || "男",
      出生地: opt.place || "未提供",
      // Python: "%s, %s" % (lat, lon) —— 直接插值，不是 Number()，
      // 所以 40.0 会保留成 "40.0"。必须用原值字符串化，不能用一元 +。
      经纬度: (opt.lat != null) ? (pyFloatStr(opt.lat) + ", " + pyFloatStr(opt.lon)) : "未提供（无法定上升/宫位）",
    },
    天体: planets,
    轴点: angles,
    相位: asp,
    元素分布: elemCnt,
    性质分布: modCnt,
    宫位: houses,
    太阳星座: planets.find((p) => p.天体 === "太阳").星座,
    月亮星座: planets.find((p) => p.天体 === "月亮").星座,
    上升星座: angles["上升"] ? angles["上升"].星座 : "未知",
  };
}
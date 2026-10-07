/* ===================================================================
   bazi.js —— bazi.py 的 JS 移植（四柱八字）
   ===================================================================
   逐段对照 Python 版移植。Python 是唯一事实来源，本文件是第二实现，
   一致性由 web/diff_py_js.py 逐案对拍保证。

   注意 Python 语义差异全部走 kernel.js：
     - (zhi_i - 2) 在子/丑宫为负，必须 pyMod
     - round() 是银行家舍入，起运月数用它
     - 索引查找、十神五行差值都用 pyMod
   =================================================================== */

import {
  GAN, ZHI, GAN_WUXING, ZHI_WUXING, GAN_YINYANG, ZHI_CANGGAN,
  dayGz, dayGzIndex, monthGz, yearGz, yearGzIndex, gzFromIndex,
  hourGz, shichenOf, solarToLunarTuple, lunarToSolar, formatLunar,
  trueSolarTime, jdFromBj, jieEventsAround, ganzhiHourLabel, nayinOf,
} from "./almanac.js";
import { pyMod, pyRound, bjUnix, bjCivilFromUnix, jdn, civilFromJdn, pyRoundN } from "./kernel.js";

const WUXING = "木火土金水";

/* ---------------- 权重与神煞表 ---------------- */

const CANG_WEIGHT = [1.0, 0.4, 0.2];
const ZHI_POS_WEIGHT = { 年: 1.0, 月: 1.8, 日: 1.4, 时: 1.0 };
const GAN_POS_WEIGHT = { 年: 1.0, 月: 1.2, 日: 0.0, 时: 1.0 };

const TIANYI = { 甲: "丑未", 戊: "丑未", 庚: "丑未", 乙: "子申", 己: "子申",
  丙: "亥酉", 丁: "亥酉", 壬: "卯巳", 癸: "卯巳", 辛: "午寅" };
const WENCHANG = { 甲: "巳", 乙: "午", 丙: "申", 丁: "酉", 戊: "申",
  己: "酉", 庚: "亥", 辛: "子", 壬: "寅", 癸: "卯" };
const XUETANG = { 甲: "亥", 乙: "午", 丙: "寅", 丁: "酉", 戊: "寅",
  己: "酉", 庚: "巳", 辛: "子", 壬: "申", 癸: "卯" };
const LUSHEN = { 甲: "寅", 乙: "卯", 丙: "巳", 丁: "午", 戊: "巳",
  己: "午", 庚: "申", 辛: "酉", 壬: "亥", 癸: "子" };
const YANGREN = { 甲: "卯", 乙: "寅", 丙: "午", 丁: "巳", 戊: "午",
  己: "巳", 庚: "酉", 辛: "子", 壬: "子", 癸: "亥" };
const GUOYIN = { 甲: "戌", 乙: "亥", 丙: "丑", 丁: "寅", 戊: "丑",
  己: "寅", 庚: "辰", 辛: "巳", 壬: "未", 癸: "申" };
const JINYU = { 甲: "辰", 乙: "巳", 丙: "未", 丁: "申", 戊: "未",
  己: "申", 庚: "戌", 辛: "亥", 壬: "丑", 癸: "寅" };
const HONGYAN = { 甲: "午", 乙: "午", 丙: "寅", 丁: "未", 戊: "辰",
  己: "辰", 庚: "戌", 辛: "酉", 壬: "子", 癸: "申" };

const TIANDE = { 寅: ["干", "丁"], 卯: ["支", "申"], 辰: ["干", "壬"], 巳: ["干", "辛"],
  午: ["支", "亥"], 未: ["干", "甲"], 申: ["干", "癸"], 酉: ["支", "寅"],
  戌: ["干", "丙"], 亥: ["干", "乙"], 子: ["干", "己"], 丑: ["干", "庚"] };
const YUEDE = { 寅: "丙", 午: "丙", 戌: "丙", 申: "壬", 子: "壬", 辰: "壬",
  亥: "甲", 卯: "甲", 未: "甲", 巳: "庚", 酉: "庚", 丑: "庚" };

const SANHE = { 申: "水", 子: "水", 辰: "水", 寅: "火", 午: "火", 戌: "火",
  巳: "金", 酉: "金", 丑: "金", 亥: "木", 卯: "木", 未: "木" };
const YIMA = { 水: "寅", 火: "申", 金: "亥", 木: "巳" };
const TAOHUA = { 水: "酉", 火: "卯", 金: "午", 木: "子" };
const HUAGAI = { 水: "辰", 火: "戌", 金: "丑", 木: "未" };
const JIANGXING = { 水: "子", 火: "午", 金: "酉", 木: "卯" };
const JIESHA = { 水: "巳", 火: "亥", 金: "寅", 木: "申" };
const WANGSHEN = { 水: "亥", 火: "巳", 金: "申", 木: "寅" };
const ZAISHA = { 水: "午", 火: "子", 金: "卯", 木: "酉" };
const GUCHEN = { 亥: "寅", 子: "寅", 丑: "寅", 寅: "巳", 卯: "巳", 辰: "巳",
  巳: "申", 午: "申", 未: "申", 申: "亥", 酉: "亥", 戌: "亥" };
const GUASU = { 亥: "戌", 子: "戌", 丑: "戌", 寅: "丑", 卯: "丑", 辰: "丑",
  巳: "辰", 午: "辰", 未: "辰", 申: "未", 酉: "未", 戌: "未" };

/* ---------------- 五行 / 十神 ---------------- */

export function wuxingOfGan(gan) { return GAN_WUXING[GAN.indexOf(gan)]; }
export function wuxingOfZhi(zhi) { return ZHI_WUXING[ZHI.indexOf(zhi)]; }

/** 以日干为「我」，求 other_gan 的十神。 */
export function shishen(dayGan, otherGan) {
  const me = WUXING.indexOf(wuxingOfGan(dayGan));
  const meYy = GAN_YINYANG[GAN.indexOf(dayGan)] === "阳";
  const oth = WUXING.indexOf(wuxingOfGan(otherGan));
  const othYy = GAN_YINYANG[GAN.indexOf(otherGan)] === "阳";
  const same = meYy === othYy;
  const rel = pyMod(oth - me, 5);
  if (rel === 0) return same ? "比肩" : "劫财";
  if (rel === 1) return same ? "食神" : "伤官";
  if (rel === 2) return same ? "偏财" : "正财";
  if (rel === 3) return same ? "七杀" : "正官";
  return same ? "偏印" : "正印";
}

/** 旬空（以日柱查）。 */
export function kongwang(dayGzIdx) {
  const xun = Math.floor(dayGzIdx / 10);
  return ZHI[pyMod(10 - xun * 2, 12)] + ZHI[pyMod(11 - xun * 2, 12)];
}

/* ---------------- 排盘主流程 ---------------- */

export function paiPan(opt) {
  const warnings = [];
  let y, m, d, lunarInfo;

  // 1. 定公历日期
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

  // 2. 定时辰
  let hh = null, mm = null;
  if (opt.hour) {
    hh = opt.hour[0]; mm = opt.hour[1];
  } else if (opt.shichen) {
    hh = pyMod(2 * (ZHI.indexOf(opt.shichen) - 1), 24); mm = 0;
    if (opt.shichen === "子") hh = 0;
  }

  // 3. 真太阳时校正
  let tstNote = null;
  if (hh !== null && opt.longitude !== null && opt.longitude !== undefined) {
    const clock = bjUnix(y, m, d, hh, mm, 0);
    const r = trueSolarTime(clock, Number(opt.longitude));
    const tc = bjCivilFromUnix(clock), sc = bjCivilFromUnix(r.t);
    const pad = (n) => String(n).padStart(2, "0");
    tstNote = {
      钟表时: pad(tc.H) + ":" + pad(tc.Mi),
      真太阳时: pad(sc.H) + ":" + pad(sc.Mi),
      校正分钟: pyRoundN(r.offsetMin, 1),
      均时差分钟: pyRoundN(r.eot, 1),
    };
    const z1 = shichenOf(hh, mm).zhi;
    const z2 = shichenOf(sc.H, sc.Mi).zhi;
    if (z1 !== z2) {
      warnings.push("真太阳时校正后由「" + z1 + "时」跨到「" + z2
        + "时」，请以真太阳时为准并确认出生地经度。");
    }
    hh = sc.H; mm = sc.Mi;
  }

  const birthT = bjUnix(y, m, d, hh !== null ? hh : 12, mm !== null ? mm : 0, 0);
  const birthYear = bjCivilFromUnix(birthT).y;

  // 4. 四柱
  const yearPillar = yearGz(birthT, birthYear).gz;
  const mg = monthGz(birthT, birthYear);
  const monthPillar = mg.gz, monthZhi = mg.zhi, jieName = mg.name, jieStart = mg.start;

  let dayPillar, hourPillar = null, dayIdx;
  if (hh === null) {
    dayIdx = dayGzIndex(y, m, d);
    dayPillar = gzFromIndex(dayIdx);
    warnings.push("未提供出生时刻，时柱未知，仅作六字（年月日）分析。");
  } else {
    if (hh >= 23) {                       // 晚子时用次日日柱
      const nd = civilFromJdn(jdn(y, m, d) + 1);
      dayIdx = dayGzIndex(nd.y, nd.m, nd.d);
      warnings.push("出生时刻在 23:00 之后，按「晚子时」用次日日柱。");
    } else {
      dayIdx = dayGzIndex(y, m, d);
    }
    dayPillar = gzFromIndex(dayIdx);
    const sc = shichenOf(hh, mm);
    hourPillar = hourGz(dayPillar[0], sc.idx);
  }

  // 节气交界提示
  const secsToJie = Math.abs(birthT - jieStart);
  if (secsToJie <= 6 * 3600) {
    warnings.push("出生时刻距「" + jieName + "」仅 " + (secsToJie / 3600).toFixed(1)
      + " 小时，处于节气交界，月柱对时刻高度敏感，请核对出生时间。");
  }
  for (const ev of jieEventsAround(y)) {
    if (ev.name === "立春" && Math.abs(birthT - ev.t) <= 6 * 3600) {
      warnings.push("出生时刻距「立春」仅 " + (Math.abs(birthT - ev.t) / 3600).toFixed(1)
        + " 小时，年柱归属临界，请核对出生时间。");
    }
  }

  const pillars = [["年", yearPillar], ["月", monthPillar], ["日", dayPillar]];
  if (hourPillar) pillars.push(["时", hourPillar]);
  const dayGan = dayPillar[0];

  // 5. 十神 / 藏干 / 纳音
  const detail = pillars.map(([pos, gz]) => {
    const g = gz[0], z = gz[1];
    return {
      柱: pos, 干: g, 支: z,
      干十神: pos === "日" ? "日主" : shishen(dayGan, g),
      支藏干: ZHI_CANGGAN[z].map((c) => ({ 干: c, 十神: shishen(dayGan, c) })),
      纳音: nayinOf(g, z),
      五行: wuxingOfGan(g) + wuxingOfZhi(z),
    };
  });

  // 6. 五行力量
  const score = {};
  for (const w of WUXING) score[w] = 0.0;
  for (const [pos, gz] of pillars) {
    const g = gz[0], z = gz[1];
    score[wuxingOfGan(g)] += GAN_POS_WEIGHT[pos];
    ZHI_CANGGAN[z].forEach((c, i) => {
      score[wuxingOfGan(c)] += CANG_WEIGHT[i] * ZHI_POS_WEIGHT[pos];
    });
  }
  let total = 0;
  for (const w of WUXING) total += score[w];
  if (!total) total = 1.0;
  const wuxingPct = {};
  for (const w of WUXING) wuxingPct[w] = pyRoundN(score[w] / total * 100, 1);

  // 7. 日主强弱
  const meWx = wuxingOfGan(dayGan);
  const meI = WUXING.indexOf(meWx);
  const shengMe = WUXING[pyMod(meI + 4, 5)];
  const tongdang = score[meWx] + score[shengMe];
  const ratio = tongdang / total;
  let strength;
  if (ratio >= 0.62) strength = "身强";
  else if (ratio >= 0.55) strength = "偏强";
  else if (ratio >= 0.45) strength = "中和";
  else if (ratio >= 0.38) strength = "偏弱";
  else strength = "身弱";
  const xiyong = ratio >= 0.5
    ? [WUXING[pyMod(meI + 1, 5)], WUXING[pyMod(meI + 2, 5)], WUXING[pyMod(meI + 3, 5)]]
    : [meWx, shengMe];

  // 8. 格局
  const monthMain = ZHI_CANGGAN[monthZhi][0];
  const gejuSs = shishen(dayGan, monthMain);
  const geju = (gejuSs !== "比肩" && gejuSs !== "劫财") ? gejuSs + "格" : "建禄/月劫格";
  const tou = pillars.filter((p) => p[0] !== "日").map((p) => p[1][0]);
  const gejuTou = tou.map((t) => shishen(dayGan, t)).includes(shishen(dayGan, monthMain));

  // 9. 神煞
  const yearZhi = pillars[0][1][1];
  const ju = SANHE[yearZhi];
  const allZhi = pillars.map((p) => p[1][1]);
  const shensha = [];
  const hit = (name, target, basis, note) => {
    const found = pillars.filter((p) => p[1][1] === target).map((p) => p[0]);
    if (found.length) {
      shensha.push({ 神煞: name, 查法: basis, 落支: target,
                     位置: found.join("、") + "柱", 说明: note || "" });
    }
  };

  for (const g of [dayGan, pillars[0][1][0]]) {
    for (const z of TIANYI[g]) hit("天乙贵人", z, "日/年干" + g, "贵人助力、逢凶化吉");
  }
  for (const z of WENCHANG[dayGan]) hit("文昌贵人", z, "日干" + dayGan, "聪颖好学、利文书考试");
  for (const z of XUETANG[dayGan]) hit("学堂", z, "日干" + dayGan, "学业有成、宜求学");
  for (const z of LUSHEN[dayGan]) hit("禄神", z, "日干" + dayGan, "衣食丰足、有独立之财");
  for (const z of YANGREN[dayGan]) hit("羊刃", z, "日干" + dayGan, "刚烈果决，宜防冲动");
  for (const z of GUOYIN[dayGan]) hit("国印贵人", z, "日干" + dayGan, "掌权柄、利公职");
  for (const z of JINYU[dayGan]) hit("金舆", z, "日干" + dayGan, "配偶贤、有车马之福");
  for (const z of HONGYAN[dayGan]) hit("红艳煞", z, "日干" + dayGan, "多情浪漫、异性缘旺");
  hit("驿马", YIMA[ju], "年支三合" + ju + "局", "奔波变动、宜外出发展");
  hit("桃花（咸池）", TAOHUA[ju], "年支三合" + ju + "局", "异性缘、人缘魅力");
  hit("华盖", HUAGAI[ju], "年支三合" + ju + "局", "孤高清雅、有宗教艺术缘");
  hit("将星", JIANGXING[ju], "年支三合" + ju + "局", "领导统御、掌权");
  hit("劫煞", JIESHA[ju], "年支三合" + ju + "局", "宜防破耗、竞争");
  hit("亡神", WANGSHEN[ju], "年支三合" + ju + "局", "心思深沉、宜防口舌");
  hit("灾煞", ZAISHA[ju], "年支三合" + ju + "局", "宜防意外");
  hit("孤辰", GUCHEN[yearZhi], "年支" + yearZhi, "性喜独处");
  hit("寡宿", GUASU[yearZhi], "年支" + yearZhi, "情感上易孤独");
  const td = TIANDE[monthZhi];
  const allGan = pillars.map((p) => p[1][0]);
  if (td[0] === "干" && allGan.includes(td[1])) {
    shensha.push({ 神煞: "天德贵人", 查法: "月支" + monthZhi, 落支: td[1],
                   位置: "天干", 说明: "福德深厚、遇难成祥" });
  } else if (td[0] === "支" && allZhi.includes(td[1])) {
    shensha.push({ 神煞: "天德贵人", 查法: "月支" + monthZhi, 落支: td[1],
                   位置: "地支", 说明: "福德深厚、遇难成祥" });
  }
  const yd = YUEDE[monthZhi];
  if (allGan.includes(yd)) {
    shensha.push({ 神煞: "月德贵人", 查法: "月支" + monthZhi, 落支: yd,
                   位置: "天干", 说明: "慈祥厚德、贵人相扶" });
  }

  const kw = kongwang(dayIdx);

  // 10. 大运
  const yGan = yearPillar[0];
  const yangYear = GAN_YINYANG[GAN.indexOf(yGan)] === "阳";
  const sex = opt.sex || "男";
  const forward = (yangYear && sex === "男") || (!yangYear && sex === "女");
  const events = jieEventsAround(birthYear);
  let deltaDays;
  if (forward) {
    let nxt = events[events.length - 1];
    for (const e of events) if (e.t > birthT) { nxt = e; break; }
    deltaDays = (nxt.t - birthT) / 86400.0;
  } else {
    let prv = null;
    for (const e of events) { if (e.t <= birthT) prv = e; else break; }
    if (!prv) prv = events[0];
    deltaDays = (birthT - prv.t) / 86400.0;
  }
  const qiyunYearsF = deltaDays / 3.0;
  let qy = Math.trunc(qiyunYearsF);
  let qm = pyRound((qiyunYearsF - qy) * 12);      // Python round()：银行家舍入
  if (qm >= 12) { qy += 1; qm -= 12; }

  let mIdx = 0;
  for (let n = 0; n < 60; n++) {
    if (GAN[n % 10] === monthPillar[0] && ZHI[n % 12] === monthPillar[1]) { mIdx = n; break; }
  }
  const dayun = [];
  const startAge = qiyunYearsF;
  for (let step = 1; step <= 10; step++) {
    const idx = forward ? pyMod(mIdx + step, 60) : pyMod(mIdx - step, 60);
    const gz = gzFromIndex(idx);
    const a0 = startAge + (step - 1) * 10;
    const a1 = a0 + 10;
    dayun.push({
      序: step, 干支: gz, 十神: shishen(dayGan, gz[0]),
      起始虚岁: pyRoundN(a0, 1), 结束虚岁: pyRoundN(a1, 1),
      起始公历: y + Math.trunc(a0),
    });
  }

  // 11. 流年
  const curYear = opt.nowYear || 2026;
  const yy0 = opt.deceasedYear
    ? Math.min(curYear, Math.trunc(opt.deceasedYear)) : curYear;
  const liunian = [];
  for (let yy = yy0 - 3; yy < yy0 + 4; yy++) {
    if (opt.deceasedYear && yy > Math.trunc(opt.deceasedYear)) break;
    const gz = gzFromIndex(yearGzIndex(yy));
    const age = yy - yearGz(birthT, birthYear).year + 1;
    const dy = dayun.find((d) => d.起始虚岁 <= age - 1 && age - 1 < d.结束虚岁);
    liunian.push({ 年: yy, 干支: gz, 十神: shishen(dayGan, gz[0]), 虚岁: age,
                   大运: dy ? dy.干支 : "" });
  }

  const pad2 = (n) => String(n).padStart(2, "0");
  return {
    输入: {
      // Python 是 "%04d-%02d-%02d"：年补 4 位、月日各补 2 位，宽度是固定的，
      // 不能按数值大小猜（否则 5 月会补成 005）。
      公历: String(y).padStart(4, "0") + "-" + pad2(m) + "-" + pad2(d),
      农历: formatLunar(lunarInfo[0], lunarInfo[1], lunarInfo[2], lunarInfo[3]),
      时辰: hourPillar
        ? hourPillar[1] + "时(" + ganzhiHourLabel(hourPillar[1]) + ")"
        : "未知",
      性别: sex,
      出生地: opt.place || "未提供",
      真太阳时: tstNote,
    },
    四柱: { 年: yearPillar, 月: monthPillar, 日: dayPillar, 时: hourPillar || "未知" },
    日主: { 干: dayGan, 五行: meWx, 阴阳: GAN_YINYANG[GAN.indexOf(dayGan)] },
    柱详解: detail,
    五行统计: wuxingPct,
    日主强弱: { 判定: strength, 同党占比: pyRoundN(ratio * 100, 1),
                喜用神: xiyong, 说明: "同党=比劫+印星，占比越高日主越强" },
    格局: { 名: geju, 月令本气: monthMain, 是否透干: gejuTou },
    旬空: kw,
    神煞: shensha,
    大运: { 顺逆: forward ? "顺排" : "逆排",
            起运: qy + "年" + qm + "个月",
            起运虚岁: pyRoundN(qiyunYearsF, 2), 列表: dayun },
    流年: liunian,
    警告: warnings,
    当前时间: String(yy0).padStart(4, "0"),
  };
}
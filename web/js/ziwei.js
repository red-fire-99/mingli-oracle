/* ===================================================================
   ziwei.js —— ziwei.py 的 JS 移植（紫微斗数命盘）
   ===================================================================
   逐段对照 Python 版。一致性由 web/diff_py_js.py 保证。

   特别注意两处 Python 语义：
   - 宫位天干五虎遁的 (zhi_i - 2) 在子/丑宫为负，必须 pyMod(x, 12)
   - sorted(stars[idx]) 是**按 Unicode 码位**排序，JS 的 Array.sort 默认也是
     按 UTF-16 码位，对中文星名与 Python 的结果一致
   =================================================================== */

import {
  GAN, ZHI, GAN_YINYANG, YUE_GAN_YIN,
  solarToLunarTuple, lunarToSolar, formatLunar, nayinWuxing,
} from "./almanac.js";
import { pyMod } from "./kernel.js";

export const GONG_NAMES = ["命宫", "兄弟", "夫妻", "子女", "财帛", "疾厄",
  "迁移", "交友", "官禄", "田宅", "福德", "父母"];

const JU_TABLE = { 水: 2, 木: 3, 金: 4, 土: 5, 火: 6 };
const JU_NAME = { 2: "水二局", 3: "木三局", 4: "金四局", 5: "土五局", 6: "火六局" };

const ZIWEI_SERIES = [["紫微", 0], ["天机", -1], ["太阳", -3], ["武曲", -4], ["天同", -5], ["廉贞", -8]];
const TIANFU_SERIES = [["天府", 0], ["太阴", 1], ["贪狼", 2], ["巨门", 3],
  ["天相", 4], ["天梁", 5], ["七杀", 6], ["破军", 10]];

// 四化：年干 → [禄, 权, 科, 忌]
const SIHUA = {
  甲: ["廉贞", "破军", "武曲", "太阳"],
  乙: ["天机", "天梁", "紫微", "太阴"],
  丙: ["天同", "天机", "文昌", "廉贞"],
  丁: ["太阴", "天同", "天机", "巨门"],
  戊: ["贪狼", "太阴", "右弼", "天机"],
  己: ["武曲", "贪狼", "天梁", "文曲"],
  庚: ["太阳", "武曲", "太阴", "天同"],
  辛: ["巨门", "太阳", "文曲", "文昌"],
  壬: ["天梁", "紫微", "左辅", "武曲"],
  癸: ["破军", "巨门", "太阴", "贪狼"],
};

const TIANKUI = { 甲: ["丑", "未"], 戊: ["丑", "未"], 庚: ["丑", "未"],
  乙: ["子", "申"], 己: ["子", "申"],
  丙: ["亥", "酉"], 丁: ["亥", "酉"],
  壬: ["卯", "巳"], 癸: ["卯", "巳"], 辛: ["午", "寅"] };

const LUCUN = { 甲: "寅", 乙: "卯", 丙: "巳", 丁: "午", 戊: "巳",
  己: "午", 庚: "申", 辛: "酉", 壬: "亥", 癸: "子" };

const HUOXING_START = { 申: "寅", 子: "寅", 辰: "寅", 寅: "丑", 午: "丑", 戌: "丑",
  巳: "卯", 酉: "卯", 丑: "卯", 亥: "酉", 卯: "酉", 未: "酉" };
const LINGXING_START = { 申: "戌", 子: "戌", 辰: "戌", 寅: "卯", 午: "卯", 戌: "卯",
  巳: "戌", 酉: "戌", 丑: "戌", 亥: "戌", 卯: "戌", 未: "戌" };
const TIANMA = { 水: "寅", 火: "申", 金: "亥", 木: "巳" };
const SANHE_JU = { 申: "水", 子: "水", 辰: "水", 寅: "火", 午: "火", 戌: "火",
  巳: "金", 酉: "金", 丑: "金", 亥: "木", 卯: "木", 未: "木" };

export const STAR_BRIEF = {
  紫微: "帝王之星，尊贵统御，喜居高位",
  天机: "智慧谋略，机变善思，多动少静",
  太阳: "光明博爱，施予奉献，利男性长辈",
  武曲: "财星刚毅，执行力强，重原则",
  天同: "福星温和，知足随和，喜安逸",
  廉贞: "次桃花，囚星，才情与规矩的张力",
  天府: "库星稳健，包容持重，善守成",
  太阴: "月亮柔情，细腻内敛，利女性长辈",
  贪狼: "正桃花，多才多欲，交际力强",
  巨门: "暗星口舌，善辩研究，宜专业立身",
  天相: "印星辅佐，忠厚公正，重体面",
  天梁: "荫星长辈，慈悲正直，善解厄",
  七杀: "将星开创，果决肃杀，起伏大",
  破军: "耗星变革，破旧立新，敢冲敢闯",
};

function zhiIdx(z) { return ZHI.indexOf(z); }

/** 由五行局数与农历生日定紫微星地支索引。 */
export function anZiwei(ju, day) {
  if (day % ju === 0) return pyMod(2 + (day / ju) - 1, 12);
  const n = Math.floor(day / ju) + 1;
  const rem = n * ju - day;
  return rem % 2 === 0 ? pyMod(2 + n - 1 + rem, 12) : pyMod(2 + n - 1 - rem, 12);
}

export function paiPan(opt) {
  const warnings = [];
  let y, m, d, ly, lm, ld, leap;
  if (opt.solar) {
    [y, m, d] = opt.solar;
    [ly, lm, ld, leap] = solarToLunarTuple(y, m, d);
  } else if (opt.lunar) {
    [ly, lm, ld] = opt.lunar;
    leap = Boolean(opt.leap);
    const dt = lunarToSolar(ly, lm, ld, leap);
    y = dt.y; m = dt.m; d = dt.d;
  } else {
    throw new Error("必须提供 solar 或 lunar");
  }

  let hh = null;
  if (opt.hour != null) {
    hh = typeof opt.hour === "number" ? opt.hour : opt.hour[0];
  } else if (opt.shichen) {
    hh = pyMod(2 * (ZHI.indexOf(opt.shichen) - 1), 24);
    if (opt.shichen === "子") hh = 0;
  } else {
    warnings.push("未提供出生时刻，按子时（0点）排盘，结果可能偏差，请补全时辰。");
  }

  const hourIdx = hh === null ? 0 : pyMod(Math.floor((hh + 1) / 2), 12);
  if (leap) warnings.push("生于闰月：本盘按「闰月归本月」处理（另有归下月流派），如需可注明。");

  // 1. 命宫 / 身宫
  const month = lm;
  const mingIdx = pyMod(2 + (month - 1) - hourIdx, 12);
  const shenIdx = pyMod(2 + (month - 1) + hourIdx, 12);

  // 2. 年干支
  const yearGan = GAN[pyMod(ly - 4, 10)];
  const yearZhi = ZHI[pyMod(ly - 4, 12)];

  // 3. 宫位天干（五虎遁，地支偏移用 %12）
  const yg = GAN.indexOf(yearGan);
  const gongGan = (zhiI) => GAN[pyMod(YUE_GAN_YIN[yg] + pyMod(zhiI - 2, 12), 10)];

  const mingGan = gongGan(mingIdx);

  // 4. 五行局
  const juWx = nayinWuxing(mingGan, ZHI[mingIdx]);
  const ju = JU_TABLE[juWx];

  // 5. 安紫微 / 天府
  const ziweiIdx = anZiwei(ju, ld);
  const tianfuIdx = pyMod(4 - ziweiIdx, 12);

  const stars = {};
  for (let i = 0; i < 12; i++) stars[i] = [];
  const putStar = (name, idx) => { stars[pyMod(idx, 12)].push(name); };

  for (const [name, off] of ZIWEI_SERIES) putStar(name, ziweiIdx + off);
  for (const [name, off] of TIANFU_SERIES) putStar(name, tianfuIdx + off);

  // 6. 辅星煞星
  putStar("左辅", 4 + (month - 1));
  putStar("右弼", 10 - (month - 1));
  putStar("文昌", 10 - hourIdx);
  putStar("文曲", 4 + hourIdx);
  const [kui, yue] = TIANKUI[yearGan];
  putStar("天魁", zhiIdx(kui));
  putStar("天钺", zhiIdx(yue));
  const luI = zhiIdx(LUCUN[yearGan]);
  putStar("禄存", luI);
  putStar("擎羊", luI + 1);
  putStar("陀罗", luI - 1);
  const hx = zhiIdx(HUOXING_START[yearZhi]);
  putStar("火星", hx + hourIdx);
  const lx = zhiIdx(LINGXING_START[yearZhi]);
  putStar("铃星", lx + hourIdx);
  putStar("地空", 11 - hourIdx);
  putStar("地劫", 11 + hourIdx);
  putStar("天马", zhiIdx(TIANMA[SANHE_JU[yearZhi]]));

  // 7. 四化（在星名后加 ·化X）
  const hua = SIHUA[yearGan];
  const huaMap = {};
  const kinds = ["禄", "权", "科", "忌"];
  for (let i = 0; i < hua.length; i++) {
    const star = hua[i], kind = kinds[i];
    huaMap[star] = kind;
    for (let k = 0; k < 12; k++) {
      if (stars[k].includes(star)) {
        stars[k] = stars[k].map((s) => (s === star ? s + "·化" + kind : s));
      }
    }
  }

  // 8. 十二宫（从命宫起逆排）
  const palaces = [];
  for (let k = 0; k < 12; k++) {
    const idx = pyMod(mingIdx - k, 12);
    palaces.push({
      宫名: GONG_NAMES[k],
      地支: ZHI[idx],
      天干: gongGan(idx),
      星曜: stars[idx].slice().sort(),
      主星: stars[idx].filter((s) => s.split("·")[0] in STAR_BRIEF),
      是否命宫: k === 0,
      是否身宫: idx === shenIdx,
    });
  }

  // 9. 大限
  const yangYear = GAN_YINYANG[GAN.indexOf(yearGan)] === "阳";
  const sex = opt.sex || "男";
  const forward = (yangYear && sex === "男") || (!yangYear && sex === "女");
  const dayun = [];
  for (let k = 0; k < 12; k++) {
    const idx = forward ? pyMod(mingIdx + k, 12) : pyMod(mingIdx - k, 12);
    const startAge = ju + k * 10;
    dayun.push({
      宫位: idx === mingIdx ? GONG_NAMES[0] : palaces[pyMod(mingIdx - idx, 12)].宫名,
      地支: ZHI[idx], 天干: gongGan(idx),
      虚岁起: startAge, 虚岁止: startAge + 9,
      星曜: stars[idx].slice().sort(),
    });
  }

  // 10. 流年
  const curYear = opt.year || 2026;
  const lnZhiI = pyMod(curYear - 4, 12);
  const lnGan = GAN[pyMod(curYear - 4, 10)];
  const lnPalaces = [];
  for (let k = 0; k < 12; k++) {
    const idx = pyMod(lnZhiI - k, 12);
    lnPalaces.push({ 宫名: GONG_NAMES[k], 地支: ZHI[idx],
                     星曜: stars[idx].slice().sort(), 是否流年命宫: k === 0 });
  }
  const curAge = curYear - ly + 1;
  const curDayun = dayun.find((x) => x.虚岁起 <= curAge && curAge <= x.虚岁止);

  const pad2 = (n) => String(n).padStart(2, "0");
  return {
    输入: {
      公历: String(y).padStart(4, "0") + "-" + pad2(m) + "-" + pad2(d),
      农历: formatLunar(ly, lm, ld, leap),
      时辰: hh !== null ? ZHI[hourIdx] + "时" : "子时(默认)",
      性别: sex, 出生地: opt.place || "未提供",
      年干支: yearGan + yearZhi,
    },
    命宫: { 地支: ZHI[mingIdx], 天干: mingGan },
    身宫: { 地支: ZHI[shenIdx], 天干: gongGan(shenIdx) },
    五行局: JU_NAME[ju],
    紫微星: ZHI[ziweiIdx] + "宫",
    天府星: ZHI[tianfuIdx] + "宫",
    十二宫: palaces,
    四化: { 年干: yearGan, 化禄: hua[0], 化权: hua[1], 化科: hua[2], 化忌: hua[3] },
    大限: { 顺逆: forward ? "顺行" : "逆行", 起运虚岁: ju, 列表: dayun },
    流年: {
      年: curYear, 干支: lnGan + ZHI[lnZhiI], 虚岁: curAge,
      流年命宫: ZHI[lnZhiI] + "宫",
      当前大限: curDayun ? curDayun.宫位 + "·" + curDayun.地支 : "",
    },
    警告: warnings,
  };
}
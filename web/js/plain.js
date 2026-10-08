/* ===================================================================
   plain.js —— plain.py 中 6 个函数的 JS 移植（白话解读）
   ===================================================================
   plain.py 有 897 行，但其中 31 个模块级字典（约七成）已由
   web/gen_plain_json.py 机器导出为 plain-data.json，无需手抄。
   本文件只移植剩下的 6 个函数：
     _pick / bazi_plain / ziwei_plain / astro_plain / headline / glossaryHtml

   注意 Python 与 JS 的取字典默认值写法不同（d.get(k, default) vs ?? ），
   以及 max/min 的并列处理：Python 的 max 取**首次出现**的最大值，
   JS 的 Math.max.apply 同样取首次 —— 行为一致，但插入顺序不能变。
   =================================================================== */

import DATA from "./plain-data.json" with { type: "json" };

const {
  DAY_MASTER, STRENGTH, SHISHEN, ZIWEI_STAR, SHENSHA,
  WUXING_HIGH, WUXING_LOW, WUXING_LUCK, ZHI_TO_SX, SHENGXIAO,
  SIGN_PROFILE, DAYUN_THEME, SUN_SIGN, MOON_SIGN, ASC_SIGN,
  MERCURY_SIGN, VENUS_SIGN, MARS_SIGN, PLANET_ROLE,
  HOUSE_MEANING, HOUSE_BY_PLANET, ASPECT_TRAIT,
  SUN_KEYWORD, MOON_KEYWORD, ASC_KEYWORD, ELEMENT_MORE, ELEMENT_MISS,
  RULER, GLOSSARY,
  DAYUN_DETAIL, LIUNIAN_DETAIL, TWELVE_STAGES, LONG_ZHI,
  STAGE_MEAN, WUXING_IMAGERY, ELEMENT_CROSS,
} = DATA;

/* ------------------------------------------------------------------
   十二长生：日干在某一步大运干上处于第几格。

   与 plain.py 的 stage_of_dayun 同构。刻度是**地支**不是天干 ——
   一开始误写成「按天干五行相生相克推 1 步或 2 步」，
   结果只能落在 5 格里，自检里「必须覆盖 12 格」直接抓出来。

   python 里靠 from almanac import GAN/ZHI 拿顺序；JS 侧 kernel.js
   已有同样的 GAN / ZHI 数组，直接用。
   ------------------------------------------------------------------ */
const GAN = ["甲","乙","丙","丁","戊","己","庚","辛","壬","癸"];
const ZHI = ["子","丑","寅","卯","辰","巳","午","未","申","酉","戌","亥"];
const GAN_YINYANG = ["阳","阴","阳","阴","阳","阴","阳","阴","阳","阴"];

function stageOfDayun(dayGan, dayunGan) {
  const meY = GAN_YINYANG[GAN.indexOf(dayGan)] === "阳";
  const dyY = GAN_YINYANG[GAN.indexOf(dayunGan)] === "阳";
  const meStart = ZHI.indexOf(LONG_ZHI[dayGan]);
  const dyStart = ZHI.indexOf(LONG_ZHI[dayunGan]);
  let delta = (dyStart - meStart + 12) % 12;
  if (meY !== dyY) delta = (12 - delta) % 12;   // 异阴阳逆行
  return TWELVE_STAGES[delta];
}

/* 五行意象：把五行统计翻成「哪股劲儿最足 / 最缺」。 */
function wuxingImagery(stat, xiyong) {
  if (!stat) return { strong: null, weak: null, items: [] };
  const keys = Object.keys(stat);
  if (!keys.length) return { strong: null, weak: null, items: [] };
  let total = 0;
  for (const k of keys) if (stat[k] > 0) total += stat[k];
  if (total <= 0) total = 1;
  const xyd = xiyong || [];
  const items = keys.map((k) => {
    const info = WUXING_IMAGERY[k] || {};
    return {
      "五行": k, "象": info["象"] || "",
      "占比": Math.round(stat[k] / total * 1000) / 10,
      "力量": stat[k],
      "描述": info["描述"] || "",
      "偏多时": info["多"] || "", "偏少时": info["少"] || "",
      "是喜用": xyd.indexOf(k) >= 0,
    };
  });
  // Python 的 sort(key=lambda x: -x["力量"]) 是稳定排序，
  // JS 的 sort 不保证稳定 —— 所以自己插入排序，保持与 Python 完全一致。
  const sorted = items.slice();
  for (let i = 1; i < sorted.length; i++) {
    const cur = sorted[i];
    let j = i - 1;
    while (j >= 0 && sorted[j]["力量"] < cur["力量"]) { sorted[j + 1] = sorted[j]; j--; }
    sorted[j + 1] = cur;
  }
  const strong = sorted[0] || null;
  let weak = sorted.length > 1 ? sorted[sorted.length - 1] : null;
  if (weak && weak["力量"] <= 0) weak = null;
  return { strong, weak, items: sorted };
}

/** Python 的 dict.get(k, default)。 */
function pick(d, k, dflt = null) {
  return (d && k in d) ? d[k] : dflt;
}

/** Python 的 max(d, key=d.get) —— 取首次出现的最大值。 */
function maxByKey(d) {
  const ks = Object.keys(d);
  let best = ks[0];
  for (const k of ks) if (d[k] > d[best]) best = k;
  return best;
}
function minByKey(d) {
  const ks = Object.keys(d);
  let best = ks[0];
  for (const k of ks) if (d[k] < d[best]) best = k;
  return best;
}

export { GLOSSARY };

/* ---------------- 八字白话 ---------------- */

export function baziPlain(r) {
  const dm = r.日主.干;
  const [archetype, oneLine, detail] = DAY_MASTER[dm];

  const strength = r.日主强弱.判定;
  const [sHead, sBody] = STRENGTH[strength];

  // 十神标签（取透干的，最多 3 个）
  const tags = [];
  const seen = new Set();
  for (const d of r.柱详解) {
    if (d.柱 === "日") continue;
    const ss = d.干十神;
    if (ss in SHISHEN && !seen.has(ss)) { seen.add(ss); tags.push([ss, SHISHEN[ss]]); }
  }
  const tagsTop = tags.slice(0, 3);

  // 五行
  const pct = r.五行统计;
  const top = maxByKey(pct);
  const low = minByKey(pct);
  let wuxingTxt = "你的「" + top + "」最旺，说明你" + WUXING_HIGH[top] + "。";
  if (pct[low] < 8) wuxingTxt += "「" + low + "」偏少，" + WUXING_LOW[low] + "。";

  // 神煞
  const lucky = [];
  const lseen = new Set();
  for (const x of r.神煞) {
    const info = pick(SHENSHA, x.神煞);
    if (info && !lseen.has(info[0])) { lseen.add(info[0]); lucky.push(info); }
  }
  const luckyTop = lucky.slice(0, 4);

  // 当前大运：取「大运自身」的十神，不能用流年十神
  let dayunNow = null;
  const curYear = parseInt(pick(r, "当前时间", "2026"), 10);
  let curLn = (r.流年 || []).find((x) => x.年 === curYear);
  if (!curLn && r.流年 && r.流年.length) curLn = r.流年[Math.floor(r.流年.length / 2)];
  if (curLn && curLn.大运) {
    const gz = curLn.大运;
    const dy = r.大运.列表.find((d) => d.干支 === gz);
    const ss = dy ? dy.十神 : "";
    dayunNow = { 干支: gz, 十神: ss, 主题: pick(DAYUN_THEME, ss, "平稳过渡"), 年份: curYear };
  }

  const summary = "你的底子是「" + archetype + "」型的人——" + oneLine;

  // 生肖
  let shengxiao = null;
  const yz = r.四柱.年;
  if (yz && yz !== "未知") {
    const sxName = pick(ZHI_TO_SX, yz[1]);
    if (sxName && sxName in SHENGXIAO) {
      const [trait, sColors, sNums] = SHENGXIAO[sxName];
      shengxiao = { 生肖: sxName, 特质: trait, 幸运色: sColors, 幸运数字: sNums };
    }
  }

  // 开运指南：按喜用神给可落地建议
  let luck = null;
  const xiyong = r.日主强弱.喜用神 || [];
  if (xiyong.length) {
    const buckets = { 颜色: [], 方位: [], 数字: [], 行业: [], 饰品: [], 日常: [] };
    for (const wx of xiyong) {
      const d = pick(WUXING_LUCK, wx);
      if (!d) continue;
      for (const k of Object.keys(buckets)) buckets[k].push(d[k]);
    }
    luck = { 五行: xiyong.join("、") };
    for (const k of Object.keys(buckets)) luck[k] = buckets[k].join("；");
  }

  // 大运逐段解读：10 步，每步带主题/正面/提醒 + 十二长生调子
  const dayGan = r.日主.干;
  const dayunFull = r.大运.列表.map((x) => {
    const ss = x.十神;
    const det = pick(DAYUN_DETAIL, ss) || {};
    const stage = x.干支 !== "未知" ? stageOfDayun(dayGan, x.干支[0]) : "";
    return {
      "序": x.序, "干支": x.干支, "十神": ss,
      "起始虚岁": x.起始虚岁, "结束虚岁": x.结束虚岁,
      "主题": det["主题"] || pick(DAYUN_THEME, ss) || "平稳过渡",
      "正面": det["正面"] || "",
      "提醒": det["提醒"] || "",
      "长生": stage,
      "长生含义": pick(STAGE_MEAN, stage) || "",
      "是当前": !!(dayunNow && dayunNow.干支 === x.干支),
    };
  });

  // 流年逐年解读
  const liunianFull = r.流年.map((x) => ({
    "年": x.年, "干支": x.干支, "十神": x.十神, "虚岁": x.虚岁,
    "大运": x.大运 || "",
    "解读": pick(LIUNIAN_DETAIL, x.十神) || "平顺的一年，按自己的节奏走。",
    "是今年": x.年 === curYear,
  }));

  // 五行意象：哪股劲儿最足、哪股最缺
  const wxImg = wuxingImagery(r.五行统计 || {}, (r.日主强弱 || {}).喜用神 || []);

  return {
    一句话: summary,
    性格底色: { 标题: "你的性格底色", 要点: oneLine, 补充: detail },
    做事方式: { 标题: "你的做事方式", 要点: sHead, 补充: sBody },
    天生擅长: { 标题: "你天生擅长什么",
                标签: tagsTop.map((t) => ({ 名: t[1][0], 说明: t[1][1] })) },
    能量分布: { 标题: "你的能量分布", 要点: wuxingTxt, 喜用: r.日主强弱.喜用神 },
    运气加成: { 标题: "你的运气加成",
                标签: luckyTop.map((t) => ({ 名: t[0], 说明: t[1] })) },
    生肖: shengxiao,
    开运指南: luck,
    当前阶段: dayunNow,
    大运详批: { 标题: "你一生十步大运", 列表: dayunFull },
    流年详批: { 标题: "未来七年的年度节奏", 列表: liunianFull },
    五行意象: { 标题: "你身上五股的劲儿",
                最强: wxImg.strong, 最弱: wxImg.weak, 明细: wxImg.items },
    术语: [["日主", GLOSSARY["日主/日干"]], ["十神", GLOSSARY["十神"]],
           ["大运", GLOSSARY["大运"]], ["神煞", GLOSSARY["神煞"]],
           ["喜用神", GLOSSARY["喜用神"]]],
  };
}

/* ---------------- 紫微白话 ---------------- */

const OPPOSITE = { 子: "午", 丑: "未", 寅: "申", 卯: "酉", 辰: "戌", 巳: "亥",
                   午: "子", 未: "丑", 申: "寅", 酉: "卯", 戌: "辰", 亥: "巳" };

export function ziweiPlain(r) {
  const ming = (r.十二宫 || []).find((p) => p.是否命宫);
  const stars = ming ? ming.星曜.map((s) => s.split("·")[0]) : [];
  const mains = stars.filter((s) => s in ZIWEI_STAR);

  let summary;
  if (mains.length) {
    const head = ZIWEI_STAR[mains[0]].核心;
    summary = "你的命宫主星是「" + mains[0] + "」——" + head[0] + "，" + head[1] + "。";
  } else {
    const oz = ming ? (OPPOSITE[ming.地支] || "") : "";
    const op = (r.十二宫 || []).find((p) => p.地支 === oz);
    const opMains = op ? op.星曜.map((s) => s.split("·")[0]).filter((s) => s in ZIWEI_STAR) : [];
    if (opMains.length) {
      summary = "你的命宫是「空宫」，要借对宫的「" + opMains[0]
        + "」来论——" + ZIWEI_STAR[opMains[0]].核心[0] + "，" + ZIWEI_STAR[opMains[0]].核心[1] + "。";
      // Python 侧这里会把 mains 重新赋成对宫主星，主星字段要跟着变
      mains.length = 0;
      mains.push(...opMains);
    } else {
      summary = "你的命宫是空宫，性格可塑性很强，环境对你的影响比较大。";
    }
  }

  // 注意：紫微的宫名字段是「宫名」，不是「宫位」
  const palaceStars = (name) => {
    const p = (r.十二宫 || []).find((x) => x.宫名 === name);
    return p ? p.星曜.map((s) => s.split("·")[0]).filter((s) => s in ZIWEI_STAR) : [];
  };
  const career = palaceStars("官禄");
  const wealth = palaceStars("财帛");
  const love = palaceStars("夫妻");

  const brief = (list, dim, dflt) => {
    if (!list.length) return dflt;
    const s = list[0];
    return "「" + s + "」——" + ZIWEI_STAR[s].核心[1] + "，" + ZIWEI_STAR[s][dim];
  };

  const h = r.四化;
  const huaNote = "生年四化中，你的「" + h.化忌 + "」化忌——这一块是你这辈子要重点面对的课题；"
    + "「" + h.化禄 + "」化禄——这一块天生有福气、有资源。";

  const juWx = (r.五行局 || "").slice(0, 1);
  let juLuck = null;
  if (juWx in WUXING_LUCK) {
    juLuck = Object.assign({ 五行: juWx, 局: r.五行局 }, WUXING_LUCK[juWx]);
  }

  return {
    一句话: summary,
    主星: mains.length ? mains[0] : null,
    事业方向: { 标题: "事业方向",
               要点: brief(career, "事业", "官禄宫无主星，事业方向灵活，跟着兴趣走就好。") },
    财运模式: { 标题: "财运模式",
               要点: brief(wealth, "财运", "财帛宫无主星，财运随大环境起伏，宜稳不宜赌。") },
    感情模式: { 标题: "感情模式",
               要点: brief(love, "感情", "夫妻宫无主星，感情模式偏自由，随缘而遇。") },
    四化提醒: { 标题: "人生课题与福气", 要点: huaNote },
    开运指南: juLuck,
    术语: [["命宫", GLOSSARY["命宫"]], ["主星", GLOSSARY["主星"]],
           ["四化", GLOSSARY["四化"]], ["大限", GLOSSARY["大限"]]],
  };
}

/* ---------------- 占星白话 ---------------- */

export function astroPlain(r) {
  const sun = r.太阳星座;
  const moon = r.月亮星座;
  const asc = pick(r, "上升星座", "未知");
  const hasAsc = asc in ASC_SIGN;

  let one;
  if (hasAsc) {
    one = "你的内核是个" + pick(SUN_KEYWORD, sun, "")
      + "，情感上最需要" + pick(MOON_KEYWORD, moon, "")
      + "，而别人看到的是一个" + pick(ASC_KEYWORD, asc, "") + "的人。";
  } else {
    one = "你的内核是个" + pick(SUN_KEYWORD, sun, "")
      + "，情感上最需要" + pick(MOON_KEYWORD, moon, "")
      + "。（填了出生地，才能算出上升星座和宫位）";
  }

  const pillars = [
    { 名: "太阳 · 你的核心自我", 座: sun, 文: pick(SUN_SIGN, sun, "") },
    { 名: "月亮 · 你的情感需求", 座: moon, 文: pick(MOON_SIGN, moon, "") },
  ];
  if (hasAsc) pillars.push({ 名: "上升 · 别人看到的你", 座: asc, 文: pick(ASC_SIGN, asc, "") });

  // 性格拼图
  const signOf = {};
  for (const p of r.天体) signOf[p.天体] = p.星座;
  const puzzle = [];
  for (const [planet, table, label] of [["水星", MERCURY_SIGN, "你怎么想、怎么说"],
                                        ["金星", VENUS_SIGN, "你怎么爱、怎么审美"],
                                        ["火星", MARS_SIGN, "你怎么行动、怎么发火"]]) {
    const sg = signOf[planet];
    if (sg in table) puzzle.push({ 名: label + "（" + planet + "在" + sg + "）", 座: sg, 文: table[sg] });
  }

  // 人生重心：行星落宫
  const houseOf = {};
  for (const h2 of (r.宫位 || [])) for (const p of h2.内行星) houseOf[p] = h2.宫;
  const focus = [];
  for (const planet of ["太阳", "月亮", "金星", "火星", "木星", "土星"]) {
    if (planet in houseOf) {
      const n = houseOf[planet];
      const tmpl = pick(HOUSE_BY_PLANET, planet);
      if (tmpl) {
        focus.push({ 名: PLANET_ROLE[planet][1] + " · 落在第 " + n + " 宫（" + HOUSE_MEANING[n] + "）",
                     文: tmpl.replace(/%s/g, HOUSE_MEANING[n]) });
      }
    }
  }

  // 元素配比
  const elem = r.元素分布;
  const elemTotal = Object.values(elem).reduce((a, b) => a + b, 0) || 1;
  const total = elemTotal;      // 保留旧名，少改一处
  const topE = maxByKey(elem);
  const missing = Object.keys(elem).filter((k) => elem[k] === 0);
  const parts = [];
  if (elem[topE] / total >= 0.4) parts.push(ELEMENT_MORE[topE]);
  if (missing.length) parts.push("另外，你的「" + missing.join("、") + "」元素偏少：" + ELEMENT_MISS[missing[0]]);
  if (!parts.length) parts.push("你的四元素配比比较均衡，性格立体，什么场合都能适应。");
  const eTxt = parts.join("");

  // 关键线索：上升守护星落在哪
  let keyClue = null;
  if (hasAsc) {
    const ruler = pick(RULER, asc);
    if (ruler) {
      const rSign = signOf[ruler];
      const rHouse = houseOf[ruler];
      let txt = "你的上升在" + asc + "，它的守护星是" + ruler;
      if (rSign) txt += "（" + ruler + "在" + rSign + "）";
      if (rHouse) {
        txt += "，落在第 " + rHouse + " 宫（" + HOUSE_MEANING[rHouse] + "）。"
          + "这是整张盘最关键的一条线索——你这辈子的重要课题，往往跟「"
          + HOUSE_MEANING[rHouse] + "」有关。";
      } else {
        txt += "。这是整张盘最关键的一条线索。";
      }
      keyClue = txt;
    }
  }

  // 关系张力
  const tension = [];
  for (const a of r.相位.slice().sort((x, y) => y.强度 - x.强度).slice(0, 4)) {
    const p1 = (pick(PLANET_ROLE, a.天体1, [a.天体1, ""]))[0];
    const p2 = (pick(PLANET_ROLE, a.天体2, [a.天体2, ""]))[0];
    const trait = pick(ASPECT_TRAIT, a.相位, a.相位);
    tension.push({ 文: "你的「" + p1 + "」和「" + p2 + "」" + trait + "。" });
  }

  // 星座实用档案
  const profiles = [];
  for (const [label, sg] of [["太阳", sun], ["月亮", moon], ["上升", hasAsc ? asc : null]]) {
    const p = sg ? pick(SIGN_PROFILE, sg) : null;
    if (p) profiles.push({ 名: label + " · " + sg + "座", 档案: p });
  }

  return {
    一句话: one,
    三支柱: { 标题: "你的三大支柱", 列表: pillars },
    性格拼图: { 标题: "你的性格拼图", 列表: puzzle },
    人生重心: { 标题: "你的人生重心在哪", 列表: focus },
    关键线索: keyClue,
    元素配比: {
      标题: "你的能量配比", 要点: eTxt, 明细: elem,
      // 逐元素展开。Python 侧用 list comprehension 按 elem 的插入顺序生成，
      // 这里必须照抄这个顺序 —— 顺序不同则对拍逐字不一致。
      逐项: Object.keys(elem).map((k) => ({
        "元素": k, "个数": elem[k],
        "占比": Math.round(elem[k] / elemTotal * 1000) / 10,
        "多时": pick(ELEMENT_MORE, k, ""),
        "少时": pick(ELEMENT_MISS, k, ""),
        "最旺": k === topE, "完全缺": elem[k] === 0,
      })),
      最多: topE, 缺失: missing,
    },
    关系张力: { 标题: "你身上的主要张力", 列表: tension },
    实用档案: { 标题: "你的星座档案", 列表: profiles },
    术语: [["太阳星座", "你的核心自我和人生主题。"],
           ["月亮星座", "你的情绪需求和内心世界。"],
           ["上升星座", GLOSSARY["上升星座"]],
           ["宫位", "星盘里的十二个生活领域，比如第4宫管家庭、第10宫管事业。"],
           ["相位", GLOSSARY["相位"]]],
  };
}

/* ---------------- 汇总 ---------------- */

export function headline(data) {
  const bits = [];
  if (data.八字) {
    const b = data.八字;
    bits.push("八字日主「" + b.日主.干 + "」，" + DAY_MASTER[b.日主.干][0]);
  }
  if (data.紫微) {
    const z = data.紫微;
    const ming = (z.十二宫 || []).find((p) => p.是否命宫);
    const mains = ming ? ming.星曜.map((s) => s.split("·")[0]).filter((s) => s in ZIWEI_STAR) : [];
    if (mains.length) bits.push("紫微命宫主星「" + mains[0] + "」");
  }
  if (data.占星) {
    const a = data.占星;
    bits.push("太阳" + a.太阳星座 + "·月亮" + a.月亮星座);
  }
  return bits.join(" ｜ ");
}

export function glossaryHtml() { return GLOSSARY; }
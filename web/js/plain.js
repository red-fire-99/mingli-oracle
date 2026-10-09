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
  PALACE_MEANING, PALACE_STAR_NOTE, ZW_MALEFIC,
  DAXIAN_THEME, SIHUA_ROLE, LIUNIAN_NOTE,
  SHENSHA_KIND, SHENSHA_KIND_NOTE, SHISHEN_COUNT_NOTE, SHISHEN_PAIR,
  ANGLE_ROLE, QUALITY_ROLE, ASPECT_TONE,
  PILLAR_ROLE, KIN_STARS, KIN_ROLE_NOTE, STAR_VISIBILITY,
  SPOUSE_PAIR, SPOUSE_SINGLE, SPOUSE_SHA,
  SPOUSE_DAXIAN_YOUNG, SPOUSE_DAXIAN_LATE,
  HOUSE_REL, HOUSE_REL_PLANET, HOUSE_REL_EMPTY, KIN_CAVEAT,
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
    神煞详批: shenshaList(r),
    十神详批: shishenList(r),
    六亲详批: kinList(r),
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

/* ---------------- 紫微：十二宫 / 大限 / 四化 ---------------- */

/** 对宫映射：空宫要借对宫的星来看 */
const ZW_OPPOSITE = { "子": "午", "丑": "未", "寅": "申", "卯": "酉", "辰": "戌", "巳": "亥",
                      "午": "子", "未": "丑", "申": "寅", "酉": "卯", "戌": "辰", "亥": "巳" };

/** 星曜字符串 -> 星名。引擎把四化拼在星名里（「太阳·化禄」）。 */
function starName(s) { return String(s).split("·")[0]; }

function palaceList(r) {
  const out = [];
  for (const p of r["十二宫"]) {
    const mains = [];
    for (const s of p["星曜"]) {
      const nm = starName(s);
      if (PALACE_STAR_NOTE[nm] || ZIWEI_STAR[nm]) mains.push(nm);
    }
    // Python 侧用「在 ZIWEI_STAR 里」筛主星，这里保持一致
    const realMains = mains.filter((nm) => !!ZIWEI_STAR[nm]);

    const tags = [];
    const cautions = [];
    for (const s of p["星曜"]) {
      const nm = starName(s);
      if (PALACE_STAR_NOTE[nm]) tags.push({ 星: nm, 说明: PALACE_STAR_NOTE[nm] });
      const m = ZW_MALEFIC[nm];
      if (m && m[1]) cautions.push({ 星: nm, 说明: m[1] });
    }

    let borrowedFrom = "";
    let borrowed = [];
    if (!realMains.length) {
      const oz = ZW_OPPOSITE[p["地支"]] || "";
      const op = r["十二宫"].find((x) => x["地支"] === oz);
      if (op) {
        borrowedFrom = op["宫名"];
        borrowed = op["星曜"].map(starName).filter((nm) => !!ZIWEI_STAR[nm]);
      }
    }

    out.push({
      "宫名": p["宫名"], "干支": p["天干"] + p["地支"],
      "主星": realMains, "借宫": borrowedFrom, "借宫主星": borrowed,
      "含义": PALACE_MEANING[p["宫名"]] || "",
      "标签": tags, "留意": cautions,
      "是命宫": !!p["是否命宫"], "是身宫": !!p["是否身宫"],
    });
  }
  return out;
}

function daxianList(r) {
  const dx = r["大限"] || {};
  const out = [];
  for (const x of (dx["列表"] || [])) {
    const pal = r["十二宫"].find((p) => p["宫名"] === x["宫位"]);
    const mains = pal
      ? pal["星曜"].map(starName).filter((nm) => !!ZIWEI_STAR[nm])
      : [];
    out.push({
      "宫位": x["宫位"], "干支": x["天干"] + x["地支"],
      "虚岁起": x["虚岁起"], "虚岁止": x["虚岁止"],
      "主星": mains, "星曜": x["星曜"].map(starName),
      "主题": DAXIAN_THEME[x["宫位"]] || "这十年按大限走，重点在自己的调整。",
      "宫位含义": PALACE_MEANING[x["宫位"]] || "",
    });
  }
  return out;
}

function liunianNote(r) {
  const ln = r["流年"];
  if (!ln) return null;
  const cur = ln["当前大限"] || "";
  // 流年命宫是「午宫」，而 PALACE_MEANING 的键是宫名（「疾厄」…），
  // 直接去掉「宫」去查必然查不到 —— 用地支反查宫名。
  const lnz = ln["流年命宫"] || "";
  const lnZhi = lnz.endsWith("宫") ? lnz.slice(0, -1) : lnz;
  const pal = r["十二宫"].find((p) => p["地支"] === lnZhi);
  const palName = pal ? pal["宫名"] : "";
  const dxPal = cur ? cur.split("·")[0] : "";
  return {
    "年": ln["年"], "干支": ln["干支"], "虚岁": ln["虚岁"],
    "流年命宫": lnz, "流年命宫名": palName,
    "当前大限": cur, "当前大限宫": dxPal,
    "说明": LIUNIAN_NOTE,
    "命宫含义": PALACE_MEANING[palName] || "",
    "大限含义": PALACE_MEANING[dxPal] || "",
    "大限主题": DAXIAN_THEME[dxPal] || "",
  };
}

function sihuaList(r) {
  const h = r["四化"] || {};
  const out = [];
  for (const key of ["化禄", "化权", "化科", "化忌"]) {
    const star = h[key];
    if (!star) continue;
    const nm = starName(star);
    const pal = r["十二宫"].find(
      (p) => p["星曜"].some((s) => starName(s) === nm));
    const role = SIHUA_ROLE[key] || ["", ""];
    out.push({
      "化": key, "星": star,
      "宫位": pal ? pal["宫名"] : "",
      "宫位含义": pal ? (PALACE_MEANING[pal["宫名"]] || "") : "",
      "角色": role[0], "要点": role[1],
    });
  }
  return out;
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
    十二宫详批: { 标题: "你的十二宫", 列表: palaceList(r) },
    大限详批: { 标题: "你一生十二步大限", 列表: daxianList(r) },
    流年详情: liunianNote(r),
    四化详批: sihuaList(r),
    夫妻详批: spouseList(r),
    术语: [["命宫", GLOSSARY["命宫"]], ["主星", GLOSSARY["主星"]],
           ["四化", GLOSSARY["四化"]], ["大限", GLOSSARY["大限"]]],
  };
}

/* ---------------- 1.5.0: 神煞 / 十神 / 轴点 / 性质 / 相位 ---------------- */

/** 相位强度档位。与 Python 侧 _aspect_level 同构（阈值必须一致）。 */
function aspectLevel(v) {
  if (v >= 0.85) return ["很强", "影响很明显，基本构成性格的一部分"];
  if (v >= 0.6) return ["较强", "有影响，但会随环境变化"];
  return ["一般", "是底色，不是主线"];
}

function shenshaList(r) {
  const out = [];
  for (const s of (r["神煞"] || [])) {
    const name = s["神煞"];
    const kind = SHENSHA_KIND[name] || "";
    out.push({
      "神煞": name, "查法": s["查法"] || "", "落支": s["落支"] || "",
      "位置": s["位置"] || "", "说明": s["说明"] || "",
      "类别": kind,
      // 表里没有的标成空而不是默认吉 —— 默认吉等于「没查过就说好」
      "类别说明": SHENSHA_KIND_NOTE[kind] || "未归类",
    });
  }
  const unknown = out.filter((x) => !x["类别"]).map((x) => x["神煞"]);
  const cnt = (k) => out.filter((x) => x["类别"] === k).length;
  return { "标题": "你命里的神煞", "列表": out, "未归类": unknown,
           "计数": { "助你": cnt("ji"), "中性": cnt("xu"),
                     "留意": cnt("xiong"), "未归类": unknown.length } };
}

function shishenList(r) {
  const count = {};
  const zCount = {};
  for (const c of (r["柱详解"] || [])) {
    const g = c["干十神"];
    if (g && g !== "日主") count[g] = (count[g] || 0) + 1;
    for (const z of (c["支藏干"] || [])) {
      const ss = z["十神"];
      if (ss) zCount[ss] = (zCount[ss] || 0) + 1;
    }
  }
  let total = 0;
  for (const k of Object.keys(count)) total += count[k];
  for (const k of Object.keys(zCount)) total += zCount[k];

  /* 十神的首次出现顺序：必须与 Python 侧一致。
   Python 的 dict 保持插入序，JS 的对象键序在「字符串键」上也是插入序 ——
   但下面 count/zCount 是分开建的，Python 侧 items 的初始顺序来自
   set(list(count) + list(zCount))，那是**无序**的。
   所以两边都改成显式的「先 count 的插入序、再 zCount 补充」，
   不依赖语言各自的集合/对象顺序。 */
  const keys = [];
  for (const k of Object.keys(count)) keys.push(k);
  for (const k of Object.keys(zCount)) if (keys.indexOf(k) < 0) keys.push(k);
  const items = keys.map((ss) => {
    const gan = count[ss] || 0, zhi = zCount[ss] || 0;
    return { "十神": ss, "干上": gan, "藏干": zhi, "合计": gan + zhi,
             "占比": total ? Math.round((gan + zhi) / total * 1000) / 10 : 0,
             "说明": SHISHEN_COUNT_NOTE[ss] || "" };
  });
  // 稳定插入排序：Python 的 sort 是稳定的，JS 的 sort 不是
  for (let i = 1; i < items.length; i++) {
    const cur = items[i];
    let j = i - 1;
    while (j >= 0 && items[j]["合计"] < cur["合计"]) { items[j + 1] = items[j]; j--; }
    items[j + 1] = cur;
  }

  // 并列最高要全列：八个字摊到十种十神上，四五个并列第一是常态
  const topN = items.length ? items[0]["合计"] : 0;
  const tied = items.filter((x) => x["合计"] === topN).map((x) => x["十神"]);
  let lead;
  if (tied.length === 1) {
    lead = { "名": tied[0], "并列": false, "说明": SHISHEN_COUNT_NOTE[tied[0]] || "" };
  } else {
    lead = { "名": tied.join("、"), "并列": true,
             "说明": "你的十神没有单一主角——" + tied.join("、") + " 各占 "
               + topN + " 个。这类盘的特点是均衡：适应面广，什么环境都能待，"
               + "代价是「没有特别想抓的那一样」。" };
  }

  const pairs = [];
  const top = items.filter((x) => x["合计"] >= 2).map((x) => x["十神"]).slice(0, 4);
  for (let i = 0; i < top.length; i++) {
    for (let j = i + 1; j < top.length; j++) {
      const txt = SHISHEN_PAIR[top[i] + "|" + top[j]]
               || SHISHEN_PAIR[top[j] + "|" + top[i]];
      if (txt) pairs.push({ "组合": top[i] + " + " + top[j], "说明": txt });
    }
  }
  return { "标题": "你的十神分布", "明细": items, "组合": pairs,
           "最多": lead["名"], "并列": lead["并列"],
           "最多说明": lead["说明"], "并列项": tied };
}

function angleList(r) {
  const out = [];
  for (const key of ["上升", "天顶"]) {
    const v = (r["轴点"] || {})[key];
    if (!v) continue;
    const role = ANGLE_ROLE[key] || { "角色": "", "含义": "" };
    out.push({ "名": key, "符号": v["符号"] || "", "星座": v["星座"] || "",
               "度数": v["星座内度"] || "",
               "角色": role["角色"], "含义": role["含义"] });
  }
  return { "标题": "两个轴点", "列表": out };
}

function qualityList(r) {
  const dist = r["性质分布"] || {};
  const planets = [];
  for (const p of (r["天体"] || [])) {
    const q = QUALITY_ROLE[p["性质"]];
    if (q) planets.push({ "天体": p["天体"], "性质": p["性质"],
                          "星座": p["星座"] || "", "含义": q["含义"] });
  }
  const items = [];
  for (const name of ["基本", "固定", "变动"]) {
    if (!(name in dist)) continue;
    const info = QUALITY_ROLE[name] || {};
    items.push({ "性质": name, "名": info["名"] || name,
                 "个数": dist[name], "含义": info["含义"] || "" });
  }
  for (let i = 1; i < items.length; i++) {
    const cur = items[i]; let j = i - 1;
    while (j >= 0 && items[j]["个数"] < cur["个数"]) { items[j + 1] = items[j]; j--; }
    items[j + 1] = cur;
  }
  let total = 0;
  for (const k of Object.keys(dist)) total += dist[k];
  return { "标题": "你的行星性质", "明细": items, "各星": planets,
           "最多": items.length ? items[0]["性质"] : "",
           "最多说明": items.length ? items[0]["含义"] : "", "总计": total };
}

function aspectList(r) {
  const good = [], tension = [];
  const list = (r["相位"] || []).slice().sort((a, b) => b["强度"] - a["强度"]);
  for (const a of list) {
    const tone = ASPECT_TONE[a["相位"]];
    if (!tone) continue;
    const lv = aspectLevel(a["强度"]);
    const p1 = (PLANET_ROLE[a["天体1"]] || [a["天体1"], ""])[0];
    const p2 = (PLANET_ROLE[a["天体2"]] || [a["天体2"], ""])[0];
    const item = { "天体1": a["天体1"], "天体2": a["天体2"],
                   "职能1": p1, "职能2": p2, "相位": a["相位"],
                   "强度": a["强度"], "强度档": lv[0], "强度含义": lv[1],
                   "性质": tone[0], "说明": tone[1],
                   "文": "你的「" + p1 + "」和「" + p2 + "」" + a["相位"]
                       + "——" + tone[1] + "（" + lv[0] + "）" };
    if (tone[0] === "和谐") good.push(item); else tension.push(item);
  }
  return { "标题": "全部相位", "和谐": good, "张力": tension,
           "合计": good.length + tension.length };
}

/* ---------------- 1.6.0: 六亲 / 夫妻宫 / 关系宫 ---------------- */

/** 二元组键的查法。SPOUSE_PAIR 的键是 Python 的二元组，
    导出成 JSON 后会变成 Python 的 str(tuple) 形式：
    "('天机', '巨门')" —— 注意是**单引号**。
    用 JSON.stringify 拼出来的是双引号版本，查不到。
    所以这里必须手工按单引号拼。 */
function pairKey(a, b) {
  return "('" + a + "', '" + b + "')";
}

/** 八字六亲。男女分派是硬要求 —— 同盘只差性别，
    不分派的话男女会看到同一段关于配偶的话。 */
function kinList(r) {
  const inp = r["输入"] || {};
  let sex = inp["性别"] || "男";
  if (!KIN_STARS[sex]) sex = "男";
  const cols = r["柱详解"] || [];

  const place = {};
  for (const c of cols) {
    const p = c["柱"];
    const g = c["干十神"];
    if (g && g !== "日主") {
      if (!place[g]) place[g] = [];
      place[g].push({ "柱": p, "位": "干", "干支": c["干"] });
    }
    for (const z of (c["支藏干"] || [])) {
      const s = z["十神"];
      if (!s) continue;
      if (!place[s]) place[s] = [];
      place[s].push({ "柱": p, "位": "支", "干支": c["支"], "藏": z["干"] });
    }
  }

  const ORD = { "年柱": 0, "月柱": 1, "日柱": 2, "时柱": 3 };
  const items = [];
  for (const role of ["配偶", "父母", "兄弟", "子女"]) {
    const stars = KIN_STARS[sex][role];
    let got = [];
    for (const st of stars) {
      for (const it of (place[st] || [])) {
        got.push({ "柱": it["柱"], "位": it["位"], "干支": it["干支"],
                   "藏": it["藏"], "十神": st, "透": it["位"] === "干" });
      }
    }
    // 先透后藏，同类按柱序（年→月→日→时）。
    // 用插入排序而不是 sort：JS 的 sort 不稳定。
    for (let i = 1; i < got.length; i++) {
      const cur = got[i];
      const kc = (cur["透"] ? 0 : 1) * 10 + (ORD[cur["柱"]] === undefined ? 9 : ORD[cur["柱"]]);
      let j = i - 1;
      while (j >= 0) {
        const kj = (got[j]["透"] ? 0 : 1) * 10
                 + (ORD[got[j]["柱"]] === undefined ? 9 : ORD[got[j]["柱"]]);
        if (kj <= kc) break;
        got[j + 1] = got[j];
        j--;
      }
      got[j + 1] = cur;
    }
    items.push({
      "角色": role, "星": stars, "个数": got.length, "位置": got,
      "有透": got.some((x) => x["透"]),
      "说明": KIN_ROLE_NOTE[sex][role],
    });
  }

  const pillars = cols.map((c) => ({
    "柱": c["柱"], "干支": c["干"] + (c["支"] || ""),
    "代表": PILLAR_ROLE[c["柱"]] || "",
  }));
  return { "标题": "六亲怎么看", "口径": KIN_CAVEAT, "列表": items,
           "柱位": pillars, "性别": sex };
}

/** 紫微夫妻宫。措辞全部走「需要磨合的地方」，不走「好 / 坏」。 */
function spouseList(r) {
  const pal = {};
  for (const p of (r["十二宫"] || [])) pal[p["宫名"]] = p;
  const fu = pal["夫妻"];
  if (!fu) return { "标题": "夫妻宫" };

  const ZHI = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"];
  const z = fu["地支"];
  let oppName = "";
  if (ZHI.indexOf(z) >= 0) {
    const oppZ = ZHI[(ZHI.indexOf(z) + 6) % 12];
    for (const k of Object.keys(pal)) {
      if (pal[k]["地支"] === oppZ) { oppName = k; break; }
    }
  }

  // 主星可能带四化后缀（"太阳·化禄"）。**不能**用
  // `filter((s) => s.indexOf("·") < 0)` 把它们滤掉 ——
  // 那样带四化的夫妻宫主星全空，整块不渲染。
  // 这个错在 512 例对拍里抓不到（那些盘夫妻宫要么有普通主星、
  // 要么本来就空），是时辰路径门禁用辰时那个盘才暴露的。
  const rawMain = (fu["主星"] || []).filter((s) => s);
  const main = rawMain.slice();
  const baseOf = (s) => s.split("·")[0];

  let combo = null;
  outer:
  for (let i = 0; i < main.length; i++) {
    for (let j = i + 1; j < main.length; j++) {
      const a = main[i], b = main[j];
      const hit = SPOUSE_PAIR[pairKey(a, b)]
               || SPOUSE_PAIR[pairKey(b, a)]
               || SPOUSE_PAIR[pairKey(baseOf(a), baseOf(b))]
               || SPOUSE_PAIR[pairKey(baseOf(b), baseOf(a))];
      if (hit) {
        combo = { "型": hit[0], "说明": hit[1], "星": [a, b] };
        break outer;
      }
    }
  }
  if (!combo && main.length === 1) {
    const one = main[0];
    const txt = SPOUSE_SINGLE[one] || SPOUSE_SINGLE[baseOf(one)];
    if (txt) combo = { "型": one, "说明": txt, "星": main.slice(0, 1) };
  }

  const sha = [], unknown = [];
  for (const s of (fu["星曜"] || [])) {
    const base = baseOf(s);
    if (rawMain.indexOf(s) >= 0) continue;
    if (SPOUSE_SHA[base]) {
      sha.push({ "星": base, "型": SPOUSE_SHA[base][0], "说明": SPOUSE_SHA[base][1] });
    } else {
      unknown.push(s);
    }
  }

  // 主星上的四化单独讲 —— 它是这块星曜的当前状态，
  // 不是「另一种星」。混进煞星或未解读里都是错的。
  const hua = [];
  for (const s of rawMain) {
    const i = s.indexOf("·");
    if (i < 0) continue;
    const k = s.slice(i + 1);
    const role = SIHUA_ROLE[k];
    hua.push({ "星": s, "化": k, "说明": (role ? role[1] : "") });
  }

  let dx = "", dxAge = "";
  for (const x of (((r["大限"] || {})["列表"]) || [])) {
    if (x["宫位"] !== "夫妻") continue;
    dxAge = x["虚岁起"] + "–" + x["虚岁止"];
    const from = parseInt(x["虚岁起"], 10);
    if (!isNaN(from)) dx = from >= 45 ? SPOUSE_DAXIAN_LATE : SPOUSE_DAXIAN_YOUNG;
    break;
  }

  return { "标题": "夫妻宫", "宫干": fu["天干"] || "", "地支": z,
           "对宫": oppName, "主星": main, "组合": combo, "四化": hua,
           "煞星": sha, "未解读": unknown,
           "大限年龄": dxAge, "大限说明": dx };
}

/** 占星关系相关宫。空的宫也要讲 —— 空宫不是「这块没有」，
    而是不靠外力推。 */
function houseRelList(r) {
  const houses = {};
  for (const h of (r["宫位"] || [])) houses[h["宫"]] = h;
  const items = [];
  for (const n of [7, 8, 4, 10, 11]) {
    const h = houses[n] || {};
    const pls = h["内行星"] || [];
    const info = HOUSE_REL[String(n)] || ["", ""];
    items.push({
      "宫": n, "名": info[0], "管什么": info[1], "星座": h["星座"] || "",
      "星": pls.map((p) => ({ "名": p, "说明": HOUSE_REL_PLANET[p] || "" })),
      "空": pls.length === 0,
    });
  }
  return { "标题": "关系相关的宫", "列表": items, "空宫说明": HOUSE_REL_EMPTY };
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
    轴点详批: angleList(r),
    性质详批: qualityList(r),
    相位详批: aspectList(r),
    关系宫详批: houseRelList(r),
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
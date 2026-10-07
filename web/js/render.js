/* ===================================================================
   render.js —— oracle.py 中 build / _h / render_* 的 JS 移植
   ===================================================================
   逐段对照 Python 版。字符串拼接顺序必须完全一致（HTML 是逐字比对的），
   因此这里刻意保留 Python 的列表 append + "".join 写法，不做「优化」。

   注意 Python 的 % 格式化与 JS 的差异：
   - Python "%.1f" 与 JS toFixed(1) 行为一致（含四舍六入五成双的细节）
   - Python "%s" 对 int 直接输出，JS String(n) 同样不带小数点
   - Python "%s" 对 float 会带 .0（如 5.0 -> '5.0'），JS String(5) 是 '5'
     本文件用到的都是 int，故无影响；真出现 float 请用 pyFloatStr
   =================================================================== */

import { STAR_BRIEF } from "./ziwei.js";
import { baziPlain, ziweiPlain, astroPlain, headline, GLOSSARY } from "./plain.js";
import { paiPan as baziPaiPan } from "./bazi.js";
import { paiPan as ziweiPaiPan } from "./ziwei.js";
import { paiPan as astroPaiPan } from "./astro.js";

/** Python 的 str.replace 三连（只转这三个，顺序同 Python）。 */
function h(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/** Python "%.1f" —— 用 toFixed，注意 Python 对负零给 '-0.0'，JS 也一样。 */
function f1(n) { return n.toFixed(1); }

/**
 * Python 的 "%d"。
 *
 * 关键坑：Python 的 "%d" % 5.3 是 **5**（向零截断），
 * 而 JS 的 String(5.3) 是 "5.3"。起运虚岁本来就是小数
 * （"5.3-15.3岁"），直接拼接会多出 ".3"，整段 HTML 就对不上了。
 */
function d(n) { return String(Math.trunc(n)); }

const WX_COLOR = { 木: "#5b8c5a", 火: "#c0504d", 土: "#b08d4a", 金: "#8a8f98", 水: "#4a6fa5" };

/** 紫微盘 4x4 地支位置：(row, col) → 地支 */
const PAN_LAYOUT = {
  "0,0": "巳", "0,1": "午", "0,2": "未", "0,3": "申",
  "1,0": "辰", "1,3": "酉",
  "2,0": "卯", "2,3": "戌",
  "3,0": "寅", "3,1": "丑", "3,2": "子", "3,3": "亥",
};

/* ------------------------------------------------------------------ */
/* build：三盘一次排出                                                 */
/* ------------------------------------------------------------------ */

export function build(o) {
  o = o || {};
  const out = {};
  const solar = o.solar || null, lunar = o.lunar || null, leap = !!o.leap;
  const hour = o.hour || null, shichen = o.shichen || null;
  const sex = o.sex || "男", place = o.place || null;
  const only = o.only || null;

  if (only === null || only === "bazi") {
    out.八字 = baziPaiPan({ solar, lunar, leap, hour, shichen, sex, place,
                            longitude: o.lon });
  }
  if (only === null || only === "ziwei") {
    out.紫微 = ziweiPaiPan({ solar, lunar, leap, hour, shichen, sex, place,
                            year: o.year });
  }
  if (only === null || only === "astro") {
    // Python: hour or (12, 0) —— 缺时刻时占星用中午
    out.占星 = astroPaiPan({ solar, lunar, leap, hour: hour || [12, 0], shichen: null,
                              sex, lat: o.lat, lon: o.lon, place });
  }
  return out;
}

/* ------------------------------------------------------------------ */
/* 八字                                                                */
/* ------------------------------------------------------------------ */

export function renderBazi(r) {
  const i = r.输入;
  const p = [];
  p.push('<section><h2>四柱八字</h2>');
  p.push('<div class="info"><span>公历 <b>' + h(i.公历) + '</b></span><span>农历 <b>'
    + h(i.农历) + '</b></span><span>时辰 <b>' + h(i.时辰) + '</b></span><span>性别 <b>'
    + h(i.性别) + '</b></span><span>出生地 <b>' + h(i.出生地) + '</b></span></div>');
  if (i.真太阳时) {
    const t = i.真太阳时;
    p.push('<div class="info"><span>真太阳时 <b>' + h(t.真太阳时)
      + '</b>（钟表 ' + h(t.钟表时) + '，校正 ' + t.校正分钟 + ' 分，均时差 '
      + t.均时差分钟 + ' 分）</span></div>');
  }
  p.push('<table><tr><th></th>'
    + '<th title="出生年份的干支，以「立春」为分界，不是元旦也不是春节">年柱</th>'
    + '<th title="出生月份的干支，以节气为分界（立春起寅月）">月柱</th>'
    + '<th title="出生日子的干支。这一柱上面的字（日干）就是「你自己」">日柱</th>'
    + '<th title="出生时辰的干支，两小时为一个时辰">时柱</th></tr>');

  const rows = { 干支: [], 十神: [], 藏干: [], 纳音: [] };
  for (const pos of ["年", "月", "日", "时"]) {
    const gz = r.四柱[pos];
    if (gz === "未知") { for (const k in rows) rows[k].push("—"); continue; }
    const d = r.柱详解.find((x) => x.柱 === pos);
    rows.干支.push('<span class="gz"><span class="gan">' + gz[0]
      + '</span><span class="zhi">' + gz[1] + '</span></span>');
    rows.十神.push(d.干十神);
    rows.藏干.push('<div class="cang">' + d.支藏干.map(
      (c) => c.干 + " <span class='ss'>" + c.十神 + "</span>").join("<br>") + '</div>');
    rows.纳音.push(d.纳音);
  }
  const ROW_TIP = { 干支: "八个字本身，上为天干、下为地支",
                    十神: "其他七个字跟「你」的关系，分十种，代表不同的人事",
                    藏干: "地支里藏着的天干，代表表面之下暗藏的力量",
                    纳音: "干支组合对应的五行意象，用于辅助参考" };
  for (const [k, label] of [["干支", ""], ["十神", "十神"], ["藏干", "藏干"], ["纳音", "纳音"]]) {
    const tip = (k in ROW_TIP) ? ' title="' + ROW_TIP[k] + '"' : "";
    p.push("<tr><th" + tip + ">" + label + "</th>"
      + rows[k].map((v) => "<td>" + v + "</td>").join("") + "</tr>");
  }
  p.push("</table>");

  const s = r.日主强弱;
  p.push('<div class="info" style="margin-top:14px">'
    + '<span>日主 <b>' + r.日主.干 + '（' + r.日主.五行 + '·' + r.日主.阴阳 + '）</b></span>'
    + '<span>强弱 <b>' + s.判定 + '</b>（同党 ' + f1(s.同党占比) + '%）</span>'
    + '<span>格局 <b>' + r.格局.名 + '</b></span><span>旬空 <b>' + r.旬空 + '</b></span>'
    + '<span>喜用 <b>' + s.喜用神.join("、") + '</b></span></div>');

  p.push("<h2 style='margin-top:20px'>五行力量</h2>");
  for (const w in r.五行统计) {
    const v = r.五行统计[w];
    p.push('<div class="bar"><div class="lb">' + w + '</div><div class="tr">'
      + '<div class="fl" style="width:' + f1(Math.max(v, 0)) + '%;background:' + WX_COLOR[w]
      + '"></div></div><div class="vl">' + f1(v) + '%</div></div>');
  }

  if (r.神煞.length) {
    p.push("<h2 style='margin-top:20px'>神煞</h2><div>");
    for (const x of r.神煞) {
      const cls = ["煞", "刃", "孤", "寡"].some((k) => x.神煞.includes(k)) ? "xiong" : "ji";
      p.push('<span class="pill ' + cls + '" title="' + h(x.说明) + '">'
        + h(x.神煞) + "·" + h(x.位置) + "</span>");
    }
    p.push("</div>");
  }

  const dy = r.大运;
  p.push("<h2 style='margin-top:20px'>大运</h2><div class='info'><span>" + h(dy.顺逆)
    + "，起运 <b>" + h(dy.起运) + "</b></span></div>");
  p.push('<div class="liu">');
  for (const x of dy.列表) {
    p.push("<span>" + h(x.十神) + "<br><b>" + h(x.干支) + "</b> " + "<br>"
      + d(x.起始虚岁) + "-" + d(x.结束虚岁) + "岁</span>");
  }
  p.push("</div>");

  p.push("<h2 style='margin-top:20px'>流年</h2><div class='liu'>");
  for (const x of r.流年) {
    p.push("<span>" + d(x.年) + " <b>" + h(x.干支) + "</b> " + h(x.十神)
      + " · " + d(x.虚岁) + "岁</span>");
  }
  p.push("</div>");
  if (r.警告.length) {
    p.push('<div class="warn">' + r.警告.map((w) => "⚠ " + h(w)).join("<br>") + "</div>");
  }
  p.push("</section>");
  return p.join("");
}

/* ------------------------------------------------------------------ */
/* 紫微                                                                */
/* ------------------------------------------------------------------ */

export function renderZiwei(r) {
  const i = r.输入;
  const byZhi = {};
  for (const pp of r.十二宫) byZhi[pp.地支] = pp;
  const p = ['<section><h2>紫微斗数</h2>'];
  p.push('<div class="info"><span>农历 <b>' + h(i.农历) + '</b></span><span>时辰 <b>'
    + h(i.时辰) + '</b></span><span>年干支 <b>' + h(i.年干支) + '</b></span><span>五行局 <b>'
    + h(r.五行局) + '</b></span><span>命宫 <b>' + r.命宫.天干 + r.命宫.地支
    + '</b></span><span>身宫 <b>' + r.身宫.天干 + r.身宫.地支 + '</b></span></div>');
  const hu = r.四化;
  p.push('<div class="info"><span>四化（' + h(hu.年干) + '干）：禄 <b>' + h(hu.化禄)
    + '</b> · 权 <b>' + h(hu.化权) + '</b> · 科 <b>' + h(hu.化科) + '</b> · 忌 <b>'
    + h(hu.化忌) + "</b></span></div>");

  p.push('<div class="pan">');
  for (let row = 0; row < 4; row++) {
    for (let col = 0; col < 4; col++) {
      if ((row === 1 || row === 2) && (col === 1 || col === 2)) continue;
      const z = PAN_LAYOUT[row + "," + col];
      const pal = byZhi[z];
      if (!pal) { p.push("<div></div>"); continue; }
      let cls = "cell";
      if (pal.是否命宫) cls += " ming";
      if (pal.是否身宫) cls += " shen";
      const stars = pal.星曜.map((s) => {
        const base = s.split("·")[0];
        const k = (base in STAR_BRIEF) ? "star main" : (s.includes("化") ? "star hua" : "star aux");
        return '<span class="' + k + '">' + h(s) + "</span>";
      });
      const tag = [];
      if (pal.是否命宫) tag.push("命");
      if (pal.是否身宫) tag.push("身");
      p.push('<div class="' + cls + '"><div class="pos"><span>' + h(pal.宫名)
        + '</span><span>' + tag.join("") + '</span></div>'
        + '<div class="gz2"><span class="gan">' + pal.天干 + '</span><span class="zhi">'
        + pal.地支 + '</span></div><div class="stars">'
        + (stars.length ? stars.join(" ") : '<span class="ss">空宫</span>') + "</div></div>");
    }
  }
  p.push('<div class="center"><div class="t">命盘</div>'
    + '<div>紫微 ' + h(r.紫微星) + '</div><div>天府 ' + h(r.天府星) + '</div><div>'
    + h(r.五行局) + '</div><div class="ss">大限' + h(r.大限.顺逆) + " · 起运"
    + d(r.大限.起运虚岁) + "岁</div></div>");
  p.push("</div>");

  p.push("<h2 style='margin-top:20px'>大限</h2><div class='liu'>");
  for (const x of r.大限.列表) {
    p.push("<span>" + d(x.虚岁起) + "-" + d(x.虚岁止) + "岁<br><b>" + x.天干 + x.地支
      + "</b><br>" + h(x.宫位) + "</span>");
  }
  p.push("</div>");
  const ln = r.流年;
  p.push('<div class="info" style="margin-top:14px"><span>流年 <b>' + d(ln.年) + " " + h(ln.干支)
    + "</b> 虚岁" + d(ln.虚岁) + ' · 流年命宫 <b>' + h(ln.流年命宫) + '</b> · 当前大限 <b>'
    + h(ln.当前大限) + "</b></span></div>");
  if (r.警告.length) {
    p.push('<div class="warn">' + r.警告.map((w) => "⚠ " + h(w)).join("<br>") + "</div>");
  }
  p.push("</section>");
  return p.join("");
}

/* ------------------------------------------------------------------ */
/* 占星                                                                */
/* ------------------------------------------------------------------ */

export function renderAstro(r) {
  const p = ['<section><h2>西洋占星本命盘</h2>'];
  p.push('<div class="info"><span>太阳 <b>' + h(r.太阳星座) + '</b></span><span>月亮 <b>'
    + h(r.月亮星座) + '</b></span><span>上升 <b>' + h(r.上升星座) + '</b></span><span>经纬度 <b>'
    + h(r.输入.经纬度) + "</b></span></div>");
  p.push("<table><tr><th>天体</th><th>星座</th><th>度数</th><th>元素</th></tr>");
  for (const x of r.天体) {
    p.push("<tr><td>" + h(x.符号) + " " + h(x.天体) + "</td><td>" + h(x.星座)
      + "</td><td>" + h(x.星座内度) + "</td><td>" + h(x.元素) + "·" + h(x.性质) + "</td></tr>");
  }
  p.push("</table>");
  if (Object.keys(r.轴点).length) {
    p.push('<div class="info" style="margin-top:12px">');
    for (const nm in r.轴点) {
      const v = r.轴点[nm];
      p.push("<span>" + h(nm) + " <b>" + h(v.星座) + " " + h(v.星座内度) + "</b></span>");
    }
    p.push("</div>");
  }
  p.push("<h2 style='margin-top:20px'>主要相位</h2><div>");
  for (const a of r.相位.slice().sort((x, y) => y.强度 - x.强度).slice(0, 14)) {
    const cls = (a.相位 === "三分相" || a.相位 === "六分相") ? "ji" : "xiong";
    p.push('<span class="pill ' + cls + '">' + h(a.天体1) + "–" + h(a.天体2) + " "
      + h(a.相位) + "</span>");
  }
  p.push("</div>");
  p.push('<div class="info" style="margin-top:12px"><span>元素：'
    + Object.entries(r.元素分布).map(([k, v]) => k + v).join(" ")
    + "</span><span>性质："
    + Object.entries(r.性质分布).map(([k, v]) => k + v).join(" ") + "</span></div>");
  p.push("</section>");
  return p.join("");
}

/* ------------------------------------------------------------------ */
/* 白话解读                                                            */
/* ------------------------------------------------------------------ */

export function renderPlain(data) {
  const P = ['<section><h2>先说人话</h2>',
    '<div class="secnote">这一段不用懂任何术语，看完就知道自己大概是什么样的人。'
    + '想研究细节，往下翻「专业排盘数据」。</div>'];

  if (data.八字) {
    const b = baziPlain(data.八字);
    P.push('<h2 style="font-size:15px;border-left-color:var(--gold)">八字 · 看你的性格和天赋</h2>');
    P.push('<div class="plain"><h3>' + h(b.性格底色.标题) + '</h3><p>' + h(b.性格底色.要点)
      + '</p><p class="sub2">' + h(b.性格底色.补充) + "</p></div>");
    P.push('<div class="plain"><h3>' + h(b.做事方式.标题) + '</h3><p>' + h(b.做事方式.要点)
      + '</p><p class="sub2">' + h(b.做事方式.补充) + "</p></div>");
    if (b.天生擅长.标签.length) {
      P.push('<div class="plain"><h3>' + h(b.天生擅长.标题) + '</h3><div class="tagline">');
      for (const t of b.天生擅长.标签) {
        P.push('<div class="tag"><b>' + h(t.名) + "</b>" + h(t.说明) + "</div>");
      }
      P.push("</div></div>");
    }
    P.push('<div class="plain"><h3>' + h(b.能量分布.标题) + "</h3><p>" + h(b.能量分布.要点)
      + '</p><p class="sub2">对你有利的五行是「' + b.能量分布.喜用.join("、")
      + "」，可以在颜色、方位、行业上多往这边靠。</p></div>");
    if (b.运气加成.标签.length) {
      P.push('<div class="plain"><h3>' + h(b.运气加成.标题) + '</h3><div class="tagline">');
      for (const t of b.运气加成.标签) {
        P.push('<div class="tag"><b>' + h(t.名) + "</b>" + h(t.说明) + "</div>");
      }
      P.push("</div></div>");
    }
    if (b.生肖) {
      const sx = b.生肖;
      P.push('<div class="plain"><h3>你的生肖</h3>'
        + '<p>你属<span class="k">' + h(sx.生肖) + "</span>——" + h(sx.特质) + "。</p>"
        + '<p class="sub2">幸运色：' + h(sx.幸运色) + " ｜ 幸运数字："
        + h(sx.幸运数字) + "</p></div>");
    }
    if (b.开运指南) {
      const lk = b.开运指南;
      P.push('<div class="plain"><h3>你的开运指南</h3>'
        + '<p>你的喜用五行是<span class="k">' + h(lk.五行) + '</span>。日常多往这些方向靠，会顺一些：</p>'
        + '<div class="luckgrid">'
        + "<div><b>幸运色</b>" + h(lk.颜色) + "</div>"
        + "<div><b>有利方位</b>" + h(lk.方位) + "</div>"
        + "<div><b>幸运数字</b>" + h(lk.数字) + "</div>"
        + "<div><b>适合行业</b>" + h(lk.行业) + "</div>"
        + "<div><b>开运饰品</b>" + h(lk.饰品) + "</div>"
        + "<div><b>日常做法</b>" + h(lk.日常) + "</div>"
        + "</div></div>");
    }
    if (b.当前阶段) {
      P.push('<div class="plain"><h3>你现在这段时期</h3>'
        + '<p>当前走在「<span class="k">' + h(b.当前阶段.干支) + "</span>」大运（"
        + h(b.当前阶段.十神) + '），主题是<span class="k">' + h(b.当前阶段.主题) + "</span>。</p></div>");
    }
  }

  if (data.紫微) {
    const z = ziweiPlain(data.紫微);
    P.push('<h2 style="font-size:15px;border-left-color:var(--gold);margin-top:22px">'
      + "紫微斗数 · 看事业、财运、感情</h2>");
    P.push('<div class="plain"><h3>命宫主星</h3><p>' + h(z.一句话) + "</p></div>");
    for (const k of ["事业方向", "财运模式", "感情模式", "四化提醒"]) {
      const blk = z[k];
      if (blk) {
        P.push('<div class="plain"><h3>' + h(blk.标题) + "</h3><p>" + h(blk.要点) + "</p></div>");
      }
    }
    if (z.开运指南) {
      const lk = z.开运指南;
      P.push('<div class="plain"><h3>开运指南 · ' + h(lk.局) + "</h3>"
        + '<p>你的五行局属<span class="k">' + h(lk.五行) + "</span>，日常可以这样用：</p>"
        + '<div class="luckgrid">'
        + "<div><b>幸运色</b>" + h(lk.颜色) + "</div>"
        + "<div><b>有利方位</b>" + h(lk.方位) + "</div>"
        + "<div><b>幸运数字</b>" + h(lk.数字) + "</div>"
        + "<div><b>适合行业</b>" + h(lk.行业) + "</div>"
        + "<div><b>开运饰品</b>" + h(lk.饰品) + "</div>"
        + "<div><b>日常做法</b>" + h(lk.日常) + "</div>"
        + "</div></div>");
    }
  }

  if (data.占星) {
    const a = astroPlain(data.占星);
    P.push('<h2 style="font-size:15px;border-left-color:var(--gold);margin-top:22px">'
      + "西洋占星 · 看性格的另一面</h2>");
    P.push('<div class="plain"><h3>一句话</h3><p>' + h(a.一句话) + "</p></div>");
    P.push('<div class="plain"><h3>' + h(a.三支柱.标题) + "</h3>");
    for (const x of a.三支柱.列表) {
      P.push('<p><span class="k">' + h(x.名) + "</span><br>" + h(x.文) + "</p>");
    }
    P.push("</div>");
    if (a.性格拼图.列表.length) {
      P.push('<div class="plain"><h3>' + h(a.性格拼图.标题) + "</h3>");
      for (const x of a.性格拼图.列表) {
        P.push('<p><span class="k">' + h(x.名) + "</span><br>" + h(x.文) + "</p>");
      }
      P.push("</div>");
    }
    if (a.人生重心.列表.length) {
      P.push('<div class="plain"><h3>' + h(a.人生重心.标题) + "</h3>");
      for (const x of a.人生重心.列表) {
        P.push('<p><span class="k">' + h(x.名) + "</span><br>" + h(x.文) + "</p>");
      }
      P.push("</div>");
    }
    if (a.关键线索) {
      P.push('<div class="plain"><h3>最关键的一条线索</h3><p>' + h(a.关键线索) + "</p></div>");
    }
    const el = a.元素配比.明细;
    P.push('<div class="plain"><h3>' + h(a.元素配比.标题) + "</h3><p>" + h(a.元素配比.要点)
      + '</p><p class="sub2">火 ' + (el.火 || 0) + " · 土 " + (el.土 || 0) + " · 风 "
      + (el.风 || 0) + " · 水 " + (el.水 || 0) + "</p></div>");
    if (a.关系张力.列表.length) {
      P.push('<div class="plain"><h3>' + h(a.关系张力.标题) + "</h3>");
      for (const x of a.关系张力.列表) P.push("<p>" + h(x.文) + "</p>");
      P.push("</div>");
    }
    if (a.实用档案.列表.length) {
      P.push('<div class="plain"><h3>' + h(a.实用档案.标题) + "</h3>");
      for (const x of a.实用档案.列表) {
        const dd = x.档案;
        P.push('<p><span class="k">' + h(x.名) + '</span></p><div class="luckgrid">'
          + "<div><b>日期范围</b>" + h(dd.日期) + "</div>"
          + "<div><b>守护星</b>" + h(dd.守护星) + "</div>"
          + "<div><b>幸运色</b>" + h(dd.幸运色) + "</div>"
          + "<div><b>幸运数字</b>" + h(dd.幸运数字) + "</div>"
          + "<div><b>幸运日</b>" + h(dd.幸运日) + "</div>"
          + "<div><b>幸运宝石</b>" + h(dd.宝石) + "</div>"
          + "<div><b>适合职业</b>" + h(dd.职业) + "</div>"
          + "<div><b>对应身体</b>" + h(dd.身体) + "</div></div>");
      }
      P.push("</div>");
    }
  }

  P.push("</section>");
  return P.join("");
}

export function renderGlossary() {
  const P = ['<section><h2>名词解释 · 看不懂的词看这里</h2><div class="gloss">'];
  for (const k in GLOSSARY) {
    P.push("<div><b>" + h(k) + "</b>：" + h(GLOSSARY[k]) + "</div>");
  }
  P.push("</div></section>");
  return P.join("");
}

export { headline };

/** 网页版唯一入口：与 app.html 里 runPython 的返回值结构保持一致。 */
export function run(v) {
  const data = build({
    sex: v.sex || "男",
    place: v.place || null,
    lat: (v.lat === undefined || v.lat === null) ? null : Number(v.lat),
    lon: (v.lon === undefined || v.lon === null) ? null : Number(v.lon),
    solar: v.solar || null,
    lunar: v.solar ? null : (v.lunar || null),
    leap: !!v.leap,
    shichen: v.shichen || null,
    hour: (!v.shichen && v.hour) ? String(v.hour).split(":").map(Number) : null,
  });
  let pro = "";
  if (data.八字) pro += renderBazi(data.八字);
  if (data.紫微) pro += renderZiwei(data.紫微);
  if (data.占星) pro += renderAstro(data.占星);
  pro += renderGlossary();
  return { headline: headline(data), plain_html: renderPlain(data), pro_html: pro };
}
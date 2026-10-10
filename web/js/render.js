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

import { pyRoundN } from "./kernel.js";
import { STAR_BRIEF } from "./ziwei.js";
import { baziPlain, ziweiPlain, astroPlain, headline, GLOSSARY, crossPlain as P_crossPlain, taohuaPlain as P_taohuaPlain, careerPlain as P_careerPlain, personaPlain as P_personaPlain } from "./plain.js";
import { paiPan as baziPaiPan } from "./bazi.js";
import { paiPan as ziweiPaiPan } from "./ziwei.js";
import { paiPan as astroPaiPan } from "./astro.js";

/ Python 的 str.replace 三连（只转这三个，顺序同 Python）。 */
function h(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/**
 * Python 的 "%.1f"。
 *
 * 必须走 pyRoundN：toFixed 是「平局远离零」（31.25 -> "31.3"），
 * Python 的 % 格式化是「平局取偶」（round(31.25, 1) -> 31.2）。
 * 五行百分比条上真实撞到过：HTML 逐字比对报 31.2% vs 31.3%。
 */
function f1(n) { return pyRoundN(n, 1).toFixed(1); }

/**
 * Python 的 "%d"。
 *
 * 关键坑：Python 的 "%d" % 5.3 是 5（向零截断），
 * 而 JS 的 String(5.3) 是 "5.3"。起运虚岁本来就是小数
 * （"5.3-15.3岁"），直接拼接会多出 ".3"，整段 HTML 就对不上了。
 */
function d(n) { return String(Math.trunc(n)); }

/**
 * 虚岁 -> 整数显示（大运区间用）。
 *
 * 与 Python 侧的 _yr 对齐：都用向下取整。
 * 虚岁本来就是整数计，写「7.3–17.3 岁」既啰嗦又没信息量。
 * 注意不能用 d()：d 是「向零截断」，-0.1 会得到 -0，
 * 而这里要的是「7.3 -> 7」这种向下取整。
 */
function yr(n) {
  const v = Number(n);
  if (!isFinite(v)) return "?";
  return String(Math.floor(v));
}

const WX_COLOR = { 木: "#5b8c5a", 火: "#c0504d", 土: "#b08d4a", 金: "#8a8f98", 水: "#4a6fa5" };

/ 占星四元素的颜色，与八字五行分开 */
const EL_COLOR = { 火: "#c0504d", 土: "#b08d4a", 风: "#4a6fa5", 水: "#3f7a52" };

/ 紫微盘 4x4 地支位置：(row, col) → 地支 */
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
    // hour 与 shichen 都传下去，由 astro 决定优先级。
    // 原先写死 hour || [12, 0]：只点时辰不填时间时，占星按中午算，
    // 而八字/紫微按真实时辰 —— 同一张盘里三个时间，结论自然互相矛盾。
    out.占星 = astroPaiPan({ solar, lunar, leap, hour, shichen,
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

/* ===================================================================
   despacify —— 把过长正文 <p> 按中文句末标点拆成多个 <p>

   与 Python 侧 _despacify 行为一致（render 层对拍比 HTML 字符串）。
   排版依据：中文一段超过 30 字就开始难读，而文案里大量是
   「三句话写在一个字符串里」，所以在渲染层按句切。

   与 Python 的差异只有一处：JS 的老版本不支持后向断言，
   所以用「替换成分隔符再 split」实现，等价于 Python 的
   re.split(r"(?<=[。！？])")。
   =================================================================== */
function _pTag(cls, body) {
  return cls ? '<p class="' + cls + '">' + body + "</p>"
             : "<p>" + body + "</p>";
}

function despacify(html, maxLen) {
  if (maxLen === undefined || maxLen === null) maxLen = 36;
  return html.replace(/<p(?: class="(li|sub2)")?>([\s\S]*?)<\/p>/g,
    function (m, cls, body) {
      cls = cls || "";
      // 有块级标签就不碰
      if (/<(div|ul|ol|table|tr|td|th|h[1-6]|section|details)\b/.test(body)) {
        return _pTag(cls, body);
      }
      const plain = body.replace(/<[^>]+>/g, "");
      if (plain.length <= maxLen) return _pTag(cls, body);
      // JS 不用后向断言：按句末标点切开
      const parts = body.split(/(?<=[。！？])/).filter(function (s) {
        return s.trim() !== "";
      });
      if (parts.length < 2) return _pTag(cls, body);
      // 短句合并，避免孤句（与 Python 一致）
      const merged = [];
      for (const p of parts) {
        const pl = p.replace(/<[^>]+>/g, "");
        const last = merged.length
          ? merged[merged.length - 1].replace(/<[^>]+>/g, "") : "";
        if (merged.length && pl.length < 8
            && last.length + pl.length <= maxLen * 2) {
          merged[merged.length - 1] += p;
          continue;
        }
        merged.push(p);
      }
      // 补未闭合的行内标签
      const out = [];
      for (let p of merged) {
        const opens = [];
        const reO = /<(b|em|i|strong|span|a)\b[^>]*>/g;
        let mm;
        while ((mm = reO.exec(p)) !== null) opens.push(mm[1]);
        const clo = [];
        const reC = /<\/([a-z]+)>/g;
        while ((mm = reC.exec(p)) !== null) clo.push(mm[1]);
        const need = opens.slice();
        for (const c of clo) {
          const i = need.indexOf(c);
          if (i >= 0) need.splice(i, 1);
        }
        const known = need.filter(function (x) {
          return ["b", "em", "i", "strong", "span", "a"].indexOf(x) >= 0;
        });
        for (let i = known.length - 1; i >= 0; i--) {
          p += "</" + known[i] + ">";
        }
        out.push(_pTag(cls, p));
      }
      return out.join("");
    });
}

export function _despacifyForTest(html) { return despacify(html); }


export function renderPlain(data) {
  const P = ['<section><h2>先说人话</h2>',
    '<div class="secnote">这一段不用懂任何术语，看完就知道自己大概是什么样的人。'
    + '想研究细节，往下翻「专业排盘数据」。</div>'];

  // 个性版本：总览，放最前面。必须与 oracle.py 逐字一致（门禁比 HTML）。
  const pe = P_personaPlain(data["八字"], data["紫微"], data["占星"]);
  if (pe["块"].length) {
    P.push('<div class="persona">');
    P.push('<div class="p-eyebrow">命 盘 印 象</div>');
    P.push('<p class="p-lead">' + h(pe["块"][0]["文"]) + "</p>");
    const rest = pe["块"].slice(1);
    if (rest.length) {
      P.push('<details class="fold"><summary>展开看：内核 / 运转'
           + " / 关系 / 独处 / 团队 / 压力</summary>");
      for (const r of rest) {
        P.push('<div class="p-block"><div class="p-k">' + h(r["块"]) + " · "
             + h(r["问"]) + '</div><div class="p-v">' + h(r["文"])
             + '</div><div class="p-src">来自 '
             + h(r["源"].map((s) => `${s[0]}（${s[1]}）`).join(" + "))
             + "</div></div>");
      }
      P.push("</details>");
    }
    P.push('<p class="p-note">' + h(pe["提醒"]) + "</p>");
    P.push("</div>");
  }

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

    // ---- 1.3.1 新增：大运逐段（折叠）----
    if (b["大运详批"] && b["大运详批"]["列表"].length) {
      const dl = b["大运详批"]["列表"];
      let curI = -1;
      dl.forEach((x, i) => { if (x["是当前"]) curI = i; });
      const curTail = curI >= 0
        ? "，当前在第 " + dl[curI]["序"] + " 步" : "";
      P.push('<details class="fold"><summary>你一生十步大运'
        + '<span class="cnt">共 ' + dl.length + " 步" + curTail
        + "</span></summary><div class=\"fbody\">"
        + '<p class="sub2">每十年换一段，是运势的主基调。'
        + "折叠起来是因为十段一起铺开太长，实际用到的是当前那一步——"
        + "所以当前那步放在最前面标出来。</p>"
        + '<div class="dy">');
      for (const x of dl) {
        const now = x["是当前"];
        const gz = x["干支"];
        const gan = gz !== "未知" ? gz[0] : "—";
        const zhi = gz !== "未知" && gz.length > 1 ? gz[1] : "";
        P.push('<div class="it' + (now ? " now" : "") + '">'
          + '<div class="hd"><span class="no">第' + x["序"] + "步</span>"
          + '<span class="gz"><span class="gan">' + h(gan) + "</span>"
          + '<span class="zhi">' + h(zhi) + "</span></span>"
          + '<span class="ss">' + h(x["十神"]) + "</span>");
        if (now) P.push('<span class="now-tag">当前</span>');
        P.push('<span class="age">' + yr(x["起始虚岁"]) + "–" + yr(x["结束虚岁"])
          + " 岁</span></div>"
          + '<div class="th">' + h(x["主题"]) + "</div>");
        if (x["正面"]) {
          P.push('<p class="li"><span class="h">好的一面</span>' + h(x["正面"]) + "</p>");
        }
        if (x["提醒"]) {
          P.push('<p class="li warn"><span class="h">要注意</span>' + h(x["提醒"]) + "</p>");
        }
        if (x["长生"]) {
          P.push('<span class="stg">十二长生 · ' + h(x["长生"]) + " —— "
            + h(x["长生含义"]) + "</span>");
        }
        P.push("</div>");
      }
      P.push("</div></div></details>");
    }

    // ---- 1.3.1 新增：流年逐年（折叠）----
    if (b["流年详批"] && b["流年详批"]["列表"].length) {
      const ll = b["流年详批"]["列表"];
      P.push('<details class="fold"><summary>未来七年的年度节奏'
        + '<span class="cnt">' + ll[0]["年"] + "–" + ll[ll.length - 1]["年"]
        + "</span></summary><div class=\"fbody\">"
        + '<p class="sub2">大运是十年的大背景，流年是这一年的具体调子。'
        + "大运管方向，流年管「今年什么事儿容易发生」。</p>"
        + '<div class="ly">');
      for (const x of ll) {
        const gz = x["干支"];
        const gan = gz !== "未知" ? gz[0] : "—";
        const zhi = gz !== "未知" && gz.length > 1 ? gz[1] : "";
        P.push('<div class="it' + (x["是今年"] ? " now" : "") + '">'
          + '<span class="yr">' + x["年"] + "</span>"
          + '<span class="tx"><b>' + h(gan) + "</b> " + h(zhi) + " · 虚岁 "
          + x["虚岁"]);
        if (x["是今年"]) P.push('<span class="yn">（今年）</span>');
        P.push("<br>" + h(x["解读"]) + "</span></div>");
      }
      P.push("</div></div></details>");
    }

    // ---- 1.3.1 新增：五行意象（折叠）----
    if (b["五行意象"] && b["五行意象"]["明细"] && b["五行意象"]["明细"].length) {
      const w = b["五行意象"];
      P.push('<details class="fold"><summary>你身上五股的劲儿'
        + '<span class="cnt">八字五行</span></summary><div class="fbody">'
        + '<p class="sub2">「多」不等于「好」，「少」也不等于「坏」——'
        + "命理里五行强弱本身没有优劣，只有适不适配你。"
        + "这里讲的是描述，不是评判。</p>"
        + '<div class="wx">');
      for (const x of w["明细"]) {
        const isTop = !!(w["最强"] && x["五行"] === w["最强"]["五行"]);
        const isLo = !!(w["最弱"] && x["五行"] === w["最弱"]["五行"]);
        P.push('<div class="it' + (isTop ? " top" : (isLo ? " lo" : "")) + '">'
          + '<div class="hd"><span class="wxn" style="color:'
          + (WX_COLOR[x["五行"]] || "#666") + '">' + h(x["五行"]) + "</span>"
          + '<span class="xiang">' + h(x["象"]) + "</span>");
        if (x["是喜用"]) P.push('<span class="tag ji">喜用</span>');
        P.push('<span class="pc">' + x["占比"].toFixed(1) + "%</span></div>"
          + '<p class="li">' + h(x["描述"]) + "</p>");
        if (x["偏多时"]) {
          P.push('<p class="li"><span class="h">偏多时</span>' + h(x["偏多时"]) + "</p>");
        }
        if (x["偏少时"]) {
          P.push('<p class="li"><span class="h">偏少时</span>' + h(x["偏少时"]) + "</p>");
        }
        P.push("</div>");
      }
      P.push("</div></div></details>");
    // 1.5.0：神煞逐条（修掉按名字猜吉凶的错判）
    if (b["神煞详批"] && b["神煞详批"]["列表"].length) {
      const ssd = b["神煞详批"];
      const cnt = ssd["计数"];
      P.push('<details class="fold"><summary>你命里的神煞'
        + '<span class="cnt">助你 ' + cnt["助你"] + " · 中性 " + cnt["中性"]
        + " · 留意 " + cnt["留意"] + "</span></summary><div class=\"fbody\">");
      if (ssd["未归类"].length) {
        // 未归类要显式说出来。默认当成吉的话，
        // 等于「没查过就说好」—— 方向是错的，而且看不见。
        P.push('<p class="warn">以下神煞还没归类，不计入吉凶统计：'
          + h(ssd["未归类"].join("、")) + "</p>");
      }
      P.push('<div class="ssx">');
      for (const x of ssd["列表"]) {
        const cls = x["类别"] === "ji" ? " ji"
                  : (x["类别"] === "xiong" ? " xiong" : "");
        P.push('<div class="it"><div class="hd">'
          + '<span class="pn' + cls + '">' + h(x["神煞"]) + "</span>"
          + '<span class="pc">' + h(x["类别说明"]) + "</span></div>"
          + '<p class="li">' + h(x["说明"]) + "</p>"
          + '<p class="sub2">查' + h(x["查法"]) + "，落" + h(x["落支"])
          + "（" + h(x["位置"]) + "）</p></div>");
      }
      P.push("</div></div></details>");
    }

    // 1.5.0：十神分布
    if (b["十神详批"] && b["十神详批"]["明细"].length) {
      const shd = b["十神详批"];
      P.push('<details class="fold"><summary>你的十神分布'
        + '<span class="cnt">哪个最重</span></summary><div class="fbody">'
        + '<p class="li"><span class="h">最重的是</span>' + h(shd["最多"]) + "</p>"
        + '<p class="sub2">' + h(shd["最多说明"]) + "</p>"
        + '<div class="ssx">');
      for (const x of shd["明细"]) {
        P.push('<div class="it"><div class="hd">'
          + '<span class="pn">' + h(x["十神"]) + "</span>"
          + '<span class="pc">' + x["合计"] + " 个 · " + x["占比"].toFixed(1)
          + "%</span></div>"
          + '<p class="li">干上 ' + x["干上"] + " · 藏干 " + x["藏干"] + "</p>"
          + '<p class="sub2">' + h(x["说明"]) + "</p></div>");
      }
      P.push("</div>");
      if (shd["组合"].length) {
        P.push("<h3 style='font-size:14px;margin:14px 0 6px'>组合看</h3>"
          + "<div class='ssx'>");
        for (const x of shd["组合"]) {
          P.push('<div class="it"><div class="hd"><span class="pn">'
            + h(x["组合"]) + "</span></div>"
            + '<p class="li">' + h(x["说明"]) + "</p></div>");
        }
        P.push("</div>");
      }
      P.push("</div></details>");
    }

    }
    // 1.6.0：六亲
    if (b["六亲详批"] && b["六亲详批"]["列表"].length) {
      const kd = b["六亲详批"];
      P.push('<details class="fold"><summary>六亲怎么看'
        + '<span class="cnt">' + h(kd["性别"]) + "</span></summary>"
        + '<div class=\"fbody\">'
        + '<p class="sub2">' + h(kd["口径"]) + "</p>"
        + '<div class="ssx">');
      for (const it of kd["列表"]) {
        if (!it["位置"].length) {
          // 一颗都没出现 —— 要说出来，不能留个空卡片让人以为漏了
          P.push('<div class="it"><div class="hd">'
            + '<span class="pn">' + h(it["角色"]) + "</span>"
            + '<span class="pc">这一块没出现</span></div>'
            + '<p class="li">你这张盘里' + h(it["星"].join("、"))
            + "都没有显出来，不代表没这部分关系，"
            + "只说明它不靠星象主导。</p></div>");
          continue;
        }
        P.push('<div class="it"><div class="hd">'
          + '<span class="pn">' + h(it["角色"]) + "</span>"
          + '<span class="pc">' + h(it["星"].join("、")) + " · "
          + it["个数"] + " 个"
          + (it["有透"] ? "，有透干" : "，都藏在支里") + "</span></div>"
          + '<p class="li">' + h(it["说明"]) + "</p>");
        for (const x of it["位置"]) {
          P.push('<p class="sub2">' + h(x["柱"]) + h(x["干支"]) + " "
            + h(x["十神"]) + "（"
            + (x["透"] ? "透干，明面上的分量重"
                       : "藏" + h(x["藏"] || "") + "，存在感弱一些")
            + "）</p>");
        }
        P.push("</div>");
      }
      P.push("</div>");
      P.push("<h3 style='font-size:14px;margin:14px 0 6px'>四柱各代表谁</h3>");
      P.push('<div class="ssx">');
      for (const x of kd["柱位"]) {
        P.push('<div class="it"><div class="hd">'
          + '<span class="pn">' + h(x["柱"]) + h(x["干支"])
          + "</span></div>"
          + '<p class="li">' + h(x["代表"]) + "</p></div>");
      }
      P.push("</div></div></details>");
    }
  }   // <- 收尾 if (data.八字)

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
    // 1.5.0 新增：紫微四块（十二宫 / 大限 / 流年 / 四化）
    // 手写而非从 Python 转换 —— 转换后 %s、.get()、列表推导式
    // 都会残留，46 处，改起来比重写更容易漏。
    if (z["十二宫详批"] && z["十二宫详批"]["列表"].length) {
      const pl = z["十二宫详批"]["列表"];
      P.push('<details class="fold"><summary>你的十二宫'
        + '<span class="cnt">逐宫看</span></summary><div class="fbody">'
        + '<p class="sub2">十二宫代表人生十二个领域。'
        + "「主星」决定这个领域的底色；宫里没有主星很常见，"
        + "要借对宫的星来看，那不是缺陷。</p>"
        + '<div class="pl">');
      for (const p2 of pl) {
        let cls = "";
        const marks = [];
        if (p2["是命宫"]) { cls += " ming"; marks.push("命宫"); }
        if (p2["是身宫"]) { cls += " shen"; marks.push("身宫"); }
        P.push('<div class="it' + cls + '"><div class="hd">'
          + '<span class="pn">' + h(p2["宫名"]) + "</span>"
          + '<span class="gz2">' + h(p2["干支"]) + "</span>");
        if (marks.length) {
          P.push('<span class="tag hi">' + h(marks.join("、")) + "</span>");
        }
        P.push('<span class="pc">主星 '
          + h(p2["主星"].length ? p2["主星"].join("、") : "（空宫）")
          + "</span></div>"
          + '<p class="li">' + h(p2["含义"]) + "</p>");
        if (p2["借宫"]) {
          P.push('<p class="li"><span class="h">借对宫</span>'
            + "本宫无主星，借「" + h(p2["借宫"]) + "」的 "
            + h(p2["借宫主星"].length ? p2["借宫主星"].join("、") : "（对宫也空宫）")
            + " 来论。</p>");
        }
        if (p2["标签"].length) {
          const t2 = p2["标签"].map((t) => t["星"] + "=" + t["说明"]).join("；");
          P.push('<p class="li"><span class="h">星曜</span>' + h(t2) + "</p>");
        }
        if (p2["留意"].length) {
          const c2 = p2["留意"].map((c) => c["星"] + "=" + c["说明"]).join("；");
          P.push('<p class="li warn"><span class="h">要留意</span>' + h(c2) + "</p>");
        }
        P.push("</div>");
      }
      P.push("</div></div></details>");
    }

    if (z["大限详批"] && z["大限详批"]["列表"].length) {
      const dl = z["大限详批"]["列表"];
      const cur = z["流年详情"] || {};
      const curDx = cur["当前大限宫"] || "";
      P.push('<details class="fold"><summary>你一生十二步大限'
        + '<span class="cnt">紫微的十年分段</span></summary><div class="fbody">'
        + '<p class="sub2">大限走的是<b>宫位</b>而不是十神 —— '
        + "每十年重心落在哪个宫，那十年的主语就是那个宫代表的事。"
        + "和大运是两套不同的分段方式，别混着看。</p>"
        + '<div class="dx">');
      for (const x of dl) {
        const now = !!curDx && x["宫位"] === curDx;
        P.push('<div class="it' + (now ? " now" : "") + '"><div class="hd">'
          + '<span class="age">' + yr(x["虚岁起"]) + "–" + yr(x["虚岁止"])
          + " 岁</span>"
          + '<span class="pn">' + h(x["宫位"]) + "</span>"
          + '<span class="gz2">' + h(x["干支"]) + "</span>");
        if (now) P.push('<span class="tag hi">当前大限</span>');
        P.push('<span class="pc">'
          + h(x["主星"].length ? x["主星"].join("、") : "空宫")
          + "</span></div>"
          + '<p class="li">' + h(x["主题"]) + "</p>"
          + '<p class="sub2">' + h(x["宫位含义"]) + "</p></div>");
      }
      P.push("</div></div></details>");
    }

    if (z["流年详情"]) {
      const ln = z["流年详情"];
      P.push('<details class="fold"><summary>今年的落点'
        + '<span class="cnt">' + h(String(ln["年"])) + "年 " + h(String(ln["干支"]))
        + '</span></summary><div class="fbody">'
        + '<div class="info" style="margin:0 0 10px">'
        + "<span>虚岁 <b>" + h(String(ln["虚岁"])) + "</b></span>"
        + "<span>流年命宫 <b>" + h(ln["流年命宫名"]) + h(ln["流年命宫"])
        + "</b></span>"
        + "<span>当前大限 <b>" + h(ln["当前大限"]) + "</b></span></div>");
      if (ln["命宫含义"]) {
        P.push('<p class="li"><span class="h">今年重心</span>'
          + h(ln["流年命宫名"]) + " —— " + h(ln["命宫含义"]) + "</p>");
      }
      if (ln["大限主题"]) {
        P.push('<p class="li"><span class="h">大限主线</span>'
          + h(ln["大限主题"]) + "</p>");
      }
      P.push('<p class="sub2">' + h(ln["说明"]) + "</p>");
      P.push("</div></details>");
    }

    if (z["四化详批"] && z["四化详批"].length) {
      P.push('<details class="fold"><summary>四化落在哪'
        + '<span class="cnt">禄权科忌</span></summary><div class="fbody">'
        + '<p class="sub2">生年四化是「哪颗星被强化」，'
        + "它落在哪个宫，那一块就跟着强化。化忌不是坏事，"
        + "是这辈子要学的课题。</p>"
        + '<div class="sh">');
      for (const h2 of z["四化详批"]) {
        const cls = h2["化"] === "化忌" ? " ji" : "";
        P.push('<div class="it' + cls + '"><div class="hd">'
          + '<span class="pn">' + h(h2["化"]) + "</span>"
          + '<span class="gz2">' + h(h2["星"]) + "</span>");
        if (h2["宫位"]) {
          P.push('<span class="tag">落' + h(h2["宫位"]) + "宫</span>");
        }
        P.push('<span class="pc">' + h(h2["角色"]) + "</span></div>"
          + '<p class="li">' + h(h2["要点"]) + "</p>");
        if (h2["宫位含义"]) {
          P.push('<p class="sub2">该宫管的是：' + h(h2["宫位含义"]) + "</p>");
        }
        P.push("</div>");
      }
      P.push("</div></div></details>");
    }

    // 1.6.0：夫妻宫。措辞走「需要磨合的地方」，不走「好 / 坏」。
    const sp = z["夫妻详批"] || {};
    // 一律用 .length：Python 的 [] 是 falsy，JS 的 [] 是 truthy，
    // 直接判空会两边行为分叉（这批已经栽过一次）。
    if ((sp["主星"] && sp["主星"].length) || (sp["煞星"] && sp["煞星"].length)) {
      P.push('<details class="fold"><summary>夫妻宫'
        + '<span class="cnt">'
        + h(sp["宫干"] ? "宫干 " + sp["宫干"] : "")
        + h(sp["大限年龄"] ? "大限 " + sp["大限年龄"] : "")
        + "</span></summary>"
        + '<div class=\"fbody\">');
      // 用 .length 而不是直接判空：Python 的 [] 是 falsy，
      // JS 的 [] 是 **truthy**，直接判空会多输出一段「主星：」。
      if (sp["组合"]) {
        P.push('<p class="li"><span class="h">' + h(sp["组合"]["型"])
          + "</span>" + h(sp["组合"]["说明"]) + "</p>");
      } else if (sp["主星"] && sp["主星"].length) {
        P.push('<p class="li">主星：' + h(sp["主星"].join("、")) + "</p>");
      }
      if (sp["四化"] && sp["四化"].length) {
        // 主星上的四化是「这块星曜的当前状态」，要单独讲 ——
        // 混进煞星或「未解读」里都是错的
        P.push("<h3 style='font-size:14px;margin:14px 0 6px'>主星带四化</h3>"
          + "<div class='ssx'>");
        for (const x of sp["四化"]) {
          P.push('<div class="it"><div class="hd">'
            + '<span class="pn">' + h(x["星"]) + "</span>"
            + '<span class="pc">' + h(x["化"]) + "</span></div>"
            + '<p class="li">' + h(x["说明"]) + "</p></div>");
        }
        P.push("</div>");
      }
      if (sp["对宫"]) {
        P.push('<p class="sub2">对宫是' + h(sp["对宫"])
          + "宫 —— 夫妻和事业这一头互相牵动，不只是感情的事。</p>");
      }
      if (sp["煞星"].length) {
        P.push("<h3 style='font-size:14px;margin:14px 0 6px'>要磨合的地方</h3>"
          + "<div class='ssx'>");
        for (const x of sp["煞星"]) {
          P.push('<div class="it"><div class="hd">'
            + '<span class="pn xiong">' + h(x["星"]) + "</span>"
            + '<span class="pc">' + h(x["型"]) + "</span></div>"
            + '<p class="li">' + h(x["说明"]) + "</p></div>");
        }
        P.push("</div>");
      }
      if (sp["未解读"].length) {
        // 查不到解读的星要显式报出来，不能静默跳过
        P.push('<p class="warn">这些星还没写解读：'
          + h(sp["未解读"].join("、")) + "</p>");
      }
      if (sp["大限说明"]) {
        P.push("<h3 style='font-size:14px;margin:14px 0 6px'>什么时候走到这块</h3>");
        P.push('<p class="li">大限虚岁 ' + h(sp["大限年龄"]) + "</p>");
        P.push('<p class="sub2">' + h(sp["大限说明"]) + "</p>");
      }
      P.push("</div></details>");
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
    // 1.3.1 新增：四元素逐项展开（折叠）
    if (a.元素配比.逐项 && a.元素配比.逐项.length) {
      P.push('<details class="fold"><summary>四种元素逐项看'
        + '<span class="cnt">占星四元素</span></summary><div class="fbody">'
        + '<div class="note-sys">这里的火 / 土 / 风 / 水是'
        + "<b>西洋占星的四元素</b>，由行星与星座决定，"
        + "和八字那套木火土金水<b>是两套独立体系</b> ——"
        + "没有换算公式，也不该互相替代。两套都看，"
        + "指向同一件事时结论才算被交叉印证。</div>"
        + '<div class="el">');
      for (const x of a.元素配比.逐项) {
        P.push('<div class="it"><div class="hd">'
          + '<span class="en" style="color:' + (EL_COLOR[x.元素] || "#666")
          + '">' + h(x.元素) + "</span>");
        if (x.最旺) P.push('<span class="tag hi">最多</span>');
        if (x.完全缺) P.push('<span class="tag lo">完全没有</span>');
        P.push('<span class="pc">' + x.个数 + " 个 · " + x.占比.toFixed(0)
          + "%</span></div>");
        if (x.多时) {
          P.push('<p class="li"><span class="h">这一项旺时</span>' + h(x.多时) + "</p>");
        }
        if (x.少时) {
          P.push('<p class="li"><span class="h">这一项缺时</span>' + h(x.少时) + "</p>");
        }
        P.push("</div>");
      }
      P.push("</div></div></details>");
    }
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
    // 1.5.0：轴点
    if (a["轴点详批"] && a["轴点详批"]["列表"].length) {
      P.push('<details class="fold"><summary>两个轴点'
        + '<span class="cnt">上升与天顶</span></summary><div class="fbody">'
        + '<p class="sub2">上升不是「真正的你」，是别人看到的你；'
        + "天顶是命运把你推向的位置。"
        + "两者都不是性格本身，"
        + "而是「你在别人眼里」和「你被认可的方向」。</p>"
        + '<div class="ssx">');
      for (const x of a["轴点详批"]["列表"]) {
        P.push('<div class="it"><div class="hd">'
          + '<span class="pn">' + h(x["名"]) + "</span>"
          + '<span class="gz2">' + h(x["符号"]) + "</span>"
          + '<span class="pc">' + h(x["星座"]) + " " + h(x["度数"])
          + "</span></div>"
          + '<p class="li"><span class="h">' + h(x["角色"]) + "</span>"
          + h(x["含义"]) + "</p></div>");
      }
      P.push("</div></div></details>");
    }

    // 1.5.0：行星性质
    if (a["性质详批"] && a["性质详批"]["明细"].length) {
      const qd = a["性质详批"];
      P.push('<details class="fold"><summary>你的行星性质'
        + '<span class="cnt">' + h(qd["最多"]) + " 最多</span></summary>"
        + '<div class="fbody">'
        + '<p class="li">' + h(qd["最多说明"]) + "</p>"
        + '<div class="ssx">');
      for (const x of qd["明细"]) {
        P.push('<div class="it"><div class="hd">'
          + '<span class="pn">' + h(x["性质"]) + "</span>"
          + '<span class="pc">' + x["个数"] + " 个</span></div>"
          + '<p class="sub2">' + h(x["含义"]) + "</p></div>");
      }
      P.push("</div>");
      P.push("<h3 style='font-size:14px;margin:14px 0 6px'>各星落哪类</h3>");
      P.push('<p class="sub2">'
        + h(qd["各星"].map((x) => x["天体"] + x["性质"][0]).join("；"))
        + "</p>");
      P.push("</div></details>");
    }

    // 1.5.0：全部相位
    if (a["相位详批"] && a["相位详批"]["合计"]) {
      const ad = a["相位详批"];
      P.push('<details class="fold"><summary>全部相位'
        + '<span class="cnt">和谐 ' + ad["和谐"].length + " · 张力 "
        + ad["张力"].length + "</span></summary><div class=\"fbody\">"
        + '<p class="sub2">和谐相是天生助力，张力相是要练的地方 —— '
        + "「哪些是助力、哪些是功课」这个分组比逐个列更重要。"
        + "之前只讲了强度前 4 组，其余 19 组算了白算。</p>");
      const groups = [["和谐", "ji", "天生的助力"],
                      ["张力", "xiong", "要练的地方"]];
      for (const grp of groups) {
        const tag = grp[0], cls = grp[1], title = grp[2];
        if (!ad[tag].length) continue;
        P.push("<h3 style='font-size:14px;margin:14px 0 6px'>" + title
          + "（" + ad[tag].length + " 组）</h3>");
        P.push('<div class="ssx">');
        for (const x of ad[tag]) {
          P.push('<div class="it"><div class="hd">'
            + '<span class="pn' + (cls ? " " + cls : "") + '">'
            + h(x["职能1"]) + " · " + h(x["职能2"]) + "</span>"
            + '<span class="pc">' + h(x["强度档"]) + " " + x["强度"].toFixed(2)
            + "</span></div>"
            + '<p class="li">' + h(x["说明"]) + "</p>"
            + '<p class="sub2">' + h(x["强度含义"]) + "</p></div>");
        }
        P.push("</div>");
      }
      P.push("</div></details>");
    }

    }
    // 1.6.0：关系宫
    if (a["关系宫详批"] && a["关系宫详批"]["列表"].length) {
      const hd2 = a["关系宫详批"];
      let nEmpty = 0;
      for (const x of hd2["列表"]) if (x["空"]) nEmpty++;
      P.push('<details class="fold"><summary>关系相关的宫'
        + '<span class="cnt">' + hd2["列表"].length + " 宫 · 空 "
        + nEmpty + " 个</span></summary>"
        + '<div class=\"fbody\">'
        // 概述不能直接用「空宫说明」—— 那是给单个空宫写的，
        // 放在开头会变成「整块的关系宫都没星」的意思，方向是错的。
        + '<p class="sub2">这五宫分别管伴侣、深度联结、家、事业角色与朋友。'
        + "先看每宫管什么，再看落了哪些星。</p>");
      if (nEmpty) {
        P.push('<p class="sub2">其中 ' + nEmpty + " 宫没有星。"
          + h(hd2["空宫说明"]) + "</p>");
      }
      P.push('<div class="ssx">');
      for (const x of hd2["列表"]) {
        P.push('<div class="it"><div class="hd">'
          + '<span class="pn">第 ' + x["宫"] + " 宫</span>"
          + '<span class="pc">' + h(x["星座"]) + "</span></div>"
          + '<p class="li"><span class="h">' + h(x["名"]) + "</span>"
          + h(x["管什么"]) + "</p>");
        if (x["空"]) {
          P.push('<p class="sub2">这一宫没有星，不靠外力推 —— '
            + "怎么走看你自己的选择。</p>");
        } else {
          for (const y of x["星"]) {
            P.push('<p class="li">' + h(y["名"]) + " · " + h(y["说明"]) + "</p>");
          }
        }
        P.push("</div>");
      }
      P.push("</div></div></details>");
    }
  }

  // ---------- B 类：三盘交叉 ----------
  // 排布与 oracle.py 保持一致：一致的当主结论、分歧的折起来。
  // 必须**逐字相同** —— render 层门禁比的是 HTML 字符串。
  if ("八字" in data || "紫微" in data || "占星" in data) {
    const x = P_crossPlain(data["八字"], data["紫微"], data["占星"]);
    if (x["一致"].length || x["分歧"].length || x["单盘"].length) {
      P.push('<h2 style="font-size:15px;border-left-color:var(--gold)">'
           + "三盘交叉 · 几套体系一起看</h2>");
      P.push('<div class="plain"><p>' + h(x["要点"]) + '</p><p class="sub2">'
           + h(x["说明"]) + "</p></div>");

      // 「怎么读」放最前面：先说怎么看，再看结论
      P.push('<div class="plain"><h3>先说怎么读</h3>'
           + "<p class=\"li\">三套体系是<em>各自独立</em>算的，"
           + "彼此之间没有换算、也不互相验证。</p>"
           + "<p class=\"li\">下面<em>直接显示</em>的，是三边都指向"
           + "同一头的那几面 —— 这种面可以作为你的倾向来看。</p>"
           + "<p class=\"li\">折起来的「三边说法不同」不是哪一套错了，"
           + "而是说明你在这一面本来就比较多 —— "
           + "不同场景下你本来就会表现得不一样。</p>"
           + "<p class=\"li\">三套体系衡量的是不同的东西，"
           + "所以这里不投票、不合成一个「唯一答案」："
           + "投出来的那个数字不对应任何一套体系真实的算法。</p></div>");

      if (x["一致"].length) {
        P.push('<div class="plain"><h3>三边都指向同一头</h3>'
             + '<div class="tagline">');
        for (const r of x["一致"]) {
          P.push('<div class="tag"><b>' + h(r["维度"]) + "</b>"
               + h(r["同向"]) + "</div>");
        }
        P.push('</div><p class="sub2">依据：'
             + h(x["一致"][0]["各家"].map((g) => `${g["盘"]} ${g["依据"]}`)
                  .join(" / ")) + "</p></div>");
      }

      const rest = x["分歧"].concat(x["单盘"]);
      if (rest.length) {
        P.push('<details class="ssx"><summary>三边说法不同（'
             + rest.length + " 个维度，点开看各自怎么说）</summary>"
             + '<div class="plain">');
        for (const r of rest) {
          P.push('<div class="xsx"><p class="xsx-q">' + h(r["维度"]) + "："
               + h(r["问"]) + "</p>");
          for (const g of r["各家"]) {
            P.push('<p class="li"><b>' + h(g["盘"]) + "</b>：" + h(g["端"])
                 + '　<span class="sub2">' + h(g["依据"]) + "</span></p>");
          }
          if (r["一致"]) {
            P.push('<p class="sub2">只有一盘给了信号，'
                 + "无从交叉 —— 这里只代表那一套体系怎么看。</p>");
          }
          P.push("</div>");
        }
        P.push("</div></details>");
      }

      P.push('<details class="ssx"><summary>这三边分别按什么算的'
           + "（想查证时点开）</summary>"
           + '<div class="plain"><div class="tagline">');
      for (const s of x["依据"]) {
        P.push('<div class="tag"><b>' + h(s["盘"]) + "</b>" + h(s["源"])
             + "</div>");
      }
      P.push('</div><p class="sub2">' + h(x["提醒"]) + "</p></div></details>");
    }
  }

  // ---------- C 类：桃花星 + 行业细分 ----------
  // 与 oracle.py 逐字一致（门禁比 HTML 字符串）。
  // 行业按依据分组：同一依据下的行业是同一件事的展开，
  // 铺平会被读成十几个并列且互相冲突的结论。
  const th = P_taohuaPlain(data["八字"], data["紫微"], data["占星"]);
  if (th["列表"].length) {
    P.push('<h2 style="font-size:15px;border-left-color:var(--gold)">'
         + h(th["标题"]) + "</h2>");
    P.push('<div class="plain"><p>' + h(th["要点"]) + "</p>"
         + "<p class=\"li\">下面三边说的是<em>不同层面</em>，"
         + "不是互相矛盾：八字看的是人缘的广度，"
         + "紫微看的是你在关系里的姿态，"
         + "占星看的是你被什么样的人吸引、"
         + "以及你希望怎么被对待。</p></div>");
    P.push('<details class="ssx"><summary>三盘分别怎么说'
         + "（点开逐条对照）</summary><div class=\"plain\">");
    for (const r of th["列表"]) {
      P.push('<div class="xsx"><p class="xsx-h"><b>' + h(r["盘"]) + "</b>"
           + h(r["项"]) + "</p>");
      P.push('<p class="li">→ ' + h(r["答"]) + '　<span class="sub2">'
           + h(r["依据"]) + "</span></p>");
      P.push('<p class="sub2">' + h(r["说明"]) + "</p>");
      P.push("</div>");
    }
    P.push('<p class="sub2">' + h(th["提醒"]) + "</p></div></details>");
  }

  const cr = P_careerPlain(data["八字"], data["紫微"], data["占星"]);
  if (cr["列表"].length) {
    P.push('<h2 style="font-size:15px;border-left-color:var(--gold)">'
         + h(cr["标题"]) + "</h2>");
    P.push('<div class="plain"><p>' + h(cr["要点"]) + '</p><p class="sub2">'
         + h(cr["提醒"]) + "</p></div>");
    const groups = [];
    for (const r of cr["列表"]) {
      const k = r["盘"] + "\u0000" + r["依据"];
      const last = groups[groups.length - 1];
      if (last && last[0] === k) last[1].push(r);
      else groups.push([k, [r]]);
    }
    if (groups.length > 1) {
      P.push('<details class="ssx"><summary>' + groups.length
           + " 组方向（点开看每组有哪些行业）</summary>"
           + '<div class="plain">');
    } else {
      P.push('<div class="plain">');
    }
    for (const [k, items] of groups) {
      const pan = items[0]["盘"];
      const why = items[0]["依据"];
      P.push('<p class="xsx-h"><b>' + h(pan) + "</b>" + h(why) + "</p>");
      P.push('<div class="tagline">');
      for (const r of items) {
        P.push('<div class="tag"><b>' + h(r["行业"]) + "</b>"
             + h(r["角色"].join("、")) + "</div>");
      }
      P.push('</div><p class="sub2">角色类型是行业内的通用分类，'
           + "不是「你应该去当的职位」。</p>");
    }
    if (groups.length > 1) {
      P.push("</div></details>");
    } else {
      P.push("</div>");
    }
  }

  P.push("</section>");

  P.push("</section>");
  return despacify(P.join(""));
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

/ 网页版唯一入口：与 app.html 里 runPython 的返回值结构保持一致。 */
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
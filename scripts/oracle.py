#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""命理神机 · 统一入口（零第三方依赖，仅标准库）。

一次输入生辰，同时排八字、紫微斗数、西洋占星，输出：
  - 终端报告（人类可读）
  - 自包含 HTML 命盘（单文件、零外链、可离线双击打开，不联网、不上传）

用法
----
python oracle.py --solar 1990-05-15 --hour 12:00 --sex 男 --place 北京 --lat 39.9 --lon 116.4
python oracle.py --solar 1990-05-15 --hour 12:00 --sex 男 --out mingpan.html
python oracle.py --solar 1990-05-15 --hour 12:00 --sex 男 --json
python oracle.py --lunar 1990-04-21 --shichen 午 --sex 女 --only ziwei
"""

import argparse
import json
import sys

from almanac import setup_console
import bazi as M_bazi
import ziwei as M_ziwei
import astro as M_astro
import plain as M_plain

ZHI = "子丑寅卯辰巳午未申酉戌亥"

# 紫微盘 4x4 地支位置：(row, col) → 地支
PAN_LAYOUT = {
    (0, 0): "巳", (0, 1): "午", (0, 2): "未", (0, 3): "申",
    (1, 0): "辰", (1, 3): "酉",
    (2, 0): "卯", (2, 3): "戌",
    (3, 0): "寅", (3, 1): "丑", (3, 2): "子", (3, 3): "亥",
}


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


def build(solar=None, lunar=None, leap=False, hour=None, shichen=None, sex="男",
          place=None, lat=None, lon=None, only=None, year=None):
    out = {}
    if only in (None, "bazi"):
        out["八字"] = M_bazi.pai_pan(solar=solar, lunar=lunar, leap=leap, hour=hour,
                                    shichen=shichen, sex=sex, place=place, longitude=lon)
    if only in (None, "ziwei"):
        out["紫微"] = M_ziwei.pai_pan(solar=solar, lunar=lunar, leap=leap, hour=hour,
                                      shichen=shichen, sex=sex, place=place, year=year)
    if only in (None, "astro"):
        # 传 hour 与 shichen 两者，由 astro.pai_pan 决定优先级。
        # 原先写死 hour or (12, 0)：用户只点时辰不填时间时，
        # 八字/紫微按真实时辰算、占星却按中午 12 点算 —— 同一张盘里三个时间。
        out["占星"] = M_astro.pai_pan(solar=solar, lunar=lunar, leap=leap,
                                      hour=hour, shichen=shichen, sex=sex,
                                      lat=lat, lon=lon, place=place)
    return out


# ---------------------------------------------------------------------------
# HTML 渲染（自包含，零外链）
# ---------------------------------------------------------------------------

CSS = """
:root{--bg:#f7f4ee;--card:#fffdf8;--ink:#2b2621;--sub:#6b6154;--line:#e3dbcd;
--red:#a8322d;--gold:#a8842c;--green:#3f7a52;--blue:#2f5d7c;--purple:#6b4a7a;}
*{box-sizing:border-box}
body{margin:0;padding:28px 18px 60px;background:var(--bg);color:var(--ink);
font-family:"PingFang SC","Microsoft YaHei","Noto Sans SC",system-ui,sans-serif;line-height:1.65}
.wrap{max-width:1000px;margin:0 auto}
h1{font-size:26px;text-align:center;margin:0 0 4px;letter-spacing:6px;color:var(--red)}
.sub{text-align:center;color:var(--sub);font-size:13px;margin-bottom:22px}
section{background:var(--card);border:1px solid var(--line);border-radius:14px;
padding:20px 22px;margin-bottom:20px;box-shadow:0 1px 3px rgba(0,0,0,.03)}
h2{font-size:17px;margin:0 0 16px;padding-left:11px;border-left:4px solid var(--red);
letter-spacing:2px}
.info{display:flex;flex-wrap:wrap;gap:8px 26px;font-size:14px;color:var(--sub);margin-bottom:14px}
.info b{color:var(--ink);font-weight:600}
table{width:100%;border-collapse:collapse;font-size:14px}
th,td{border:1px solid var(--line);padding:7px 9px;text-align:center}
th{background:#f1ece1;font-weight:600;color:var(--sub);font-size:13px}
.gz{font-size:20px;font-weight:700;letter-spacing:2px}
.gan{color:var(--red)}.zhi{color:var(--blue)}
.ss{font-size:12px;color:var(--sub)}
.cang{font-size:12px;color:var(--sub);line-height:1.5}
.pill{display:inline-block;padding:1px 8px;border-radius:9px;font-size:12px;
background:#f0e9db;color:var(--sub);margin:2px 3px 2px 0}
.pill.ji{background:#e8f2ea;color:var(--green)}
.pill.xiong{background:#fae9e7;color:var(--red)}
.bar{display:flex;align-items:center;gap:9px;margin:6px 0;font-size:13px}
.bar .lb{width:30px;color:var(--sub)}
.bar .tr{flex:1;height:16px;background:#efe9dd;border-radius:8px;overflow:hidden}
.bar .fl{height:100%;border-radius:8px}
.bar .vl{width:52px;text-align:right;color:var(--sub);font-variant-numeric:tabular-nums}
/* 紫微盘 */
.pan{display:grid;grid-template-columns:repeat(4,1fr);grid-template-rows:repeat(4,1fr);
gap:6px;aspect-ratio:1/1;max-width:680px;margin:0 auto}
.cell{border:1px solid var(--line);border-radius:9px;padding:7px;background:#fffefb;
font-size:12px;overflow:hidden;position:relative;min-height:0}
.cell.ming{border-color:var(--red);background:#fdf6f0;box-shadow:0 0 0 1px var(--red) inset}
.cell.shen{border-style:dashed}
.cell .pos{font-size:11px;color:var(--sub);display:flex;justify-content:space-between}
.cell .gz2{font-size:15px;font-weight:700;margin:2px 0}
.cell .stars{line-height:1.45}
.star{color:var(--ink)}
.star.main{color:var(--red);font-weight:700}
.star.hua{color:var(--gold)}
.star.aux{color:var(--blue)}
.center{grid-column:2/4;grid-row:2/4;border:1px solid var(--line);border-radius:9px;
background:#faf6ee;display:flex;flex-direction:column;justify-content:center;
align-items:center;padding:14px;text-align:center;font-size:13px;gap:5px}
.center .t{font-size:16px;font-weight:700;letter-spacing:3px;color:var(--red)}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:18px}
@media(max-width:720px){.grid2{grid-template-columns:1fr}}
.liu{display:flex;flex-wrap:wrap;gap:6px;font-size:12px}
.liu span{padding:3px 9px;background:#f1ece1;border-radius:8px}
.warn{color:var(--red);font-size:13px;margin-top:8px}
.foot{text-align:center;color:var(--sub);font-size:12px;margin-top:26px;line-height:1.8}
/* 白话解读 */
.headline{background:linear-gradient(135deg,#fdf6ee,#f6eee0);border:1px solid #e8dcc8;
border-radius:14px;padding:20px 24px;margin-bottom:20px;text-align:center}
.headline .big{font-size:19px;font-weight:700;color:var(--red);line-height:1.75}
.headline .tip{font-size:13px;color:var(--sub);margin-top:8px}
.plain{background:#fbf8f1;border-left:4px solid var(--gold);border-radius:0 10px 10px 0;
padding:13px 18px;margin:11px 0}
.plain h3{margin:0 0 7px;font-size:15px;color:var(--red);letter-spacing:1px}
.plain p{margin:5px 0;font-size:14px;line-height:1.85}
.plain .k{color:var(--red);font-weight:600}
.plain .sub2{color:var(--sub);font-size:13px}
.tagline{display:flex;flex-wrap:wrap;gap:8px;margin:8px 0 2px}
.tagline .tag{background:#fff;border:1px solid var(--line);border-radius:10px;
padding:8px 12px;font-size:13px;flex:1 1 250px;min-width:210px;line-height:1.65}
.tagline .tag b{color:var(--red);display:block;margin-bottom:3px;font-size:14px}
/* 折叠区块：新增内容默认收起，首屏保持原来的长度。
   用原生 <details> 而不是 JS 展开 —— 零脚本就能开，合上时浏览器
   不会渲染里面的内容，页面首屏成本不涨。 */
details.fold{background:#fbf8f1;border:1px solid var(--line);border-radius:11px;
 margin:12px 0;overflow:hidden}
details.fold>summary{cursor:pointer;padding:11px 16px;font-size:14px;font-weight:600;
 color:var(--red);list-style:none;display:flex;align-items:center;gap:8px}
details.fold>summary::-webkit-details-marker{display:none}
details.fold>summary::before{content:"▸";color:var(--gold);font-size:13px;
 transition:transform .15s}
details.fold[open]>summary::before{transform:rotate(90deg)}
details.fold>summary .cnt{margin-left:auto;color:var(--sub);font-weight:400;font-size:12px}
details.fold .fbody{padding:2px 16px 14px}
/* 大运 / 流年逐条 */
.dy{display:grid;grid-template-columns:repeat(auto-fill,minmax(268px,1fr));gap:9px;
 margin-top:4px}
.dy .it{background:#fff;border:1px solid var(--line);border-radius:10px;padding:10px 13px;
 line-height:1.7}
.dy .it.now{border-color:var(--red);background:#fdf6f0;box-shadow:0 0 0 1px var(--red) inset}
.dy .hd{display:flex;align-items:baseline;gap:7px;margin-bottom:4px;flex-wrap:wrap}
.dy .no{font-size:12px;color:var(--sub)}
.dy .gz{font-size:17px;font-weight:700;letter-spacing:1px}
.dy .ss{font-size:12px;color:var(--blue)}
.dy .age{margin-left:auto;font-size:12px;color:var(--sub)}
.dy .now-tag{font-size:11px;background:var(--red);color:#fff;border-radius:8px;
 padding:0 7px;letter-spacing:1px}
.dy .th{font-size:13px;color:var(--red);font-weight:600;margin-bottom:2px}
.dy .li{font-size:13px;margin:4px 0 0;color:var(--ink)}
.dy .li .h{color:var(--sub);margin-right:5px}
.dy .li.warn{color:#8a4a20}
.dy .stg{display:inline-block;font-size:11px;background:#f0e9db;color:var(--sub);
 border-radius:8px;padding:0 7px;margin-top:5px}
/* 流年 */
.ly{display:flex;flex-direction:column;gap:6px;margin-top:4px}
.ly .it{display:flex;gap:11px;align-items:flex-start;background:#fff;
 border:1px solid var(--line);border-radius:10px;padding:9px 13px;line-height:1.7}
.ly .it.now{border-color:var(--red);background:#fdf6f0}
.ly .yr{font-size:16px;font-weight:700;width:56px;flex:none;font-variant-numeric:tabular-nums}
.ly .tx{flex:1;font-size:13px}
/* 五行意象 */
.wx{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:9px;margin-top:4px}
.wx .it{background:#fff;border:1px solid var(--line);border-radius:10px;padding:10px 13px;
 line-height:1.7;font-size:13px}
.wx .it.top{border-color:var(--gold)}
.wx .it.lo{border-style:dashed}
.wx .hd{display:flex;align-items:baseline;gap:8px;margin-bottom:3px;flex-wrap:wrap}
.wx .wxn{font-size:19px;font-weight:700}
.wx .xiang{color:var(--red)}
.wx .pc{margin-left:auto;font-size:13px;color:var(--sub);font-variant-numeric:tabular-nums}
.wx .tag{font-size:11px;border-radius:8px;padding:0 7px;background:#f0e9db;color:var(--sub)}
.wx .tag.ji{background:#e8f2ea;color:var(--green)}
.wx .tag.hi{background:#f6e6e4;color:var(--red)}
/* 四元素逐项 */
.el{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:9px;margin-top:4px}
.el .it{background:#fff;border:1px solid var(--line);border-radius:10px;padding:10px 13px;
 line-height:1.7;font-size:13px}
.el .hd{display:flex;align-items:baseline;gap:8px;margin-bottom:3px}
.el .en{font-size:18px;font-weight:700}
.el .pc{margin-left:auto;color:var(--sub);font-variant-numeric:tabular-nums}
/* 紫微：十二宫 / 大限 / 四化 */
.pl,.dx,.sh{display:grid;grid-template-columns:repeat(auto-fill,minmax(272px,1fr));gap:9px;margin-top:4px}
.pl .it,.dx .it,.sh .it{background:#fff;border:1px solid var(--line);border-radius:10px;
 padding:10px 13px;line-height:1.7}
.pl .it.ming{border-color:var(--red)}
.pl .it.shen{border-style:dashed}
.dx .it.now,.sh .it.ji{border-color:var(--gold)}
.pl .hd,.dx .hd,.sh .hd{display:flex;align-items:baseline;gap:7px;margin-bottom:4px;flex-wrap:wrap}
.pl .pn,.dx .pn,.sh .pn{font-size:15px;font-weight:700;color:var(--red)}
.pl .gz2,.dx .gz2,.sh .gz2{font-size:15px;font-weight:700;letter-spacing:1px}
.pl .pc,.dx .pc,.sh .pc{margin-left:auto;font-size:12px;color:var(--sub)}
.pl .tag,.dx .tag,.sh .tag{font-size:11px;background:#f0e9db;color:var(--sub);
 border-radius:8px;padding:0 7px}
.pl .tag.hi,.dx .tag.hi{background:var(--red);color:#fff}
.sh .it.ji .pn{color:#8a6a1f}
/* 1.5.0：神煞 / 十神 / 轴点 / 性质 / 相位 的卡片容器
   布局沿用 .pl/.dx/.sh，只是条目长短差得多，用 flex 竖排更好读 */
.ssx{display:flex;flex-direction:column;gap:8px;margin-top:10px}
.ssx .it{background:#fff;border:1px solid var(--line);border-radius:10px;
 padding:10px 13px;line-height:1.7}
.ssx .hd{display:flex;align-items:baseline;gap:7px;margin-bottom:4px;flex-wrap:wrap}
.ssx .pn{font-size:15px;font-weight:700;color:var(--red)}
.ssx .pc{margin-left:auto;font-size:12px;color:var(--sub);text-align:right}
.ssx .li{font-size:13px;margin:4px 0 0;color:var(--ink)}
.ssx .li .h{color:var(--sub);margin-right:5px}
.ssx .sub2{color:var(--sub);font-size:12px;margin:3px 0 0}
.ssx .gz2{font-size:15px;font-weight:700;letter-spacing:1px}
/* 类别色只加在神煞名这个标签上。整张卡染色会变成
   「吉=绿卡、凶=红卡」的吉凶断语观感，而这里只想区分标签。 */
.ssx .pn.ji{color:var(--green)}
.ssx .pn.xiong{color:#8a4a20}
/* 两套体系并置的说明条 */
.note-sys{background:#f3f6f8;border-left:4px solid var(--blue);border-radius:0 8px 8px 0;
 padding:9px 14px;font-size:13px;color:#3c5566;line-height:1.75;margin:9px 0}
.gloss{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:8px;font-size:13px}
.gloss div{background:#fbf8f1;border-radius:8px;padding:8px 11px;line-height:1.65}
.gloss b{color:var(--red)}
/* 开运对应表 */
.luckgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:8px;margin:9px 0 2px}
.luckgrid>div{background:#fff;border:1px solid var(--line);border-radius:9px;
padding:8px 11px;font-size:13px;line-height:1.65}
.luckgrid b{display:block;color:var(--red);font-size:12px;margin-bottom:3px;font-weight:600}
.luckgrid .em{color:var(--ink);font-weight:600}
@media(max-width:480px){.luckgrid{grid-template-columns:1fr 1fr;gap:6px}
.luckgrid>div{padding:7px 9px;font-size:12px}}
[title]{cursor:help;border-bottom:1px dotted #cbbfa8}
.secnote{font-size:12px;color:var(--sub);margin:-8px 0 14px}
"""

WX_COLOR = {"木": "#5b8c5a", "火": "#c0504d", "土": "#b08d4a", "金": "#8a8f98", "水": "#4a6fa5"}

# 占星四元素的颜色，与五行区分开
EL_COLOR = {"火": "#c0504d", "土": "#b08d4a", "风": "#4a6fa5", "水": "#3f7a52"}


def _h(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _yr(v):
    """虚岁 -> 整数显示。

    起运岁数带小数（7.26 岁起运 -> 第一步从 7.3 虚岁开始），
    但给人看的大运区间写「7.3–17.3 岁」既啰嗦又没信息量 ——
    虚岁本来就是整数计的。取整与 JS 侧保持一致（都用 Math.floor），
    否则两边 HTML 会差一位小数，对拍会逐字报出来。
    """
    import math
    try:
        return int(math.floor(float(v)))
    except (TypeError, ValueError):
        return "?"


def render_bazi(r):
    i = r["输入"]
    p = []
    p.append('<section><h2>四柱八字</h2>')
    p.append('<div class="info"><span>公历 <b>%s</b></span><span>农历 <b>%s</b></span>'
             '<span>时辰 <b>%s</b></span><span>性别 <b>%s</b></span><span>出生地 <b>%s</b></span></div>'
             % (_h(i["公历"]), _h(i["农历"]), _h(i["时辰"]), _h(i["性别"]), _h(i["出生地"])))
    if i.get("真太阳时"):
        t = i["真太阳时"]
        p.append('<div class="info"><span>真太阳时 <b>%s</b>（钟表 %s，校正 %s 分，均时差 %s 分）</span></div>'
                 % (_h(t["真太阳时"]), _h(t["钟表时"]), t["校正分钟"], t["均时差分钟"]))
    # 四柱表
    p.append('<table><tr><th></th>'
             '<th title="出生年份的干支，以「立春」为分界，不是元旦也不是春节">年柱</th>'
             '<th title="出生月份的干支，以节气为分界（立春起寅月）">月柱</th>'
             '<th title="出生日子的干支。这一柱上面的字（日干）就是「你自己」">日柱</th>'
             '<th title="出生时辰的干支，两小时为一个时辰">时柱</th></tr>')
    rows = {"干支": [], "十神": [], "藏干": [], "纳音": []}
    for pos in ("年", "月", "日", "时"):
        gz = r["四柱"][pos]
        if gz == "未知":
            for k in rows:
                rows[k].append("—")
            continue
        d = next(x for x in r["柱详解"] if x["柱"] == pos)
        rows["干支"].append('<span class="gz"><span class="gan">%s</span><span class="zhi">%s</span></span>' % (gz[0], gz[1]))
        rows["十神"].append(d["干十神"])
        rows["藏干"].append('<div class="cang">%s</div>' % "<br>".join("%s <span class='ss'>%s</span>" % (c["干"], c["十神"]) for c in d["支藏干"]))
        rows["纳音"].append(d["纳音"])
    ROW_TIP = {"干支": "八个字本身，上为天干、下为地支",
               "十神": "其他七个字跟「你」的关系，分十种，代表不同的人事",
               "藏干": "地支里藏着的天干，代表表面之下暗藏的力量",
               "纳音": "干支组合对应的五行意象，用于辅助参考"}
    for k, label in (("干支", ""), ("十神", "十神"), ("藏干", "藏干"), ("纳音", "纳音")):
        tip = ' title="%s"' % ROW_TIP[k] if k in ROW_TIP else ""
        p.append("<tr><th%s>%s</th>" % (tip, label) + "".join("<td>%s</td>" % v for v in rows[k]) + "</tr>")
    p.append("</table>")
    # 日主 / 强弱 / 格局
    s = r["日主强弱"]
    p.append('<div class="info" style="margin-top:14px">'
             '<span>日主 <b>%s（%s·%s）</b></span>'
             '<span>强弱 <b>%s</b>（同党 %.1f%%）</span>'
             '<span>格局 <b>%s</b></span><span>旬空 <b>%s</b></span>'
             '<span>喜用 <b>%s</b></span></div>'
             % (r["日主"]["干"], r["日主"]["五行"], r["日主"]["阴阳"], s["判定"], s["同党占比"],
                r["格局"]["名"], r["旬空"], "、".join(s["喜用神"])))
    # 五行
    p.append("<h2 style='margin-top:20px'>五行力量</h2>")
    for w, v in r["五行统计"].items():
        p.append('<div class="bar"><div class="lb">%s</div><div class="tr">'
                 '<div class="fl" style="width:%.1f%%;background:%s"></div></div>'
                 '<div class="vl">%.1f%%</div></div>' % (w, max(v, 0), WX_COLOR[w], v))
    # 神煞
    if r["神煞"]:
        p.append("<h2 style='margin-top:20px'>神煞</h2><div>")
        for x in r["神煞"]:
            cls = "xiong" if any(k in x["神煞"] for k in ("煞", "刃", "孤", "寡")) else "ji"
            p.append('<span class="pill %s" title="%s">%s·%s</span>' % (cls, _h(x["说明"]), _h(x["神煞"]), _h(x["位置"])))
        p.append("</div>")
    # 大运
    d = r["大运"]
    p.append("<h2 style='margin-top:20px'>大运</h2><div class='info'><span>%s，起运 <b>%s</b></span></div>"
             % (_h(d["顺逆"]), _h(d["起运"])))
    p.append('<div class="liu">')
    for x in d["列表"]:
        p.append("<span>%s<br><b>%s</b> %s<br>%d-%d岁</span>"
                 % (_h(x["十神"]), _h(x["干支"]), "", x["起始虚岁"], x["结束虚岁"]))
    p.append("</div>")
    # 流年
    p.append("<h2 style='margin-top:20px'>流年</h2><div class='liu'>")
    for x in r["流年"]:
        p.append("<span>%d <b>%s</b> %s · %d岁</span>" % (x["年"], _h(x["干支"]), _h(x["十神"]), x["虚岁"]))
    p.append("</div>")
    if r["警告"]:
        p.append('<div class="warn">' + "<br>".join("⚠ " + _h(w) for w in r["警告"]) + "</div>")
    p.append("</section>")
    return "".join(p)


def render_ziwei(r):
    i = r["输入"]
    by_zhi = {p["地支"]: p for p in r["十二宫"]}
    p = ['<section><h2>紫微斗数</h2>']
    p.append('<div class="info"><span>农历 <b>%s</b></span><span>时辰 <b>%s</b></span>'
             '<span>年干支 <b>%s</b></span><span>五行局 <b>%s</b></span>'
             '<span>命宫 <b>%s%s</b></span><span>身宫 <b>%s%s</b></span></div>'
             % (_h(i["农历"]), _h(i["时辰"]), _h(i["年干支"]), _h(r["五行局"]),
                r["命宫"]["天干"], r["命宫"]["地支"], r["身宫"]["天干"], r["身宫"]["地支"]))
    h = r["四化"]
    p.append('<div class="info"><span>四化（%s干）：禄 <b>%s</b> · 权 <b>%s</b> · 科 <b>%s</b> · 忌 <b>%s</b></span></div>'
             % (_h(h["年干"]), _h(h["化禄"]), _h(h["化权"]), _h(h["化科"]), _h(h["化忌"])))
    # 4x4 盘
    p.append('<div class="pan">')
    for row in range(4):
        for col in range(4):
            if row in (1, 2) and col in (1, 2):
                continue
            z = PAN_LAYOUT[(row, col)]
            pal = by_zhi.get(z)
            if not pal:
                p.append("<div></div>")
                continue
            cls = "cell"
            if pal["是否命宫"]:
                cls += " ming"
            if pal["是否身宫"]:
                cls += " shen"
            stars = []
            for s in pal["星曜"]:
                base = s.split("·")[0]
                k = "star main" if base in M_ziwei.STAR_BRIEF else ("star hua" if "化" in s else "star aux")
                stars.append('<span class="%s">%s</span>' % (k, _h(s)))
            tag = []
            if pal["是否命宫"]:
                tag.append("命")
            if pal["是否身宫"]:
                tag.append("身")
            p.append('<div class="%s"><div class="pos"><span>%s</span><span>%s</span></div>'
                     '<div class="gz2"><span class="gan">%s</span><span class="zhi">%s</span></div>'
                     '<div class="stars">%s</div></div>'
                     % (cls, _h(pal["宫名"]), "".join(tag), pal["天干"], pal["地支"],
                        " ".join(stars) if stars else '<span class="ss">空宫</span>'))
    p.append('<div class="center"><div class="t">命盘</div>'
             '<div>紫微 %s</div><div>天府 %s</div><div>%s</div>'
             '<div class="ss">大限%s · 起运%d岁</div></div>'
             % (_h(r["紫微星"]), _h(r["天府星"]), _h(r["五行局"]),
                _h(r["大限"]["顺逆"]), r["大限"]["起运虚岁"]))
    p.append("</div>")
    # 大限
    p.append("<h2 style='margin-top:20px'>大限</h2><div class='liu'>")
    for x in r["大限"]["列表"]:
        p.append("<span>%d-%d岁<br><b>%s%s</b><br>%s</span>"
                 % (x["虚岁起"], x["虚岁止"], x["天干"], x["地支"], _h(x["宫位"])))
    p.append("</div>")
    ln = r["流年"]
    p.append('<div class="info" style="margin-top:14px"><span>流年 <b>%d %s</b> 虚岁%d · 流年命宫 <b>%s</b> · 当前大限 <b>%s</b></span></div>'
             % (ln["年"], _h(ln["干支"]), ln["虚岁"], _h(ln["流年命宫"]), _h(ln["当前大限"])))
    if r["警告"]:
        p.append('<div class="warn">' + "<br>".join("⚠ " + _h(w) for w in r["警告"]) + "</div>")
    p.append("</section>")
    return "".join(p)


def render_astro(r):
    p = ['<section><h2>西洋占星本命盘</h2>']
    p.append('<div class="info"><span>太阳 <b>%s</b></span><span>月亮 <b>%s</b></span>'
             '<span>上升 <b>%s</b></span><span>经纬度 <b>%s</b></span></div>'
             % (_h(r["太阳星座"]), _h(r["月亮星座"]), _h(r["上升星座"]), _h(r["输入"]["经纬度"])))
    p.append("<table><tr><th>天体</th><th>星座</th><th>度数</th><th>元素</th></tr>")
    for x in r["天体"]:
        p.append("<tr><td>%s %s</td><td>%s</td><td>%s</td><td>%s·%s</td></tr>"
                 % (_h(x["符号"]), _h(x["天体"]), _h(x["星座"]), _h(x["星座内度"]), _h(x["元素"]), _h(x["性质"])))
    p.append("</table>")
    if r["轴点"]:
        p.append('<div class="info" style="margin-top:12px">')
        for nm, v in r["轴点"].items():
            p.append("<span>%s <b>%s %s</b></span>" % (_h(nm), _h(v["星座"]), _h(v["星座内度"])))
        p.append("</div>")
    p.append("<h2 style='margin-top:20px'>主要相位</h2><div>")
    for a in sorted(r["相位"], key=lambda x: -x["强度"])[:14]:
        cls = "ji" if a["相位"] in ("三分相", "六分相") else "xiong"
        p.append('<span class="pill %s">%s–%s %s</span>' % (cls, _h(a["天体1"]), _h(a["天体2"]), _h(a["相位"])))
    p.append("</div>")
    p.append('<div class="info" style="margin-top:12px"><span>元素：%s</span><span>性质：%s</span></div>'
             % (" ".join("%s%d" % (k, v) for k, v in r["元素分布"].items()),
                " ".join("%s%d" % (k, v) for k, v in r["性质分布"].items())))
    p.append("</section>")
    return "".join(p)


def render_plain(data):
    """白话解读区：先给结论，再给依据，全部用日常语言。"""
    P = ['<section><h2>先说人话</h2>',
         '<div class="secnote">这一段不用懂任何术语，看完就知道自己大概是什么样的人。'
         '想研究细节，往下翻「专业排盘数据」。</div>']

    if "八字" in data:
        b = M_plain.bazi_plain(data["八字"])
        P.append('<h2 style="font-size:15px;border-left-color:var(--gold)">八字 · 看你的性格和天赋</h2>')
        P.append('<div class="plain"><h3>%s</h3><p>%s</p><p class="sub2">%s</p></div>'
                 % (_h(b["性格底色"]["标题"]), _h(b["性格底色"]["要点"]), _h(b["性格底色"]["补充"])))
        P.append('<div class="plain"><h3>%s</h3><p>%s</p><p class="sub2">%s</p></div>'
                 % (_h(b["做事方式"]["标题"]), _h(b["做事方式"]["要点"]), _h(b["做事方式"]["补充"])))
        if b["天生擅长"]["标签"]:
            P.append('<div class="plain"><h3>%s</h3><div class="tagline">' % _h(b["天生擅长"]["标题"]))
            for t in b["天生擅长"]["标签"]:
                P.append('<div class="tag"><b>%s</b>%s</div>' % (_h(t["名"]), _h(t["说明"])))
            P.append("</div></div>")
        P.append('<div class="plain"><h3>%s</h3><p>%s</p>'
                 '<p class="sub2">对你有利的五行是「%s」，可以在颜色、方位、行业上多往这边靠。</p></div>'
                 % (_h(b["能量分布"]["标题"]), _h(b["能量分布"]["要点"]),
                    "、".join(b["能量分布"]["喜用"])))
        if b["运气加成"]["标签"]:
            P.append('<div class="plain"><h3>%s</h3><div class="tagline">' % _h(b["运气加成"]["标题"]))
            for t in b["运气加成"]["标签"]:
                P.append('<div class="tag"><b>%s</b>%s</div>' % (_h(t["名"]), _h(t["说明"])))
            P.append("</div></div>")
        if b.get("生肖"):
            sx = b["生肖"]
            P.append('<div class="plain"><h3>你的生肖</h3>'
                     '<p>你属<span class="k">%s</span>——%s。</p>'
                     '<p class="sub2">幸运色：%s ｜ 幸运数字：%s</p></div>'
                     % (_h(sx["生肖"]), _h(sx["特质"]), _h(sx["幸运色"]), _h(sx["幸运数字"])))
        if b.get("开运指南"):
            lk = b["开运指南"]
            P.append('<div class="plain"><h3>你的开运指南</h3>'
                     '<p>你的喜用五行是<span class="k">%s</span>。日常多往这些方向靠，会顺一些：</p>'
                     '<div class="luckgrid">'
                     '<div><b>幸运色</b>%s</div>'
                     '<div><b>有利方位</b>%s</div>'
                     '<div><b>幸运数字</b>%s</div>'
                     '<div><b>适合行业</b>%s</div>'
                     '<div><b>开运饰品</b>%s</div>'
                     '<div><b>日常做法</b>%s</div>'
                     '</div></div>'
                     % (_h(lk["五行"]), _h(lk["颜色"]), _h(lk["方位"]), _h(lk["数字"]),
                        _h(lk["行业"]), _h(lk["饰品"]), _h(lk["日常"])))
        if b["当前阶段"]:
            P.append('<div class="plain"><h3>你现在这段时期</h3>'
                     '<p>当前走在「<span class="k">%s</span>」大运（%s），主题是<span class="k">%s</span>。</p></div>'
                     % (_h(b["当前阶段"]["干支"]), _h(b["当前阶段"]["十神"]), _h(b["当前阶段"]["主题"])))

        # ---- 1.3.1 新增：大运逐段（折叠）----
        if b.get("大运详批") and b["大运详批"]["列表"]:
            dl = b["大运详批"]["列表"]
            cur_i = next((i for i, x in enumerate(dl) if x["是当前"]), None)
            P.append('<details class="fold"><summary>你一生十步大运'
                     '<span class="cnt">共 %d 步%s</span></summary><div class="fbody">'
                     '<p class="sub2">每十年换一段，是运势的主基调。'
                     '折叠起来是因为十段一起铺开太长，实际用到的是当前那一步——'
                     '所以当前那步放在最前面标出来。</p><div class="dy">'
                     % (len(dl), ("，当前在第 %d 步" % dl[cur_i]["序"]) if cur_i is not None else ""))
            for i, x in enumerate(dl):
                now = x["是当前"]
                P.append('<div class="it%s"%s>'
                         % (" now" if now else "", " open" if False else ""))
                P.append('<div class="hd"><span class="no">第%d步</span>'
                         '<span class="gz"><span class="gan">%s</span>'
                         '<span class="zhi">%s</span></span>'
                         '<span class="ss">%s</span>'
                         % (x["序"], _h(x["干支"][0] if x["干支"] != "未知" else "—"),
                            _h(x["干支"][1] if len(x["干支"]) > 1 and x["干支"] != "未知" else ""),
                            _h(x["十神"])))
                if now:
                    P.append('<span class="now-tag">当前</span>')
                P.append('<span class="age">%s–%s 岁</span></div>'
                         % (_yr(x["起始虚岁"]), _yr(x["结束虚岁"])))
                P.append('<div class="th">%s</div>' % _h(x["主题"]))
                if x["正面"]:
                    P.append('<p class="li"><span class="h">好的一面</span>%s</p>' % _h(x["正面"]))
                if x["提醒"]:
                    P.append('<p class="li warn"><span class="h">要注意</span>%s</p>' % _h(x["提醒"]))
                if x["长生"]:
                    P.append('<span class="stg">十二长生 · %s —— %s</span>'
                             % (_h(x["长生"]), _h(x["长生含义"])))
                P.append("</div>")
            P.append("</div></div></details>")

        # ---- 1.3.1 新增：流年逐年（折叠）----
        if b.get("流年详批") and b["流年详批"]["列表"]:
            ll = b["流年详批"]["列表"]
            P.append('<details class="fold"><summary>未来七年的年度节奏'
                     '<span class="cnt">%d–%d</span></summary><div class="fbody">'
                     '<p class="sub2">大运是十年的大背景，流年是这一年的具体调子。'
                     '大运管方向，流年管「今年什么事儿容易发生」。</p><div class="ly">'
                     % (ll[0]["年"], ll[-1]["年"]))
            for x in ll:
                gz = x["干支"]
                gan = gz[0] if gz != "未知" else "—"
                zhi = gz[1] if len(gz) > 1 and gz != "未知" else ""
                cls = " now" if x["是今年"] else ""
                head = ('<div class="it%s"><span class="yr">%d</span>'
                        '<span class="tx"><b>%s</b> %s · 虚岁 %d'
                        % (cls, x["年"], _h(gan), _h(zhi), x["虚岁"]))
                if x["是今年"]:
                    head += '<span class="yn">（今年）</span>'
                P.append(head + "<br>" + _h(x["解读"]) + "</span></div>")
            P.append("</div></div></details>")

        # ---- 1.3.1 新增：五行意象（折叠）----
        if b.get("五行意象") and b["五行意象"].get("明细"):
            w = b["五行意象"]
            P.append('<details class="fold"><summary>你身上五股的劲儿'
                     '<span class="cnt">八字五行</span></summary><div class="fbody">')
            P.append('<p class="sub2">「多」不等于「好」，「少」也不等于「坏」——'
                     '命理里五行强弱本身没有优劣，只有适不适配你。'
                     '这里讲的是描述，不是评判。</p><div class="wx">')
            for x in w["明细"]:
                cls = " top" if (w.get("最强") and x["五行"] == w["最强"]["五行"]) else (
                      " lo" if (w.get("最弱") and x["五行"] == w["最弱"]["五行"]) else "")
                P.append('<div class="it%s"><div class="hd"><span class="wxn" style="color:%s">%s</span>'
                         % (cls, WX_COLOR.get(x["五行"], "#666"), _h(x["五行"])))
                P.append('<span class="xiang">%s</span>' % _h(x["象"]))
                if x["是喜用"]:
                    P.append('<span class="tag ji">喜用</span>')
                P.append('<span class="pc">%.1f%%</span></div>' % x["占比"])
                P.append('<p class="li">%s</p>' % _h(x["描述"]))
                if x["偏多时"]:
                    P.append('<p class="li"><span class="h">偏多时</span>%s</p>' % _h(x["偏多时"]))
                if x["偏少时"]:
                    P.append('<p class="li"><span class="h">偏少时</span>%s</p>' % _h(x["偏少时"]))
                P.append("</div>")
            P.append("</div></div></details>")


        # ---- 1.5.0：神煞逐条（修掉按名字猜吉凶的错判）----
        if b.get("神煞详批") and b["神煞详批"]["列表"]:
            ssd = b["神煞详批"]
            cnt = ssd["计数"]
            P.append('<details class="fold"><summary>你命里的神煞'
                     '<span class="cnt">助你 %d · 中性 %d · 留意 %d</span>'
                     '</summary><div class="fbody">' % (cnt["助你"], cnt["中性"], cnt["留意"]))
            if ssd["未归类"]:
                # 未归类要显式说出来。默认当成吉的话，
                # 等于「没查过就说好」—— 方向是错的，而且看不见。
                P.append('<p class="warn">以下神煞还没归类，不计入吉凶统计：%s</p>'
                         % _h("、".join(ssd["未归类"])))
            P.append('<div class="ssx">')
            for x in ssd["列表"]:
                cls = {"ji": "ji", "xiong": "xiong"}.get(x["类别"], "")
                P.append('<div class="it"><div class="hd">'
                         '<span class="pn%s">%s</span>' % (
                             " " + cls if cls else "", _h(x["神煞"])))
                P.append('<span class="pc">%s</span></div>'
                         % _h(x["类别说明"]))
                P.append('<p class="li">%s</p>' % _h(x["说明"]))
                P.append('<p class="sub2">查%s，落%s（%s）</p>'
                         % (_h(x["查法"]), _h(x["落支"]), _h(x["位置"])))
                P.append("</div>")
            P.append("</div></div></details>")

        # ---- 1.5.0：十神分布 ----
        if b.get("十神详批") and b["十神详批"]["明细"]:
            shd = b["十神详批"]
            P.append('<details class="fold"><summary>你的十神分布'
                     '<span class="cnt">哪个最重</span></summary><div class="fbody">')
            P.append('<p class="li"><span class="h">最重的是</span>%s</p>'
                     % _h(shd["最多"]))
            P.append('<p class="sub2">%s</p>' % _h(shd["最多说明"]))
            P.append('<div class="ssx">')
            for x in shd["明细"]:
                P.append('<div class="it"><div class="hd">'
                         '<span class="pn">%s</span>'
                         '<span class="pc">%d 个 · %.1f%%</span></div>'
                         '<p class="li">干上 %d · 藏干 %d</p>'
                         '<p class="sub2">%s</p></div>'
                         % (_h(x["十神"]), x["合计"], x["占比"],
                            x["干上"], x["藏干"], _h(x["说明"])))
            P.append("</div>")
            if shd["组合"]:
                P.append("<h3 style='font-size:14px;margin:14px 0 6px'>组合看</h3><div class='ssx'>")
                for x in shd["组合"]:
                    P.append('<div class="it"><div class="hd"><span class="pn">%s</span></div>'
                             '<p class="li">%s</p></div>' % (_h(x["组合"]), _h(x["说明"])))
                P.append("</div>")
            P.append("</div></details>")

        # ---- 1.6.0：六亲 ----
        if b.get("六亲详批") and b["六亲详批"]["列表"]:
            kd = b["六亲详批"]
            P.append('<details class="fold"><summary>六亲怎么看'
                     '<span class="cnt">%s</span></summary><div class="fbody">'
                     % _h(kd["性别"]))
            P.append('<p class="sub2">%s</p>' % _h(kd["口径"]))
            P.append('<div class="ssx">')
            for it in kd["列表"]:
                if not it["位置"]:
                    # 一颗都没出现 —— 要说出来，不能留个空卡片让人以为漏了
                    P.append('<div class="it"><div class="hd">'
                             '<span class="pn">%s</span>'
                             '<span class="pc">这一块没出现</span></div>'
                             '<p class="li">你这张盘里%s都没有显出来，'
                             '不代表没这部分关系，只说明它不靠星象主导。</p></div>'
                             % (_h(it["角色"]), _h("、".join(it["星"]))))
                    continue
                P.append('<div class="it"><div class="hd">'
                         '<span class="pn">%s</span>'
                         '<span class="pc">%s · %d 个%s</span></div>'
                         % (_h(it["角色"]), _h("、".join(it["星"])), it["个数"],
                            "，有透干" if it["有透"] else "，都藏在支里"))
                P.append('<p class="li">%s</p>' % _h(it["说明"]))
                for x in it["位置"]:
                    P.append('<p class="sub2">%s%s %s（%s）</p>'
                             % (_h(x["柱"]), _h(x["干支"]), _h(x["十神"]),
                                "透干，明面上的分量重"
                                if x["透"] else "藏%s，存在感弱一些"
                                % _h(x.get("藏") or "")))
                P.append("</div>")
            P.append("</div>")
            P.append("<h3 style='font-size:14px;margin:14px 0 6px'>四柱各代表谁</h3>")
            P.append('<div class="ssx">')
            for x in kd["柱位"]:
                P.append('<div class="it"><div class="hd">'
                         '<span class="pn">%s%s</span></div>'
                         '<p class="li">%s</p></div>'
                         % (_h(x["柱"]), _h(x["干支"]), _h(x["代表"])))
            P.append("</div></div></details>")
    if "紫微" in data:
        z = M_plain.ziwei_plain(data["紫微"])
        P.append('<h2 style="font-size:15px;border-left-color:var(--gold);margin-top:22px">紫微斗数 · 看事业、财运、感情</h2>')
        P.append('<div class="plain"><h3>命宫主星</h3><p>%s</p></div>' % _h(z["一句话"]))
        for k in ("事业方向", "财运模式", "感情模式", "四化提醒"):
            blk = z.get(k)
            if blk:
                P.append('<div class="plain"><h3>%s</h3><p>%s</p></div>' % (_h(blk["标题"]), _h(blk["要点"])))
        if z.get("开运指南"):
            lk = z["开运指南"]
            P.append('<div class="plain"><h3>开运指南 · %s</h3>'
                     '<p>你的五行局属<span class="k">%s</span>，日常可以这样用：</p>'
                     '<div class="luckgrid">'
                     '<div><b>幸运色</b>%s</div>'
                     '<div><b>有利方位</b>%s</div>'
                     '<div><b>幸运数字</b>%s</div>'
                     '<div><b>适合行业</b>%s</div>'
                     '<div><b>开运饰品</b>%s</div>'
                     '<div><b>日常做法</b>%s</div>'
                     '</div></div>'
                     % (_h(lk["局"]), _h(lk["五行"]), _h(lk["颜色"]), _h(lk["方位"]),
                        _h(lk["数字"]), _h(lk["行业"]), _h(lk["饰品"]), _h(lk["日常"])))

        # ---- 1.5.0 新增：紫微四块（十二宫 / 大限 / 流年 / 四化）----
        # 之前紫微这边只有「命宫主星 + 事业/财运/感情」三段，
        # 十二宫、大限 12 步、流年命宫、四化落宫全都没展开 ——
        # 而同一张盘里八字那边已经逐项展开了，两边详略不该差这么多。
        if z.get("十二宫详批") and z["十二宫详批"]["列表"]:
            pl = z["十二宫详批"]["列表"]
            P.append('<details class="fold"><summary>你的十二宫'
                     '<span class="cnt">逐宫看</span></summary><div class="fbody">'
                     '<p class="sub2">十二宫代表人生十二个领域。'
                     '「主星」决定这个领域的底色；宫里没有主星很常见，'
                     '要借对宫的星来看，那不是缺陷。</p><div class="pl">')
            for p2 in pl:
                cls = ""
                marks = []
                if p2["是命宫"]:
                    cls += " ming"
                    marks.append("命宫")
                if p2["是身宫"]:
                    cls += " shen"
                    marks.append("身宫")
                P.append('<div class="it%s"><div class="hd">'
                         '<span class="pn">%s</span><span class="gz2">%s</span>'
                         % (cls, _h(p2["宫名"]), _h(p2["干支"])))
                if marks:
                    P.append('<span class="tag hi">%s</span>' % _h("、".join(marks)))
                P.append('<span class="pc">主星 %s</span></div>'
                         % _h("、".join(p2["主星"]) if p2["主星"] else "（空宫）"))
                P.append('<p class="li">%s</p>' % _h(p2["含义"]))
                if p2["借宫"]:
                    P.append('<p class="li"><span class="h">借对宫</span>'
                             '本宫无主星，借「%s」的 %s 来论。</p>'
                             % (_h(p2["借宫"]),
                                _h("、".join(p2["借宫主星"]) if p2["借宫主星"] else "（对宫也空宫）")))
                if p2["标签"]:
                    P.append('<p class="li"><span class="h">星曜</span>%s</p>'
                             % _h("；".join("%s=%s" % (t["星"], t["说明"]) for t in p2["标签"])))
                if p2["留意"]:
                    P.append('<p class="li warn"><span class="h">要留意</span>%s</p>'
                             % _h("；".join("%s=%s" % (c["星"], c["说明"]) for c in p2["留意"])))
                P.append("</div>")
            P.append("</div></div></details>")

        if z.get("大限详批") and z["大限详批"]["列表"]:
            dl = z["大限详批"]["列表"]
            cur = z.get("流年详情") or {}
            cur_dx = cur.get("当前大限宫", "")
            P.append('<details class="fold"><summary>你一生十二步大限'
                     '<span class="cnt">紫微的十年分段</span></summary><div class="fbody">'
                     '<p class="sub2">大限走的是<b>宫位</b>而不是十神 —— '
                     '每十年重心落在哪个宫，那十年的主语就是那个宫代表的事。'
                     '和大运是两套不同的分段方式，别混着看。</p><div class="dx">')
            for x in dl:
                now = bool(cur_dx) and x["宫位"] == cur_dx
                P.append('<div class="it%s"><div class="hd">'
                         '<span class="age">%d–%d 岁</span>'
                         '<span class="pn">%s</span><span class="gz2">%s</span>'
                         % (" now" if now else "", x["虚岁起"], x["虚岁止"],
                            _h(x["宫位"]), _h(x["干支"])))
                if now:
                    P.append('<span class="tag hi">当前大限</span>')
                P.append('<span class="pc">%s</span></div>'
                         % _h("、".join(x["主星"]) if x["主星"] else "空宫"))
                P.append('<p class="li">%s</p>' % _h(x["主题"]))
                P.append('<p class="sub2">%s</p>' % _h(x["宫位含义"]))
                P.append("</div>")
            P.append("</div></div></details>")

        if z.get("流年详情"):
            ln = z["流年详情"]
            P.append('<details class="fold"><summary>今年的落点'
                     '<span class="cnt">%s年 %s</span></summary><div class="fbody">'
                     % (_h(str(ln.get("年", ""))), _h(str(ln.get("干支", "")))))
            P.append('<div class="info" style="margin:0 0 10px">'
                     '<span>虚岁 <b>%s</b></span>'
                     '<span>流年命宫 <b>%s%s</b></span>'
                     '<span>当前大限 <b>%s</b></span></div>'
                     % (ln.get("虚岁", "—"), _h(ln.get("流年命宫名", "")),
                        _h(ln.get("流年命宫", "")), _h(ln.get("当前大限", ""))))
            if ln.get("命宫含义"):
                P.append('<p class="li"><span class="h">今年重心</span>%s —— %s</p>'
                         % (_h(ln.get("流年命宫名", "")), _h(ln["命宫含义"])))
            if ln.get("大限主题"):
                P.append('<p class="li"><span class="h">大限主线</span>%s</p>'
                         % _h(ln["大限主题"]))
            P.append('<p class="sub2">%s</p>' % _h(ln.get("说明", "")))
            P.append("</div></details>")

        if z.get("四化详批"):
            P.append('<details class="fold"><summary>四化落在哪'
                     '<span class="cnt">禄权科忌</span></summary><div class="fbody">'
                     '<p class="sub2">生年四化是「哪颗星被强化」，'
                     '它落在哪个宫，那一块就跟着强化。化忌不是坏事，'
                     '是这辈子要学的课题。</p><div class="sh">')
            for h2 in z["四化详批"]:
                cls = " ji" if h2["化"] == "化忌" else ""
                P.append('<div class="it%s"><div class="hd">'
                         '<span class="pn">%s</span><span class="gz2">%s</span>'
                         % (cls, _h(h2["化"]), _h(h2["星"])))
                if h2["宫位"]:
                    P.append('<span class="tag">落%s宫</span>' % _h(h2["宫位"]))
                P.append('<span class="pc">%s</span></div>' % _h(h2["角色"]))
                P.append('<p class="li">%s</p>' % _h(h2["要点"]))
                if h2["宫位含义"]:
                    P.append('<p class="sub2">该宫管的是：%s</p>' % _h(h2["宫位含义"]))
                P.append("</div>")
            P.append("</div></div></details>")

        # ---- 1.6.0：夫妻宫 ----
        # 措辞纪律：这里最容易顺嘴写成断语（「婚姻不顺」）。
        # 一律走「需要磨合的地方 / 怎么相处」，不走「好 / 坏」。
        sp = z.get("夫妻详批") or {}
        if sp.get("主星") or sp.get("煞星"):
            P.append('<details class="fold"><summary>夫妻宫'
                     '<span class="cnt">%s%s</span></summary><div class="fbody">'
                     % (_h(("宫干 " + sp["宫干"]) if sp.get("宫干") else ""),
                        _h(("大限 " + sp["大限年龄"]) if sp.get("大限年龄") else "")))
            if sp.get("组合"):
                P.append('<p class="li"><span class="h">%s</span>%s</p>'
                         % (_h(sp["组合"]["型"]), _h(sp["组合"]["说明"])))
            elif sp.get("主星"):
                P.append('<p class="li">主星：%s</p>'
                         % _h("、".join(sp["主星"])))
            if sp.get("四化"):
                # 主星上的四化是「这块星曜的当前状态」，要单独讲 ——
                # 混进煞星或「未解读」里都是错的
                P.append("<h3 style='font-size:14px;margin:14px 0 6px'>"
                         "主星带四化</h3><div class='ssx'>")
                for x in sp["四化"]:
                    P.append('<div class="it"><div class="hd">'
                             '<span class="pn">%s</span>'
                             '<span class="pc">%s</span></div>'
                             '<p class="li">%s</p></div>'
                             % (_h(x["星"]), _h(x["化"]), _h(x["说明"])))
                P.append("</div>")
            if sp.get("对宫"):
                P.append('<p class="sub2">对宫是%s宫 —— 夫妻和事业这一头'
                         '互相牵动，不只是感情的事。</p>' % _h(sp["对宫"]))
            if sp.get("煞星"):
                P.append("<h3 style='font-size:14px;margin:14px 0 6px'>"
                         "要磨合的地方</h3><div class=\'ssx\'>")
                for x in sp["煞星"]:
                    P.append('<div class="it"><div class="hd">'
                             '<span class="pn xiong">%s</span>'
                             '<span class="pc">%s</span></div>'
                             '<p class="li">%s</p></div>'
                             % (_h(x["星"]), _h(x["型"]), _h(x["说明"])))
                P.append("</div>")
            if sp.get("未解读"):
                # 查不到解读的星要显式报出来，不能静默跳过 ——
                # 静默跳过的话页面看着完整，其实少讲了东西
                P.append('<p class="warn">这些星还没写解读：%s</p>'
                         % _h("、".join(sp["未解读"])))
            if sp.get("大限说明"):
                P.append("<h3 style='font-size:14px;margin:14px 0 6px'>"
                         "什么时候走到这块</h3>")
                P.append('<p class="li">大限虚岁 %s</p>' % _h(sp["大限年龄"]))
                P.append('<p class="sub2">%s</p>' % _h(sp["大限说明"]))
            P.append("</div></details>")
    if "占星" in data:
        a = M_plain.astro_plain(data["占星"])
        P.append('<h2 style="font-size:15px;border-left-color:var(--gold);margin-top:22px">西洋占星 · 看性格的另一面</h2>')
        P.append('<div class="plain"><h3>一句话</h3><p>%s</p></div>' % _h(a["一句话"]))
        P.append('<div class="plain"><h3>%s</h3>' % _h(a["三支柱"]["标题"]))
        for x in a["三支柱"]["列表"]:
            P.append('<p><span class="k">%s</span><br>%s</p>' % (_h(x["名"]), _h(x["文"])))
        P.append("</div>")
        if a["性格拼图"]["列表"]:
            P.append('<div class="plain"><h3>%s</h3>' % _h(a["性格拼图"]["标题"]))
            for x in a["性格拼图"]["列表"]:
                P.append('<p><span class="k">%s</span><br>%s</p>' % (_h(x["名"]), _h(x["文"])))
            P.append("</div>")
        if a["人生重心"]["列表"]:
            P.append('<div class="plain"><h3>%s</h3>' % _h(a["人生重心"]["标题"]))
            for x in a["人生重心"]["列表"]:
                P.append('<p><span class="k">%s</span><br>%s</p>' % (_h(x["名"]), _h(x["文"])))
            P.append("</div>")
        if a.get("关键线索"):
            P.append('<div class="plain"><h3>最关键的一条线索</h3><p>%s</p></div>' % _h(a["关键线索"]))
        d = a["元素配比"]["明细"]
        P.append('<div class="plain"><h3>%s</h3><p>%s</p>'
                 '<p class="sub2">火 %d · 土 %d · 风 %d · 水 %d</p></div>'
                 % (_h(a["元素配比"]["标题"]), _h(a["元素配比"]["要点"]),
                    d.get("火", 0), d.get("土", 0), d.get("风", 0), d.get("水", 0)))
        # 1.3.1 新增：四元素逐项展开（折叠）。
        # 上面那行只有四个数字，看不出「我这个配比意味着什么」——
        # 哪一项最旺、旺了像什么样、哪一项完全缺、缺了要补什么。
        if a["元素配比"].get("逐项"):
            P.append('<details class="fold"><summary>四种元素逐项看'
                     '<span class="cnt">占星四元素</span></summary><div class="fbody">')
            P.append('<div class="note-sys">这里的火 / 土 / 风 / 水是'
                     '<b>西洋占星的四元素</b>，由行星与星座决定，'
                     '和八字那套木火土金水<b>是两套独立体系</b> ——'
                     '没有换算公式，也不该互相替代。两套都看，'
                     '指向同一件事时结论才算被交叉印证。</div>')
            P.append('<div class="el">')
            for x in a["元素配比"]["逐项"]:
                P.append('<div class="it"><div class="hd">'
                         '<span class="en" style="color:%s">%s</span>'
                         % (EL_COLOR.get(x["元素"], "#666"), _h(x["元素"])))
                if x["最旺"]:
                    P.append('<span class="tag hi">最多</span>')
                if x["完全缺"]:
                    P.append('<span class="tag lo">完全没有</span>')
                P.append('<span class="pc">%d 个 · %.0f%%</span></div>'
                         % (x["个数"], x["占比"]))
                if x["多时"]:
                    P.append('<p class="li"><span class="h">这一项旺时</span>%s</p>'
                             % _h(x["多时"]))
                if x["少时"]:
                    P.append('<p class="li"><span class="h">这一项缺时</span>%s</p>'
                             % _h(x["少时"]))
                P.append("</div>")
            P.append("</div></div></details>")
        if a["关系张力"]["列表"]:
            P.append('<div class="plain"><h3>%s</h3>' % _h(a["关系张力"]["标题"]))
            for x in a["关系张力"]["列表"]:
                P.append('<p>%s</p>' % _h(x["文"]))
            P.append("</div>")
        if a["实用档案"]["列表"]:
            P.append('<div class="plain"><h3>%s</h3>' % _h(a["实用档案"]["标题"]))
            for x in a["实用档案"]["列表"]:
                d = x["档案"]
                P.append('<p><span class="k">%s</span></p><div class="luckgrid">'
                         '<div><b>日期范围</b>%s</div>'
                         '<div><b>守护星</b>%s</div>'
                         '<div><b>幸运色</b>%s</div>'
                         '<div><b>幸运数字</b>%s</div>'
                         '<div><b>幸运日</b>%s</div>'
                         '<div><b>幸运宝石</b>%s</div>'
                         '<div><b>适合职业</b>%s</div>'
                         '<div><b>对应身体</b>%s</div></div>'
                         % (_h(x["名"]), _h(d["日期"]), _h(d["守护星"]), _h(d["幸运色"]),
                            _h(d["幸运数字"]), _h(d["幸运日"]), _h(d["宝石"]),
                            _h(d["职业"]), _h(d["身体"])))
            P.append("</div>")

        # ---- 1.5.0：轴点 ----
        if a.get("轴点详批") and a["轴点详批"]["列表"]:
            P.append('<details class="fold"><summary>两个轴点'
                     '<span class="cnt">上升与天顶</span></summary><div class="fbody">')
            P.append('<p class="sub2">上升不是「真正的你」，是别人看到的你；'
                     '天顶是命运把你推向的位置。两者都不是性格本身，'
                     '而是「你在别人眼里」和「你被认可的方向」。</p><div class="ssx">')
            for x in a["轴点详批"]["列表"]:
                P.append('<div class="it"><div class="hd">'
                         '<span class="pn">%s</span><span class="gz2">%s</span>'
                         '<span class="pc">%s %s</span></div>'
                         % (_h(x["名"]), _h(x["符号"]), _h(x["星座"]), _h(x["度数"])))
                P.append('<p class="li"><span class="h">%s</span>%s</p>'
                         % (_h(x["角色"]), _h(x["含义"])))
                P.append("</div>")
            P.append("</div></div></details>")

        # ---- 1.5.0：行星性质 ----
        if a.get("性质详批") and a["性质详批"]["明细"]:
            qd = a["性质详批"]
            P.append('<details class="fold"><summary>你的行星性质'
                     '<span class="cnt">%s 最多</span></summary><div class="fbody">'
                     % _h(qd["最多"]))
            P.append('<p class="li">%s</p>' % _h(qd["最多说明"]))
            P.append('<div class="ssx">')
            for x in qd["明细"]:
                P.append('<div class="it"><div class="hd">'
                         '<span class="pn">%s</span><span class="pc">%d 个</span></div>'
                         '<p class="sub2">%s</p></div>'
                         % (_h(x["性质"]), x["个数"], _h(x["含义"])))
            P.append("</div>")
            P.append("<h3 style='font-size:14px;margin:14px 0 6px'>各星落哪类</h3>")
            P.append('<p class="sub2">%s</p>'
                     % _h("；".join("%s%s" % (x["天体"], x["性质"][0]) for x in qd["各星"])))
            P.append("</div></details>")

        # ---- 1.5.0：全部相位 ----
        if a.get("相位详批") and a["相位详批"]["合计"]:
            ad = a["相位详批"]
            P.append('<details class="fold"><summary>全部相位'
                     '<span class="cnt">和谐 %d · 张力 %d</span></summary><div class="fbody">'
                     % (len(ad["和谐"]), len(ad["张力"])))
            P.append('<p class="sub2">和谐相是天生助力，张力相是要练的地方 —— '
                     '「哪些是助力、哪些是功课」这个分组比逐个列更重要。'
                     '之前只讲了强度前 4 组，其余 19 组算了白算。</p>')
            for tag, cls, title in (("和谐", "ji", "天生的助力"),
                                    ("张力", "xiong", "要练的地方")):
                if not ad[tag]:
                    continue
                P.append("<h3 style='font-size:14px;margin:14px 0 6px'>%s（%d 组）</h3>"
                         % (title, len(ad[tag])))
                P.append('<div class="ssx">')
                for x in ad[tag]:
                    P.append('<div class="it"><div class="hd">'
                             '<span class="pn%s">%s · %s</span>'
                             '<span class="pc">%s %.2f</span></div>'
                             % (" " + cls if cls else "", _h(x["职能1"]),
                                _h(x["职能2"]), _h(x["强度档"]), x["强度"]))
                    P.append('<p class="li">%s</p>' % _h(x["说明"]))
                    P.append('<p class="sub2">%s</p>' % _h(x["强度含义"]))
                    P.append("</div>")
                P.append("</div>")
            P.append("</div></details>")
        # ---- 1.6.0：关系宫 ----
        if a.get("关系宫详批") and a["关系宫详批"]["列表"]:
            hd2 = a["关系宫详批"]
            nEmpty = len([x for x in hd2["列表"] if x["空"]])
            P.append('<details class="fold"><summary>关系相关的宫'
                     '<span class="cnt">%d 宫 · 空 %d 个</span></summary>'
                     '<div class="fbody">' % (len(hd2["列表"]), nEmpty))
            # 概述不能直接用「空宫说明」—— 那是给单个空宫写的，
            # 放在开头会变成「整块的关系宫都没星」的意思，方向是错的。
            P.append('<p class="sub2">这五宫分别管伴侣、深度联结、家、'
                     '事业角色与朋友。先看每宫管什么，再看落了哪些星。</p>')
            if nEmpty:
                P.append('<p class="sub2">其中 %d 宫没有星。%s</p>'
                         % (nEmpty, _h(hd2["空宫说明"])))
            P.append('<div class="ssx">')
            for x in hd2["列表"]:
                P.append('<div class="it"><div class="hd">'
                         '<span class="pn">第 %d 宫</span>'
                         '<span class="pc">%s</span></div>'
                         % (x["宫"], _h(x["星座"])))
                P.append('<p class="li"><span class="h">%s</span>%s</p>'
                         % (_h(x["名"]), _h(x["管什么"])))
                if x["空"]:
                    P.append('<p class="sub2">这一宫没有星，'
                             '不靠外力推 —— 怎么走看你自己的选择。</p>')
                else:
                    for y in x["星"]:
                        P.append('<p class="li">%s · %s</p>'
                                 % (_h(y["名"]), _h(y["说明"])))
                P.append("</div>")
            P.append("</div></div></details>")

    # ---------- B 类：三盘交叉 ----------
    # 放在三段之后：三盘的数据都齐了才交叉得出来。
    #
    # 排布上刻意把「一致」放主位、「分歧」折起来。
    # 用户反馈过「很混乱，好多不同的结果」——技术上每条都有依据，
    # 但把三段互相矛盾的话平铺开、让读者自己判断信哪个，是设计失职。
    # 读者默认看到的应该是三边都指向同一头的那一面。
    # 分歧如实保留，只是不占主位。
    if "八字" in data or "紫微" in data or "占星" in data:
        x = M_plain.cross_plain(data.get("八字"), data.get("紫微"),
                                data.get("占星"))
        if x["一致"] or x["分歧"] or x["单盘"]:
            P.append('<h2 style="font-size:15px;border-left-color:var(--gold)">'
                     '三盘交叉 · 几套体系一起看</h2>')
            P.append('<div class="plain"><p>%s</p><p class="sub2">%s</p>'
                     '</div>' % (_h(x["要点"]), _h(x["说明"])))

            # 「怎么读」放在最前面：读者需要先知道怎么看，
            # 再看结论 —— 顺序反过来等于让人先困惑再解释。
            P.append('<div class="plain"><h3>先说怎么读</h3>'
                     '<p class="li">三套体系是<em>各自独立</em>算的，'
                     '彼此之间没有换算、也不互相验证。</p>'
                     '<p class="li">下面<em>直接显示</em>的，是三边都指向'
                     '同一头的那几面 —— 这种面可以作为你的倾向来看。</p>'
                     '<p class="li">折起来的「三边说法不同」不是哪一套错了，'
                     '而是说明你在这一面本来就比较多 —— '
                     '不同场景下你本来就会表现得不一样。</p>'
                     '<p class="li">三套体系衡量的是不同的东西，'
                     '所以这里不投票、不合成一个「唯一答案」：'
                     '投出来的那个数字不对应任何一套体系真实的算法。</p>'
                     '</div>')

            if x["一致"]:
                P.append('<div class="plain"><h3>三边都指向同一头</h3>'
                         '<div class="tagline">')
                for r in x["一致"]:
                    P.append('<div class="tag"><b>%s</b>%s</div>'
                             % (_h(r["维度"]), _h(r["同向"])))
                P.append('</div><p class="sub2">依据：%s</p></div>'
                         % _h(" / ".join("%s %s" % (g["盘"], g["依据"])
                                         for g in x["一致"][0]["各家"])))

            rest = x["分歧"] + x["单盘"]
            if rest:
                P.append("<details class=\"ssx\"><summary>三边说法不同"
                         "（%d 个维度，点开看各自怎么说）</summary>"
                         % len(rest))
                P.append('<div class="plain">')
                for r in rest:
                    P.append('<div class="xsx"><p class="xsx-q">%s：%s</p>'
                             % (_h(r["维度"]), _h(r["问"])))
                    for g in r["各家"]:
                        P.append('<p class="li"><b>%s</b>：%s　'
                                 '<span class="sub2">%s</span></p>'
                                 % (_h(g["盘"]), _h(g["端"]), _h(g["依据"])))
                    if r["一致"]:
                        P.append('<p class="sub2">只有一盘给了信号，'
                                 '无从交叉 —— 这里只代表那一套体系怎么看。</p>')
                    P.append("</div>")
                P.append("</div></details>")

            P.append("<details class=\"ssx\"><summary>这三边分别按什么算的"
                     "（想查证时点开）</summary>"
                     '<div class="plain"><div class="tagline">')
            for s in x["依据"]:
                P.append('<div class="tag"><b>%s</b>%s</div>'
                         % (_h(s["盘"]), _h(s["源"])))
            P.append('</div><p class="sub2">%s</p></div></details>'
                     % _h(x["提醒"]))
    # ---------- C 类：桃花星 + 行业细分 ----------
    #
    # 同样按「减少并列结论」的思路处理：
    #  - 桃花星补一句「怎么读」，说明三边说的是不同层面
    #  - 行业按依据分组（同一喜用神下的行业本来就是同一件事的展开，
    #    铺平了会被读成十几个互相冲突的结论）
    th = M_plain.taohua_plain(data.get("八字"), data.get("紫微"),
                              data.get("占星"))
    if th["列表"]:
        P.append('<h2 style="font-size:15px;border-left-color:var(--gold)">'
                 '%s</h2>' % _h(th["标题"]))
        P.append('<div class="plain"><p>%s</p>'
                 '<p class="li">下面三边说的是<em>不同层面</em>，'
                 '不是互相矛盾：八字看的是人缘的广度，'
                 '紫微看的是你在关系里的姿态，'
                 '占星看的是你被什么样的人吸引、'
                 '以及你希望怎么被对待。</p></div>'
                 % _h(th["要点"]))
        P.append('<details class="ssx"><summary>三盘分别怎么说'
                 '（点开逐条对照）</summary><div class="plain">')
        for r in th["列表"]:
            P.append('<div class="xsx"><p class="xsx-h"><b>%s</b>%s</p>'
                     % (_h(r["盘"]), _h(r["项"])))
            P.append('<p class="li">→ %s　<span class="sub2">%s</span></p>'
                     % (_h(r["答"]), _h(r["依据"])))
            P.append('<p class="sub2">%s</p>' % _h(r["说明"]))
            P.append("</div>")
        P.append('<p class="sub2">%s</p></div></details>' % _h(th["提醒"]))

    cr = M_plain.career_plain(data.get("八字"), data.get("紫微"),
                              data.get("占星"))
    if cr["列表"]:
        P.append('<h2 style="font-size:15px;border-left-color:var(--gold)">'
                 '%s</h2>' % _h(cr["标题"]))
        P.append('<div class="plain"><p>%s</p><p class="sub2">%s</p></div>'
                 % (_h(cr["要点"]), _h(cr["提醒"])))
        # 按依据分组：同一依据下的行业是同一件事的展开，
        # 铺平会被读成十几个并列且互相冲突的结论。
        groups = []
        for r in cr["列表"]:
            k = (r["盘"], r["依据"])
            if groups and groups[-1][0] == k:
                groups[-1][1].append(r)
            else:
                groups.append((k, [r]))
        if len(groups) > 1:
            P.append('<details class="ssx"><summary>%d 组方向'
                     '（点开看每组有哪些行业）</summary><div class="plain">'
                     % len(groups))
        else:
            P.append('<div class="plain">')
        for (pan, why), items in groups:
            P.append('<p class="xsx-h"><b>%s</b>%s</p>'
                     % (_h(pan), _h(why)))
            P.append('<div class="tagline">')
            for r in items:
                P.append('<div class="tag"><b>%s</b>%s</div>'
                         % (_h(r["行业"]), _h("、".join(r["角色"]))))
            P.append('</div><p class="sub2">角色类型是行业内的通用分类，'
                     '不是「你应该去当的职位」。</p>')
        if len(groups) > 1:
            P.append("</div></details>")
        else:
            P.append("</div>")
    P.append("</section>")

    P.append("</section>")
    return "".join(P)


def render_glossary():
    P = ['<section><h2>名词解释 · 看不懂的词看这里</h2><div class="gloss">']
    for k, v in M_plain.GLOSSARY.items():
        P.append("<div><b>%s</b>：%s</div>" % (_h(k), _h(v)))
    P.append("</div></section>")
    return "".join(P)


def render_html(data, title="命理神机 · 命盘"):
    hl = M_plain.headline(data)
    parts = ['<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width,initial-scale=1">',
             "<title>%s</title><style>%s</style></head><body><div class='wrap'>" % (_h(title), CSS),
             "<h1>命 理 神 机</h1>",
             "<div class='sub'>八字 · 紫微斗数 · 西洋占星　|　在你自己的电脑上算，不上传、不联网</div>",
             '<div class="headline"><div class="big">%s</div>'
             '<div class="tip">↑ 这是你命盘的三个关键词，下面用大白话展开</div></div>' % _h(hl)]
    parts.append(render_plain(data))
    parts.append('<div class="secnote" style="text-align:center;margin:6px 0 16px">'
                 '———— 以下是专业排盘数据，想深入研究的可以往下看 ————</div>')
    if "八字" in data:
        parts.append(render_bazi(data["八字"]))
    if "紫微" in data:
        parts.append(render_ziwei(data["紫微"]))
    if "占星" in data:
        parts.append(render_astro(data["占星"]))
    parts.append(render_glossary())
    parts.append('<div class="foot">上面的排盘结果是按天文历法和命理规则算出来的，'
                 '解读部分仅供娱乐参考，不能当作医疗、投资或人生的决策依据。<br>'
                 '命盘显示的是可能性，路怎么走还是看你自己。</div>')
    parts.append("</div></body></html>")
    return "".join(parts)


def main(argv=None):
    setup_console()
    p = argparse.ArgumentParser(description="命理神机 · 八字/紫微/占星综合排盘（零依赖、可离线）")
    p.add_argument("--solar", type=parse_date, help="阳历生日，例如 1990-05-15")
    p.add_argument("--lunar", type=parse_date, help="农历生日，例如 1990-04-21")
    p.add_argument("--leap", action="store_true", help="如果生日在闰月，加上这个开关")
    p.add_argument("--hour", type=parse_hour, help="出生时间，例如 12:00")
    p.add_argument("--shichen", choices=list(ZHI), help="出生时辰：子、丑、寅…（不知道几点就用这个）")
    p.add_argument("--sex", required=True, choices=("男", "女"))
    p.add_argument("--place", default=None, help="出生地")
    p.add_argument("--lat", type=float, default=None, help="出生地纬度，例如 39.9（占星算上升星座要用）")
    p.add_argument("--lon", type=float, default=None, help="出生地经度，例如 116.4")
    p.add_argument("--year", type=int, default=None, help="想看哪一年的运势，例如 2027")
    p.add_argument("--only", choices=("bazi", "ziwei", "astro"), default=None)
    p.add_argument("--out", default=None, help="把命盘保存成网页文件，例如 命盘.html")
    p.add_argument("--json", action="store_true", help="输出给程序看的原始数据")
    a = p.parse_args(argv)
    if not a.solar and not a.lunar:
        p.error("请至少填一个生日：阳历用 --solar，农历用 --lunar")
    data = build(solar=a.solar, lunar=a.lunar, leap=a.leap, hour=a.hour, shichen=a.shichen,
                 sex=a.sex, place=a.place, lat=a.lat, lon=a.lon, only=a.only, year=a.year)

    if a.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    if a.out:
        html = render_html(data)
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(html)
        print("已生成自包含命盘：%s（%d 字节，可离线双击打开）" % (a.out, len(html.encode("utf-8"))))
        return 0
    # 终端报告
    if "八字" in data:
        print(M_bazi.format_report(data["八字"]))
        print()
    if "紫微" in data:
        print(M_ziwei.format_report(data["紫微"]))
        print()
    if "占星" in data:
        print(M_astro.format_report(data["占星"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

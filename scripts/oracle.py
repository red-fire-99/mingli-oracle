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
        out["占星"] = M_astro.pai_pan(solar=solar, lunar=lunar, leap=leap,
                                      hour=hour or (12, 0), sex=sex, lat=lat, lon=lon, place=place)
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


def _h(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


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

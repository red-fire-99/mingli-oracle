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
import re
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

CSS = """/* ===================================================================
   命书 · 设计系统

   纸、墨、朱砂、金线。标题用衬线，正文用无衬线；
   章节靠留白和细线分隔，不再一层层套卡片。
   改配色、字阶、间距只动下面的令牌，组件规则在令牌之后。
   =================================================================== */
:root{
  --bg:#f2ece1; --card:#fbf7ee; --paper:#f8f2e5;
  --ink:#241f19; --ink2:#3a332a; --sub:#6a6052; --faint:#6f6556;
  --line:#ddd2bf; --line2:#eae1d1;
  --red:#9c2a24; --gold:#a5812c; --gold-ink:#7c611e;
  --green:#356b46; --blue:#2e5a77; --purple:#684877;
  --serif:"Noto Serif SC","Source Han Serif SC","Songti SC","STSong","SimSun",serif;
  --sans:"PingFang SC","Noto Sans SC","Microsoft YaHei","Source Han Sans SC",system-ui,sans-serif;
  /* 字阶 */
  --t-xs:11px; --t-sm:12.5px; --t-md:13.5px; --t-base:15.5px;
  --t-lg:17px; --t-xl:20px; --t-2xl:24px; --t-3xl:30px;
  /* 间距 */
  --s1:4px; --s2:8px; --s3:12px; --s4:16px; --s5:24px; --s6:34px;
  /* 圆角与阴影：印刷品是直角的，圆角只留 2–4px */
  --r-sm:3px; --r-md:4px; --r-lg:4px; --r-pill:999px;
  --sh-1:0 1px 2px rgba(60,45,25,.04);
  --sh-2:0 8px 22px rgba(60,45,25,.08);
  --sh-3:0 18px 44px rgba(60,45,25,.14);
  --dur:.2s; --ease:cubic-bezier(.4,0,.2,1);
}
@media (prefers-reduced-motion: reduce){
  :root{--dur:0s}
  *{animation:none!important;transition:none!important}
}

*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{
  margin:0; padding:0 22px 84px; color:var(--ink);
  font-family:var(--sans); font-size:var(--t-base); line-height:1.85;
  background-color:var(--bg);
  /* 纸纹：两层暖光 + 一层极淡的织纹。
     织纹用重复渐变而不是 SVG 滤镜 —— 滤镜得引用一个内部 id，
     而产物校验要求 CSS 里除 data: 外不得出现任何 url()。 */
  background-image:
    radial-gradient(1100px 620px at 50% -8%,#fcf8ef 0,rgba(252,248,239,0) 62%),
    radial-gradient(820px 520px at 100% 104%,#e9dfcd 0,rgba(233,223,205,0) 60%),
    repeating-linear-gradient(90deg,rgba(120,90,40,.014) 0 2px,rgba(0,0,0,0) 2px 4px),
    repeating-linear-gradient(0deg,rgba(120,90,40,.014) 0 3px,rgba(0,0,0,0) 3px 7px);
  background-attachment:fixed;
}
.wrap{max-width:780px;margin:0 auto}

/* ---------- 封面 ---------- */
.wrap>h1{
  position:relative;font-family:var(--serif);font-size:42px;font-weight:600;
  text-align:center;letter-spacing:.28em;text-indent:.28em;color:var(--ink);
  margin:34px 0 12px;line-height:1.35;
}
/* 朱印。不是装饰贴纸：它给整页定一个「命书」的调子 */
.wrap>h1::before{
  content:"命";display:block;width:40px;height:40px;margin:0 auto 22px;
  background:var(--red);color:#fff8ee;font-family:var(--serif);
  font-size:23px;line-height:40px;letter-spacing:0;text-indent:0;
  border-radius:2px;transform:rotate(-4deg);
  box-shadow:0 2px 0 rgba(120,30,25,.22);
}
.sub{
  text-align:center;color:var(--sub);font-size:var(--t-sm);
  letter-spacing:.14em;margin:0 0 4px;line-height:1.9;
}
.headline{
  border-top:1px solid var(--line);border-bottom:1px solid var(--line);
  padding:32px 14px 28px;margin:28px 0 0;text-align:center;
  background:none;border-radius:0;
}
.headline .big{
  font-family:var(--serif);font-size:21px;font-weight:600;color:var(--ink);
  line-height:2.1;letter-spacing:.02em;max-width:34em;margin:0 auto;
}
.headline .tip{
  font-size:var(--t-xs);color:var(--faint);margin-top:12px;letter-spacing:.08em;
}

/* ---------- 目录：一条条书目，不是一排按钮 ---------- */
.toc{
  margin:0;padding:28px 0 20px;background:none;border:0;
  border-bottom:1px solid var(--line);border-radius:0;box-shadow:none;
}
.toc-h{
  display:block;font-family:var(--serif);font-size:18px;font-weight:600;
  color:var(--ink);letter-spacing:.14em;margin:0 0 14px;
}
.toc-h::before{
  content:"CONTENTS";display:block;font-family:var(--sans);font-size:9px;
  font-weight:600;letter-spacing:.36em;color:var(--gold-ink);margin-bottom:7px;
}
.toc-tip{
  display:block;font-family:var(--sans);font-size:var(--t-xs);
  font-weight:400;color:var(--faint);letter-spacing:.06em;margin-top:4px;
}
.toc-grid{display:grid;grid-template-columns:1fr 1fr;gap:0 44px;counter-reset:toc}
.toc-i{
  display:flex;align-items:baseline;gap:10px;padding:9px 0;
  border-bottom:1px solid var(--line2);background:none;border-radius:0;
  color:var(--ink);text-decoration:none;font-size:var(--t-md);line-height:1.6;
  counter-increment:toc;transition:color var(--dur) var(--ease);
}
.toc-i::before{
  content:counter(toc,decimal-leading-zero);flex:none;width:20px;
  font-size:9.5px;letter-spacing:.08em;color:var(--gold-ink);
  font-variant-numeric:tabular-nums;
}
.toc-i:hover{color:var(--red)}
.toc-i:hover::before{color:var(--red)}
.toc-tools{display:flex;align-items:center;gap:16px;margin-top:16px;flex-wrap:wrap}
.toc-search{
  flex:1 1 200px;min-width:140px;padding:7px 2px;font-size:var(--t-md);
  font-family:inherit;color:var(--ink);background:none;
  border:0;border-bottom:1px solid var(--line);border-radius:0;
}
.toc-search::placeholder{color:var(--faint)}
.toc-search:focus{outline:none;border-bottom-color:var(--red)}
.toc-btn{
  padding:4px 0;font-size:var(--t-xs);font-family:inherit;cursor:pointer;
  color:var(--sub);background:none;border:0;border-bottom:1px solid transparent;
  letter-spacing:.08em;
}
.toc-btn:hover{color:var(--red);border-bottom-color:var(--red)}
.toc-results{
  margin-top:14px;max-height:240px;overflow:auto;
  border-top:1px solid var(--line);padding-top:10px;
}
.toc-results .r-h{font-size:var(--t-xs);color:var(--faint);margin-bottom:6px}
.toc-results .r-i{
  display:block;width:100%;text-align:left;padding:7px 0;font-size:var(--t-md);
  line-height:1.7;color:var(--ink);background:none;border:0;
  border-bottom:1px solid var(--line2);border-radius:0;cursor:pointer;
  font-family:inherit;
}
.toc-results .r-i:hover{color:var(--red)}
.toc-results mark{background:#f2e2b6;color:inherit;border-radius:1px}
/* 本页查找的命中底色（Custom Highlight API 只负责区间，颜色得自己写） */
::highlight(ml-find){background-color:#f2e2b6}
/* 锚点跳转时别被吸顶条压住 */
h2[id]{scroll-margin-top:44px}

/* ---------- 章节 ---------- */
section{
  background:none;border:0;border-radius:0;box-shadow:none;
  padding:52px 0 10px;margin:0;position:relative;
}
section+section{border-top:1px solid var(--line)}
.wrap h2,#result h2{
  position:relative;font-family:var(--serif);font-size:27px;font-weight:600;
  color:var(--ink);letter-spacing:.08em;line-height:1.45;
  margin:0 0 22px;padding:0 0 14px 24px;border:0;
}
.wrap h2::before,#result h2::before{
  content:"";position:absolute;left:2px;top:.66em;width:7px;height:7px;
  background:var(--red);transform:rotate(45deg);
}
.wrap h2::after,#result h2::after{
  content:"";position:absolute;left:0;bottom:0;width:100%;height:1px;
  background:linear-gradient(90deg,var(--red) 0 42px,var(--line) 42px 100%);
}
/* 说人话区里的小节标题（八字 / 紫微 / 占星…）：比章标题轻一档 */
#s-bazi,#s-ziwei,#s-astro,#s-cross,#s-taohua,#s-industry{
  font-size:21px;letter-spacing:.06em;margin-top:54px;
  padding-left:20px;padding-bottom:12px;
}
#s-bazi::before,#s-ziwei::before,#s-astro::before,#s-cross::before,
#s-taohua::before,#s-industry::before{
  left:1px;top:.7em;width:6px;height:6px;background:var(--gold);
}
#s-bazi::after,#s-ziwei::after,#s-astro::after,#s-cross::after,
#s-taohua::after,#s-industry::after{
  background:linear-gradient(90deg,var(--gold) 0 28px,var(--line) 28px 100%);
}

/* ---------- 一分钟速览：一页装订线内的题要 ---------- */
.quick{
  position:relative;margin:0 0 34px;padding:26px 28px;
  background:var(--paper);border:1px solid var(--line);border-radius:2px;
  box-shadow:inset 0 0 0 1px rgba(255,255,255,.5);
}
.quick::before{
  content:"";position:absolute;inset:9px;
  border:1px solid rgba(165,129,44,.18);pointer-events:none;
}
.quick-h{
  font-family:var(--serif);font-size:17px;font-weight:600;
  color:var(--ink);letter-spacing:.1em;
}
.quick-t{font-size:var(--t-xs);color:var(--faint);margin:2px 0 16px;letter-spacing:.04em}
.quick-grid{display:grid;gap:18px 32px;grid-template-columns:repeat(auto-fit,minmax(230px,1fr))}
.q{min-width:0;padding-top:10px;border-top:1px solid var(--line2)}
.quick-grid b{
  display:block;font-size:10.5px;font-weight:600;color:var(--red);
  letter-spacing:.16em;margin-bottom:5px;
}
.quick-grid span{font-size:var(--t-sm);color:var(--ink2);line-height:1.85}
/* 每一节开头一句话：这一节讲什么，读者不用点开才知道 */
.sec-lead{
  font-size:var(--t-md);color:var(--sub);line-height:1.85;
  margin:0 0 20px;padding-left:14px;border-left:1px solid var(--gold);
  max-width:44em;
}

/* ---------- 命盘印象：整页的「题眼」 ---------- */
.persona{
  position:relative;background:#fbf6ea;border:1px solid var(--line);
  border-radius:2px;padding:40px 42px 30px;margin:8px 0 34px;
  box-shadow:0 10px 30px rgba(80,60,30,.05);
}
.persona::before{
  content:"";position:absolute;inset:10px;
  border:1px solid rgba(165,129,44,.22);pointer-events:none;
}
.persona .p-eyebrow{
  font-size:10px;font-weight:600;letter-spacing:.42em;
  color:var(--gold-ink);margin-bottom:16px;
}
.persona .p-lead{
  font-family:var(--serif);font-size:29px;font-weight:600;line-height:1.72;
  color:var(--ink);margin:0 0 28px;letter-spacing:.02em;
  max-width:30em;text-wrap:pretty;
}
.persona .p-block{margin:24px 0 0;padding-top:22px;border-top:1px solid var(--line2)}
.persona .p-block:first-of-type{border-top:0;padding-top:0;margin-top:0}
.persona .p-k{
  font-size:10.5px;font-weight:600;color:var(--red);
  letter-spacing:.2em;margin-bottom:6px;
}
.persona .p-v{
  font-size:var(--t-base);line-height:2;color:var(--ink2);
  max-width:36em;margin:0 0 8px;text-wrap:pretty;
}
.persona .p-v:last-child{margin-bottom:0}
.persona .p-src{font-size:var(--t-xs);color:var(--faint);margin-top:4px}
.persona .p-note{
  font-size:var(--t-xs);color:var(--sub);margin-top:26px;
  padding-top:18px;border-top:1px solid var(--line2);
}
/* 内嵌折叠块：不再套一层底色，只用细线 */
.persona details.fold{border-top:1px solid var(--line2);margin:14px 0 0}
.persona details.fold>summary{padding:13px 0;color:var(--red)}
.persona details.fold>summary::before{border-color:var(--gold)}

/* ---------- 白话正文 ---------- */
.plain{
  margin:26px 0;padding:2px 0 2px 20px;
  background:none;border:0;border-left:1px solid #e0d3bc;border-radius:0;
}
.plain h3{
  font-family:var(--serif);font-size:17px;font-weight:600;color:var(--ink);
  letter-spacing:.06em;margin:0 0 9px;line-height:1.5;
}
.plain h3::before{
  content:"";display:inline-block;width:5px;height:5px;background:var(--red);
  transform:rotate(45deg);margin-right:10px;vertical-align:3px;
}
.plain p{
  font-size:var(--t-base);line-height:1.95;color:var(--ink2);
  max-width:38em;margin:6px 0;text-wrap:pretty;
}
.plain .k{color:var(--red);font-weight:600}
.plain .sub2{
  color:var(--sub);font-size:var(--t-sm);line-height:1.9;max-width:40em;
}
.tagline{display:flex;flex-wrap:wrap;gap:12px 28px;margin:14px 0 4px}
.tagline .tag{
  flex:1 1 250px;min-width:210px;padding-top:10px;
  border-top:1px solid var(--line);background:none;border-radius:0;
  font-size:var(--t-md);line-height:1.8;color:var(--ink2);
}
.tagline .tag b{
  display:block;color:var(--red);font-size:10.5px;letter-spacing:.16em;
  margin-bottom:3px;font-weight:600;
}

/* ---------- 折叠块：一行标题 + 一枚 ＋ ---------- */
details.fold{
  background:none;border:0;border-top:1px solid var(--line);
  border-radius:0;margin:10px 0;padding:0;overflow:visible;
}
details.fold>summary{
  cursor:pointer;padding:15px 0;font-size:var(--t-md);font-weight:600;
  color:var(--ink);list-style:none;display:flex;align-items:center;gap:12px;
  letter-spacing:.01em;transition:color var(--dur) var(--ease);
}
details.fold>summary::-webkit-details-marker{display:none}
details.fold>summary::before{
  content:"+";flex:none;width:20px;height:20px;border:1px solid var(--gold);
  border-radius:50%;color:var(--gold-ink);font-size:14px;font-weight:400;
  line-height:18px;text-align:center;
  transition:background var(--dur) var(--ease),color var(--dur) var(--ease);
}
details.fold[open]>summary{color:var(--red)}
details.fold[open]>summary::before{
  content:"−";background:var(--gold-ink);border-color:var(--gold-ink);color:#fff;
}
details.fold:hover>summary{color:var(--red)}
details.fold>summary:focus-visible{outline:2px solid var(--gold);outline-offset:-2px;border-radius:2px}
/* 展开时内容淡入：details 的内容打开前不渲染，transition 没有起点 */
details.fold[open]>*:not(summary){animation:fadeSlide var(--dur) var(--ease)}
@keyframes fadeSlide{from{opacity:0;transform:translateY(-4px)}to{opacity:1;transform:none}}
.fbody{padding:4px 0 24px 32px;font-size:var(--t-base);line-height:1.9;color:var(--ink2)}
.fbody p{margin:6px 0;max-width:40em}
/* 摘要右侧的结论预览：不点开也知道里面有什么 */
details.fold>summary .fold-prev{
  margin-left:auto;font-size:var(--t-sm);font-weight:400;color:var(--faint);
  text-align:right;overflow:hidden;text-overflow:ellipsis;
  white-space:nowrap;max-width:62%;
}
details.fold>summary .fold-prev+.cnt{margin-left:var(--s2)}
details.fold>summary .cnt{
  margin-left:auto;font-size:var(--t-xs);font-weight:400;
  color:var(--faint);letter-spacing:0;
}

/* ---------- 折叠内容 ---------- */
.li{position:relative;padding-left:16px;max-width:40em;line-height:1.9;margin:7px 0}
.li::before{
  content:"";position:absolute;left:0;top:.75em;width:4px;height:4px;
  background:var(--gold);transform:rotate(45deg);
}
.li.warn{color:#8a4a44}
.li.warn::before{background:var(--red)}
.li>span.h{color:var(--sub);font-size:var(--t-md);margin-right:6px}
.hd{
  font-family:var(--serif);font-size:14px;font-weight:600;color:var(--red);
  margin:20px 0 8px;letter-spacing:.1em;
}
.hd:first-child{margin-top:0}
.pn{font-weight:600;color:var(--ink);margin-right:8px}
.pc{color:var(--sub);font-size:var(--t-sm)}
.age,.th,.stg,.tx,.yn,.wx,.wxn,.xiang,.lo,.el,.en,.sh,.dx,.yr{
  font-size:var(--t-sm);color:var(--sub);
}
.age b,.th b,.tx b,.yn b,.wx b,.el b,.en b,.sh b,.dx b,.yr b{
  color:var(--ink);font-weight:600;
}
.cnt{font-variant-numeric:tabular-nums}

.ssx{margin:14px 0;display:flex;flex-direction:column;gap:10px}
.xsx{
  background:none;border:0;border-left:1px solid var(--line);
  border-radius:0;padding:2px 0 2px 14px;line-height:1.85;
}
.xsx-q{font-size:var(--t-xs);color:var(--faint);margin:0 0 3px;letter-spacing:.06em}
.xsx-h{
  font-family:var(--serif);font-size:var(--t-base);font-weight:600;
  margin:0 0 6px;color:var(--ink);
}
.luckgrid{
  display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));
  gap:8px 24px;font-size:var(--t-md);margin:8px 0;
}
.luckgrid>div{line-height:1.8}
.luckgrid b{
  display:block;color:var(--faint);font-size:10px;font-weight:600;
  letter-spacing:.12em;margin-bottom:2px;
}
.hi{
  background:#f8e9e5;color:var(--red);font-weight:600;
  padding:1px 7px;border-radius:2px;font-size:var(--t-sm);
}
.no{color:var(--sub);font-style:normal}
.now-tag{
  background:var(--red);color:#fff;font-size:10px;padding:1px 6px;
  border-radius:2px;margin-left:8px;letter-spacing:.06em;
}
.note-sys{font-size:var(--t-xs);color:var(--faint)}
.gloss{padding:2px 0}
.gloss>div{
  padding:11px 0;border-bottom:1px solid var(--line2);
  line-height:1.85;font-size:var(--t-base);color:var(--ink2);
}
.gloss>div:last-child{border-bottom:0}
.gloss b{color:var(--red);margin-right:8px;font-weight:600}
.secnote{
  font-size:var(--t-xs);color:var(--faint);line-height:1.8;
  margin:36px 0 0;letter-spacing:.12em;text-align:center;
}
.fbody .dy-tl,.fbody .ln-tl{margin:14px 0}
.fbody .astro,.fbody .donut{display:block;margin:16px auto}

/* ---------- 表格：只留横线 ---------- */
.info{
  display:flex;flex-wrap:wrap;gap:6px 28px;font-size:var(--t-md);
  color:var(--sub);margin-bottom:20px;padding-bottom:14px;
  border-bottom:1px solid var(--line2);
}
.info b{color:var(--ink);font-weight:600}
table{width:100%;border-collapse:collapse;font-size:var(--t-base)}
th,td{border:0;border-bottom:1px solid var(--line2);padding:9px 10px;text-align:center}
th{
  font-size:10.5px;font-weight:600;letter-spacing:.1em;color:var(--faint);
  border-bottom:1px solid #c9bca6;background:none;
}
td{color:var(--ink2)}
.gz{font-family:var(--serif);font-size:22px;font-weight:600;letter-spacing:.08em;color:var(--ink)}
.gan{color:var(--red)}.zhi{color:var(--blue)}
.ss{font-size:var(--t-sm);color:var(--sub)}
.cang{font-size:var(--t-sm);color:var(--sub);line-height:1.6}
.pill{
  display:inline-block;padding:1px 8px;border-radius:2px;font-size:var(--t-sm);
  background:transparent;border:1px solid var(--line);color:var(--sub);
  margin:2px 3px 2px 0;
}
.pill.ji{background:#eaf3ec;border-color:#cfe3d4;color:var(--green)}
.pill.xiong{background:#f9eae7;border-color:#eed3cf;color:var(--red)}
.bar{display:flex;align-items:center;gap:10px;margin:8px 0;font-size:var(--t-md)}
.bar .lb{width:30px;color:var(--sub);flex:none;font-size:var(--t-sm)}
.bar .tr{flex:1;height:10px;background:#e9dfcd;border-radius:0;overflow:hidden}
.bar .fl{height:100%;border-radius:0;transition:width var(--dur) var(--ease)}
.bar .vl{
  width:52px;text-align:right;color:var(--sub);
  font-variant-numeric:tabular-nums;flex:none;font-size:var(--t-sm);
}

/* ---------- 紫微十二宫盘 ---------- */
.pan{
  display:grid;grid-template-columns:repeat(4,1fr);
  grid-template-rows:repeat(4,1fr);gap:7px;aspect-ratio:1/1;
  max-width:680px;margin:0 auto;
}
.cell{
  border:1px solid var(--line);border-radius:2px;padding:8px;
  background:#fcf8ef;font-size:var(--t-sm);overflow:hidden;
  position:relative;min-height:0;
}
.cell.ming{
  border-color:var(--red);background:#fbf1e9;
  box-shadow:inset 0 0 0 1px var(--red);
}
.cell.shen{border-style:dashed}
.cell .pos{
  font-size:10px;color:var(--faint);
  display:flex;justify-content:space-between;letter-spacing:.06em;
}
.cell .gz2{
  font-family:var(--serif);font-size:16px;font-weight:600;
  margin:3px 0;letter-spacing:.04em;
}
.cell .stars{line-height:1.55}
.star{color:var(--ink2)}
.star.main{color:var(--red);font-weight:600}
/* 化曜星名用的金色单独加深：--gold 还承担边框/装饰，
   全局加深会让金边发闷。文字版 5.5:1。 */
.star.hua{color:#7c611e}
.star.aux{color:var(--blue)}
.center{
  grid-column:2/4;grid-row:2/4;border:1px solid var(--line);border-radius:2px;
  background:var(--paper);display:flex;flex-direction:column;
  justify-content:center;align-items:center;padding:var(--s4);
  text-align:center;font-size:var(--t-md);gap:5px;
}
.center .t{
  font-family:var(--serif);font-size:18px;font-weight:600;
  letter-spacing:.3em;text-indent:.3em;color:var(--red);
}
/* 说人话区的迷你盘：只留宫名和主星，先给形状，不抢正文 */
.pan.mini{max-width:400px;gap:5px;margin:24px auto 10px}
.pan.mini .cell{padding:6px 7px;border-radius:2px}
.pan.mini .pos{font-size:10px}
.pan.mini .stars{font-size:11px;line-height:1.4}
.pan.mini .center{padding:8px;gap:2px}
.pan.mini .center .t{font-size:15px;letter-spacing:.18em}
.pan.mini .center .ss{font-size:10px}
a.cell{
  text-decoration:none;color:inherit;cursor:pointer;
  transition:border-color var(--dur) var(--ease),
  box-shadow var(--dur) var(--ease),transform var(--dur) var(--ease);
}
a.cell:hover{
  border-color:var(--gold);box-shadow:var(--sh-2);
  transform:translateY(-1px);z-index:2;
}
a.cell:focus-visible{outline:2px solid var(--gold);outline-offset:1px}
a.cell.ming:hover{border-color:var(--red)}
.pl .it:target{animation:plHi 1.2s var(--ease)}
@keyframes plHi{
  0%{background:#fdf1e7;box-shadow:inset 0 0 0 2px var(--gold)}
  100%{background:transparent;box-shadow:none}
}
.pl .it{scroll-margin-top:12px}

/* ---------- 五行环 ---------- */
.donut{display:block;margin:0 auto}
.donut .dseg{transition:stroke-dasharray var(--dur) var(--ease)}
.donut .d-main{font-family:var(--serif);font-size:26px;font-weight:600}
.donut .d-sub{font-size:12px}
.donut-wrap{display:flex;align-items:center;gap:32px;flex-wrap:wrap;margin:16px 0}
.donut-legend{flex:1;min-width:180px;font-size:var(--t-md);color:var(--sub)}
.donut-legend div{
  display:flex;align-items:center;gap:9px;margin:7px 0;
  border-bottom:1px solid var(--line2);padding-bottom:6px;
}
.donut-legend div:last-child{border-bottom:0}
.donut-legend i{
  width:8px;height:8px;border-radius:1px;flex:none;transform:rotate(45deg);
}
.donut-legend b{color:var(--ink);font-weight:600}

/* ---------- 方位罗盘：喜用方向直接填朱砂 ---------- */
.compass{position:relative;width:min(300px,100%);aspect-ratio:1/1;margin:24px auto 8px}
.cmp-box{
  position:absolute;inset:20%;border:1px dashed var(--line);
  border-radius:2px;transform:rotate(45deg);
}
.cmp{
  position:absolute;width:64px;height:64px;border-radius:50%;
  display:flex;flex-direction:column;align-items:center;justify-content:center;
  background:var(--paper);border:1px solid var(--line);color:var(--sub);
  font-size:var(--t-sm);line-height:1.2;z-index:1;
}
.cmp b{font-family:var(--serif);font-size:17px;color:var(--ink);font-weight:600}
.cmp span{font-size:var(--t-xs)}
.cmp.on{
  background:var(--red);border-color:var(--red);
  box-shadow:0 6px 16px rgba(156,42,36,.22);
}
.cmp.on b,.cmp.on span{color:#fff}
.cmp-n{top:0;left:50%;transform:translateX(-50%)}
.cmp-s{bottom:0;left:50%;transform:translateX(-50%)}
.cmp-e{right:0;top:50%;transform:translateY(-50%)}
.cmp-w{left:0;top:50%;transform:translateY(-50%)}
.cmp-c{
  top:50%;left:50%;transform:translate(-50%,-50%);
  width:76px;height:76px;background:#f4eddf;border-color:var(--gold);
}
.cmp-c.on{background:var(--red);border-color:var(--red)}

/* ---------- 一生流年格：一格一年，深色 = 助力年 ---------- */
.life{max-width:540px;margin:16px auto 8px}
.life-key{
  display:flex;flex-wrap:wrap;gap:18px;font-size:var(--t-xs);
  color:var(--sub);margin-bottom:10px;
}
.life-key span{display:flex;align-items:center;gap:6px}
.life-key i{width:9px;height:9px;border-radius:1px;background:#e9dfcd}
.life-key i.on{background:var(--red)}
.life-key i.now{background:transparent;box-shadow:inset 0 0 0 1.5px var(--red)}
.life-row{
  display:grid;grid-template-columns:88px repeat(10,1fr);gap:3px;
  align-items:center;margin:3px 0;
}
.life-lab{font-size:var(--t-xs);color:var(--faint);white-space:nowrap}
.life-lab em{display:block;font-style:normal;font-size:10px;color:var(--faint)}
.life .lc{
  display:block;aspect-ratio:1/1;border-radius:1px;
  background:#e9dfcd;min-height:13px;
}
.life .lc.on{background:var(--red)}
.life .lc.now{box-shadow:inset 0 0 0 1.5px #fff,0 0 0 1.5px var(--red)}

/* ---------- 大运时间轴 ---------- */
.dy-tl{
  display:flex;position:relative;margin:22px 0 14px;
  border-top:1px solid var(--line);border-bottom:1px solid var(--line);
  background:none;border-radius:0;overflow:visible;
}
.dy-seg{
  flex:1;padding:11px 4px;text-align:center;font-size:var(--t-xs);
  color:var(--sub);border-right:1px solid var(--line2);
  display:flex;flex-direction:column;gap:2px;min-width:0;
  transition:background var(--dur) var(--ease);
}
.dy-seg:last-child{border-right:0}
.dy-seg b{
  font-family:var(--serif);font-size:14px;color:var(--ink);
  letter-spacing:.04em;font-weight:600;
}
.dy-seg i{font-style:normal;color:var(--faint);font-size:10.5px}
.dy-seg u{text-decoration:none;color:var(--faint);font-size:10px}
.dy-seg.now{background:#f7ecd9;color:var(--red)}
.dy-seg.now b{color:var(--red)}
.dy-now{
  position:absolute;top:-8px;bottom:-8px;width:0;
  border-left:1.5px solid var(--red);pointer-events:none;
}
.dy-now span{
  position:absolute;top:-18px;left:50%;transform:translateX(-50%);
  background:var(--red);color:#fff;font-size:10px;padding:2px 7px;
  border-radius:2px;white-space:nowrap;
}

/* 流年时间轴：七年一格，比大运轴更紧凑 */
.ln-tl{display:flex;gap:5px;margin:16px 0}
.ln-seg{
  flex:1;text-align:center;padding:9px 2px;
  background:none;border:1px solid var(--line);border-radius:2px;
  font-size:var(--t-sm);color:var(--sub);min-width:0;
}
.ln-seg i{display:block;font-style:normal;font-size:10px;color:var(--faint)}
.ln-seg b{
  display:block;font-family:var(--serif);font-size:14px;color:var(--ink);
  letter-spacing:.04em;margin-top:2px;font-weight:600;
}
.ln-seg.now{background:var(--red);border-color:var(--red);color:#fff}
.ln-seg.now i{color:rgba(255,255,255,.9)}
.ln-seg.now b{color:#fff}

/* ---------- 占星星盘 ---------- */
.astro-wrap{display:flex;align-items:center;gap:32px;flex-wrap:wrap;margin:16px 0}
.astro{
  display:block;margin:0 auto;background:#fffdf7;border-radius:50%;
  box-shadow:0 0 0 1px var(--line),0 14px 34px rgba(80,60,30,.07);
  max-width:100%;height:auto;
}
.astro-note{flex:1;min-width:200px}
.astro .a-sign{font-size:9px;letter-spacing:1px}
.astro .a-num{font-size:8px}
.astro .a-sym{font-size:13px;fill:#7a6f5f;font-weight:600}
.astro .a-sym.main{font-size:15px;fill:var(--red);font-weight:700}
.astro .a-core{font-family:var(--serif);font-size:15px;font-weight:600;letter-spacing:2px}
.astro .a-core-sub{font-size:10px;letter-spacing:2px}
.astro .a-asp-t{font-size:8px}
.astro .a-dot{stroke:#e3dbcd;stroke-width:1}
.astro .a-dot.main{stroke:var(--gold);stroke-width:1.5}
.astro .a-pl{cursor:default}
.astro .a-asp{opacity:.55}

/* ---------- 专业区零散件 ---------- */
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:36px}
/* 大运/大限：一列一格，像账簿，不像按钮 */
.liu{
  display:grid;grid-template-columns:repeat(auto-fit,minmax(88px,1fr));
  gap:0;margin:10px 0;font-size:var(--t-sm);
}
.liu span{
  padding:10px 6px;text-align:center;line-height:1.75;
  background:none;border:0;border-top:1px solid var(--line);
  border-right:1px solid var(--line2);color:var(--sub);
}
.liu span:last-child{border-right:0}
.liu span b{color:var(--ink);font-weight:600}
.warn{color:var(--red);font-size:var(--t-md);margin-top:8px}
.foot{
  text-align:center;color:var(--faint);font-size:var(--t-xs);
  margin-top:56px;padding-top:26px;border-top:1px solid var(--line);
  line-height:2;letter-spacing:.06em;
}
.dy,.ly{margin:14px 0;display:flex;flex-direction:column;gap:0}
.dy .it,.ly .it{
  background:none;border:0;border-bottom:1px solid var(--line2);
  border-radius:0;padding:11px 0;line-height:1.85;font-size:var(--t-md);
}
.dy .it.now,.ly .it.now{
  border-color:var(--gold);background:#f9f1e2;
  box-shadow:inset 2px 0 0 var(--gold);padding-left:10px;
}

/* ---------- 接下来三年 ---------- */
.y3{
  margin:18px 0 28px;padding:20px 22px;background:var(--paper);
  border:1px solid var(--line);border-left:2px solid var(--red);border-radius:2px;
}
.y3-h{
  font-family:var(--serif);font-size:15px;font-weight:600;
  color:var(--ink);margin-bottom:3px;letter-spacing:.06em;
}
.y3-sub{font-size:var(--t-xs);color:var(--faint);margin:0 0 12px;line-height:1.7}
.y3-grid{display:grid;gap:14px 26px;grid-template-columns:repeat(auto-fit,minmax(200px,1fr))}
.y3-i{padding-left:12px;border-left:1px solid var(--line);min-width:0}
.y3-yr{
  font-size:var(--t-sm);font-weight:600;color:var(--ink);
  display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin-bottom:4px;
}
.y3-tag{
  font-size:10px;font-weight:600;color:var(--red);background:#f6e5e2;
  border-radius:2px;padding:1px 6px;letter-spacing:.04em;
}
.y3-t{font-size:var(--t-sm);color:var(--ink2);line-height:1.8;margin:0 0 3px}
.y3-n{font-size:var(--t-xs);color:var(--faint);line-height:1.7;margin:0}

/* ---------- 吸顶进度条 + 跳转面板 ---------- */
.ml-pgbar{
  position:fixed;left:0;right:0;top:0;height:30px;z-index:60;
  background:rgba(246,240,230,.94);backdrop-filter:blur(10px);
  border-bottom:1px solid var(--line);display:flex;align-items:center;
  opacity:0;pointer-events:none;transition:opacity .2s;
}
.ml-pgbar.on{opacity:1;pointer-events:auto}
.ml-pgbar-f{position:absolute;left:0;top:0;height:1.5px;width:0;background:var(--red)}
.ml-pgbar-btn{
  display:flex;align-items:center;gap:12px;width:100%;height:100%;
  padding:0 16px;background:none;border:0;font-family:inherit;
  font-size:var(--t-xs);color:var(--sub);cursor:pointer;text-align:left;
  letter-spacing:.06em;
}
.ml-pgbar-btn:hover{color:var(--ink)}
.ml-pgbar-t{flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ml-pgbar-c{
  flex:none;color:var(--red);font-weight:600;font-size:9.5px;letter-spacing:.14em;
}
.ml-jump{
  position:fixed;left:0;right:0;top:30px;z-index:61;display:flex;
  justify-content:center;pointer-events:none;
}
.ml-jump[hidden]{display:none}
.ml-jump-in{
  pointer-events:auto;width:min(540px,calc(100% - 16px));
  max-height:min(72vh,560px);overflow:auto;background:var(--card);
  border:1px solid var(--line);border-top:0;
  border-radius:0 0 2px 2px;box-shadow:var(--sh-3);
}
.ml-jump-h{
  display:flex;align-items:center;justify-content:space-between;
  padding:12px 16px 8px;font-family:var(--serif);font-size:var(--t-md);
  color:var(--ink);letter-spacing:.06em;
}
.ml-jump-x{
  border:0;background:none;font-size:15px;line-height:1;color:var(--sub);
  cursor:pointer;padding:4px 6px;border-radius:2px;font-family:inherit;
}
.ml-jump-x:hover{color:var(--red)}
.ml-jump-s{
  display:block;width:calc(100% - 24px);margin:0 12px 6px;padding:6px 2px;
  font-size:var(--t-md);font-family:inherit;color:var(--ink);
  background:none;border:0;border-bottom:1px solid var(--line);border-radius:0;
}
.ml-jump-s:focus{outline:none;border-bottom-color:var(--red)}
.ml-jump-list{padding:2px 0 6px}
.ml-jump-i{
  display:flex;align-items:baseline;gap:10px;width:100%;padding:9px 16px;
  background:none;border:0;border-bottom:1px solid var(--line2);
  font-family:inherit;font-size:var(--t-md);color:var(--ink);
  text-align:left;cursor:pointer;
}
.ml-jump-i:last-child{border-bottom:0}
.ml-jump-i:hover{background:#f6efe1}
.ml-jump-i.cur{background:#f8ece8;color:var(--red);font-weight:600}
.ml-jump-n{
  flex:none;font-size:9.5px;color:var(--gold-ink);
  font-variant-numeric:tabular-nums;letter-spacing:.08em;
}
.ml-jump-i.cur .ml-jump-n{color:var(--red)}
.ml-jump-t{min-width:0}
.ml-jump-res{padding:0 16px 8px;max-height:38vh;overflow:auto}
.ml-jump-res[hidden]{display:none}
.ml-jump-ft{
  padding:8px 16px 10px;font-size:var(--t-xs);color:var(--faint);
  border-top:1px solid var(--line);
}

/* 节末导航：长文读到一节末尾，最想问的是「然后呢」 */
.ml-secnav{
  display:flex;align-items:center;gap:10px;flex-wrap:wrap;
  margin:28px 0 12px;padding-top:14px;
  border-top:1px solid var(--line2);font-size:var(--t-sm);
}
.ml-secnav-a{color:var(--red);text-decoration:none;line-height:1.6}
.ml-secnav-a:hover{text-decoration:underline}
.ml-secnav-p{flex:1 1 auto}
.ml-secnav-t{
  flex:none;color:var(--sub);font-size:var(--t-xs);
  border:1px solid var(--line);border-radius:2px;
  padding:1px 8px;text-decoration:none;
}
.ml-secnav-t:hover{background:#f6efe1;text-decoration:none}
.ml-secnav-n{flex:1 1 auto;text-align:right}

/* 跳转落点闪一下：滚完常常不知道落在哪 */
.ml-flash{animation:mlFlash 1.3s var(--ease)}
@keyframes mlFlash{0%{background:#f2e2b6}100%{background:transparent}}

.ml-totop{
  position:fixed;right:14px;bottom:18px;width:40px;height:40px;
  border-radius:2px;border:0;background:var(--red);color:#fff;
  font-family:var(--serif);font-size:17px;line-height:1;cursor:pointer;
  opacity:0;pointer-events:none;transition:opacity .2s;z-index:60;
  box-shadow:0 6px 18px rgba(156,42,36,.26);
}
.ml-totop.on{opacity:1;pointer-events:auto}

/* ---------- 窄屏 ---------- */
@media(max-width:900px){
  body{padding:0 16px 64px}
  .wrap{max-width:100%}
  .wrap>h1{font-size:34px}
  section{padding-top:42px}
  .persona{padding:32px 30px 26px}
  .persona .p-lead{font-size:25px}
  .grid2{grid-template-columns:1fr}
  .astro-wrap{gap:20px}
}
@media(max-width:720px){
  .toc-grid{grid-template-columns:1fr;gap:0}
  .headline{padding:26px 4px 22px}
  .headline .big{font-size:18px}
  .persona{padding:28px 20px 24px}
  .persona::before{inset:6px}
  .persona .p-lead{font-size:22px;line-height:1.8}
  .persona .p-v{font-size:var(--t-base)}
  .quick{padding:22px 18px}
  .quick::before{inset:6px}
  .quick-grid{grid-template-columns:1fr;gap:14px}
  .plain{padding-left:14px}
  .fbody{padding-left:0}
  /* 十二宫盘降两列：4 列时每格约 60px，星曜看不全 */
  .pan{grid-template-columns:repeat(2,1fr);grid-template-rows:auto;aspect-ratio:auto;gap:8px}
  .center{grid-column:1/3;grid-row:auto;padding:22px}
  .cell{padding:10px;font-size:var(--t-base);min-height:74px}
  .cell .gz2{font-size:var(--t-lg)}
  .cell .pos{font-size:var(--t-sm)}
  /* 迷你盘是「说人话」区的形状提示，窄屏也保持 4x4，别降成两列 */
  .pan.mini{grid-template-columns:repeat(4,1fr);grid-template-rows:repeat(4,1fr);aspect-ratio:1/1;gap:4px}
  .pan.mini .center{grid-column:2/4;grid-row:2/4;padding:8px}
  .pan.mini .cell{padding:5px 6px;font-size:var(--t-sm);min-height:0}
  .pan.mini .pos{font-size:9.5px}
  .pan.mini .stars{font-size:10.5px}
  /* 流年格：窄屏把大运名放到单独一行，十格就能占满宽度 */
  .life-row{grid-template-columns:repeat(10,1fr)}
  .life-lab{grid-column:1/-1;display:flex;justify-content:space-between;align-items:baseline}
  .life-lab em{display:inline}
  .dy-seg u{display:none}
  .dy-seg b{font-size:var(--t-sm)}
  .astro-wrap{justify-content:center}
  .astro-note{flex:1 1 100%}
  .ml-pgbar{height:34px}
  .ml-jump{top:34px}
  .ml-jump-in{width:calc(100% - 12px);max-height:76vh}
  .ml-jump-i{padding:11px 16px}
  .ml-totop{right:12px;bottom:14px;width:38px;height:38px}
  /* 结论预览独占一行（必须排在基础规则之后） */
  details.fold>summary{flex-wrap:wrap;row-gap:3px}
  details.fold>summary .cnt{order:1}
  details.fold>summary .fold-prev{
    order:2;flex-basis:100%;max-width:100%;margin-left:32px;
    text-align:left;padding-top:2px;white-space:normal;
  }
  .li{padding-left:14px}
  .xsx{padding-left:12px}
  .luckgrid{grid-template-columns:repeat(auto-fill,minmax(120px,1fr))}
}
@media(max-width:420px){
  .wrap>h1{font-size:27px;letter-spacing:.2em;text-indent:.2em}
  .wrap>h1::before{width:34px;height:34px;line-height:34px;font-size:20px;margin-bottom:16px}
  .persona .p-lead{font-size:20px}
  .tagline .tag{min-width:100%}
  .ln-seg i{display:none}
  .ln-seg b{font-size:var(--t-sm)}
  .life-lab{font-size:10px}
  .quick{padding:18px 14px}
}

/* ---------- 打印 ---------- */
@media print{
  body{background:#fff;padding:0;color:#000}
  .wrap>h1::before{box-shadow:none}
  section{padding-top:24px}
  section+section{border-top:1px solid #bbb}
  .persona,.quick,.y3{background:#fff;border:1px solid #999;box-shadow:none}
  .persona::before,.quick::before{display:none}
  details.fold{border-color:#ccc}
  details.fold>*:not(summary){animation:none}
  /* 打印/存 PDF 时不能只印半份：折叠块里的内容占了大半篇幅 */
  details.fold,details.ssx{break-inside:avoid-page}
  .fbody{padding-top:8px}
  /* 网页版的两个页签都要印出来，否则只印了当前那个 */
  .panel{display:block!important}
  .tabs,.toc-tools,.toc-results,.ml-totop,.ml-pgbar,.ml-jump,.ml-secnav{display:none!important}
  .astro{box-shadow:none;border:1px solid #ccc}
}
"""

# 页面级交互：吸顶进度条 + 返回顶部 + 目录跳转。
#
# 这份代码在三个地方用同一份：CLI 导出的命盘网页、网页版（构建时注入）、
# 网页版导出的离线命盘文件。放一处是为了避免三份副本改一处漏两处 ——
# 之前 CSS 就是这么散过（app.html 一份、oracle.py 一份）。
PAGE_JS = r"""(function () {
  if (window.__mlPageReady) return;
  window.__mlPageReady = 1;

  var FLASH_MS = 1300;

  // ---------- 吸顶条：进度 + 当前小节 + 目录按钮 ----------
  // 以前这条只能看不能点：读到第 15 屏想换小节，得先滚回页首。
  var bar = document.createElement("div");
  bar.className = "ml-pgbar";
  bar.innerHTML = '<div class="ml-pgbar-f"></div>';
  var barBtn = document.createElement("button");
  barBtn.type = "button";
  barBtn.className = "ml-pgbar-btn";
  barBtn.setAttribute("aria-expanded", "false");
  barBtn.setAttribute("aria-controls", "ml-jump");
  barBtn.innerHTML = '<span class="ml-pgbar-t"></span>' +
                     '<span class="ml-pgbar-c">目录</span>';
  var fill = bar.firstChild;
  var label = barBtn.firstChild;
  bar.appendChild(barBtn);

  var top = document.createElement("button");
  top.type = "button";
  top.className = "ml-totop";
  top.setAttribute("aria-label", "回到顶部");
  top.textContent = "↑";

  // ---------- 跳转面板 ----------
  var jump = document.createElement("div");
  jump.className = "ml-jump";
  jump.id = "ml-jump";
  jump.hidden = true;
  jump.innerHTML = '<div class="ml-jump-in" role="dialog" aria-label="跳到小节">' +
    '<div class="ml-jump-h"><b>跳到…</b>' +
    '<button type="button" class="ml-jump-x" aria-label="关闭">✕</button></div>' +
    '<input class="ml-jump-s" type="search" placeholder="找一句话…" ' +
    'aria-label="在本页查找">' +
    '<div class="ml-jump-list"></div>' +
    '<div class="ml-jump-res" hidden></div>' +
    '<div class="ml-jump-ft">点一节跳过去 · Esc 关闭</div>' +
    '</div>';

  // 顺序 = Tab 顺序：面板紧跟吸顶条，点开目录后按 Tab 直接进面板
  document.body.appendChild(bar);
  document.body.appendChild(jump);
  document.body.appendChild(top);

  var jumpInner = jump.querySelector(".ml-jump-in");
  var jumpList = jump.querySelector(".ml-jump-list");
  var jumpRes = jump.querySelector(".ml-jump-res");
  var jumpInput = jump.querySelector(".ml-jump-s");

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  // ---------- 小节列表 ----------
  // secs：全部小节（含另一个页签里的）—— 面板要能跳过去
  // vis ：当前可见的下标 —— 「现在读到哪一节」只在这堆里找
  var secs = [];
  var vis = [];

  function collect() {
    secs = [];
    vis = [];
    var hs = document.querySelectorAll("h2[data-t]");
    for (var i = 0; i < hs.length; i++) {
      secs.push(hs[i]);
      if (hs[i].offsetParent !== null) vis.push(i);
    }
    buildSecNav();
  }

  function currentIdx() {
    var idx = -1;
    for (var k = 0; k < vis.length; k++) {
      if (secs[vis[k]].getBoundingClientRect().top <= 90) idx = vis[k];
    }
    return idx;
  }

  function update() {
    var y = window.pageYOffset || document.documentElement.scrollTop || 0;
    var h = document.documentElement.scrollHeight - window.innerHeight;
    var p = h > 0 ? Math.max(0, Math.min(1, y / h)) : 0;
    fill.style.width = (p * 100).toFixed(2) + "%";
    var i = currentIdx();
    var c = i >= 0 ? secs[i].getAttribute("data-t") : "";
    if (label.textContent !== c) label.textContent = c;
    if (y > 360) {
      bar.classList.add("on");
      top.classList.add("on");
    } else {
      bar.classList.remove("on");
      top.classList.remove("on");
    }
  }

  // 刷新进度条。用时间节流而不是 requestAnimationFrame：
  // 窗口不可见时 rAF 不触发，进度条会永远停在空白（实测踩过）。
  var lastRun = 0, pending = false;
  function onScroll() {
    var now = (window.performance && performance.now) ? performance.now()
                                                        : Date.now();
    var wait = 60 - (now - lastRun);
    if (wait <= 0) {
      lastRun = now;
      update();
      return;
    }
    if (pending) return;
    pending = true;
    setTimeout(function () {
      pending = false;
      lastRun = (window.performance && performance.now) ? performance.now()
                                                        : Date.now();
      update();
    }, wait);
  }

  // 瞬时跳转，不用动画。
  // 实测：窗口不可见时 requestAnimationFrame 不触发，原生 smooth 滚动
  // 也依赖合成器、同样不动 —— 症状是「点了目录没反应」。
  // window.scrollTo 立即生效，任何环境都可靠。
  function scrollToY(targetY) {
    var y = Math.max(0, Math.round(targetY));
    if (window.scrollTo) window.scrollTo(0, y);
    // 主动刷一次：程序化滚动不保证有 scroll 事件（窗口不可见时就没有），
    // 不刷的话吸顶条会停在上一节的名字。
    onScroll();
  }

  // 落点要停在吸顶条下面，否则标题正好被压住
  function barH() { return (bar.offsetHeight || 26) + 8; }

  function scrollToEl(el) {
    var r = el.getBoundingClientRect();
    var y = r.top + (window.pageYOffset || document.documentElement.scrollTop || 0)
      - barH();
    scrollToY(y);
  }

  // 跳过去以后闪一下：长文里滚完常常不知道落在哪
  function flash(el) {
    if (!el || !el.classList) return;
    el.classList.remove("ml-flash");
    void el.offsetWidth;
    el.classList.add("ml-flash");
    setTimeout(function () { el.classList.remove("ml-flash"); }, FLASH_MS);
  }

  function goTo(id) {
    var el = document.getElementById(id);
    if (!el) return;
    closeJump();
    // 目标可能落在另一个页签里（网页版「专业数据」是单独一页签），
    // 先广播一个事件让页面切过去，再滚动。
    try {
      document.dispatchEvent(new CustomEvent("mingli:goto",
        { detail: { id: id } }));
    } catch (err) { /* 老浏览器没有 CustomEvent，忽略 */ }
    setTimeout(function () {
      scrollToEl(el);
      flash(el);
    }, 60);
  }

  // 页内锚点如果落在折叠块里（比如紫微盘格子的 #pl-N），
  // 浏览器原生跳转只会滚到收起的标题上，点完还是看不到内容。
  // 这里统一：先展开祖先 details，再走 goTo（跨页签也能接上）。
  document.addEventListener("click", function (ev) {
    var a = (ev.target && ev.target.closest)
      ? ev.target.closest('a[href^="#"]') : null;
    if (!a) return;
    var id = (a.getAttribute("href") || "").slice(1);
    if (!id) return;
    var el = document.getElementById(id);
    if (!el) return;
    var p = el.parentElement, opened = false;
    while (p && p !== document.body) {
      if (p.tagName === "DETAILS" && !p.open) { p.open = true; opened = true; }
      p = p.parentElement;
    }
    if (!opened) return;   // 不在折叠块里：交给浏览器原生跳转
    ev.preventDefault();
    goTo(id);
  });

  top.addEventListener("click", function () { scrollToY(0); });

  // ---------- 面板开关 ----------
  function pad2(n) { return n < 10 ? "0" + n : "" + n; }

  function fillList() {
    var cur = currentIdx();
    var html = "";
    for (var i = 0; i < secs.length; i++) {
      var s = secs[i];
      var on = (i === cur);
      html += '<button type="button" class="ml-jump-i' + (on ? " cur" : "") +
        '" data-ml="jump" data-id="' + esc(s.id) + '"' +
        (on ? ' aria-current="true"' : "") + ">" +
        '<span class="ml-jump-n">' + pad2(i + 1) + "</span>" +
        '<span class="ml-jump-t">' + esc(s.getAttribute("data-t")) +
        "</span></button>";
    }
    jumpList.innerHTML = html;
    jumpRes.hidden = true;
    jumpRes.innerHTML = "";
    jumpInput.value = "";
    clearFind();
    findQuery = "";
    hitIdx = -1;
  }

  function openJump() {
    fillList();
    jump.hidden = false;
    barBtn.setAttribute("aria-expanded", "true");
    onScroll();
  }

  function closeJump() {
    if (jump.hidden) return;
    jump.hidden = true;
    barBtn.setAttribute("aria-expanded", "false");
  }

  barBtn.addEventListener("click", function () {
    if (jump.hidden) openJump(); else closeJump();
  });

  jump.querySelector(".ml-jump-x").addEventListener("click", function (e) {
    e.preventDefault();
    closeJump();
    barBtn.focus();
  });

  // 点面板外面关掉（点面板里不算）
  document.addEventListener("mousedown", function (e) {
    if (jump.hidden) return;
    var t = e.target;
    if (jumpInner.contains(t) || bar.contains(t)) return;
    closeJump();
  });

  // ---------- 节末导航：上一节 / 目录 / 下一节 ----------
  // 长文读到一节末尾时，最想问的是「然后呢」。
  // 用当前可见的小节列表现算，所以页签切换、数据不全时都不会指向空处。
  var secNavSig = "";

  function mkNav(i) {
    var nav = document.createElement("nav");
    nav.className = "ml-secnav";
    nav.setAttribute("aria-label", "小节导航");
    var html = "";
    if (i > 0) {
      html += '<a class="ml-secnav-a ml-secnav-p" href="#' + esc(secs[i - 1].id) +
        '">← ' + esc(secs[i - 1].getAttribute("data-t")) + "</a>";
    }
    html += '<a class="ml-secnav-a ml-secnav-t" href="#s-toc">目录</a>';
    if (i + 1 < secs.length) {
      html += '<a class="ml-secnav-a ml-secnav-n" href="#' + esc(secs[i + 1].id) +
        '">' + esc(secs[i + 1].getAttribute("data-t")) + " →</a>";
    }
    nav.innerHTML = html;
    return nav;
  }

  function buildSecNav() {
    // 签名要带可见性：切页签时 id 不变，但该重建（隐藏的小节不插导航）
    var sig = "";
    for (var i = 0; i < secs.length; i++) {
      sig += secs[i].id + (secs[i].offsetParent !== null ? "*" : "-") + "|";
    }
    if (sig === secNavSig) return;
    secNavSig = sig;
    var olds = document.querySelectorAll(".ml-secnav");
    for (var k = 0; k < olds.length; k++) {
      if (olds[k].parentNode) olds[k].parentNode.removeChild(olds[k]);
    }
    // 按容器分组：同一个小节容器（section / 面板）里的连续小节算一组。
    // 只看可见的 —— 往隐藏页签里插导航是白插（看不见）。
    var groups = [];
    var lastBox = null;
    for (var k = 0; k < vis.length; k++) {
      var j = vis[k];
      var box = secs[j].parentNode;
      if (box !== lastBox) {
        groups.push({ box: box, items: [] });
        lastBox = box;
      }
      groups[groups.length - 1].items.push(j);
    }
    for (var g = 0; g < groups.length; g++) {
      var items = groups[g].items;
      for (var m = 0; m < items.length; m++) {
        var idx = items[m];
        var nav = mkNav(idx);
        if (m + 1 < items.length) {
          groups[g].box.insertBefore(nav, secs[items[m + 1]]);
        } else {
          groups[g].box.appendChild(nav);
        }
      }
    }
  }

  // ---------- 全部展开 / 全部收起 ----------
  function setAll(open) {
    var ds = document.querySelectorAll("details");
    for (var i = 0; i < ds.length; i++) {
      if (ds[i].open !== open) ds[i].open = open;
    }
    onScroll();
  }

  // ---------- 打印前展开全部 ----------
  // 折叠块里是大运、流年、神煞、十二宫、四化……占了大半篇幅。
  // 折叠着打印出来就是半份命盘。CSS 没法真的打开 details，只能在
  // 打印前用脚本打开，打完还原。
  var printOpened = null;
  window.addEventListener("beforeprint", function () {
    if (printOpened) return;
    printOpened = [];
    var ds = document.querySelectorAll("details");
    for (var i = 0; i < ds.length; i++) {
      if (!ds[i].open) { printOpened.push(ds[i]); ds[i].open = true; }
    }
  });
  window.addEventListener("afterprint", function () {
    if (!printOpened) return;
    for (var i = 0; i < printOpened.length; i++) printOpened[i].open = false;
    printOpened = null;
  });

  // ---------- 本页查找 ----------
  // 不用 innerHTML 高亮：改 innerHTML 会重建节点，details 的展开状态
  // 全丢（用户刚点开的折叠块会全合上）。改用 CSS Custom Highlight API，
  // 不动 DOM；浏览器不支持时退化成「只列命中处」。
  var results = [];
  var findRoot = document.querySelector("main") || document.body;
  var findQuery = "";
  var findBox = null;
  var hitIdx = -1;

  function clearFind() {
    results = [];
    try {
      if (window.CSS && CSS.highlights) CSS.highlights.delete("ml-find");
    } catch (e) { /* 不支持就算了 */ }
  }

  function snippetFor(node, q) {
    var block = node.parentElement;
    while (block && block !== findRoot) {
      var tag = block.tagName;
      if (tag === "P" || tag === "LI" || tag === "DIV" || tag === "TD") break;
      block = block.parentElement;
    }
    var txt = ((block ? block.textContent : node.nodeValue) || "")
      .replace(/\s+/g, " ").trim();
    var at = txt.indexOf(q);
    if (at < 0) at = 0;
    var from = Math.max(0, at - 14);
    var to = Math.min(txt.length, at + q.length + 22);
    return (from > 0 ? "…" : "") + txt.slice(from, to) +
      (to < txt.length ? "…" : "");
  }

  function renderFind(q) {
    var box = findBox;
    if (!box) return;
    if (!q) { box.hidden = true; box.innerHTML = ""; return; }
    if (!results.length) {
      box.hidden = false;
      box.innerHTML = '<div class="r-h">没找到「' + esc(q) + "」</div>";
      return;
    }
    var head = "找到 " + results.length + " 处";
    if (hitIdx >= 0) head = "第 " + (hitIdx + 1) + " / " + results.length + " 处";
    var html = '<div class="r-h">' + head + "：</div>";
    for (var i = 0; i < results.length && i < 30; i++) {
      html += '<button type="button" class="r-i" data-find="' + i + '">' +
        results[i].snip + "</button>";
    }
    if (results.length > 30) {
      html += '<div class="r-h">还有 ' + (results.length - 30) + " 处未列出</div>";
    }
    box.hidden = false;
    box.innerHTML = html;
  }

  function doFind(q, box) {
    clearFind();
    findBox = box || findBox;
    q = (q || "").trim();
    findQuery = q;
    hitIdx = -1;
    if (q.length < 2) { renderFind(""); return; }
    var walker = document.createTreeWalker(findRoot, NodeFilter.SHOW_TEXT);
    var ranges = [];
    var node;
    while ((node = walker.nextNode())) {
      if (!node.nodeValue || node.nodeValue.indexOf(q) < 0) continue;
      var par = node.parentElement;
      if (!par) continue;
      var tag = par.tagName;
      if (tag === "SCRIPT" || tag === "STYLE") continue;
      var text = node.nodeValue;
      var at = text.indexOf(q);
      while (at >= 0) {
        var r = document.createRange();
        try {
          r.setStart(node, at);
          r.setEnd(node, at + q.length);
        } catch (e) { break; }
        ranges.push(r);
        results.push({ range: r, node: node, snip: snippetFor(node, q) });
        at = text.indexOf(q, at + q.length);
        if (results.length >= 200) break;
      }
      if (results.length >= 200) break;
    }
    try {
      if (window.CSS && CSS.highlights && ranges.length) {
        // 注意：Highlight 是 class，不能 .apply（会抛 not a constructor）。
        // 必须展开传参 —— 这里错了高亮会一直静默失效。
        CSS.highlights.set("ml-find", new Highlight(...ranges));
      }
    } catch (e) { /* 不支持 Custom Highlight 就只列命中处 */ }
    renderFind(q);
  }

  function jumpHit(i) {
    var r = results[i];
    if (!r) return;
    // 命中的内容在折叠块里就先把块打开，否则滚过去也是空的
    var p = r.node.parentElement;
    while (p && p !== document.body) {
      if (p.tagName === "DETAILS") p.open = true;
      p = p.parentElement;
    }
    setTimeout(function () {
      var el = r.range.startContainer.parentElement;
      if (el) { scrollToEl(el); flash(el); }
    }, 30);
  }

  // 回车 / 边打边找：一条一条往下走，跟浏览器自带查找一个手感
  function nextHit() {
    if (!results.length) return;
    hitIdx = (hitIdx + 1) % results.length;
    renderFind(findQuery);
    jumpHit(hitIdx);
  }

  function wireSearch(input, box) {
    if (!input || !box) return;
    var timer = null;
    input.addEventListener("input", function () {
      if (timer) clearTimeout(timer);
      timer = setTimeout(function () {
        timer = null;
        doFind(input.value, box);
      }, 180);
    });
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter") {
        e.preventDefault();
        if (timer) { clearTimeout(timer); timer = null; }
        if (findQuery !== input.value.trim() || findBox !== box) {
          doFind(input.value, box);
        } else {
          nextHit();
        }
      } else if (e.key === "Escape") {
        input.value = "";
        doFind("", box);
      }
    });
  }

  wireSearch(document.querySelector(".toc-search"),
             document.querySelector(".toc-results"));
  wireSearch(jumpInput, jumpRes);

  // ---------- 快捷键 ----------
  // 「/」直接开查找：长文里手不用离开键盘
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && !jump.hidden) {
      closeJump();
      barBtn.focus();
      return;
    }
    var tag = (e.target && e.target.tagName) || "";
    if (e.key === "/" && !/^(INPUT|TEXTAREA|SELECT)$/.test(tag)) {
      e.preventDefault();
      if (jump.hidden) openJump();
      setTimeout(function () { jumpInput.focus(); }, 20);
    }
  });

  // ---------- 点击总入口 ----------
  document.addEventListener("click", function (e) {
    var t = e.target;
    if (!t || !t.closest) return;

    var jitem = t.closest("[data-ml='jump']");
    if (jitem) {
      e.preventDefault();
      goTo(jitem.getAttribute("data-id"));
      return;
    }
    var btn = t.closest("[data-toc]");
    if (btn) {
      e.preventDefault();
      setAll(btn.getAttribute("data-toc") === "expand");
      return;
    }
    var hit = t.closest("[data-find]");
    if (hit) {
      e.preventDefault();
      var idx = Number(hit.getAttribute("data-find"));
      if (!results[idx]) return;
      closeJump();
      hitIdx = idx;
      renderFind(findQuery);
      jumpHit(idx);
      return;
    }
    var a = t.closest("a[href^='#']");
    if (!a) return;
    var id = a.getAttribute("href").slice(1);
    if (!id || !document.getElementById(id)) return;
    e.preventDefault();
    goTo(id);
  });

  window.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", function () { collect(); onScroll(); });
  document.addEventListener("mingli:refresh", function () {
    collect();
    onScroll();
  });

  collect();
  onScroll();
})();
"""

WX_COLOR = {"木": "#5b8c5a", "火": "#c0504d", "土": "#b08d4a", "金": "#8a8f98", "水": "#4a6fa5"}

# 占星四元素的颜色，与五行区分开
EL_COLOR = {"火": "#c0504d", "土": "#b08d4a", "风": "#4a6fa5", "水": "#3f7a52"}


_MAXP = 34


def _split_sentences(text):
    """按中文句末标点把一段切成多段。

    为什么在渲染层切
    ----------------
    量化发现页面上 11 段超过 60 字（最长 105）。中文一段超过 30 字
    就开始难读 —— 读者容易串行，然后就跳读。而文案里大量是
    「三句话写在一个字符串里」。回去改每条文案不解决根本问题，
    所以在渲染层按句切。

    切法
    ----
    - 只切句末标点（。！？），不切句内停顿（逗号顿号）——
      句内切开反而更碎
    - 少于两句就不切；本来不长的段不要动
    - 短于 8 字的句子并到前一句，避免出现「孤句」
    - 标签安全：切完补未闭合的行内标签，否则 <b> 被切成两半
    """
    import re as _re
    if not text:
        return [text]
    parts = [p for p in _re.split(r"(?<=[。！？])", text) if p.strip()]
    if len(parts) < 2:
        return [text]
    merged = []
    for p in parts:
        plain = _re.sub(r"<[^>]+>", "", p)
        if merged and len(plain) < 8:
            prev = _re.sub(r"<[^>]+>", "", merged[-1])
            if len(prev) + len(plain) <= _MAXP * 2:
                merged[-1] += p
                continue
        merged.append(p)
    out = []
    for p in merged:
        opens = _re.findall(r"<(b|em|i|strong|span|a)\b[^>]*>", p)
        clo = _re.findall(r"</([a-z]+)>", p)
        need = list(opens)
        for c in clo:
            if c in need:
                need.remove(c)
        for tag in reversed([x for x in need
                             if x in ("b", "em", "i", "strong",
                                      "span", "a")]):
            p += "</%s>" % tag
        out.append(p)
    return out


def _p(text, cls="li"):
    """把一段文本渲染成一个或多个 <p>。排版的关键一步。"""
    segs = _split_sentences(text)
    if len(segs) <= 1:
        return '<p class="%s">%s</p>' % (cls, text)
    return "".join('<p class="%s">%s</p>' % (cls, s) for s in segs)


def _h(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _yr(v):
    """虚岁 -> 整数显示。

    起运岁数带小数（7.26 岁起运 -> 第一步从 7.3 虚岁开始），
    但给人看的大运区间写「7.3–17.3 岁」既啰嗦又没信息量 ——
    虚岁本来就是整数计的。取整与 JS 侧保持一致（都用 Math.floor），
    否则两边 HTML 会差一位小数，逐例比对会逐字报出来。
    """
    import math
    try:
        return int(math.floor(float(v)))
    except (TypeError, ValueError):
        return "?"


def render_bazi(r):
    i = r["输入"]
    p = []
    p.append('<section><h2 id="s-bazi-pro" data-t="四柱八字">四柱八字</h2>')
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
    # 五行：环形图 + 图例（替代原来的小 bar）
    p.append("<h2 style='margin-top:20px'>五行力量</h2>")
    p.append('<div class="donut-wrap">')
    p.append(M_plain.wuxing_donut(r["五行统计"]))
    p.append('<div class="donut-legend">')
    for w, v in r["五行统计"].items():
        p.append('<div><i style="background:%s"></i><b>%s</b>%.1f%%</div>'
                 % (WX_COLOR[w], w, v))
    p.append("</div></div>")
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


def ziwei_pan(r, mini=False):
    """紫微 4x4 盘。mini=True 用在说人话区：只留宫名和主星，格子小一点。

    格子链接到 #pl-N。那个 id 是按「十二宫详批」的列表顺序编的
    （命宫、兄弟、夫妻……），不是按盘面位置编的 ——
    以前两边各用各的序号，结果点「迁移」跳到「命宫」，十二个全错位。
    现在统一按宫名查 id。
    """
    by_zhi = {x["地支"]: x for x in r["十二宫"]}
    idx_of = {x["宫名"]: i for i, x in enumerate(r["十二宫"])}
    p = ['<div class="pan%s">' % (" mini" if mini else "")]
    for row in range(4):
        for col in range(4):
            if row in (1, 2) and col in (1, 2):
                continue
            pal = by_zhi.get(PAN_LAYOUT[(row, col)])
            if not pal:
                p.append("<div></div>")
                continue
            cls = "cell"
            if pal["是否命宫"]:
                cls += " ming"
            if pal["是否身宫"]:
                cls += " shen"
            tag = []
            if pal["是否命宫"]:
                tag.append("命")
            if pal["是否身宫"]:
                tag.append("身")
            _meaning = M_plain.PALACE_MEANING.get(pal["宫名"], "")
            _tip = ("%s：%s" % (pal["宫名"], _meaning)) if _meaning else pal["宫名"]
            if mini:
                mains = [s for s in pal["星曜"]
                         if s.split("·")[0] in M_ziwei.STAR_BRIEF][:2]
                stars = " ".join('<span class="star main">%s</span>' % _h(s)
                                 for s in mains)
                body = ('<div class="pos"><span>%s</span><span>%s</span></div>'
                        '<div class="stars">%s</div>'
                        % (_h(pal["宫名"]), "".join(tag),
                           stars or '<span class="ss">空宫</span>'))
            else:
                stars = []
                for s in pal["星曜"]:
                    base = s.split("·")[0]
                    k = ("star main" if base in M_ziwei.STAR_BRIEF
                         else ("star hua" if "化" in s else "star aux"))
                    stars.append('<span class="%s">%s</span>' % (k, _h(s)))
                body = ('<div class="pos"><span>%s</span><span>%s</span></div>'
                        '<div class="gz2"><span class="gan">%s</span>'
                        '<span class="zhi">%s</span></div>'
                        '<div class="stars">%s</div>'
                        % (_h(pal["宫名"]), "".join(tag),
                           pal["天干"], pal["地支"],
                           " ".join(stars) if stars
                           else '<span class="ss">空宫</span>'))
            p.append('<a class="%s" href="#pl-%d" title="%s">%s</a>'
                     % (cls, idx_of.get(pal["宫名"], 0), _h(_tip), body))
    if mini:
        p.append('<div class="center"><div class="t">你的盘</div>'
                 '<div class="ss">命宫 %s · 身宫 %s</div></div>'
                 % (_h(r["命宫"]["地支"]), _h(r["身宫"]["地支"])))
    else:
        p.append('<div class="center"><div class="t">命盘</div>'
                 '<div>紫微 %s</div><div>天府 %s</div><div>%s</div>'
                 '<div class="ss">大限%s · 起运%d岁</div></div>'
                 % (_h(r["紫微星"]), _h(r["天府星"]), _h(r["五行局"]),
                    _h(r["大限"]["顺逆"]), r["大限"]["起运虚岁"]))
    p.append("</div>")
    return "".join(p)


def render_ziwei(r):
    i = r["输入"]
    p = ['<section><h2 id="s-ziwei-pro" data-t="紫微斗数">紫微斗数</h2>']
    p.append('<div class="info"><span>农历 <b>%s</b></span><span>时辰 <b>%s</b></span>'
             '<span>年干支 <b>%s</b></span><span>五行局 <b>%s</b></span>'
             '<span>命宫 <b>%s%s</b></span><span>身宫 <b>%s%s</b></span></div>'
             % (_h(i["农历"]), _h(i["时辰"]), _h(i["年干支"]), _h(r["五行局"]),
                r["命宫"]["天干"], r["命宫"]["地支"], r["身宫"]["天干"], r["身宫"]["地支"]))
    h = r["四化"]
    p.append('<div class="info"><span>四化（%s干）：禄 <b>%s</b> · 权 <b>%s</b> · 科 <b>%s</b> · 忌 <b>%s</b></span></div>'
             % (_h(h["年干"]), _h(h["化禄"]), _h(h["化权"]), _h(h["化科"]), _h(h["化忌"])))
    # 4x4 盘
    p.append(ziwei_pan(r))
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
    p = ['<section><h2 id="s-astro-pro" data-t="占星盘">西洋占星本命盘</h2>']
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
    p.append('<div class="astro-wrap">')
    p.append(M_plain.astro_chart(r))
    p.append('<div class="astro-note"><p class="sub2">外圈是黄道十二宫，'
             '行星按真实黄经落在盘上，两点之间的线是相位。'
             '实线是和谐相，细线是张力相。</p></div></div>')
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


def _tag(cls, body):
    """按 class 拼 <p>。class 为空时输出无 class 的 <p>。

    必须与 render.js 的 _pTag 一致：空 class 时**不写 class 属性**。
    写成 class="" 会让两侧 HTML 差几个字符，逐例比对全红。
    """
    return ('<p class="%s">%s</p>' % (cls, body)) if cls \
        else ("<p>%s</p>" % body)


def _despacify(html, max_len=36):
    """把 HTML 里过长的正文 <p> 按中文句末标点拆成多个 <p>。

    只动 <p class="li"> 与 <p class="sub2">（纯文本正文段）。
    含块级标签（<div>/<ul>/<table>）的段不碰 ——
    切开会破坏结构。

    阈值 36：中文一行 15~25 字，36 字以上就该拆。
    """
    import re as _re

    def repl(cls, body):
        # 有块级标签就不碰
        if _re.search(r"<(div|ul|ol|table|tr|td|th|h\d|section|details)\b",
                      body):
            return _tag(cls, body)
        plain = _re.sub(r"<[^>]+>", "", body)
        if len(plain) <= max_len:
            return _tag(cls, body)
        parts = [p for p in _re.split(r"(?<=[。！？])", body) if p.strip()]
        if len(parts) < 2:
            return _tag(cls, body)
        # 短句合并，避免孤句
        merged = []
        for p in parts:
            pl = _re.sub(r"<[^>]+>", "", p)
            if merged and len(pl) < 8 and len(
                    _re.sub(r"<[^>]+>", "", merged[-1])) + len(pl) <= max_len * 2:
                merged[-1] += p
                continue
            merged.append(p)
        out = []
        for p in merged:
            opens = _re.findall(r"<(b|em|i|strong|span|a)\b[^>]*>", p)
            clo = _re.findall(r"</([a-z]+)>", p)
            need = list(opens)
            for c in clo:
                if c in need:
                    need.remove(c)
            for tag in reversed([x for x in need if x in
                                 ("b", "em", "i", "strong", "span", "a")]):
                p += "</%s>" % tag
            out.append(_tag(cls, p))
        return "".join(out)

    out_html = _re.sub(r'<p(?: class="(li|sub2)")?>(.*?)</p>',
                       lambda m: repl(m.group(1) or "", m.group(2)),
                       html, flags=_re.S)
    # persona 的 .p-v 是 <div>，上面那条正则不碰它 ——
    # 于是每个 persona 块是五六句话挤成一段，而它是读者第一眼看的门面。
    out_html = _re.sub(r'<div class="p-v">(.*?)</div>',
                       lambda m: repl("p-v", m.group(1)),
                       out_html, flags=_re.S)
    return out_html


def _prev(text):
    """折叠标题右侧的「结论预览」。

    只放可核对的事实（哪一步、哪个宫、几个），不放判断句 ——
    判断句在正文里已经说过了，重复一遍反而稀释。
    """
    if not text:
        return ""
    # title 一起带上：预览太长会被省略号截断，悬停仍要看得到全文
    return '<span class="fold-prev" title="%s">%s</span>' % (_h(text), _h(text))


def render_plain(data):
    """白话解读区：先给结论，再给依据，全部用日常语言。"""
    P = ['<section><h2 id="s-plain" data-t="先说人话">先说人话</h2>',
         '<div class="secnote">这一段不用懂任何术语，看完就知道自己大概是什么样的人。'
         '想研究细节，往下翻「专业排盘数据」。</div>',
         "@@QUICK@@"]
    # 下面要用到各体系的白话结果，但它们在各自的 if 块里才赋值。
    # 这里先占位，块没跑到就是 None（对应那一套体系没数据）。
    b = z = a = None

    # ---------- 个性版本：总览，放最前面 ----------
    # 它必须是这份解读的「门面」—— 一段连贯的人，而不是 15 个小块。
    # 放在三段之后读起来就变成「正文读完了才给总结」。
    pe = M_plain.persona_plain(data.get("八字"), data.get("紫微"),
                               data.get("占星"))
    if pe["块"]:
        P.append('<div class="persona">')
        P.append('<div class="p-eyebrow">命 盘 印 象</div>')
        lead = pe["块"][0]["文"]
        P.append('<p class="p-lead">%s</p>' % _h(lead))
        rest = pe["块"][1:]
        if rest:
            # 默认展开：这一块是「结论」本身，不是细节。
            # 折叠起来的话，读者看到的第一眼就只有一句「像一把好刀」，
            # 而内核、运转、关系这些真正在回答「我是什么人」的内容全在折叠里。
            P.append("<details class=\"fold\" open><summary>展开看：内核 / 运转"
                     " / 关系 / 独处 / 团队 / 压力"
                     "<span class=\"cnt\">%d 个角度</span></summary>" % len(rest))
            for r in rest:
                P.append('<div class="p-block"><div class="p-k">%s · %s</div>'
                         '<div class="p-v">%s</div>'
                         '<div class="p-src">%s</div></div>'
                         % (_h(r["块"]), _h(r["问"]), _h(r["文"]),
                            _h("来自 " + " + ".join(
                                "%s（%s）" % (s[0], s[1]) for s in r["源"]))))
            P.append("</details>")
        P.append('<p class="p-note">%s</p>' % _h(pe["提醒"]))
        P.append("</div>")

    if "八字" in data:
        b = M_plain.bazi_plain(data["八字"])
        P.append('<h2 id="s-bazi" data-t="八字 · 性格天赋">八字 · 看你的性格和天赋</h2>')
        P.append('<div class="sec-lead">这一节讲你是什么样的人、怎么做事、'
                 '力气往哪儿使。</div>')
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
        # 环图放在「能量分布」下面：先读一句结论，再看比例。
        _wx = (data.get("八字") or {}).get("五行统计") or {}
        if _wx:
            P.append('<div class="plain"><h3>五行的配比</h3>'
                     '<p class="sub2">这不是好坏，是配比：哪一块多、哪一块少。'
                     '环图就是你的比例。</p><div class="donut-wrap">%s'
                     '<div class="donut-legend">'
                     % M_plain.wuxing_donut(_wx))
            for _w, _v in _wx.items():
                P.append('<div><i style="background:%s"></i><b>%s</b>%.1f%%</div>'
                         % (WX_COLOR[_w], _w, _v))
            P.append("</div></div></div>")
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
            # 方位图：把「有利方位」那句文字变成一张图。
            P.append('<div class="plain"><h3>你的方位图</h3>'
                     '<p class="sub2">填色的是你的喜用方位；四个正方向 + 中间（本地），'
                     '和上面的「有利方位」是同一套。</p>%s</div>'
                     % M_plain.fangwei_compass(b["能量分布"]["喜用"]))
        if b["当前阶段"]:
            P.append('<div class="plain"><h3>你现在这段时期</h3>'
                     '<p>当前走在「<span class="k">%s</span>」大运（%s），主题是<span class="k">%s</span>。</p>'
                     '下面这条线是你一生的十步大运，现在的位置标出来了。</p></div>'
                     % (_h(b["当前阶段"]["干支"]), _h(b["当前阶段"]["十神"]), _h(b["当前阶段"]["主题"])))
        # 大运时间轴：把十步画成一条线，标出「现在」在哪。
        # 注意它**不在** `if b["当前阶段"]` 里面：
        # 「当前阶段」在大运还没起（生年较晚或起运未到）时是 None，
        # 那时整块会被跳过 —— 但时间轴照样该画，
        # 因为它讲的是十步的分布，不是「现在在哪一步」。
        # （1900/2100 两个边界盘就是这种情况，两侧都为空。）
        # 大运时间轴：把十步画成一条线，标出「现在」在哪。
        # 当前虚岁算法：本步起始公历 <= 今年 < 本步 + 10 年即落在这一步，
        # 取该步的起始虚岁作为标记位置（不必精确到年，标出区间就够）。
        _bz = data.get("八字") or {}
        _dz = _bz.get("大运") or {}
        _cur_xs = None
        if _dz.get("列表"):
            try:
                _ny = int(_bz.get("当前时间") or 2026)
            except (TypeError, ValueError):
                _ny = 2026
            for _it in _dz["列表"]:
                _y0 = _it.get("起始公历") or 0
                if _y0 and _y0 <= _ny < _y0 + 10:
                    _cur_xs = _it.get("起始虚岁")
                    break
        _tl = M_plain.dayun_timeline(_dz, cur_xs=_cur_xs)
        if _tl:
            P.append(_tl)
            # 一生流年格：十步大运 × 十年压成一张图。
            # 只标「天干五行是不是喜用」，和「未来三年」同一个口径。
            try:
                _ny = int(_bz.get("当前时间") or 2026)
            except (TypeError, ValueError):
                _ny = 2026
            _lg = M_plain.life_grid(_dz, b["能量分布"]["喜用"], _ny)
            if _lg:
                P.append('<div class="plain"><h3>一生流年一览</h3>'
                         '<p class="sub2">横着是十年一步的大运，每格一年。'
                         '深色是助力年 —— 这一年的天干五行是你的喜用；'
                         '圈出来的是今年。</p>%s</div>' % _lg)

        # ---- 1.10.0：未来适合方位与推荐城市 ----
        # 紧跟开运指南之后（两者都是「未来往哪走」），默认折叠。
        _lp = M_plain.lucky_places(
            b["能量分布"].get("喜用") or [],
            (data.get("八字") or {}).get("输入", {}).get("出生地"))
        if _lp["方位"]:
            P.append('<details class="fold"><summary>未来适合方位与推荐城市'
                     '%s<span class="cnt">%d 个方位</span></summary>'
                     '<div class="fbody">'
                     % (_prev("%s · %d 城"
                              % ("、".join("宜" + d["方位"] for d in _lp["方位"]),
                                 len(_lp["城市"]))),
                        len(_lp["方位"])))
            P.append('<p class="sub2">%s</p>' % _h(_lp["说明"]))
            for d in _lp["方位"]:
                P.append('<div class="xsx"><p class="xsx-h">'
                         '<b>宜向%s</b>（喜用 %s）</p>'
                         '<p class="li">%s</p>'
                         '<p class="sub2">%s</p></div>'
                         % (_h(d["方位"]), _h(d["五行"]),
                            _h(d["地理"]), _h(d["理由"])))
            if _lp["城市"]:
                P.append('<p class="hd">这些城市落在喜用方位上</p>')
                P.append('<div class="tagline">')
                for c in _lp["城市"]:
                    dist = ("距出生地约 %d 公里" % c["距离"]) if c["有距离"]                         else "距离未知（没填出生地）"
                    P.append('<div class="tag"><b>%s</b>%s · %s<br>'
                             '<span class="sub2">%s</span></div>'
                             % (_h(c["城市"]), _h(c["省"]),
                                _h(c["方位名"]), _h(dist)))
                P.append("</div>")
            P.append('<p class="sub2">%s</p></div></details>'
                     % _h(_lp["提醒"]))

        # ---- 1.3.1 新增：大运逐段（折叠）----
        if b.get("大运详批") and b["大运详批"]["列表"]:
            dl = b["大运详批"]["列表"]
            cur_i = next((i for i, x in enumerate(dl) if x["是当前"]), None)
            P.append('<details class="fold"><summary>你一生十步大运'
                     '%s<span class="cnt">共 %d 步%s</span></summary><div class="fbody">'
                     '<p class="sub2">每十年换一段，是运势的主基调。'
                     '折叠起来是因为十段一起铺开太长，实际用到的是当前那一步——'
                     '所以当前那步放在最前面标出来。</p><div class="dy">'
                     % (_prev(("当前 %s · %s" % (dl[cur_i]["干支"],
                                               dl[cur_i]["主题"][:12]))
                              if cur_i is not None else ""),
                        len(dl), ("，当前在第 %d 步" % dl[cur_i]["序"]) if cur_i is not None else ""))
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
            # 流年时间轴：七年一格，先给个形状再看逐年
            _lnt = M_plain.liunian_timeline(
                (data.get("八字") or {}).get("流年"),
                now_year=int((data.get("八字") or {}).get("当前时间", 2026)))
            if _lnt:
                P.append(_lnt)
            _now_ln = next((y for y in ll if y.get("是今年")), None)
            # 接下来三年：七年平铺着看不出轻重，先给三年摘要
            if b.get("未来三年"):
                _cells = ""
                for _y in b["未来三年"]:
                    _cells += ('<div class="y3-i"><div class="y3-yr">%d %s%s'
                               '<span class="y3-tag">%s</span></div>'
                               '<p class="y3-t">%s</p><p class="y3-n">%s</p></div>'
                               % (_y["年"], _h(_y.get("干支", "")),
                                  "（今年）" if _y.get("是今年") else "",
                                  _h(_y.get("标签", "")), _h(_y.get("解读", "")),
                                  _h(_y.get("说明", ""))))
                P.append('<div class="y3"><div class="y3-h">接下来三年</div>'
                         '<p class="y3-sub">判据只有一条：这一年的天干五行'
                         '是不是你的喜用 —— 与方位、颜色、行业同一套口径。</p>'
                         '<div class="y3-grid">%s</div></div>' % _cells)
            P.append('<details class="fold"><summary>未来七年的年度节奏'
                     '%s<span class="cnt">%d–%d</span></summary><div class="fbody">'
                     '<p class="sub2">大运是十年的大背景，流年是这一年的具体调子。'
                     '大运管方向，流年管「今年什么事儿容易发生」。</p><div class="ly">'
                     % (_prev(("%d %s · 虚岁 %d" % (_now_ln["年"], _now_ln["干支"],
                                                  _now_ln["虚岁"]))
                              if _now_ln else ""),
                        ll[0]["年"], ll[-1]["年"]))
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
                     '%s<span class="cnt">八字五行</span></summary><div class="fbody">'
                     % _prev(" · ".join(
                         ([("%s最旺" % w["最强"]["五行"])] if w.get("最强") else [])
                         + ([("%s最弱" % w["最弱"]["五行"])] if w.get("最弱") else []))))
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
                     '%s<span class="cnt">哪个最重</span></summary><div class="fbody">'
                     % _prev((lambda its: ("最重 %s" % its[0])
                              + ("（%d 个并列）" % len(its) if len(its) > 1 else ""))
                              ([x for x in str(shd["最多"]).split("、") if x])))
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
        P.append('<h2 id="s-ziwei" data-t="紫微 · 事业财运">紫微斗数 · 看事业、财运、感情</h2>')
        P.append('<div class="sec-lead">这一节讲事业、财运、感情，'
                 '还有眼前这一段的重心落在哪儿。</div>')
        # 十二宫小盘：先给形状，再逐条读。点一格跳到下面那一宫的解读。
        P.append(ziwei_pan(data["紫微"], mini=True))
        P.append('<p class="sub2" style="text-align:center;margin:6px 0 14px">'
                 '红框是命宫，虚线是身宫；点一格，下面会滚到那一宫的解读。</p>')
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
            _ming = next((q for q in pl if q.get("是命宫")), None)
            P.append('<details class="fold"><summary>你的十二宫'
                     '%s<span class="cnt">逐宫看</span></summary><div class="fbody">'
                     '<p class="sub2">十二宫代表人生十二个领域。'
                     '「主星」决定这个领域的底色；宫里没有主星很常见，'
                     '要借对宫的星来看，那不是缺陷。</p><div class="pl">'
                     % _prev(("命宫 %s" % ("、".join(_ming["主星"])
                                        if _ming and _ming["主星"] else "空宫"))
                              if _ming else ""))
            for pl_i, p2 in enumerate(pl):
                cls = ""
                marks = []
                if p2["是命宫"]:
                    cls += " ming"
                    marks.append("命宫")
                if p2["是身宫"]:
                    cls += " shen"
                    marks.append("身宫")
                P.append('<div class="it%s" id="pl-%d"><div class="hd">'
                         '<span class="pn">%s</span><span class="gz2">%s</span>'
                         % (cls, pl_i, _h(p2["宫名"]), _h(p2["干支"])))
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
                     '%s<span class="cnt">紫微的十年分段</span></summary><div class="fbody">'
                     '<p class="sub2">大限走的是<b>宫位</b>而不是十神 —— '
                     '每十年重心落在哪个宫，那十年的主语就是那个宫代表的事。'
                     '和大运是两套不同的分段方式，别混着看。</p><div class="dx">'
                     % _prev(("当前 %s" % cur_dx) if cur_dx else ""))
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
                     '%s<span class="cnt">%s年 %s</span></summary><div class="fbody">'
                     % (_prev(("流年命宫 %s" % ln["流年命宫名"])
                              if ln.get("流年命宫名") else ""),
                        _h(str(ln.get("年", ""))), _h(str(ln.get("干支", "")))))
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
            _lu = next((q for q in z["四化详批"] if q.get("化") == "化禄"), None)
            _ji = next((q for q in z["四化详批"] if q.get("化") == "化忌"), None)
            _sh_prev = []
            if _lu and _lu.get("宫位"):
                _sh_prev.append("化禄在%s" % _lu["宫位"])
            if _ji and _ji.get("宫位"):
                _sh_prev.append("化忌在%s" % _ji["宫位"])
            P.append('<details class="fold"><summary>四化落在哪'
                     '%s<span class="cnt">禄权科忌</span></summary><div class="fbody">'
                     '<p class="sub2">生年四化是「哪颗星被强化」，'
                     '它落在哪个宫，那一块就跟着强化。化忌不是坏事，'
                     '是这辈子要学的课题。</p><div class="sh">'
                     % _prev(" · ".join(_sh_prev)))
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
            if sp.get("组合"):
                _sp_prev = sp["组合"]["型"]
            elif sp.get("主星"):
                _sp_prev = "主星 " + "、".join(sp["主星"])
            else:
                _sp_prev = ""
            P.append('<details class="fold"><summary>夫妻宫'
                     '%s<span class="cnt">%s%s</span></summary><div class="fbody">'
                     % (_prev(_sp_prev),
                        _h(("宫干 " + sp["宫干"]) if sp.get("宫干") else ""),
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
        P.append('<h2 id="s-astro" data-t="占星 · 性格另一面">西洋占星 · 看性格的另一面</h2>')
        P.append('<div class="sec-lead">这一节从另一个角度看性格：别人看到的你、'
                 '情绪的来处、关系里的张力。</div>')
        # 星盘轮：先把盘给出来，再读文字。和「专业数据」里那张是同一张。
        if data["占星"].get("天体"):
            P.append('<div class="plain"><h3>你的星盘</h3>'
                     '<p class="sub2">外圈是黄道十二宫，行星按真实黄经落在盘上；'
                     '两点之间的线是相位。看个形状就好，细节在下面的文字里。</p>%s</div>'
                     % M_plain.astro_chart(data["占星"], 300))
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
            _el_max = next((x for x in a["元素配比"]["逐项"] if x.get("最旺")), None)
            _el_none = next((x for x in a["元素配比"]["逐项"] if x.get("完全缺")), None)
            _el_prev = []
            if _el_max:
                _el_prev.append("%s最多" % _el_max["元素"])
            if _el_none:
                _el_prev.append("%s完全没有" % _el_none["元素"])
            P.append('<details class="fold"><summary>四种元素逐项看'
                     '%s<span class="cnt">占星四元素</span></summary><div class="fbody">'
                     % _prev(" · ".join(_el_prev)))
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
            _ax = {}
            for _x in a["轴点详批"]["列表"]:
                # 键是「名」（上升 / 天顶），不是「角色」（那是一句解释）
                _ax[_x.get("名")] = _x.get("星座")
            P.append('<details class="fold"><summary>两个轴点'
                     '%s<span class="cnt">上升与天顶</span></summary><div class="fbody">'
                     % _prev(" · ".join(x for x in [
                         ("上升" + _ax["上升"]) if _ax.get("上升") else "",
                         ("天顶" + _ax["天顶"]) if _ax.get("天顶") else ""] if x)))
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
            P.append('<h2 id="s-cross" data-t="三盘交叉">'
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

            rest = x["分歧"] + x["单盘"] + x["一致"]
            if rest:
                P.append("<details class=\"ssx\"><summary>六个维度逐项对照"
                         '<span class="cnt">%d 个 · 三边各说了什么</span></summary>'
                         % len(rest))
                P.append('<div class="plain">')
                for r in rest:
                    P.append('<div class="xsx"><p class="xsx-q">%s：%s</p>'
                             % (_h(r["维度"]), _h(r["问"])))
                    if r["一致"]:
                        P.append('<p class="xsx-h"><b>· %s</b>　三边都指向'
                                 '「%s」</p>' % (_h(r["维度"]), _h(r["同向"])))
                    else:
                        P.append('<p class="xsx-h"><b>%s</b>　三边说法不一</p>'
                                 % _h(r["维度"]))
                    if r["一致"] and r.get("表现"):
                        P.append('<p class="li">%s</p>' % _h(r["表现"]))
                    for g in r["各家"]:
                        P.append('<p class="li"><b>%s</b>：%s　'
                                 '<span class="sub2">%s</span></p>'
                                 % (_h(g["盘"]), _h(g["端"]), _h(g["依据"])))
                    if not r["一致"] and r.get("场景"):
                        P.append('<p class="hd">两边各自什么时候出现</p>')
                        for sc in r["场景"]:
                            P.append('<p class="li"><b>%s</b>：%s'
                                     '<span class="sub2">（多在%s）</span></p>'
                                     % (_h(sc["端"]),
                                        _h(sc["说明"] or ""),
                                        _h(sc["场景"] or "各种场景")))
                    if r["一致"]:
                        P.append('<p class="sub2">只有一盘给了信号，'
                                 '无从交叉 —— 这里只代表那一套体系怎么看。</p>')
                    P.append("</div>")
                P.append("</div></details>")

            P.append("<details class=\"ssx\"><summary>这三边分别按什么算的"
                     "<span class=\"cnt\">三边各一节</span></summary>"
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
        P.append('<h2 id="s-taohua" data-t="桃花星">'
                 '%s</h2>' % _h(th["标题"]))
        P.append('<div class="plain"><p>%s</p>'
                 '<p class="li">下面三边说的是<em>不同层面</em>，'
                 '不是互相矛盾：八字看的是人缘的广度，'
                 '紫微看的是你在关系里的姿态，'
                 '占星看的是你被什么样的人吸引、'
                 '以及你希望怎么被对待。</p></div>'
                 % _h(th["要点"]))
        P.append('<details class="ssx"><summary>三盘分别怎么说'
                 '<span class="cnt">%d 条逐条对照</span></summary><div class="plain">'
                 % len(th["列表"]))
        for r in th["列表"]:
            P.append('<div class="xsx"><p class="xsx-h"><b>%s</b>%s</p>'
                     % (_h(r["盘"]), _h(r["项"])))
            P.append('<p class="li">→ %s　<span class="sub2">%s</span></p>'
                     % (_h(r["答"]), _h(r["依据"])))
            P.append('<p class="sub2">%s</p>' % _h(r["说明"]))
            if r.get("提示"):
                P.append('<p class="li">%s</p>' % _h(r["提示"]))
            P.append("</div>")
        P.append('<p class="sub2">%s</p></div></details>' % _h(th["提醒"]))

    cr = M_plain.career_plain(data.get("八字"), data.get("紫微"),
                              data.get("占星"))
    if cr["列表"]:
        P.append('<h2 id="s-industry" data-t="行业细分">'
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
                     '<span class="cnt">点开看每组有哪些行业</span></summary>'
                     '<div class="plain">'
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

    # ---- 一分钟速览：全篇结论的四句话 ----
    # 文案全部取自引擎已有的结论（不是另写一句话），
    # 所以速览和正文不会打架。
    q_items = []
    if pe["块"]:
        q_items.append(("像什么", pe["块"][0]["文"]))
    if b and b.get("做事方式"):
        q_items.append(("怎么做事", b["做事方式"]["要点"]))
    if z and z.get("感情模式"):
        q_items.append(("关系里", z["感情模式"]["要点"]))
    if b and b.get("当前阶段"):
        _cs = b["当前阶段"]
        q_items.append(("眼前这段", "%s 大运 · %s"
                        % (_cs.get("干支", ""), _cs.get("主题", ""))))
    if b and b.get("最该注意"):
        # 提醒一直写在十步大运里，但没人会把十个折叠逐个点开去找 ——
        # 提到速览里，它才真的被看见
        q_items.append(("最该注意", b["最该注意"]))
    if q_items:
        _cells = "".join('<div class="q"><b>%s</b><span>%s</span></div>'
                         % (_h(k), _h(v)) for k, v in q_items)
        _quick = ('<div class="quick"><div class="quick-h">一分钟速览</div>'
                  '<div class="quick-t">下面这几句就是全篇的结论，'
                  '想细看再往下。</div>'
                  '<div class="quick-grid">%s</div></div>' % _cells)
    else:
        _quick = ""
    _qi = P.index("@@QUICK@@")
    P[_qi] = _quick

    P.append("</section>")
    return _despacify("".join(P))


def render_glossary():
    P = ['<section><h2 id="s-glossary" data-t="名词解释">'
         '名词解释 · 看不懂的词看这里</h2><div class="gloss">']
    for k, v in M_plain.GLOSSARY.items():
        P.append("<div><b>%s</b>：%s</div>" % (_h(k), _h(v)))
    P.append("</div></section>")
    return "".join(P)


def render_toc(plain_html, pro_html):
    """从已渲染的 HTML 反推本页目录。

    为什么不另写一份「本页有哪些小节」的清单：
    清单会和实际渲染脱节（数据不够时某节不渲染，目录里却还留着，
    点过去什么都没有），而且清单要在 Python 和 JS 两边各写一遍，
    改一处就可能对不上。这里改成扫 h2[data-t]：
    渲染出什么，目录就是什么；两边输入相同，输出必然相同。
    """
    items = []
    for html in (plain_html, pro_html):
        for m in re.finditer(r"<h2([^>]*)>([^<]*)</h2>", html):
            attrs = m.group(1)
            idm = re.search(r'id="([^"]+)"', attrs)
            tm = re.search(r'data-t="([^"]*)"', attrs)
            if not (idm and tm):
                continue
            items.append((idm.group(1), tm.group(1)))
    if not items:
        return ""
    links = "".join('<a class="toc-i" href="#%s">%s</a>' % (i, t)
                    for i, t in items)
    return ('<nav class="toc" id="s-toc" aria-label="本页目录">'
            '<div class="toc-h">本页目录'
            '<span class="toc-tip">点一下跳到对应小节</span></div>'
            '<div class="toc-grid">%s</div>'
            '<div class="toc-tools">'
            '<input class="toc-search" type="search" placeholder="找一句话…'
            '" aria-label="在本页查找">'
            '<button type="button" class="toc-btn" data-toc="expand">'
            '全部展开</button>'
            '<button type="button" class="toc-btn" data-toc="collapse">'
            '全部收起</button>'
            '</div>'
            '<div class="toc-results" hidden></div>'
            '</nav>' % links)


def render_html(data, title="命理神机 · 命盘"):
    hl = M_plain.headline(data)
    parts = ['<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">',
             '<meta name="description" content="' + _h('八字、紫微斗数、西洋占星在线排盘。全部计算在你的浏览器里完成，生辰不上传任何服务器，可离线使用。') + '">',  # noqa: E501
             '<meta name="viewport" content="width=device-width,initial-scale=1">',
             "<title>%s</title><style>%s</style></head><body><main class='wrap'>" % (_h(title), CSS),
             "<h1>命 理 神 机</h1>",
             "<div class='sub'>八字 · 紫微斗数 · 西洋占星　|　在你自己的电脑上算，不上传、不联网</div>",
             '<div class="headline"><div class="big">%s</div>'
             '<div class="tip">这是你命盘的三个关键词，下面用大白话展开</div></div>' % _h(hl)]
    plain_html = render_plain(data)
    pro_parts = []
    if "八字" in data:
        pro_parts.append(render_bazi(data["八字"]))
    if "紫微" in data:
        pro_parts.append(render_ziwei(data["紫微"]))
    if "占星" in data:
        pro_parts.append(render_astro(data["占星"]))
    pro_parts.append(render_glossary())
    pro_html = "".join(pro_parts)
    parts.append(render_toc(plain_html, pro_html))
    parts.append(plain_html)
    parts.append('<div class="secnote">'
                 '———— 以下是专业排盘数据，想深入研究的可以往下看 ————</div>')
    parts.append(pro_html)
    parts.append('<div class="foot">上面的排盘结果是按天文历法和命理规则算出来的，'
                 '解读部分仅供娱乐参考，不能当作医疗、投资或人生的决策依据。<br>'
                 '命盘显示的是可能性，路怎么走还是看你自己。</div>')
    parts.append("<script>%s</script>" % PAGE_JS)
    parts.append("</main></body></html>")
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

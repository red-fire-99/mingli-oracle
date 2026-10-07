#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""临时脚本：用 iztro 交叉验证紫微斗数排盘（全星曜位置对比）。"""
import json
import shutil
import subprocess
import sys
import tempfile
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import almanac as A
import ziwei as Z

# Node 可执行文件：优先 $NODE，其次 PATH 里的 node
NODE = os.environ.get("NODE") or shutil.which("node") or "node"

# 装了 iztro 的那层目录（含 node_modules/iztro）。按 README 的用法，
# 在 tools/ 下执行 `npm install iztro` 就会命中第一个候选。
_TOOLS = os.path.dirname(os.path.abspath(__file__))


def _find_workspace():
    cands = []
    if os.environ.get("IZTRO_WORKSPACE"):
        cands.append(os.environ["IZTRO_WORKSPACE"])
    d = _TOOLS
    while True:                      # 从 tools/ 一路向上找 node_modules/iztro
        cands.append(d)
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    cands.append(os.getcwd())
    for c in cands:
        if os.path.isdir(os.path.join(c, "node_modules", "iztro")):
            return c
    return _TOOLS                  # 找不到就用 tools/，让报错信息提示 npm install


WORKSPACE = _find_workspace()
JS = os.path.join(_TOOLS, "ziwei_ref.js")

ZHI = A.ZHI
# iztro 五行局 → 中文
FIVE_MAP = {"water2nd": "水二局", "wood3rd": "木三局", "gold4th": "金四局",
            "earth5th": "土五局", "fire6th": "火六局"}
# 只比对十四主星（辅星各家口径略有差异）
MAJOR = ("紫微", "天机", "太阳", "武曲", "天同", "廉贞",
         "天府", "太阴", "贪狼", "巨门", "天相", "天梁", "七杀", "破军")


def gen_cases():
    """生成一批对照用例：不同年/月/日/时辰/性别。"""
    cases = []
    for (y, m, d) in [(1990, 5, 15), (1991, 8, 15), (1985, 2, 4), (1976, 11, 3),
                      (2000, 1, 1), (1965, 6, 20), (1995, 12, 31), (2010, 3, 8),
                      (1988, 7, 22), (2003, 9, 30)]:
        for ti in (0, 2, 5, 6, 9, 11):
            for gender in ("男", "女"):
                cases.append({"date": "%04d-%02d-%02d" % (y, m, d),
                              "timeIndex": ti, "gender": gender})
    return cases


def main():
    if not os.path.isdir(os.path.join(WORKSPACE, "node_modules", "iztro")):
        print("没找到 iztro。当前查找目录:", WORKSPACE)
        print("装一下即可:  cd tools && npm install iztro")
        print("（若装在别处，设环境变量 IZTRO_WORKSPACE 指向那层目录）")
        return 2
    cases = gen_cases()
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(cases, f)
        tmp = f.name
    env = dict(os.environ)
    env["NODE_PATH"] = os.path.join(WORKSPACE, "node_modules")
    res = subprocess.run([NODE, JS, tmp], capture_output=True, text=True,
                         env=env, cwd=WORKSPACE, timeout=300)
    os.unlink(tmp)
    if res.returncode != 0:
        print("Node 执行失败:", res.stderr[:800])
        return 1
    refs = json.loads(res.stdout)

    total = ok = 0
    fails = []
    for c, ref in zip(cases, refs):
        if not ref.get("ok"):
            continue
        total += 1
        y, m, d = (int(x) for x in c["date"].split("-"))
        # 我的引擎：timeIndex 与 iztro 一致（子=0 … 亥=11）
        hour = {0: 0, 1: 1, 2: 3, 3: 5, 4: 7, 5: 9, 6: 11, 7: 13,
                8: 15, 9: 17, 10: 19, 11: 21}[c["timeIndex"]]
        r = Z.pai_pan(solar=(y, m, d), hour=hour, sex=c["gender"])
        # 命宫地支
        ming = next(p for p in r["十二宫"] if p["是否命宫"])
        errs = []
        if ming["地支"] != ref["soulZhi"]:
            errs.append("命宫 %s≠%s" % (ming["地支"], ref["soulZhi"]))
        # 五行局
        if r["五行局"] != FIVE_MAP.get(ref["five"], ref["five"]):
            errs.append("五行局 %s≠%s" % (r["五行局"], ref["five"]))
        # 十四主星落宫
        by_zhi = {p["地支"]: p["星曜"] for p in r["十二宫"]}
        for pref in ref["palaces"]:
            for s in pref["stars"]:
                base = s["n"]
                if base not in MAJOR:
                    continue
                mine = by_zhi.get(pref["zhi"], [])
                if base not in [x.split("·")[0] for x in mine]:
                    errs.append("%s 应在%s宫" % (base, pref["zhi"]))
        if errs:
            fails.append((c, errs))
        else:
            ok += 1
    print("=" * 60)
    print("  紫微斗数 vs iztro 对照")
    print("=" * 60)
    print("  用例总数：%d   完全一致：%d   存在差异：%d" % (total, ok, len(fails)))
    for c, errs in fails[:12]:
        print("   ✗ %s ti=%d %s -> %s" % (c["date"], c["timeIndex"], c["gender"], "; ".join(errs[:4])))
    if len(fails) > 12:
        print("   ... 另有 %d 例" % (len(fails) - 12))
    print("=" * 60)
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())

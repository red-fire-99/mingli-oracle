#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 plain.py 里的文案字典导出成 JSON，供 JS 版直接读取。

为什么可以机器转换
------------------
plain.py 有 897 行，但其中约七成是**模块级字典**（30 个），只有 6 个函数。
字典是纯数据，不含逻辑，直接 json.dump 即可 —— 不必手抄，也不会抄错。
这也顺带避免了「两份文案不一致」的风险：JSON 由 Python 生成，同源。

真正需要移植的只有那 6 个函数：
  _pick / bazi_plain / ziwei_plain / astro_plain / headline / glossary_html

用法
----
    python web/gen_plain_json.py            # 输出到 web/js/plain-data.json
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import plain as PL  # noqa: E402

# 需要导出的字典（按 plain.py 的模块级定义）
NAMES = ["DAY_MASTER", "STRENGTH", "SHISHEN", "ZIWEI_STAR", "SHENSHA",
         "WUXING_HIGH", "WUXING_LOW", "WUXING_LUCK", "ZHI_TO_SX", "SHENGXIAO",
         "SIGN_PROFILE", "DAYUN_THEME", "SIGN_PLAIN", "SUN_SIGN", "MOON_SIGN",
         "ASC_SIGN", "MERCURY_SIGN", "VENUS_SIGN", "MARS_SIGN", "PLANET_ROLE",
         "PLANET_PLAIN", "HOUSE_MEANING", "HOUSE_BY_PLANET", "ASPECT_TRAIT",
         "SUN_KEYWORD", "MOON_KEYWORD", "ASC_KEYWORD", "ELEMENT_MORE",
         "ELEMENT_MISS", "RULER", "GLOSSARY"]


def sanitize(o):
    """把 Python 值转成 JSON 可序列化的形式，并报告改动了什么。"""
    notes = []

    def conv(x, path):
        if isinstance(x, dict):
            return {str(k): conv(v, path + "." + str(k)) for k, v in x.items()}
        if isinstance(x, (list, tuple)):
            return [conv(v, path + "[%d]" % i) for i, v in enumerate(x)]
        if isinstance(x, (set, frozenset)):
            notes.append("%s: set -> sorted(list)" % path)
            return sorted(conv(v, path) for v in x)
        if isinstance(x, bool) or x is None:
            return x
        if isinstance(x, (int, float, str)):
            return x
        if isinstance(x, tuple):          # 不可达，保险
            return [conv(v, path) for v in x]
        notes.append("%s: %s -> str" % (path, type(x).__name__))
        return str(x)

    return conv(o, ""), notes


def main():
    data = {}
    all_notes = []
    for n in NAMES:
        v = getattr(PL, n, None)
        if v is None:
            print("缺失：%s" % n, file=sys.stderr)
            return 1
        conv, notes = sanitize(v)
        data[n] = conv
        all_notes += notes
        print("  %-20s %5d 项" % (n, len(conv)))

    dest = os.path.join(HERE, "js", "plain-data.json")
    text = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    with io.open(dest, "w", encoding="utf-8") as f:
        f.write(text)
    kb = len(text.encode("utf-8")) / 1024.0
    print("\n已生成 %s（%d 个字典, %.1f KB）" % (dest, len(data), kb))
    if all_notes:
        print("注意：有 %d 处类型需要转换" % len(all_notes))
        for n in all_notes[:10]:
            print("   " + n)
    else:
        print("全部为原生 JSON 类型，无需转换")
    return 0


if __name__ == "__main__":
    sys.exit(main())
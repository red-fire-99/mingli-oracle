#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""时区无关性验证：同一生辰，在不同时区下跑 JS 引擎，结果必须逐字相同。

为什么这是必须验的
------------------
命理一切以北京时间为准，但浏览器跑在**用户本机时区**。
若代码里有一处用了 new Date() / getFullYear() 这类依赖本机时区的写法：
  - 开发者在北京（UTC+8）测试，一切正常
  - 用户在纽约（UTC-5）或东京（UTC+9），结果悄悄偏了，且不报错

kernel.js 里 bjCivilFromUnix 用 getUTC* 系列、bjUnix 用 Date.UTC，
刻意不碰本机时区。这道检查守住这个设计。

挑的时区刻意刁钻，覆盖跨日与跨年边界：
  UTC-11 / UTC-8 / UTC-5 / UTC / UTC+8 / UTC+9 / UTC+12~13 / UTC+14

探针文件由本脚本现写现删 —— 不留成仓库文件，避免它被 .gitignore
之类的规则漏掉（我就在这上面翻过车：探针文件某次被清理掉了，
检查从此静默地「全部失败」而不是「全部通过」，一度像引擎坏了）。

用法
----
    python web/check_timezone.py [--js node]
"""
import argparse
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
JS = os.path.join(HERE, "js")
PROBE_NAME = ".tz_probe.mjs"
PROBE = os.path.join(JS, PROBE_NAME)

TZS = [
    ("Etc/GMT+11", "UTC-11"),
    ("America/Los_Angeles", "UTC-8 (含夏令时)"),
    ("America/New_York", "UTC-5 (含夏令时)"),
    ("UTC", "UTC"),
    ("Asia/Shanghai", "UTC+8 (基准)"),
    ("Asia/Tokyo", "UTC+9"),
    ("Pacific/Auckland", "UTC+12/13 (含夏令时)"),
    ("Pacific/Kiritimati", "UTC+14"),
]

PROBE_JS = r"""
import { paiPan as baziPaiPan } from "./bazi.js";
import { paiPan as ziweiPaiPan } from "./ziwei.js";
import { paiPan as astroPaiPan } from "./astro.js";
import { baziPlain, ziweiPlain, astroPlain, headline } from "./plain.js";

const PIN = 2026;   // 钉死「当前年」，否则不同机器的流年不同，比对无意义

const CASES = [
  { solar: [1990, 5, 15], hour: [12, 0], sex: "男", place: "北京", lon: 116.41, lat: 39.90 },
  { solar: [1990, 5, 15], hour: [23, 30], sex: "男", place: "北京", lon: 116.41, lat: 39.90 },
  { solar: [2024, 2, 4], hour: [23, 0], sex: "女", place: "拉萨", lon: 91.11, lat: 29.97 },
  { solar: [2000, 1, 1], hour: [0, 30], sex: "女", place: "上海", lon: 121.47, lat: 31.23 },
  { solar: [1984, 2, 4], hour: [1, 0], sex: "男", place: "广州", lon: 113.26, lat: 23.13 },
  { solar: [1900, 1, 1], hour: [12, 0], sex: "男", place: "乌鲁木齐", lon: 87.62, lat: 43.83 },
  { solar: [2100, 12, 31], hour: [23, 59], sex: "女", place: "北京", lon: 116.41, lat: 39.90 },
  { solar: [2020, 6, 21], hour: [12, 0], sex: "男", place: "北京", lon: 116.41, lat: 39.90 },
];

const out = [];
for (const c of CASES) {
  const rb = baziPaiPan({ solar: c.solar, lunar: null, leap: false, hour: c.hour,
    shichen: null, sex: c.sex, place: c.place, longitude: c.lon, nowYear: PIN });
  const rz = ziweiPaiPan({ solar: c.solar, lunar: null, leap: false, hour: c.hour,
    shichen: null, sex: c.sex, place: c.place, year: PIN });
  const ra = astroPaiPan({ solar: c.solar, lunar: null, leap: false, hour: c.hour,
    shichen: null, sex: c.sex, lat: c.lat, lon: c.lon, place: c.place });
  out.push({
    case: JSON.stringify(c.solar) + " " + c.sex + " " + c.hour.join(":"),
    四柱: rb.四柱,
    真太阳时: rb.输入.真太阳时,
    日主: rb.日主.干,
    旬空: rb.旬空,
    起运: rb.大运.起运,
    五行: rb.五行统计,
    紫微五行局: rz.五行局,
    紫微命宫: rz.命宫,
    紫微十二宫: rz.十二宫.map(p => [p.宫名, p.地支, p.天干, p.星曜]),
    上升: ra.上升星座,
    太阳: ra.太阳星座,
    天体: ra.天体.map(t => [t.天体, t.黄经, t.星座, t.星座内度]),
    相位: ra.相位.map(a => [a.天体1, a.天体2, a.相位, a.标准角, a.偏差, a.强度]),
    文案: [baziPlain(rb), ziweiPlain(rz), astroPlain(ra),
            headline({ 八字: rb, 紫微: rz, 占星: ra })],
  });
}

process.stdout.write("@@TZ@@" + JSON.stringify(out));
"""


def run(js, tz):
    env = dict(os.environ)
    env["TZ"] = tz
    r = subprocess.run([js, PROBE_NAME], capture_output=True, env=env,
                       cwd=JS, timeout=300)
    so = r.stdout.decode("utf-8", "replace")
    if "@@TZ@@" not in so:
        return None, (r.stderr.decode("utf-8", "replace")[-400:] or "无输出")
    return json.loads(so.split("@@TZ@@", 1)[1]), None


def main(argv=None):
    p = argparse.ArgumentParser(description="JS 引擎的时区无关性检查")
    p.add_argument("--js", default=os.environ.get("MINGLI_NODE", "node"))
    a = p.parse_args(argv)

    io.open(PROBE, "w", encoding="utf-8").write(PROBE_JS)
    print("时区无关性检查\n")
    try:
        base, base_name = None, None
        fails = []
        for tz, desc in TZS:
            data, err = run(a.js, tz)
            if data is None:
                print("  [FAIL] %-22s 运行失败: %s" % (tz, err.replace("\n", " ")[:150]))
                fails.append(tz)
                continue
            if base is None:
                base, base_name = data, tz
                print("  [OK]   %-22s %-22s 基准" % (tz, desc))
                continue
            if data == base:
                print("  [OK]   %-22s %-22s 与基准逐字一致" % (tz, desc))
                continue
            for x, y in zip(base, data):
                if x != y:
                    diff = [k for k in x if x[k] != y[k]]
                    print("  [FAIL] %-22s %-22s 用例「%s」字段 %s 不同"
                          % (tz, desc, x["case"], ",".join(diff)))
                    for k in diff:
                        print("           基准(%s)=%s"
                              % (base_name, json.dumps(x[k], ensure_ascii=False)[:130]))
                        print("           本时区=%s"
                              % json.dumps(y[k], ensure_ascii=False)[:130])
                    break
            fails.append(tz)
    finally:
        try:
            os.remove(PROBE)
        except OSError:
            pass

    print("\n" + "=" * 60)
    if fails:
        print("失败 %d 个时区：%s" % (len(fails), ", ".join(fails)))
        print("引擎里存在依赖本机时区的代码 —— 用户在非 UTC+8 时区会算错。")
        return 1
    print("全部 %d 个时区结果逐字一致 —— 引擎与用户所在时区无关" % len(TZS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
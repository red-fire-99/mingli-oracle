# 命理神机 · mingli-oracle

一个**零依赖、纯本地、可离线**的中式命理与西方占星排盘引擎。

一次输入生辰，确定性排出 **四柱八字、紫微斗数、西洋占星本命盘**，并按所问之事起 **六爻 / 梅花易数** 卦，
输出「说人话」的白话解读和可离线打开的命盘网页。

> 排盘结果由天文历法与命理规则确定性计算得出，**不联网、不上传任何数据**。
> 所有解读仅供文化研究与娱乐参考，不构成任何医疗、投资或人生决策依据。

---

## 特点

- **零第三方依赖**：只用 Python 标准库，`pip install` 什么都不用装。
- **纯本地运行**：不联网、不上传，关掉程序就什么都不留。
- **天文级精度**：节气用太阳视黄经「定气」、朔望用 Meeus 定朔、行星位置经权威星历交叉验证。
- **确定性排盘**：同样的输入永远得到同样的输出，不靠大模型「编」。
- **说人话**：内置白话文案库，把术语翻译成日常语言，还给出幸运色、方位、数字、行业等实用对应。
- **双端可用**：带一个本地网页界面，桌面和手机浏览器都能流畅使用。
- **可作为 AI Skill**：附带 `SKILL.md`，可被 AI Agent 直接加载调用。

---

## 在线使用

**https://red-fire-99.github.io/mingli-oracle/**

打开即用。填生日 → 出命盘 → 可切「说人话版 / 专业数据」→ 可保存成离线网页。

页面加载后**不发起任何网络请求**，不需要下载任何运行时，
`file://` 双击打开也能跑（产物是单个自包含 HTML，168KB）。

关于隐私：纯前端计算，没有后端服务器。**生辰只在你自己的浏览器里算，
不发往任何地方**，关掉页面什么都不留。

不想在浏览器里跑，用下面的本地版。

## 本地使用

要求：**Python 3.8+**（不需要装任何包）。

> Windows 用户注意：命令行里的 `python` 有时指向的是很老的 3.5 版本，会报
> `ImportError: cannot import name 'ThreadingHTTPServer'`。用官方启动器更稳妥：
> `py -3 server.py`。先确认版本：`python --version`，低于 3.8 就改用 `py -3`。

### 方式一：网页界面（推荐给普通用户）

```bash
cd scripts
python server.py
```

会自动打开 `http://127.0.0.1:8765`，在页面里填生日就能排盘。

```bash
python server.py --port 9000         # 换端口
python server.py --host 0.0.0.0      # 让同一 WiFi 下的手机也能打开
python server.py --no-browser        # 不自动开浏览器
```

界面自带表单、按钮、加载提示和出错提示，排完盘直接看「说人话版」，可切换「专业数据」，
还能一键保存成离线网页。按 `Ctrl+C` 停止。

### 方式二：命令行

```bash
cd scripts

# 综合排盘（八字 + 紫微 + 占星），打印到终端
python oracle.py --solar 1990-05-15 --hour 12:00 --sex 男 --place 北京 --lat 39.9 --lon 116.4

# 生成自包含命盘网页（单文件、零外链、可离线双击打开）
python oracle.py --solar 1990-05-15 --hour 12:00 --sex 男 --lat 39.9 --lon 116.4 --out 命盘.html

# 只要某一项
python oracle.py --solar 1990-05-15 --hour 12:00 --sex 男 --only ziwei
python oracle.py --lunar 1990-04-21 --shichen 午 --sex 女 --only bazi

# 单模块调用（需要 JSON 时加 --json）
python bazi.py --solar 1990-05-15 --hour 12:00 --sex 男 --lon 116.4
python ziwei.py --solar 1991-08-15 --hour 1 --sex 男 --year 2027
python astro.py --solar 1990-05-15 --hour 12:00 --lat 39.9 --lon 116.4

# 六爻占卜
python divination.py --time --solar 1990-05-15 --hour 12:00
python divination.py --numbers 7 15
python divination.py --toss

# 改过代码后跑一遍自测
python self_test.py
```

**常用参数**：`--solar` 阳历生日 · `--lunar` 农历生日（`--leap` 闰月） · `--hour HH:MM` ·
`--shichen 子|丑|…|亥` · `--sex 男|女` · `--lon/--lat` 经纬度 · `--year` 指定流年。

---

## 它能算什么

### 四柱八字
四柱干支、十神、藏干、纳音、日主强弱、格局判定、旬空、二十余种神煞、大运（顺逆与起运）、
流年，以及按喜用神给出的**开运指南**（幸运色 / 方位 / 数字 / 行业 / 饰品 / 日常做法）和生肖速查。

### 紫微斗数
命宫身宫、五行局、十四主星、辅星煞星、生年四化、大限顺逆、流年，
并按事业 / 财运 / 感情分维度给出白话解读，附五行局开运建议。

### 西洋占星
日月与八大行星黄经、星座与度数、上升点与天顶、整宫制十二宫、主要相位、元素与性质配比，
以及每个星座的**实用档案**（守护星 / 幸运色 / 数字 / 日 / 宝石 / 职业 / 身体）。
解读拆成七个层次：一句话、三大支柱、性格拼图、人生重心、关键线索、能量配比、主要张力。

### 六爻 / 梅花易数
支持时间起卦、数字起卦、摇卦三种方式，自动装卦（纳甲、六亲、世应、六神）并给出变卦。

---

## 精度与验证

排盘不是玄学，是可复现的数学。本项目做了多轮交叉验证：

| 项目 | 验证方式 | 结果 |
|---|---|---|
| 行星黄经 | 与 `ephem`（VSOP87 / ELP2000）逐天体对比 11 个时间截面 | 太阳 0.01°、月亮 0.04°、行星最高 0.25° |
| 紫微斗数 | 与 `iztro` 2.6.1 对比 120 个命盘的命宫、身宫、五行局、十四主星 | **120 / 120 完全一致** |
| 紫微星定位 | 与 iztro 文档算法对比 5 局 × 30 日 | 150 组全等，文档三示例全吻合 |
| 农历 | 15 个历年春节 + 30 组闰月 + 朔望自洽 + 往返一致 | 全部命中 |
| 八字 | 日柱 / 月柱 / 年柱 / 时柱锚点、400 天日柱连续性 | 全部通过 |
| JS 移植 | 与 Python 引擎逐案对拍 512 例（render 层 HTML 逐字比对） | **512 / 512 一致** |

运行内置自测（157 项断言，无需任何外部依赖）：

```bash
cd scripts && python self_test.py
```

可选的外部交叉验证脚本放在 `tools/`，需要额外安装依赖：

```bash
pip install ephem          # 行星精度对照
cd tools && python verify_astro.py

npm install iztro          # 紫微全星曜对照
cd tools && python verify_ziwei.py

cd tools && python verify_calendar.py   # 农历对照（无额外依赖）
```

### 开发中踩过并修掉的坑（都写进了回归测试）

1. **行星黄经整体偏 1.4°/百年** —— 行星用 J2000 根数、地球却用 of-date 太阳公式，坐标系混用。
   修法：统一在 J2000 系计算，最后加岁差转 of-date。
2. **所有行星位置全错** —— 地球日心坐标少加 180°（地球在日心系位于太阳反方向）。
3. **闰月与春节错位一个月** —— 置闰和冬至月按「精确时刻」判定；国标 GB/T 33661 应按「北京时间日期」判定。
   典型触发场景：2020-06-21 夏至与朔同日、2014-12-22 冬至与朔同日。
4. **子、丑两宫（两月）天干算错** —— 五虎遁公式里 `(zhi_i - 2)` 为负数时取模结果错误，应为 `(zhi_i - 2) % 12`。

JS 移植阶段又踩了几个（只靠逐案对拍抓得到，静态检查全都发现不了）：

5. **`pyRound(x * 10^n) / 10^n` 与 Python `round(x, n)` 不等价** ——
   Python 基于精确值做十进制舍入，先乘 10^n 会丢精度：
   `0.975` 的真实 double 是 `0.97499999999999997779…`，乘 100 后被舍入成
   **恰好 97.5**，于是误判成平局得 98，而 Python 看精确值得 97。
6. **Python `"%d" % 5.3` 是 5，JS `String(5.3)` 是 `"5.3"`** —— 起运虚岁本来就是小数。
7. **字典导出时用了 `sort_keys=True`**，打乱了 31 个文案字典的插入顺序，
   而渲染层是按插入顺序输出 HTML 的。

---

## 项目结构

```
mingli-oracle/
├── README.md                 # 本文件
├── SKILL.md                  # AI Agent 加载用的技能说明
├── scripts/
│   ├── almanac.py            # 天文历法引擎（节气/朔望/农历/干支/星历/真太阳时）
│   ├── bazi.py               # 四柱八字排盘
│   ├── ziwei.py              # 紫微斗数排盘
│   ├── astro.py              # 西洋占星本命盘
│   ├── divination.py         # 六爻 / 梅花易数
│   ├── plain.py              # 白话解读文案库（约 300 条）
│   ├── oracle.py             # 统一入口 + 自包含 HTML 命盘生成
│   ├── server.py             # 本地网页服务（浏览器填表排盘）
│   └── self_test.py          # 回归自测（157 项）
├── templates/app.html        # 前端交互界面（原生 JS，响应式）
├── references/               # 解读规则知识库
├── tools/                    # 与第三方库的交叉验证脚本
├── examples/                 # 生成好的示例命盘（可直接打开）
├── web/                      # 网页版（纯 JS 引擎，打开即用）
│   ├── js/                   # JS 引擎（Python 的移植，逐模块对照）
│   │   ├── kernel.js         # Python 语义对齐层（% / // / round / 浮点）
│   │   ├── almanac.js        # 天文历法底座
│   │   ├── bazi.js  ziwei.js  astro.js
│   │   ├── plain.js          # 白话解读（文案数据由 gen_plain_json.py 生成）
│   │   └── render.js         # HTML 渲染层
│   ├── bundle.py             # 把 js/*.js 拼成单文件 IIFE
│   ├── build_web.py          # 生成器：内联引擎成单个 HTML（零构建依赖）
│   ├── diff_py_js.py         # Python ↔ JS 逐案对拍（CI 门禁，512 例）
│   ├── gen_plain_json.py     # 把 plain.py 的文案字典机器导出为 JSON
│   ├── verify_dist.py        # 部署前校验产物
│   ├── test_load_chain.py    # 把产物里的引擎抠出来端到端跑
│   ├── check_secrets.py      # 扫仓库里的敏感信息
│   └── app.html              # 网页版模板（构建时填入引擎）
└── .github/workflows/ci.yml  # 自测 + 自动部署到 GitHub Pages
```

### 网页版是怎么工作的

```
scripts/*.py ──移植──► web/js/*.js ──打包──► web/dist/index.html ──► GitHub Pages
（唯一事实来源）            （第二实现）        （单文件 168KB）
                              │
                              └─ web/bundle.py 拼成 IIFE 内联进 HTML
```

网页版跑的是 `web/js/` 里的 **JS 引擎**，不是 Python。仓库里因此有两份实现 ——
这不是疏忽，是「打开即用」的代价（另一条路是下载 13MB 的 WASM 版 CPython）。

两份实现的一致性由 `web/diff_py_js.py` 保证：

```bash
python web/diff_py_js.py --layer all      # 512 个用例逐项比对
```

| 层 | 用例 | 覆盖 |
|---|---|---|
| almanac | 327 | 干支纪日、定气定朔、节气、行星黄经、真太阳时 |
| bazi | 85 | 四柱全流程、十神全覆盖、六十甲子旬空 |
| render | 48 | **HTML 逐字比对** |
| plain | 29 | 6 个白话解读函数 |
| ziwei | 15 | 命身宫、安星、十二宫、大限、流年 |
| astro | 8 | 十天体、上升天顶、相位、整宫制 |

render 层做的是**逐字符**比对，只报第一个不同的位置 —— 
结构比对抓不出「值对了但拼错位置」这类错误，而那恰好是渲染层最容易犯的错。

这条门禁确实有用：移植期间它抓出了几个静态检查完全发现不了的错误，
比如 Python 的 `round(x, 2)` 基于精确值舍入，而 JS 常见的
`pyRound(x * 100) / 100` 会因为乘法丢精度，把「略低于平局点的值」误判成平局。

`build_web.py` 与 `bundle.py` 都只用 Python 标准库，不需要 npm 或打包器。
CI 里每次 push 现建现部署，`web/dist/` 不入库。

自己构建：

```bash
python web/build_web.py          # 输出到 web/dist/index.html（168KB）
python web/verify_dist.py        # 校验产物（零外链、无占位符残留）
python web/test_load_chain.py    # 把产物里的引擎抠出来在 Node 里跑一遍
```

产物是**单文件**，`file://` 双击就能用，不需要起 HTTP 服务。

---

## 作为 AI Skill 使用

本仓库自带 `SKILL.md`，遵循通用 Agent Skill 规范。把整个目录复制到你的 agent skills 目录即可
（各家 agent 的位置不同，按你自己的来）：

```bash
# 常见几种，任选其一；也可用 $AGENT_SKILLS_DIR 之类你自己定义的环境变量
cp -r mingli-oracle ~/.claude/skills/          # Claude Code
cp -r mingli-oracle ~/.config/opencode/skills/  # OpenCode
# cp -r mingli-oracle <你的 agent 的 skills 目录>/
```

装好后让 agent 加载 `mingli-oracle` 这个 skill 即可调用。

Skill 中约定了三条铁律：

1. **排盘以脚本为准** —— 严禁口算、严禁凭记忆中的万年历改四柱。
2. **判定规则单一来源** —— 脚本负责算，`references/` 负责解释。
3. **先讲人话** —— 结论先行、术语必解释，不做绝对化断言。

---

## 免责声明

- 排盘结果按天文历法和传统命理规则计算得出，**解读部分仅供文化研究与娱乐参考**。
- 不得作为医疗、法律、投资、婚姻或任何人生决策的依据。
- 本项目**不会**预言死亡、制造恐惧或替代专业判断。
- 命盘显示的是倾向与可能性，人生方向由每个人自己的选择与努力决定。

---

## 许可证

[MIT License](LICENSE) —— 可自由使用、修改和分发。

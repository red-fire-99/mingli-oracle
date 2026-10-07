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

打开即用，不用装任何东西。填生日 → 出命盘 → 可切「说人话版 / 专业数据」→ 可保存成离线网页。

技术上是把本仓库 `scripts/` 里**同一份 Python 引擎**跑在浏览器里（Pyodide = CPython 的 WASM 构建），
不是另写了一个 JS 版本，所以**网页上的排盘结果和本地 CLI 完全一致**。

关于隐私：Pyodide 是纯前端运行时，没有后端服务器。**生辰只在你自己的浏览器里计算，
不发往任何地方**（页面除了首次下载 Pyodide 运行时外不产生任何网络请求）。
不想在浏览器里跑、或者网络访问 CDN 受限时，用下面的本地版。

### 首次加载

需要下载 Python 运行时：wasm 2.85MB + 标准库 2.20MB（服务端已做 brotli 压缩，
实际传输约 5MB）。之后浏览器会缓存，第二次打开基本是瞬时的。

页面内置**多镜像自动回退**（wasm 与标准库分别选源），国内走淘宝源通常 1~4 秒，
并会显示实际使用的来源与耗时。单个源超时或失败会自动换下一个，不会卡死。

---

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
├── web/                      # 网页版（Pyodide 跑同一份 Python 引擎）
│   ├── build_web.py          # 生成器：把引擎内联成单个 HTML（零构建依赖）
│   └── app.html              # 网页版模板（构建时会填入引擎源码）
└── .github/workflows/ci.yml  # 自测 + 自动部署到 GitHub Pages
```

### 网页版是怎么工作的

```
scripts/*.py  ──►  web/build_web.py  ──►  web/dist/index.html  ──►  GitHub Pages
（唯一一份引擎）      （内联成字符串）      （单文件，约 210KB）
                          │
                          └─ 浏览器加载 Pyodide，在 WebAssembly 里执行它
```

`build_web.py` 只用 Python 标准库，不需要 npm 或打包器，产物是单个 HTML 文件，
扔进任意静态托管都能跑。CI 里每次 push 现建现部署，`web/dist/` 不入库。

自己构建：

```bash
python web/build_web.py                    # 输出到 web/dist/
python -m http.server -d web/dist 8000     # 本地预览（必须用 http:// 而非 file://）
```

部署由 `.github/workflows/ci.yml` 自动完成：先跑 `self_test.py`（Python 3.8 与 3.12 各一遍），
**自测不过就不部署**，避免把坏版本推上线。

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

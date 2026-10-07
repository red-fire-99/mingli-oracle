# 更新日志

本项目使用语义化版本号（MAJOR.MINOR.PATCH）。

## [1.1.0] — 2026-10-07

**网页版改为纯 JS 引擎，打开即用。** 不再下载任何运行时。

### 新增

**零依赖网页版**
- `web/js/`：Python 引擎的纯 JS 移植，逐模块对照移植
  （`kernel` / `almanac` / `ziwei` / `plain` / `bazi` / `astro` / `render` / `engine`）
- `web/bundle.py`：把 ES 模块拼成单个 IIFE，构建时内联进 HTML
  —— 故产物是**一个自包含 HTML**，`file://` 双击也能跑，不需要 HTTP 服务
- `web/gen_plain_json.py`：把 `plain.py` 的 31 个文案字典**机器导出**为
  `web/js/plain-data.json`，避免手抄（手抄必然漂移，且漂移了没检查能发现）

**两份实现的一致性门禁**
- `web/diff_py_js.py` 扩到 6 层共 **512 个用例**：
  almanac 327 / bazi 85 / astro 8 / ziwei 15 / plain 29 / render 48
- render 层做 **HTML 逐字比对**，只报首个不同的字符位置 ——
  结构比对抓不出「值对了但拼错位置」的错误
- 已接入 CI，`--layer all` 任一不一致即失败

### 变更

- `web/build_web.py`：改为内联 JS 引擎，删掉 `fetch_pyodide.py` 调用
- `web/app.html`：删掉整个 Pyodide 加载状态机（约 190 行：多镜像源回退、
  双层索引推进、超时重试、字节进度），换成引擎就绪检查
- `web/verify_dist.py`：重写 —— 新增「零外部依赖」硬性检查
  （无外链 script、无 CDN 主机、无 `fetch`/动态 `import()`、CSS 无外部 `url()`）
- `web/test_load_chain.py`：改为把**产物里的引擎**抠出来在 Node 里端到端跑
- 删除 `web/fetch_pyodide.py`
- CI 少一步（不再需要下载 12MB 运行时），产物从 22MB 降到 168KB

### 修复

对拍抓出的错误（静态检查全都发现不了，其中三个是系统性的）：

1. **`pyRound(x * 10^n) / 10^n` 与 Python `round(x, n)` 不等价**
   Python 基于精确值做十进制舍入；先乘 10^n 再舍入，乘法本身就丢信息 ——
   `0.975` 的真实 double 是 `0.97499999999999997779…`，乘 100 后被舍入成
   **恰好 97.5**，于是走进「平局」分支得 98，而 Python 看精确值得 97。
   表现为占星相位「强度」0.97 被算成 0.98，连带相位排序错位。
   新增 `kernel.pyRoundN()`（`toFixed` 基于精确值正确舍入）

2. **Python `"%d" % 5.3` 是 5，JS `String(5.3)` 是 "5.3"**
   起运虚岁本来就是小数（"5.3-15.3岁"），HTML 逐字比对立刻抓到

3. **`gen_plain_json.py` 用了 `sort_keys=True`**，把 31 个字典的插入顺序打乱。
   渲染层按 `GLOSSARY` 顺序逐条输出 HTML，排序后网页上的名词解释顺序
   就和 Python 版不一致了

4. **紫微宫位的字段名是 `宫名` 不是 `宫位`** —— 查宫位永远返回空，
   表现为「官禄宫无主星」在所有命盘上都出现

5. JS number 分不清 `40` 与 `40.0`，而 Python float 一定带 `.0`

### 已知限制

- 网页版**不含六爻 / 梅花易数**（网页 UI 本来就没有占卜入口，
  `divination.py` 只在 CLI 里用）。JS 移植未覆盖 `divination.py`
- 生辰数据全在浏览器本地计算，不上传任何服务器

---

## [1.0.0] — 2026-10-07

首个可开源版本。

### 新增

**网页版（GitHub Pages）**
- `web/build_web.py`：把 `scripts/` 里**同一份引擎源码**内联成单个 HTML，
  浏览器用 Pyodide（CPython 的 WASM 构建）执行它 —— 不是另写一份 JS 实现，
  因此网页结果与本地 CLI 逐字一致。零构建依赖，只用标准库。
- `web/app.html`：网页版模板，含加载状态机（多镜像源回退、真实字节进度、
  超时重试、逐组合去重）
- `web/verify_dist.py`：构建产物校验（占位符替换、Python 语法配平、
  JS 括号配平、DOM id 引用、敏感信息）
- `web/test_load_chain.py`：把产物抠出来在 Node 里端到端跑
- `web/fetch_pyodide.py`：把 Pyodide 运行时下载到本地，网页随站点一起发布
- `web/check_secrets.py`：敏感信息扫描（路径泄漏、凭据）

**修复（开发中发现并回归固化）**
- 乱码：根因是 Windows 中文系统控制台代码页 936，`sys.stdout.encoding` 为 `gbk`，
  走管道时被按 UTF-8 解码。`almanac.py` 新增 `setup_console()`（切 65001 +
  两流重配 UTF-8），七个入口统一调用
- 隐私：`tools/verify_ziwei.py` 硬编码本机路径、`README.md` 暴露工具链目录，
  两者均已修正

**已知问题（已在 1.1.0 修复）**
- 网页版首次需下载约 5MB Python 运行时（已 brotli 压缩）
- 网页版曾两次完全打不开 / 卡在「已 3%」：
  - 进度条从未接线，且形参 `settledFlag` 与函数体 `settled` 不一致导致守卫失效
  - 自托管漏下 `pyodide.asm.js`（`pyodide.js` 里有动态 `import()` 指向它）

### 精度（实测，非声称）

| 项目 | 参照实现 | 结果 |
|---|---|---|
| 行星黄经 | `ephem`（VSOP87/ELP2000） | 太阳 0.01°、月亮 0.04°、行星 ≤ 0.25° |
| 紫微斗数 | `iztro 2.6.1` | 120 / 120 命盘完全一致 |
| 历法 | GB/T 33661 | 30 个闰月 + 15 个春节全对 |
| 内置自测 | — | 157 项全部通过 |
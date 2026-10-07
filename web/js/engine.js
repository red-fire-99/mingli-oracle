/* ===================================================================
   engine.js —— 网页版唯一入口：把各模块拼成一个 window.MingLi 对象
   ===================================================================
   构建时（build_web.py）把本文件与其依赖的 ES 模块**去 import 语句
   拼接**成一个 IIFE 内联进 HTML。这样页面加载即用，不发起任何网络请求，
   也不需要 import maps / 服务端模块支持（file:// 直接打开也能跑）。

   为什么不是保留 import：
     浏览器要加载 ES 模块必须走 HTTP，且 import 必须带 .js 后缀。
     GitHub Pages 上可行，但产物就不再是「一个自包含 HTML」，
     离线保存单文件也跑不起来。内联后单文件即全部。
   =================================================================== */

import { build, renderBazi, renderZiwei, renderAstro, renderPlain,
         renderGlossary, headline, run } from "./render.js";

const API = {
  run,
  build,
  renderBazi,
  renderZiwei,
  renderAstro,
  renderPlain,
  renderGlossary,
  headline,
  /** 版本号，由构建时注入 */
  // 版本号由构建时注入（见 web/build_web.py）。
  // 占位符**不含引号**：注入的是 json.dumps 的结果（自带引号），
  // 写成 "..." 会被替换成 ""1.0.0"" 这种双引号套双引号的坏代码。
  version: "__ENGINE_VERSION__",
};

if (typeof window !== "undefined") {
  window.MingLi = API;
}

export { API };
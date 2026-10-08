/**
 * 浮点补偿求和（Neumaier 算法）—— Python fsum() 的逐行对应。
 *
 * 为什么不能用朴素循环：CPython 3.12 给内置 sum() 加了这个算法，
 * 3.8/3.11 没有。差 1 ulp 会被下游放大成可见差异：
 *   朴素循环 total=10.239999999999998 -> 水 31.250000000000007 -> 显示 31.3%
 *   补偿求和 total=10.24              -> 水 31.25             -> 显示 31.2%
 * 也就是说：不实现补偿，同一份代码在 3.8 与 3.12 上会给出不同的五行百分比。
 */
export function fsum(values) {
  let s = 0.0, c = 0.0;
  for (const x of values) {
    const t = s + x;
    if (Math.abs(s) >= Math.abs(x)) c += (s - t) + x;
    else c += (x - t) + s;
    s = t;
  }
  return s + c;
}

/* ===================================================================
   kernel.js —— Python 语义在 JS 上的精确复刻
   ===================================================================
   移植 Python 引擎到 JS，最大的风险不是语法，而是**整数与取模的语义差异**。
   Python 与 JS 在以下几点行为不同，照抄必然出错：

   1. 取模：Python 的 % 是「向下取整取模」（floor mod），JS 的 % 是「向零截断」。
        -5 % 12   Python = 7     JS = -5
      本项目的 `month_gz` 恰好踩过这个坑（(zhi_i-2) 在子/丑宫为负），
      那个 bug 就是当年 Python 侧修的 —— 移植到 JS 必须再修一次，否则同样的错会回来。

   2. 整除：Python 的 // 是向下取整，JS 的 / 是向零截断。
        -7 // 2   Python = -4    JS = -3.5（再 | 截断得 -3）

   3. round()：Python 内置 round 用「银行家舍入」（四舍六入五成双），
      JS 的 Math.round 是「四舍五入」（.5 永远进位）。
        round(0.5)  Python = 0    JS = 1
        round(1.5)  Python = 2    JS = 2
        round(2.5)  Python = 2    JS = 3     ← 不一致
      almanac 的 _k_near() 用 round() 定朔序号，差 1 就是差一个月。

   4. 浮点：两者都是 IEEE 754 双精度，算术一一对应；但 Python 的 int() 是截断，
      JS 需要显式 Math.trunc / Math.floor。

   本文件把这些语义一一对齐，并提供日期运算（公历 ↔ 儒略日 ↔ 北京时间）。
   =================================================================== */

export const J2000 = 2451545.0;
export const UNIX_JD = 2440587.5;
export const BJ_OFFSET = 8 * 3600;   // 北京 UTC+8

/* ---------------- Python 语义对齐 ---------------- */

/** Python 的 %（向下取整取模）。结果与被除数同号。 */
export function pyMod(a, n) {
  const r = a % n;
  return r !== 0 && (r < 0) !== (n < 0) ? r + n : r;
}

/** Python 的 //（向下取整除）。 */
export function pyFloorDiv(a, n) {
  return Math.floor(a / n);
}

/** Python 内置 round()：银行家舍入（四舍六入五成双）。 */
export function pyRound(x) {
  const f = Math.floor(x);
  const diff = x - f;
  if (diff > 0.5) return f + 1;
  if (diff < 0.5) return f;
  return (f % 2 === 0) ? f : f + 1;   // 恰好 .5 时取偶
}

/** Python 的 int(x)：向零截断。 */
export function pyInt(x) {
  return x < 0 ? Math.ceil(x) : Math.floor(x);
}

/** Python 的 %360.0（浮点）。 */
export function norm360(x) {
  return pyMod(x, 360.0);
}

/**
 * Python 的 round(x, ndigits)：对**精确二进制值**做十进制舍入，且**平局取偶**。
 *
 * 两个坑，都要处理：
 *
 * 1) 不要用 pyRound(x * 10^n) / 10^n —— 乘法本身会丢精度：
 *    0.975 的真实 double 是 0.974999999999999977795...
 *    x*100 会被舍入成恰好 97.5，于是走进「平局」分支得 98；
 *    而 Python 看精确值知道它略低于 0.975，得 97。差 0.01。
 *    （占星相位「强度」字段真实出现过这个 bug：0.97 被算成 0.98）
 *
 * 2) toFixed 是「平局远离零」，Python 是「平局取偶」：
 *    toFixed(31.25, 1) = "31.3"，但 Python round(31.25, 1) = 31.2。
 *    （五行百分比条真实出现过：31.2% vs 31.3%）
 *
 * 判断「是否恰好落在平局点」不能靠 x*10^n —— 乘法会把
 * 0.9749999… 舍成恰好 97.5，掩盖真实情况。用 toPrecision(21) 取
 * double 的精确十进制展开，看第 nd+1 位是不是 5 且其后全 0。
 */
export function pyRoundN(x, nd) {
  if (!isFinite(x)) return x;
  if (nd === undefined || nd === null) return pyRound(x);

  const r = Number(x.toFixed(nd));

  // 精确十进制展开：31.25 -> "31.250000000000000000000"
  const ex = x.toPrecision(21);
  const neg = ex.charCodeAt(0) === 0x2d;            // '-'
  const dot = ex.indexOf(".");
  const intDigits = neg ? ex.slice(1, dot) : ex.slice(0, dot);
  const frac = dot < 0 ? "" : ex.slice(dot + 1);

  if (nd >= frac.length) return r;                  // 保留位已覆盖全部小数位
  if (frac[nd] !== "5") return r;                   // 不是平局点
  for (let i = nd + 1; i < frac.length; i++) {
    if (frac[i] !== "0") return r;                  // 后面还有非零位 -> 不是恰好平局
  }

  // 恰好平局：按 round-half-even 取偶。
  // toFixed 已经「远离零」地舍过一遍了，所以当保留位为**偶数**时
  // 需要往回收一格（正数减、负数加）—— 负数也要「往内」，
  // 因为远离零对负数就是变得��负。
  const keep = nd === 0 ? intDigits : frac.slice(0, nd);
  const lastDigit = Number(keep[keep.length - 1] || 0);
  if (lastDigit % 2 === 0) {
    const step = Math.pow(10, -nd);
    return Number((r + (neg ? step : -step)).toFixed(nd));
  }
  return r;
}

/* ---------------- 日期：公历 ↔ 儒略日（整数 JDN） ---------------- */

/** 格里历儒略日数（整数），与 Python almanac.jdn 逐行对应。 */
export function jdn(year, month, day) {
  const a = pyFloorDiv(14 - month, 12);
  const y = year + 4800 - a;
  const m = month + 12 * a - 3;
  return day + pyFloorDiv(153 * m + 2, 5) + 365 * y
    + pyFloorDiv(y, 4) - pyFloorDiv(y, 100) + pyFloorDiv(y, 400) - 32045;
}

/** JDN → {y, m, d}（公历）。逆运算，用查表反推避免负数取整问题。 */
export function civilFromJdn(z) {
  let a = z + 32044;
  const b = pyFloorDiv(4 * a + 3, 146097);
  const c = a - pyFloorDiv(146097 * b, 4);
  const dd = pyFloorDiv(4 * c + 3, 1461);
  const e = c - pyFloorDiv(1461 * dd, 4);
  const m = pyFloorDiv(5 * e + 2, 153);
  const day = e - pyFloorDiv(153 * m + 2, 5) + 1;
  const month = m + 3 - 12 * pyFloorDiv(m, 10);
  const year = 100 * b + dd - 4800 + pyFloorDiv(m, 10);
  return { y: year, m: month, d: day };
}

/** {y,m,d} → JDN 整数。 */
export function jdnOf(y, m, d) { return jdn(y, m, d); }

/**
 * JDN → Python `date.toordinal()` 的表示（自 0001-01-01 起的天数）。
 *
 * 两种纪日零点不同：JDN 0 对应 -4712-01-01，而 ordinal 1 对应 0001-01-01
 *（前推格里历），恒差 1721425。对拍时必须换算到同一纪日，否则会看到
 * 「差 1.72e6」这种看似天文数字、实则只是纪日不同的假不一致。
 */
export const ORDINAL_OFFSET = 1721425;
export function jdnToOrdinal(z) { return z - ORDINAL_OFFSET; }
export function ordinalToJdn(o) { return o + ORDINAL_OFFSET; }

/** JDN 加减天数。 */
export function addDays(z, n) { return z + n; }

/** 两个 JDN 相差天数（整数）。 */
export function daysBetween(z1, z2) { return z2 - z1; }

/* ---------------- 北京时间（墙钟） ----------------
   表示方式：t = 把「北京墙钟字段」当成 UTC 得到的 unix 秒数。
   这样 jd_from / tt→北京 的换算是纯线性，无需处理时区对象，
   也彻底避开 JS Date 的本地时区陷阱。
   ------------------------------------------------------------------- */

/** 北京墙钟 → unix 秒（字段按 UTC 解释）。 */
export function bjUnix(y, mo, d, H, Mi, S) {
  return Date.UTC(y, mo - 1, d, H || 0, Mi || 0, S || 0) / 1000;
}

/** unix 秒 → 北京墙钟字段（按 UTC 读取）。 */
export function bjCivilFromUnix(t) {
  const d = new Date(Math.round(t * 1000));
  return {
    y: d.getUTCFullYear(), m: d.getUTCMonth() + 1, d: d.getUTCDate(),
    H: d.getUTCHours(), Mi: d.getUTCMinutes(), S: d.getUTCSeconds(),
  };
}

/** 北京 datetime → 儒略日（同一瞬时）。对应 Python jd_from_datetime。 */
export function jdFromBjUnix(t) {
  return UNIX_JD + (t - BJ_OFFSET) / 86400.0;
}

/** 儒略日 → 北京墙钟的 unix 秒。 */
export function bjUnixFromJd(jdUtc) {
  return (jdUtc - UNIX_JD) * 86400.0 + BJ_OFFSET;
}

/* ---------------- 缓存 ---------------- */

/** 对应 Python 的 functools.lru_cache：按 key 缓存 fn 的返回值。 */
export function memo(fn) {
  const cache = new Map();
  return function (...args) {
    const key = args.join("\u0000");
    if (cache.has(key)) return cache.get(key);
    const v = fn.apply(this, args);
    cache.set(key, v);
    return v;
  };
}

/** 深拷贝结构化数据（用于避免调用方改到缓存里的对象）。 */
export function clone(o) {
  return JSON.parse(JSON.stringify(o));
}
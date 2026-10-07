#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 web/js/ 下的 ES 模块拼成一个可内联的 IIFE。

为什么需要这一步
----------------
浏览器加载 ES 模块必须走 HTTP（file:// 下 import 会被 CORS 拦掉），
而且 import 语句必须原样保留 —— 这意味着产物会散成多个 .js 文件，
「下载一个 HTML 双击就能用」做不到。

所以构建时把各模块的 import 语句**解析掉**，按依赖顺序拼进一个
IIFE：模块顶层的 import 变成对已声明 const 的引用，其余代码原样保留。

只做机械变换，不改任何逻辑 —— 排盘结果是否与 Python 一致由
web/diff_py_js.py 保证，这里只保证「拼起来能跑」。
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
JS = os.path.join(HERE, "js")

# 依赖顺序：被依赖的必须先声明。
# 每一项都是「文件名 -> 它 import 的模块名」的反向依赖，由下面的
# 拓扑排序自己算，这里只声明入口。
ENTRY = "engine.js"

IMPORT_RE = re.compile(
    r'^import\s+(?:([\w$]+)\s*,\s*)?(?:\{([^}]*)\}|\*\s+as\s+([\w$]+)|([\w$]+))'
    r'\s+from\s+["\']\./([\w.]+)["\'];\s*$',
    re.M)

# JSON import（plain.js 从 plain-data.json 取文案）
JSON_IMPORT_RE = re.compile(
    r'^import\s+(\w+)\s+from\s+["\']\./([\w.-]+\.json)["\']\s*'
    r'(?:with\s*\{\s*type:\s*["\']json["\']\s*\})?;\s*$',
    re.M)


def read(name):
    with io.open(os.path.join(JS, name), encoding="utf-8") as f:
        return f.read()


def parse_imports(src):
    """返回 [(本地别名, 源模块名, 导入的符号列表)]，并把 import 行标记删除。"""
    found = []

    def grab(m):
        found.append((m.group(1), m.group(2), m.group(3)))
        return ""

    src2 = re.sub(
        r'^import\s+\{([^}]*)\}\s+from\s+["\']\./([\w.]+)["\']\s*;',
        lambda m: found.append(("", m.group(2), m.group(1))) or "", src, flags=re.M)

    for m in JSON_IMPORT_RE.finditer(src2):
        found.append((m.group(1), m.group(2), "*JSON*"))

    src2 = JSON_IMPORT_RE.sub("", src2)

    # export { a, b } from "./x"  —— 本项目没用到，留个显式报错免得静默漏掉
    if re.search(r'^export\s+\{[^}]*\}\s+from', src2, flags=re.M):
        raise SystemExit("暂不支持 export ... from，请改成先 import 再 export")

    return src2, found


def toposort(entry):
    """按 import 关系排好序，返回 [模块名...]，被依赖者在前。"""
    order, seen = [], set()

    def visit(name, stack):
        if name in seen:
            return
        if name in stack:
            raise SystemExit("模块循环依赖: %s" % " -> ".join(stack + [name]))
        if not os.path.isfile(os.path.join(JS, name)):
            raise SystemExit("缺少模块 %s" % name)
        _, deps = parse_imports(read(name))
        for _, src, _syms in deps:
            if src.endswith(".json"):
                continue
            visit(src, stack + [name])
        seen.add(name)
        order.append(name)

    visit(entry, [])
    return order


def strip_export(src):
    """把 export 关键字去掉，让模块内容变成 IIFE 里的普通声明。

    export const X -> const X
    export function f -> function f
    export { a, b }   -> 删掉（符号已在同一作用域）
    export default X  -> 删掉
    """
    src = re.sub(r'^export\s+(const|let|var|function|class|async)\s',
                 r'\1 ', src, flags=re.M)
    # export { a, b as c };
    src = re.sub(r'^export\s+\{[^}]*\}\s*;\s*$', "", src, flags=re.M)
    src = re.sub(r'^export\s+default\s+.*$', "", src, flags=re.M)
    if re.search(r'^export\s', src, flags=re.M):
        raise SystemExit("仍有未处理的 export，请检查")
    return src


def bundle(entry=ENTRY):
    """拼成**扁平**的单作用域代码。

    每个模块各自包一层 IIFE，而不是把所有模块的顶层声明平铺到一个作用域：
    平铺会撞名（almanac 与 astro 都导出 SIGNS，且各自都有内部 helper），
    撞名时报的是 "Identifier 'X' has already been declared"，
    很难看出是哪两个模块冲突。

    改为每模块一个 IIFE 后：
      - 顶层 const/function 天然私有，不会撞名
      - 跨模块 import 变成「先声明一个 let，再在模块体里赋值」，
        赋值发生在 IIFE 内，模块之间按依赖序执行，时序有保证
      - 只有确实 export 的符号才会泄漏到下一层
    """
    order = toposort(entry)
    parts = []
    # 模块名 -> 它的 IIFE 返回对象（只含 export 的符号）
    for name in order:
        src = read(name)
        src, deps = parse_imports(src)

        exported = _exported_names(read(name))
        body = strip_export(src).strip()

        chunk = ["/* ====== %s ====== */" % name]
        # 依赖：模块按依赖序求值，被依赖者此时已是完整对象，
        # 所以直接 const 解构赋值即可（无需 let 占位，避免 TDZ）。
        # 代价是不支持循环依赖 —— 本项目依赖图是 DAG，
        # toposort() 遇到环会直接报错，不会静默产出坏代码。
        for alias, src_mod, syms in deps:
            if src_mod.endswith(".json"):
                chunk.append("const %s = JSON.parse(%s);"
                             % (alias, _js_str(read(src_mod))))
                continue
            if syms == "*JSON*":
                continue
            mod = src_mod[:-3]
            # import { a as b } ->  本地叫 b，取的是 mod.a
            pairs = []
            for n in [x.strip() for x in syms.split(",") if x.strip()]:
                if " as " in n:
                    orig, local = [x.strip() for x in n.split(" as ", 1)]
                    pairs.append((local, orig))
                else:
                    pairs.append((n, n))
            # 逐个 const 声明。不能用 `const a, b = {...}`：
            # 那只有 b 被初始化，a 会报 "Missing initializer"。
            for local, orig in pairs:
                chunk.append("const %s = %s.%s;" % (local, mod, orig))
        chunk.append(body)
        if exported:
            chunk.append("return { %s };" % ", ".join(exported))
        parts.append("\n".join(chunk))

    # 入口：把每个模块的返回值存成 const <mod>，最后一个就是出口
    out = []
    for i, name in enumerate(order):
        out.append("const %s = (function () {\n%s\n})();"
                   % (name[:-3], parts[i]))
    return order, "\n\n".join(out)


_EXPORT_BLOCK = re.compile(r'^export\s+\{([^}]*)\}\s*;', re.M)
_EXPORT_DECL = re.compile(r'^export\s+(?:const|let|var|function|class|async)\s+'
                          r'(?:function\s+)?([\w$]+)', re.M)


def _exported_names(src):
    """模块通过 export 暴露的全部符号名。"""
    names = []
    for m in _EXPORT_BLOCK.finditer(src):
        for n in m.group(1).split(","):
            n = n.strip()
            if not n:
                continue
            names.append(n.split(" as ")[-1].strip())
    for m in _EXPORT_DECL.finditer(src):
        names.append(m.group(1))
    if "export default" in src:
        raise SystemExit("暂不支持 export default")
    # 去重并保序
    seen, out = set(), []
    for n in names:
        if n not in seen:
            seen.add(n); out.append(n)
    return out


def _js_str(s):
    """把 Python 字符串转成 JS 字符串字面量（转义交给 json）。"""
    import json
    return json.dumps(s, ensure_ascii=False)


def main(argv=None):
    p = argparse.ArgumentError if False else None  # noqa
    import argparse
    ap = argparse.ArgumentParser(description="把 ES 模块拼成单文件 IIFE")
    ap.add_argument("--entry", default=ENTRY)
    ap.add_argument("--out", default=None, help="输出文件；不给则打到 stdout")
    a = ap.parse_args(argv)

    order, code = bundle(a.entry)
    body = "(function () {\n\"use strict\";\n%s\n})();" % code

    if a.out:
        with io.open(a.out, "w", encoding="utf-8") as f:
            f.write(body)
        print("已生成 %s (%d 个模块, %.1f KB)"
              % (a.out, len(order), os.path.getsize(a.out) / 1024.0))
        print("顺序: %s" % " -> ".join(order))
    else:
        sys.stdout.write(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
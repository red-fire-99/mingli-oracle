#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""命理神机 · 本地排盘服务。

在你自己电脑上跑一个小服务，用浏览器填个表就能排盘。
纯 Python 标准库，不联网、不上传任何数据，关掉窗口就没了。

用法
----
    python server.py                     # 本机访问 http://127.0.0.1:8765
    python server.py --port 9000         # 换个端口
    python server.py --host 0.0.0.0      # 让同一 WiFi 下的手机也能打开
    python server.py --no-browser        # 不自动开浏览器

按 Ctrl+C 停止。
"""

import argparse
import io
import json
import os
import socket
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import oracle as O
import plain as PL

MAX_BODY = 64 * 1024
HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "..", "templates", "app.html")


def build_page():
    """读取页面模板，并把命盘的样式表注入到 <style id="oracle-css"> 里。

    注意：只替换占位符，绝不做全局的 </head> 之类替换——
    否则会把 <script> 里的字符串一起改坏。
    """
    with io.open(TEMPLATE, encoding="utf-8") as f:
        html = f.read()
    return html.replace("/*__ORACLE_CSS__*/", O.CSS)


PAGE = None


def render_pro(data):
    """专业区：四柱 / 紫微 / 占星 / 名词解释。"""
    parts = []
    if "八字" in data:
        parts.append(O.render_bazi(data["八字"]))
    if "紫微" in data:
        parts.append(O.render_ziwei(data["紫微"]))
    if "占星" in data:
        parts.append(O.render_astro(data["占星"]))
    parts.append(O.render_glossary())
    return "".join(parts)


def do_paipan(body):
    """收到表单数据 → 排盘 → 返回结果。"""
    solar = tuple(body["solar"]) if body.get("solar") else None
    lunar = tuple(body["lunar"]) if body.get("lunar") else None
    if not solar and not lunar:
        return {"ok": False, "error": "请先填出生日期。"}

    leap = bool(body.get("leap"))
    hour = tuple(body["hour"]) if body.get("hour") else None
    shichen = body.get("shichen")
    sex = body.get("sex") or "男"
    if sex not in ("男", "女"):
        return {"ok": False, "error": "请选择性别（男或女）。"}

    lon = body.get("lon")
    lat = body.get("lat")
    place = body.get("place")
    try:
        lon = float(lon) if lon not in (None, "") else None
        lat = float(lat) if lat not in (None, "") else None
    except (TypeError, ValueError):
        return {"ok": False, "error": "经纬度请填数字，例如 116.4 / 39.9。"}

    # 范围检查（友好提示，而不是抛异常）
    y = (solar[0] if solar else lunar[0])
    if not (1900 <= y <= 2100):
        return {"ok": False, "error": "年份需要在 1900—2100 之间，请检查一下生日。"}
    if hour is not None and not (0 <= hour[0] <= 23 and 0 <= hour[1] <= 59):
        return {"ok": False, "error": "出生时间不太对，小时是 0—23，分钟是 0—59。"}

    try:
        data = O.build(solar=solar, lunar=lunar, leap=leap, hour=hour, shichen=shichen,
                       sex=sex, place=place, lat=lat, lon=lon)
    except ValueError as e:
        return {"ok": False, "error": friendly(str(e))}
    except Exception as e:  # 兜底，别把堆栈甩给用户
        return {"ok": False, "error": "排盘时出了点问题：%s" % friendly(str(e))}

    return {
        "ok": True,
        "headline": PL.headline(data),
        "plain_html": O.render_plain(data),
        "pro_html": render_pro(data),
    }


def friendly(msg):
    """把内部异常翻译成用户看得懂的话。"""
    if "闰" in msg:
        return "这个农历年份好像没有闰月，请检查一下闰月的勾选。"
    if "找不到农历" in msg:
        return "这个农历日期不存在，请检查年、月、日是否填对。"
    if "只有" in msg and "天" in msg:
        return "这个农历月没有这么多天，请检查一下日期。"
    if "超出推算范围" in msg:
        return "这个日期超出可算范围（1900—2100 年），请换一个日期。"
    return msg or "请检查一下填写的内容。"


class Handler(BaseHTTPRequestHandler):
    server_version = "MingLiOracle/1.0"

    def _send(self, code, ctype, payload):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionAbortedError):
            pass

    def _json(self, obj, code=200):
        self._send(code, "application/json; charset=utf-8",
                   json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            self._send(200, "text/html; charset=utf-8", PAGE.encode("utf-8"))
        elif path == "/api/health":
            self._json({"ok": True, "service": "命理神机"})
        else:
            self._send(404, "text/plain; charset=utf-8", "页面不存在".encode("utf-8"))

    def do_POST(self):
        path = self.path.split("?")[0]
        if path != "/api/paipan":
            self._json({"ok": False, "error": "接口不存在"}, 404)
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if n <= 0 or n > MAX_BODY:
            self._json({"ok": False, "error": "请求内容为空或过大。"}, 400)
            return
        try:
            body = json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            self._json({"ok": False, "error": "数据格式不对，请刷新页面重试。"}, 400)
            return
        try:
            self._json(do_paipan(body))
        except Exception as e:
            self._json({"ok": False, "error": "服务出错了：%s" % friendly(str(e))}, 500)

    def log_message(self, fmt, *args):
        # 只记一行简短日志，别刷屏
        sys.stderr.write("  · %s\n" % (fmt % args))


def lan_ip():
    """取本机局域网 IP（只读本机网卡信息，不往外发数据）。"""
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if not ip.startswith("127.") and ":" not in ip:
                return ip
    except Exception:
        pass
    return None


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    p = argparse.ArgumentParser(
        description="命理神机 · 本地排盘服务 —— 在浏览器里填表排盘，不联网、不上传")
    p.add_argument("--host", default="127.0.0.1",
                   help="监听地址。默认 127.0.0.1（只有本机能访问）；填 0.0.0.0 让手机也能访问")
    p.add_argument("--port", type=int, default=8765, help="端口，默认 8765")
    p.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    a = p.parse_args(argv)

    global PAGE
    PAGE = build_page()

    httpd = None
    port = a.port
    for _ in range(12):
        try:
            httpd = ThreadingHTTPServer((a.host, port), Handler)
            break
        except OSError:
            port += 1
    if httpd is None:
        print("端口都被占用了，请用 --port 换一个。")
        return 1

    url = "http://127.0.0.1:%d" % port
    print("=" * 56)
    print("  命理神机 · 本地排盘服务已启动")
    print("=" * 56)
    print("  电脑上打开：  %s" % url)
    if a.host == "0.0.0.0":
        ip = lan_ip()
        if ip:
            print("  手机上打开：  http://%s:%d   （手机要和电脑连同一个 WiFi）" % (ip, port))
        else:
            print("  手机上打开：  请先查一下电脑的局域网 IP")
    else:
        print("  想让手机也能用：重新运行并加上 --host 0.0.0.0")
    print()
    print("  数据只在你自己的电脑上算，不上传、不联网。")
    print("  停止服务：按 Ctrl+C")
    print("=" * 56)

    if not a.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止，再见。")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

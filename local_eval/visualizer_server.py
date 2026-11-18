# -*- coding: utf-8 -*-
"""
Lightweight local HTTP server with Byte-Range (206 Partial Content) support
for instant MP4 scrubbing, frame-by-frame stepping, and playback rate control.
"""
import os
import re
import sys
import socket
import webbrowser
import mimetypes
import urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

ROOT_DIR = r"D:\pingpang源文件汇总"
PUBLIC_DATA_DIR = os.path.join(ROOT_DIR, "participant", "pingpang", "public_data")
HTML_PATH = os.path.join(ROOT_DIR, "pingpong_visualizer.html")

mimetypes.add_type("video/mp4", ".mp4")
mimetypes.add_type("text/html; charset=utf-8", ".html")
mimetypes.add_type("application/json; charset=utf-8", ".json")


class RangeRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        if args and str(args[1]).startswith(("4", "5")):
            super().log_message(format, *args)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Accept-Ranges", "bytes")
        super().end_headers()

    def do_HEAD(self):
        self._serve(send_body=False)

    def do_GET(self):
        self._serve(send_body=True)

    def _resolve_path(self, req_path):
        clean_path = urllib.parse.unquote(req_path.split("?", 1)[0])
        if clean_path in ("/", "/index.html", "/pingpong_visualizer.html"):
            return HTML_PATH

        rel = clean_path.lstrip("/")
        cand1 = os.path.abspath(os.path.join(PUBLIC_DATA_DIR, rel))
        if cand1.startswith(os.path.abspath(PUBLIC_DATA_DIR)) and os.path.isfile(cand1):
            return cand1

        cand2 = os.path.abspath(os.path.join(ROOT_DIR, rel))
        if cand2.startswith(os.path.abspath(ROOT_DIR)) and os.path.isfile(cand2):
            return cand2

        return None

    def _serve(self, send_body=True):
        file_path = self._resolve_path(self.path)
        if not file_path or not os.path.isfile(file_path):
            self.send_error(404, f"File not found: {self.path}")
            return

        file_size = os.path.getsize(file_path)
        ctype, _ = mimetypes.guess_type(file_path)
        if not ctype:
            ctype = "application/octet-stream"

        range_header = self.headers.get("Range")
        if range_header:
            m = re.match(r"bytes=(\d+)-(\d*)", range_header)
            if m:
                start = int(m.group(1))
                end = int(m.group(2)) if m.group(2) else file_size - 1
                end = min(end, file_size - 1)
                if start > end or start >= file_size:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{file_size}")
                    self.end_headers()
                    return
                length = end - start + 1
                self.send_response(206)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                self.send_header("Content-Length", str(length))
                self.end_headers()
                if send_body:
                    with open(file_path, "rb") as f:
                        f.seek(start)
                        remaining = length
                        while remaining > 0:
                            chunk = f.read(min(65536, remaining))
                            if not chunk:
                                break
                            try:
                                self.wfile.write(chunk)
                            except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                                break
                            remaining -= len(chunk)
                return

        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(file_size))
        self.end_headers()
        if send_body:
            with open(file_path, "rb") as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    try:
                        self.wfile.write(chunk)
                    except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                        break


def is_port_open(host, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def main():
    port = int(os.environ.get("VIS_PORT", "8765"))
    url = f"http://127.0.0.1:{port}/"
    auto_open = "--open" in sys.argv

    if is_port_open("127.0.0.1", port):
        print(f"[Visualizer Server] Already running at {url}", flush=True)
        if auto_open:
            webbrowser.open(url)
        return

    server = ThreadingHTTPServer(("127.0.0.1", port), RangeRequestHandler)
    print(f"[Visualizer Server] Running at {url}", flush=True)
    if auto_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import json
import os
import re
import socket
import sys
import time
import urllib.parse
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


ROOT = os.path.dirname(os.path.abspath(__file__))
ALLOWED = {
    "工作紀錄資料.json": "工作紀錄",
    "專案資料.json": "專案",
}
BACKUP_KEEP = 200


def pick_port():
    for port in range(8765, 8795):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("找不到可用的本機連接埠")


def safe_path(name):
    if name not in ALLOWED:
        raise ValueError("不允許的檔名")
    return os.path.join(ROOT, name)


def read_json_array(name):
    path = safe_path(name)
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return []
    with open(path, "r", encoding="utf-8-sig") as f:
        text = f.read().strip()
    if not text:
        return []
    data = json.loads(text)
    if isinstance(data, dict):
        if name == "工作紀錄資料.json" and isinstance(data.get("records"), list):
            return data["records"]
        if name == "專案資料.json" and isinstance(data.get("projects"), list):
            return data["projects"]
    if not isinstance(data, list):
        raise ValueError("JSON 內容必須是陣列")
    return data


def write_json_array(name, data, backup):
    if not isinstance(data, list):
        raise ValueError("寫入內容必須是陣列")
    path = safe_path(name)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)
    if backup:
        write_backup(ALLOWED[name], data)


def write_backup(prefix, data):
    backup_dir = os.path.join(ROOT, "備份")
    os.makedirs(backup_dir, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    path = os.path.join(backup_dir, f"{prefix}_{stamp}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    prune_backups(backup_dir, prefix)


def prune_backups(backup_dir, prefix):
    pat = re.compile(rf"^{re.escape(prefix)}_.*\.json$")
    names = sorted(n for n in os.listdir(backup_dir) if pat.match(n))
    for name in names[:-BACKUP_KEEP]:
        try:
            os.remove(os.path.join(backup_dir, name))
        except OSError:
            pass


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/status":
            self.send_json(200, {"ok": True})
            return
        if parsed.path == "/api/read":
            try:
                qs = urllib.parse.parse_qs(parsed.query)
                name = qs.get("name", [""])[0]
                self.send_json(200, {"ok": True, "data": read_json_array(name)})
            except Exception as e:
                self.send_json(400, {"ok": False, "error": str(e)})
            return
        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/api/write":
            self.send_json(404, {"ok": False, "error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            payload = json.loads(body)
            write_json_array(payload.get("name", ""), payload.get("data"), bool(payload.get("backup")))
            self.send_json(200, {"ok": True})
        except Exception as e:
            self.send_json(400, {"ok": False, "error": str(e)})


def main():
    os.chdir(ROOT)
    port = pick_port()
    url = f"http://127.0.0.1:{port}/工作紀錄.html"
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print("Safari 版工作紀錄已啟動")
    print(url)
    print("要停止時，關閉這個終端機視窗或按 Control+C。")
    webbrowser.get("safari").open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("啟動失敗：", e, file=sys.stderr)
        sys.exit(1)

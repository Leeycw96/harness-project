import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from urllib.parse import unquote, urlparse

from .db import initialize
from .service import InventoryError, cancel_reservation, confirm_reservation, get_inventory, reserve_stock


def make_handler(database):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = urlparse(self.path).path
            try:
                if path == "/health":
                    self.send_json(200, {"status": "ok"})
                elif path.startswith("/inventory/"):
                    self.send_json(200, get_inventory(database, unquote(path.removeprefix("/inventory/"))))
                else:
                    self.send_json(404, {"error": "接口不存在"})
            except InventoryError as error:
                self.send_json(error.status, {"error": error.message})

        def do_POST(self):
            path = urlparse(self.path).path
            try:
                if path == "/reservations":
                    try:
                        payload = json.loads(self.read_body())
                    except (ValueError, UnicodeError) as error:
                        raise InventoryError(400, "请求体必须是JSON对象") from error
                    if not isinstance(payload, dict):
                        raise InventoryError(400, "请求体必须是JSON对象")
                    result = reserve_stock(database, payload.get("order_id"), payload.get("sku"), payload.get("quantity"))
                else:
                    segments = path.split("/")
                    if len(segments) != 4 or segments[1] != "reservations" or segments[3] not in ("confirm", "cancel"):
                        raise InventoryError(404, "接口不存在")
                    if self.read_body():
                        raise InventoryError(400, "确认和取消不接受请求体")
                    try:
                        order_id = unquote(segments[2], errors="strict")
                    except UnicodeError as error:
                        raise InventoryError(400, "订单路径编码错误") from error
                    operation = confirm_reservation if segments[3] == "confirm" else cancel_reservation
                    result = operation(database, order_id)
                self.send_json(200, result)
            except InventoryError as error:
                self.send_json(error.status, {"error": error.message})

        def read_body(self):
            if self.headers.get("Transfer-Encoding") is not None:
                raise InventoryError(400, "不支持此请求体编码")
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError as error:
                raise InventoryError(400, "Content-Length格式错误") from error
            if length < 0:
                raise InventoryError(400, "Content-Length格式错误")
            return self.rfile.read(length)

        def send_json(self, status, payload):
            data = json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True)
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    initialize(args.db)
    ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(args.db)).serve_forever()


if __name__ == "__main__":
    main()

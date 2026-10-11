from contextlib import closing
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.parse import quote

from inventory.db import connect, initialize
from inventory.http import make_handler


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = str(Path(self.directory.name) / "inventory.sqlite3")
        initialize(self.database)
        self.start_server()
        self.addCleanup(self.stop_server)

    def start_server(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.database))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def request(self, method, path, body=None, headers=None):
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=15)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            data = response.read()
            self.assertEqual(response.getheader("Content-Type"), "application/json; charset=utf-8")
            self.assertEqual(int(response.getheader("Content-Length")), len(data))
            return response.status, json.loads(data)
        finally:
            connection.close()

    def reserve(self, order="order", sku="DEMO", quantity=2):
        return self.request("POST", "/reservations", json.dumps({
            "order_id": order, "sku": sku, "quantity": quantity,
        }).encode(), {"Content-Type": "application/json"})

    def assert_error(self, status, result):
        self.assertEqual(result[0], status)
        self.assertEqual(set(result[1]), {"error"})
        self.assertIsInstance(result[1]["error"], str)
        self.assertTrue(result[1]["error"])

    def test_create_confirm_and_query_use_real_persistent_service(self):
        status, reserved = self.reserve()
        self.assertEqual(status, 200)
        self.assertEqual(reserved, {"order_id": "order", "sku": "DEMO", "quantity": 2, "status": "RESERVED"})
        self.assertEqual(self.reserve(), (status, reserved))
        self.assertEqual(self.request("GET", "/inventory/DEMO")[1]["available"], 8)
        confirmed = self.request("POST", "/reservations/order/confirm")
        self.assertEqual(confirmed, (200, {**reserved, "status": "CONFIRMED"}))
        self.assertEqual(self.request("POST", "/reservations/order/confirm"), confirmed)
        self.assert_error(409, self.request("POST", "/reservations/order/cancel"))
        self.assertEqual(self.request("GET", "/inventory/DEMO"), (200, {
            "sku": "DEMO", "name": "示例商品", "stock": 8, "reserved": 0, "available": 8,
        }))
        self.stop_server()
        initialize(self.database)
        self.start_server()
        self.assertEqual(self.reserve(), confirmed)
        self.assertEqual(self.request("GET", "/inventory/DEMO")[1]["stock"], 8)

    def test_encoded_order_segment_and_cancel_retries(self):
        order = " 订单/a%?b#c "
        status, reserved = self.reserve(order)
        self.assertEqual(status, 200)
        path = f"/reservations/{quote(order, safe='')}/cancel"
        cancelled = self.request("POST", path)
        self.assertEqual(cancelled, (200, {**reserved, "status": "CANCELLED"}))
        self.assertEqual(self.request("POST", path), cancelled)
        self.assertEqual(self.reserve(order), cancelled)
        self.assert_error(409, self.request("POST", f"/reservations/{quote(order, safe='')}/confirm"))
        self.assertEqual(self.request("GET", "/inventory/DEMO")[1]["available"], 10)

    def test_exact_stock_reservation_retries_cancel_and_confirm(self):
        reserved = self.reserve(order="boundary-order", quantity=10)
        self.assertEqual(reserved, (200, {
            "order_id": "boundary-order", "sku": "DEMO", "quantity": 10, "status": "RESERVED",
        }))
        self.assertEqual(self.reserve(order="boundary-order", quantity=10), reserved)
        exhausted = (200, {
            "sku": "DEMO", "name": "示例商品", "stock": 10, "reserved": 10, "available": 0,
        })
        self.assertEqual(self.request("GET", "/inventory/DEMO"), exhausted)
        self.assert_error(409, self.reserve(order="excess", quantity=1))
        self.assertEqual(self.request("GET", "/inventory/DEMO"), exhausted)
        cancelled = self.request("POST", "/reservations/boundary-order/cancel")
        self.assertEqual(cancelled, (200, {**reserved[1], "status": "CANCELLED"}))
        self.assertEqual(self.request("POST", "/reservations/boundary-order/cancel"), cancelled)
        self.assertEqual(self.request("GET", "/inventory/DEMO"), (200, {
            "sku": "DEMO", "name": "示例商品", "stock": 10, "reserved": 0, "available": 10,
        }))
        self.assertEqual(self.reserve(order="confirmed-order", quantity=10)[0], 200)
        confirmed = self.request("POST", "/reservations/confirmed-order/confirm")
        self.assertEqual(confirmed, (200, {
            "order_id": "confirmed-order", "sku": "DEMO", "quantity": 10, "status": "CONFIRMED",
        }))
        self.assertEqual(self.request("POST", "/reservations/confirmed-order/confirm"), confirmed)
        self.assertEqual(self.request("GET", "/inventory/DEMO"), (200, {
            "sku": "DEMO", "name": "示例商品", "stock": 0, "reserved": 0, "available": 0,
        }))

    def test_create_rejects_malformed_or_nonobject_json(self):
        for body in (b"", b"{", b"[]", b"null", b"true", b"1", b'"text"', b"\xff"):
            with self.subTest(body=body):
                self.assert_error(400, self.request("POST", "/reservations", body))
        self.assertEqual(self.request("GET", "/inventory/DEMO")[1]["reserved"], 0)

    def test_create_rejects_missing_fields_and_invalid_quantities(self):
        bodies = [{}, {"order_id": "order"}, {"order_id": "order", "sku": "DEMO"}]
        bodies.extend({"order_id": "order", "sku": "DEMO", "quantity": value}
                      for value in (True, 1.0, "1", 0, -1, 9223372036854775808))
        for body in bodies:
            with self.subTest(body=body):
                self.assert_error(400, self.request("POST", "/reservations", json.dumps(body)))
        self.assertEqual(self.request("GET", "/inventory/DEMO")[1]["reserved"], 0)

    def test_protocol_errors_are_explicit(self):
        self.assert_error(400, self.request("POST", "/reservations", b"{}", {"Content-Length": "bad"}))
        self.assert_error(400, self.request("POST", "/reservations", b"", {"Content-Length": "-1"}))
        self.assert_error(400, self.request("POST", "/reservations", b"{}", {"Transfer-Encoding": "chunked"}))
        self.assert_error(400, self.request("POST", "/reservations/%20/confirm"))
        self.assert_error(400, self.request("POST", "/reservations/order/cancel", b"{}"))

    def test_http_errors_preserve_stock(self):
        self.assert_error(404, self.reserve(sku="missing"))
        self.assert_error(409, self.reserve(quantity=11))
        self.assertEqual(self.reserve()[0], 200)
        self.assert_error(409, self.reserve(quantity=3))
        self.assert_error(409, self.reserve(sku="missing"))
        self.assert_error(404, self.request("POST", "/reservations/missing/confirm"))
        self.assert_error(404, self.request("POST", "/reservations/missing/cancel"))
        self.assertEqual(self.request("GET", "/inventory/DEMO")[1]["reserved"], 2)

    def test_health_and_unknown_routes(self):
        self.assertEqual(self.request("GET", "/health"), (200, {"status": "ok"}))
        self.assert_error(404, self.request("GET", "/inventory/missing"))
        for path in ("/unknown", "/reservations/order/unknown", "/reservations/raw/slash/confirm"):
            self.assert_error(404, self.request("POST", path))

    def test_database_failure_is_a_json_error_and_rolls_back(self):
        self.reserve()
        with closing(connect(self.database)) as connection:
            connection.executescript("""
                CREATE TRIGGER fail_confirmation BEFORE UPDATE OF status ON reservations
                BEGIN SELECT RAISE(ABORT, 'forced database failure'); END;
            """)
        self.assert_error(500, self.request("POST", "/reservations/order/confirm"))
        self.assertEqual(self.request("GET", "/inventory/DEMO")[1]["stock"], 10)
        self.assertEqual(self.request("GET", "/inventory/DEMO")[1]["reserved"], 2)

"""独立 QA 补充验收。业务实现保持不变，使用临时数据库和本地 HTTP。"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from http.client import HTTPConnection
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest

PROJECT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(PROJECT))

from inventory import service
from inventory.db import connect, initialize


class IndependentServiceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = str(Path(self.directory.name) / "qa.sqlite3")
        initialize(self.database)

    def assert_counts(self, stock, reserved, available, sku="DEMO"):
        actual = service.get_inventory(self.database, sku)
        self.assertEqual((actual["stock"], actual["reserved"], actual["available"]),
                         (stock, reserved, available))

    def assert_error(self, status, operation, *args):
        with self.assertRaises(service.InventoryError) as raised:
            operation(self.database, *args)
        self.assertEqual(raised.exception.status, status)

    def concurrent_terminal_retries(self, operation, terminal, stock):
        service.reserve_stock(self.database, "same", "DEMO", 3)
        barrier = threading.Barrier(8)

        def apply(_):
            barrier.wait()
            return operation(self.database, "same")

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(apply, range(8)))
        expected = {"order_id": "same", "sku": "DEMO", "quantity": 3, "status": terminal}
        self.assertEqual(results, [expected] * 8)
        self.assert_counts(stock, 0, stock)
        with closing(connect(self.database)) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM reservations").fetchone()[0], 1)

    def test_concurrent_duplicate_confirmations_deduct_once(self):
        self.concurrent_terminal_retries(service.confirm_reservation, "CONFIRMED", 7)

    def test_concurrent_duplicate_cancellations_release_once(self):
        self.concurrent_terminal_retries(service.cancel_reservation, "CANCELLED", 10)

    def test_distinct_products_keep_separate_inventory_and_global_order_identity(self):
        with closing(connect(self.database)) as connection:
            connection.execute("INSERT INTO products VALUES (?, ?, ?)", ("中文 /%?", "第二商品", 4))
        service.reserve_stock(self.database, "first", "DEMO", 2)
        service.reserve_stock(self.database, "second", "中文 /%?", 4)
        self.assert_error(409, service.reserve_stock, "first", "中文 /%?", 2)
        self.assert_counts(10, 2, 8)
        self.assert_counts(4, 4, 0, "中文 /%?")
        service.confirm_reservation(self.database, "second")
        self.assert_counts(0, 0, 0, "中文 /%?")
        service.cancel_reservation(self.database, "first")
        self.assert_counts(10, 0, 10)

    def test_cancel_failed_updates_leave_reservation_unchanged(self):
        service.reserve_stock(self.database, "order", "DEMO", 3)
        for statement, status in (("RAISE(ABORT, 'qa')", 500), ("RAISE(IGNORE)", 409)):
            with self.subTest(statement=statement):
                with closing(connect(self.database)) as connection:
                    connection.executescript(f"""
                        CREATE TRIGGER qa_cancel BEFORE UPDATE OF status ON reservations
                        BEGIN SELECT {statement}; END;
                    """)
                self.assert_error(status, service.cancel_reservation, "order")
                self.assert_counts(10, 3, 7)
                self.assertEqual(service.reserve_stock(self.database, "order", "DEMO", 3)["status"], "RESERVED")
                with closing(connect(self.database)) as connection:
                    connection.execute("DROP TRIGGER qa_cancel")


class IndependentProcessTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = str(Path(self.directory.name) / "restart.sqlite3")
        self.process = None
        self.addCleanup(self.stop)

    def start(self):
        with closing(socket.socket()) as allocation:
            allocation.bind(("127.0.0.1", 0))
            self.port = allocation.getsockname()[1]
        self.process = subprocess.Popen(
            [sys.executable, "-m", "inventory.http", "--db", self.database, "--port", str(self.port)],
            cwd=PROJECT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            self.assertIsNone(self.process.poll(), "HTTP 进程提前退出")
            try:
                self.assertEqual(self.request("GET", "/health"), (200, {"status": "ok"}))
                return
            except OSError:
                time.sleep(0.02)
        self.fail("HTTP 进程未能启动")

    def stop(self):
        if self.process is not None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
            self.process = None

    def request(self, method, path, body=None):
        with closing(HTTPConnection("127.0.0.1", self.port, timeout=15)) as connection:
            connection.request(method, path, None if body is None else json.dumps(body).encode())
            response = connection.getresponse()
            return response.status, json.loads(response.read())

    def reserve(self, order_id):
        return self.request("POST", "/reservations", {"order_id": order_id, "sku": "DEMO", "quantity": 2})

    def test_real_process_restart_preserves_all_states_and_inventory(self):
        self.start()
        original = {}
        for order_id in ("reserved", "confirmed", "cancelled"):
            status, original[order_id] = self.reserve(order_id)
            self.assertEqual(status, 200)
        for order_id, action, state in (("confirmed", "confirm", "CONFIRMED"),
                                        ("cancelled", "cancel", "CANCELLED")):
            original[order_id]["status"] = state
            self.assertEqual(self.request("POST", f"/reservations/{order_id}/{action}"), (200, original[order_id]))
        expected = (200, {"sku": "DEMO", "name": "示例商品", "stock": 8, "reserved": 2, "available": 6})
        self.assertEqual(self.request("GET", "/inventory/DEMO"), expected)
        self.stop()
        self.start()
        self.assertEqual(self.request("GET", "/inventory/DEMO"), expected)
        for order_id, result in original.items():
            self.assertEqual(self.reserve(order_id), (200, result))
        self.assertEqual(self.request("GET", "/inventory/DEMO"), expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)

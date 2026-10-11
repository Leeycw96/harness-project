"""Independent real-process checks for the approved stock boundary fix."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from http.client import HTTPConnection
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import unittest


PROJECT = Path(__file__).resolve().parents[5]
REPORT = Path(__file__).resolve().parent
BASELINE = "3d3609954e2c4e86674951a5fd400ae154bc6bdb"
COMMIT = "68e10818b5172db30a3bc2cd082ff8beab516436"
ORIGINAL = json.loads((PROJECT / ".keel/eval/bug-http-evidence.json").read_text())
EVIDENCE = {"baseline_commit": BASELINE, "fix_commit": COMMIT, "scenarios": {}}


def request(port, method, path, payload=None):
    connection = HTTPConnection("127.0.0.1", port, timeout=15)
    try:
        body = json.dumps(payload).encode() if payload is not None else None
        connection.request(method, path, body, {"Content-Type": "application/json"})
        response = connection.getresponse()
        data = response.read()
        assert response.getheader("Content-Type") == "application/json; charset=utf-8"
        assert int(response.getheader("Content-Length")) == len(data)
        return {"status": response.status, "body": json.loads(data)}
    finally:
        connection.close()


@contextmanager
def running_service(root, database):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    log = database.parent / f"server-{port}.log"
    with log.open("wb") as output:
        process = subprocess.Popen(
            [sys.executable, "-m", "inventory.http", "--db", str(database), "--port", str(port)],
            cwd=root, stdout=output, stderr=output,
        )
        try:
            deadline = time.monotonic() + 5
            while True:
                if process.poll() is not None:
                    raise AssertionError(log.read_text())
                try:
                    if request(port, "GET", "/health") == {"status": 200, "body": {"status": "ok"}}:
                        break
                except (OSError, TimeoutError):
                    pass
                if time.monotonic() >= deadline:
                    raise AssertionError("Real HTTP process did not become healthy")
                time.sleep(0.02)
            yield port
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            EVIDENCE.setdefault("server_logs", []).append({
                "root": str(root), "database": str(database), "exit_code": process.returncode,
                "log": log.read_text(),
            })


def inventory(stock, reserved, available):
    return {"status": 200, "body": {
        "sku": "DEMO", "name": "示例商品", "stock": stock,
        "reserved": reserved, "available": available,
    }}


class BoundaryChecks(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        (REPORT / "qa-http-evidence.json").write_text(
            json.dumps(EVIDENCE, ensure_ascii=False, indent=2) + "\n",
        )

    def test_baseline_reproduces_recorded_http_failure(self):
        with tempfile.TemporaryDirectory(prefix="qa-boundary-baseline-") as directory:
            root = Path(directory)
            archive = subprocess.check_output(["git", "archive", BASELINE, "inventory"], cwd=PROJECT)
            with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
                bundle.extractall(root, filter="data")
            with running_service(root, root / "baseline.sqlite3") as port:
                trace = {
                    "source_commit": BASELINE, "kind": "real_local_http",
                    "before": request(port, "GET", "/inventory/DEMO"),
                    "request": ORIGINAL["request"],
                    "actual": request(port, "POST", "/reservations", ORIGINAL["request"]["body"]),
                    "expected": ORIGINAL["expected"],
                    "after_failed_request": request(port, "GET", "/inventory/DEMO"),
                    "control_quantity_9": request(port, "POST", "/reservations", {
                        "order_id": "control-order", "sku": "DEMO", "quantity": 9,
                    }),
                }
                EVIDENCE["scenarios"]["baseline_original_request"] = trace
                self.assertEqual(trace, ORIGINAL)

    def test_original_request_lifecycle_survives_real_process_restarts(self):
        with tempfile.TemporaryDirectory(prefix="qa-boundary-fixed-") as directory:
            database = Path(directory) / "fixed.sqlite3"
            trace = {}
            EVIDENCE["scenarios"]["fixed_original_request"] = trace
            with running_service(PROJECT, database) as port:
                trace["before"] = request(port, "GET", "/inventory/DEMO")
                self.assertEqual(trace["before"], ORIGINAL["before"])
                trace["request"] = ORIGINAL["request"]
                trace["actual"] = request(port, "POST", "/reservations", ORIGINAL["request"]["body"])
                reserved = {"status": 200, "body": {
                    "order_id": "boundary-order", "sku": "DEMO", "quantity": 10, "status": "RESERVED",
                }}
                self.assertEqual(trace["actual"], reserved)
                trace["after_original_request"] = request(port, "GET", "/inventory/DEMO")
                self.assertEqual(trace["after_original_request"], inventory(10, 10, 0))
            with running_service(PROJECT, database) as port:
                trace["after_restart"] = request(port, "GET", "/inventory/DEMO")
                self.assertEqual(trace["after_restart"], inventory(10, 10, 0))
                trace["retry"] = request(port, "POST", "/reservations", ORIGINAL["request"]["body"])
                self.assertEqual(trace["retry"], reserved)
                for name, body in (("quantity_conflict", {"order_id": "boundary-order", "sku": "DEMO", "quantity": 9}),
                                   ("sku_conflict", {"order_id": "boundary-order", "sku": "missing", "quantity": 10}),
                                   ("overbooking", {"order_id": "excess", "sku": "DEMO", "quantity": 1})):
                    trace[name] = request(port, "POST", "/reservations", body)
                    self.assertEqual(trace[name]["status"], 409)
                    self.assertEqual(request(port, "GET", "/inventory/DEMO"), inventory(10, 10, 0))
                cancelled = {"status": 200, "body": {**reserved["body"], "status": "CANCELLED"}}
                trace["cancel"] = request(port, "POST", "/reservations/boundary-order/cancel")
                self.assertEqual(trace["cancel"], cancelled)
                self.assertEqual(request(port, "POST", "/reservations/boundary-order/cancel"), cancelled)
                self.assertEqual(request(port, "POST", "/reservations", ORIGINAL["request"]["body"]), cancelled)
                self.assertEqual(request(port, "POST", "/reservations/boundary-order/confirm")["status"], 409)
                trace["after_cancel"] = request(port, "GET", "/inventory/DEMO")
                self.assertEqual(trace["after_cancel"], inventory(10, 0, 10))
            with running_service(PROJECT, database) as port:
                self.assertEqual(request(port, "POST", "/reservations", ORIGINAL["request"]["body"]), cancelled)
                body = {"order_id": "confirmed-order", "sku": "DEMO", "quantity": 10}
                self.assertEqual(request(port, "POST", "/reservations", body)["status"], 200)
                confirmed = {"status": 200, "body": {**body, "status": "CONFIRMED"}}
                trace["confirm"] = request(port, "POST", "/reservations/confirmed-order/confirm")
                self.assertEqual(trace["confirm"], confirmed)
                self.assertEqual(request(port, "POST", "/reservations/confirmed-order/confirm"), confirmed)
                self.assertEqual(request(port, "POST", "/reservations/confirmed-order/cancel")["status"], 409)
                trace["after_confirm"] = request(port, "GET", "/inventory/DEMO")
                self.assertEqual(trace["after_confirm"], inventory(0, 0, 0))
            with running_service(PROJECT, database) as port:
                trace["confirmed_after_restart"] = request(port, "POST", "/reservations", body)
                self.assertEqual(trace["confirmed_after_restart"], confirmed)
                self.assertEqual(request(port, "GET", "/inventory/DEMO"), inventory(0, 0, 0))
                self.assertEqual(request(port, "POST", "/reservations", {
                    "order_id": "another-order", "sku": "DEMO", "quantity": 1,
                })["status"], 409)

    def test_concurrent_full_stock_http_orders_cannot_oversell(self):
        with tempfile.TemporaryDirectory(prefix="qa-boundary-concurrent-") as directory:
            with running_service(PROJECT, Path(directory) / "concurrent.sqlite3") as port:
                barrier = threading.Barrier(4)

                def reserve(number):
                    barrier.wait()
                    return request(port, "POST", "/reservations", {
                        "order_id": f"full-{number}", "sku": "DEMO", "quantity": 10,
                    })

                with ThreadPoolExecutor(max_workers=4) as executor:
                    results = list(executor.map(reserve, range(4)))
                after = request(port, "GET", "/inventory/DEMO")
                EVIDENCE["scenarios"]["concurrent_full_stock_requests"] = {"results": results, "after": after}
                self.assertEqual(sum(result["status"] == 200 for result in results), 1)
                self.assertEqual(sum(result["status"] == 409 for result in results), 3)
                self.assertEqual(after, inventory(10, 10, 0))
                successful = next(result for result in results if result["status"] == 200)
                self.assertEqual(successful["body"]["quantity"], 10)
                self.assertEqual(successful["body"]["status"], "RESERVED")


if __name__ == "__main__":
    unittest.main(verbosity=2)

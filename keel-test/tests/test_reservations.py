from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest

from inventory import service
from inventory.db import connect, initialize


class ReservationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = str(Path(self.directory.name) / "inventory.sqlite3")
        initialize(self.database)

    def assert_inventory(self, stock, reserved, available):
        inventory = service.get_inventory(self.database, "DEMO")
        self.assertEqual(inventory, {
            "sku": "DEMO", "name": "示例商品", "stock": stock,
            "reserved": reserved, "available": available,
        })

    def assert_error(self, status, operation, *args):
        with self.assertRaises(service.InventoryError) as raised:
            operation(self.database, *args)
        self.assertEqual(raised.exception.status, status)

    def test_inventory_without_reservations(self):
        self.assert_inventory(10, 0, 10)

    def test_reserve_exact_available_stock_and_reject_overbooking(self):
        self.assertEqual(service.reserve_stock(self.database, "first", "DEMO", 10), {
            "order_id": "first", "sku": "DEMO", "quantity": 10, "status": "RESERVED",
        })
        self.assert_inventory(10, 10, 0)
        self.assert_error(409, service.reserve_stock, "second", "DEMO", 1)
        self.assert_inventory(10, 10, 0)

    def test_reserve_last_available_unit_with_existing_reservation(self):
        service.reserve_stock(self.database, "first", "DEMO", 9)
        self.assert_inventory(10, 9, 1)
        last = service.reserve_stock(self.database, "last", "DEMO", 1)
        self.assertEqual(last, {
            "order_id": "last", "sku": "DEMO", "quantity": 1, "status": "RESERVED",
        })
        self.assertEqual(service.reserve_stock(self.database, "last", "DEMO", 1), last)
        self.assert_inventory(10, 10, 0)
        self.assert_error(409, service.reserve_stock, "excess", "DEMO", 1)
        self.assert_inventory(10, 10, 0)

    def test_retries_are_idempotent_and_conflicts_take_precedence(self):
        original = service.reserve_stock(self.database, "order", "DEMO", 2)
        self.assertEqual(service.reserve_stock(self.database, "order", "DEMO", 2), original)
        self.assert_error(409, service.reserve_stock, "order", "DEMO", 3)
        self.assert_error(409, service.reserve_stock, "order", "missing", 2)
        self.assert_inventory(10, 2, 8)

    def test_invalid_reservation_inputs_do_not_write(self):
        invalid = [
            ("", "DEMO", 1), (" \t", "DEMO", 1), (None, "DEMO", 1),
            (1, "DEMO", 1), ("order", "", 1), ("order", " \n", 1),
            ("order", None, 1), ("order", 1, 1),
        ]
        invalid.extend(("order", "DEMO", value) for value in (
            None, True, False, 0, -1, 1.0, "1", [], {}, 9223372036854775808,
        ))
        for arguments in invalid:
            with self.subTest(arguments=arguments):
                self.assert_error(400, service.reserve_stock, *arguments)
        self.assert_inventory(10, 0, 10)
        with closing(connect(self.database)) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM reservations").fetchone()[0], 0)

    def test_unknown_product_and_insufficient_stock_leave_no_reservation(self):
        self.assert_error(404, service.reserve_stock, "order", "missing", 1)
        self.assert_error(409, service.reserve_stock, "order", "DEMO", 11)
        self.assertEqual(service.reserve_stock(self.database, "order", "DEMO", 1)["status"], "RESERVED")
        self.assert_inventory(10, 1, 9)

    def test_identifiers_are_preserved_exactly(self):
        original = service.reserve_stock(self.database, " Order / 中文 ", "DEMO", 1)
        other = service.reserve_stock(self.database, " order / 中文 ", "DEMO", 1)
        self.assertEqual(original["order_id"], " Order / 中文 ")
        self.assertEqual(other["order_id"], " order / 中文 ")
        self.assert_error(404, service.reserve_stock, "third", " DEMO ", 1)
        self.assert_inventory(10, 2, 8)

    def test_maximum_integer_quantity_is_supported(self):
        maximum = 9223372036854775807
        with closing(connect(self.database)) as connection:
            connection.execute("UPDATE products SET stock = ? WHERE sku = 'DEMO'", (maximum,))
        self.assertEqual(service.reserve_stock(self.database, "order", "DEMO", maximum)["quantity"], maximum)
        self.assert_inventory(maximum, maximum, 0)
        self.assertEqual(service.confirm_reservation(self.database, "order")["status"], "CONFIRMED")
        self.assert_inventory(0, 0, 0)

    def test_confirm_deducts_once_and_preserves_available_stock(self):
        service.reserve_stock(self.database, "order", "DEMO", 3)
        service.reserve_stock(self.database, "other", "DEMO", 2)
        confirmed = service.confirm_reservation(self.database, "order")
        self.assertEqual(confirmed, {
            "order_id": "order", "sku": "DEMO", "quantity": 3, "status": "CONFIRMED",
        })
        self.assertEqual(service.confirm_reservation(self.database, "order"), confirmed)
        self.assertEqual(service.reserve_stock(self.database, "order", "DEMO", 3), confirmed)
        self.assert_error(409, service.cancel_reservation, "order")
        self.assert_inventory(7, 2, 5)

    def test_cancel_releases_once_and_never_reactivates(self):
        service.reserve_stock(self.database, "order", "DEMO", 3)
        cancelled = service.cancel_reservation(self.database, "order")
        self.assertEqual(cancelled, {
            "order_id": "order", "sku": "DEMO", "quantity": 3, "status": "CANCELLED",
        })
        self.assertEqual(service.cancel_reservation(self.database, "order"), cancelled)
        self.assertEqual(service.reserve_stock(self.database, "order", "DEMO", 3), cancelled)
        self.assert_error(409, service.confirm_reservation, "order")
        self.assert_error(409, service.reserve_stock, "order", "DEMO", 4)
        self.assert_inventory(10, 0, 10)

    def test_unknown_or_invalid_order_cannot_transition(self):
        for operation in (service.confirm_reservation, service.cancel_reservation):
            with self.subTest(operation=operation.__name__):
                self.assert_error(404, operation, "missing")
                for order_id in ("", " \n", None, 1):
                    self.assert_error(400, operation, order_id)
        self.assert_inventory(10, 0, 10)

    def test_concurrent_reservations_cannot_oversell(self):
        barrier = threading.Barrier(16)

        def reserve(number):
            barrier.wait()
            try:
                return service.reserve_stock(self.database, f"order-{number}", "DEMO", 1)
            except service.InventoryError as error:
                return error.status

        with ThreadPoolExecutor(max_workers=16) as executor:
            results = list(executor.map(reserve, range(16)))
        self.assertEqual(sum(isinstance(result, dict) for result in results), 10)
        self.assertEqual(results.count(409), 6)
        self.assert_inventory(10, 10, 0)

    def test_concurrent_retries_create_one_reservation(self):
        barrier = threading.Barrier(8)

        def reserve(_):
            barrier.wait()
            return service.reserve_stock(self.database, "order", "DEMO", 2)

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(reserve, range(8)))
        self.assertTrue(all(result == results[0] for result in results))
        self.assert_inventory(10, 2, 8)

    def test_concurrent_confirm_and_cancel_reach_only_one_terminal_state(self):
        service.reserve_stock(self.database, "order", "DEMO", 3)
        barrier = threading.Barrier(2)

        def transition(operation):
            barrier.wait()
            try:
                return operation(self.database, "order")
            except service.InventoryError as error:
                return error.status

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(transition, (service.confirm_reservation, service.cancel_reservation)))
        self.assertEqual(sum(isinstance(result, dict) for result in results), 1)
        self.assertEqual(results.count(409), 1)
        terminal = next(result["status"] for result in results if isinstance(result, dict))
        self.assert_inventory(7 if terminal == "CONFIRMED" else 10, 0, 7 if terminal == "CONFIRMED" else 10)
        self.assertEqual(service.reserve_stock(self.database, "order", "DEMO", 3)["status"], terminal)

    def test_reinitialize_preserves_stock_and_all_reservation_states(self):
        for order_id in ("reserved", "confirmed", "cancelled"):
            service.reserve_stock(self.database, order_id, "DEMO", 2)
        service.confirm_reservation(self.database, "confirmed")
        service.cancel_reservation(self.database, "cancelled")
        initialize(self.database)
        self.assert_inventory(8, 2, 6)
        for order_id, status in (("reserved", "RESERVED"), ("confirmed", "CONFIRMED"), ("cancelled", "CANCELLED")):
            self.assertEqual(service.reserve_stock(self.database, order_id, "DEMO", 2)["status"], status)

    def test_migration_preserves_existing_products_and_enforces_constraints(self):
        old_database = str(Path(self.directory.name) / "old.sqlite3")
        with closing(connect(old_database)) as connection:
            connection.executescript((Path(__file__).parents[1] / "inventory/migrations/001_products.sql").read_text())
            connection.execute("INSERT INTO products VALUES ('DEMO', '原商品', 4)")
        initialize(old_database)
        self.assertEqual(service.get_inventory(old_database, "DEMO")["stock"], 4)
        self.assertEqual(service.get_inventory(old_database, "DEMO")["name"], "原商品")
        with closing(connect(old_database)) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM reservations").fetchone()[0], 0)
            for values in ((None, "DEMO", 1, "RESERVED"), ("o", "missing", 1, "RESERVED"),
                           ("o", "DEMO", 0, "RESERVED"), ("o", "DEMO", 1.5, "RESERVED"),
                           ("o", "DEMO", 1, "UNKNOWN")):
                with self.subTest(values=values), self.assertRaises(sqlite3.IntegrityError):
                    connection.execute("INSERT INTO reservations VALUES (?, ?, ?, ?)", values)
            self.assertIn("idx_reservations_sku_status", [row[1] for row in connection.execute("PRAGMA index_list(reservations)")])

    def test_inconsistent_stock_cannot_be_confirmed(self):
        service.reserve_stock(self.database, "order", "DEMO", 3)
        with closing(connect(self.database)) as connection:
            connection.execute("UPDATE products SET stock = 2 WHERE sku = 'DEMO'")
        self.assert_error(409, service.confirm_reservation, "order")
        self.assertEqual(service.reserve_stock(self.database, "order", "DEMO", 3)["status"], "RESERVED")
        self.assert_inventory(2, 3, -1)

    def test_confirm_rolls_back_stock_when_status_update_fails(self):
        service.reserve_stock(self.database, "order", "DEMO", 3)
        with closing(connect(self.database)) as connection:
            connection.executescript("""
                CREATE TRIGGER fail_confirmation BEFORE UPDATE OF status ON reservations
                BEGIN SELECT RAISE(ABORT, 'forced database failure'); END;
            """)
        self.assert_error(500, service.confirm_reservation, "order")
        self.assert_inventory(10, 3, 7)
        self.assertEqual(service.reserve_stock(self.database, "order", "DEMO", 3)["status"], "RESERVED")
        with closing(connect(self.database)) as connection:
            connection.execute("DROP TRIGGER fail_confirmation")
        self.assertEqual(service.confirm_reservation(self.database, "order")["status"], "CONFIRMED")

    def test_confirm_checks_both_conditional_update_counts(self):
        service.reserve_stock(self.database, "order", "DEMO", 3)
        for table, column in (("products", "stock"), ("reservations", "status")):
            with self.subTest(table=table):
                with closing(connect(self.database)) as connection:
                    connection.executescript(f"""
                        CREATE TRIGGER ignore_update BEFORE UPDATE OF {column} ON {table}
                        BEGIN SELECT RAISE(IGNORE); END;
                    """)
                self.assert_error(409, service.confirm_reservation, "order")
                self.assert_inventory(10, 3, 7)
                with closing(connect(self.database)) as connection:
                    connection.execute("DROP TRIGGER ignore_update")

    def test_write_lock_timeout_returns_retryable_error_without_writes(self):
        with closing(connect(self.database)) as connection:
            connection.execute("BEGIN IMMEDIATE")
            self.assert_error(503, service.reserve_stock, "order", "DEMO", 1)
            connection.rollback()
        self.assert_inventory(10, 0, 10)
        self.assertEqual(service.reserve_stock(self.database, "order", "DEMO", 1)["status"], "RESERVED")

    def test_database_open_failure_is_reported(self):
        bad_database = str(Path(self.directory.name) / "missing" / "inventory.sqlite3")
        for operation, arguments in ((service.reserve_stock, ("order", "DEMO", 1)),
                                     (service.confirm_reservation, ("order",)),
                                     (service.cancel_reservation, ("order",))):
            with self.subTest(operation=operation.__name__), self.assertRaises(service.InventoryError) as raised:
                operation(bad_database, *arguments)
            self.assertEqual(raised.exception.status, 500)

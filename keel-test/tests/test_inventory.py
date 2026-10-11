from pathlib import Path
import tempfile
import unittest
from inventory.db import initialize
from inventory.service import InventoryError, get_inventory


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = str(Path(self.directory.name) / "inventory.sqlite3")
        initialize(self.database)

    def test_existing_stock(self):
        self.assertEqual(get_inventory(self.database, "DEMO")["stock"], 10)

    def test_unknown_product(self):
        with self.assertRaises(InventoryError) as raised:
            get_inventory(self.database, "missing")
        self.assertEqual(raised.exception.status, 404)

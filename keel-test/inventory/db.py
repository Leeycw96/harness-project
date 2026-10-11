from contextlib import closing
from pathlib import Path
import sqlite3


def connect(path):
    connection = sqlite3.connect(path, timeout=10, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize(path):
    with closing(connect(path)) as connection:
        for migration in sorted((Path(__file__).parent / "migrations").glob("*.sql")):
            connection.executescript(migration.read_text())
        connection.execute("INSERT OR IGNORE INTO products VALUES (?, ?, ?)", ("DEMO", "示例商品", 10))

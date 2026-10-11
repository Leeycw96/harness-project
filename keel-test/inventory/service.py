from contextlib import closing, contextmanager
import sqlite3

from .db import connect


class InventoryError(Exception):
    def __init__(self, status, message):
        self.status = status
        self.message = message
        super().__init__(message)


def get_inventory(path, sku):
    try:
        with closing(connect(path)) as connection:
            product = connection.execute("""
                SELECT p.sku, p.name, p.stock, COALESCE(SUM(r.quantity), 0) AS reserved,
                       p.stock - COALESCE(SUM(r.quantity), 0) AS available
                FROM products AS p
                LEFT JOIN reservations AS r ON r.sku = p.sku AND r.status = 'RESERVED'
                WHERE p.sku = ?
                GROUP BY p.sku, p.name, p.stock
            """, (sku,)).fetchone()
    except sqlite3.Error as error:
        raise _database_error(error) from error
    if product is None:
        raise InventoryError(404, "商品不存在")
    return dict(product)


def _database_error(error):
    code = getattr(error, "sqlite_errorcode", 0) & 0xff
    if code in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
        return InventoryError(503, "数据库繁忙，请重试")
    return InventoryError(500, "数据库错误")


@contextmanager
def _write_transaction(path):
    try:
        with closing(connect(path)) as connection:
            connection.execute("BEGIN IMMEDIATE")
            # sqlite 的连接上下文在成功时提交，异常时回滚；外层负责关闭连接。
            with connection:
                yield connection
    except sqlite3.Error as error:
        raise _database_error(error) from error


def _validate_identifier(value, name):
    if not isinstance(value, str) or not value.strip():
        raise InventoryError(400, f"{name}必须是非空白字符串")


def _reservation(connection, order_id):
    reservation = connection.execute(
        "SELECT order_id, sku, quantity, status FROM reservations WHERE order_id = ?", (order_id,),
    ).fetchone()
    if reservation is None:
        raise InventoryError(404, "预占不存在")
    return dict(reservation)


def reserve_stock(path, order_id, sku, quantity):
    _validate_identifier(order_id, "order_id")
    _validate_identifier(sku, "sku")
    if type(quantity) is not int or not 1 <= quantity <= 9223372036854775807:
        raise InventoryError(400, "quantity必须是1至9223372036854775807的整数")
    with _write_transaction(path) as connection:
        existing = connection.execute(
            "SELECT order_id, sku, quantity, status FROM reservations WHERE order_id = ?", (order_id,),
        ).fetchone()
        if existing is not None:
            if existing["sku"] != sku or existing["quantity"] != quantity:
                raise InventoryError(409, "订单预占冲突")
            result = dict(existing)
        else:
            product = connection.execute("SELECT stock FROM products WHERE sku = ?", (sku,)).fetchone()
            if product is None:
                raise InventoryError(404, "商品不存在")
            reserved = connection.execute(
                "SELECT COALESCE(SUM(quantity), 0) FROM reservations WHERE sku = ? AND status = 'RESERVED'",
                (sku,),
            ).fetchone()[0]
            if quantity > product["stock"] - reserved:
                raise InventoryError(409, "库存不足")
            connection.execute(
                "INSERT INTO reservations (order_id, sku, quantity, status) VALUES (?, ?, ?, 'RESERVED')",
                (order_id, sku, quantity),
            )
            result = _reservation(connection, order_id)
    return result


def confirm_reservation(path, order_id):
    _validate_identifier(order_id, "order_id")
    with _write_transaction(path) as connection:
        reservation = _reservation(connection, order_id)
        if reservation["status"] == "CANCELLED":
            raise InventoryError(409, "已取消，不能确认")
        if reservation["status"] == "RESERVED":
            updated = connection.execute(
                "UPDATE products SET stock = stock - ? WHERE sku = ? AND stock >= ?",
                (reservation["quantity"], reservation["sku"], reservation["quantity"]),
            )
            if updated.rowcount != 1:
                raise InventoryError(409, "库存数据不一致")
            updated = connection.execute(
                "UPDATE reservations SET status = 'CONFIRMED' WHERE order_id = ? AND status = 'RESERVED'",
                (order_id,),
            )
            if updated.rowcount != 1:
                raise InventoryError(409, "库存数据不一致")
            reservation = _reservation(connection, order_id)
    return reservation


def cancel_reservation(path, order_id):
    _validate_identifier(order_id, "order_id")
    with _write_transaction(path) as connection:
        reservation = _reservation(connection, order_id)
        if reservation["status"] == "CONFIRMED":
            raise InventoryError(409, "已确认，不能取消")
        if reservation["status"] == "RESERVED":
            updated = connection.execute(
                "UPDATE reservations SET status = 'CANCELLED' WHERE order_id = ? AND status = 'RESERVED'",
                (order_id,),
            )
            if updated.rowcount != 1:
                raise InventoryError(409, "预占数据不一致")
            reservation = _reservation(connection, order_id)
    return reservation

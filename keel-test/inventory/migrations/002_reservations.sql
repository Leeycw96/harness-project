CREATE TABLE IF NOT EXISTS reservations (
    order_id TEXT PRIMARY KEY NOT NULL,
    sku TEXT NOT NULL REFERENCES products(sku),
    quantity INTEGER NOT NULL CHECK (typeof(quantity) = 'integer' AND quantity > 0),
    status TEXT NOT NULL CHECK (status IN ('RESERVED', 'CONFIRMED', 'CANCELLED'))
);
CREATE INDEX IF NOT EXISTS idx_reservations_sku_status ON reservations(sku, status);

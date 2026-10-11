CREATE TABLE IF NOT EXISTS products (
    sku TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    stock INTEGER NOT NULL CHECK (stock >= 0)
);

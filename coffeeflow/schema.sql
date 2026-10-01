PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE CHECK(length(name) BETWEEN 1 AND 80)
);
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE RESTRICT,
    name TEXT NOT NULL CHECK(length(name) BETWEEN 1 AND 120),
    description TEXT NOT NULL DEFAULT '',
    price_cents INTEGER NOT NULL CHECK(price_cents BETWEEN 1 AND 10000000),
    image_url TEXT NOT NULL DEFAULT '',
    is_available INTEGER NOT NULL DEFAULT 1 CHECK(is_available IN (0,1)),
    is_deleted INTEGER NOT NULL DEFAULT 0 CHECK(is_deleted IN (0,1))
);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);
CREATE TABLE IF NOT EXISTS admins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_hash TEXT NOT NULL,
    customer_name TEXT NOT NULL,
    phone TEXT NOT NULL,
    pickup_at TEXT NOT NULL,
    comment TEXT NOT NULL DEFAULT '',
    total_cents INTEGER NOT NULL CHECK(total_cents > 0),
    status TEXT NOT NULL DEFAULT 'new'
        CHECK(status IN ('new','accepted','preparing','ready','completed','cancelled')),
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_orders_status_id ON orders(status, id);
CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    product_name TEXT NOT NULL,
    unit_price_cents INTEGER NOT NULL CHECK(unit_price_cents > 0),
    quantity INTEGER NOT NULL CHECK(quantity BETWEEN 1 AND 20),
    UNIQUE(order_id, product_id)
);
PRAGMA user_version = 1;

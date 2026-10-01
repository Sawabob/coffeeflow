from ..db import get_db, transaction
from ..errors import APIError
from ..validation import utc_now

TRANSITIONS = {
    'new': {'accepted', 'cancelled'},
    'accepted': {'preparing', 'cancelled'},
    'preparing': {'ready', 'cancelled'},
    'ready': {'completed', 'cancelled'},
    'completed': set(), 'cancelled': set(),
}


def read_order(order_id, owner=None, admin=False, db=None):
    db = db or get_db()
    row = db.execute('SELECT * FROM orders WHERE id=?', (order_id,)).fetchone()
    # 404 does not reveal another guest's order existence.
    if row is None or (not admin and row['owner_hash'] != owner):
        raise APIError('order_not_found', 'Замовлення не знайдено.', 404)
    result = dict(row)
    result.pop('owner_hash')
    result['items'] = [dict(r) for r in db.execute('''SELECT product_id, product_name,
        unit_price_cents, quantity, unit_price_cents*quantity AS line_total_cents
        FROM order_items WHERE order_id=? ORDER BY id''', (order_id,))]
    return result


def create_order(fields, owner):
    name, phone, pickup, comment, items = fields
    with transaction() as db:
        snapshots, total = [], 0
        for product_id, quantity in items:
            p = db.execute('SELECT * FROM products WHERE id=?', (product_id,)).fetchone()
            if p is None or p['is_deleted'] or not p['is_available']:
                raise APIError('product_unavailable', 'Один із товарів недоступний.', 409,
                               {'product_id': product_id})
            total += p['price_cents'] * quantity
            snapshots.append((product_id, p['name'], p['price_cents'], quantity))
        cur = db.execute('''INSERT INTO orders
            (owner_hash,customer_name,phone,pickup_at,comment,total_cents,created_at)
            VALUES (?,?,?,?,?,?,?)''', (owner, name, phone, pickup, comment, total, utc_now().isoformat()))
        order_id = cur.lastrowid
        db.executemany('''INSERT INTO order_items
            (order_id,product_id,product_name,unit_price_cents,quantity) VALUES (?,?,?,?,?)''',
            [(order_id, *item) for item in snapshots])
        return read_order(order_id, owner, db=db)


def change_status(order_id, status):
    with transaction() as db:
        order = read_order(order_id, admin=True, db=db)
        if status != order['status'] and status not in TRANSITIONS[order['status']]:
            raise APIError('invalid_transition', 'Такий перехід статусу заборонений.', 409)
        db.execute('UPDATE orders SET status=? WHERE id=?', (status, order_id))
        return read_order(order_id, admin=True, db=db)

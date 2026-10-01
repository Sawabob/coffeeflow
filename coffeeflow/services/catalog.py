from ..db import get_db, transaction
from ..errors import APIError


def require_category(db, category_id):
    if db.execute('SELECT id FROM categories WHERE id=?', (category_id,)).fetchone() is None:
        raise APIError('category_not_found', 'Категорію не знайдено.', 404)


def product_dict(row):
    data = dict(row)
    data.pop('is_deleted', None)
    data['is_available'] = bool(data['is_available'])
    return data


def get_product(product_id, db=None):
    db = db or get_db()
    row = db.execute('SELECT * FROM products WHERE id=? AND is_deleted=0', (product_id,)).fetchone()
    if row is None:
        raise APIError('product_not_found', 'Товар не знайдено.', 404)
    return product_dict(row)


def save_product(data, product_id=None):
    with transaction() as db:
        if product_id is not None:
            get_product(product_id, db)
        if 'category_id' in data:
            require_category(db, data['category_id'])
        if product_id is None:
            fields = dict(description='', image_url='', is_available=True)
            fields.update(data)
            cur = db.execute('''INSERT INTO products
                (category_id,name,description,price_cents,image_url,is_available)
                VALUES (:category_id,:name,:description,:price_cents,:image_url,:is_available)''', fields)
            product_id = cur.lastrowid
        else:
            # Field names are a closed allowlist from product_fields, never user SQL.
            allowed = {'category_id','name','description','price_cents','image_url','is_available'}
            assert set(data) <= allowed
            assignments = ','.join(f'{key}=?' for key in data)
            db.execute(f'UPDATE products SET {assignments} WHERE id=?', (*data.values(), product_id))
        return get_product(product_id, db)


def delete_product(product_id):
    with transaction() as db:
        get_product(product_id, db)
        db.execute('UPDATE products SET is_deleted=1,is_available=0 WHERE id=?', (product_id,))

from flask import Blueprint, jsonify, request
from ..db import get_db, transaction
from ..errors import APIError
from ..security import require_admin
from .. import validation as v
from ..services import catalog as service

bp = Blueprint('catalog', __name__, url_prefix='/api/v1')


@bp.get('/categories')
def categories():
    limit, offset = v.pagination()
    db = get_db()
    items = [dict(r) for r in db.execute('SELECT * FROM categories ORDER BY id LIMIT ? OFFSET ?', (limit, offset))]
    return jsonify(items=items, total=db.execute('SELECT COUNT(*) FROM categories').fetchone()[0], limit=limit, offset=offset)


@bp.get('/categories/<int:category_id>')
def category(category_id):
    service.require_category(get_db(), category_id)
    return jsonify(dict(get_db().execute('SELECT * FROM categories WHERE id=?', (category_id,)).fetchone()))


@bp.post('/categories')
@require_admin
def add_category():
    data = v.body({'name'}, {'name'})
    name = v.string(data['name'], 'name')
    with transaction() as db:
        category_id = db.execute('INSERT INTO categories(name) VALUES (?)', (name,)).lastrowid
    return jsonify(id=category_id, name=name), 201, {'Location': f'/api/v1/categories/{category_id}'}


@bp.patch('/categories/<int:category_id>')
@require_admin
def edit_category(category_id):
    data = v.body({'name'}, {'name'})
    name = v.string(data['name'], 'name')
    with transaction() as db:
        service.require_category(db, category_id)
        db.execute('UPDATE categories SET name=? WHERE id=?', (name, category_id))
    return jsonify(id=category_id, name=name)


@bp.delete('/categories/<int:category_id>')
@require_admin
def remove_category(category_id):
    with transaction() as db:
        service.require_category(db, category_id)
        if db.execute('SELECT 1 FROM products WHERE category_id=? LIMIT 1', (category_id,)).fetchone():
            raise APIError('category_in_use', 'Категорія має товари, у тому числі архівні.', 409)
        db.execute('DELETE FROM categories WHERE id=?', (category_id,))
    return '', 204


@bp.get('/products')
def products():
    limit, offset = v.pagination({'category_id', 'available'})
    sql, params = ' FROM products WHERE is_deleted=0', []
    if 'category_id' in request.args:
        raw = request.args['category_id']
        if not raw.isascii() or not raw.isdigit() or len(raw) > 10:
            v.fail('category_id', 'Потрібен додатний ідентифікатор.')
        sql += ' AND category_id=?'
        params.append(v.integer(int(raw), 'category_id'))
    if 'available' in request.args:
        if request.args['available'] not in ('true','false'):
            v.fail('available', 'Потрібне true або false.')
        sql += ' AND is_available=?'
        params.append(int(request.args['available'] == 'true'))
    db = get_db()
    total = db.execute('SELECT COUNT(*)' + sql, params).fetchone()[0]
    rows = db.execute('SELECT *' + sql + ' ORDER BY id LIMIT ? OFFSET ?', (*params, limit, offset))
    return jsonify(items=[service.product_dict(r) for r in rows], total=total, limit=limit, offset=offset)


@bp.get('/products/<int:product_id>')
def product(product_id):
    return jsonify(service.get_product(product_id))


PRODUCT_FIELDS = {'name','description','category_id','price_cents','image_url','is_available'}


@bp.post('/products')
@require_admin
def add_product():
    data = v.product_fields(v.body(PRODUCT_FIELDS, {'name','category_id','price_cents'}))
    product = service.save_product(data)
    return jsonify(product), 201, {'Location': f'/api/v1/products/{product["id"]}'}


@bp.patch('/products/<int:product_id>')
@require_admin
def edit_product(product_id):
    data = v.body(PRODUCT_FIELDS)
    if not data:
        v.fail('body', 'Вкажіть хоча б одне поле.')
    return jsonify(service.save_product(v.product_fields(data), product_id))


@bp.delete('/products/<int:product_id>')
@require_admin
def remove_product(product_id):
    service.delete_product(product_id)
    return '', 204

from flask import Blueprint, jsonify, g, request
from .. import validation as v
from ..db import get_db
from ..security import owner_hash, require_admin
from ..services import orders as service

bp = Blueprint('orders', __name__, url_prefix='/api/v1/orders')


@bp.post('')
def create():
    data = v.body({'customer_name','phone','pickup_at','comment','items'},
                  {'customer_name','phone','pickup_at','items'})
    order = service.create_order(v.order_fields(data), owner_hash())
    return jsonify(order), 201, {'Location': f'/api/v1/orders/{order["id"]}'}


@bp.get('/<int:order_id>')
def detail(order_id):
    return jsonify(service.read_order(order_id, owner_hash(), g.admin is not None))


@bp.get('')
@require_admin
def list_orders():
    limit, offset = v.pagination({'status'})
    status = request.args.get('status')
    if status is not None and status not in service.TRANSITIONS:
        v.fail('status', 'Невідомий статус.')
    clause, params = (' WHERE status=?', [status]) if status else ('', [])
    db = get_db()
    total = db.execute('SELECT COUNT(*) FROM orders' + clause, params).fetchone()[0]
    rows = db.execute('SELECT id FROM orders' + clause + ' ORDER BY id DESC LIMIT ? OFFSET ?', (*params, limit, offset))
    return jsonify(items=[service.read_order(r['id'], admin=True) for r in rows], total=total, limit=limit, offset=offset)


@bp.patch('/<int:order_id>')
@require_admin
def update(order_id):
    data = v.body({'status'}, {'status'})
    if not isinstance(data['status'], str) or data['status'] not in service.TRANSITIONS:
        v.fail('status', 'Невідомий статус.')
    return jsonify(service.change_status(order_id, data['status']))

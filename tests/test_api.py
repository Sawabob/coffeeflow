"""Запуск: python -m unittest discover -v. Також сумісно з pytest."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch
from werkzeug.security import generate_password_hash
from coffeeflow import create_app
from coffeeflow.db import get_db, init_db

NOW = datetime(2026, 9, 18, 10, 0, tzinfo=timezone.utc)
PASSWORD = 'Test-only-password-2026!'
HASH = generate_password_hash(PASSWORD)


class APITest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = create_app({'TESTING': True, 'DATABASE': str(Path(self.tmp.name)/'test.db'),
            'SECRET_KEY': 'test-only-secret-key-not-for-production-12345',
            'NOW': lambda: NOW, 'RATE_LIMIT_ENABLED': False})
        self.client = self.app.test_client()
        with self.app.app_context():
            init_db()
            db = get_db()
            db.execute('INSERT INTO admins(username,password_hash) VALUES (?,?)', ('admin', HASH))
            db.execute('INSERT INTO categories(name) VALUES (?)', ('Кава',))
            db.executemany('INSERT INTO products(category_id,name,price_cents,is_available) VALUES (1,?,?,?)',
                           [('Капучино', 6500, 1), ('Недоступна кава', 4500, 0), ('Еспресо', 4500, 1)])

    def tearDown(self):
        self.tmp.cleanup()

    def csrf(self, client=None):
        return (client or self.client).get('/api/v1/auth/csrf').json['csrf_token']

    def send(self, method, path, data=None, client=None, **kwargs):
        c = client or self.client
        return c.open(path, method=method, json=data,
                      headers={'X-CSRFToken': self.csrf(c)}, **kwargs)

    def login(self, client=None):
        result = self.send('POST', '/api/v1/auth/login', {'username':'admin', 'password':PASSWORD}, client)
        self.assertEqual(result.status_code, 200, result.json)
        return result

    def payload(self):
        return {'customer_name':'Олена', 'phone':'+380501234567',
                'pickup_at':(NOW+timedelta(hours=1)).isoformat(),
                'items':[{'product_id':1,'quantity':2}]}

    def order(self, data=None, client=None):
        return self.send('POST','/api/v1/orders', data or self.payload(),client)

    def count(self, table):
        assert table in {'orders','order_items','products','categories'}
        with self.app.app_context():
            return get_db().execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]

    def test_health_and_unicode_catalog(self):
        self.assertEqual(self.client.get('/api/v1/health').json, {'status':'ok'})
        r = self.client.get('/api/v1/products?available=true&limit=1')
        self.assertEqual(r.status_code,200)
        self.assertEqual((len(r.json['items']),r.json['total']), (1,2))
        self.assertEqual(r.json['items'][0]['name'],'Капучино')

    def test_pagination_rejects_invalid_repeated_unknown(self):
        for query in ['limit=0','limit=101','offset=-1','limit=1&limit=2','oops=1','category_id=true','available=1']:
            with self.subTest(query=query):
                self.assertEqual(self.client.get('/api/v1/products?'+query).status_code,422)

    def test_csrf_required_and_bound_to_cookie(self):
        self.assertEqual(self.client.post('/api/v1/orders',json=self.payload()).status_code,400)
        token = self.csrf()
        other = self.app.test_client()
        r = other.post('/api/v1/orders',json=self.payload(),headers={'X-CSRFToken':token})
        self.assertEqual(r.json['error']['code'],'csrf_failed')

    def test_csrf_expires(self):
        token=self.csrf()
        with patch('itsdangerous.timed.time.time',return_value=time.time()+3700):
            r=self.client.post('/api/v1/orders',json=self.payload(),headers={'X-CSRFToken':token})
        self.assertEqual(r.status_code,400)

    def test_mutations_require_admin(self):
        for method,path,data in [('POST','/api/v1/products',{}),('PATCH','/api/v1/products/1',{}),
                                 ('DELETE','/api/v1/products/1',None),('POST','/api/v1/categories',{}),
                                 ('PATCH','/api/v1/orders/1',{'status':'accepted'})]:
            with self.subTest(path=path):self.assertEqual(self.send(method,path,data).status_code,401)
        self.assertEqual(self.client.get('/api/v1/orders').status_code,401)

    def test_login_logout_and_csrf_rotation(self):
        old=self.csrf()
        self.login()
        self.assertEqual(self.client.get('/api/v1/auth/me').json['admin']['username'],'admin')
        self.assertEqual(self.client.post('/api/v1/auth/logout',headers={'X-CSRFToken':old}).status_code,400)
        self.assertEqual(self.send('POST','/api/v1/auth/logout').status_code,204)
        self.assertEqual(self.client.get('/api/v1/auth/me').status_code,401)

    def test_wrong_password_and_unknown_account_same_error(self):
        results=[self.send('POST','/api/v1/auth/login',{'username':u,'password':'wrong'}) for u in ['admin','unknown']]
        self.assertEqual(results[0].json,results[1].json)
        self.assertEqual(results[0].status_code,401)

    def test_login_rate_limit(self):
        self.app.config['RATE_LIMIT_ENABLED']=True
        for _ in range(10):
            self.assertEqual(self.send('POST','/api/v1/auth/login',{'username':'xxy','password':'wrong'}).status_code,401)
        r=self.send('POST','/api/v1/auth/login',{'username':'admin','password':PASSWORD})
        self.assertEqual(r.status_code,429)
        self.assertEqual(r.headers['Retry-After'],'900')

    def test_category_crud_and_conflicts(self):
        self.login()
        r=self.send('POST','/api/v1/categories',{'name':'Чай'})
        self.assertEqual(r.status_code,201)
        path=r.headers['Location']
        self.assertEqual(self.client.get(path).json['name'],'Чай')
        self.assertEqual(self.send('POST','/api/v1/categories',{'name':'Чай'}).status_code,409)
        self.assertEqual(self.send('PATCH',path,{'name':'Десерти'}).status_code,200)
        self.assertEqual(self.send('DELETE',path).status_code,204)
        self.assertEqual(self.client.get(path).status_code,404)
        self.assertEqual(self.send('DELETE','/api/v1/categories/1').status_code,409)

    def test_product_crud(self):
        self.login()
        r=self.send('POST','/api/v1/products',{'name':'Лате','category_id':1,'price_cents':7000})
        self.assertEqual(r.status_code,201)
        path=r.headers['Location']
        self.assertTrue(r.json['is_available'])
        r=self.send('PATCH',path,{'price_cents':7500,'is_available':False})
        self.assertEqual((r.status_code,r.json['price_cents'],r.json['is_available']),(200,7500,False))
        self.assertEqual(self.send('DELETE',path).status_code,204)
        self.assertEqual(self.client.get(path).status_code,404)
        self.assertEqual(self.send('DELETE',path).status_code,404)

    def test_product_rejects_bad_fields(self):
        self.login()
        for change in [{'price_cents':True},{'price_cents':12.5},{'price_cents':-1},
                       {'is_available':'false'},{'name':''},{'unknown':1}, {'image_url':'javascript:alert(1)'},
                       {'image_url':'https://['}, {'image_url':'https://bad host/x'},{}]:
            with self.subTest(change=change):
                self.assertEqual(self.send('PATCH','/api/v1/products/1',change).status_code,422)
        self.assertEqual(self.send('PATCH','/api/v1/products/1',{'category_id':9999}).status_code,404)

    def test_sql_injection_is_data(self):
        self.login()
        name="'); DROP TABLE products; --"
        self.assertEqual(self.send('POST','/api/v1/categories',{'name':name}).status_code,201)
        self.assertEqual(self.count('products'),3)
        self.assertEqual(self.send('POST','/api/v1/auth/login',{'username':"admin' OR 1=1 --",'password':'wrong'}).status_code,401)

    def test_order_price_location_and_snapshot(self):
        r=self.order()
        self.assertEqual(r.status_code,201,r.json)
        self.assertEqual(r.json['total_cents'],13000)
        self.assertEqual(r.json['status'],'new')
        self.assertEqual(self.client.get(r.headers['Location']).status_code,200)
        self.assertNotIn('owner_hash',r.json)
        self.login()
        self.send('PATCH','/api/v1/products/1',{'name':'Нова назва','price_cents':9999})
        self.send('DELETE','/api/v1/products/1')
        snap=self.client.get(r.headers['Location']).json
        self.assertEqual((snap['items'][0]['product_name'],snap['items'][0]['unit_price_cents']),('Капучино',6500))

    def test_other_guest_cannot_read_order(self):
        r=self.order()
        other=self.app.test_client()
        self.assertEqual(other.get(r.headers['Location']).status_code,404)
        self.login(other)
        self.assertEqual(other.get(r.headers['Location']).status_code,200)

    def test_spoofed_total_and_status_are_rejected(self):
        for k,val in [('total_cents',1),('status','completed'),('owner_hash','x')]:
            p=self.payload();p[k]=val
            self.assertEqual(self.order(p).status_code,422)
        self.assertEqual(self.count('orders'),0)

    def test_order_input_validation(self):
        for fields in [
            {'customer_name':' '},{'phone':'not-phone'},{'items':[]},
            {'items':[{'product_id':1,'quantity':True}]},
            {'items':[{'product_id':1,'quantity':0}]},
            {'items':[{'product_id':1,'quantity':21}]},
            {'items':[{'product_id':1,'quantity':1,'price_cents':1}]},
            {'items':[{'product_id':1,'quantity':1}]*2},
            {'pickup_at':NOW.isoformat()},
            {'pickup_at':(NOW+timedelta(days=8)).isoformat()},
            {'pickup_at':'2026-09-18T15:00:00'},
            {'pickup_at':'this is not a datetime'},
            {'pickup_at':'9999-12-31T23:59:00-12:00'},
        ]:
            p=self.payload();p.update(fields)
            with self.subTest(fields=fields):self.assertEqual(self.order(p).status_code,422)
        self.assertEqual(self.count('orders'),0)

    def test_pickup_timezone_normalized(self):
        p=self.payload();p['pickup_at']='2026-09-18T14:00:00+03:00'
        self.assertEqual(self.order(p).json['pickup_at'],'2026-09-18T11:00:00+00:00')

    def test_missing_or_unavailable_product_no_order(self):
        for product_id in [2,999]:
            p=self.payload();p['items'].append({'product_id':product_id,'quantity':1})
            self.assertEqual(self.order(p).status_code,409)
            self.assertEqual(self.count('orders'),0)
            self.assertEqual(self.count('order_items'),0)

    def test_transaction_rolls_back_after_insert_failure(self):
        with self.app.app_context():
            get_db().execute("""CREATE TRIGGER fail_second BEFORE INSERT ON order_items
                WHEN NEW.product_id=3 BEGIN SELECT RAISE(ABORT,'test failure'); END""")
        p=self.payload();p['items'].append({'product_id':3,'quantity':1})
        self.assertEqual(self.order(p).status_code,409)
        self.assertEqual(self.count('orders'),0)
        self.assertEqual(self.count('order_items'),0)

    def test_status_lifecycle_and_terminal_state(self):
        order=self.order().json
        self.login()
        path=f'/api/v1/orders/{order["id"]}'
        self.assertEqual(self.send('PATCH',path,{'status':'completed'}).status_code,409)
        for status in ['accepted','preparing','ready','completed','completed']:
            self.assertEqual(self.send('PATCH',path,{'status':status}).status_code,200)
        self.assertEqual(self.send('PATCH',path,{'status':'cancelled'}).status_code,409)
        self.assertEqual(self.client.get('/api/v1/orders?status=completed').json['total'],1)

    def test_cancelled_order_cannot_restart(self):
        r=self.order();self.login();path=r.headers['Location']
        self.assertEqual(self.send('PATCH',path,{'status':'cancelled'}).status_code,200)
        self.assertEqual(self.send('PATCH',path,{'status':'accepted'}).status_code,409)

    def test_json_errors_and_http_headers(self):
        token=self.csrf()
        r=self.client.post('/api/v1/orders',data='{',content_type='application/json',headers={'X-CSRFToken':token})
        self.assertEqual(r.status_code,400)
        self.assertEqual(r.content_type,'application/json')
        r=self.client.post('/api/v1/orders',data='x',headers={'X-CSRFToken':token})
        self.assertEqual(r.status_code,415)
        self.assertEqual(self.send('POST','/api/v1/orders',[]).status_code,422)
        r=self.client.put('/api/v1/products',headers={'X-CSRFToken':token})
        self.assertEqual(r.status_code,405)
        self.assertIn('Allow',r.headers)
        self.assertEqual(r.headers['X-Content-Type-Options'],'nosniff')

    def test_payload_size_limit(self):
        p=self.payload();p['comment']='a'*40000
        self.assertEqual(self.order(p).status_code,413)

    def test_oversized_resource_id_is_validation_error(self):
        for path in ['/api/v1/products/','/api/v1/categories/','/api/v1/orders/']:
            self.assertEqual(self.client.get(path+'99999999999999999999999').status_code,422)

    def test_database_constraints(self):
        with self.app.app_context():
            db=get_db()
            self.assertEqual(db.execute('PRAGMA foreign_keys').fetchone()[0],1)
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("INSERT INTO products(category_id,name,price_cents) VALUES (999,'x',10)")
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('UPDATE products SET price_cents=-1 WHERE id=1')

    def test_initialization_does_not_erase_data(self):
        r=self.order()
        runner=self.app.test_cli_runner()
        self.assertEqual(runner.invoke(args=['init-db']).exit_code,0)
        self.assertEqual(self.client.get(r.headers['Location']).status_code,200)
        self.assertNotEqual(runner.invoke(args=['seed-demo']).exit_code,0)
        self.assertEqual(self.count('products'),3)

    def test_admin_cli_validation_and_hash(self):
        runner=self.app.test_cli_runner()
        self.assertNotEqual(runner.invoke(args=['create-admin','--username','staff','--password','short']).exit_code,0)
        r=runner.invoke(args=['create-admin','--username','staff','--password',PASSWORD])
        self.assertEqual(r.exit_code,0,r.output)
        with self.app.app_context():
            stored=get_db().execute("SELECT password_hash FROM admins WHERE username='staff'").fetchone()[0]
            self.assertNotEqual(stored,PASSWORD)
        self.assertEqual(self.send('POST','/api/v1/auth/login',{'username':'staff','password':PASSWORD}).status_code,200)

    def test_openapi_covers_registered_api_routes(self):
        r=self.client.get('/api/v1/openapi.json')
        self.assertEqual(r.status_code,200)
        spec=r.json
        self.assertEqual(spec['openapi'],'3.0.3')
        import re
        for rule in self.app.url_map.iter_rules():
            if not rule.rule.startswith('/api/v1/') or rule.rule.endswith('/openapi.json'):
                continue
            path=re.sub(r'<int:(\w+)>',r'{\1}',rule.rule[len('/api/v1'):])
            self.assertIn(path,spec['paths'])
            for method in rule.methods-{'HEAD','OPTIONS'}:
                self.assertIn(method.lower(),spec['paths'][path])


if __name__ == '__main__':
    unittest.main(verbosity=2)

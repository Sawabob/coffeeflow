"""Реальні запити до Flask test client; тільки тимчасова база."""
import json
import secrets
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from coffeeflow import create_app


def main():
    with tempfile.TemporaryDirectory() as folder:
        app = create_app({'TESTING':True,'DATABASE':str(Path(folder)/'demo.db'),
                          'SECRET_KEY':secrets.token_hex(32),'RATE_LIMIT_ENABLED':False})
        runner=app.test_cli_runner()
        for command in ['init-db','seed-demo']:
            result=runner.invoke(args=[command])
            if result.exit_code:
                raise RuntimeError(result.output)
        client=app.test_client()
        def show(label,response):
            print(label, response.status_code)
            print(json.dumps(response.json,ensure_ascii=False,indent=2))
        show('GET /api/v1/products',client.get('/api/v1/products'))
        token=client.get('/api/v1/auth/csrf').json['csrf_token']
        body={'customer_name':'Демонстраційний клієнт','phone':'+380501234567',
              'pickup_at':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),
              'items':[{'product_id':1,'quantity':2}]}
        response=client.post('/api/v1/orders',json=body,headers={'X-CSRFToken':token})
        show('POST /api/v1/orders',response)
        assert response.status_code==201 and response.json['total_cents']==9000
        location=response.headers['Location']
        show('GET own order',client.get(location))
        other=app.test_client()
        show('GET order from another guest',other.get(location))
        assert other.get(location).status_code==404
        body['items'][0]['quantity']=-1
        response=client.post('/api/v1/orders',json=body,headers={'X-CSRFToken':token})
        show('POST invalid quantity',response)
        assert response.status_code==422
        print('Demonstration passed. Temporary database removed on exit.')


if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    main()

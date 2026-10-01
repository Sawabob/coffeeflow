"""Temporary local test server. Do not use for production or real customer data."""
import sys
import secrets
import tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from coffeeflow import create_app

if __name__=='__main__':
    with tempfile.TemporaryDirectory(prefix='coffeeflow-ui-') as folder:
        app=create_app({'DATABASE':str(Path(folder)/'test.sqlite3'),
                       'SECRET_KEY':secrets.token_hex(32),'RATE_LIMIT_ENABLED':False})
        runner=app.test_cli_runner()
        for command in [['init-db'],['seed-demo'],['create-admin','--username','tester','--password','Ui-test-only-2026!']]:
            result=runner.invoke(args=command)
            if result.exit_code:raise RuntimeError(result.output)
        app.run(host='127.0.0.1',port=5016,debug=False,use_reloader=False)

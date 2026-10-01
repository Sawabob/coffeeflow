"""HTTP integration between Flask, templates and frontend assets."""
import tempfile
import unittest
from pathlib import Path
from coffeeflow import create_app


class FrontendHTTPTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.app=create_app({'TESTING':True,'SECRET_KEY':'frontend-test-secret-only-0123456789',
                             'DATABASE':str(Path(self.temp.name)/'frontend.db')})
        self.client=self.app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    def test_html_screens_without_database_dependency(self):
        for path,page in [('/','shop'),('/checkout','checkout'),('/orders','orders'),('/orders/1','orders'),('/admin','admin')]:
            with self.subTest(path=path):
                response=self.client.get(path)
                self.assertEqual(response.status_code,200)
                self.assertIn('text/html',response.content_type)
                self.assertIn('lang="uk"',response.text)
                self.assertIn(f'data-page="{page}"',response.text)
                self.assertIn(f'/static/js/{page}.js',response.text)

    def test_local_frontend_assets(self):
        for path in ['css/style.css','js/api.js','js/ui.js','js/state.js','images/coffee.svg','images/cake.svg']:
            with self.subTest(path=path):
                response=self.client.get('/static/'+path)
                self.assertEqual(response.status_code,200)
                self.assertGreater(len(response.data),50)
                response.close()

    def test_admin_html_does_not_grant_api_access(self):
        self.assertEqual(self.client.get('/admin').status_code,200)
        self.assertEqual(self.client.get('/api/v1/orders').status_code,401)

    def test_guest_pages_do_not_embed_customer_data(self):
        response=self.client.get('/orders/1')
        self.assertIn('data-order-id="1"',response.text)
        self.assertNotIn('customer_name',response.text)
        self.assertNotIn('password_hash',response.text)

    def test_database_failure_remains_json_for_frontend(self):
        response=self.client.get('/api/v1/products')
        self.assertEqual(response.status_code,503)
        self.assertEqual(response.json['error']['code'],'database_unavailable')


if __name__=='__main__':unittest.main()

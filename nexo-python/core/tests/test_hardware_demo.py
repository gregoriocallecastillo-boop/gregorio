import json
import uuid
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.test import Client, TestCase, override_settings
from django.utils import timezone
from PIL import Image

from core.demo import COOKIE
from core.models import Business, Document, Product
from core.tests.test_inventory import TEST_SETTINGS


@override_settings(**TEST_SETTINGS)
class HardwareDemoTests(TestCase):
    entry = '/demo/ferreteria/'
    base = '/demo/ferreteria/api/b/1/'

    def setUp(self):
        self.guest = Client()
        self.assertRedirects(self.guest.post(self.entry), self.entry+'app/', fetch_redirect_response=False)

    def state(self, client=None, base=None):
        response = (client or self.guest).get((base or self.base)+'state/')
        self.assertEqual(response.status_code, 200)
        return response.json()

    def action(self, operation, data):
        return self.guest.post(self.base+'action/', json.dumps({'action':operation,'data':data}), content_type='application/json')

    def test_entry_catalog_photos_and_application_prefix(self):
        public = Client()
        landing = public.get(self.entry)
        self.assertContains(landing, 'Entrar a la ferretería como invitado')
        self.assertContains(landing, 'Créditos de las fotografías')
        self.assertEqual(public.get(self.base+'state/').status_code, 401)
        cookie = self.guest.cookies[COOKIE+'_hardware']
        self.assertTrue(cookie['httponly'])
        self.assertEqual(cookie['path'], self.entry)
        self.assertEqual(cookie['samesite'], 'Lax')
        app = self.guest.get(self.entry+'app/')
        self.assertContains(app, 'data-demo-base="/demo/ferreteria"')
        self.assertContains(app, 'action="/demo/ferreteria/logout/"')
        state = self.state()
        self.assertEqual(state['business']['sector'], 'Ferretería')
        self.assertEqual(len(state['products']), 8)
        self.assertTrue(state['documents'] and state['invoices'])
        for product in state['products']:
            photo = product['demo_photo']
            self.assertTrue(photo['author'] and photo['license'] and photo['source'])
            path = Path(__file__).resolve().parents[1] / 'static' / photo['src'].removeprefix('/static/')
            with Image.open(path) as image:
                self.assertEqual(image.format, 'JPEG')
                image.verify()
        self.assertEqual(len({p['demo_photo']['src'] for p in state['products']}), 8)
        self.assertFalse(Business.objects.exists())
        self.assertFalse(Product.objects.exists())
        self.assertFalse(Document.objects.exists())

    def test_profiles_visitors_reset_and_logout_are_independent(self):
        self.guest.post('/demo/')
        other = Client(); other.post(self.entry)
        market = self.state(base='/demo/api/b/1/')
        hardware = self.state(other)
        sale = {'request_key':str(uuid.uuid4()),'kind':'sale','warehouse':1,'lines':[{'product':1,'quantity':1}]}
        self.assertEqual(self.action('document',sale).status_code,200)
        self.assertEqual(self.state(base='/demo/api/b/1/'),market)
        self.assertEqual(self.state(other),hardware)
        self.assertNotEqual(self.state()['products'][0]['stock'],hardware['products'][0]['stock'])
        self.assertEqual(self.guest.post(self.entry+'api/reset/','{}',content_type='application/json').status_code,200)
        self.assertEqual(self.state()['products'],hardware['products'])
        self.assertEqual(self.state()['business']['sector'],'Ferretería')
        self.guest.post(self.entry+'logout/')
        self.assertEqual(self.guest.get(self.base+'state/').status_code,401)
        self.assertEqual(self.state(base='/demo/api/b/1/'),market)
        self.assertEqual(self.state(other),hardware)

    def test_market_token_cannot_be_reused_as_hardware_token(self):
        self.guest.post('/demo/')
        market = self.state(base='/demo/api/b/1/')
        forged = Client()
        forged.cookies[COOKIE+'_hardware'] = self.guest.cookies[COOKIE].value
        self.assertEqual(forged.get(self.base+'state/').status_code,401)
        self.assertRedirects(forged.get(self.entry+'app/'),self.entry,fetch_redirect_response=False)
        forged.post(self.entry+'logout/')
        self.assertEqual(self.state(base='/demo/api/b/1/'),market)

    def test_sale_payment_invoice_and_every_stock_ledger(self):
        before = Decimal(self.state()['products'][0]['stock'])
        sale = self.action('document',{'request_key':str(uuid.uuid4()),'kind':'sale','warehouse':1,'contact':2,'lines':[{'product':1,'quantity':2}]})
        self.assertEqual(sale.status_code,200,sale.content)
        invoice = self.state()['invoices'][0]
        self.assertEqual(Decimal(invoice['total']),Decimal('25.80'))
        self.assertIn('Ferretería',invoice['issuer']['name'])
        self.assertEqual(Decimal(self.state()['products'][0]['stock']),before-2)
        self.assertEqual(self.action('payment',{'request_key':str(uuid.uuid4()),'invoice':invoice['id'],'amount':'25.80','method':'cash'}).status_code,200)
        self.assertEqual(self.state()['invoices'][0]['status'],'paid')
        pdf = self.guest.get(self.base+f"invoices/{invoice['id']}/pdf/")
        self.assertEqual(pdf.status_code,200);self.assertTrue(pdf.content.startswith(b'%PDF'))
        params={'start':str(timezone.localdate()-timedelta(days=30)),'end':str(timezone.localdate())}
        state=self.state()
        for product in state['products']:
            for warehouse in state['warehouses']:
                query={**params,'product':product['id'],'warehouse':warehouse['id']}
                ledger=self.guest.get(self.base+'kardex/',query).json()
                qty=next((Decimal(row['quantity']) for row in product['stocks'] if row['warehouse']==warehouse['id']),Decimal(0))
                self.assertEqual(Decimal(ledger['closing']),qty)
                self.assertTrue(all(Decimal(row['balance'])>=0 for row in ledger['rows']))
        csv=self.guest.get(self.base+'kardex/',{**params,'product':1,'warehouse':1,'format':'csv'})
        self.assertContains(csv,'Martillo de uña')
        self.assertFalse(Business.objects.exists())

    def test_employee_permissions_and_hardware_csrf(self):
        self.guest.post(self.entry+'api/role/',json.dumps({'role':'employee'}),content_type='application/json')
        self.assertNotIn('cost',self.state()['products'][0])
        self.assertTrue(self.state()['products'][0]['demo_photo']['src'])
        self.assertEqual(self.guest.get(self.base+'kardex/',{'product':1,'warehouse':1}).status_code,403)
        self.assertEqual(self.action('document',{'request_key':str(uuid.uuid4()),'kind':'purchase'}).status_code,403)
        self.assertEqual(self.guest.post(self.base+'products/1/photo/',{}).status_code,403)
        csrf=Client(enforce_csrf_checks=True)
        self.assertEqual(csrf.post(self.entry).status_code,403)
        csrf.get(self.entry)
        token=csrf.cookies['csrftoken'].value
        self.assertEqual(csrf.post(self.entry,HTTP_X_CSRFTOKEN=token).status_code,302)
        self.assertEqual(csrf.post(self.entry+'api/reset/','{}',content_type='application/json').status_code,403)

import csv
import io
import json
import uuid
from datetime import timedelta
from decimal import Decimal
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from core.tests.test_inventory import TEST_SETTINGS
from core.models import StockMovement, Business, Document


@override_settings(**TEST_SETTINGS)
class DemoKardexTests(TestCase):
    def setUp(self):
        self.client=Client();self.client.post('/demo/')
        self.base='/demo/api/b/1/'
        self.params={'product':1,'warehouse':1,'start':str(timezone.localdate()-timedelta(days=30)),'end':str(timezone.localdate())}
    def post(self,data):
        return self.client.post(self.base+'action/',json.dumps({'action':'document','data':data}),content_type='application/json')
    def ledger(self,**args):return self.client.get(self.base+'kardex/',{**self.params,**args})
    def test_seed_ledger_reconciles_every_product_and_warehouse(self):
        state=self.client.get(self.base+'state/').json()
        for p in state['products']:
            for w in state['warehouses']:
                k=self.ledger(product=p['id'],warehouse=w['id']).json()
                qty=next((Decimal(s['quantity']) for s in p['stocks'] if s['warehouse']==w['id']),Decimal(0))
                self.assertEqual(Decimal(k['closing']),qty)
                self.assertTrue(all(Decimal(row['balance'])>=0 for row in k['rows']))
                self.assertEqual(Decimal(k['opening'])+Decimal(k['incoming'])-Decimal(k['outgoing']),qty)
    def test_count_and_duplicate_do_not_touch_business_data(self):
        snapshot=self.client.get(self.base+'stock-snapshot/',self.params).json()
        data={'request_key':str(uuid.uuid4()),'kind':'adjustment','warehouse':1,'note':'Conteo de prueba','lines':[{'product':1,'quantity':'-2','expected':snapshot['quantity'],'counted':str(Decimal(snapshot['quantity'])-2),'last_movement':snapshot['last_movement']}]}
        self.assertEqual(self.post(data).status_code,200)
        self.assertFalse(self.post(data).json()['created'])
        self.assertEqual(Decimal(self.ledger().json()['closing']),Decimal(snapshot['quantity'])-2)
        self.assertEqual(StockMovement.objects.count(),0)
        self.assertEqual(Business.objects.count(),0)
        self.assertEqual(Document.objects.count(),0)
    def test_employee_cannot_read_ledger_or_snapshot_or_costs(self):
        self.client.post('/demo/api/role/',json.dumps({'role':'employee'}),content_type='application/json')
        self.assertEqual(self.ledger().status_code,403)
        self.assertEqual(self.client.get(self.base+'stock-snapshot/',self.params).status_code,403)
        data={'request_key':str(uuid.uuid4()),'kind':'sale','warehouse':1,'lines':[{'product':1,'quantity':'1','price':'6.50'}]}
        self.assertEqual(self.post(data).status_code,200)
        state=self.client.get(self.base+'state/').json()
        line=state['documents'][0]['lines'][0]
        self.assertNotIn('average_cost',line)
        self.assertNotIn('unit_cost',line)
    def test_count_stale_and_export(self):
        snapshot=self.client.get(self.base+'stock-snapshot/',self.params).json()
        sale={'request_key':str(uuid.uuid4()),'kind':'sale','warehouse':1,'lines':[{'product':1,'quantity':'1','price':'6.50'}]}
        self.post(sale)
        count={'request_key':str(uuid.uuid4()),'kind':'adjustment','warehouse':1,'note':'Conteo','lines':[{'product':1,'quantity':'-2','expected':snapshot['quantity'],'counted':str(Decimal(snapshot['quantity'])-2),'last_movement':snapshot['last_movement']}]}
        self.assertEqual(self.post(count).status_code,400)
        response=self.ledger(format='csv')
        self.assertEqual(response.status_code,200)
        self.assertIn('DATOS FICTICIOS',response.content.decode())
        self.assertEqual(self.ledger(warehouse=999).status_code,400)
        self.assertEqual(self.ledger(product=999).status_code,400)

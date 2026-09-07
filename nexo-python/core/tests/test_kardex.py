import csv
import io
import json
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, Client, override_settings
from django.utils import timezone
from core.models import Stock, StockMovement
from core.services import post_document, return_sale
from core.tests.test_inventory import Fixtures, TEST_SETTINGS


@override_settings(**TEST_SETTINGS)
class KardexTests(Fixtures, TestCase):
    def ledger(self, **kwargs):
        query={'product':self.p.id,'warehouse':self.w.id,**kwargs}
        return self.client.get(f'/api/b/{self.b.id}/kardex/', query)

    def snapshot(self):
        return self.client.get(f'/api/b/{self.b.id}/stock-snapshot/', {'product':self.p.id,'warehouse':self.w.id}).json()

    def count_payload(self, expected='10', counted='8', last=0):
        payload=self.payload('adjustment',str(Decimal(counted)-Decimal(expected)))
        payload['lines'][0].update(counted=counted,expected=expected,last_movement=last)
        return payload

    def test_running_balances_include_purchases_sales_transfer_and_return(self):
        sale=self.sale()
        post_document(self.admin,self.b.id,self.payload('purchase','3','4.00'))
        post_document(self.admin,self.b.id,self.payload('transfer','1',destination=self.w2.id))
        return_sale(self.admin,self.b.id,sale.id,{'request_key':self.payload()['request_key'],'note':'Devuelto'})
        result=self.ledger().json()
        self.assertEqual([Decimal(r['balance']) for r in result['rows']],[8,11,10,12])
        self.assertEqual(Decimal(result['opening']),10)
        self.assertEqual(Decimal(result['incoming']),5)
        self.assertEqual(Decimal(result['outgoing']),3)
        self.assertEqual(Decimal(result['closing']),12)
        destination=self.ledger(warehouse=self.w2.id).json()
        self.assertEqual(Decimal(destination['incoming']),1)
        self.assertEqual(Decimal(destination['closing']),1)

    def test_date_filter_carries_opening_and_excludes_later_movements(self):
        now=timezone.now()
        with patch('django.utils.timezone.now',return_value=now-timedelta(days=2)):
            self.sale(quantity='2')
        with patch('django.utils.timezone.now',return_value=now-timedelta(days=1)):
            self.sale(quantity='3')
        self.sale(quantity='1')
        day=str(timezone.localtime(now-timedelta(days=1)).date())
        result=self.ledger(start=day,end=day).json()
        self.assertEqual(Decimal(result['opening']),8)
        self.assertEqual(Decimal(result['closing']),5)
        self.assertEqual(result['total_rows'],1)
        empty=self.ledger(start=str(timezone.localdate()+timedelta(days=1)),end=str(timezone.localdate()+timedelta(days=1))).json()
        self.assertEqual(empty['total_rows'],0)
        self.assertEqual(Decimal(empty['opening']),4)
        self.assertEqual(Decimal(empty['closing']),4)

    def test_empty_history_and_stock_snapshot(self):
        result=self.ledger().json()
        self.assertEqual(result['rows'],[])
        self.assertEqual(Decimal(result['closing']),10)
        self.assertEqual(self.snapshot()['last_movement'],0)

    def test_pagination_summaries_and_full_export_not_truncated(self):
        for _ in range(52):post_document(self.admin,self.b.id,self.payload('adjustment','1'))
        first=self.ledger().json();second=self.ledger(page=2).json()
        self.assertEqual(first['total_rows'],52)
        self.assertEqual(len(first['rows']),50)
        self.assertEqual(len(second['rows']),2)
        self.assertEqual(first['closing'],second['closing'])
        self.assertEqual(Decimal(second['rows'][0]['balance']),61)
        response=self.ledger(format='csv',page=2)
        rows=list(csv.reader(io.StringIO(response.content.decode('utf-8-sig'))))
        self.assertEqual(len(rows),57)
        self.assertEqual(rows[-1][8],'62.000')

    def test_permissions_business_isolation_and_input_validation(self):
        self.client.force_login(self.employee)
        self.assertEqual(self.ledger().status_code,403)
        self.assertEqual(self.client.get(f'/api/b/{self.b.id}/stock-snapshot/',{'product':self.p.id,'warehouse':self.w.id}).status_code,403)
        self.client.force_login(self.other)
        self.assertEqual(self.ledger().status_code,403)
        self.client.force_login(self.admin)
        self.assertEqual(self.ledger(warehouse=self.foreign.id).status_code,404)
        self.assertEqual(self.ledger(product=9999999).status_code,404)
        self.assertEqual(self.ledger(start='invalid').status_code,400)
        self.assertEqual(self.ledger(start='2020-01-01',end='2025-01-01').status_code,400)
        self.assertEqual(self.ledger(page=0).status_code,400)
        self.assertEqual(self.ledger(page=10).status_code,400)
        self.assertEqual(Client().get(f'/api/b/{self.b.id}/kardex/').status_code,401)

    def test_count_matches_snapshot_and_is_idempotent(self):
        payload=self.count_payload()
        first=self.action('document',payload)
        self.assertEqual(first.status_code,200)
        self.assertEqual(Stock.objects.get(product=self.p,warehouse=self.w).quantity,8)
        again=self.action('document',payload)
        self.assertEqual(again.status_code,200)
        self.assertFalse(again.json()['created'])
        self.assertEqual(StockMovement.objects.count(),1)
        self.assertEqual(Decimal(self.ledger().json()['closing']),8)

    def test_count_rejects_sale_after_snapshot_and_same_quantity_aba(self):
        payload=self.count_payload()
        self.sale(quantity='1')
        self.assertEqual(self.action('document',payload).status_code,400)
        post_document(self.admin,self.b.id,self.payload('adjustment','1'))
        self.assertEqual(Stock.objects.get(product=self.p,warehouse=self.w).quantity,10)
        self.assertEqual(self.action('document',payload).status_code,400)
        fresh=self.snapshot();payload=self.count_payload(last=fresh['last_movement'])
        self.assertEqual(self.action('document',payload).status_code,200)

    def test_count_rejects_forged_difference_and_excess_precision(self):
        payload=self.count_payload();payload['lines'][0]['quantity']='-1'
        self.assertEqual(self.action('document',payload).status_code,400)
        payload=self.count_payload(counted='8.0001')
        self.assertEqual(self.action('document',payload).status_code,400)
        self.client.force_login(self.employee)
        self.assertEqual(self.action('document',self.count_payload()).status_code,403)

    def test_export_escapes_formula_injection(self):
        post_document(self.admin,self.b.id,self.payload('adjustment','1',note='=HYPERLINK("bad")'))
        self.assertIn("'=HYPERLINK", self.ledger(format='csv').content.decode())

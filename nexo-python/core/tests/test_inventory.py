import json,uuid,os
from decimal import Decimal
from datetime import timedelta
from unittest import skipIf
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.test import TestCase,TransactionTestCase,Client,override_settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import IntegrityError,DatabaseError,transaction,connections
from django.utils import timezone
from core.models import *
from core.services import post_document,return_sale,post_payment,void_payment,invoice_paid,invoice_status
TEST_SETTINGS={'SECURE_SSL_REDIRECT':False,'ALLOWED_HOSTS':['testserver','localhost','127.0.0.1'],'STORAGES':{'default':{'BACKEND':'django.core.files.storage.FileSystemStorage'},'staticfiles':{'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage'}},'PASSWORD_HASHERS':['django.contrib.auth.hashers.MD5PasswordHasher']}
class Fixtures:
    def setUp(self):
        User=get_user_model();self.admin=User.objects.create_user('admin',password='TestingOnly-Long-Password!');self.employee=User.objects.create_user('employee',password='TemporaryOnly-Long-Password!');self.other=User.objects.create_user('other',password='TestingOnly-Long-Password!')
        self.b=Business.objects.create(name='Business A',tax_rate=Decimal('8.00'));self.b2=Business.objects.create(name='Business B')
        self.admin_member=Membership.objects.create(user=self.admin,business=self.b,role='admin');Membership.objects.create(user=self.employee,business=self.b,role='employee');Membership.objects.create(user=self.other,business=self.b2,role='admin')
        self.w=Warehouse.objects.create(business=self.b,name='Principal');self.w2=Warehouse.objects.create(business=self.b,name='Tienda');self.foreign=Warehouse.objects.create(business=self.b2,name='Foreign')
        self.p=Product.objects.create(business=self.b,name='Café',sku='CAFE',category='Bebidas',unit='unidad',cost=Decimal('2.0000'),price=Decimal('5.00'),minimum=3)
        Stock.objects.create(product=self.p,warehouse=self.w,quantity=10)
        self.client=Client();self.client.force_login(self.admin)
    def payload(self,kind='sale',quantity='2',price='5.00',**extras):return {'request_key':str(uuid.uuid4()),'kind':kind,'warehouse':self.w.id,'note':'Test operation','lines':[{'product':self.p.id,'quantity':quantity,'price':price}],**extras}
    def sale(self,user=None,**kwargs):return post_document(user or self.admin,self.b.id,self.payload(**kwargs))[0]
    def action(self,op,data,business=None):return self.client.post(f'/api/b/{business or self.b.id}/action/',json.dumps({'action':op,'data':data}),content_type='application/json')

@override_settings(**TEST_SETTINGS)
class InventoryTests(Fixtures,TestCase):
    def test_sale_and_invoice_are_atomic_and_tax_rounded(self):
        d=self.sale(quantity='2');self.assertEqual(d.total,Decimal('10.80'));self.assertEqual(Stock.objects.get(product=self.p,warehouse=self.w).quantity,8);self.assertEqual(d.invoice.number,'FAC-000001');self.assertEqual(d.lines.get().unit_cost,Decimal(2));self.assertEqual(StockMovement.objects.get(document=d).delta,-2)
    def test_purchase_weighted_cost_and_tax(self):
        d=post_document(self.admin,self.b.id,self.payload('purchase','10','4.00'))[0];self.p.refresh_from_db();self.assertEqual(self.p.cost,Decimal('3.0000'));self.assertEqual(d.total,Decimal('43.20'));self.assertFalse(Invoice.objects.filter(document=d).exists())
    def test_overselling_rejects_all_changes(self):
        with self.assertRaises(ValidationError):self.sale(quantity='11')
        self.assertEqual(Document.objects.count(),0);self.assertEqual(Invoice.objects.count(),0);self.assertEqual(Stock.objects.get(product=self.p,warehouse=self.w).quantity,10)
    def test_duplicate_submit_is_idempotent(self):
        payload=self.payload();d,new=post_document(self.admin,self.b.id,payload);same,new2=post_document(self.admin,self.b.id,payload);self.assertTrue(new);self.assertFalse(new2);self.assertEqual(d.pk,same.pk);self.assertEqual(Stock.objects.get(product=self.p,warehouse=self.w).quantity,8)
        payload['lines'][0]['quantity']='1'
        with self.assertRaises(ValidationError):post_document(self.admin,self.b.id,payload)
    def test_invalid_second_line_rolls_back(self):
        p=self.payload();p['lines'].append({'product':99999,'quantity':'1','price':'1'})
        with self.assertRaises(ValidationError):post_document(self.admin,self.b.id,p)
        self.assertEqual(Stock.objects.get(product=self.p,warehouse=self.w).quantity,10);self.assertEqual(Document.objects.count(),0)
    def test_transfer_conserves_stock(self):
        d=post_document(self.admin,self.b.id,self.payload('transfer','3',destination=self.w2.id))[0]
        self.assertEqual(Stock.objects.get(product=self.p,warehouse=self.w).quantity,7);self.assertEqual(Stock.objects.get(product=self.p,warehouse=self.w2).quantity,3);self.assertEqual(StockMovement.objects.filter(document=d).aggregate(n=models.Sum('delta'))['n'],0)
    def test_adjustment_requires_reason(self):
        with self.assertRaises(ValidationError):post_document(self.admin,self.b.id,self.payload('adjustment','-1',note=''))
        post_document(self.admin,self.b.id,self.payload('adjustment','-1'));self.assertEqual(Stock.objects.get(product=self.p,warehouse=self.w).quantity,9)
    def test_fractional_quantity_and_decimal_validation(self):
        d=self.sale(quantity='0.125');self.assertEqual(d.subtotal,Decimal('.63'));self.assertEqual(d.tax,Decimal('.05'));self.assertEqual(d.total,Decimal('.68'))
        for q in ['0.0001','NaN','Infinity','-1','0']:
            with self.assertRaises(ValidationError):self.sale(quantity=q)
    def test_employee_cannot_change_sale_price(self):
        with self.assertRaises(PermissionDenied):self.sale(user=self.employee,price='1')
        self.sale(user=self.employee)
    def test_employee_cannot_purchase_transfer_adjust(self):
        for kind in ['purchase','adjustment','transfer']:
            with self.assertRaises(PermissionDenied):post_document(self.employee,self.b.id,self.payload(kind))
    def test_cross_business_warehouse_and_products_rejected(self):
        with self.assertRaises(ValidationError):post_document(self.admin,self.b.id,self.payload(warehouse=self.foreign.id))
        with self.assertRaises(PermissionDenied):post_document(self.other,self.b.id,self.payload())
        foreignp=Product.objects.create(business=self.b2,name='Other',sku='OTHER',category='Other',price=10)
        p=self.payload();p['lines'][0]['product']=foreignp.id
        with self.assertRaises(ValidationError):post_document(self.admin,self.b.id,p)
    def test_expired_product_cannot_be_sold(self):
        self.p.expiry=timezone.localdate()-timedelta(days=1);self.p.save()
        with self.assertRaises(ValidationError):self.sale()
    def test_return_creates_credit_note_and_retains_sale(self):
        original=self.sale();credit,created=return_sale(self.admin,self.b.id,original.id,{'request_key':str(uuid.uuid4()),'note':'Customer return'})
        self.assertEqual(credit.original,original);self.assertEqual(credit.invoice.kind,'credit');self.assertEqual(Stock.objects.get(product=self.p,warehouse=self.w).quantity,10);self.assertEqual(invoice_status(original.invoice),'credited');self.assertEqual(Document.objects.count(),2)
        with self.assertRaises(ValidationError):return_sale(self.admin,self.b.id,original.id,{'request_key':str(uuid.uuid4()),'note':'Again'})
    def test_partial_payment_overpayment_and_duplicate(self):
        i=self.sale().invoice;p={'request_key':str(uuid.uuid4()),'amount':'5.00','method':'cash'}
        pay,new=post_payment(self.admin,self.b.id,i.id,p);pay2,new2=post_payment(self.admin,self.b.id,i.id,p);self.assertFalse(new2);self.assertEqual(pay.pk,pay2.pk);self.assertEqual(invoice_paid(i),5);self.assertEqual(invoice_status(i),'partial')
        with self.assertRaises(ValidationError):post_payment(self.admin,self.b.id,i.id,{'request_key':str(uuid.uuid4()),'amount':'6.00','method':'cash'})
    def test_paid_sale_requires_payment_reversal_before_return(self):
        d=self.sale();p,_=post_payment(self.admin,self.b.id,d.invoice.id,{'request_key':str(uuid.uuid4()),'amount':'10.80','method':'card'})
        with self.assertRaises(ValidationError):return_sale(self.admin,self.b.id,d.id,{'request_key':str(uuid.uuid4()),'note':'Return'})
        void_payment(self.admin,self.b.id,p.id,'Refund confirmed');return_sale(self.admin,self.b.id,d.id,{'request_key':str(uuid.uuid4()),'note':'Return'});p.refresh_from_db();self.assertTrue(p.voided)
    def test_invoice_issuer_snapshot_survives_settings_change(self):
        i=self.sale().invoice;Business.objects.filter(pk=self.b.id).update(name='New name');i.refresh_from_db();self.assertEqual(i.issuer['name'],'Business A')
    def test_database_guards_negative_stock_and_duplicate_sku(self):
        with self.assertRaises(IntegrityError),transaction.atomic():Stock.objects.filter(product=self.p).update(quantity=-1)
        with self.assertRaises(IntegrityError),transaction.atomic():Product.objects.create(business=self.b,name='Duplicate',sku='CAFE',category='Beverage')
    def test_database_guards_immutable_history(self):
        d=self.sale()
        for model in [StockMovement,DocumentLine,Invoice,Audit]:
            obj=model.objects.first()
            with self.assertRaises(DatabaseError),transaction.atomic():obj.delete()
    def test_anonymous_and_other_business_denied(self):
        c=Client();self.assertEqual(c.get(f'/api/b/{self.b.id}/state/').status_code,401);self.assertEqual(self.client.get(f'/api/b/{self.b2.id}/state/').status_code,403)
    def test_employee_api_hides_costs_and_admin_records(self):
        self.sale();self.sale(user=self.employee);self.client.force_login(self.employee);r=self.client.get(f'/api/b/{self.b.id}/state/');self.assertEqual(r.status_code,200);j=r.json();self.assertNotIn('cost',j['products'][0]);self.assertNotIn('users',j);self.assertNotIn('audit',j);self.assertEqual(len(j['documents']),1);self.assertNotIn('unit_cost',j['documents'][0]['lines'][0]);self.assertEqual(self.client.get(f'/api/b/{self.b.id}/export/').status_code,403)
    def test_employee_cannot_view_or_collect_another_sellers_invoice(self):
        i=self.sale().invoice;self.client.force_login(self.employee);self.assertEqual(self.client.get(f'/api/b/{self.b.id}/invoices/{i.id}/pdf/').status_code,403);r=self.action('payment',{'invoice':i.id,'request_key':str(uuid.uuid4()),'amount':'1','method':'cash'});self.assertEqual(r.status_code,403)
    def test_admin_product_create_with_initial_stock(self):
        r=self.action('product',{'name':'Rice','sku':'rice','category':'Food','unit':'kg','price':'2.00','cost':'1.0000','minimum':'2','initial':'3.5','warehouse':self.w.id});self.assertEqual(r.status_code,200,r.content);p=Product.objects.get(sku='RICE');self.assertEqual(Stock.objects.get(product=p).quantity,Decimal('3.500'))
    def test_last_admin_cannot_remove_self(self):
        r=self.action('user_update',{'id':self.admin_member.id,'role':'employee','active':False});self.assertEqual(r.status_code,400);self.admin_member.refresh_from_db();self.assertTrue(self.admin_member.active)
    def test_employee_direct_admin_action_denied(self):
        self.client.force_login(self.employee)
        for action in ['settings','product','archive','user_create','warehouse','contact']:
            self.assertEqual(self.action(action,{}).status_code,403)
    def test_product_optimistic_edit_conflict(self):
        r=self.action('product',{'id':self.p.id,'version':999});self.assertEqual(r.status_code,409)
    def test_product_photo_is_sanitized_versioned_and_permission_checked(self):
        from io import BytesIO
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        output=BytesIO();Image.new('RGB',(1000,500),'green').save(output,format='PNG')
        url=f'/api/b/{self.b.id}/products/{self.p.id}/photo/'
        before=self.p.version
        r=self.client.post(url,{'photo':SimpleUploadedFile('product.png',output.getvalue(),content_type='image/png')})
        self.assertEqual(r.status_code,200,r.content);self.p.refresh_from_db();self.assertEqual(self.p.version,before+1)
        r=self.client.get(url);self.assertEqual(r['Content-Type'],'image/jpeg')
        with Image.open(BytesIO(r.content)) as img:self.assertEqual(img.size,(800,400))
        self.client.force_login(self.employee)
        self.assertEqual(self.client.get(url).status_code,200)
        self.assertEqual(self.client.post(url,{'photo':SimpleUploadedFile('product.png',output.getvalue())}).status_code,403)
        self.client.force_login(self.other);self.assertEqual(self.client.get(url).status_code,403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(url,{'photo':SimpleUploadedFile('invalid.png',b'not an image')}).status_code,400)
    def test_change_of_currency_rejected_after_transaction(self):
        self.sale();r=self.action('settings',{'name':'A','sector':'Other','currency':'EUR','tax_rate':'0'});self.assertEqual(r.status_code,400)
    def test_reports_reconcile_with_sale_and_return(self):
        d=self.sale();report=self.client.get(f'/api/b/{self.b.id}/report/').json();self.assertEqual(Decimal(report['sales']),10);self.assertEqual(Decimal(report['margin']),6);return_sale(self.admin,self.b.id,d.id,{'request_key':str(uuid.uuid4()),'note':'Return'});r=self.client.get(f'/api/b/{self.b.id}/report/').json();self.assertEqual(Decimal(r['sales']),0);self.assertEqual(Decimal(r['margin']),0)
    def test_csrf_required_for_writes_and_login(self):
        c=Client(enforce_csrf_checks=True);c.force_login(self.admin);self.assertEqual(c.post(f'/api/b/{self.b.id}/action/','{}',content_type='application/json').status_code,403);self.assertEqual(Client(enforce_csrf_checks=True).post('/login/',{'username':'admin','password':'x'}).status_code,403)
    def test_forced_password_change_blocks_business_data(self):
        Profile.objects.create(user=self.employee,must_change_password=True);self.client.force_login(self.employee);self.assertEqual(self.client.get('/api/me/').status_code,403)
        r=self.client.post('/api/password/',json.dumps({'current':'TemporaryOnly-Long-Password!','password':'Fresh-Secure-Password-789!','confirm':'Fresh-Secure-Password-789!'}),content_type='application/json');self.assertEqual(r.status_code,200,r.content);self.assertEqual(self.client.get('/api/me/').status_code,200)
    def test_login_rate_limit_and_logout(self):
        c=Client()
        for _ in range(8):c.post('/login/',{'username':'admin','password':'incorrect'})
        r=c.post('/login/',{'username':'admin','password':'TestingOnly-Long-Password!'});self.assertContains(r,'Demasiados intentos')
        r=self.client.post('/logout/');self.assertEqual(r.status_code,302);self.assertEqual(self.client.get('/api/me/').status_code,401)
    def test_invoice_pdf_generation(self):
        from core.pdf import invoice_pdf
        d=self.sale();pdf=invoice_pdf(d.invoice);self.assertTrue(pdf.startswith(b'%PDF'));self.assertGreater(len(pdf),2000)
    def test_csv_formula_injection_neutralized(self):
        Product.objects.filter(pk=self.p.id).update(name='=HYPERLINK("https://example.com")');r=self.client.get(f'/api/b/{self.b.id}/export/');self.assertEqual(r.status_code,200);self.assertIn("'=HYPERLINK",r.content.decode())
    def test_all_main_http_surfaces(self):
        for url in ['/', '/api/me/', f'/api/b/{self.b.id}/state/', f'/api/b/{self.b.id}/report/', f'/api/b/{self.b.id}/export/?kind=movements', '/health/']:
            self.assertEqual(self.client.get(url).status_code,200,url)
    def test_login_page_has_no_default_credentials(self):
        r=Client().get('/login/');self.assertEqual(r.status_code,200);self.assertContains(r,'autocomplete="current-password"');self.assertNotContains(r,'TestingOnly')

@override_settings(**TEST_SETTINGS)
class DeploymentBootstrapTests(TestCase):
    def test_deployment_bootstrap_is_once_only_and_seeds_separately(self):
        from django.core.management import call_command
        from io import StringIO
        with patch.dict(os.environ, {'NEXO_BOOTSTRAP_USERNAME':'owner', 'NEXO_BOOTSTRAP_PASSWORD':'Initial-Secure-Password-972!', 'NEXO_SEED_DEMO':'1'}):
            call_command('bootstrap_deploy', stdout=StringIO())
        user=get_user_model().objects.get(username='owner')
        self.assertTrue(user.check_password('Initial-Secure-Password-972!'))
        self.assertEqual(Membership.objects.filter(user=user,role='admin').count(),2)
        self.assertEqual(Product.objects.filter(business__name='Mi negocio').count(),0)
        self.assertEqual(Product.objects.filter(business__name='Mercado Central · Ejemplo').count(),8)
        with patch.dict(os.environ, {'NEXO_BOOTSTRAP_PASSWORD':'Different-Password-883!'}):
            call_command('bootstrap_deploy', stdout=StringIO())
        user.refresh_from_db()
        self.assertTrue(user.check_password('Initial-Secure-Password-972!'))
        self.assertEqual(get_user_model().objects.count(),1)
    def test_deployment_bootstrap_requires_strong_secret(self):
        from django.core.management import call_command, CommandError
        from io import StringIO
        for password in ['', '123']:
            with patch.dict(os.environ, {'NEXO_BOOTSTRAP_PASSWORD':password}), self.assertRaises(CommandError):
                call_command('bootstrap_deploy', stdout=StringIO())
            self.assertFalse(get_user_model().objects.exists())

@skipIf(os.getenv('NEXO_EMBEDDED_TEST')=='1','Requires independent native PostgreSQL connections, not the embedded development engine')
@override_settings(**TEST_SETTINGS)
class ConcurrencyTests(Fixtures,TransactionTestCase):
    def test_two_sellers_cannot_oversell(self):
        Stock.objects.filter(product=self.p).update(quantity=5);barrier=Barrier(2)
        payloads=[self.payload(quantity='4'),self.payload(quantity='4')]
        def sell(payload):
            connections.close_all();user=get_user_model().objects.get(pk=self.admin.pk);barrier.wait(timeout=5)
            try:post_document(user,self.b.id,payload);return 'ok'
            except ValidationError:return 'insufficient'
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(sell,payloads))
        self.assertCountEqual(results,['ok','insufficient']);self.assertEqual(Stock.objects.get(product=self.p).quantity,1);self.assertEqual(Invoice.objects.count(),1)

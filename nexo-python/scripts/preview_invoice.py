"""Create a fictional invoice PDF inside a rolled-back transaction (testing only)."""
import os,sys,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','nexo.settings')
import django
django.setup()
from django.db import transaction
from django.contrib.auth import get_user_model
from core.models import Business,Membership,Warehouse,Product,Stock,Contact
from core.services import post_document
from core.pdf import invoice_pdf
root=Path(__file__).resolve().parent.parent
with transaction.atomic():
    user=get_user_model().objects.create_user(username='pdf-preview-'+uuid.uuid4().hex,password=None)
    b=Business.objects.create(name='Mercado Central - EJEMPLO',tax_id='IDENTIFICACIÓN DE EJEMPLO',address='Dirección de ejemplo, ciudad de ejemplo',email='ventas@example.com',tax_rate='8.00');Membership.objects.create(business=b,user=user,role='admin');w=Warehouse.objects.create(business=b,name='Principal')
    client=Contact.objects.create(business=b,name='Cliente de ejemplo',kind='customer',address='Dirección del cliente para demostración')
    lines=[]
    products=[('Café molido 250 g','4.20','6.50'),('Arroz premium 1 kg','1.10','2.25'),('Aceite de oliva 500 ml','5.30','8.90')]
    for index in range(30):
        name,cost,price=products[index%3]
        p=Product.objects.create(business=b,name=name+f' - Presentación {index+1}',sku=f'DEMO-{index+1:03}',category='Ejemplo',price=price,cost=cost)
        Stock.objects.create(product=p,warehouse=w,quantity=10)
        lines.append({'product':p.id,'quantity':'2','price':price})
    sale,_=post_document(user,b.id,{'kind':'sale','request_key':str(uuid.uuid4()),'warehouse':w.id,'contact':client.id,'note':'EJEMPLO. Documento ficticio para revisar el diseño y los saltos de página. No registra una operación real.','lines':lines})
    (root/'docs'/'Factura-ejemplo.pdf').write_bytes(invoice_pdf(sale.invoice))
    transaction.set_rollback(True)
print('Factura de ejemplo creada con 30 renglones; datos de prueba descartados.')

from django.core.management.base import BaseCommand,CommandError
from django.contrib.auth import get_user_model
from django.db import transaction
from decimal import Decimal
import uuid
from core.models import Business,Membership,Warehouse,Product,Contact
from core.services import post_document,post_payment
class Command(BaseCommand):
    help='Crear un negocio separado con datos ficticios; nunca mezcla datos con negocios existentes.'
    def add_arguments(self,p):p.add_argument('--username',required=True)
    @transaction.atomic
    def handle(self,*args,**o):
        try:u=get_user_model().objects.get(username=o['username'])
        except get_user_model().DoesNotExist:raise CommandError('Primero crea tu administrador.')
        if not Membership.objects.filter(user=u,role='admin',active=True).exists():raise CommandError('El usuario debe ser administrador.')
        if Business.objects.filter(name='Mercado Central · Ejemplo',memberships__user=u).exists():raise CommandError('Ya existe el negocio de ejemplo para esta cuenta.')
        b=Business.objects.create(name='Mercado Central · Ejemplo',address='Dirección de ejemplo',email='ventas@example.com',tax_rate=Decimal('8.00'))
        Membership.objects.create(business=b,user=u,role='admin');w=Warehouse.objects.create(business=b,name='Almacén principal',location='Área de recepción');Warehouse.objects.create(business=b,name='Punto de venta',location='Mostrador')
        c=Contact.objects.create(business=b,name='Distribuidora Central',kind='supplier',email='proveedor@example.com',notes='Contacto ficticio para practicar');client=Contact.objects.create(business=b,name='Cliente de ejemplo',kind='customer',email='cliente@example.com')
        rows=[('Café molido 250 g','CAF-001','Bebidas','4.20','6.50',24,10),('Arroz premium 1 kg','ARR-001','Abarrotes','1.10','2.25',42,15),('Aceite de oliva 500 ml','ACE-001','Abarrotes','5.30','8.90',7,10),('Leche entera 1 L','LEC-001','Lácteos','1.30','2.10',18,12),('Galletas de avena','GAL-001','Snacks','1.60','2.95',0,8),('Jabón de manos 250 ml','JAB-001','Limpieza','2.25','3.75',16,6),('Agua mineral 1 L','AGU-001','Bebidas','.45','1.20',60,20),('Papel de cocina','PAP-001','Limpieza','1.75','2.80',5,8)]
        products=[]
        for name,sku,cat,cost,price,stock,minimum in rows:
            p=Product.objects.create(business=b,name=name,sku=sku,category=cat,cost=Decimal(cost),price=Decimal(price),minimum=minimum,location='Estante A');products.append(p)
            if stock:post_document(u,b.id,{'request_key':str(uuid.uuid4()),'kind':'purchase','warehouse':w.id,'contact':c.id,'note':'Datos de ejemplo','lines':[{'product':p.id,'quantity':str(stock),'price':cost}]})
        sale,_=post_document(u,b.id,{'request_key':str(uuid.uuid4()),'kind':'sale','warehouse':w.id,'contact':client.id,'lines':[{'product':products[0].id,'quantity':'2','price':'6.50'},{'product':products[1].id,'quantity':'1','price':'2.25'}]})
        post_payment(u,b.id,sale.invoice.id,{'request_key':str(uuid.uuid4()),'amount':'10.00','method':'cash','reference':'Cobro de ejemplo'})
        self.stdout.write(self.style.SUCCESS('Negocio de ejemplo creado por separado.'))

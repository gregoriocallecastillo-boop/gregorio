from decimal import Decimal
from django.db import models
from django.db.models import Q
from django.conf import settings

class Business(models.Model):
    name=models.CharField(max_length=120)
    sector=models.CharField(max_length=80,default='Tienda / supermercado')
    currency=models.CharField(max_length=3,default='USD')
    tax_id=models.CharField(max_length=80,blank=True)
    address=models.CharField(max_length=300,blank=True)
    email=models.EmailField(blank=True)
    phone=models.CharField(max_length=60,blank=True)
    tax_rate=models.DecimalField(max_digits=5,decimal_places=2,default=0)
    next_document=models.PositiveIntegerField(default=1)
    next_invoice=models.PositiveIntegerField(default=1)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.CheckConstraint(condition=Q(tax_rate__gte=0,tax_rate__lte=100),name='business_tax_valid')]

class Membership(models.Model):
    ADMIN='admin';EMPLOYEE='employee'
    business=models.ForeignKey(Business,on_delete=models.CASCADE,related_name='memberships')
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    role=models.CharField(max_length=12,choices=[(ADMIN,'Administrador'),(EMPLOYEE,'Empleado')])
    active=models.BooleanField(default=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['business','user'],name='unique_membership')]

class Profile(models.Model):
    user=models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.CASCADE)
    must_change_password=models.BooleanField(default=False)

class LoginAttempt(models.Model):
    key=models.CharField(max_length=64,unique=True)
    failures=models.PositiveIntegerField(default=0)
    window_start=models.DateTimeField()

class Warehouse(models.Model):
    business=models.ForeignKey(Business,on_delete=models.PROTECT)
    name=models.CharField(max_length=100)
    location=models.CharField(max_length=200,blank=True)
    active=models.BooleanField(default=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['business','name'],name='unique_warehouse')]

class Contact(models.Model):
    business=models.ForeignKey(Business,on_delete=models.PROTECT)
    name=models.CharField(max_length=120)
    kind=models.CharField(max_length=12,choices=[('customer','Cliente'),('supplier','Proveedor')])
    email=models.EmailField(blank=True)
    phone=models.CharField(max_length=60,blank=True)
    tax_id=models.CharField(max_length=80,blank=True)
    address=models.CharField(max_length=300,blank=True)
    notes=models.CharField(max_length=500,blank=True)

class Product(models.Model):
    business=models.ForeignKey(Business,on_delete=models.PROTECT)
    name=models.CharField(max_length=120)
    sku=models.CharField(max_length=80)
    category=models.CharField(max_length=80)
    unit=models.CharField(max_length=20,default='unidad')
    price=models.DecimalField(max_digits=12,decimal_places=2,default=0)
    cost=models.DecimalField(max_digits=12,decimal_places=4,default=0)
    minimum=models.DecimalField(max_digits=14,decimal_places=3,default=0)
    expiry=models.DateField(null=True,blank=True)
    location=models.CharField(max_length=120,blank=True)
    active=models.BooleanField(default=True)
    photo=models.BinaryField(null=True,blank=True)
    version=models.PositiveIntegerField(default=1)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['business','sku'],name='unique_product_sku'),models.CheckConstraint(condition=Q(price__gte=0,cost__gte=0,minimum__gte=0),name='product_positive_values')]
        indexes=[models.Index(fields=['business','active','name'])]

class Stock(models.Model):
    product=models.ForeignKey(Product,on_delete=models.PROTECT,related_name='stocks')
    warehouse=models.ForeignKey(Warehouse,on_delete=models.PROTECT)
    quantity=models.DecimalField(max_digits=14,decimal_places=3,default=0)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['product','warehouse'],name='unique_stock'),models.CheckConstraint(condition=Q(quantity__gte=0),name='stock_never_negative')]

class Document(models.Model):
    business=models.ForeignKey(Business,on_delete=models.PROTECT)
    kind=models.CharField(max_length=12,choices=[('purchase','Compra'),('sale','Venta'),('adjustment','Ajuste'),('transfer','Traslado'),('return','Devolución')])
    number=models.CharField(max_length=40)
    request_key=models.UUIDField()
    request_hash=models.CharField(max_length=64)
    warehouse=models.ForeignKey(Warehouse,on_delete=models.PROTECT,related_name='+')
    destination=models.ForeignKey(Warehouse,on_delete=models.PROTECT,null=True,related_name='+')
    contact=models.ForeignKey(Contact,on_delete=models.PROTECT,null=True)
    contact_name=models.CharField(max_length=120,blank=True)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    note=models.CharField(max_length=500,blank=True)
    reference=models.CharField(max_length=120,blank=True)
    subtotal=models.DecimalField(max_digits=16,decimal_places=2,default=0)
    tax=models.DecimalField(max_digits=16,decimal_places=2,default=0)
    total=models.DecimalField(max_digits=16,decimal_places=2,default=0)
    original=models.OneToOneField('self',on_delete=models.PROTECT,null=True,related_name='reversal')
    class Meta:
        constraints=[models.UniqueConstraint(fields=['business','request_key'],name='document_idempotency'),models.UniqueConstraint(fields=['business','number'],name='unique_document_number')]
        indexes=[models.Index(fields=['business','created_at'])]

class DocumentLine(models.Model):
    document=models.ForeignKey(Document,on_delete=models.PROTECT,related_name='lines')
    product=models.ForeignKey(Product,on_delete=models.PROTECT)
    name=models.CharField(max_length=120)
    sku=models.CharField(max_length=80)
    unit=models.CharField(max_length=20)
    quantity=models.DecimalField(max_digits=14,decimal_places=3)
    unit_price=models.DecimalField(max_digits=12,decimal_places=2)
    unit_cost=models.DecimalField(max_digits=12,decimal_places=4)
    tax_rate=models.DecimalField(max_digits=5,decimal_places=2,default=0)
    subtotal=models.DecimalField(max_digits=16,decimal_places=2)
    tax=models.DecimalField(max_digits=16,decimal_places=2)
    total=models.DecimalField(max_digits=16,decimal_places=2)

class StockMovement(models.Model):
    business=models.ForeignKey(Business,on_delete=models.PROTECT)
    document=models.ForeignKey(Document,on_delete=models.PROTECT)
    product=models.ForeignKey(Product,on_delete=models.PROTECT)
    warehouse=models.ForeignKey(Warehouse,on_delete=models.PROTECT)
    delta=models.DecimalField(max_digits=14,decimal_places=3)
    balance=models.DecimalField(max_digits=14,decimal_places=3)
    cost=models.DecimalField(max_digits=12,decimal_places=4)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        indexes=[models.Index(fields=['business','product','created_at'])]

class Invoice(models.Model):
    business=models.ForeignKey(Business,on_delete=models.PROTECT)
    document=models.OneToOneField(Document,on_delete=models.PROTECT,related_name='invoice')
    number=models.CharField(max_length=40)
    kind=models.CharField(max_length=12,default='invoice')
    issuer=models.JSONField()
    customer=models.JSONField()
    currency=models.CharField(max_length=3)
    due_date=models.DateField()
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['business','number'],name='unique_invoice_number')]

class Payment(models.Model):
    invoice=models.ForeignKey(Invoice,on_delete=models.PROTECT,related_name='payments')
    amount=models.DecimalField(max_digits=16,decimal_places=2)
    method=models.CharField(max_length=20)
    reference=models.CharField(max_length=120,blank=True)
    request_key=models.UUIDField()
    request_hash=models.CharField(max_length=64)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    voided=models.BooleanField(default=False)
    void_reason=models.CharField(max_length=500,blank=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['invoice','request_key'],name='payment_idempotency'),models.CheckConstraint(condition=Q(amount__gt=0),name='positive_payment')]

class Audit(models.Model):
    business=models.ForeignKey(Business,on_delete=models.PROTECT)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    action=models.CharField(max_length=80)
    target=models.CharField(max_length=120)
    detail=models.JSONField(default=dict)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        indexes=[models.Index(fields=['business','created_at'])]

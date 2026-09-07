import hashlib,json,uuid
from datetime import date
from decimal import Decimal,InvalidOperation,ROUND_HALF_UP
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from .models import Business,Membership,Warehouse,Product,Stock,Contact,Document,DocumentLine,StockMovement,Invoice,Payment,Audit
ZERO=Decimal('0');MONEY=Decimal('.01');QTY=Decimal('.001');COST=Decimal('.0001')
UNITS=['unidad','kg','litro','metro','caja','paquete','par']
CURRENCIES=['USD','EUR','MXN','COP','PEN']
def text(value,maxlen=120,required=False):
    value=value.strip() if isinstance(value,str) else ''
    if len(value)>maxlen:raise ValidationError(f'El texto supera {maxlen} caracteres.')
    if required and not value:raise ValidationError('Completa los campos obligatorios.')
    return value

def decimal(value,quant=MONEY,minimum=ZERO,maximum=Decimal('999999999')):
    try:
        n=Decimal(str(value))
        if not n.is_finite() or n<minimum or n>maximum or n.quantize(quant)!=n:raise ValueError()
        return n.quantize(quant)
    except (ValueError,InvalidOperation,TypeError):raise ValidationError('Revisa las cantidades, precios y decimales permitidos.')

def member(user,business_id,admin=False,lock=False):
    qs=Membership.objects.select_for_update() if lock else Membership.objects
    try:m=qs.select_related('business').get(user=user,business_id=business_id,active=True)
    except (Membership.DoesNotExist,ValueError,TypeError):raise PermissionDenied('No tienes acceso a este negocio.')
    if admin and m.role!=Membership.ADMIN:raise PermissionDenied('Esta operación requiere un administrador.')
    return m

def audit(b,user,action,target,detail=None):return Audit.objects.create(business=b,actor=user,action=action,target=str(target),detail=detail or {})
def fingerprint(payload):return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def request_key(payload):
    try:return uuid.UUID(str(payload.get('request_key')))
    except (ValueError,TypeError,AttributeError):raise ValidationError('Falta la referencia única de la operación. Actualiza la página.')
def _stock(product,warehouse):return Stock.objects.select_for_update().get_or_create(product=product,warehouse=warehouse)[0]
def _change(b,doc,p,w,delta):
    stock=_stock(p,w);stock.quantity+=delta
    if stock.quantity<0:raise ValidationError(f'Existencias insuficientes de {p.name} en {w.name}.')
    if stock.quantity>Decimal('99999999999'):raise ValidationError('La cantidad supera la capacidad del registro.')
    stock.save(update_fields=['quantity'])
    StockMovement.objects.create(business=b,document=doc,product=p,warehouse=w,delta=delta,balance=stock.quantity,cost=p.cost)

def snapshot_contact(c):return {'name':c.name,'tax_id':c.tax_id,'email':c.email,'address':c.address,'phone':c.phone} if c else {'name':'Consumidor final','tax_id':'','email':'','address':'','phone':''}
def _invoice(b,doc,due=None,kind='invoice',customer=None):
    number=f'{"NC" if kind=="credit" else "FAC"}-{b.next_invoice:06d}';b.next_invoice+=1
    issuer={k:getattr(b,k) for k in ['name','tax_id','address','email','phone']}
    return Invoice.objects.create(business=b,document=doc,number=number,kind=kind,issuer=issuer,customer=customer or snapshot_contact(doc.contact),currency=b.currency,due_date=due or timezone.localdate())

@transaction.atomic
def post_document(user,business_id,payload):
    b=Business.objects.select_for_update().get(pk=business_id)
    m=member(user,b.id)
    kind=payload.get('kind')
    if kind not in ['purchase','sale','adjustment','transfer']:raise ValidationError('Tipo de operación no válido.')
    if m.role!='admin' and kind!='sale':raise PermissionDenied('Solo administradores pueden registrar compras, ajustes o traslados.')
    key=request_key(payload);digest=fingerprint(payload)
    previous=Document.objects.filter(business=b,request_key=key).first()
    if previous:
        if previous.request_hash!=digest:raise ValidationError('Esta referencia ya se utilizó para una operación diferente.')
        if m.role!='admin' and previous.created_by_id!=user.id:raise PermissionDenied()
        return previous,False
    try:w=Warehouse.objects.get(pk=payload.get('warehouse'),business=b,active=True)
    except (Warehouse.DoesNotExist,ValueError,TypeError):raise ValidationError('Selecciona un almacén válido.')
    dest=None
    if kind=='transfer':
        try:dest=Warehouse.objects.get(pk=payload.get('destination'),business=b,active=True)
        except (Warehouse.DoesNotExist,ValueError,TypeError):raise ValidationError('Selecciona un almacén de destino válido.')
        if dest==w:raise ValidationError('Origen y destino deben ser distintos.')
    c=None
    if payload.get('contact'):
        try:c=Contact.objects.get(pk=payload['contact'],business=b,kind='supplier' if kind=='purchase' else 'customer')
        except (Contact.DoesNotExist,ValueError,TypeError):raise ValidationError('Contacto no válido para esta operación.')
    note=text(payload.get('note'),500,required=kind in ['adjustment','transfer'])
    raw=payload.get('lines')
    if not isinstance(raw,list) or not 1<=len(raw)<=100:raise ValidationError('Agrega entre 1 y 100 productos.')
    checked=[];seen=set()
    for row in raw:
        if not isinstance(row,dict):raise ValidationError('Línea no válida.')
        try:p=Product.objects.select_for_update().get(pk=row.get('product'),business=b,active=True)
        except (Product.DoesNotExist,ValueError,TypeError):raise ValidationError('Producto no disponible.')
        if p.pk in seen:raise ValidationError('No repitas un producto en la misma operación.')
        seen.add(p.pk)
        q=decimal(row.get('quantity'),QTY,Decimal('-999999999') if kind=='adjustment' else QTY)
        if not q:raise ValidationError('La cantidad no puede ser cero.')
        price=decimal(row.get('price',p.price if kind=='sale' else p.cost.quantize(MONEY))) if kind in ['sale','purchase'] else ZERO
        if m.role!='admin' and price!=p.price:raise PermissionDenied('El empleado debe usar el precio vigente del catálogo.')
        stock=_stock(p,w)
        if 'counted' in row:
            if kind!='adjustment':raise ValidationError('El conteo solo puede registrar un ajuste.')
            counted=decimal(row['counted'],QTY)
            expected=decimal(row.get('expected'),QTY)
            latest=StockMovement.objects.filter(product=p,warehouse=w).order_by('-id').values_list('id',flat=True).first() or 0
            if stock.quantity!=expected or row.get('last_movement')!=latest:
                raise ValidationError('Las existencias cambiaron mientras contabas. Actualiza el conteo y revisa de nuevo antes de guardar.')
            if q!=counted-expected:raise ValidationError('La diferencia del conteo no coincide. Revisa el cambio.')
        if kind in ['sale','transfer'] and stock.quantity<q or kind=='adjustment' and stock.quantity+q<0:raise ValidationError(f'Stock insuficiente: {p.name}. Disponible: {stock.quantity} {p.unit}.')
        if kind=='sale' and p.expiry and p.expiry<timezone.localdate():raise ValidationError(f'El producto {p.name} está vencido.')
        rate=b.tax_rate if kind in ['sale','purchase'] else ZERO
        sub=(q*price).quantize(MONEY,rounding=ROUND_HALF_UP);tax=(sub*rate/100).quantize(MONEY,rounding=ROUND_HALF_UP)
        checked.append((p,q,price,rate,sub,tax,p.cost))
    doc=Document.objects.create(business=b,kind=kind,number=f'MOV-{b.next_document:06d}',request_key=key,request_hash=digest,warehouse=w,destination=dest,contact=c,contact_name=c.name if c else '',created_by=user,note=note,reference=text(payload.get('reference')))
    b.next_document+=1
    for p,q,price,rate,sub,tax,oldcost in checked:
        if kind=='purchase':
            totalstock=Stock.objects.filter(product=p).aggregate(n=Sum('quantity'))['n'] or ZERO
            p.cost=((totalstock*p.cost+q*price)/(totalstock+q)).quantize(COST,rounding=ROUND_HALF_UP);p.save(update_fields=['cost'])
        _change(b,doc,p,w,-q if kind in ['sale','transfer'] else q)
        if dest:_change(b,doc,p,dest,q)
        DocumentLine.objects.create(document=doc,product=p,name=p.name,sku=p.sku,unit=p.unit,quantity=q,unit_price=price,unit_cost=oldcost,tax_rate=rate,subtotal=sub,tax=tax,total=sub+tax)
        doc.subtotal+=sub;doc.tax+=tax
    doc.total=doc.subtotal+doc.tax;doc.save(update_fields=['subtotal','tax','total'])
    if kind=='sale':
        try:due=date.fromisoformat(payload.get('due_date') or str(timezone.localdate()))
        except (ValueError,TypeError):raise ValidationError('Fecha de vencimiento no válida.')
        if due<timezone.localdate():raise ValidationError('La fecha de pago no puede ser anterior a hoy.')
        _invoice(b,doc,due)
    b.save(update_fields=['next_document','next_invoice'])
    audit(b,user,'document.posted',doc.number,{'kind':kind,'total':str(doc.total)})
    return doc,True

@transaction.atomic
def return_sale(user,business_id,document_id,payload):
    b=Business.objects.select_for_update().get(pk=business_id);member(user,b.id,admin=True)
    key=request_key(payload);digest=fingerprint({'document':document_id,**payload})
    previous=Document.objects.filter(business=b,request_key=key).first()
    if previous:
        if previous.request_hash!=digest:raise ValidationError('Referencia ya utilizada.')
        return previous,False
    try:original=Document.objects.select_for_update().get(pk=document_id,business=b,kind='sale')
    except Document.DoesNotExist:raise ValidationError('Venta no encontrada.')
    if Document.objects.filter(original=original).exists():raise ValidationError('Esta venta ya tiene una devolución.')
    if original.invoice.payments.filter(voided=False).exists():raise ValidationError('Primero registra la anulación o el reembolso de sus cobros en Facturación. Luego devuelve la venta.')
    doc=Document.objects.create(business=b,kind='return',number=f'MOV-{b.next_document:06d}',request_key=key,request_hash=digest,warehouse=original.warehouse,contact=original.contact,contact_name=original.contact_name,created_by=user,note=text(payload.get('note'),500,True),original=original,subtotal=original.subtotal,tax=original.tax,total=original.total)
    b.next_document+=1
    for l in original.lines.select_related('product'):
        p=Product.objects.select_for_update().get(pk=l.product_id)
        totalstock=Stock.objects.filter(product=p).aggregate(n=Sum('quantity'))['n'] or ZERO
        p.cost=((totalstock*p.cost+l.quantity*l.unit_cost)/(totalstock+l.quantity)).quantize(COST,rounding=ROUND_HALF_UP);p.active=True;p.save(update_fields=['cost','active'])
        _change(b,doc,p,original.warehouse,l.quantity)
        DocumentLine.objects.create(document=doc,product=p,name=l.name,sku=l.sku,unit=l.unit,quantity=l.quantity,unit_price=l.unit_price,unit_cost=l.unit_cost,tax_rate=l.tax_rate,subtotal=l.subtotal,tax=l.tax,total=l.total)
    _invoice(b,doc,kind='credit',customer=original.invoice.customer)
    b.save(update_fields=['next_document','next_invoice']);audit(b,user,'sale.returned',original.number,{'credit':doc.invoice.number,'reason':doc.note})
    return doc,True

def invoice_paid(inv):
    if 'payments' in getattr(inv,'_prefetched_objects_cache',{}):return sum((p.amount for p in inv.payments.all() if not p.voided),ZERO)
    return inv.payments.filter(voided=False).aggregate(n=Sum('amount'))['n'] or ZERO

def invoice_status(inv):
    if inv.kind=='credit':return 'credit'
    if hasattr(inv.document,'reversal'):return 'credited'
    paid=invoice_paid(inv)
    if paid>=inv.document.total:return 'paid'
    if inv.due_date<timezone.localdate():return 'overdue'
    return 'partial' if paid else 'pending'

@transaction.atomic
def post_payment(user,business_id,invoice_id,payload):
    b=Business.objects.select_for_update().get(pk=business_id);m=member(user,b.id)
    try:inv=Invoice.objects.select_for_update().select_related('document').get(pk=invoice_id,business=b)
    except Invoice.DoesNotExist:raise ValidationError('Factura no encontrada.')
    if m.role!='admin' and inv.document.created_by_id!=user.id:raise PermissionDenied('Solo puedes registrar cobros de tus ventas.')
    key=request_key(payload);digest=fingerprint(payload)
    prev=Payment.objects.filter(invoice=inv,request_key=key).first()
    if prev:
        if prev.request_hash!=digest:raise ValidationError('Referencia ya utilizada.')
        return prev,False
    if invoice_status(inv) in ['credit','credited']:raise ValidationError('No se pueden registrar cobros para este documento.')
    amount=decimal(payload.get('amount'),minimum=MONEY)
    if amount>inv.document.total-invoice_paid(inv):raise ValidationError('El cobro supera el saldo pendiente.')
    method=payload.get('method')
    if method not in ['cash','card','transfer']:raise ValidationError('Selecciona efectivo, tarjeta o transferencia.')
    p=Payment.objects.create(invoice=inv,amount=amount,method=method,reference=text(payload.get('reference')),request_key=key,request_hash=digest,created_by=user)
    audit(b,user,'payment.recorded',inv.number,{'amount':str(amount),'method':method});return p,True

@transaction.atomic
def void_payment(user,business_id,payment_id,reason):
    b=Business.objects.select_for_update().get(pk=business_id);member(user,b.id,admin=True)
    try:p=Payment.objects.select_for_update().select_related('invoice').get(pk=payment_id,invoice__business=b)
    except Payment.DoesNotExist:raise ValidationError('Cobro no encontrado.')
    if p.voided:raise ValidationError('Este cobro ya está anulado.')
    p.void_reason=text(reason,500,True);p.voided=True;p.save(update_fields=['voided','void_reason'])
    audit(b,user,'payment.voided',p.invoice.number,{'payment':p.id,'amount':str(p.amount),'reason':p.void_reason})

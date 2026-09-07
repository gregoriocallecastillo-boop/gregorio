import csv,hashlib,io,json,logging,uuid
from datetime import date,timedelta
from decimal import Decimal
from functools import wraps
from django.conf import settings
from django.contrib.auth import authenticate,login,logout,update_session_auth_hash,get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError,PermissionDenied,ObjectDoesNotExist
from django.db import transaction,IntegrityError,DatabaseError
from django.db.models import Sum,Q,Exists,OuterRef,Case,When,Value,BooleanField,F
from django.http import JsonResponse,HttpResponse,FileResponse
from django.shortcuts import render,redirect
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from .models import *
from .services import *
User=get_user_model();log=logging.getLogger(__name__)

def response(data,status=200):
    r=JsonResponse(data,status=status);r['Cache-Control']='no-store';return r

def api(fn):
    @wraps(fn)
    def wrapped(request,*args,**kwargs):
        if not request.user.is_authenticated:return response({'error':'Inicia sesión para continuar.'},401)
        if Profile.objects.filter(user=request.user,must_change_password=True).exists() and fn.__name__!='password_change':return response({'error':'Cambia tu contraseña temporal para continuar.','must_change_password':True},403)
        try:return fn(request,*args,**kwargs)
        except PermissionDenied as e:return response({'error':str(e) or 'No tienes permiso para esta operación.'},403)
        except (ValidationError,ValueError,TypeError,KeyError,AttributeError) as e:
            msg=' '.join(e.messages) if isinstance(e,ValidationError) else 'Revisa los datos de la solicitud.'
            return response({'error':msg},400)
        except ObjectDoesNotExist:return response({'error':'Registro no encontrado.'},404)
        except IntegrityError:return response({'error':'El registro entra en conflicto con otro existente. Actualiza y vuelve a intentar.'},409)
        except DatabaseError:
            log.exception('Database operation failed');return response({'error':'No se pudo completar la operación. Conserva tus datos y vuelve a intentar.'},503)
    return wrapped

def body(request):
    if request.method!='POST':raise PermissionDenied('Método no permitido.')
    try:p=json.loads(request.body)
    except (ValueError,UnicodeDecodeError):raise ValidationError('Solicitud no válida.')
    if not isinstance(p,dict):raise ValidationError('Solicitud no válida.')
    return p

@ensure_csrf_cookie
def login_page(request):
    if request.user.is_authenticated:return redirect('/')
    error=''
    if request.method=='POST':
        username=request.POST.get('username','').strip()[:150];password=request.POST.get('password','')
        key=hashlib.sha256(username.lower().encode()).hexdigest();now=timezone.now()
        with transaction.atomic():
            attempt,_=LoginAttempt.objects.select_for_update().get_or_create(key=key,defaults={'window_start':now})
            if now-attempt.window_start>timedelta(minutes=15):attempt.failures=0;attempt.window_start=now
            if attempt.failures>=8:error='Demasiados intentos. Espera 15 minutos antes de volver a intentar.'
            else:
                user=authenticate(request,username=username,password=password)
                if user is not None and Membership.objects.filter(user=user,active=True).exists():
                    attempt.failures=0;attempt.save();login(request,user);return redirect('/')
                attempt.failures+=1;error='Usuario o contraseña incorrectos.'
            attempt.save()
    return render(request,'core/login.html',{'error':error})

@require_POST
def logout_view(request):logout(request);return redirect('/login/')

@ensure_csrf_cookie
def home(request):
    if not request.user.is_authenticated:return redirect('/login/')
    return render(request,'core/app.html',{'password_required':Profile.objects.filter(user=request.user,must_change_password=True).exists()})

@api
@require_POST
def password_change(request):
    p=body(request)
    if not request.user.check_password(p.get('current','')):raise ValidationError('La contraseña actual no es correcta.')
    password=p.get('password','');validate_password(password,request.user)
    if password!=p.get('confirm'):raise ValidationError('Las contraseñas nuevas no coinciden.')
    with transaction.atomic():
        request.user.set_password(password);request.user.save(update_fields=['password'])
        Profile.objects.update_or_create(user=request.user,defaults={'must_change_password':False})
    update_session_auth_hash(request,request.user);return response({'ok':True})

@api
def bootstrap(request):
    if request.method!='GET':return response({'error':'Método no permitido.'},405)
    ms=Membership.objects.filter(user=request.user,active=True).select_related('business')
    return response({'user':{'name':request.user.first_name or request.user.username,'username':request.user.username},'businesses':[{'id':m.business_id,'name':m.business.name,'role':m.role} for m in ms]})

def product_data(p,admin):
    stocks=[{'warehouse':s.warehouse_id,'name':s.warehouse.name,'quantity':str(s.quantity)} for s in p.stocks.all()]
    d={k:getattr(p,k) for k in ['id','name','sku','category','unit','price','minimum','expiry','location','active','version']}
    d.update(stock=sum((s.quantity for s in p.stocks.all()),ZERO),stocks=stocks,has_photo=getattr(p,'photo_present',False))
    if admin:d['cost']=p.cost
    return d

def invoice_data(inv):
    paid=invoice_paid(inv);status=invoice_status(inv)
    return {'id':inv.id,'number':inv.number,'kind':inv.kind,'date':inv.created_at,'due_date':inv.due_date,'customer':inv.customer,'issuer':inv.issuer,'currency':inv.currency,'document':inv.document_id,'created_by':inv.document.created_by_id,'subtotal':inv.document.subtotal,'tax':inv.document.tax,'total':inv.document.total,'paid':paid,'balance':ZERO if status in ['credit','credited'] else inv.document.total-paid,'status':status,'payments':[{'id':p.id,'amount':p.amount,'method':p.method,'reference':p.reference,'date':p.created_at,'voided':p.voided,'void_reason':p.void_reason} for p in inv.payments.all()]}

def doc_data(d,admin):
    lines=[]
    for l in d.lines.all():
        line={k:getattr(l,k) for k in ['name','sku','unit','quantity','unit_price','tax_rate','subtotal','tax','total']}
        line['product']=l.product_id
        if admin:line['unit_cost']=l.unit_cost
        lines.append(line)
    return {'id':d.id,'number':d.number,'kind':d.kind,'date':d.created_at,'contact':d.contact_name,'warehouse':d.warehouse.name,'destination':d.destination.name if d.destination else '', 'creator':d.created_by.first_name or d.created_by.username,'lines':lines,'subtotal':d.subtotal,'tax':d.tax,'total':d.total,'reference':d.reference,'note':d.note,'returned':getattr(d,'is_returned',False),'invoice_id':getattr(getattr(d,'invoice',None),'id',None)}

@api
def state(request,business_id):
    m=member(request.user,business_id);b=m.business;admin=m.role=='admin'
    products=Product.objects.filter(business=b).defer('photo').annotate(photo_present=Case(When(photo__isnull=False,then=Value(True)),default=Value(False),output_field=BooleanField())).prefetch_related('stocks__warehouse').order_by('name')
    docs=Document.objects.filter(business=b).select_related('warehouse','destination','created_by','invoice').annotate(is_returned=Exists(Document.objects.filter(original_id=OuterRef('pk')))).prefetch_related('lines').order_by('-id')
    invs=Invoice.objects.filter(business=b).select_related('document','document__reversal').prefetch_related('payments').order_by('-id')
    contacts=Contact.objects.filter(business=b).order_by('name')
    if not admin:docs=docs.filter(kind='sale',created_by=request.user);invs=invs.filter(document__created_by=request.user);contacts=contacts.filter(kind='customer')
    data={'business':{k:getattr(b,k) for k in ['id','name','sector','currency','tax_id','address','email','phone','tax_rate']},'role':m.role,'products':[product_data(p,admin) for p in products],'warehouses':list(Warehouse.objects.filter(business=b).values('id','name','location','active')),'contacts':list(contacts.values('id','name','kind','email','phone','tax_id','address','notes')),'documents':[doc_data(d,admin) for d in docs[:250]],'invoices':[invoice_data(i) for i in invs[:250]],'history_limit':250}
    if admin:
        data['users']=[{'id':x.id,'user_id':x.user_id,'username':x.user.username,'name':x.user.first_name,'role':x.role,'active':x.active} for x in Membership.objects.filter(business=b).select_related('user')]
        data['audit']=[{'date':a.created_at,'actor':a.actor.username,'action':a.action,'target':a.target,'detail':a.detail} for a in Audit.objects.filter(business=b).select_related('actor').order_by('-id')[:150]]
    return response(data)

@api
def report(request,business_id):
    m=member(request.user,business_id);b=m.business;admin=m.role=='admin'
    today=timezone.localdate()
    try:start=date.fromisoformat(request.GET.get('start',str(today.replace(day=1))));end=date.fromisoformat(request.GET.get('end',str(today)))
    except ValueError:raise ValidationError('Fechas no válidas.')
    if end<start or (end-start).days>366:raise ValidationError('Selecciona un período de hasta 366 días.')
    docs=Document.objects.filter(business=b,created_at__date__gte=start,created_at__date__lte=end)
    if not admin:docs=docs.filter(created_by=request.user,kind='sale')
    totals={k:docs.filter(kind=k).aggregate(n=Sum('subtotal'))['n'] or ZERO for k in ['sale','purchase','return']}
    sales=docs.filter(kind='sale');returns=docs.filter(kind='return')
    margin=ZERO;ranking={};daily={}
    for d in docs.filter(kind__in=['sale','return']).prefetch_related('lines'):
        sign=-1 if d.kind=='return' else 1;day=str(timezone.localtime(d.created_at).date())
        daily[day]=daily.get(day,ZERO)+sign*d.subtotal
        for l in d.lines.all():
            margin+=sign*(l.subtotal-l.quantity*l.unit_cost)
            key=(l.product_id,l.name,l.unit)
            r=ranking.setdefault(key,{'name':l.name,'unit':l.unit,'quantity':ZERO,'revenue':ZERO});r['quantity']+=sign*l.quantity;r['revenue']+=sign*l.subtotal
    result={'start':start,'end':end,'sales':totals['sale']-totals['return'],'sale_count':sales.count(),'daily':[{'date':k,'value':v} for k,v in sorted(daily.items())],'ranking':sorted(ranking.values(),key=lambda r:r['quantity'],reverse=True)[:8]}
    if admin:
        inventory=ZERO;categories={}
        for s in Stock.objects.filter(product__business=b,product__active=True).select_related('product'):
            val=s.quantity*s.product.cost;inventory+=val;categories[s.product.category]=categories.get(s.product.category,ZERO)+val
        invs=Invoice.objects.filter(business=b,kind='invoice').select_related('document','document__reversal').prefetch_related('payments')
        receivable=sum((i.document.total-invoice_paid(i) for i in invs if invoice_status(i) not in ['credited','paid']),ZERO)
        result.update(purchases=totals['purchase'],returns=totals['return'],margin=margin.quantize(MONEY,rounding=ROUND_HALF_UP),inventory=inventory.quantize(MONEY,rounding=ROUND_HALF_UP),receivable=receivable,categories=[{'name':k,'value':v} for k,v in sorted(categories.items(),key=lambda x:-x[1])])
    return response(result)

@api
@require_POST
def action(request,business_id):
    p=body(request);op=p.get('action');data=p.get('data',{})
    if not isinstance(data,dict):raise ValidationError('Datos no válidos.')
    m=member(request.user,business_id);b=m.business;admin=m.role=='admin'
    if op=='document':d,created=post_document(request.user,b.id,data);return response({'ok':True,'created':created,'document':d.id,'invoice':getattr(getattr(d,'invoice',None),'id',None)})
    if op=='return':d,created=return_sale(request.user,b.id,data.get('document'),data);return response({'ok':True,'created':created,'document':d.id})
    if op=='payment':pay,created=post_payment(request.user,b.id,data.get('invoice'),data);return response({'ok':True,'created':created,'payment':pay.id})
    if op=='void_payment':void_payment(request.user,b.id,data.get('id'),data.get('reason'));return response({'ok':True})
    if not admin:raise PermissionDenied('Esta operación requiere un administrador.')
    with transaction.atomic():
        b=Business.objects.select_for_update().get(pk=b.id)
        member(request.user,b.id,admin=True)
        if op=='product':
            obj=Product.objects.select_for_update().get(pk=data['id'],business=b) if data.get('id') else Product(business=b)
            new=not obj.pk
            if not new and data.get('version')!=obj.version:return response({'error':'El producto fue modificado en otra sesión. Actualiza antes de guardar.'},409)
            if not new and data.get('unit')!=obj.unit and DocumentLine.objects.filter(product=obj).exists():raise ValidationError('La unidad no puede cambiar después de registrar movimientos.')
            for key,length in [('name',120),('sku',80),('category',80),('unit',20)]:setattr(obj,key,text(data.get(key),length,True))
            obj.sku=obj.sku.upper()
            if obj.unit not in UNITS:raise ValidationError('Unidad no válida.')
            obj.price=decimal(data.get('price'));obj.minimum=decimal(data.get('minimum'),QTY)
            if new:obj.cost=decimal(data.get('cost'),COST)
            obj.location=text(data.get('location'))
            obj.expiry=date.fromisoformat(data['expiry']) if data.get('expiry') else None
            obj.version+=0 if new else 1;obj.full_clean(exclude=['photo']);obj.save()
            if new and data.get('initial') not in (None,'',0,'0'):
                initial=decimal(data['initial'],QTY)
                if initial:post_document(request.user,b.id,{'request_key':str(uuid.uuid4()),'kind':'adjustment','warehouse':data.get('warehouse'),'note':'Existencias iniciales','lines':[{'product':obj.id,'quantity':str(initial)}]})
            audit(b,request.user,'product.created' if new else 'product.updated',obj.sku)
        elif op=='archive':
            obj=Product.objects.get(pk=data.get('id'),business=b)
            if obj.active and Stock.objects.filter(product=obj,quantity__gt=0).exists():raise ValidationError('El producto debe tener existencias en cero para archivarlo.')
            obj.active=not obj.active;obj.version+=1;obj.save(update_fields=['active','version']);audit(b,request.user,'product.archived' if not obj.active else 'product.restored',obj.sku)
        elif op=='contact':
            obj=Contact.objects.get(pk=data['id'],business=b) if data.get('id') else Contact(business=b)
            for key,length in [('name',120),('kind',12),('email',254),('phone',60),('tax_id',80),('address',300),('notes',500)]:setattr(obj,key,text(data.get(key),length,key in ['name','kind']))
            obj.full_clean();obj.save();audit(b,request.user,'contact.saved',obj.name)
        elif op=='warehouse':
            obj=Warehouse.objects.get(pk=data['id'],business=b) if data.get('id') else Warehouse(business=b)
            obj.name=text(data.get('name'),100,True);obj.location=text(data.get('location'),200);obj.full_clean();obj.save();audit(b,request.user,'warehouse.saved',obj.name)
        elif op=='settings':
            currency=data.get('currency')
            if currency not in CURRENCIES:raise ValidationError('Moneda no válida.')
            if b.currency!=currency and Document.objects.filter(business=b).exists():raise ValidationError('La moneda queda fija tras el primer movimiento.')
            for key,length in [('name',120),('sector',80),('tax_id',80),('address',300),('email',254),('phone',60)]:setattr(b,key,text(data.get(key),length,key in ['name','sector']))
            b.currency=currency;b.tax_rate=decimal(data.get('tax_rate'),maximum=Decimal(100));b.full_clean();b.save();audit(b,request.user,'business.updated',b.name)
        elif op=='user_create':
            role=data.get('role')
            if role not in ['admin','employee']:raise ValidationError('Rol no válido.')
            user=User(username=text(data.get('username'),150,True),first_name=text(data.get('name'),150,True),email=text(data.get('email'),254));user.full_clean(exclude=['password']);validate_password(data.get('password',''),user);user.set_password(data['password']);user.save()
            Membership.objects.create(business=b,user=user,role=role);Profile.objects.create(user=user,must_change_password=True);audit(b,request.user,'user.created',user.username,{'role':role})
        elif op=='user_update':
            target=Membership.objects.select_for_update().get(pk=data.get('id'),business=b)
            role=data.get('role');active=data.get('active')
            if role not in ['admin','employee'] or not isinstance(active,bool):raise ValidationError('Permisos no válidos.')
            if target.role=='admin' and target.active and (role!='admin' or not active) and Membership.objects.filter(business=b,role='admin',active=True).count()<=1:raise ValidationError('Debe permanecer al menos un administrador activo.')
            target.role=role;target.active=active;target.save();audit(b,request.user,'user.permissions',target.user.username,{'role':role,'active':active})
        else:raise ValidationError('Acción no disponible.')
    return response({'ok':True,'id':getattr(locals().get('obj'),'id',None)})

@api
@require_POST
def create_business(request):
    if not Membership.objects.filter(user=request.user,role='admin',active=True).exists():raise PermissionDenied()
    p=body(request)
    with transaction.atomic():
        currency=p.get('currency','USD')
        if currency not in CURRENCIES:raise ValidationError('Moneda no válida.')
        b=Business(name=text(p.get('name'),120,True),sector=text(p.get('sector'),80,True),currency=currency);b.full_clean();b.save()
        Membership.objects.create(business=b,user=request.user,role='admin');Warehouse.objects.create(business=b,name='Almacén principal');audit(b,request.user,'business.created',b.name)
    return response({'ok':True,'id':b.id})

@api
def photo(request,business_id,product_id):
    member(request.user,business_id,admin=request.method=='POST')
    obj=Product.objects.get(pk=product_id,business_id=business_id)
    if request.method=='GET':
        if not obj.photo:return HttpResponse(status=404)
        r=HttpResponse(bytes(obj.photo),content_type='image/jpeg');r['Cache-Control']='private, max-age=300';return r
    if request.method!='POST':return response({'error':'Método no permitido.'},405)
    file=request.FILES.get('photo')
    if not file or file.size>2*1024*1024:raise ValidationError('Selecciona una imagen JPG o PNG de hasta 2 MB.')
    from PIL import Image,UnidentifiedImageError,ImageOps
    try:
        img=Image.open(file)
        if img.format not in ['PNG','JPEG','WEBP'] or img.width*img.height>16_000_000:raise ValidationError('Imagen no permitida o demasiado grande.')
        img=ImageOps.exif_transpose(img).convert('RGB');img.thumbnail((800,800));output=io.BytesIO();img.save(output,format='JPEG',quality=82)
    except (UnidentifiedImageError,OSError,Image.DecompressionBombError):raise ValidationError('La imagen no es válida.')
    with transaction.atomic():
        b=Business.objects.select_for_update().get(pk=business_id);member(request.user,business_id,admin=True)
        Product.objects.filter(pk=obj.pk).update(photo=output.getvalue(),version=F('version')+1);audit(b,request.user,'product.photo',obj.sku)
    return response({'ok':True})

@api
def export_csv(request,business_id):
    member(request.user,business_id,admin=True);kind=request.GET.get('kind','inventory')
    stream=io.StringIO();stream.write('\ufeff');writer=csv.writer(stream)
    def row(values):
        safe=[]
        for v in values:
            s=str(v if v is not None else '')
            if s.startswith(('=','+','-','@','\t','\r')):s="'"+s
            safe.append(s)
        writer.writerow(safe)
    if kind=='inventory':
        row(['Código','Producto','Categoría','Unidad','Almacén','Existencias','Costo promedio','Precio','Mínimo','Vencimiento','Activo'])
        for p in Product.objects.filter(business_id=business_id).prefetch_related('stocks__warehouse').order_by('sku'):
            stocks=list(p.stocks.all())
            for s in stocks or [None]:row([p.sku,p.name,p.category,p.unit,s.warehouse.name if s else '',s.quantity if s else 0,p.cost,p.price,p.minimum,p.expiry,p.active])
    elif kind=='movements':
        row(['Fecha','Documento','Tipo','Código','Producto','Almacén','Cambio','Saldo','Costo'])
        for m in StockMovement.objects.filter(business_id=business_id).select_related('document','product','warehouse').order_by('id').iterator():row([m.created_at,m.document.number,m.document.kind,m.product.sku,m.product.name,m.warehouse.name,m.delta,m.balance,m.cost])
    elif kind=='invoices':
        row(['Número','Tipo','Fecha','Cliente','Moneda','Base','Impuesto','Total','Cobrado','Estado'])
        for i in Invoice.objects.filter(business_id=business_id).select_related('document').order_by('id').iterator():row([i.number,i.kind,i.created_at,i.customer['name'],i.currency,i.document.subtotal,i.document.tax,i.document.total,invoice_paid(i),invoice_status(i)])
    else:raise ValidationError('Exportación no disponible.')
    r=HttpResponse(stream.getvalue(),content_type='text/csv; charset=utf-8');r['Content-Disposition']=f'attachment; filename="nexo-{kind}.csv"';r['Cache-Control']='no-store';return r

@api
def invoice_view(request,business_id,invoice_id):
    m=member(request.user,business_id)
    inv=Invoice.objects.select_related('document').get(pk=invoice_id,business_id=business_id)
    if m.role!='admin' and inv.document.created_by_id!=request.user.id:raise PermissionDenied()
    from .pdf import invoice_pdf
    r=HttpResponse(invoice_pdf(inv),content_type='application/pdf');r['Content-Disposition']=f'inline; filename="{inv.number}.pdf"';r['Cache-Control']='no-store';return r

def health(request):
    from django.db import connection
    try:
        with connection.cursor() as cur:cur.execute('SELECT 1');cur.fetchone()
        return response({'status':'ok'})
    except DatabaseError:return response({'status':'unavailable'},503)

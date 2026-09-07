"""Read-only, paginated stock ledger with opening balances and full CSV export."""
import csv
import io
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum, Q, Max
from django.http import HttpResponse
from django.utils import timezone

from .models import Business, Product, Warehouse, StockMovement, Stock

ZERO = Decimal('0')
PAGE_SIZE = 50
KINDS = {'sale': 'Venta', 'purchase': 'Compra', 'transfer': 'Traslado',
         'adjustment': 'Ajuste / conteo', 'return': 'Devolución'}


def parameters(query):
    today = timezone.localdate()
    try:
        start = date.fromisoformat(query.get('start') or str(today.replace(day=1)))
        end = date.fromisoformat(query.get('end') or str(today))
        page = int(query.get('page', 1))
        product = int(query.get('product', 0))
        warehouse = int(query.get('warehouse', 0))
    except (ValueError, TypeError):
        raise ValidationError('Selecciona un producto, un almacén y fechas válidas.')
    if not product or not warehouse or page < 1 or end < start or (end-start).days > 366:
        raise ValidationError('Elige producto y almacén. El período debe tener como máximo 366 días.')
    return product, warehouse, start, end, page


def movement_data(m):
    return {'id': m.id, 'date': m.created_at, 'document': m.document.number,
            'document_id': m.document_id, 'kind': m.document.kind,
            'reference': m.document.reference, 'note': m.document.note,
            'actor': m.document.created_by.first_name or m.document.created_by.username,
            'incoming': max(m.delta, ZERO), 'outgoing': max(-m.delta, ZERO),
            'balance': m.balance, 'average_cost': m.cost}


@transaction.atomic
def ledger(business, query):
    Business.objects.select_for_update().get(pk=business.pk)
    pid, wid, start, end, page = parameters(query)
    product = Product.objects.get(id=pid, business=business)
    warehouse = Warehouse.objects.get(id=wid, business=business)
    begin = timezone.make_aware(datetime.combine(start, time.min))
    until = timezone.make_aware(datetime.combine(end+timedelta(days=1), time.min))
    base = StockMovement.objects.filter(business=business, product=product, warehouse=warehouse)
    # Freeze the query at a movement ID so concurrent sales cannot change a report halfway through.
    cutoff = base.aggregate(value=Max('id'))['value'] or 0
    base = base.filter(id__lte=cutoff)
    previous = base.filter(created_at__lt=begin).order_by('-created_at', '-id').first()
    period = base.filter(created_at__gte=begin, created_at__lt=until)
    first = base.order_by('created_at', 'id').first()
    # Handles imported opening stock that predates the first recorded movement.
    initial = first.balance-first.delta if first else (
        Stock.objects.filter(product=product, warehouse=warehouse).values_list('quantity', flat=True).first() or ZERO)
    opening = previous.balance if previous else initial
    totals = period.aggregate(incoming=Sum('delta', filter=Q(delta__gt=0)), outgoing=Sum('delta', filter=Q(delta__lt=0)))
    incoming, outgoing = totals['incoming'] or ZERO, -(totals['outgoing'] or ZERO)
    ordered = period.select_related('document__created_by').order_by('created_at', 'id')
    total_rows = ordered.count()
    pages = max(1, (total_rows+PAGE_SIZE-1)//PAGE_SIZE)
    if page > pages:raise ValidationError('Esa página ya no está disponible. Vuelve a la primera.')
    result = {'product': {'id': product.id, 'name': product.name, 'sku': product.sku, 'unit': product.unit},
              'warehouse': {'id': warehouse.id, 'name': warehouse.name},
              'start': start, 'end': end, 'opening': opening, 'incoming': incoming,
              'outgoing': outgoing, 'closing': opening+incoming-outgoing,
              'page': page, 'pages': pages, 'total_rows': total_rows,
              'rows': [movement_data(m) for m in ordered[(page-1)*PAGE_SIZE:page*PAGE_SIZE]]}
    return result, ordered


def csv_response(result, rows=None, demo=False):
    stream = io.StringIO();stream.write('\ufeff');writer = csv.writer(stream)
    def write(values):
        writer.writerow(["'"+str(v) if isinstance(v, str) and v.lstrip().startswith(('=', '+', '-', '@')) else v for v in values])
    write(['Kardex Nexo' + (' · DEMOSTRACIÓN · DATOS FICTICIOS' if demo else '')])
    write(['Producto', result['product']['name'], 'Código', result['product']['sku'], 'Unidad', result['product']['unit']])
    write(['Almacén', result['warehouse']['name'], 'Desde', result['start'], 'Hasta', result['end']])
    write(['Saldo inicial', result['opening'], 'Entradas', result['incoming'], 'Salidas', result['outgoing'], 'Saldo final', result['closing']])
    write(['Fecha', 'Documento', 'Operación', 'Referencia', 'Motivo', 'Persona', 'Entradas', 'Salidas', 'Saldo', 'Costo promedio registrado'])
    iterable = (movement_data(m) for m in rows.iterator(chunk_size=1000)) if rows is not None else result['all_rows']
    for row in iterable:
        write([row['date'], row['document'], KINDS.get(row['kind'], row['kind']), row['reference'], row['note'], row['actor'], row['incoming'], row['outgoing'], row['balance'], row.get('average_cost', '')])
    response = HttpResponse(stream.getvalue(), content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="nexo-kardex.csv"'
    response['Cache-Control'] = 'no-store'
    return response

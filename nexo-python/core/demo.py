"""Public interactive demo. All mutations touch a disposable JSON sandbox only.

There are deliberately no Business, User, Membership or production service writes
here. A separate HttpOnly bearer cookie identifies each visitor. PostgreSQL row
locks serialize their actions and exceptions roll the complete action back.
"""
import base64
import copy
import csv
import hashlib
import io
import json
import secrets
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from functools import wraps
from types import SimpleNamespace

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from .models import DemoSandbox
from .services import CURRENCIES, UNITS

COOKIE = "nexo_demo"
MAX_BYTES = 512_000
MAX_ACTIONS = 100
ZERO = Decimal("0")


def number(value, places="0.01", negative=False, maximum="999999"):
    try:
        n = Decimal(str(value))
        if not n.is_finite() or abs(n) > Decimal(maximum) or (n < 0 and not negative):
            raise ValueError()
        return n.quantize(Decimal(places), rounding=ROUND_HALF_UP)
    except (ValueError, InvalidOperation, TypeError):
        raise ValidationError("Revisa las cantidades e importes.")


def text(value, limit=120, required=False):
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise ValidationError("Revisa los campos obligatorios y su longitud.")
    return value.strip()


def find(items, identifier):
    for item in items:
        if item["id"] == int(identifier):
            return item
    raise ValidationError("Registro no encontrado en tu demostración.")


def next_id(items):
    return max((x["id"] for x in items), default=0) + 1


def timestamp():
    return timezone.localtime().isoformat()


def reply(data, status=200):
    response = JsonResponse(data, status=status)
    response["Cache-Control"] = "no-store"
    return response


def token_hash(request):
    token = request.COOKIES.get(COOKIE, "")
    return hashlib.sha256(token.encode()).hexdigest() if len(token) == 43 else ""


def admin(s):
    if s["role"] != "admin":
        raise PermissionDenied("Esta operación requiere la vista de administrador. Cámbiala en la barra de demostración.")


def actor(s):
    return 1 if s["role"] == "admin" else 2


def audit(s, action, target):
    s["audit"].insert(0, {"date": timestamp(), "actor": "invitado" if actor(s) == 1 else "empleado_demo",
                           "action": action, "target": str(target), "detail": {}})
    del s["audit"][150:]


def stock(p, warehouse):
    return next((x for x in p["stocks"] if x["warehouse"] == warehouse["id"]), None)


def change_stock(p, warehouse, delta):
    row = stock(p, warehouse)
    quantity = Decimal(row["quantity"]) if row else ZERO
    value = quantity + delta
    if value < 0:
        raise ValidationError("Existencias insuficientes de " + p["name"] + " en " + warehouse["name"] + ".")
    if value > Decimal("999999"):
        raise ValidationError("Se superó el límite de existencias de la demostración.")
    if row is None:
        row = {"warehouse": warehouse["id"], "name": warehouse["name"], "quantity": "0"}
        p["stocks"].append(row)
    row["quantity"] = str(value)
    p["stock"] = str(sum((Decimal(x["quantity"]) for x in p["stocks"]), ZERO))


def refresh_invoice(i, documents):
    document = find(documents, i["document"])
    paid = sum((Decimal(p["amount"]) for p in i["payments"] if not p["voided"]), ZERO)
    balance = Decimal(i["total"]) - paid
    status = "credit" if i["kind"] == "credit" else "credited" if document["returned"] else "paid" if balance == 0 else "overdue" if i["due_date"] < str(timezone.localdate()) else "partial" if paid else "pending"
    i.update(paid=str(paid), balance="0" if status in ("credit", "credited") else str(balance), status=status)


def post_document(s, data):
    kind = data.get("kind")
    if kind not in ("sale", "purchase", "adjustment", "transfer"):
        raise ValidationError("Operación no válida.")
    if kind != "sale":
        admin(s)
    warehouse = find(s["warehouses"], data.get("warehouse"))
    destination = find(s["warehouses"], data.get("destination")) if kind == "transfer" else None
    if not warehouse["active"] or (destination and (destination["id"] == warehouse["id"] or not destination["active"])):
        raise ValidationError("Selecciona almacenes activos y diferentes.")
    note = text(data.get("note", ""), 500, kind in ("adjustment", "transfer"))
    reference = text(data.get("reference", ""), 120)
    contact = find(s["contacts"], data["contact"]) if data.get("contact") else None
    if contact and contact["kind"] != ("supplier" if kind == "purchase" else "customer"):
        raise ValidationError("Selecciona un contacto del tipo correcto.")
    due = date.fromisoformat(data.get("due_date") or str(timezone.localdate()))
    if kind == "sale" and due < timezone.localdate():
        raise ValidationError("La fecha de vencimiento no puede ser anterior a hoy.")
    raw_lines = data.get("lines")
    if not isinstance(raw_lines, list) or not 1 <= len(raw_lines) <= 40:
        raise ValidationError("Agrega entre 1 y 40 productos.")
    lines, seen = [], set()
    for raw in raw_lines:
        p = find(s["products"], raw.get("product"))
        if not p["active"] or p["id"] in seen:
            raise ValidationError("Hay un producto archivado o repetido.")
        seen.add(p["id"])
        q = number(raw.get("quantity"), "0.001", negative=kind == "adjustment")
        if q == 0:
            raise ValidationError("La cantidad debe ser distinta de cero.")
        if kind == "sale" and p["expiry"] and p["expiry"] < str(timezone.localdate()):
            raise ValidationError("No se puede vender un producto vencido.")
        cost = Decimal(p["cost"])
        if 'counted' in raw:
            from .services import decimal as checked_decimal, QTY
            if kind != 'adjustment':
                raise ValidationError('El conteo solo puede registrar un ajuste.')
            expected, counted = checked_decimal(raw.get('expected'), QTY), checked_decimal(raw['counted'], QTY)
            current = stock(p, warehouse)
            quantity = Decimal(current['quantity']) if current else ZERO
            latest = demo_last_movement(s, p['id'], warehouse['id'])
            if quantity != expected or raw.get('last_movement') != latest:
                raise ValidationError('Las existencias cambiaron mientras contabas. Actualiza el conteo y revisa de nuevo antes de guardar.')
            if q != counted-expected:
                raise ValidationError('La diferencia del conteo no coincide. Revisa el cambio.')
        price = number(raw.get("price", p["price"])) if kind in ("sale", "purchase") else ZERO
        if kind == "sale" and s["role"] == "employee" and price != Decimal(p["price"]):
            raise PermissionDenied("El empleado no puede modificar el precio de venta.")
        rate = Decimal(s["business"]["tax_rate"]) if kind in ("sale", "purchase") else ZERO
        subtotal = (q * price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        tax = (subtotal * rate / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if kind == "purchase":
            before = Decimal(p["stock"])
            p["cost"] = str(((before * cost + q * price) / (before + q)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))
        change_stock(p, warehouse, -q if kind in ("sale", "transfer") else q)
        if destination:
            change_stock(p, destination, q)
        p["version"] += 1
        lines.append({"product": p["id"], "name": p["name"], "sku": p["sku"], "unit": p["unit"],
                      "quantity": str(q), "unit_price": str(price), "unit_cost": str(cost), "tax_rate": str(rate),
                      "subtotal": str(subtotal), "tax": str(tax), "total": str(subtotal + tax), "average_cost": p['cost']})
    identifier = next_id(s["documents"])
    document = {"id": identifier, "number": f"DEMO-{identifier:05d}", "kind": kind, "date": timestamp(),
                "contact": contact["name"] if contact else "", "warehouse": warehouse["name"], "warehouse_id": warehouse["id"],
                "destination": destination["name"] if destination else "", "destination_id": destination['id'] if destination else None, "creator": "Invitado" if actor(s) == 1 else "Empleado demo",
                "created_by": actor(s), "lines": lines, "reference": reference, "note": note, "returned": False, "invoice_id": None}
    for field in ("subtotal", "tax", "total"):
        document[field] = str(sum((Decimal(l[field]) for l in lines), ZERO))
    s["documents"].insert(0, document)
    if kind == "sale":
        invoice_id = next_id(s["invoices"])
        document["invoice_id"] = invoice_id
        inv = {"id": invoice_id, "number": f"DEMO-F-{invoice_id:05d}", "kind": "invoice", "date": document["date"],
               "due_date": str(due), "customer": copy.deepcopy(contact or {"name": "Consumidor final", "address": "", "tax_id": ""}),
               "issuer": copy.deepcopy(s["business"]), "currency": s["business"]["currency"], "document": identifier,
               "created_by": actor(s), "payments": [], **{k: document[k] for k in ("subtotal", "tax", "total")}}
        refresh_invoice(inv, s["documents"])
        s["invoices"].insert(0, inv)
    audit(s, "document." + kind, document["number"])
    return {"ok": True, "created": True, "document": identifier, "invoice": document["invoice_id"]}


def seed():
    s = {"role": "admin", "actions": 0, "keys": {}, "photos": {}, "history_limit": 250,
         "business": {"id": 1, "name": "Mercado Central · Demo", "sector": "Tienda / supermercado", "currency": "USD",
                      "tax_rate": "0", "tax_id": "DEMO-000", "address": "Avenida del Mercado 120 · Dirección ficticia", "email": "demo@example.com", "phone": ""},
         "warehouses": [{"id": 1, "name": "Tienda principal", "location": "Área de ventas", "active": True},
                        {"id": 2, "name": "Bodega central", "location": "Almacén de reserva", "active": True}],
         "contacts": [{"id": 1, "name": "Distribuidora Horizonte · Ejemplo", "kind": "supplier", "email": "proveedor@example.com", "phone": "", "tax_id": "DEMO-01", "address": "Dirección de ejemplo", "notes": "Proveedor ficticio"},
                      {"id": 2, "name": "Cafetería La Esquina · Ejemplo", "kind": "customer", "email": "cliente@example.com", "phone": "", "tax_id": "DEMO-02", "address": "Dirección de ejemplo", "notes": "Cliente ficticio"}],
         "users": [{"id": 1, "user_id": 1, "username": "invitado", "name": "Invitado", "role": "admin", "active": True},
                   {"id": 2, "user_id": 2, "username": "empleado_demo", "name": "Empleado demo", "role": "employee", "active": True}],
         "products": [], "documents": [], "invoices": [], "audit": []}
    products = [
        ("Café de altura 250 g", "CAFE-250", "Café y bebidas", "4.20", "6.50", 48, 10),
        ("Arroz premium 1 kg", "ARROZ-1K", "Despensa", "1.10", "2.25", 75, 15),
        ("Aceite de oliva 500 ml", "ACEITE-500", "Despensa", "5.30", "8.90", 7, 10),
        ("Leche entera 1 L", "LECHE-1L", "Lácteos", "1.30", "2.10", 40, 12),
        ("Galletas de avena", "GALLETAS", "Snacks", "1.60", "2.95", 0, 8),
        ("Jabón de manos", "JABON", "Cuidado personal", "2.25", "3.75", 16, 6),
        ("Agua mineral 600 ml", "AGUA-600", "Café y bebidas", "0.45", "1.20", 90, 20),
        ("Papel de cocina", "PAPEL", "Hogar", "1.75", "2.80", 5, 8),
    ]
    for idx, (name, sku, category, cost, price, quantity, minimum) in enumerate(products, 1):
        s["products"].append({"id": idx, "name": name, "sku": sku, "category": category, "unit": "unidad",
                              "cost": cost, "price": price, "stock": "0", "minimum": str(minimum), "stocks": [],
                              "location": f"Pasillo {(idx + 1) // 2} · Estante {idx}", "expiry": None,
                              "active": True, "version": 1, "has_photo": False})
        if quantity:
            post_document(s, {"kind": "purchase", "warehouse": 1, "contact": 1, "reference": "Inventario de ejemplo",
                              "lines": [{"product": idx, "quantity": quantity, "price": cost}]})
            s['documents'][0]['date'] = (timezone.localtime()-timedelta(days=8)).isoformat()
    # Several dates make the real dashboard, receivables and charts useful immediately.
    for days, product, quantity in [(6, 1, 2), (5, 2, 5), (4, 7, 12), (3, 4, 4), (2, 1, 3), (1, 2, 7), (0, 1, 4)]:
        post_document(s, {"kind": "sale", "warehouse": 1, "contact": 2, "lines": [{"product": product, "quantity": quantity}]})
        when = timezone.localtime() - timedelta(days=days)
        s["documents"][0]["date"] = s["invoices"][0]["date"] = when.isoformat()
        if days > 2:
            s["invoices"][0]["payments"] = [{"id": days, "amount": s["invoices"][0]["total"], "method": "cash", "reference": "Pago de ejemplo", "date": when.isoformat(), "voided": False, "void_reason": ""}]
        elif days == 1:
            s["invoices"][0]["payments"] = [{"id": 1, "amount": "5.00", "method": "card", "reference": "Pago parcial de ejemplo", "date": when.isoformat(), "voided": False, "void_reason": ""}]
        refresh_invoice(s["invoices"][0], s["documents"])
    post_document(s, {"kind": "transfer", "warehouse": 1, "destination": 2, "note": "Reserva de ejemplo", "lines": [{"product": 7, "quantity": 10}]})
    s["audit"].insert(0, {"date": timestamp(), "actor": "invitado", "action": "demo.started", "target": "Datos ficticios de ejemplo", "detail": {}})
    return s


def visible(s):
    d = copy.deepcopy(s)
    for key in ("keys", "photos", "actions"):
        d.pop(key, None)
    for inv in d["invoices"]:
        refresh_invoice(inv, d["documents"])
    if s["role"] == "employee":
        d.pop("audit", None)
        d.pop("users", None)
        d["contacts"] = [c for c in d["contacts"] if c["kind"] == "customer"]
        d["documents"] = [x for x in d["documents"] if x["created_by"] == 2 and x["kind"] == "sale"]
        d["invoices"] = [x for x in d["invoices"] if x["created_by"] == 2]
        for p in d["products"]:
            p.pop("cost", None)
        for doc in d["documents"]:
            for line in doc["lines"]:
                line.pop("unit_cost", None)
                line.pop("average_cost", None)
    return d


def report_data(s, query):
    today = timezone.localdate()
    start = date.fromisoformat(query.get("start") or str(today - timedelta(days=30)))
    end = date.fromisoformat(query.get("end") or str(today))
    if end < start or (end - start).days > 366:
        raise ValidationError("Selecciona un período de hasta 366 días.")
    docs = [d for d in s["documents"] if str(start) <= d["date"][:10] <= str(end)]
    if s["role"] == "employee":
        docs = [d for d in docs if d["created_by"] == 2 and d["kind"] == "sale"]
    daily, ranking, margin, categories = {}, {}, ZERO, {}
    total = lambda kind: sum((Decimal(d["subtotal"]) for d in docs if d["kind"] == kind), ZERO)
    for d in docs:
        if d["kind"] not in ("sale", "return"):
            continue
        sign = -1 if d["kind"] == "return" else 1
        day = d["date"][:10]
        daily[day] = daily.get(day, ZERO) + sign * Decimal(d["subtotal"])
        for line in d["lines"]:
            q, revenue = sign * Decimal(line["quantity"]), sign * Decimal(line["subtotal"])
            r = ranking.setdefault(line["product"], {"name": line["name"], "unit": line["unit"], "quantity": ZERO, "revenue": ZERO})
            r["quantity"] += q
            r["revenue"] += revenue
            margin += revenue - q * Decimal(line["unit_cost"])
    result = {"start": start, "end": end, "sales": total("sale") - total("return"), "sale_count": sum(d["kind"] == "sale" for d in docs),
              "daily": [{"date": k, "value": v} for k, v in sorted(daily.items())], "ranking": sorted(ranking.values(), key=lambda x: -x["quantity"])[:8]}
    if s["role"] == "admin":
        for p in s["products"]:
            if p["active"]:
                categories[p["category"]] = categories.get(p["category"], ZERO) + Decimal(p["stock"]) * Decimal(p["cost"])
        result.update(purchases=total("purchase"), returns=total("return"), margin=margin, inventory=sum(categories.values(), ZERO),
                      receivable=sum((Decimal(i["balance"]) for i in visible(s)["invoices"]), ZERO),
                      categories=[{"name": k, "value": v} for k, v in sorted(categories.items(), key=lambda x: -x[1])])
    return result


def perform(s, operation, data):
    if not isinstance(data, dict):
        raise ValidationError("Datos no válidos.")
    if operation == "document":
        return post_document(s, data)
    if operation == "payment":
        inv = find(s["invoices"], data.get("invoice"))
        if s["role"] == "employee" and inv["created_by"] != 2:
            raise PermissionDenied("Solo puedes cobrar tus propias ventas.")
        refresh_invoice(inv, s["documents"])
        amount = number(data.get("amount"))
        if amount <= 0 or amount > Decimal(inv["balance"]):
            raise ValidationError("El importe debe ser mayor que cero y no superar el saldo pendiente.")
        if data.get("method") not in ("cash", "card", "transfer"):
            raise ValidationError("Método de pago no válido.")
        identifier = next_id([p for i in s["invoices"] for p in i["payments"]])
        inv["payments"].append({"id": identifier, "amount": str(amount), "method": data["method"], "reference": text(data.get("reference", "")), "date": timestamp(), "voided": False, "void_reason": ""})
        refresh_invoice(inv, s["documents"])
        audit(s, "payment.created", inv["number"])
        return {"ok": True, "created": True, "payment": identifier}
    admin(s)
    if operation == "void_payment":
        payment = find([p for i in s["invoices"] for p in i["payments"]], data.get("id"))
        if payment["voided"]:
            raise ValidationError("El cobro ya fue anulado.")
        payment.update(voided=True, void_reason=text(data.get("reason"), 500, True))
    elif operation == "return":
        original = find(s["documents"], data.get("document"))
        if original["kind"] != "sale" or original["returned"]:
            raise ValidationError("Solo puedes devolver una venta sin devolución anterior.")
        inv = find(s["invoices"], original["invoice_id"])
        if any(not p["voided"] for p in inv["payments"]):
            raise ValidationError("Anula o reembolsa los cobros antes de devolver esta venta.")
        note = text(data.get("note") or data.get("reason", ""), 500, True)
        for line in original["lines"]:
            p = find(s["products"], line["product"])
            before, q = Decimal(p["stock"]), Decimal(line["quantity"])
            p["cost"] = str(((before * Decimal(p["cost"]) + q * Decimal(line["unit_cost"])) / (before + q)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))
            change_stock(p, find(s["warehouses"], original["warehouse_id"]), q)
            p["version"] += 1
        doc = copy.deepcopy(original)
        for line in doc['lines']:
            line['average_cost'] = find(s['products'], line['product'])['cost']
        doc.update(id=next_id(s["documents"]), kind="return", date=timestamp(), note=note, reference=original["number"], returned=False, original=original["id"], created_by=1, creator="Invitado")
        doc["number"] = f"DEMO-{doc['id']:05d}"
        credit = copy.deepcopy(inv)
        credit.update(id=next_id(s["invoices"]), kind="credit", document=doc["id"], date=doc["date"], payments=[], due_date=str(timezone.localdate()), created_by=1)
        credit["number"] = f"DEMO-NC-{credit['id']:05d}"
        doc["invoice_id"] = credit["id"]
        original["returned"] = True
        s["documents"].insert(0, doc)
        s["invoices"].insert(0, credit)
        audit(s, "document.return", doc["number"])
        return {"ok": True, "created": True, "document": doc["id"], "invoice": credit["id"]}
    elif operation == "product":
        new = not data.get("id")
        if new and len(s["products"]) >= 40:
            raise ValidationError("La demo admite 40 productos. Puedes reiniciarla para continuar.")
        p = {"id": next_id(s["products"]), "stock": "0", "stocks": [], "active": True, "has_photo": False, "version": 1} if new else find(s["products"], data["id"])
        if not new and data.get("version") != p["version"]:
            raise ValidationError("El producto cambió. Actualiza antes de guardar.")
        if not new and data.get("unit") != p["unit"] and any(l["product"] == p["id"] for d in s["documents"] for l in d["lines"]):
            raise ValidationError("No puedes cambiar la unidad después de registrar movimientos.")
        for field, limit in [("name", 120), ("sku", 80), ("category", 80), ("unit", 20)]:
            p[field] = text(data.get(field), limit, True)
        p["sku"] = p["sku"].upper()
        if any(x["id"] != p["id"] and x["sku"] == p["sku"] for x in s["products"]):
            raise ValidationError("Ya existe un producto con ese código.")
        if p["unit"] not in UNITS:
            raise ValidationError("Unidad no válida.")
        p.update(price=str(number(data.get("price"))), minimum=str(number(data.get("minimum"), "0.001")), location=text(data.get("location", ""), 200), expiry=str(date.fromisoformat(data["expiry"])) if data.get("expiry") else None)
        if new:
            p["cost"] = str(number(data.get("cost"), "0.0001"))
            s["products"].append(p)
            initial = number(data.get("initial") or "0", "0.001")
            if initial:
                post_document(s, {"kind": "adjustment", "warehouse": data.get("warehouse"), "note": "Existencias iniciales", "lines": [{"product": p["id"], "quantity": str(initial)}]})
        else:
            p["version"] += 1
    elif operation == "archive":
        p = find(s["products"], data.get("id"))
        if p["active"] and Decimal(p["stock"]) > 0:
            raise ValidationError("Las existencias deben ser cero para archivar.")
        p["active"] = not p["active"]
        p["version"] += 1
    elif operation in ("contact", "warehouse"):
        collection = s["contacts" if operation == "contact" else "warehouses"]
        if not data.get("id") and len(collection) >= 20:
            raise ValidationError("Alcanzaste el límite de 20 registros de este módulo. Reinicia la demo.")
        item = find(collection, data["id"]) if data.get("id") else {"id": next_id(collection)}
        item["name"] = text(data.get("name"), 100, True)
        if operation == "contact":
            if data.get("kind") not in ("customer", "supplier"):
                raise ValidationError("Tipo de contacto no válido.")
            item["kind"] = data["kind"]
            for field, limit in [("email", 254), ("phone", 60), ("tax_id", 80), ("address", 300), ("notes", 500)]:
                item[field] = text(data.get(field, ""), limit)
        else:
            item.update(location=text(data.get("location", ""), 200), active=True)
            for p in s["products"]:
                for row in p["stocks"]:
                    if row["warehouse"] == item["id"]:
                        row["name"] = item["name"]
        if not data.get("id"):
            collection.append(item)
    elif operation == "settings":
        if data.get("currency") != s["business"]["currency"]:
            raise ValidationError("La moneda queda fija tras el primer movimiento.")
        for field, limit in [("name", 120), ("sector", 80), ("tax_id", 80), ("address", 300), ("email", 254), ("phone", 60)]:
            s["business"][field] = text(data.get(field, ""), limit, field in ("name", "sector"))
        s["business"]["tax_rate"] = str(number(data.get("tax_rate"), maximum="100"))
    elif operation == "user_create":
        if len(s["users"]) >= 12:
            raise ValidationError("La demo admite hasta 12 integrantes ficticios.")
        username = text(data.get("username"), 150, True)
        if any(u["username"] == username for u in s["users"]):
            raise ValidationError("Ese usuario ya está en tu equipo de ejemplo.")
        if data.get("role") not in ("admin", "employee"):
            raise ValidationError("Rol no válido.")
        identifier = next_id(s["users"])
        # Never store passwords or create a Django authentication account.
        s["users"].append({"id": identifier, "user_id": identifier, "username": username, "name": text(data.get("name"), 150, True), "role": data["role"], "active": True})
    elif operation == "user_update":
        u = find(s["users"], data.get("id"))
        if u["id"] in (1, 2):
            raise ValidationError("Los dos perfiles de visita se conservan. Crea un integrante ficticio para probar los permisos.")
        if data.get("role") not in ("admin", "employee") or not isinstance(data.get("active"), bool):
            raise ValidationError("Permisos no válidos.")
        u.update(role=data["role"], active=data["active"])
    else:
        raise ValidationError("Acción no disponible en la demostración.")
    audit(s, operation + ".saved", data.get("name") or data.get("id") or "Demostración")
    return {"ok": True}


def sandbox_api(fn):
    @wraps(fn)
    def wrapped(request, *args, **kwargs):
        if request.method not in ("GET", "POST"):
            return reply({"error": "Método no permitido."}, 405)
        try:
            with transaction.atomic():
                box = DemoSandbox.objects.select_for_update().filter(token_hash=token_hash(request), expires_at__gt=timezone.now()).first()
                if box is None:
                    return reply({"error": "Tu demostración terminó. Vuelve a entrar como invitado."}, 401)
                if kwargs.get("business_id", 1) != 1:
                    return reply({"error": "Ese negocio no pertenece a tu demostración."}, 404)
                result = fn(request, box, *args, **kwargs)
                if request.method == "POST" and result.status_code < 400:
                    if len(json.dumps(box.data).encode()) > MAX_BYTES:
                        raise ValidationError("La prueba alcanzó su capacidad. Reiníciala para continuar.")
                    box.save(update_fields=["data"])
                result["Cache-Control"] = "no-store"
                return result
        except PermissionDenied as e:
            return reply({"error": str(e)}, 403)
        except ValidationError as e:
            return reply({"error": " ".join(e.messages)}, 400)
        except (ValueError, TypeError, KeyError, AttributeError, InvalidOperation):
            return reply({"error": "Revisa los datos de la solicitud."}, 400)
        except DatabaseError:
            return reply({"error": "No se pudo guardar. Vuelve a intentar en un momento."}, 503)
    return wrapped


def payload(request):
    if request.method != "POST":
        raise PermissionDenied("Esta acción requiere confirmación.")
    if len(request.body) > 32_000:
        raise ValidationError("La solicitud es demasiado grande.")
    data = json.loads(request.body)
    if not isinstance(data, dict):
        raise ValidationError("Solicitud no válida.")
    return data


@ensure_csrf_cookie
def entry(request):
    error = ""
    if request.method == "POST":
        try:
            with transaction.atomic():
                # Serializes admission and bounds total storage even under parallel requests.
                from django.db import connection
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_advisory_xact_lock(734209118)")
                DemoSandbox.objects.filter(expires_at__lte=timezone.now()).delete()
                existing = DemoSandbox.objects.filter(token_hash=token_hash(request)).exists()
                if existing:
                    return redirect("/demo/app/")
                if DemoSandbox.objects.count() >= 200:
                    error = "La demostración está muy concurrida. Intenta de nuevo más tarde."
                else:
                    token = secrets.token_urlsafe(32)
                    DemoSandbox.objects.create(token_hash=hashlib.sha256(token.encode()).hexdigest(), data=seed(), expires_at=timezone.now() + timedelta(hours=24))
                    result = redirect("/demo/app/")
                    result.set_cookie(COOKIE, token, max_age=86400, httponly=True, secure=settings.SESSION_COOKIE_SECURE, samesite="Lax", path="/demo/")
                    result["Cache-Control"] = "no-store"
                    return result
        except DatabaseError:
            error = "El servicio está iniciando. Vuelve a intentar en un momento."
    result = render(request, "core/demo_login.html", {"error": error})
    result["Cache-Control"] = "no-store"
    return result


@ensure_csrf_cookie
def app(request):
    if not DemoSandbox.objects.filter(token_hash=token_hash(request), expires_at__gt=timezone.now()).exists():
        return redirect("/demo/")
    result = render(request, "core/app.html", {"demo": True, "password_required": False})
    result["Cache-Control"] = "no-store"
    return result


@require_POST
def leave(request):
    DemoSandbox.objects.filter(token_hash=token_hash(request)).delete()
    result = redirect("/demo/")
    result.delete_cookie(COOKIE, path="/demo/")
    return result


@sandbox_api
def me(request, box):
    s = box.data
    return reply({"user": {"name": "Invitado" if actor(s) == 1 else "Empleado demo", "username": "invitado"},
                  "businesses": [{"id": 1, "name": s["business"]["name"], "role": s["role"]}]})


@sandbox_api
def state_view(request, box, business_id):
    return reply(visible(box.data))


@sandbox_api
def report(request, box, business_id):
    return reply(report_data(box.data, request.GET))


def warehouse_delta(s, document, line, warehouse_id):
    q = Decimal(line['quantity'])
    if document['warehouse_id'] == warehouse_id:
        return -q if document['kind'] in ('sale', 'transfer') else q
    destination_id = document.get('destination_id')
    if not destination_id and document.get('destination'):
        destination_id = next((w['id'] for w in s['warehouses'] if w['name'] == document['destination']), None)
    return q if document['kind'] == 'transfer' and destination_id == warehouse_id else ZERO


def demo_last_movement(s, product_id, warehouse_id):
    return max((d['id'] for d in s['documents'] for l in d['lines']
                if l['product'] == product_id and warehouse_delta(s, d, l, warehouse_id)), default=0)


@sandbox_api
def stock_snapshot(request, box, business_id):
    if request.method != 'GET':return reply({'error': 'Método no permitido.'}, 405)
    s = box.data;admin(s)
    p = find(s['products'], request.GET.get('product'));w = find(s['warehouses'], request.GET.get('warehouse'))
    if not p['active'] or not w['active']:raise ValidationError('Selecciona un producto y un almacén activos.')
    row = stock(p, w)
    return reply({'product': p['id'], 'warehouse': w['id'], 'quantity': row['quantity'] if row else '0',
                  'last_movement': demo_last_movement(s, p['id'], w['id'])})


@sandbox_api
def kardex(request, box, business_id):
    from .kardex import parameters, PAGE_SIZE, csv_response
    if request.method != 'GET':return reply({'error': 'Método no permitido.'}, 405)
    s = box.data;admin(s)
    pid, wid, start, end, page = parameters(request.GET)
    p = find(s['products'], pid);w = find(s['warehouses'], wid)
    all_rows = []
    # Demo documents retain the movements; no business records are queried.
    for d in s['documents']:
        for line in d['lines']:
            if line['product'] != pid:continue
            delta = warehouse_delta(s, d, line, wid)
            if not delta:continue
            when = d['date']
            # Older disposable demos seeded opening purchases after example sales.
            if d['kind'] == 'purchase' and d['reference'] == 'Inventario de ejemplo':
                earliest = min(x['date'] for x in s['documents'])
                when = (datetime.fromisoformat(earliest)-timedelta(days=1)).isoformat()
            all_rows.append({'id': d['id'], 'date': when, 'document': d['number'], 'document_id': d['id'],
                             'kind': d['kind'], 'reference': d['reference'], 'note': d['note'], 'actor': d['creator'],
                             'incoming': max(delta, ZERO), 'outgoing': max(-delta, ZERO), 'delta': delta,
                             'average_cost': line.get('average_cost')})
    all_rows.sort(key=lambda r: (r['date'], r['id']))
    stock_row = stock(p, w)
    initial = Decimal(stock_row['quantity']) if stock_row else ZERO
    initial -= sum((r['delta'] for r in all_rows), ZERO)
    running = initial;opening = initial;filtered = []
    for row in all_rows:
        running += row.pop('delta');row['balance'] = running
        if row['date'][:10] < str(start):opening = running
        elif row['date'][:10] <= str(end):filtered.append(row)
    incoming = sum((r['incoming'] for r in filtered), ZERO)
    outgoing = sum((r['outgoing'] for r in filtered), ZERO)
    pages = max(1, (len(filtered)+PAGE_SIZE-1)//PAGE_SIZE)
    if page > pages:raise ValidationError('Esa página ya no está disponible.')
    result = {'product': {k: p[k] for k in ('id', 'name', 'sku', 'unit')}, 'warehouse': {'id': w['id'], 'name': w['name']},
              'start': start, 'end': end, 'opening': opening, 'incoming': incoming, 'outgoing': outgoing,
              'closing': opening+incoming-outgoing, 'page': page, 'pages': pages, 'total_rows': len(filtered),
              'rows': filtered[(page-1)*PAGE_SIZE:page*PAGE_SIZE]}
    if request.GET.get('format') == 'csv':
        result['all_rows'] = filtered
        return csv_response(result, demo=True)
    return reply(result)


@sandbox_api
def action(request, box, business_id):
    data = payload(request)
    op, fields = data.get("action"), data.get("data", {})
    if not isinstance(fields, dict):
        raise ValidationError("Datos no válidos.")
    s = box.data
    # Matches production retry behavior for sales, returns and payments.
    key = fields.get("request_key") if op in ("document", "payment", "return") else None
    fingerprint = hashlib.sha256(json.dumps([s["role"], op, fields], sort_keys=True).encode()).hexdigest()
    if op in ("document", "payment", "return"):
        uuid.UUID(key)
        if key in s["keys"]:
            previous = s["keys"][key]
            if previous["hash"] != fingerprint:
                raise ValidationError("Ese identificador ya corresponde a otra operación.")
            return reply({**previous["result"], "created": False})
    if s["actions"] >= MAX_ACTIONS:
        raise ValidationError("Completaste 100 operaciones. Reinicia la demo para seguir probando.")
    result = perform(s, op, fields)
    s["actions"] += 1
    if key:
        s["keys"][key] = {"hash": fingerprint, "result": result}
    return reply(result)


@sandbox_api
def reset(request, box):
    payload(request)
    box.data = seed()
    return reply({"ok": True})


@sandbox_api
def role(request, box):
    value = payload(request).get("role")
    if value not in ("admin", "employee"):
        raise ValidationError("Rol no válido.")
    box.data["role"] = value
    return reply({"ok": True})


@sandbox_api
def photo(request, box, business_id, product_id):
    p = find(box.data["products"], product_id)
    if request.method == "GET":
        value = box.data["photos"].get(str(product_id))
        return HttpResponse(base64.b64decode(value), content_type="image/jpeg") if value else HttpResponse(status=404)
    admin(box.data)
    upload = request.FILES.get("photo")
    if not upload or upload.size > 2 * 1024 * 1024:
        raise ValidationError("Selecciona una imagen de hasta 2 MB.")
    from PIL import Image, ImageOps, UnidentifiedImageError
    try:
        image = Image.open(upload)
        if image.format not in ("PNG", "JPEG", "WEBP") or image.width * image.height > 16_000_000:
            raise ValidationError("Imagen no válida o demasiado grande.")
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((240, 240))
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=75)
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError):
        raise ValidationError("No se pudo leer la imagen.")
    box.data["photos"][str(product_id)] = base64.b64encode(output.getvalue()).decode()
    p.update(has_photo=True, version=p["version"] + 1)
    audit(box.data, "product.photo", p["sku"])
    return reply({"ok": True})


@sandbox_api
def export(request, box, business_id):
    admin(box.data)
    s = visible(box.data)
    kind = request.GET.get("kind", "inventory")
    if kind == "inventory":
        rows = [["Código", "Producto", "Categoría", "Existencias", "Costo", "Precio"]] + [[p[k] for k in ("sku", "name", "category", "stock", "cost", "price")] for p in s["products"]]
    elif kind == "invoices":
        rows = [["Número", "Cliente", "Fecha", "Total", "Cobrado", "Saldo", "Estado"]] + [[i["number"], i["customer"]["name"], i["date"], i["total"], i["paid"], i["balance"], i["status"]] for i in s["invoices"]]
    elif kind == "movements":
        rows = [["Fecha", "Documento", "Operación", "Almacén", "Destino", "Código", "Cantidad"]] + [[d["date"], d["number"], d["kind"], d["warehouse"], d["destination"], l["sku"], l["quantity"]] for d in s["documents"] for l in d["lines"]]
    else:
        raise ValidationError("Exportación no disponible.")
    stream = io.StringIO()
    stream.write("\ufeff")
    writer = csv.writer(stream)
    writer.writerow(["DEMOSTRACIÓN NEXO · DATOS FICTICIOS"])
    for row in rows:
        writer.writerow([("'" + str(v)) if str(v).lstrip().startswith(("=", "+", "-", "@")) else str(v) for v in row])
    result = HttpResponse(stream.getvalue(), content_type="text/csv; charset=utf-8")
    result["Content-Disposition"] = f'attachment; filename="nexo-demo-{kind}.csv"'
    return result


@sandbox_api
def invoice(request, box, business_id, invoice_id):
    from .pdf import invoice_pdf
    s = visible(box.data)
    inv = copy.deepcopy(find(s["invoices"], invoice_id))
    d = copy.deepcopy(find(s["documents"], inv["document"]))
    lines = []
    for line in d["lines"]:
        for key in ("quantity", "unit_price", "subtotal", "tax", "total"):
            line[key] = Decimal(line[key])
        lines.append(SimpleNamespace(**line))
    for key in ("subtotal", "tax", "total"):
        d[key] = Decimal(d[key])
    d["lines"] = SimpleNamespace(all=lambda: lines)
    if inv["kind"] == "credit":
        original = find(box.data["documents"], d["original"])
        original_invoice = find(box.data["invoices"], original["invoice_id"])
        d["original"] = SimpleNamespace(invoice=SimpleNamespace(number=original_invoice["number"]))
    inv.update(document=SimpleNamespace(**d), created_at=timezone.datetime.fromisoformat(inv["date"]), due_date=date.fromisoformat(inv["due_date"]))
    result = HttpResponse(invoice_pdf(SimpleNamespace(**inv), demo=True, paid_override=Decimal(inv["paid"]), status_override=inv["status"]), content_type="application/pdf")
    result["Content-Disposition"] = f'inline; filename="{inv["number"]}.pdf"'
    return result

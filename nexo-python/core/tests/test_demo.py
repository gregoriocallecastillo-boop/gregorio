import copy
import io
import json
import uuid
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipIf
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.db import connections
from django.utils import timezone

from core.demo import COOKIE, seed
from core.models import Business, DemoSandbox, Document, Product


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["testserver"], STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class GuestDemoTests(TestCase):
    def setUp(self):
        self.visitor = Client()
        self.enter(self.visitor)

    def enter(self, client):
        result = client.post("/demo/")
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.url, "/demo/app/")
        return result

    def post(self, operation, data, client=None):
        data = copy.deepcopy(data)
        if operation in ("document", "payment", "return"):
            data.setdefault("request_key", str(uuid.uuid4()))
        return (client or self.visitor).post("/demo/api/b/1/action/", json.dumps({"action": operation, "data": data}), content_type="application/json")

    def state(self, client=None):
        response = (client or self.visitor).get("/demo/api/b/1/state/")
        self.assertEqual(response.status_code, 200)
        return response.json()

    def role(self, value):
        return self.visitor.post("/demo/api/role/", json.dumps({"role": value}), content_type="application/json")

    def test_landing_guest_cookie_and_real_api_isolation(self):
        response = Client().get("/demo/")
        self.assertContains(response, "Entrar como invitado")
        self.assertEqual(DemoSandbox.objects.count(), 1)
        cookie = self.visitor.cookies[COOKIE]
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Lax")
        self.assertEqual(cookie["path"], "/demo/")
        self.assertEqual(self.visitor.get("/api/me/").status_code, 401)
        self.assertEqual(self.visitor.get("/api/b/1/state/").status_code, 401)
        self.assertEqual(self.visitor.get("/demo/api/b/999/state/").status_code, 404)
        self.assertEqual(self.visitor.get("/demo/api/b/999/invoices/1/pdf/").status_code, 404)
        self.assertEqual(self.visitor.post("/api/businesses/", {}, content_type="application/json").status_code, 401)
        self.assertFalse(get_user_model().objects.exists())
        self.assertFalse(Business.objects.exists())
        self.assertFalse(Product.objects.exists())
        self.assertFalse(Document.objects.exists())

    def test_visitors_do_not_share_mutations_or_reset(self):
        other = Client()
        self.enter(other)
        before = self.state(other)
        self.assertEqual(self.post("document", {"kind": "sale", "warehouse": 1, "lines": [{"product": 1, "quantity": 1}]}).status_code, 200)
        self.assertNotEqual(self.state()["products"][0]["stock"], before["products"][0]["stock"])
        self.assertEqual(self.state(other), before)
        self.assertEqual(self.visitor.post("/demo/api/reset/", "{}", content_type="application/json").status_code, 200)
        self.assertEqual(self.state()["products"][0]["stock"], before["products"][0]["stock"])
        self.assertEqual(self.state(other), before)

    def test_sale_payment_refund_return_and_downloads(self):
        before = Decimal(self.state()["products"][0]["stock"])
        sale = self.post("document", {"kind": "sale", "warehouse": 1, "contact": 2, "lines": [{"product": 1, "quantity": 2}]}).json()
        self.assertEqual(Decimal(self.state()["products"][0]["stock"]), before - 2)
        invoice = next(i for i in self.state()["invoices"] if i["id"] == sale["invoice"])
        self.assertEqual(Decimal(invoice["total"]), Decimal("13.00"))
        payment = self.post("payment", {"invoice": sale["invoice"], "amount": "5.00", "method": "cash"}).json()
        self.assertEqual(self.state()["invoices"][0]["status"], "partial")
        self.assertEqual(self.post("return", {"document": sale["document"], "note": "Devolución de prueba"}).status_code, 400)
        self.assertEqual(self.post("void_payment", {"id": payment["payment"], "reason": "Reembolso de prueba"}).status_code, 200)
        returned = self.post("return", {"document": sale["document"], "note": "Devolución completa"})
        self.assertEqual(returned.status_code, 200, returned.content)
        self.assertEqual(Decimal(self.state()["products"][0]["stock"]), before)
        for identifier in (sale["invoice"], returned.json()["invoice"]):
            pdf = self.visitor.get(f"/demo/api/b/1/invoices/{identifier}/pdf/")
            self.assertEqual(pdf.status_code, 200, pdf.content[:100])
            self.assertTrue(pdf.content.startswith(b"%PDF"))
            self.assertIn("DEMO", pdf["Content-Disposition"])
        self.assertEqual(self.post("return", {"document": sale["document"], "note": "Duplicada"}).status_code, 400)
        for kind in ("inventory", "movements", "invoices"):
            csv = self.visitor.get("/demo/api/b/1/export/?kind=" + kind)
            self.assertContains(csv, "DATOS FICTICIOS")

    def test_no_overselling_atomic_rollback_and_retry_idempotency(self):
        before = self.state()
        failed = self.post("document", {"kind": "sale", "warehouse": 1, "lines": [{"product": 1, "quantity": 1}, {"product": 5, "quantity": 1}]})
        self.assertEqual(failed.status_code, 400)
        self.assertEqual(self.state(), before)
        data = {"request_key": str(uuid.uuid4()), "kind": "sale", "warehouse": 1, "lines": [{"product": 1, "quantity": 1}]}
        first = self.post("document", data).json()
        second = self.post("document", data).json()
        self.assertFalse(second["created"])
        self.assertEqual(first["document"], second["document"])
        self.assertEqual(len(self.state()["documents"]), len(before["documents"]) + 1)
        data["lines"][0]["quantity"] = 2
        self.assertEqual(self.post("document", data).status_code, 400)

    def test_employee_permissions_are_enforced_on_server(self):
        old_invoice = self.state()["invoices"][0]["id"]
        self.assertEqual(self.role("employee").status_code, 200)
        state = self.state()
        self.assertNotIn("users", state)
        self.assertNotIn("audit", state)
        self.assertNotIn("cost", state["products"][0])
        self.assertFalse(state["invoices"])
        self.assertEqual(self.post("product", {"name": "Prohibido"}).status_code, 403)
        self.assertEqual(self.post("document", {"kind": "purchase"}).status_code, 403)
        self.assertEqual(self.post("document", {"kind": "sale", "warehouse": 1, "lines": [{"product": 1, "quantity": 1, "price": "0.01"}]}).status_code, 403)
        self.assertEqual(self.visitor.get("/demo/api/b/1/export/").status_code, 403)
        self.assertEqual(self.visitor.get(f"/demo/api/b/1/invoices/{old_invoice}/pdf/").status_code, 400)
        self.assertEqual(self.post("payment", {"invoice": old_invoice, "amount": 1, "method": "cash"}).status_code, 403)
        sale = self.post("document", {"kind": "sale", "warehouse": 1, "lines": [{"product": 1, "quantity": 1}]})
        self.assertEqual(sale.status_code, 200, sale.content)
        self.assertEqual(len(self.state()["invoices"]), 1)
        self.assertEqual(self.post("payment", {"invoice": sale.json()["invoice"], "amount": "6.50", "method": "cash"}).status_code, 200)
        self.assertEqual(self.visitor.get(f"/demo/api/b/1/invoices/{sale.json()['invoice']}/pdf/").status_code, 200)
        report = self.visitor.get("/demo/api/b/1/report/").json()
        self.assertEqual(Decimal(report["sales"]), Decimal("6.50"))
        self.assertNotIn("margin", report)

    def test_product_purchase_transfer_adjustment_and_version(self):
        data = {"name": "Martillo de prueba", "sku": "PRUEBA-1", "category": "Ferretería", "unit": "unidad", "price": "20", "cost": "8", "minimum": "2", "initial": "5", "warehouse": 1}
        self.assertEqual(self.post("product", data).status_code, 200)
        p = self.state()["products"][-1]
        pid = p["id"]
        self.assertEqual(self.post("document", {"kind": "purchase", "warehouse": 1, "lines": [{"product": pid, "quantity": 5, "price": 12}]}).status_code, 200)
        self.assertEqual(Decimal(self.state()["products"][-1]["cost"]), 10)
        self.assertEqual(self.post("document", {"kind": "transfer", "warehouse": 1, "destination": 2, "note": "Reserva", "lines": [{"product": pid, "quantity": 3}]}).status_code, 200)
        self.assertEqual(Decimal(self.state()["products"][-1]["stock"]), 10)
        self.assertEqual(self.post("document", {"kind": "adjustment", "warehouse": 2, "note": "Conteo", "lines": [{"product": pid, "quantity": -1}]}).status_code, 200)
        self.assertEqual(Decimal(self.state()["products"][-1]["stock"]), 9)
        self.assertEqual(self.post("product", {**data, "id": pid, "version": p["version"]}).status_code, 400)
        self.assertEqual(self.post("archive", {"id": pid}).status_code, 400)
        self.assertEqual(self.post("product", data).status_code, 400)

    def test_tax_and_invoice_snapshots(self):
        business = self.state()["business"]
        self.assertEqual(self.post("settings", {**business, "name": "Mi demo", "tax_rate": "16"}).status_code, 200)
        sale = self.post("document", {"kind": "sale", "warehouse": 1, "lines": [{"product": 1, "quantity": 2}]}).json()
        invoice = self.state()["invoices"][0]
        self.assertEqual(invoice["id"], sale["invoice"])
        self.assertEqual(Decimal(invoice["total"]), Decimal("15.08"))
        self.post("settings", {**business, "name": "Otro nombre", "tax_rate": "10"})
        self.assertEqual(self.state()["invoices"][0]["issuer"]["name"], "Mi demo")
        self.assertEqual(Decimal(self.state()["invoices"][0]["total"]), Decimal("15.08"))

    def test_contacts_warehouses_team_simulation_and_csv_escaping(self):
        self.assertEqual(self.post("contact", {"name": "Cliente de prueba", "kind": "customer"}).status_code, 200)
        self.assertEqual(self.post("warehouse", {"name": "Nueva bodega"}).status_code, 200)
        data = {"name": "Persona ficticia", "username": "persona_demo", "role": "employee", "password": "never-store-this-password"}
        self.assertEqual(self.post("user_create", data).status_code, 200)
        self.assertFalse(get_user_model().objects.exists())
        self.assertNotIn(data["password"], json.dumps(DemoSandbox.objects.first().data))
        uid = self.state()["users"][-1]["id"]
        self.assertEqual(self.post("user_update", {"id": uid, "role": "admin", "active": False}).status_code, 200)
        self.assertEqual(self.post("user_update", {"id": 1, "role": "employee", "active": False}).status_code, 400)
        p = self.state()["products"][0]
        self.post("product", {**p, "name": "=HYPERLINK(test)"})
        self.assertContains(self.visitor.get("/demo/api/b/1/export/"), "'=HYPERLINK(test)")

    def test_photo_upload_stays_in_sandbox(self):
        from PIL import Image
        stream = io.BytesIO()
        Image.new("RGB", (20, 20), (20, 150, 90)).save(stream, "PNG")
        upload = SimpleUploadedFile("demo.png", stream.getvalue(), content_type="image/png")
        self.assertEqual(self.visitor.post("/demo/api/b/1/products/1/photo/", {"photo": upload}).status_code, 200)
        self.assertTrue(self.state()["products"][0]["has_photo"])
        response = self.visitor.get("/demo/api/b/1/products/1/photo/")
        self.assertEqual(response["Content-Type"], "image/jpeg")
        self.assertFalse(Product.objects.exists())

    def test_csrf_required_for_guest_entry_actions_and_reset(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post("/demo/").status_code, 403)
        client.get("/demo/")
        csrf = client.cookies["csrftoken"].value
        self.assertEqual(client.post("/demo/", HTTP_X_CSRFTOKEN=csrf).status_code, 302)
        self.assertEqual(client.post("/demo/api/reset/", "{}", content_type="application/json").status_code, 403)
        self.assertEqual(client.post("/demo/api/reset/", "{}", content_type="application/json", HTTP_X_CSRFTOKEN=csrf).status_code, 200)

    def test_expiration_bad_token_capacity_and_action_limits(self):
        box = DemoSandbox.objects.first()
        box.data["actions"] = 100
        box.save()
        self.assertEqual(self.post("warehouse", {"name": "Límite"}).status_code, 400)
        self.visitor.post("/demo/api/reset/", "{}", content_type="application/json")
        self.assertEqual(self.post("warehouse", {"name": "Disponible"}).status_code, 200)
        box.refresh_from_db()
        box.expires_at = timezone.now() - timedelta(seconds=1)
        box.save()
        self.assertEqual(self.visitor.get("/demo/api/me/").status_code, 401)
        self.enter(self.visitor)
        self.assertEqual(DemoSandbox.objects.count(), 1)
        self.visitor.cookies[COOKIE] = "x" * 43
        self.assertEqual(self.visitor.get("/demo/api/me/").status_code, 401)

    def test_owner_session_survives_demo_entry_and_exit(self):
        owner = get_user_model().objects.create_user("owner", password="private-owner-test-password")
        owner_client = Client()
        owner_client.force_login(owner)
        session_key = owner_client.session.session_key
        self.enter(owner_client)
        self.assertEqual(owner_client.session.session_key, session_key)
        self.assertEqual(owner_client.post("/demo/logout/").status_code, 302)
        self.assertEqual(owner_client.session["_auth_user_id"], str(owner.pk))
        self.assertEqual(owner_client.get("/demo/api/me/").status_code, 401)

    def test_invalid_amounts_dates_and_methods_do_not_mutate(self):
        before = self.state()
        for value in ("NaN", "Infinity", "-1", "9999999999999", "0"):
            response = self.post("document", {"kind": "sale", "warehouse": 1, "lines": [{"product": 1, "quantity": value}]})
            self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(self.visitor.get("/demo/api/b/1/report/?start=bad").status_code, 400)
        self.assertEqual(self.visitor.get("/demo/api/reset/").status_code, 403)
        self.assertEqual(self.visitor.delete("/demo/api/b/1/state/").status_code, 405)
        self.assertEqual(self.state(), before)


@override_settings(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["testserver"])
class GuestConcurrencyTests(TransactionTestCase):
    @skipIf(os.getenv("NEXO_EMBEDDED_TEST") == "1", "Requires independent native PostgreSQL connections")
    def test_parallel_sales_in_one_browser_preserve_both_changes(self):
        import hashlib
        token = "a" * 43
        key = hashlib.sha256(token.encode()).hexdigest()
        data = seed()
        before = Decimal(data["products"][0]["stock"])
        count = len(data["documents"])
        DemoSandbox.objects.create(token_hash=key, data=data, expires_at=timezone.now() + timedelta(hours=1))
        barrier = Barrier(2)

        def sell():
            try:
                client = Client()
                client.cookies[COOKIE] = token
                barrier.wait(timeout=10)
                return client.post("/demo/api/b/1/action/", json.dumps({"action": "document", "data": {
                    "request_key": str(uuid.uuid4()), "kind": "sale", "warehouse": 1,
                    "lines": [{"product": 1, "quantity": 1}],
                }}), content_type="application/json").status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: sell(), range(2)))
        self.assertEqual(results, [200, 200])
        saved = DemoSandbox.objects.get(pk=key).data
        self.assertEqual(Decimal(saved["products"][0]["stock"]), before - 2)
        self.assertEqual(len(saved["documents"]), count + 2)

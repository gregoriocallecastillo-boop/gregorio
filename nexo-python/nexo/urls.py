from django.urls import path
from core import views as v
from core import demo
demo_routes = [
    ('', demo.entry),
    ('app/', demo.app),
    ('logout/', demo.leave),
    ('api/me/', demo.me),
    ('api/reset/', demo.reset),
    ('api/role/', demo.role),
    ('api/b/<int:business_id>/state/', demo.state_view),
    ('api/b/<int:business_id>/report/', demo.report),
    ('api/b/<int:business_id>/kardex/', demo.kardex),
    ('api/b/<int:business_id>/stock-snapshot/', demo.stock_snapshot),
    ('api/b/<int:business_id>/action/', demo.action),
    ('api/b/<int:business_id>/export/', demo.export),
    ('api/b/<int:business_id>/products/<int:product_id>/photo/', demo.photo),
    ('api/b/<int:business_id>/invoices/<int:invoice_id>/pdf/', demo.invoice),
]
demo_urls = [path(prefix + route, view) for prefix in ("demo/", "demo/ferreteria/") for route, view in demo_routes]

urlpatterns=[path('',v.home),path('login/',v.login_page),path('logout/',v.logout_view),path('health/',v.health),path('api/password/',v.password_change),path('api/me/',v.bootstrap),path('api/businesses/',v.create_business),path('api/b/<int:business_id>/state/',v.state),path('api/b/<int:business_id>/report/',v.report),path('api/b/<int:business_id>/action/',v.action),path('api/b/<int:business_id>/export/',v.export_csv),path('api/b/<int:business_id>/products/<int:product_id>/photo/',v.photo),path('api/b/<int:business_id>/invoices/<int:invoice_id>/pdf/',v.invoice_view)]

urlpatterns += demo_urls
urlpatterns += [path('api/b/<int:business_id>/kardex/',v.kardex),path('api/b/<int:business_id>/stock-snapshot/',v.stock_snapshot)]

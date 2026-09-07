from django.urls import path
from core import views as v
from core import demo
demo_urls = [
    path('demo/', demo.entry),
    path('demo/app/', demo.app),
    path('demo/logout/', demo.leave),
    path('demo/api/me/', demo.me),
    path('demo/api/reset/', demo.reset),
    path('demo/api/role/', demo.role),
    path('demo/api/b/<int:business_id>/state/', demo.state_view),
    path('demo/api/b/<int:business_id>/report/', demo.report),
    path('demo/api/b/<int:business_id>/action/', demo.action),
    path('demo/api/b/<int:business_id>/export/', demo.export),
    path('demo/api/b/<int:business_id>/products/<int:product_id>/photo/', demo.photo),
    path('demo/api/b/<int:business_id>/invoices/<int:invoice_id>/pdf/', demo.invoice),
]
urlpatterns=[path('',v.home),path('login/',v.login_page),path('logout/',v.logout_view),path('health/',v.health),path('api/password/',v.password_change),path('api/me/',v.bootstrap),path('api/businesses/',v.create_business),path('api/b/<int:business_id>/state/',v.state),path('api/b/<int:business_id>/report/',v.report),path('api/b/<int:business_id>/action/',v.action),path('api/b/<int:business_id>/export/',v.export_csv),path('api/b/<int:business_id>/products/<int:product_id>/photo/',v.photo),path('api/b/<int:business_id>/invoices/<int:invoice_id>/pdf/',v.invoice_view)]

urlpatterns += demo_urls

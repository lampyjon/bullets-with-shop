from . import views
from django.views.generic import TemplateView, RedirectView
from django.shortcuts import redirect

from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include

shop_patterns = ([
    path('', views.index, name='home'),

    path('products', views.ShopProductList.as_view(), name='products'),
    path('product/<int:product_pk>/<slug:slug>', views.ShopProduct, name='product'),

    path('basket', views.ShopBasket, name='basket'),
    path('basket/update', views.ShopBasketUpdate, name='basket-update'),

], 'shop')




dashboard_patterns = ([
    path('', views.dashboard, name='index'),
    path('products', views.ProductList.as_view(), name='products'),
    path('products/add', views.product_create, name='product-add'),
    path('products/add/category/<int:category_pk>', views.product_create, name='product-add-category'),
    path('products/add/supplier/<int:supplier_pk>', views.product_create, name='product-add-supplier'),

    path('products/edit/<int:product_pk>', views.product_create, name='product-edit'),
  
    path('products/view/<int:product_pk>', views.product_view, name='product-view'),

    path('products/<int:product_pk>/items/edit', views.product_edit_items, name='product-edit-items'),
    path('products/<int:product_pk>/pictures/add', views.product_picture_create, name='product-picture-add'),


    path('orders', views.OrderList.as_view(), name='orders'),
    path('orders/paid', views.PaidOrderList.as_view(), name='orders-paid'),
    path('orders/<int:pk>/view', views.OrderDetail.as_view(), name='order'),


    path('categories', views.CategoryList.as_view(), name='categories'),
    path('categories/add', views.CategoryCreate.as_view(), name='category-add'),
    path('categories/<int:pk>/edit', views.CategoryUpdate.as_view(), name='category-update'),
    path('categories/<int:pk>/delete', views.CategoryDelete.as_view(), name='category-delete'),


    path('suppliers', views.SupplierList.as_view(), name='suppliers'),
    path('suppliers/add', views.SupplierCreate.as_view(), name='supplier-add'),
    path('suppliers/<int:pk>/edit', views.SupplierUpdate.as_view(), name='supplier-update'),
    path('suppliers/<int:pk>/delete', views.SupplierDelete.as_view(), name='supplier-delete'),
    path('suppliers/<int:pk>', views.SupplierDetail.as_view(), name='supplier-view'),
    path('suppliers/<int:supplier_pk>/delivery', views.supplier_delivery, name='supplier-delivery'),
    path('suppliers/<int:supplier_pk>/order', views.supplier_order, name='supplier-order'),
#    path('suppliers/<int:supplier_pk>/order/save', views.supplier_order_save, name='supplier-order-save'),

], 'dashboard')



urlpatterns = [
    path("", include(shop_patterns)),
    path("dashboard/", include(dashboard_patterns)),
]

 

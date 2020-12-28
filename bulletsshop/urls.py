from . import views
from django.views.generic import TemplateView, RedirectView
from django.shortcuts import redirect

from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include

shop_patterns = ([
    path('', views.index, name='home'),

    path('products', views.ShopProductList.as_view(), name='products'),
    path('products/category/<int:category_pk>', views.ShopProductCategoryList.as_view(), name='product-category'),
    path('product/<int:product_pk>/<slug:slug>', views.ShopProduct, name='product'),

    path('basket', views.ShopBasket, name='basket'),
    path('basket/update', views.ShopBasketUpdate, name='basket-update'),

    path('checkout/start', views.CheckoutViewBasket, name='checkout'),
    path('checkout/billing', views.CheckoutBillingAddress, name='checkout-billing'),
    path('checkout/delivery', views.CheckoutDeliveryAddress, name='checkout-delivery'),
    path('checkout/summary', views.CheckoutSummary, name='checkout-summary'),
    path('checkout/voucher', views.CheckoutAddVoucher, name='checkout-voucher'),
    path('checkout/voucher/remove', views.CheckoutRemoveVoucher, name='checkout-voucher-remove'),
  
    path('checkout/pay/<int:payment_id>', views.payment_details, name='pay'),
    path('checkout/pay/success/<uuid:uuid>', views.payment_success, name='payment-success'),
    path('checkout/pay/problem/<uuid:uuid>', views.payment_failed, name='payment-problem'),

    path('purchase/view/<uuid:uuid>', views.view_order, name='view-order'),
    path('purchase/pay/<uuid:uuid>', views.make_payment, name='pay-order'),

], 'shop')




dashboard_patterns = ([
    path('', views.dashboard, name='index'),
    path('products', views.ProductList.as_view(), name='products'),
    path('products/add', views.product_create, name='product-add'),
    path('products/add/category/<int:category_pk>', views.product_create, name='product-add-category'),
    path('products/add/supplier/<int:supplier_pk>', views.product_create, name='product-add-supplier'),

    path('products/edit/<int:product_pk>', views.product_create, name='product-edit'),
    path('products/edit/ajax/<int:product_pk>', views.product_edit_ajax, name='product-edit-ajax'),
    path('products/view/<int:product_pk>', views.product_view, name='product-view'),
    path('products/sell-now/<int:item_pk>', views.product_sell_now, name='product-sell-now'),

    path('products/<int:product_pk>/items/edit', views.product_edit_items, name='product-edit-items'),
    path('products/<int:product_pk>/pictures/add', views.product_picture_create, name='product-picture-add'),
    path('products/<int:product_pk>/pictures/view', views.product_picture_list, name='product-pictures-view'),
    path('products/pictures/<int:productpicture_pk>/delete', views.product_picture_delete, name='product-picture-delete'),


    path('products/<int:product_pk>/analytics', views.product_analytics, name='product-analytics'),
    path('products/<int:product_pk>/<int:year>/analytics', views.product_analytics, name='product-analytics'),
    path('products/<int:product_pk>/purchases', views.product_purchases, name='product-purchases'),

    path('products/<int:item_pk>/dispatch', views.product_bulk_ship, name='product-bulk-ship'),

    path('orders', views.order_list, {'status':'all'}, name='orders'),
    path('orders/paid', views.order_list, {'status':'paid'}, name='orders-paid'),
    path('orders/paid/outstanding', views.order_list, {'status':'outstanding'}, name='orders-paid-outstanding'),
    path('orders/unpaid', views.order_list, {'status':'unpaid'}, name='orders-unpaid'),

    path('orders/<int:pk>/view', views.OrderDetail.as_view(), name='order'),
    path('orders/<int:pk>/items-dispatch', views.order_items_dispatch, name='order-items-dispatch'),
    path('orders/<int:pk>/add-comment', views.order_comment, name='order-comment'),
    path('orders/<int:pk>/cash-payment', views.order_cash_payment, name='order-pay-cash'),
    path('orders/<int:pk>/cancel', views.order_cancel, name='order-cancel'),
    path('orders/item/<int:pk>/return', views.order_item_return, name='order-item-return'),


    path('categories', views.CategoryList.as_view(), name='categories'),
    path('categories/add', views.CategoryCreate.as_view(), name='category-add'),
    path('categories/<int:pk>/edit', views.CategoryUpdate.as_view(), name='category-update'),
    path('categories/<int:pk>/delete', views.CategoryDelete.as_view(), name='category-delete'),


    path('vouchers', views.VoucherList.as_view(), name='vouchers'),
    path('vouchers/add', views.VoucherCreate.as_view(), name='voucher-add'),
    path('vouchers/create-gift-voucher', views.gift_voucher_create, name='voucher-create-gift-voucher'),
    path('vouchers/view/<int:pk>', views.voucher_view, name='voucher-view'),
    path('vouchers/edit/<int:pk>', views.VoucherEdit.as_view(), name='voucher-edit'),


    path('suppliers', views.SupplierList.as_view(), name='suppliers'),
    path('suppliers/add', views.SupplierCreate.as_view(), name='supplier-add'),
    path('suppliers/<int:pk>/edit', views.SupplierUpdate.as_view(), name='supplier-update'),
    path('suppliers/<int:pk>/delete', views.SupplierDelete.as_view(), name='supplier-delete'),
    path('suppliers/<int:pk>', views.SupplierDetail.as_view(), name='supplier-view'),
    path('suppliers/<int:supplier_pk>/delivery', views.supplier_delivery, name='supplier-delivery'),
    path('suppliers/delivery/dispatch', views.supplier_delivery_dispatch, name='supplier-delivery-dispatch'),
    path('suppliers/<int:supplier_pk>/order', views.supplier_order, name='supplier-order'),
    path('suppliers/no-order-if-not-in-stock/<int:supplier_pk>', views.supplier_no_order, name='supplier-no-order'),

#   path('suppliers/<int:supplier_pk>/order/save', views.supplier_order_save, name='supplier-order-save'),

    path('postage', views.PostageList.as_view(), name='postage'),
    path('postage/add', views.PostageCreate.as_view(), name='postage-add'),
    path('postage/<int:pk>/edit', views.PostageUpdate.as_view(), name='postage-update'),
    path('postage/<int:pk>/delete', views.PostageDelete.as_view(), name='postage-delete'),

    path('allocations', views.allocations, name='allocations'),
#    path('allocations/date', views.allocations, {'order_by': 'date'}, name='allocations-date'),
 #   path('allocations/order', views.allocations, {'order_by': 'order'}, name='allocations-order'),
 #   path('allocations/item', views.allocations, {'order_by': 'item'}, name='allocations-item'),
    path('allocations/item/<int:item_pk>', views.allocations, name='allocations-specific-item'),

    path('allocations/item/on-order/<int:item_pk>', views.on_order_allocations, name='on-order-allocations'),


], 'dashboard')



urlpatterns = [
    path("", include(shop_patterns)),
    path("dashboard/", include(dashboard_patterns)),
    path('payments', include('payments.urls')),
]

 

from django.contrib import admin
from .models import Product, ProductCategory, Supplier, ProductItem, Order, OrderItem, Payment, OrderHistory, Voucher
admin.site.register(Product)
admin.site.register(Supplier)
admin.site.register(ProductCategory)
admin.site.register(ProductItem)
admin.site.register(Order)
admin.site.register(OrderItem)
admin.site.register(OrderHistory)
admin.site.register(Payment)
admin.site.register(Voucher)


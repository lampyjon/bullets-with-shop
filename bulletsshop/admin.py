from django.contrib import admin
from .models import Product, ProductCategory, Supplier, ProductItem
admin.site.register(Product)
admin.site.register(Supplier)
admin.site.register(ProductCategory)
admin.site.register(ProductItem)


from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('vlb-admin/', admin.site.urls),
    path('bullets-shop/', include('bulletsshop.urls')),
    path('', include('bulletsweb.urls')),
    path('summernote/', include('django_summernote.urls')),
]

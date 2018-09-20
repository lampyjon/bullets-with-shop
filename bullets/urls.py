from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('vlb-admin/', admin.site.urls),
    path('', include('bulletsweb.urls')),
]

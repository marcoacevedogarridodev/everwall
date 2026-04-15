# backend/pixels/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PixelViewSet

# Crear router para ViewSet
router = DefaultRouter()
router.register(r'pixels', PixelViewSet, basename='pixel')

# URLs adicionales fuera del router
urlpatterns = [
    path('', include(router.urls)),
]

# URLs adicionales (si necesitas endpoints específicos)
# urlpatterns += []

# backend/pixels/apps.py
from django.apps import AppConfig

class PixelsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'pixels'
    verbose_name = 'Gestión de Pixeles Everwall'

    def ready(self):
        pass

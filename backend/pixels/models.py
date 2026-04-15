# backend/pixels/models.py
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import uuid
import random
import string

class PixelGridConfig(models.Model):
    """Configuración global de la grilla"""
    grid_width = models.IntegerField(default=100, validators=[MinValueValidator(1), MaxValueValidator(1000)])
    grid_height = models.IntegerField(default=100, validators=[MinValueValidator(1), MaxValueValidator(1000)])
    pixel_price_usd = models.DecimalField(max_digits=10, decimal_places=2, default=1.00)
    pixel_price_clp = models.IntegerField(default=1000)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuración de Grilla"
        verbose_name_plural = "Configuraciones de Grilla"
        ordering = ['-created_at']

    def __str__(self):
        return f"Grid {self.grid_width}x{self.grid_height} - ${self.pixel_price_usd} USD / ${self.pixel_price_clp} CLP"

class Pixel(models.Model):
    """Modelo principal del pixel comprado"""
    STATUS_CHOICES = [
        ('available', 'Disponible'),
        ('reserved', 'Reservado'),
        ('sold', 'Vendido'),
        ('pending_payment', 'Pago Pendiente'),
    ]

    MODERATION_STATUS = [
        ('pending', 'Pendiente'),
        ('approved', 'Aprobada'),
        ('rejected', 'Rechazada'),
    ]

    # Ubicación en grilla
    x = models.IntegerField(validators=[MinValueValidator(0)])
    y = models.IntegerField(validators=[MinValueValidator(0)])

    # Códigos únicos para búsqueda
    access_code = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    search_code = models.CharField(max_length=12, unique=True, editable=False)
    display_code = models.CharField(max_length=20, unique=True, editable=False)  # #XXXXX format

    # Imágenes
    main_image = models.ImageField(upload_to='pixels/%Y/%m/%d/', max_length=500)
    additional_images = models.JSONField(default=list, blank=True)
    image_filename = models.CharField(max_length=255, blank=True)

    # Información del dueño
    owner_name = models.CharField(max_length=200, blank=True)
    owner_email = models.EmailField()
    owner_message = models.TextField(max_length=500, blank=True)

    # Datos de pago
    purchase_id = models.CharField(max_length=100, unique=True, blank=True, null=True)
    amount_usd = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    amount_clp = models.IntegerField(null=True, blank=True)
    payment_currency = models.CharField(max_length=3, choices=[('USD', 'USD'), ('CLP', 'CLP')], blank=True)
    stripe_payment_intent_id = models.CharField(max_length=200, unique=True, blank=True, null=True)
    stripe_payment_method = models.CharField(max_length=100, blank=True)
    payment_status = models.CharField(max_length=50, default='pending')

    # Estados
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending_payment')
    moderation_status = models.CharField(max_length=20, choices=MODERATION_STATUS, default='pending')
    moderation_reason = models.TextField(blank=True)
    moderation_flagged_categories = models.JSONField(default=list, blank=True)

    # Estadísticas
    views_count = models.IntegerField(default=0)
    shares_count = models.JSONField(default=dict, blank=True)

    # Timestamps
    purchased_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['x', 'y']
        indexes = [
            models.Index(fields=['x', 'y']),
            models.Index(fields=['access_code']),
            models.Index(fields=['search_code']),
            models.Index(fields=['display_code']),
            models.Index(fields=['owner_email']),
            models.Index(fields=['status', 'moderation_status']),
            models.Index(fields=['-purchased_at']),
        ]
        ordering = ['-purchased_at']

    def save(self, *args, **kwargs):
        if not self.search_code:
            self.search_code = self.generate_search_code()
        if not self.display_code:
            self.display_code = self.generate_display_code()
        super().save(*args, **kwargs)

    def generate_search_code(self):
        """Genera código legible tipo PX-ABC123"""
        while True:
            chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            code = f"PX-{chars}"
            if not Pixel.objects.filter(search_code=code).exists():
                return code

    def generate_display_code(self):
        """Genera código para mostrar tipo #12345"""
        while True:
            code = f"#{random.randint(10000, 99999)}"
            if not Pixel.objects.filter(display_code=code).exists():
                return code

    def increment_views(self):
        """Incrementa contador de vistas"""
        self.views_count += 1
        self.save(update_fields=['views_count'])

    def increment_share(self, platform):
        """Incrementa contador de compartidos"""
        if not self.shares_count:
            self.shares_count = {}
        self.shares_count[platform] = self.shares_count.get(platform, 0) + 1
        self.save(update_fields=['shares_count'])

    @property
    def all_images(self):
        """Retorna todas las imágenes"""
        images = [self.main_image.url] if self.main_image else []
        images.extend(self.additional_images)
        return images

    @property
    def grid_position(self):
        return f"({self.x}, {self.y})"

    @property
    def share_url(self):
        return f"/pixel/{self.search_code}"

    def __str__(self):
        return f"Pixel {self.grid_position} - {self.display_code}"

class PixelPurchaseSession(models.Model):
    """Sesión temporal de compra"""
    session_id = models.CharField(max_length=100, unique=True)
    pixel_x = models.IntegerField()
    pixel_y = models.IntegerField()
    images_data = models.JSONField(default=list)
    image_filenames = models.JSONField(default=list)
    owner_email = models.EmailField()
    owner_name = models.CharField(max_length=200, blank=True)
    owner_message = models.TextField(blank=True)
    payment_intent_id = models.CharField(max_length=200, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_completed = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=['session_id']),
            models.Index(fields=['expires_at']),
            models.Index(fields=['payment_intent_id']),
        ]

    def __str__(self):
        return f"Sesión {self.session_id[:8]} - Pixel ({self.pixel_x}, {self.pixel_y})"

class PixelViewLog(models.Model):
    """Registro detallado de vistas por IP"""
    pixel = models.ForeignKey(Pixel, on_delete=models.CASCADE, related_name='view_logs')
    viewer_ip = models.GenericIPAddressField()
    viewer_user_agent = models.TextField(blank=True)
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['pixel', 'viewed_at']),
            models.Index(fields=['viewed_at']),
        ]
        ordering = ['-viewed_at']

    def __str__(self):
        return f"{self.pixel.display_code} visto desde {self.viewer_ip} - {self.viewed_at}"

# backend/pixels/admin.py
from django.contrib import admin
from django.utils.html import format_html
from .models import Pixel, PixelGridConfig, PixelPurchaseSession, PixelViewLog

@admin.register(Pixel)
class PixelAdmin(admin.ModelAdmin):
    list_display = ['display_code', 'search_code', 'x', 'y', 'owner_name', 'owner_email', 'status', 'moderation_status', 'views_count', 'purchased_at']
    list_filter = ['status', 'moderation_status', 'payment_status', 'purchased_at']
    search_fields = ['search_code', 'display_code', 'access_code', 'owner_email', 'owner_name']
    readonly_fields = ['search_code', 'display_code', 'access_code', 'created_at', 'updated_at', 'views_count']

    fieldsets = (
        ('Ubicación en Grilla', {
            'fields': ('x', 'y')
        }),
        ('Códigos de Identificación', {
            'fields': ('search_code', 'display_code', 'access_code'),
            'classes': ('wide',)
        }),
        ('Información del Dueño', {
            'fields': ('owner_name', 'owner_email', 'owner_message')
        }),
        ('Imágenes', {
            'fields': ('main_image', 'additional_images', 'image_filename'),
            'classes': ('wide',)
        }),
        ('Información de Pago', {
            'fields': ('purchase_id', 'stripe_payment_intent_id', 'stripe_payment_method', 'amount_usd', 'amount_clp', 'payment_currency', 'payment_status')
        }),
        ('Estados', {
            'fields': ('status', 'moderation_status', 'moderation_reason', 'moderation_flagged_categories')
        }),
        ('Estadísticas', {
            'fields': ('views_count', 'shares_count')
        }),
        ('Fechas', {
            'fields': ('purchased_at', 'created_at', 'updated_at')
        }),
    )

    def thumbnail(self, obj):
        if obj.main_image:
            return format_html('<img src="{}" width="50" height="50" style="object-fit: cover;" />', obj.main_image.url)
        return "Sin imagen"
    thumbnail.short_description = 'Miniatura'

@admin.register(PixelGridConfig)
class PixelGridConfigAdmin(admin.ModelAdmin):
    list_display = ['grid_width', 'grid_height', 'pixel_price_usd', 'pixel_price_clp', 'is_active', 'created_at']
    list_editable = ['is_active']
    fieldsets = (
        ('Dimensiones de la Grilla', {
            'fields': ('grid_width', 'grid_height')
        }),
        ('Precios', {
            'fields': ('pixel_price_usd', 'pixel_price_clp')
        }),
        ('Estado', {
            'fields': ('is_active',)
        }),
    )

@admin.register(PixelPurchaseSession)
class PixelPurchaseSessionAdmin(admin.ModelAdmin):
    list_display = ['session_id', 'pixel_x', 'pixel_y', 'owner_email', 'created_at', 'expires_at', 'is_completed']
    list_filter = ['is_completed', 'created_at']
    search_fields = ['session_id', 'owner_email']
    readonly_fields = ['session_id', 'created_at']

@admin.register(PixelViewLog)
class PixelViewLogAdmin(admin.ModelAdmin):
    list_display = ['pixel', 'viewer_ip', 'viewed_at']
    list_filter = ['viewed_at']
    search_fields = ['pixel__display_code', 'viewer_ip']
    readonly_fields = ['pixel', 'viewer_ip', 'viewer_user_agent', 'viewed_at']

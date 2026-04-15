# backend/pixels/serializers.py
from rest_framework import serializers
from django.db import models as django_models
from .models import Pixel, PixelGridConfig, PixelPurchaseSession

class PixelSerializer(serializers.ModelSerializer):
    all_images = serializers.ListField(read_only=True)
    grid_position = serializers.CharField(read_only=True)
    image_url = serializers.SerializerMethodField()
    formatted_date = serializers.SerializerMethodField()

    class Meta:
        model = Pixel
        fields = [
            'id', 'x', 'y', 'access_code', 'search_code', 'display_code',
            'main_image', 'additional_images', 'all_images', 'image_url',
            'owner_name', 'owner_email', 'owner_message', 'image_filename',
            'purchased_at', 'formatted_date', 'grid_position',
            'moderation_status', 'payment_status', 'status', 'views_count'
        ]
        read_only_fields = ['access_code', 'search_code', 'display_code',
                           'moderation_status', 'purchased_at', 'views_count']

    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.main_image and request:
            return request.build_absolute_uri(obj.main_image.url)
        return None

    def get_formatted_date(self, obj):
        return obj.purchased_at.strftime('%d de %B, %Y')

class PixelPurchaseSerializer(serializers.Serializer):
    x = serializers.IntegerField(min_value=0, max_value=999)
    y = serializers.IntegerField(min_value=0, max_value=999)
    owner_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    owner_email = serializers.EmailField()
    owner_message = serializers.CharField(max_length=500, required=False, allow_blank=True)
    currency = serializers.ChoiceField(choices=['USD', 'CLP'], default='CLP')

    def validate(self, data):
        # Verificar que el pixel esté disponible
        if Pixel.objects.filter(x=data['x'], y=data['y'], status='sold').exists():
            raise serializers.ValidationError({
                'error': f"El pixel ({data['x']}, {data['y']}) ya está vendido"
            })
        return data

class PixelSearchSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=50)

    def validate_code(self, value):
        value = value.strip().upper()
        if not Pixel.objects.filter(
            django_models.Q(search_code=value) |
            django_models.Q(display_code=value) |
            django_models.Q(access_code=value)
        ).exists():
            raise serializers.ValidationError("No se encontró ningún pixel con ese código")
        return value

class PixelGridConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = PixelGridConfig
        fields = '__all__'

class PixelPurchaseSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PixelPurchaseSession
        fields = '__all__'

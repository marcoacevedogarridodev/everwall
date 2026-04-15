# backend/pixels/services/grid_manager.py
from django.core.cache import cache
from ..models import Pixel, PixelGridConfig
import logging

logger = logging.getLogger(__name__)

class GridManager:
    """Gestor de la grilla con caché"""

    CACHE_KEY = 'grid_status'
    CACHE_TIMEOUT = 300  # 5 minutos

    @staticmethod
    def get_grid_status(request=None):
        """Retorna estado completo de la grilla"""
        cached = cache.get(GridManager.CACHE_KEY)

        if cached:
            return cached

        config = PixelGridConfig.objects.filter(is_active=True).first()
        if not config:
            config = PixelGridConfig.objects.create()

        total_pixels = config.grid_width * config.grid_height
        sold_pixels = Pixel.objects.filter(status='sold', moderation_status='approved').count()

        # Obtener últimos 100 pixeles para rendimiento
        occupied = Pixel.objects.filter(
            status='sold',
            moderation_status='approved'
        ).values('x', 'y', 'search_code', 'display_code', 'owner_name', 'main_image')[:100]

        # Agregar URLs completas
        occupied_list = []
        for pixel in occupied:
            pixel_data = dict(pixel)
            if request and pixel.get('main_image'):
                pixel_data['image_url'] = request.build_absolute_uri(pixel['main_image'])
            occupied_list.append(pixel_data)

        result = {
            'grid_width': config.grid_width,
            'grid_height': config.grid_height,
            'total_pixels': total_pixels,
            'sold_pixels': sold_pixels,
            'available_pixels': total_pixels - sold_pixels,
            'percentage_sold': round((sold_pixels / total_pixels) * 100, 2) if total_pixels > 0 else 0,
            'occupied_positions': occupied_list,
            'price_usd': float(config.pixel_price_usd),
            'price_clp': config.pixel_price_clp
        }

        cache.set(GridManager.CACHE_KEY, result, GridManager.CACHE_TIMEOUT)
        return result

    @staticmethod
    def invalidate_cache():
        """Invalida caché cuando se vende un pixel"""
        cache.delete(GridManager.CACHE_KEY)
        logger.info("Grid cache invalidated")

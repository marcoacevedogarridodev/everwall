# backend/pixels/services/email.py
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags
import logging

logger = logging.getLogger(__name__)

class EmailService:
    """Servicio para envío de emails"""

    @staticmethod
    def send_pixel_confirmation(pixel, request):
        """Envía email de confirmación al comprador"""
        try:
            base_url = getattr(settings, 'BASE_URL', 'http://localhost:8000')
            pixel_url = f"{base_url}/pixel/{pixel.search_code}"
            grid_url = f"{base_url}/grid"

            context = {
                'pixel': pixel,
                'display_code': pixel.display_code,
                'search_code': pixel.search_code,
                'pixel_url': pixel_url,
                'grid_url': grid_url,
                'purchased_date': pixel.purchased_at.strftime('%d/%m/%Y %H:%M'),
                'coordinates': f"({pixel.x}, {pixel.y})",
                'image_url': request.build_absolute_uri(pixel.main_image.url) if pixel.main_image else None,
                'share_facebook': f"https://www.facebook.com/sharer/sharer.php?u={pixel_url}",
                'share_twitter': f"https://twitter.com/intent/tweet?text=¡Mi pixel eterno en Everwall!&url={pixel_url}",
                'share_whatsapp': f"https://wa.me/?text=¡Mira mi pixel eterno en Everwall! {pixel_url}",
            }

            html_message = render_to_string('emails/pixel_confirmation.html', context)
            plain_message = strip_tags(html_message)

            if settings.EMAIL_HOST_USER:
                send_mail(
                    subject=f'✨ Tu pixel eterno en Everwall - Código {pixel.display_code}',
                    message=plain_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[pixel.owner_email],
                    html_message=html_message,
                    fail_silently=False,
                )
                logger.info(f"Email enviado a {pixel.owner_email}")
            else:
                logger.warning("Email no configurado, no se envió confirmación")

            return True

        except Exception as e:
            logger.error(f"Error enviando email: {str(e)}")
            return False

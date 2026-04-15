# backend/pixels/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.db import models as django_models
from datetime import timedelta
import uuid
import logging

from .models import Pixel, PixelPurchaseSession, PixelGridConfig, PixelViewLog
from .serializers import PixelSerializer, PixelPurchaseSerializer, PixelSearchSerializer
from .services.moderation import ImageModerationService
from .services.payment import StripePaymentService
from .services.email import EmailService
from .services.grid_manager import GridManager

logger = logging.getLogger(__name__)

class PixelViewSet(viewsets.GenericViewSet):
    """
    ViewSet para gestionar pixeles de Everwall
    """
    queryset = Pixel.objects.all()
    serializer_class = PixelSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @action(detail=False, methods=['get'])
    def grid_status(self, request):
        """
        GET /api/pixels/grid_status/
        Obtener estado completo de la grilla
        """
        try:
            status_data = GridManager.get_grid_status(request)
            return Response({
                'success': True,
                'data': status_data,
                'timestamp': timezone.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Error en grid_status: {str(e)}")
            return Response({
                'success': False,
                'error': 'Error al obtener estado de la grilla'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    def initiate_purchase(self, request):
        """
        POST /api/pixels/initiate_purchase/
        Iniciar compra de un pixel con imágenes
        """
        # Validar campos requeridos
        required_fields = ['x', 'y', 'owner_email']
        for field in required_fields:
            if field not in request.data:
                return Response({
                    'success': False,
                    'error': f'Campo requerido: {field}'
                }, status=status.HTTP_400_BAD_REQUEST)

        # Validar imágenes
        images = request.FILES.getlist('images')
        if not images:
            return Response({
                'success': False,
                'error': 'Debes subir al menos una imagen'
            }, status=status.HTTP_400_BAD_REQUEST)

        if len(images) > 5:
            return Response({
                'success': False,
                'error': 'Máximo 5 imágenes por pixel'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            x = int(request.data['x'])
            y = int(request.data['y'])
        except ValueError:
            return Response({
                'success': False,
                'error': 'Coordenadas inválidas'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Verificar pixel disponible
        if Pixel.objects.filter(x=x, y=y, status='sold').exists():
            return Response({
                'success': False,
                'error': f'El pixel ({x}, {y}) ya fue comprado para la eternidad',
                'pixel_available': False
            }, status=status.HTTP_409_CONFLICT)

        # Moderar imágenes
        moderated_images = []
        image_filenames = []
        moderation_service = ImageModerationService()

        for image in images:
            try:
                is_approved, reason, categories = moderation_service.moderate_image(image, image.name)

                if not is_approved:
                    return Response({
                        'success': False,
                        'error': f'Imagen "{image.name}" rechazada: {reason}',
                        'moderation_details': {
                            'reason': reason,
                            'categories': categories
                        }
                    }, status=status.HTTP_400_BAD_REQUEST)

                # Guardar imagen temporalmente
                temp_filename = f'temp/{uuid.uuid4()}_{image.name}'
                saved_path = default_storage.save(temp_filename, ContentFile(image.read()))
                moderated_images.append(saved_path)
                image_filenames.append(image.name)

            except Exception as e:
                logger.error(f"Error moderando imagen {image.name}: {str(e)}")
                return Response({
                    'success': False,
                    'error': f'Error procesando imagen {image.name}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Obtener configuración
        config = PixelGridConfig.objects.filter(is_active=True).first()
        if not config:
            config = PixelGridConfig.objects.create()

        # Determinar moneda
        currency = request.data.get('currency', 'CLP')

        # Crear sesión
        session = PixelPurchaseSession.objects.create(
            session_id=str(uuid.uuid4()),
            pixel_x=x,
            pixel_y=y,
            images_data=moderated_images,
            image_filenames=image_filenames,
            owner_email=request.data['owner_email'],
            owner_name=request.data.get('owner_name', ''),
            owner_message=request.data.get('owner_message', ''),
            expires_at=timezone.now() + timedelta(minutes=30)
        )

        # Calcular monto
        if currency == 'USD':
            amount = int(config.pixel_price_usd * 100)
            price_display = f"${config.pixel_price_usd} USD"
        else:
            amount = config.pixel_price_clp
            price_display = f"${config.pixel_price_clp} CLP"

        return Response({
            'success': True,
            'data': {
                'session_id': session.session_id,
                'pixel_coords': {'x': x, 'y': y},
                'prices': {
                    'usd': float(config.pixel_price_usd),
                    'clp': config.pixel_price_clp
                },
                'selected_currency': currency,
                'amount_to_pay': amount,
                'price_display': price_display,
                'expires_at': session.expires_at.isoformat(),
                'images_uploaded': len(moderated_images),
                'moderation_status': 'approved'
            }
        })

    @action(detail=False, methods=['post'])
    def create_payment_intent(self, request):
        """
        POST /api/pixels/create_payment_intent/
        Crear PaymentIntent de Stripe
        """
        session_id = request.data.get('session_id')
        currency = request.data.get('currency', 'CLP')

        if not session_id:
            return Response({
                'success': False,
                'error': 'session_id requerido'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            session = PixelPurchaseSession.objects.get(session_id=session_id, is_completed=False)
        except PixelPurchaseSession.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Sesión no encontrada o ya completada'
            }, status=status.HTTP_404_NOT_FOUND)

        if session.expires_at < timezone.now():
            return Response({
                'success': False,
                'error': 'La sesión ha expirado. Debes iniciar una nueva compra'
            }, status=status.HTTP_410_GONE)

        config = PixelGridConfig.objects.filter(is_active=True).first()
        if not config:
            config = PixelGridConfig.objects.create()

        # Calcular monto
        if currency.upper() == 'USD':
            amount = int(config.pixel_price_usd * 100)
        else:
            amount = config.pixel_price_clp

        # Crear PaymentIntent
        try:
            payment_data = StripePaymentService.create_payment_intent(
                pixel_data={
                    'x': session.pixel_x,
                    'y': session.pixel_y,
                    'owner_email': session.owner_email,
                },
                amount=amount,
                currency=currency.lower(),
                session_id=session.session_id
            )

            # Guardar payment_intent_id en la sesión
            session.payment_intent_id = payment_data['payment_intent_id']
            session.save(update_fields=['payment_intent_id'])

            return Response({
                'success': True,
                'data': {
                    'client_secret': payment_data['client_secret'],
                    'payment_intent_id': payment_data['payment_intent_id'],
                    'amount': payment_data['amount'],
                    'currency': payment_data['currency'],
                    'pixel_id': f"{session.pixel_x}_{session.pixel_y}"
                }
            })

        except Exception as e:
            logger.error(f"Error creating payment intent: {str(e)}")
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def confirm_purchase(self, request):
        """
        POST /api/pixels/confirm_purchase/
        Confirmar compra después del pago
        """
        payment_intent_id = request.data.get('payment_intent_id')
        session_id = request.data.get('session_id')

        if not payment_intent_id or not session_id:
            return Response({
                'success': False,
                'error': 'payment_intent_id y session_id son requeridos'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            session = PixelPurchaseSession.objects.get(session_id=session_id)
        except PixelPurchaseSession.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Sesión no encontrada'
            }, status=status.HTTP_404_NOT_FOUND)

        # Verificar pago en Stripe
        payment_intent = StripePaymentService.retrieve_payment_intent(payment_intent_id)
        if not payment_intent or payment_intent.status != 'succeeded':
            return Response({
                'success': False,
                'error': 'El pago no ha sido completado'
            }, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            # Mover imágenes a ubicación permanente
            main_image = None
            additional_images = []

            for idx, img_path in enumerate(session.images_data):
                if default_storage.exists(img_path):
                    final_path = f'pixels/{session.session_id}/image_{idx}.jpg'
                    saved_path = default_storage.save(final_path, default_storage.open(img_path))
                    if idx == 0:
                        main_image = saved_path
                    else:
                        additional_images.append(saved_path)

            # Crear pixel
            pixel = Pixel.objects.create(
                x=session.pixel_x,
                y=session.pixel_y,
                main_image=main_image,
                additional_images=additional_images,
                image_filename=session.image_filenames[0] if session.image_filenames else '',
                owner_name=session.owner_name,
                owner_email=session.owner_email,
                owner_message=session.owner_message,
                purchase_id=payment_intent_id,
                stripe_payment_intent_id=payment_intent_id,
                stripe_payment_method=payment_intent.payment_method,
                amount_usd=payment_intent.amount if payment_intent.currency == 'usd' else None,
                amount_clp=payment_intent.amount if payment_intent.currency == 'clp' else None,
                payment_currency=payment_intent.currency.upper(),
                payment_status='completed',
                status='sold',
                moderation_status='approved',
                purchased_at=timezone.now()
            )

            session.is_completed = True
            session.save()

            # Invalidar caché
            GridManager.invalidate_cache()

            # Enviar email de confirmación
            EmailService.send_pixel_confirmation(pixel, request)

            # Preparar respuesta
            response_data = PixelSerializer(pixel, context={'request': request}).data

            # Agregar URLs para compartir
            base_url = request.build_absolute_uri('/').rstrip('/')
            pixel_url = f"{base_url}/pixel/{pixel.search_code}"

            response_data.update({
                'share_urls': {
                    'facebook': f"https://www.facebook.com/sharer/sharer.php?u={pixel_url}",
                    'twitter': f"https://twitter.com/intent/tweet?text=¡Mi pixel eterno en Everwall!&url={pixel_url}",
                    'whatsapp': f"https://wa.me/?text=¡Mira mi pixel eterno en Everwall! {pixel_url}",
                    'copy_link': pixel_url
                },
                'view_pixel_url': pixel_url,
                'grid_url': f"{base_url}/grid"
            })

            return Response({
                'success': True,
                'message': '¡Felicidades! Tu pixel quedará en Everwall para la eternidad',
                'data': response_data
            })

    @action(detail=False, methods=['post'])
    def search_pixel(self, request):
        """
        POST /api/pixels/search_pixel/
        Buscar pixel por código (#XXXXX o PX-XXXXX)
        """
        code = request.data.get('code', '').strip().upper()

        if not code:
            return Response({
                'success': False,
                'error': 'Código requerido'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            pixel = Pixel.objects.get(
                django_models.Q(display_code=code) |
                django_models.Q(search_code=code) |
                django_models.Q(access_code=code),
                status='sold',
                moderation_status='approved'
            )

            # Incrementar contador de vistas
            pixel.increment_views()

            # Registrar vista detallada
            PixelViewLog.objects.create(
                pixel=pixel,
                viewer_ip=request.META.get('REMOTE_ADDR', '0.0.0.0'),
                viewer_user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
            )

            # Preparar respuesta
            serializer = PixelSerializer(pixel, context={'request': request})
            data = serializer.data

            base_url = request.build_absolute_uri('/').rstrip('/')
            pixel_url = f"{base_url}/pixel/{pixel.search_code}"

            data.update({
                'views_count': pixel.views_count,
                'image_filename': pixel.image_filename,
                'formatted_date': pixel.purchased_at.strftime('%d de %B, %Y'),
                'share_urls': {
                    'facebook': f"https://www.facebook.com/sharer/sharer.php?u={pixel_url}",
                    'twitter': f"https://twitter.com/intent/tweet?text=¡Mi pixel eterno en Everwall!&url={pixel_url}",
                    'whatsapp': f"https://wa.me/?text=¡Mira mi pixel eterno en Everwall! {pixel_url}",
                    'copy_link': pixel_url
                }
            })

            return Response({
                'success': True,
                'data': data
            })

        except Pixel.DoesNotExist:
            return Response({
                'success': False,
                'error': 'No se encontró ningún pixel con ese código',
                'code_provided': code
            }, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['post'])
    def share_pixel(self, request):
        """
        POST /api/pixels/share_pixel/
        Registrar cuando un usuario comparte un pixel
        """
        code = request.data.get('code', '').strip().upper()
        platform = request.data.get('platform')

        if not code or not platform:
            return Response({
                'success': False,
                'error': 'Código y plataforma requeridos'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            pixel = Pixel.objects.get(
                django_models.Q(display_code=code) |
                django_models.Q(search_code=code)
            )
            pixel.increment_share(platform)

            return Response({
                'success': True,
                'message': f'Compartido en {platform} registrado'
            })
        except Pixel.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Pixel no encontrado'
            }, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        GET /api/pixels/stats/
        Estadísticas rápidas
        """
        config = PixelGridConfig.objects.filter(is_active=True).first()
        total_pixels = config.grid_width * config.grid_height if config else 10000
        sold_pixels = Pixel.objects.filter(status='sold').count()
        total_views = Pixel.objects.aggregate(total=django_models.Sum('views_count'))['total'] or 0
        pending_moderation = Pixel.objects.filter(moderation_status='pending').count()

        return Response({
            'success': True,
            'data': {
                'total_pixels': total_pixels,
                'sold_pixels': sold_pixels,
                'available_pixels': total_pixels - sold_pixels,
                'percentage_sold': round((sold_pixels / total_pixels) * 100, 2) if total_pixels > 0 else 0,
                'total_views': total_views,
                'pending_moderation': pending_moderation,
                'price_usd': float(config.pixel_price_usd) if config else 1.00,
                'price_clp': config.pixel_price_clp if config else 1000
            }
        })

    @action(detail=False, methods=['get'])
    def recent_pixels(self, request):
        """
        GET /api/pixels/recent_pixels/?limit=10
        Últimos pixeles comprados
        """
        limit = int(request.query_params.get('limit', 10))

        recent = Pixel.objects.filter(
            status='sold',
            moderation_status='approved'
        ).order_by('-purchased_at')[:limit]

        serializer = PixelSerializer(recent, many=True, context={'request': request})

        return Response({
            'success': True,
            'data': serializer.data
        })

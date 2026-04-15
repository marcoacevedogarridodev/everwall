# backend/pixels/services/payment.py
import stripe
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class StripePaymentService:
    """Servicio de pagos con Stripe"""

    def __init__(self):
        if settings.STRIPE_SECRET_KEY:
            stripe.api_key = settings.STRIPE_SECRET_KEY

    @staticmethod
    def create_payment_intent(pixel_data, amount, currency, session_id):
        """
        Crea un PaymentIntent de Stripe
        """
        try:
            if not settings.STRIPE_SECRET_KEY:
                # Modo desarrollo sin Stripe
                logger.warning("Stripe API key no configurada, usando modo simulación")
                return {
                    'client_secret': 'simulated_client_secret',
                    'payment_intent_id': f'simulated_{session_id}',
                    'amount': amount,
                    'currency': currency
                }

            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency.lower(),
                metadata={
                    'pixel_x': pixel_data['x'],
                    'pixel_y': pixel_data['y'],
                    'owner_email': pixel_data['owner_email'],
                    'session_id': session_id,
                    'platform': 'everwall'
                },
                receipt_email=pixel_data['owner_email'],
                description=f"Compra de pixel ({pixel_data['x']}, {pixel_data['y']}) - Everwall",
                statement_descriptor="EVERWALL PIXEL"
            )

            logger.info(f"PaymentIntent creado: {intent.id}")

            return {
                'client_secret': intent.client_secret,
                'payment_intent_id': intent.id,
                'amount': intent.amount,
                'currency': intent.currency
            }

        except stripe.error.StripeError as e:
            logger.error(f"Error de Stripe: {str(e)}")
            raise Exception(f"Error de pago: {str(e)}")

    @staticmethod
    def retrieve_payment_intent(payment_intent_id):
        """Obtener información de un PaymentIntent"""
        try:
            if not settings.STRIPE_SECRET_KEY or payment_intent_id.startswith('simulated_'):
                # Modo simulación
                return type('obj', (object,), {
                    'status': 'succeeded',
                    'amount': 1000,
                    'currency': 'clp',
                    'payment_method': 'simulated',
                    'id': payment_intent_id
                })

            return stripe.PaymentIntent.retrieve(payment_intent_id)

        except stripe.error.StripeError as e:
            logger.error(f"Error recuperando PaymentIntent: {str(e)}")
            return None

# backend/pixels/services/moderation.py
import openai
from django.conf import settings
import base64
from PIL import Image
import logging

logger = logging.getLogger(__name__)

class ImageModerationService:
    """Servicio de moderación de imágenes con OpenAI GPT-4 Vision"""

    def __init__(self):
        if settings.OPENAI_API_KEY and settings.OPENAI_API_KEY != 'sk-dummy-key':
            openai.api_key = settings.OPENAI_API_KEY

    @staticmethod
    def moderate_image(image_file, image_filename):
        """
        Modera una imagen usando OpenAI GPT-4 Vision
        Retorna: (is_approved, reason, flagged_categories)
        """
        try:
            # Verificar que la API key esté configurada
            if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY == 'sk-dummy-key':
                logger.warning("OpenAI API key no configurada, usando moderación básica")
                return ImageModerationService._basic_moderation(image_file, image_filename)

            # Preparar imagen para OpenAI
            image_file.seek(0)
            image_data = image_file.read()
            base64_image = base64.b64encode(image_data).decode('utf-8')

            # Determinar tipo de contenido
            content_type = "image/jpeg"
            if image_filename.lower().endswith('.png'):
                content_type = "image/png"
            elif image_filename.lower().endswith('.webp'):
                content_type = "image/webp"

            # Llamar a OpenAI GPT-4 Vision
            client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)

            response = client.chat.completions.create(
                model="gpt-4o-mini",  # Usar modelo más económico
                messages=[
                    {
                        "role": "system",
                        "content": "Eres un moderador de contenido. Analiza imágenes y determina si contienen contenido prohibido: desnudos, violencia gráfica, gore, odio racial, discriminación, drogas, armas, material ilegal, o contenido sexual explícito. Responde SOLO en formato JSON."
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Analiza esta imagen. Responde con un JSON exactamente así: {\"approved\": true/false, \"reason\": \"razón si es rechazada\", \"categories\": [\"categoría1\", \"categoría2\"]}"
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{content_type};base64,{base64_image}",
                                    "detail": "low"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=300,
                temperature=0.1
            )

            # Parsear respuesta
            import json
            result_text = response.choices[0].message.content
            result_text = result_text.replace('```json', '').replace('```', '').strip()
            result = json.loads(result_text)

            is_approved = result.get('approved', True)
            reason = result.get('reason', '')
            categories = result.get('categories', [])

            if not is_approved:
                logger.info(f"Imagen rechazada: {image_filename} - Razón: {reason}")
                return False, reason, categories

            return True, "Imagen aprobada", []

        except Exception as e:
            logger.error(f"Error en moderación OpenAI: {str(e)}")
            return ImageModerationService._basic_moderation(image_file, image_filename)

    @staticmethod
    def _basic_moderation(image_file, image_filename):
        """Moderación básica local (fallback)"""
        try:
            image_file.seek(0)
            img = Image.open(image_file)

            # Verificar dimensiones
            if img.width > 2000 or img.height > 2000:
                return False, "La imagen es demasiado grande (máx 2000x2000px)", ["dimensions"]

            # Verificar formato
            if img.format not in ['JPEG', 'PNG', 'WEBP']:
                return False, "Formato no soportado. Usa JPEG, PNG o WEBP", ["format"]

            # Verificar tamaño de archivo (máx 5MB)
            image_file.seek(0, 2)
            file_size = image_file.tell()
            image_file.seek(0)
            if file_size > 5 * 1024 * 1024:
                return False, "La imagen es demasiado grande (máx 5MB)", ["size"]

            return True, "Imagen aprobada", []

        except Exception as e:
            return False, f"Error al procesar imagen: {str(e)}", ["error"]

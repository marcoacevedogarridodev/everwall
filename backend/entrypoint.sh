#!/bin/bash
# backend/entrypoint.sh

set -e

echo "Iniciando Everwall Backend..."

# Esperar a que PostgreSQL esté listo
if [ -n "$DATABASE_HOST" ]; then
    echo "Esperando a PostgreSQL en $DATABASE_HOST:$DATABASE_PORT..."
    while ! nc -z $DATABASE_HOST $DATABASE_PORT; do
        sleep 0.5
    done
    echo "PostgreSQL está listo"
fi

# Esperar a que Redis esté listo
if [ -n "$REDIS_HOST" ]; then
    echo "Esperando a Redis en $REDIS_HOST:$REDIS_PORT..."
    while ! nc -z $REDIS_HOST $REDIS_PORT; do
        sleep 0.5
    done
    echo "Redis está listo"
fi

# Aplicar migraciones
echo "Aplicando migraciones..."
python manage.py makemigrations
python manage.py migrate

# Crear superusuario si no existe (opcional)
echo "Creando superusuario si no existe..."
python manage.py shell -c "
from django.contrib.auth import get_user_model;
User = get_user_model();
if not User.objects.filter(is_superuser=True).exists():
    User.objects.create_superuser('admin', 'admin@everwall.com', 'admin123456')
    print('Superusuario creado: admin/admin123456')
"

# Recolectar archivos estáticos
echo "Recolectando archivos estáticos..."
python manage.py collectstatic --noinput

# Iniciar servidor
echo "Iniciando servidor Django en http://0.0.0.0:8000"
exec python manage.py runserver 0.0.0.0:8000

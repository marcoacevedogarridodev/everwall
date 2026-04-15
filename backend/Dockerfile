# backend/Dockerfile con certificados
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Instalar certificados CA actualizados
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libjpeg-dev \
    zlib1g-dev \
    libffi-dev \
    curl \
    ca-certificates \
    && update-ca-certificates \
    && apt-get clean

# Configurar pip para usar SSL con certificados del sistema
RUN pip install --upgrade pip setuptools wheel

COPY requirements.txt .

# Deshabilitar verificación SSL solo para construcción (no recomendado para producción)
RUN pip install --no-cache-dir --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    docker-cli \
    curl \
    bash \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Directorio de trabajo
WORKDIR /app

## Copiar código
#COPY . /app

# 👉 SOLO dependencias (no el codigo)
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Evitar buffering de logs (logs en tiempo real)
ENV PYTHONUNBUFFERED=1

# Esto fuerza a Python a ver /app como raíz de imports.
ENV PYTHONPATH=/app/Codigo
